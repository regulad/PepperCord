from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, tzinfo
from functools import partial, reduce
from io import BytesIO
from logging import getLogger
from operator import attrgetter
from os import getcwd
from os.path import join
from random import choice
from typing import (
    Literal,
    Any,
    cast,
    Awaitable,
    Callable,
    Mapping,
    Sequence,
)

from aiofiles import open as aopen
from aiohttp import ClientSession
from aiosplatoon3ink import (
    Festivals,
    Gesotown,
    MonthlyGear,
    Region,
    Schedules,
    Splatoon3InkClient,
)
from aiosplatoon3ink.festivals import Fest, FestState
from aiosplatoon3ink.schedules import (
    BankaraMode,
    CoopSchedule,
    CoopWeapon,
    CurrentFest,
    EventSchedule,
    FestMode,
    LeagueMatchEvent,
    TimePeriod,
    VsRuleKey,
    VsSetting,
    VsStage,
)
from discord import (
    Colour,
    Embed,
    File,
    SelectOption,
    Interaction,
    Message,
    Role,
    TextChannel,
)
from discord.app_commands import Choice, choices, describe
from discord.ext import tasks
from discord.ext.commands import Cog, hybrid_group, CheckFailure, parameter
from discord.ui import Select, View
from discord.utils import format_dt, get, MISSING
from pytz import UTC as PYTZ_UTC

from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext
from utils.consts import TIME_EMOJIS
from utils.images import vrt_concat_pngs, hrz_concat_pngs
from utils.markdown_tools import bold
from utils.misc import edit_with_files_send_wrapper, FrozenDict
from utils.watch import (
    GRACE,
    FirstSeen,
    Rendered,
    WatchEvent,
    Watcher,
    add_watch,
    list_watches,
    remove_watch,
)

logger = getLogger(__name__)

# splatoon3.ink asks for a User-Agent that says who to contact: https://github.com/misenhower/splatoon3.ink/wiki/Data-Access
USER_AGENT = "PepperCord/1.0 https://github.com/regulad/PepperCord @regulad#7959"

SPLATFEST_UNSTARTED_COLOR: int = 0x666775
REGULAR_BATTLE_COLOR: int = 0xCFF622
ANARCHY_BATTLE_COLOR: int = 0xF54910
SALMON_RUN_COLOR: int = 0xFF5600
X_BATTLE_COLOR: int = 0x5D2EEF
LEAGUE_BATTLE_COLOR: int = 0xF02D7D
SPLATNET_COLOR: int = 0xEAFF3D

TIMESLOT_LONG: str = "%m/%d"
TIMESLOT_SHORT: str = "%I:%M %p"
TIMESLOT_TZ: str = "%Z"

SPLATFEST_LONG: str = "%m/%d/%y"

MODE_LITERAL = Literal[
    "Regular Battle",
    "Anarchy Battle (Series)",
    "Anarchy Battle (Open)",
    "League Battle",
    "X Battle",
    "Salmon Run",
    "Splatfest Battle (Open)",
    "Splatfest Battle (Pro)",
]
MODES: set[MODE_LITERAL] = {
    "Regular Battle",
    "Anarchy Battle (Series)",
    "Anarchy Battle (Open)",
    "League Battle",
    "X Battle",
    "Salmon Run",
    "Splatfest Battle (Open)",
    "Splatfest Battle (Pro)",
}
MODE_COLORS: FrozenDict[MODE_LITERAL, int] = FrozenDict(
    {
        "Regular Battle": REGULAR_BATTLE_COLOR,
        "Anarchy Battle (Series)": ANARCHY_BATTLE_COLOR,
        "Anarchy Battle (Open)": ANARCHY_BATTLE_COLOR,
        "League Battle": LEAGUE_BATTLE_COLOR,
        "X Battle": X_BATTLE_COLOR,
        "Salmon Run": SALMON_RUN_COLOR,
        "Splatfest Battle (Open)": SPLATFEST_UNSTARTED_COLOR,  # special case
        "Splatfest Battle (Pro)": SPLATFEST_UNSTARTED_COLOR,  # special case
    }
)
MODE_EMOJI_NAME: FrozenDict[MODE_LITERAL, str] = FrozenDict(
    {  # special because weird short names n crap
        "Regular Battle": "regular",
        "Anarchy Battle (Series)": "bankara",
        "Anarchy Battle (Open)": "bankara",
        "League Battle": "league",
        "X Battle": "xb",
        "Salmon Run": "coop",
        "Splatfest Battle (Open)": "tricolor",
        "Splatfest Battle (Pro)": "tricolor",
    }
)
# The emojis are named after SplatNet's Japanese names for the rules.
RULE_EMOJI_NAME: FrozenDict[VsRuleKey, str] = FrozenDict(
    {
        VsRuleKey.TURF_WAR: "turfwar",
        VsRuleKey.SPLAT_ZONES: "area",
        VsRuleKey.TOWER_CONTROL: "yagura",
        VsRuleKey.RAINMAKER: "hoko",
        VsRuleKey.CLAM_BLITZ: "asari",
        VsRuleKey.TRICOLOR_TURF_WAR: "tricolor",
    }
)

REGION_LITERAL = Literal["US", "EU", "JP", "AP"]
DEFAULT_REGION: REGION_LITERAL = "US"  # I guess change this if I ever move.


@dataclass(frozen=True)
class VsRotation:
    """One rotation of a battle mode, with its rule and stages if the mode is being played then."""

    period: TimePeriod
    setting: VsSetting | None
    event: LeagueMatchEvent | None = None


def vs_rotations(
    schedules: Schedules, mode: MODE_LITERAL, now: datetime | None = None
) -> list[VsRotation]:
    """Every rotation of a battle mode that hasn't ended by ``now``, in order."""
    rotations: list[VsRotation]
    match mode:
        case "Regular Battle":
            rotations = [
                VsRotation(node, node.regular_match_setting)
                for node in schedules.regular_schedules
            ]
        case "Anarchy Battle (Series)":
            rotations = [
                VsRotation(node, node.setting(BankaraMode.SERIES))
                for node in schedules.bankara_schedules
            ]
        case "Anarchy Battle (Open)":
            rotations = [
                VsRotation(node, node.setting(BankaraMode.OPEN))
                for node in schedules.bankara_schedules
            ]
        case "X Battle":
            rotations = [
                VsRotation(node, node.x_match_setting) for node in schedules.x_schedules
            ]
        case "Splatfest Battle (Open)":
            rotations = [
                VsRotation(node, node.setting(FestMode.OPEN))
                for node in schedules.fest_schedules
            ]
        case "Splatfest Battle (Pro)":
            rotations = [
                VsRotation(node, node.setting(FestMode.PRO))
                for node in schedules.fest_schedules
            ]
        case "League Battle":
            # Challenges replaced League Battle. Each runs in several separate periods, which stand in for rotations.
            rotations = sorted(
                (
                    VsRotation(
                        period,
                        event.league_match_setting,
                        event.league_match_setting.league_match_event,
                    )
                    for event in schedules.event_schedules
                    for period in event.time_periods
                ),
                key=lambda rotation: rotation.period.start_time,
            )
        case "Salmon Run":
            raise ValueError("Salmon Run has no battle rotations.")
    now = now or datetime.now(UTC)
    return [rotation for rotation in rotations if rotation.period.end_time > now]


def salmon_run_rotations(
    schedules: Schedules, now: datetime | None = None
) -> list[CoopSchedule]:
    """Every Salmon Run rotation that hasn't ended by ``now``, in order, with Big Runs in their place."""
    now = now or datetime.now(UTC)
    coop = schedules.coop_grouping_schedule
    # Regular Salmon Run pauses while a Big Run is on, so a Big Run takes its place in the rotations.
    return sorted(
        (
            node
            for node in (*coop.regular_schedules, *coop.big_run_schedules)
            if node.end_time > now
        ),
        key=lambda node: node.start_time,
    )


# What a channel can watch, and what each topic posts. Discord shows these as the topic's choices.
TOPICS: FrozenDict[str, str] = FrozenDict(
    {
        "regular": "Each new Regular Battle rotation",
        "anarchy-series": "Each new Anarchy Battle (Series) rotation",
        "anarchy-open": "Each new Anarchy Battle (Open) rotation",
        "x": "Each new X Battle rotation",
        "splatfest-open": "Each new Splatfest Battle (Open) rotation",
        "splatfest-pro": "Each new Splatfest Battle (Pro) rotation",
        "challenge": "Each Challenge, when it's announced and each time it's on",
        "salmon-run": "Each Salmon Run rotation, and each Big Run and Eggstra Work",
        "splatfest": "Each Splatfest: announced, started, second half and results",
        "gear": "SplatNet's brand of the day, and each month's Salmon Run reward gear",
    }
)
TOPIC_MODES: FrozenDict[str, MODE_LITERAL] = FrozenDict(
    {
        "regular": "Regular Battle",
        "anarchy-series": "Anarchy Battle (Series)",
        "anarchy-open": "Anarchy Battle (Open)",
        "x": "X Battle",
        "splatfest-open": "Splatfest Battle (Open)",
        "splatfest-pro": "Splatfest Battle (Pro)",
    }
)
# How long after a Splatfest ends its results are still news.
SPLATFEST_RESULTS_WINDOW = timedelta(days=3)


class Splatoon3Watch:
    """What Splatoon 3 can be watched for, derived from the cog's copies of splatoon3.ink's feeds.

    Rotations, Challenge periods and Splatfests' start and second half are dated in the feeds. Announcements, results
    and the shop's brand of the day only show up in them, so they're dated by when the bot first noticed them.
    """

    namespace = "splatoon3"
    name = "Splatoon 3"
    topics: Mapping[str, str] = TOPICS

    def __init__(self, cog: "Splatoon3") -> None:
        self.cog = cog
        self.first_seen = FirstSeen()

    def events(self, now: datetime) -> list[WatchEvent]:
        events: list[WatchEvent] = []
        schedules = self.cog.schedules
        if schedules is not None:
            events += self._rotations(schedules, now)
            events += self._challenges(schedules, now)
            events += self._salmon_run(schedules, now)
            if self.cog.festivals is not None:
                events += self._splatfests(
                    self.cog.festivals, schedules.current_fest, now
                )
        events += self._gear(now)
        self.first_seen.forget_all_but(event.key for event in events)
        return events

    def _noticed(
        self,
        key: str,
        topic: str,
        now: datetime,
        expires: datetime,
        render: Callable[[], Awaitable[Rendered]],
    ) -> WatchEvent:
        return WatchEvent(key, topic, self.first_seen(key, now), expires, render)

    def _rotations(self, schedules: Schedules, now: datetime) -> list[WatchEvent]:
        events: list[WatchEvent] = []
        for topic, mode in TOPIC_MODES.items():
            for rotation in vs_rotations(schedules, mode, now):
                if rotation.setting is None or rotation.period.start_time > now:
                    continue
                events.append(
                    WatchEvent.dated(
                        f"{topic}:{rotation.period.start_time.isoformat()}",
                        topic,
                        rotation.period.start_time,
                        partial(
                            self._render_vs,
                            schedules,
                            mode,
                            rotation,
                            f"A new {mode} rotation has started.",
                        ),
                        ends=rotation.period.end_time,
                    )
                )
        return events

    def _challenges(self, schedules: Schedules, now: datetime) -> list[WatchEvent]:
        events: list[WatchEvent] = []
        for challenge in schedules.event_schedules:
            setting = challenge.league_match_setting
            info = setting.league_match_event
            periods = sorted(challenge.time_periods, key=lambda p: p.start_time)
            if not periods:
                continue
            # A Challenge can come back, so its first period tells this run from the last.
            ident = f"challenge:{info.league_match_event_id}:{periods[0].start_time.isoformat()}"
            events.append(
                self._noticed(
                    f"{ident}:announced",
                    "challenge",
                    now,
                    periods[0].start_time,
                    partial(self._render_challenge, schedules, challenge),
                )
            )
            for period in periods:
                if period.start_time <= now:
                    events.append(
                        WatchEvent.dated(
                            f"{ident}:{period.start_time.isoformat()}",
                            "challenge",
                            period.start_time,
                            partial(
                                self._render_vs,
                                schedules,
                                "League Battle",
                                VsRotation(period, setting, info),
                                f"The {info.name} Challenge is on now.",
                            ),
                            ends=period.end_time,
                        )
                    )
        return events

    def _salmon_run(self, schedules: Schedules, now: datetime) -> list[WatchEvent]:
        events: list[WatchEvent] = []
        coop = schedules.coop_grouping_schedule
        for kind, nodes, called in (
            ("Salmon Run", coop.regular_schedules, "A new Salmon Run rotation"),
            ("Big Run", coop.big_run_schedules, "A Big Run"),
            ("Eggstra Work", coop.team_contest_schedules, "Eggstra Work"),
        ):
            for node in nodes:
                ident = f"salmon-run:{kind.lower().replace(' ', '-')}:{node.start_time.isoformat()}"
                if node.start_time <= now:
                    events.append(
                        WatchEvent.dated(
                            ident,
                            "salmon-run",
                            node.start_time,
                            partial(
                                self._render_salmon_run,
                                node,
                                kind,
                                f"{called} has started.",
                            ),
                            ends=node.end_time,
                        )
                    )
                elif kind != "Salmon Run":
                    events.append(
                        self._noticed(
                            f"{ident}:announced",
                            "salmon-run",
                            now,
                            node.start_time,
                            partial(
                                self._render_salmon_run,
                                node,
                                kind,
                                f"{called} is coming {format_dt(node.start_time, 'R')}.",
                            ),
                        )
                    )
        return events

    def _splatfests(
        self, festivals: Festivals, current_fest: CurrentFest | None, now: datetime
    ) -> list[WatchEvent]:
        events: list[WatchEvent] = []
        for fest in festivals.in_region(Region(DEFAULT_REGION)):
            if fest.end_time + SPLATFEST_RESULTS_WINDOW < now:
                continue  # long over: nothing about it is news
            ident = f"splatfest:{fest.splatoon3ink_id}"
            # The schedules' current Splatfest has its exact midterm and its Tricolor stages.
            current = (
                current_fest
                if current_fest is not None
                and current_fest.start_time == fest.start_time
                else None
            )
            if fest.start_time > now:
                events.append(
                    self._noticed(
                        f"{ident}:announced",
                        "splatfest",
                        now,
                        fest.start_time,
                        partial(
                            self._render_splatfest,
                            fest,
                            current,
                            f"A new Splatfest has been announced: {fest.title}",
                        ),
                    )
                )
            else:
                events.append(
                    WatchEvent.dated(
                        f"{ident}:started",
                        "splatfest",
                        fest.start_time,
                        partial(
                            self._render_splatfest,
                            fest,
                            current,
                            f"The Splatfest has started: {fest.title}",
                        ),
                        ends=fest.end_time,
                    )
                )
                midterm = (
                    current.midterm_time
                    if current is not None
                    else fest.start_time + (fest.end_time - fest.start_time) / 2
                )
                if midterm <= now:
                    events.append(
                        WatchEvent.dated(
                            f"{ident}:second-half",
                            "splatfest",
                            midterm,
                            partial(
                                self._render_splatfest,
                                fest,
                                current,
                                "The Splatfest's second half has started, and with it Tricolor Turf War.",
                            ),
                            ends=fest.end_time,
                        )
                    )
            if fest.has_results:
                events.append(
                    self._noticed(
                        f"{ident}:results",
                        "splatfest",
                        now,
                        fest.end_time + SPLATFEST_RESULTS_WINDOW,
                        partial(
                            self._render_splatfest,
                            fest,
                            None,
                            f"The results of {fest.title} are in!",
                        ),
                    )
                )
        return events

    def _gear(self, now: datetime) -> list[WatchEvent]:
        events: list[WatchEvent] = []
        if (gesotown := self.cog.gear) is not None:
            pickup = gesotown.pickup_brand
            events.append(
                self._noticed(
                    f"gear:brand:{pickup.brand.id}:{pickup.sale_end_time.isoformat()}",
                    "gear",
                    now,
                    pickup.sale_end_time,
                    partial(self._render_brand, gesotown),
                )
            )
        if (monthly := self.cog.monthly_gear) is not None:
            key = f"gear:monthly:{monthly.splatoon3ink_id}"
            events.append(
                self._noticed(
                    key,
                    "gear",
                    now,
                    self.first_seen(key, now) + GRACE,
                    partial(self._render_monthly_gear, monthly),
                )
            )
        return events

    async def _render_vs(
        self,
        schedules: Schedules,
        mode: MODE_LITERAL,
        rotation: VsRotation,
        content: str,
    ) -> Rendered:
        embed, files = await self.cog.vs_message(schedules, mode, rotation)
        return Rendered(content, embed, tuple(files))

    async def _render_challenge(
        self, schedules: Schedules, challenge: EventSchedule
    ) -> Rendered:
        setting = challenge.league_match_setting
        info = setting.league_match_event
        periods = sorted(challenge.time_periods, key=lambda p: p.start_time)
        embed, files = await self.cog.vs_message(
            schedules, "League Battle", VsRotation(periods[0], setting, info)
        )
        embed.add_field(
            name="Times",
            value="\n".join(
                f"{format_dt(period.start_time, 'f')} to {format_dt(period.end_time, 't')}"
                for period in periods
            )[:1024],
            inline=False,
        ).add_field(
            name="Rules",
            value=info.regulation.replace("<br />", "\n")[:1024],
            inline=False,
        )
        return Rendered(f"A new Challenge is coming: {info.name}.", embed, tuple(files))

    async def _render_salmon_run(
        self, rotation: CoopSchedule, kind: str, content: str
    ) -> Rendered:
        embed, files = await self.cog.salmon_run_message(rotation, kind)
        return Rendered(content, embed, tuple(files))

    async def _render_splatfest(
        self, fest: Fest, current: CurrentFest | None, content: str
    ) -> Rendered:
        embed, files = await self.cog.splatfest_message(
            fest, current, relative=not fest.has_results
        )
        return Rendered(content, embed, tuple(files))

    async def _render_brand(self, gesotown: Gesotown) -> Rendered:
        embed, files = await self.cog.brand_message(gesotown)
        return Rendered(
            f"SplatNet's brand of the day is {gesotown.pickup_brand.brand.name}.",
            embed,
            tuple(files),
        )

    async def _render_monthly_gear(self, gear: MonthlyGear) -> Rendered:
        embed, files = await self.cog.monthly_gear_message(gear)
        return Rendered(
            f"This month's Salmon Run reward gear is {gear.name}.", embed, tuple(files)
        )


class TimeSlotData:  # This could probably extend SelectOption, but this is separate for the sake of selfbot support.
    def __init__(
        self, start: datetime, end: datetime, index: int, mode: MODE_LITERAL
    ) -> None:
        self.start: datetime = start
        self.end: datetime = end
        self.index: int = index
        self.mode: str = mode

    @classmethod
    def from_nodes(
        cls,
        nodes: Sequence[TimePeriod],
        mode: MODE_LITERAL,
    ) -> list["TimeSlotData"]:
        return [
            cls(node.start_time, node.end_time, index, mode)
            for index, node in enumerate(nodes)
        ]

    __slots__ = ("start", "end", "index", "mode")

    @property
    def name(self) -> str:
        now: datetime = datetime.now()
        ctz: tzinfo = now.tzinfo or PYTZ_UTC
        return (
            f"{self.start.astimezone(ctz).strftime(TIMESLOT_SHORT)} "
            f"- {self.end.astimezone(ctz).strftime(TIMESLOT_SHORT)} "
            f"({self.index + 1})"
        )

    @property
    def description(self) -> str:
        now: datetime = datetime.now()
        ctz: tzinfo = now.tzinfo or PYTZ_UTC
        now = now.astimezone(ctz)  # weird.
        return (
            f"{self.start.astimezone(ctz).strftime(TIMESLOT_LONG)} "
            f"- {self.end.astimezone(ctz).strftime(TIMESLOT_LONG)} "
            f"({now.strftime(TIMESLOT_TZ)})"
        )

    @property
    def emoji(self) -> str:
        now: datetime = datetime.now()
        ctz: tzinfo = now.tzinfo or PYTZ_UTC
        localized_start: datetime = self.start.astimezone(ctz)

        hour_str: str = localized_start.strftime("%I")
        hour: int = int(hour_str)

        while hour > 11:
            hour -= 12

        return TIME_EMOJIS[hour]

    def __repr__(self) -> str:
        return f"<TimeSlotData start={self.start} end={self.end} index={self.index}>"


class SplatfestData:  # Same deal as above with SelectOption
    def __init__(self, name: str, start: datetime, end: datetime, index: int) -> None:
        self.name: str = name
        self.start: datetime = start
        self.end: datetime = end
        self.index: int = index

    __slots__ = ("name", "start", "end", "index")

    @property
    def description(self) -> str:
        now: datetime = datetime.now()
        ctz: tzinfo = now.tzinfo or PYTZ_UTC
        now = now.astimezone(ctz)  # weird.
        return (
            f"{self.start.astimezone(ctz).strftime(SPLATFEST_LONG)} "
            f"- {self.end.astimezone(ctz).strftime(SPLATFEST_LONG)} "
            f"({now.strftime(TIMESLOT_TZ)})"
        )

    @classmethod
    def from_nodes(cls, nodes: Sequence[Fest]) -> list["SplatfestData"]:
        return [
            cls(node.title, node.start_time, node.end_time, index)
            for index, node in enumerate(nodes)
        ]


class ScheduleSelectionMenu(Select["ScheduleView"]):
    def __init__(
        self,
        ctx: CustomContext,
        data: list[TimeSlotData],
        mode: MODE_LITERAL,
        **attrs: Any,  # TODO: better passthrough kwargs
    ) -> None:
        self.ctx: CustomContext = ctx
        self.data: list[TimeSlotData] = data
        self.game: MODE_LITERAL = mode

        self.splatoon_3_cog: "Splatoon3" = cast(
            "Splatoon3", self.ctx.bot.get_cog("Splatoon3")
        )

        options: list[SelectOption] = [
            SelectOption(
                label=timeslot.name,
                emoji=timeslot.emoji,
                description=timeslot.description,
            )
            for timeslot in data
        ]

        super().__init__(
            placeholder="Select Time Window...",
            options=options,
            min_values=1,
            max_values=1,
            **attrs,
        )

    async def callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()

        # Each option is named after one of self.data, and the user can't pick anything else.
        timeslot = cast(TimeSlotData, get(self.data, name=self.values[0]))

        await self.splatoon_3_cog.send_schedule(
            self.ctx,
            self.game,
            timeslot.index,
            lambda *args, **kwargs: edit_with_files_send_wrapper(
                self.ctx["response"].edit, *args, **kwargs
            ),
        )


class ModeSelectionMenu(Select["ScheduleView"]):
    def __init__(
        self, ctx: CustomContext, **attrs: Any
    ) -> None:  # TODO: better kwarg passthrough
        self.ctx = ctx

        self.splatoon_3_cog = cast("Splatoon3", self.ctx.bot.get_cog("Splatoon3"))

        options: list[SelectOption] = [
            SelectOption(
                label=mode,
                emoji=ctx.bot.get_custom_emoji(MODE_EMOJI_NAME[mode]),
            )
            for mode in MODES
        ]

        super().__init__(
            placeholder="Select Game Mode...",
            options=options,
            min_values=1,
            max_values=1,
            **attrs,
        )

    async def callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()

        await self.splatoon_3_cog.send_schedule(
            self.ctx,
            cast(MODE_LITERAL, self.values[0]),
            0,
            lambda *args, **kwargs: edit_with_files_send_wrapper(
                self.ctx["response"].edit, *args, **kwargs
            ),
        )


class SplatfestSelectionMenu(Select["SplatfestView"]):
    def __init__(
        self,
        ctx: CustomContext,
        data: list[SplatfestData],
        region: REGION_LITERAL = DEFAULT_REGION,
        **attrs: Any,  # TODO: Better kwarg passthrough
    ) -> None:
        self.ctx: CustomContext = ctx
        self.data: list[SplatfestData] = data
        self.region: REGION_LITERAL = region

        self.splatoon_3_cog: "Splatoon3" = cast(
            "Splatoon3", self.ctx.bot.get_cog("Splatoon3")
        )

        options: list[SelectOption] = [
            SelectOption(
                label=splatfest.name,
                description=splatfest.description,
                emoji=ctx.bot.get_custom_emoji("tricolor.png"),
            )
            # A select menu takes at most 25 options. The feed lists the newest first, and has had more than 25.
            for splatfest in data[:25]
        ]

        super().__init__(
            placeholder="Select Splatfest...",
            options=options,
            min_values=1,
            max_values=1,
            **attrs,
        )

    async def callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()

        # Each option is named after one of self.data, and the user can't pick anything else.
        timeslot = cast(SplatfestData, get(self.data, name=self.values[0]))

        await self.splatoon_3_cog.send_splatfest(
            self.ctx,
            False,
            timeslot.index,
            self.region,
            lambda *args, **kwargs: edit_with_files_send_wrapper(
                self.ctx["response"].edit, *args, **kwargs
            ),
        )


class ScheduleView(View):
    def __init__(
        self,
        ctx: CustomContext,
        data: list[TimeSlotData],
        mode: MODE_LITERAL,
        **attrs: Any,  # TODO: Better kwarg passthrough
    ) -> None:
        self.ctx: CustomContext = ctx
        self.data: list[TimeSlotData] = data
        self.game: MODE_LITERAL = mode

        super().__init__(**attrs)

        self.add_item(ScheduleSelectionMenu(ctx, data, mode))
        self.add_item(ModeSelectionMenu(ctx))


class SplatfestView(View):
    def __init__(
        self,
        ctx: CustomContext,
        data: list[SplatfestData],
        region: REGION_LITERAL,
        **attrs: Any,  # TODO: Better kwarg passthrough
    ) -> None:
        self.ctx: CustomContext = ctx
        self.data: list[SplatfestData] = data
        self.game: REGION_LITERAL = region

        super().__init__(**attrs)

        self.add_item(SplatfestSelectionMenu(ctx, data, region))


class Splatoon3(Cog):
    """
    Get information about the current status of Splatoon 3.
    Powered by https://splatoon3.ink/ and https://splatoonwiki.org/wiki/
    """

    def __init__(self, bot: CustomBot) -> None:
        self.bot: CustomBot = bot
        self.cs: ClientSession | None = None
        self.client: Splatoon3InkClient | None = None

        self.schedules: Schedules | None = None
        self.monthly_gear: MonthlyGear | None = None
        self.festivals: Festivals | None = None
        self.gear: Gesotown | None = None  # only watches use it

        self.watcher = Watcher(bot, Splatoon3Watch(self))

    async def _fetch[T](self, feed: str, fetch: Callable[[], Awaitable[T]]) -> T | None:
        try:
            return await fetch()
        except Exception:
            logger.exception(f"Couldn't fetch {feed} from splatoon3.ink.")
            return None

    @tasks.loop(hours=1)
    async def update_cache(self) -> None:
        # splatoon3.ink updates hourly and asks to be cached: https://github.com/misenhower/splatoon3.ink/wiki/Data-Access
        # A tasks.loop stops for good on an error it doesn't treat as a dropped connection, so each feed is fetched on
        # its own, and one that fails keeps its last copy until the next hour.
        if self.client is None:
            return
        if (
            schedules := await self._fetch("schedules", self.client.schedules)
        ) is not None:
            self.schedules = schedules
        if (
            gear := await self._fetch("monthly gear", self.client.monthly_gear)
        ) is not None:
            self.monthly_gear = gear
        if (
            festivals := await self._fetch("festivals", self.client.festivals)
        ) is not None:
            self.festivals = festivals
        if (
            gesotown := await self._fetch("SplatNet's shop", self.client.gear)
        ) is not None:
            self.gear = gesotown

    @property
    def is_ready(self) -> bool:
        return all(
            (
                self.schedules is not None,
                self.monthly_gear is not None,
                self.festivals is not None,
            )
        )

    async def cog_check(self, ctx: CustomContext) -> bool:  # type: ignore[override]  # d.py bad export
        if self.is_ready:
            return True
        else:
            raise CheckFailure(
                "We are still preparing, hold on! The cache is being populated."
            )

    @Cog.listener()
    async def on_ready(self) -> None:
        # on_ready fires again after every new gateway session, and starting a running loop raises.
        if not self.update_cache.is_running():
            self.update_cache.start()
        self.watcher.start()

    async def cog_load(self) -> None:
        self.cs = ClientSession(headers={"User-Agent": USER_AGENT})
        self.client = Splatoon3InkClient(USER_AGENT, session=self.cs)

    async def cog_unload(self) -> None:
        if self.cs is not None and not self.cs.closed:
            await self.cs.close()
        if self.update_cache.is_running():
            self.update_cache.cancel()
        self.watcher.stop()

    async def _make_salmon_run_thumbnail(
        self, weapons: Sequence[CoopWeapon]
    ) -> bytes | None:
        assert self.cs is not None

        weapon_urls = [weapon.image.url for weapon in weapons]

        weapon_pngs: list[bytes] = []

        for weapon_url in weapon_urls:
            async with self.cs.get(weapon_url) as resp:
                weapon_pngs.append(await resp.read())

        if len(weapons) == 4:
            set_1: bytes = await self.bot.loop.run_in_executor(
                None, hrz_concat_pngs, *weapon_pngs[:2]  # type: ignore[arg-type]  # it is compatible.
            )
            set_2: bytes = await self.bot.loop.run_in_executor(
                None, hrz_concat_pngs, *weapon_pngs[2:]  # type: ignore[arg-type]  # it is compatible.
            )
            return await self.bot.loop.run_in_executor(
                None, vrt_concat_pngs, set_1, set_2
            )
        else:
            return None  # TODO: Handle this case (probably for special weapons)

    async def _make_two_stage_image(self, vs_stages: Sequence[VsStage]) -> bytes:
        assert self.cs is not None

        async with self.cs.get(vs_stages[0].image.url) as resp:
            stage1_png: bytes = await resp.read()

        async with self.cs.get(vs_stages[1].image.url) as resp:
            stage2_png: bytes = await resp.read()

        return await self.bot.loop.run_in_executor(
            None, vrt_concat_pngs, stage1_png, stage2_png
        )

    async def _favicon(self) -> tuple[str, bytes]:
        async with aopen(
            join(getcwd(), "resources", "images", "splatoon3", "favicon.png"), "rb"
        ) as fp:
            return "favicon.png", await fp.read()

    @staticmethod
    def _credit(embed: Embed) -> Embed:
        return embed.set_footer(
            text="Powered by https://splatoon3.ink/",
            icon_url="attachment://favicon.png",
        )

    async def vs_message(
        self, schedules: Schedules, mode: MODE_LITERAL, rotation: VsRotation | None
    ) -> tuple[Embed, list[tuple[str, bytes]]]:
        """A battle rotation's embed and files, or a note that the mode isn't being played."""
        files = [await self._favicon()]

        color: int = MODE_COLORS[mode]
        if (
            mode in ("Splatfest Battle (Open)", "Splatfest Battle (Pro)")
            and schedules.current_fest is not None
        ):
            color = Colour.from_rgb(
                *choice(schedules.current_fest.teams).color.rgb
            ).value

        if rotation is None or rotation.setting is None:
            embed = self._credit(
                Embed(
                    title=mode,
                    color=color,
                    description="This game mode is not currently available.",
                )
            )
            return embed, files

        vsmatch_settings = rotation.setting
        rule_emoji = self.bot.get_custom_emoji(
            f"{RULE_EMOJI_NAME[vsmatch_settings.vs_rule.rule]}.png"
        )
        description = f"{vsmatch_settings.vs_rule.name} {rule_emoji or ''}"
        if rotation.event is not None:
            # SplatNet breaks the summary where the game wraps it.
            summary = rotation.event.desc.replace("<br />", " ")
            description = f"**{rotation.event.name}**: {summary}\n{description}"

        files.append(
            ("stages.png", await self._make_two_stage_image(vsmatch_settings.vs_stages))
        )

        embed = self._credit(
            Embed(
                title=f"{mode} "
                f"{self.bot.get_custom_emoji(f'{MODE_EMOJI_NAME[mode]}.png') or ''}",
                color=color,
                description=description,
            )
            .add_field(
                name="Start Time",
                value=format_dt(rotation.period.start_time, "R"),
            )
            .add_field(
                name="End Time",
                value=format_dt(rotation.period.end_time, "R"),
            )
            .add_field(
                name="Stage 1",
                value=vsmatch_settings.vs_stages[0].name,
                inline=False,
            )
            .add_field(
                name="Stage 2",
                value=vsmatch_settings.vs_stages[1].name,
            )
            .set_image(url="attachment://stages.png")
        )
        return embed, files

    async def salmon_run_message(
        self, rotation: CoopSchedule, title: str
    ) -> tuple[Embed, list[tuple[str, bytes]]]:
        """A Salmon Run rotation's embed and files."""
        files = [await self._favicon()]
        setting = rotation.setting

        embed = Embed(title=title, color=SALMON_RUN_COLOR)

        salmon_run_thumbnail_bytes = await self._make_salmon_run_thumbnail(
            setting.weapons
        )
        if salmon_run_thumbnail_bytes is not None:
            embed = embed.set_thumbnail(url="attachment://weapons.png")
            files.append(("weapons.png", salmon_run_thumbnail_bytes))

        embed = self._credit(
            embed.add_field(
                name="Start Time",
                value=format_dt(rotation.start_time, "R"),
            )
            .add_field(name="End Time", value=format_dt(rotation.end_time, "R"))
            .add_field(
                name="Stage",
                value=setting.coop_stage.name,
            )
            .set_image(url=setting.coop_stage.image.url)
        )

        for weapon_index, weapon in enumerate(setting.weapons):
            embed = embed.add_field(
                name=f"Weapon {weapon_index + 1}",
                value=weapon.name,
                inline=False,
            )
        return embed, files

    async def splatfest_message(
        self, fest: Fest, current_fest: CurrentFest | None, relative: bool
    ) -> tuple[Embed, list[tuple[str, bytes]]]:
        """A Splatfest's embed and files.

        With the schedules' ``current_fest`` for it, the embed has the exact midterm and the Tricolor stages, which
        aren't kept for other Splatfests; without, it has the results, if they're in. ``relative`` shows times relative
        to now rather than as dates.
        """
        assert self.cs is not None
        files = [await self._favicon()]

        start_time: datetime = fest.start_time
        end_time: datetime = fest.end_time

        color: int = (
            SPLATFEST_UNSTARTED_COLOR
            if fest.state is FestState.SCHEDULED
            else Colour.from_rgb(*choice(fest.teams).color.rgb).value
        )

        embed = self._credit(
            Embed(
                title=fest.title,
                description=fest.state.replace("_", " ").title(),
                color=color,
            )
            .add_field(
                name="Start Time",
                value=format_dt(start_time, "R" if relative else "D"),
            )
            .add_field(
                name="End Time",
                value=format_dt(end_time, "R" if relative else "D"),
            )
        )

        if current_fest is not None:
            # Midterm & tricolor data is only available for the current splatfest
            tricolor_stages = current_fest.tricolor_stages or ()

            embed = embed.add_field(
                name="Midterm Time",
                value=format_dt(current_fest.midterm_time, "R" if relative else "D"),
            ).add_field(
                name=(
                    "Tricolor Stages" if len(tricolor_stages) > 1 else "Tricolor Stage"
                ),
                value=", ".join(stage.name for stage in tricolor_stages)
                or "Not announced yet.",
                inline=False,
            )
        else:
            midterm = start_time + (end_time - start_time) / 2
            # approx. since we do not have exact

            embed = embed.add_field(
                name="Midterm Time",
                value=f"{format_dt(midterm, 'R' if relative else 'D')} (approx.)",
            ).add_field(
                name="Tricolor Stage",
                value=(
                    "This data is not stored for previous Splatfests."
                    if fest.state is FestState.CLOSED
                    else "Not announced yet."
                ),
                inline=False,
            )

        if current_fest is None and fest.has_results:
            for team in fest.teams:
                result = team.result
                if result is None:
                    continue

                if result.is_winner:
                    embed.color = Colour.from_rgb(*team.color.rgb)

                # Each figure is the team's share of a category, named as splatoon3.ink names it. Early Splatfests
                # didn't count Tricolor Battles.
                categories: list[tuple[str, float | None, bool | None]] = [
                    ("Votes", result.vote_ratio, result.is_vote_ratio_top),
                    (
                        "Conch Shells",
                        result.horagai_ratio,
                        result.is_horagai_ratio_top,
                    ),
                    (
                        "Open",
                        result.regular_contribution_ratio,
                        result.is_regular_contribution_ratio_top,
                    ),
                    (
                        "Pro",
                        result.challenge_contribution_ratio,
                        result.is_challenge_contribution_ratio_top,
                    ),
                    (
                        "Tricolor Battle",
                        result.tricolor_contribution_ratio,
                        result.is_tricolor_contribution_ratio_top,
                    ),
                ]
                lines = [
                    f"Color: `{Colour.from_rgb(*team.color.rgb)}`",
                    bold(
                        f"Was victorious: {'Yes' if result.is_winner else 'No'}",
                        result.is_winner,
                    ),
                    *(
                        bold(f"{name}: `{ratio * 100:.2f}`%", bool(top))
                        for name, ratio, top in categories
                        if ratio is not None
                    ),
                ]

                embed = embed.add_field(
                    name=team.team_name,
                    value="\n".join(lines),
                    inline=True,
                )
        else:
            for team in fest.teams:
                embed = embed.add_field(
                    name=team.team_name,
                    value=f"Color: `{Colour.from_rgb(*team.color.rgb)}`",
                    inline=True,
                )

        if current_fest is not None and current_fest.tricolor_stages:
            pngs: list[bytes] = []
            for url in (
                fest.image.url,
                *(stage.image.url for stage in current_fest.tricolor_stages),
            ):
                async with self.cs.get(url) as resp:
                    pngs.append(await resp.read())

            final_png: bytes = await self.bot.loop.run_in_executor(
                None, reduce, vrt_concat_pngs, pngs
            )

            files.append(("image.png", final_png))

            embed = embed.set_image(url="attachment://image.png")
        else:
            embed = embed.set_image(url=fest.image.url)

        return embed, files

    async def monthly_gear_message(
        self, gear: MonthlyGear
    ) -> tuple[Embed, list[tuple[str, bytes]]]:
        """The month's Salmon Run reward gear's embed and files."""
        embed = self._credit(
            Embed(title="Salmon Run Gear", color=SALMON_RUN_COLOR)
            .add_field(name="Name", value=gear.name)
            .add_field(name="Slot", value=gear.kind.value)
            .set_image(url=gear.image.url)
        )
        return embed, [await self._favicon()]

    async def brand_message(
        self, gesotown: Gesotown
    ) -> tuple[Embed, list[tuple[str, bytes]]]:
        """SplatNet's brand of the day's embed and files."""
        pickup = gesotown.pickup_brand
        embed = Embed(
            title=f"Brand of the day: {pickup.brand.name}",
            description=f"On sale until {format_dt(pickup.sale_end_time, 'R')}.",
            color=SPLATNET_COLOR,
        )
        if pickup.brand.usual_gear_power is not None:
            embed.add_field(
                name="Common ability", value=pickup.brand.usual_gear_power.name
            )
        embed.add_field(name="Tomorrow's brand", value=pickup.next_brand.name)
        for sale in pickup.brand_gears:
            embed.add_field(
                name=sale.gear.name,
                value=f"{sale.gear.primary_gear_power.name}, {sale.price:,} coins",
                inline=False,
            )
        return self._credit(embed.set_image(url=pickup.image.url)), [
            await self._favicon()
        ]

    async def send_schedule(
        self,
        ctx: CustomContext,
        mode: MODE_LITERAL,
        index: int,
        send: Callable[..., Awaitable[Message]] = MISSING,
    ) -> Message:
        """Send a schedule message with embed, file, and view."""
        if self.schedules is None:
            raise RuntimeError("Couldn't get the schedule!")
        schedules = self.schedules

        if send is MISSING:
            send = ctx.send

        timeslots: list[TimeSlotData]
        if mode == "Salmon Run":
            salmon_run = salmon_run_rotations(schedules)
            timeslots = TimeSlotData.from_nodes(salmon_run, mode)
            rotation = salmon_run[index]
            big_run = rotation in schedules.coop_grouping_schedule.big_run_schedules
            embed, files = await self.salmon_run_message(
                rotation, "Big Run" if big_run else "Salmon Run"
            )
        else:  # All other modes
            rotations = vs_rotations(schedules, mode)
            timeslots = TimeSlotData.from_nodes(
                [rotation.period for rotation in rotations], mode
            )
            embed, files = await self.vs_message(
                schedules, mode, rotations[index] if index < len(rotations) else None
            )

        return await send(
            embed=embed,
            files=[File(fp=BytesIO(data), filename=name) for name, data in files],
            view=ScheduleView(ctx, timeslots, mode) if len(timeslots) > 0 else None,
        )

    async def send_splatfest(
        self,
        ctx: CustomContext,
        current: bool = True,
        index: int = 0,
        region: REGION_LITERAL = DEFAULT_REGION,
        send: Callable[..., Awaitable[Message]] = MISSING,
    ) -> Message:
        assert self.festivals is not None
        assert self.schedules is not None

        if send is MISSING:
            send = ctx.send

        if current and index != 0:
            raise RuntimeError("Index must be 0 for a current splatfest")

        nodes = self.festivals.in_region(Region(region))
        current_fest = self.schedules.current_fest
        historic_splatfests: list[SplatfestData] = SplatfestData.from_nodes(nodes)

        if current and current_fest is None:
            embed = self._credit(
                Embed(
                    title="Splatfest",
                    color=SPLATFEST_UNSTARTED_COLOR,
                    description="There is no Splatfest currently running.",
                )
            )
            files = [await self._favicon()]
        else:
            embed, files = await self.splatfest_message(
                nodes[index], current_fest if current else None, relative=current
            )

        return await send(
            embed=embed,
            files=[File(fp=BytesIO(data), filename=name) for name, data in files],
            view=None if current else SplatfestView(ctx, historic_splatfests, region),
        )

    @hybrid_group(aliases=["splat", "splatoon", "sp", "sp3"], fallback="schedule")  # type: ignore[arg-type]  # bad d.py export
    @describe(mode="The game mode to get information about.")
    async def splatoon3(
        self, ctx: CustomContext, *, mode: MODE_LITERAL = "Regular Battle"
    ) -> None:
        """
        Get information about the current scheduele of different game modes in Splatoon 3.
        Powered by https://splatoon3.ink/
        """
        async with ctx.typing():
            await self.send_schedule(ctx, mode, 0)

    # Todo: current version command? setup bs4 for scraping inkpedia but didnt finish

    @splatoon3.command()  # type: ignore[arg-type]  # bad d.py export
    @describe(
        current="If information should be gathered on current or historic Splatfests.",
        region="The region to get information about. Splatfests may vary between regions.",
    )
    async def splatfest(
        self,
        ctx: CustomContext,
        current: bool = True,
        *,
        region: REGION_LITERAL = DEFAULT_REGION,
    ) -> None:
        """
        Get information on the current splatfest or historical information on a splatfest.
        Powered by https://splatoon3.ink/
        """
        async with ctx.typing():
            await self.send_splatfest(ctx, current, 0, region)

    @splatoon3.command()  # type: ignore[arg-type]  # bad d.py export
    async def salmon_run_gear(self, ctx: CustomContext) -> None:
        """
        Get information on this month's Salmon Run gear.
        Powered by https://splatoon3.ink/
        """
        assert self.monthly_gear is not None

        async with ctx.typing():
            embed, files = await self.monthly_gear_message(self.monthly_gear)
            await ctx.send(
                embed=embed,
                files=[File(fp=BytesIO(data), filename=name) for name, data in files],
            )

    @splatoon3.group(name="watch")  # type: ignore[arg-type]  # bad d.py export
    async def watch(self, ctx: CustomContext) -> None:
        """
        Post Splatoon 3 updates in a channel as they happen.
        Powered by https://splatoon3.ink/
        """
        if ctx.invoked_subcommand is None:
            await list_watches(ctx, self.watcher)

    @watch.command(name="add")  # type: ignore[arg-type]  # bad d.py export
    @describe(
        topic="What to post.",
        channel="The channel to post in, if not this one.",
        dms="Post in your direct messages instead.",
        role="A role to mention with each update.",
    )
    @choices(topic=[Choice(name=name, value=topic) for topic, name in TOPICS.items()])
    async def watch_add(
        self,
        ctx: CustomContext,
        topic: str,
        channel: TextChannel = parameter(
            default=attrgetter("channel"), displayed_default="this channel"
        ),
        dms: bool = False,
        role: Role | None = None,
    ) -> None:
        """Post a kind of Splatoon 3 update in a channel as it happens."""
        await add_watch(ctx, self.watcher, topic, channel, dms, role)

    @watch.command(name="remove")  # type: ignore[arg-type]  # bad d.py export
    @describe(
        topic="What to stop posting.",
        channel="The channel to stop posting in, if not this one.",
        dms="Stop posting in your direct messages instead.",
    )
    @choices(
        topic=[
            Choice(name="Everything", value="all"),
            *(Choice(name=name, value=topic) for topic, name in TOPICS.items()),
        ]
    )
    async def watch_remove(
        self,
        ctx: CustomContext,
        topic: str,
        channel: TextChannel = parameter(
            default=attrgetter("channel"), displayed_default="this channel"
        ),
        dms: bool = False,
    ) -> None:
        """Stop posting a kind of Splatoon 3 update in a channel."""
        await remove_watch(ctx, self.watcher, topic, channel, dms)

    @watch.command(name="list")  # type: ignore[arg-type]  # bad d.py export
    async def watch_list(self, ctx: CustomContext) -> None:
        """List what this server's channels, or your direct messages, get posted."""
        await list_watches(ctx, self.watcher)


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(Splatoon3(bot))

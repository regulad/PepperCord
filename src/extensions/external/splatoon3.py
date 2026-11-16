from dataclasses import dataclass
from datetime import UTC, datetime, tzinfo
from functools import reduce
from io import BytesIO
from logging import getLogger
from os import getcwd
from os.path import join
from random import choice
from typing import (
    Literal,
    Any,
    cast,
    Awaitable,
    Callable,
    Sequence,
)

from aiofiles import open as aopen
from aiohttp import ClientSession
from aiosplatoon3ink import (
    Festivals,
    MonthlyGear,
    Region,
    Schedules,
    Splatoon3InkClient,
)
from aiosplatoon3ink.festivals import Fest, FestState
from aiosplatoon3ink.schedules import (
    BankaraMode,
    CoopWeapon,
    FestMode,
    LeagueMatchEvent,
    TimePeriod,
    VsRuleKey,
    VsSetting,
    VsStage,
)
from discord import Colour, Embed, File, SelectOption, Interaction, Message
from discord.app_commands import describe
from discord.ext import tasks
from discord.ext.commands import Cog, hybrid_group, CheckFailure
from discord.ui import Select, View
from discord.utils import format_dt, get, MISSING
from pytz import UTC as PYTZ_UTC

from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext
from utils.consts import TIME_EMOJIS
from utils.images import vrt_concat_pngs, hrz_concat_pngs
from utils.markdown_tools import bold
from utils.misc import edit_with_files_send_wrapper, FrozenDict

logger = getLogger(__name__)

# splatoon3.ink asks for a User-Agent that says who to contact: https://github.com/misenhower/splatoon3.ink/wiki/Data-Access
USER_AGENT = "PepperCord/1.0 https://github.com/regulad/PepperCord @regulad#7959"

SPLATFEST_UNSTARTED_COLOR: int = 0x666775
REGULAR_BATTLE_COLOR: int = 0xCFF622
ANARCHY_BATTLE_COLOR: int = 0xF54910
SALMON_RUN_COLOR: int = 0xFF5600
X_BATTLE_COLOR: int = 0x5D2EEF
LEAGUE_BATTLE_COLOR: int = 0xF02D7D

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


def vs_rotations(schedules: Schedules, mode: MODE_LITERAL) -> list[VsRotation]:
    """Every rotation of a battle mode that hasn't ended yet, in order."""
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
    now = datetime.now(UTC)
    return [rotation for rotation in rotations if rotation.period.end_time > now]


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

    async def cog_load(self) -> None:
        self.cs = ClientSession(headers={"User-Agent": USER_AGENT})
        self.client = Splatoon3InkClient(USER_AGENT, session=self.cs)

    async def cog_unload(self) -> None:
        if self.cs is not None and not self.cs.closed:
            await self.cs.close()
        if self.update_cache.is_running():
            self.update_cache.cancel()

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

        files: list[tuple[str, bytes]] = []
        embed: Embed
        timeslots: list[TimeSlotData] = []

        async with aopen(
            join(getcwd(), "resources", "images", "splatoon3", "favicon.png"), "rb"
        ) as fp:
            files.append(("favicon.png", await fp.read()))

        if mode == "Salmon Run":
            now = datetime.now(UTC)
            coop = schedules.coop_grouping_schedule
            # Regular Salmon Run pauses while a Big Run is on, so a Big Run takes its place in the rotations.
            salmon_run_rotations = sorted(
                (
                    node
                    for node in (*coop.regular_schedules, *coop.big_run_schedules)
                    if node.end_time > now
                ),
                key=lambda node: node.start_time,
            )
            timeslots = TimeSlotData.from_nodes(salmon_run_rotations, mode)

            salmon_run_schedule = salmon_run_rotations[index]
            salmon_run_match_settings = salmon_run_schedule.setting

            embed = Embed(
                title=(
                    "Big Run"
                    if salmon_run_schedule in coop.big_run_schedules
                    else "Salmon Run"
                ),
                color=SALMON_RUN_COLOR,
            )

            salmon_run_thumbnail_bytes = await self._make_salmon_run_thumbnail(
                salmon_run_match_settings.weapons
            )
            if salmon_run_thumbnail_bytes is not None:
                embed = embed.set_thumbnail(url="attachment://weapons.png")
                files.append(("weapons.png", salmon_run_thumbnail_bytes))

            embed = (
                embed.add_field(
                    name="Start Time",
                    value=format_dt(salmon_run_schedule.start_time, "R"),
                )
                .add_field(
                    name="End Time", value=format_dt(salmon_run_schedule.end_time, "R")
                )
                .add_field(
                    name="Stage",
                    value=salmon_run_match_settings.coop_stage.name,
                )
                .set_image(url=salmon_run_match_settings.coop_stage.image.url)
                .set_footer(
                    text="Powered by https://splatoon3.ink/",
                    icon_url="attachment://favicon.png",
                )
            )

            for weapon_index, weapon in enumerate(salmon_run_match_settings.weapons):
                embed = embed.add_field(
                    name=f"Weapon {weapon_index + 1}",
                    value=weapon.name,
                    inline=False,
                )
        else:  # All other modes
            rotations = vs_rotations(schedules, mode)
            timeslots = TimeSlotData.from_nodes(
                [rotation.period for rotation in rotations], mode
            )

            color: int = MODE_COLORS[mode]
            if (
                mode in ("Splatfest Battle (Open)", "Splatfest Battle (Pro)")
                and schedules.current_fest is not None
            ):
                color = Colour.from_rgb(
                    *choice(schedules.current_fest.teams).color.rgb
                ).value

            vs_rotation = rotations[index] if index < len(rotations) else None

            if vs_rotation is None or vs_rotation.setting is None:
                embed = Embed(
                    title=mode,
                    color=color,
                    description="This game mode is not currently available.",
                ).set_footer(
                    text="Powered by https://splatoon3.ink/",
                    icon_url="attachment://favicon.png",
                )
            else:
                vsmatch_settings = vs_rotation.setting
                rule_emoji = ctx.bot.get_custom_emoji(
                    f"{RULE_EMOJI_NAME[vsmatch_settings.vs_rule.rule]}.png"
                )
                description = f"{vsmatch_settings.vs_rule.name} {rule_emoji or ''}"
                if vs_rotation.event is not None:
                    # SplatNet breaks the summary where the game wraps it.
                    summary = vs_rotation.event.desc.replace("<br />", " ")
                    description = (
                        f"**{vs_rotation.event.name}**: {summary}\n{description}"
                    )

                files.append(
                    (
                        "stages.png",
                        await self._make_two_stage_image(vsmatch_settings.vs_stages),
                    )
                )

                embed = (
                    Embed(
                        title=f"{mode} "
                        f"{ctx.bot.get_custom_emoji(f'{MODE_EMOJI_NAME[mode]}.png') or ''}",
                        color=color,
                        description=description,
                    )
                    .add_field(
                        name="Start Time",
                        value=format_dt(vs_rotation.period.start_time, "R"),
                    )
                    .add_field(
                        name="End Time",
                        value=format_dt(vs_rotation.period.end_time, "R"),
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
                    .set_footer(
                        text="Powered by https://splatoon3.ink/",
                        icon_url="attachment://favicon.png",
                    )
                )

        return await send(
            embed=embed,
            files=(
                [File(fp=BytesIO(data), filename=name) for name, data in files]
                if len(files) > 0
                else None
            ),
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
        assert self.cs is not None

        if send is MISSING:
            send = ctx.send

        if current and index != 0:
            raise RuntimeError("Index must be 0 for a current splatfest")

        nodes = self.festivals.in_region(Region(region))
        current_fest = self.schedules.current_fest
        files: list[tuple[str, bytes]] = []
        historic_splatfests: list[SplatfestData] = SplatfestData.from_nodes(nodes)

        async with aopen(
            join(getcwd(), "resources", "images", "splatoon3", "favicon.png"), "rb"
        ) as fp:
            files.append(("favicon.png", await fp.read()))

        if current and current_fest is None:
            embed: Embed = Embed(
                title="Splatfest",
                color=SPLATFEST_UNSTARTED_COLOR,
                description="There is no Splatfest currently running.",
            ).set_footer(
                text="Powered by https://splatoon3.ink/",
                icon_url="attachment://favicon.png",
            )
        else:
            historic_splatfest_info = nodes[index]

            start_time: datetime = historic_splatfest_info.start_time
            end_time: datetime = historic_splatfest_info.end_time

            is_scheduled: bool = historic_splatfest_info.state is FestState.SCHEDULED

            color: int = (
                SPLATFEST_UNSTARTED_COLOR
                if is_scheduled
                else Colour.from_rgb(
                    *choice(historic_splatfest_info.teams).color.rgb
                ).value
            )

            embed = (
                Embed(
                    title=historic_splatfest_info.title,
                    description=historic_splatfest_info.state.replace("_", " ").title(),
                    color=color,
                )
                .add_field(
                    name="Start Time",
                    value=format_dt(start_time, "R" if current else "D"),
                )
                .add_field(
                    name="End Time",
                    value=format_dt(end_time, "R" if current else "D"),
                )
                .set_footer(
                    text="Powered by https://splatoon3.ink/",
                    icon_url="attachment://favicon.png",
                )
            )

            midterm: datetime
            if current and current_fest is not None:
                midterm = current_fest.midterm_time
                # Midterm & tricolor data is only available for the current splatfest
                tricolor_stages = current_fest.tricolor_stages or ()

                embed = embed.add_field(
                    name="Midterm Time",
                    value=format_dt(midterm, "R" if current else "D"),
                ).add_field(
                    name=(
                        "Tricolor Stages"
                        if len(tricolor_stages) > 1
                        else "Tricolor Stage"
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
                    value=f"{format_dt(midterm, 'D')} (approx.)",
                ).add_field(
                    name="Tricolor Stage",
                    value="This data is not stored for previous Splatfests.",
                    inline=False,
                )

            if not current and historic_splatfest_info.has_results:
                for team in historic_splatfest_info.teams:
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
                for team in historic_splatfest_info.teams:
                    embed = embed.add_field(
                        name=team.team_name,
                        value=f"Color: `{Colour.from_rgb(*team.color.rgb)}`",
                        inline=True,
                    )

            if current and current_fest is not None and current_fest.tricolor_stages:
                pngs: list[bytes] = []
                for url in (
                    historic_splatfest_info.image.url,
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
                embed = embed.set_image(url=historic_splatfest_info.image.url)

        return await send(
            embed=embed,
            files=(
                [File(fp=BytesIO(data), filename=name) for name, data in files]
                if len(files) > 0
                else None
            ),
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
            monthly_gear_info = self.monthly_gear

            embed: Embed = (
                Embed(title="Salmon Run Gear", color=SALMON_RUN_COLOR)
                .add_field(
                    name="Name",
                    value=monthly_gear_info.name,
                )
                .add_field(
                    name="Slot",
                    value=monthly_gear_info.kind.value,
                )
                .set_image(url=monthly_gear_info.image.url)
                .set_footer(
                    text="Powered by https://splatoon3.ink/",
                    icon_url="attachment://favicon.png",
                )
            )
            await ctx.send(
                embed=embed,
                file=File(
                    join(getcwd(), "resources", "images", "splatoon3", "favicon.png")
                ),
            )


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(Splatoon3(bot))

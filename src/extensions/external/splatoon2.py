"""Splatoon 2's battle and Salmon Run schedules, Splatfests and SplatNet gear, from https://splatoon2.ink/."""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from functools import partial
from io import BytesIO
from logging import getLogger
from operator import attrgetter
from typing import Literal, cast

from aiohttp import ClientSession
from aiosplatoon2ink import (
    CoopSchedules,
    Festivals,
    Merchandise,
    Region,
    Schedules,
    Splatoon2InkClient,
    Team,
    TimePeriod,
    Timeline,
)
from aiosplatoon2ink.festivals import Festival, TeamRates
from aiosplatoon2ink.salmon_run import CoopScheduleDetail, RandomWeapon
from aiosplatoon2ink.schedules import GameMode, Rotation, Rule
from aiosplatoon2ink.timeline import RewardGear
from discord import Colour, Embed, Emoji, File, Message, Role, TextChannel
from discord.app_commands import Choice, choices, describe
from discord.ext import tasks
from discord.ext.commands import CheckFailure, Cog, hybrid_group, parameter
from discord.utils import MISSING, format_dt

from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext
from utils.markdown_tools import bold
from utils.misc import FrozenDict
from utils.splatoon import (
    ScheduleView,
    SplatfestData,
    SplatfestView,
    TimeSlotData,
    stack_images,
    tile_four_images,
)
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

# splatoon2.ink asks for a User-Agent that says who to contact: https://github.com/misenhower/splatoon2.ink/wiki/Data-access-policy
USER_AGENT = "PepperCord/1.0 https://github.com/regulad/PepperCord @regulad#7959"

# The bot's emoji of splatoon2.ink's favicon, from resources/emojis, which the credit under each embed shows.
CREDIT_EMOJI = "splatoon2ink"

REGULAR_BATTLE_COLOR: int = 0x19D719
RANKED_BATTLE_COLOR: int = 0xF54910
LEAGUE_BATTLE_COLOR: int = 0xF02D7D
SALMON_RUN_COLOR: int = 0xFF5600
SPLATNET_COLOR: int = 0xCFF622

MODE_LITERAL = Literal["Regular Battle", "Ranked Battle", "League Battle", "Salmon Run"]
MODES: tuple[MODE_LITERAL, ...] = (
    "Regular Battle",
    "Ranked Battle",
    "League Battle",
    "Salmon Run",
)
MODE_GAME_MODES: FrozenDict[MODE_LITERAL, GameMode] = FrozenDict(
    {
        "Regular Battle": GameMode.REGULAR,
        "Ranked Battle": GameMode.RANKED,
        "League Battle": GameMode.LEAGUE,
    }
)
MODE_COLORS: FrozenDict[MODE_LITERAL, int] = FrozenDict(
    {
        "Regular Battle": REGULAR_BATTLE_COLOR,
        "Ranked Battle": RANKED_BATTLE_COLOR,
        "League Battle": LEAGUE_BATTLE_COLOR,
        "Salmon Run": SALMON_RUN_COLOR,
    }
)
# Splatoon 2 shares Splatoon 3's icons for its modes and rules: Ranked Battle became Anarchy Battle.
MODE_EMOJI_NAME: FrozenDict[MODE_LITERAL, str] = FrozenDict(
    {
        "Regular Battle": "regular",
        "Ranked Battle": "bankara",
        "League Battle": "league",
        "Salmon Run": "coop",
    }
)
RULE_EMOJI_NAME: FrozenDict[Rule, str] = FrozenDict(
    {
        Rule.TURF_WAR: "turfwar",
        Rule.SPLAT_ZONES: "area",
        Rule.TOWER_CONTROL: "yagura",
        Rule.RAINMAKER: "hoko",
        Rule.CLAM_BLITZ: "asari",
    }
)

REGION_LITERAL = Literal["NA", "EU", "JP"]
DEFAULT_REGION: REGION_LITERAL = "NA"

# What a channel can watch, and what each topic posts. Splatoon 2's Splatfests are over, so there's nothing to watch.
TOPICS: FrozenDict[str, str] = FrozenDict(
    {
        "regular": "Each new Regular Battle rotation",
        "ranked": "Each new Ranked Battle rotation",
        "league": "Each new League Battle rotation",
        "salmon-run": "Each Salmon Run rotation",
        "gear": "Each new item in SplatNet's shop, and each new Salmon Run reward gear",
    }
)
TOPIC_MODES: FrozenDict[str, MODE_LITERAL] = FrozenDict(
    {
        "regular": "Regular Battle",
        "ranked": "Ranked Battle",
        "league": "League Battle",
    }
)


def rotations(
    schedules: Schedules, mode: MODE_LITERAL, now: datetime | None = None
) -> list[Rotation]:
    """Every rotation of a battle mode that hasn't ended by ``now``, in order."""
    now = now or datetime.now(UTC)
    return [
        rotation
        for rotation in schedules.in_mode(MODE_GAME_MODES[mode])
        if rotation.end_time > now
    ]


def salmon_run_rotations(
    coop: CoopSchedules, now: datetime | None = None
) -> list[TimePeriod]:
    """Every Salmon Run rotation that hasn't ended by ``now``, in order."""
    now = now or datetime.now(UTC)
    return [period for period in coop.schedules if period.end_time > now]


def _rate(rates: TeamRates, team: Team) -> float:
    # SplatNet 2 gives each share in hundredths of a percent.
    return (rates.alpha if team is Team.ALPHA else rates.bravo) / 100


class Splatoon2Watch:
    """What Splatoon 2 can be watched for, derived from the cog's copies of splatoon2.ink's feeds.

    Rotations are dated in the feeds. Gear only shows up in them, so it's dated by when the bot first noticed it.
    """

    namespace = "splatoon2"
    name = "Splatoon 2"
    topics: Mapping[str, str] = TOPICS

    def __init__(self, cog: "Splatoon2") -> None:
        self.cog = cog
        self.first_seen = FirstSeen()

    def events(self, now: datetime) -> list[WatchEvent]:
        events: list[WatchEvent] = []
        if (schedules := self.cog.schedules) is not None:
            for topic, mode in TOPIC_MODES.items():
                for rotation in rotations(schedules, mode, now):
                    if rotation.start_time <= now:
                        events.append(
                            WatchEvent.dated(
                                f"{topic}:{rotation.start_time.isoformat()}",
                                topic,
                                rotation.start_time,
                                partial(self._render_vs, mode, rotation),
                                ends=rotation.end_time,
                            )
                        )
        if (coop := self.cog.salmon_run) is not None:
            for period in salmon_run_rotations(coop, now):
                if period.start_time <= now:
                    events.append(
                        WatchEvent.dated(
                            f"salmon-run:{period.start_time.isoformat()}",
                            "salmon-run",
                            period.start_time,
                            partial(self._render_salmon_run, coop, period),
                            ends=period.end_time,
                        )
                    )
        for merchandise in self.cog.merchandises or ():
            key = f"gear:item:{merchandise.id}"
            events.append(
                WatchEvent(
                    key,
                    "gear",
                    self.first_seen(key, now),
                    merchandise.end_time,
                    partial(self._render_merchandise, merchandise),
                )
            )
        if (timeline := self.cog.timeline) is not None and timeline.coop is not None:
            reward = timeline.coop.reward_gear
            key = f"gear:reward:{reward.gear.id}:{reward.available_time.isoformat()}"
            at = self.first_seen(key, now)
            events.append(
                WatchEvent(
                    key, "gear", at, at + GRACE, partial(self._render_reward, reward)
                )
            )
        self.first_seen.forget_all_but(event.key for event in events)
        return events

    async def _render_vs(self, mode: MODE_LITERAL, rotation: Rotation) -> Rendered:
        embed, files = await self.cog.vs_message(mode, rotation)
        return Rendered(f"A new {mode} rotation has started.", embed, tuple(files))

    async def _render_salmon_run(
        self, coop: CoopSchedules, period: TimePeriod
    ) -> Rendered:
        embed, files = await self.cog.salmon_run_message(period, coop.detail(period))
        return Rendered("A new Salmon Run rotation has started.", embed, tuple(files))

    async def _render_merchandise(self, merchandise: Merchandise) -> Rendered:
        embed, files = await self.cog.merchandise_message(merchandise)
        return Rendered(
            f"New in SplatNet's shop: {merchandise.gear.name}.", embed, tuple(files)
        )

    async def _render_reward(self, reward: RewardGear) -> Rendered:
        embed, files = await self.cog.reward_gear_message(reward)
        return Rendered(
            f"Salmon Run's reward gear is now {reward.gear.name}.", embed, tuple(files)
        )


class Splatoon2(Cog):
    """
    Get information about the current status of Splatoon 2.
    Powered by https://splatoon2.ink/
    """

    modes: Sequence[str] = MODES

    def __init__(self, bot: CustomBot) -> None:
        self.bot: CustomBot = bot
        self.cs: ClientSession | None = None
        self.client: Splatoon2InkClient | None = None

        self.schedules: Schedules | None = None
        self.salmon_run: CoopSchedules | None = None
        self.merchandises: tuple[Merchandise, ...] | None = None
        self.festivals: Festivals | None = None
        self.timeline: Timeline | None = None

        self.watcher = Watcher(bot, Splatoon2Watch(self))

    async def _fetch[T](self, feed: str, fetch: Callable[[], Awaitable[T]]) -> T | None:
        try:
            return await fetch()
        except Exception:
            logger.exception(f"Couldn't fetch {feed} from splatoon2.ink.")
            return None

    @tasks.loop(hours=1)
    async def update_cache(self) -> None:
        # splatoon2.ink updates hourly and asks to be cached. A tasks.loop stops for good on an error it doesn't treat
        # as a dropped connection, so each feed is fetched on its own, and one that fails keeps its last copy.
        if self.client is None:
            return
        if (
            schedules := await self._fetch("schedules", self.client.schedules)
        ) is not None:
            self.schedules = schedules
        if (
            coop := await self._fetch("Salmon Run", self.client.salmon_run)
        ) is not None:
            self.salmon_run = coop
        if (gear := await self._fetch("SplatNet's shop", self.client.gear)) is not None:
            self.merchandises = gear
        if (
            festivals := await self._fetch("Splatfests", self.client.festivals)
        ) is not None:
            self.festivals = festivals
        if (
            timeline := await self._fetch("the timeline", self.client.timeline)
        ) is not None:
            self.timeline = timeline

    @property
    def is_ready(self) -> bool:
        return (
            self.schedules is not None
            and self.salmon_run is not None
            and self.merchandises is not None
            and self.festivals is not None
            and self.timeline is not None
        )

    async def cog_check(self, ctx: CustomContext) -> bool:  # type: ignore[override]  # d.py bad export
        if self.is_ready:
            return True
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
        self.client = Splatoon2InkClient(USER_AGENT, session=self.cs)

    async def cog_unload(self) -> None:
        if self.cs is not None and not self.cs.closed:
            await self.cs.close()
        if self.update_cache.is_running():
            self.update_cache.cancel()
        self.watcher.stop()

    def mode_emoji(self, mode: str) -> Emoji | None:
        return self.bot.get_custom_emoji(MODE_EMOJI_NAME[cast(MODE_LITERAL, mode)])

    def splatfest_emoji(self) -> Emoji | None:
        return None  # Splatoon 2's Splatfests had no Tricolor Turf War to show

    # Each message's embed and files, which the commands send and watches post.

    def _credit(self, embed: Embed) -> Embed:
        # splatoon2.ink's favicon is one of the bot's emojis, uploaded at startup, so no message has to attach it.
        emoji = self.bot.get_custom_emoji(CREDIT_EMOJI)
        return embed.set_footer(
            text="Powered by https://splatoon2.ink/",
            icon_url=emoji.url if emoji is not None else None,
        )

    async def vs_message(
        self, mode: MODE_LITERAL, rotation: Rotation | None
    ) -> tuple[Embed, list[tuple[str, bytes]]]:
        """A battle rotation's embed and files, or a note that there's none."""
        color = MODE_COLORS[mode]
        if rotation is None:
            return (
                self._credit(
                    Embed(title=mode, color=color, description="No rotation is listed.")
                ),
                [],
            )

        assert self.cs is not None
        rule_emoji = self.bot.get_custom_emoji(
            f"{RULE_EMOJI_NAME[rotation.rule.key]}.png"
        )
        mode_emoji = self.bot.get_custom_emoji(f"{MODE_EMOJI_NAME[mode]}.png")
        stages = await stack_images(
            self.cs, [stage.image.url for stage in rotation.stages]
        )
        embed = self._credit(
            Embed(
                title=f"{mode} {mode_emoji or ''}",
                color=color,
                description=f"{rotation.rule.name} {rule_emoji or ''}",
            )
            .add_field(name="Start Time", value=format_dt(rotation.start_time, "R"))
            .add_field(name="End Time", value=format_dt(rotation.end_time, "R"))
            .add_field(name="Stage 1", value=rotation.stage_a.name, inline=False)
            .add_field(name="Stage 2", value=rotation.stage_b.name)
            .set_image(url="attachment://stages.png")
        )
        return embed, [("stages.png", stages)]

    async def salmon_run_message(
        self, period: TimePeriod, detail: CoopScheduleDetail | None
    ) -> tuple[Embed, list[tuple[str, bytes]]]:
        """A Salmon Run rotation's embed and files. SplatNet 2 only lists the stage and weapons of the next two."""
        embed = (
            Embed(title="Salmon Run", color=SALMON_RUN_COLOR)
            .add_field(name="Start Time", value=format_dt(period.start_time, "R"))
            .add_field(name="End Time", value=format_dt(period.end_time, "R"))
        )
        if detail is None:
            embed.description = (
                "Grizzco hasn't announced this rotation's stage and weapons yet."
            )
            return self._credit(embed), []

        assert self.cs is not None
        embed = embed.add_field(name="Stage", value=detail.stage.name).set_image(
            url=detail.stage.image.url
        )
        pictures: list[str] = []
        for index, slot in enumerate(detail.weapons):
            if isinstance(slot, RandomWeapon):
                name = "Random (rare weapons too)" if slot.is_golden else "Random"
                if slot.coop_special_weapon is not None:
                    pictures.append(slot.coop_special_weapon.image.url)
            else:
                name = slot.weapon.name
                pictures.append(slot.weapon.image.url)
            embed = embed.add_field(
                name=f"Weapon {index + 1}", value=name, inline=False
            )

        embed = self._credit(embed)
        files: list[tuple[str, bytes]] = []
        if (weapons := await tile_four_images(self.cs, pictures)) is not None:
            embed = embed.set_thumbnail(url="attachment://weapons.png")
            files.append(("weapons.png", weapons))
        return embed, files

    async def splatfest_message(
        self, fest: Festival
    ) -> tuple[Embed, list[tuple[str, bytes]]]:
        """A Splatfest's embed and files, with its results."""
        names = fest.names
        winner = fest.winner
        # The winner's colour, or the Splatfest's own before its results.
        colors = {
            None: fest.colors.middle,
            Team.ALPHA: fest.colors.alpha,
            Team.BRAVO: fest.colors.bravo,
        }
        embed = (
            Embed(
                title=f"{names.alpha_short} vs. {names.bravo_short}",
                description=f"{names.alpha_long}\nor\n{names.bravo_long}",
                color=Colour.from_rgb(*colors[winner].rgb),
            )
            .add_field(name="Start Time", value=format_dt(fest.times.start, "D"))
            .add_field(name="End Time", value=format_dt(fest.times.end, "D"))
            .add_field(name="Special Stage", value=fest.special_stage.name)
            .set_image(url=fest.images.panel.url)
        )

        result = fest.result
        for team in Team:
            lines = [f"Color: `{Colour.from_rgb(*colors[team].rgb)}`"]
            if result is not None:
                summary, rates = result.summary, result.rates
                # Splatfests before version 4.0 counted Solo and Team battles; later ones, Normal and Pro.
                categories = [
                    ("Votes", rates.vote, summary.vote),
                    ("Solo", rates.solo, summary.solo),
                    ("Team", rates.team, summary.team),
                    ("Normal", rates.regular, summary.regular),
                    ("Pro", rates.challenge, summary.challenge),
                ]
                lines.append(
                    bold(
                        f"Was victorious: {'Yes' if winner is team else 'No'}",
                        winner is team,
                    )
                )
                lines += [
                    bold(f"{name}: `{_rate(share, team):.2f}`%", leader is team)
                    for name, share, leader in categories
                    if share is not None
                ]
            embed = embed.add_field(
                name=names.short(team), value="\n".join(lines), inline=True
            )
        return self._credit(embed), []

    async def gear_message(self) -> tuple[Embed, list[tuple[str, bytes]]]:
        """Everything on sale in SplatNet's shop."""
        embed = Embed(title="SplatNet Gear", color=SPLATNET_COLOR)
        for merchandise in sorted(self.merchandises or (), key=attrgetter("end_time")):
            gear = merchandise.gear
            embed = embed.add_field(
                name=gear.name,
                value=f"{gear.brand.name}, {merchandise.skill.name}, {merchandise.price:,} coins. "
                f"Until {format_dt(merchandise.end_time, 'R')}.",
                inline=False,
            )
        return self._credit(embed), []

    async def merchandise_message(
        self, merchandise: Merchandise
    ) -> tuple[Embed, list[tuple[str, bytes]]]:
        """One item on sale in SplatNet's shop."""
        gear = merchandise.gear
        embed = (
            Embed(title=gear.name, color=SPLATNET_COLOR)
            .add_field(name="Brand", value=gear.brand.name)
            .add_field(name="Ability", value=merchandise.skill.name)
            .add_field(name="Price", value=f"{merchandise.price:,} coins")
            .add_field(name="On Sale Until", value=format_dt(merchandise.end_time, "R"))
            .set_image(url=gear.image.url)
        )
        return self._credit(embed), []

    async def reward_gear_message(
        self, reward: RewardGear
    ) -> tuple[Embed, list[tuple[str, bytes]]]:
        """Salmon Run's reward gear."""
        embed = (
            Embed(title="Salmon Run Gear", color=SALMON_RUN_COLOR)
            .add_field(name="Name", value=reward.gear.name)
            .add_field(name="Slot", value=reward.gear.kind.value.title())
            .add_field(name="Since", value=format_dt(reward.available_time, "D"))
            .set_image(url=reward.gear.image.url)
        )
        return self._credit(embed), []

    async def send_schedule(
        self,
        ctx: CustomContext,
        mode: MODE_LITERAL,
        index: int,
        send: Callable[..., Awaitable[Message]] = MISSING,
    ) -> Message:
        """Send a schedule message with embed, file, and view."""
        assert self.schedules is not None and self.salmon_run is not None

        if send is MISSING:
            send = ctx.send

        timeslots: list[TimeSlotData]
        if mode == "Salmon Run":
            periods = salmon_run_rotations(self.salmon_run)
            timeslots = TimeSlotData.from_nodes(periods, mode)
            period = periods[index]
            embed, files = await self.salmon_run_message(
                period, self.salmon_run.detail(period)
            )
        else:
            listed = rotations(self.schedules, mode)
            timeslots = TimeSlotData.from_nodes(listed, mode)
            embed, files = await self.vs_message(
                mode, listed[index] if index < len(listed) else None
            )

        return await send(
            embed=embed,
            files=[File(fp=BytesIO(data), filename=name) for name, data in files],
            view=ScheduleView(self, ctx, timeslots, mode) if timeslots else None,
        )

    async def send_splatfest(
        self,
        ctx: CustomContext,
        current: bool = False,
        index: int = 0,
        region: REGION_LITERAL = DEFAULT_REGION,
        send: Callable[..., Awaitable[Message]] = MISSING,
    ) -> Message:
        """Send a Splatfest. Splatoon 2's are all over, so ``current`` changes nothing."""
        assert self.festivals is not None

        if send is MISSING:
            send = ctx.send

        fests = self.festivals.in_region(Region[region])
        listing = SplatfestData.listing(
            (
                f"{fest.names.alpha_short} vs. {fest.names.bravo_short}",
                fest.times.start,
                fest.times.end,
            )
            for fest in fests
        )
        embed, files = await self.splatfest_message(fests[index])
        return await send(
            embed=embed,
            files=[File(fp=BytesIO(data), filename=name) for name, data in files],
            view=SplatfestView(self, ctx, listing, region),
        )

    @hybrid_group(aliases=["sp2", "splat2"], fallback="schedule")  # type: ignore[arg-type]  # bad d.py export
    @describe(mode="The game mode to get information about.")
    async def splatoon2(
        self, ctx: CustomContext, *, mode: MODE_LITERAL = "Regular Battle"
    ) -> None:
        """
        Get the schedule of a game mode in Splatoon 2.
        Powered by https://splatoon2.ink/
        """
        async with ctx.typing():
            await self.send_schedule(ctx, mode, 0)

    @splatoon2.command()  # type: ignore[arg-type]  # bad d.py export
    @describe(
        region="The region to get Splatfests of. Splatfests varied between regions."
    )
    async def splatfest(
        self, ctx: CustomContext, *, region: REGION_LITERAL = DEFAULT_REGION
    ) -> None:
        """
        Get Splatoon 2's past Splatfests, and their results.
        Powered by https://splatoon2.ink/
        """
        async with ctx.typing():
            await self.send_splatfest(ctx, False, 0, region)

    @splatoon2.command()  # type: ignore[arg-type]  # bad d.py export
    async def gear(self, ctx: CustomContext) -> None:
        """
        Get the gear on sale in Splatoon 2's SplatNet shop.
        Powered by https://splatoon2.ink/
        """
        async with ctx.typing():
            embed, files = await self.gear_message()
            await ctx.send(
                embed=embed,
                files=[File(fp=BytesIO(data), filename=name) for name, data in files],
            )

    @splatoon2.command()  # type: ignore[arg-type]  # bad d.py export
    async def salmon_run_gear(self, ctx: CustomContext) -> None:
        """
        Get Salmon Run's current reward gear in Splatoon 2.
        Powered by https://splatoon2.ink/
        """
        assert self.timeline is not None
        if self.timeline.coop is None:
            await ctx.send(
                "splatoon2.ink doesn't list Salmon Run's reward gear right now."
            )
            return
        async with ctx.typing():
            embed, files = await self.reward_gear_message(
                self.timeline.coop.reward_gear
            )
            await ctx.send(
                embed=embed,
                files=[File(fp=BytesIO(data), filename=name) for name, data in files],
            )

    @splatoon2.group(name="watch")  # type: ignore[arg-type]  # bad d.py export
    async def watch(self, ctx: CustomContext) -> None:
        """
        Post Splatoon 2 updates in a channel as they happen.
        Powered by https://splatoon2.ink/
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
        """Post a kind of Splatoon 2 update in a channel as it happens."""
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
        """Stop posting a kind of Splatoon 2 update in a channel."""
        await remove_watch(ctx, self.watcher, topic, channel, dms)

    @watch.command(name="list")  # type: ignore[arg-type]  # bad d.py export
    async def watch_list(self, ctx: CustomContext) -> None:
        """List what this server's channels, or your direct messages, get posted."""
        await list_watches(ctx, self.watcher)


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(Splatoon2(bot))

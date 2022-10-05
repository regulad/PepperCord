from datetime import datetime, tzinfo
from io import BytesIO
from os import getcwd
from os.path import join
from random import choice
from typing import Literal, Any, Type, Awaitable, Callable

from aiofiles import open as aopen
from aiohttp import ClientSession
from dateutil.parser import isoparse
from dateutil.tz import tzutc
from discord import Embed, File, Message
from discord.ext import tasks
from discord.ext.commands import Cog, group, CheckFailure
from discord.utils import format_dt, MISSING

from utils.bots import BOT_TYPES, CustomContext
from utils.consts import TIME_EMOJIS
from utils.images import vrt_concat_pngs, hrz_concat_pngs
from utils.markdown_tools import bold
from utils.misc import rgb_human_readable, FrozenDict

SPLATFEST_UNSTARTED_COLOR: int = 0x666775
REGULAR_BATTLE_COLOR: int = 0xcff622
ANARCHY_BATTLE_COLOR: int = 0xf54910
SALMON_RUN_COLOR: int = 0xff5600
X_BATTLE_COLOR: int = 0x5d2eef
LEAGUE_BATTLE_COLOR: int = 0xf02d7d

TIMESLOT_LONG: str = "%m/%d"
TIMESLOT_SHORT: str = "%I:%M %p"
TIMESLOT_TZ: str = "%Z"

SPLATFEST_LONG: str = "%m/%d/%y"

SPLATFEST_STATES: Type = Literal["SCHEDULED", "FIRST_HALF", "SECOND_HALF", "CLOSED"]

MODE_LITERAL: Type = Literal[
    "Regular Battle",
    "Anarchy Battle (Series)",
    "Anarchy Battle (Open)",
    "League Battle",
    "X Battle",
    "Salmon Run",
    "Splatfest Battle",
]
MODES: set[MODE_LITERAL] = {
    "Regular Battle",
    "Anarchy Battle (Series)",
    "Anarchy Battle (Open)",
    "League Battle",
    "X Battle",
    "Salmon Run",
    "Splatfest Battle",
}
MODE_DATA_SLOTS: FrozenDict[MODE_LITERAL, str] = FrozenDict({
    "Regular Battle": "regularSchedules",
    "Anarchy Battle (Series)": "bankaraSchedules",  # special case
    "Anarchy Battle (Open)": "bankaraSchedules",  # special case
    "League Battle": "leagueSchedules",
    "X Battle": "xSchedules",
    "Salmon Run": "coopGroupingSchedules",
    "Splatfest Battle": "festSchedules",
})
MODE_SETTINGS_NAME: FrozenDict[MODE_LITERAL, str] = FrozenDict({
    "Regular Battle": "regularMatchSetting",
    "Anarchy Battle (Series)": "bankaraMatchSettings",
    "Anarchy Battle (Open)": "bankaraMatchSettings",
    "X Battle": "xMatchSetting",
    "League Battle": "leagueMatchSetting",
    "Salmon Run": "setting",
    "Splatfest Battle": "festMatchSetting",
})
MODE_COLORS: FrozenDict[MODE_LITERAL, int] = FrozenDict({
    "Regular Battle": REGULAR_BATTLE_COLOR,
    "Anarchy Battle (Series)": ANARCHY_BATTLE_COLOR,
    "Anarchy Battle (Open)": ANARCHY_BATTLE_COLOR,
    "League Battle": LEAGUE_BATTLE_COLOR,
    "X Battle": X_BATTLE_COLOR,
    "Salmon Run": SALMON_RUN_COLOR,
    "Splatfest Battle": SPLATFEST_UNSTARTED_COLOR,  # special case
})
MODE_SVG_NAME: FrozenDict[MODE_LITERAL, str] = FrozenDict({
    "Regular Battle": "regular",
    "Anarchy Battle (Series)": "bankara",
    "Anarchy Battle (Open)": "bankara",
    "League Battle": "league",
    "X Battle": "x",
    "Salmon Run": "coop",  # unused
    "Splatfest Battle": "regular",  # probably going to be updated
})
MODE_EMOJI_NAME: FrozenDict[MODE_LITERAL, str] = FrozenDict({  # special because weird short names n crap
    "Regular Battle": "regular",
    "Anarchy Battle (Series)": "bankara",
    "Anarchy Battle (Open)": "bankara",
    "League Battle": "league",
    "X Battle": "xb",
    "Salmon Run": "coop",
    "Splatfest Battle": "tricolor",
})

REGION_LITERAL: Type = Literal[
    "US",
    "EU",
    "JP",
    "AP"
]
REGION_FULL_NAME: FrozenDict[REGION_LITERAL, str] = FrozenDict({
    "US": "The Americas, Australia, New Zealand",
    "EU": "Europe",
    "JP": "Japan",
    "AP": "Hong Kong, South Korea (Asia/Pacific)"
})
REGION_EMOJI: FrozenDict[REGION_LITERAL, str] = FrozenDict({
    "US": "🇺🇸",
    "EU": "🇪🇺",
    "JP": "🇯🇵",
    "AP": "🇭🇰"
})
DEFAULT_REGION: REGION_LITERAL = "US"  # I guess change this if I ever move.


def splatfest_rgb(colors: dict[str, float]) -> tuple[int, int, int]:
    r: int = int(colors["r"] * 255)
    g: int = int(colors["g"] * 255)
    b: int = int(colors["b"] * 255)
    return r, g, b


def splatfest_color(colors: dict[str, float]) -> int:
    r, g, b = splatfest_rgb(colors)
    r: int
    g: int
    b: int
    return (r << 16) + (g << 8) + b


def _convert_rule_name(english: str) -> str:
    match english:
        case "clam":
            return "asari"
        case "loft":
            return "yagura"
        case "goal":
            return "hoko"
        case "turf_war":
            return "regular"
        case _:
            return english


def _convert_rule_name_emoji(english: str) -> str:
    match english:
        case "turf_war":
            return "turfwar"
        case _:
            return _convert_rule_name(english)


class TimeSlotData:  # This could probably extend SelectOption, but this is separate for the sake of selfbot support.
    def __init__(self, start: datetime, end: datetime, index: int, mode: MODE_LITERAL) -> None:
        self.start: datetime = start
        self.end: datetime = end
        self.index: int = index
        self.mode: str = mode

    @classmethod
    def from_nodes(cls, nodes: list[dict[str, Any]], mode: MODE_LITERAL) -> list["TimeSlotData"]:
        return [cls(isoparse(node["startTime"]), isoparse(node["endTime"]), index, mode) for index, node in
                enumerate(nodes)]

    __slots__ = ("start", "end", "index", "mode")

    @property
    def name(self) -> str:
        now: datetime = datetime.now()
        ctz: tzinfo = now.tzinfo
        return f"{self.start.astimezone(ctz).strftime(TIMESLOT_SHORT)} " \
               f"- {self.end.astimezone(ctz).strftime(TIMESLOT_SHORT)} " \
               f"({self.index + 1})"

    @property
    def description(self) -> str:
        now: datetime = datetime.now()
        ctz: tzinfo = now.tzinfo
        now = now.astimezone(ctz)  # weird.
        return f"{self.start.astimezone(ctz).strftime(TIMESLOT_LONG)} " \
               f"- {self.end.astimezone(ctz).strftime(TIMESLOT_LONG)} " \
               f"({now.strftime(TIMESLOT_TZ)})"

    @property
    def emoji(self) -> str:
        now: datetime = datetime.now()
        ctz: tzinfo = now.tzinfo
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
        ctz: tzinfo = now.tzinfo
        now = now.astimezone(ctz)  # weird.
        return f"{self.start.astimezone(ctz).strftime(SPLATFEST_LONG)} " \
               f"- {self.end.astimezone(ctz).strftime(SPLATFEST_LONG)} " \
               f"({now.strftime(TIMESLOT_TZ)})"

    @classmethod
    def from_nodes(cls, nodes: list[dict[str, Any]]) -> list["SplatfestData"]:
        return [cls(node["title"], isoparse(node["startTime"]), isoparse(node["endTime"]), index) for index, node in
                enumerate(nodes)]


class Splatoon3(Cog):
    """
    Get information about the current status of Splatoon 3.
    Powered by https://splatoon3.ink/ and https://splatoonwiki.org/wiki/
    """

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot
        self.cs: ClientSession | None = None

        self.cached_schedules: Any | None = None
        self.cached_gear: Any | None = None
        self.cached_coop: Any | None = None
        self.cached_festivals: Any | None = None

    @tasks.loop(hours=1)
    async def update_cache(self) -> None:
        # https://github.com/misenhower/splatoon3.ink/wiki/Data-Access recommends caching, so we will cache.
        if self.cs is not None and not self.cs.closed:
            async with self.cs.get("https://splatoon3.ink/data/schedules.json") as resp:
                self.cached_schedules = (await resp.json())["data"]
            async with self.cs.get("https://splatoon3.ink/data/gear.json") as resp:
                self.cached_gear = (await resp.json())["data"]["gesotown"]
            async with self.cs.get("https://splatoon3.ink/data/coop.json") as resp:
                self.cached_coop = (await resp.json())["data"]["coopResult"]
            async with self.cs.get("https://splatoon3.ink/data/festivals.json") as resp:
                self.cached_festivals = await resp.json()

    @property
    def is_ready(self) -> bool:
        return all(
            (
                self.cached_schedules is not None,
                self.cached_gear is not None,
                self.cached_coop is not None,
                self.cached_festivals is not None
            )
        )

    async def cog_check(self, ctx: CustomContext) -> bool:
        if self.is_ready:
            return True
        else:
            raise CheckFailure("We are still preparing, hold on! The cache is being populated.")

    @Cog.listener()
    async def on_ready(self) -> None:
        self.update_cache.start()

    async def cog_load(self) -> None:
        self.cs = ClientSession(
            headers={"User-Agent": "PepperCord/1.0 https://github.com/regulad/PepperCord @regulad#7959"})

    async def cog_unload(self) -> None:
        if self.cs is not None and not self.cs.closed:
            await self.cs.close()
        if self.update_cache.is_running():
            self.update_cache.cancel()

    async def _make_salmon_run_thumbnail(self, weapons: list[dict[str, str | dict[str, str]]]) -> bytes | None:
        weapon_urls: list[str] = [
            weapon["image"]["url"]
            for weapon in weapons
        ]

        weapon_pngs: list[bytes] = []

        for weapon_url in weapon_urls:
            async with self.cs.get(weapon_url) as resp:
                weapon_pngs.append(await resp.read())

        if len(weapons) == 4:
            set_1: bytes = await self.bot.loop.run_in_executor(None, hrz_concat_pngs, *weapon_pngs[:2])
            set_2: bytes = await self.bot.loop.run_in_executor(None, hrz_concat_pngs, *weapon_pngs[2:])
            return await self.bot.loop.run_in_executor(None, vrt_concat_pngs, set_1, set_2)
        else:
            return None  # TODO: Handle this case (probably for special weapons)

    async def _make_two_stage_image(self, vs_stages: list[dict[str, Any | dict[str, str]]]) -> bytes:
        stage1_url: str = vs_stages[0]["image"]["url"]
        stage2_url: str = vs_stages[1]["image"]["url"]

        async with self.cs.get(stage1_url) as resp:
            stage1_png: bytes = await resp.read()

        async with self.cs.get(stage2_url) as resp:
            stage2_png: bytes = await resp.read()

        return await self.bot.loop.run_in_executor(None, vrt_concat_pngs, stage1_png, stage2_png)

    async def send_schedule(
            self,
            ctx: CustomContext,
            mode: MODE_LITERAL,
            index: int,
            send: Callable[..., Awaitable[Message]] = MISSING,
    ) -> Message:
        """Send a schedule message with embed, file, and view."""
        if send is MISSING:
            send = ctx.send

        files: list[tuple[str, bytes]] = []
        embed: Embed | None = None
        timeslots: list[TimeSlotData] = []

        async with aopen(join(getcwd(), "resources", "images", "splatoon3", "favicon.png"), "rb") as fp:
            files.append(("favicon.png", await fp.read()))

        match mode:
            case "Salmon Run":
                nodes: list[dict[str, Any]] = self.cached_schedules["coopGroupingSchedule"]["regularSchedules"]["nodes"]

                if isoparse(nodes[0]["endTime"]) < datetime.now(tzutc()):
                    nodes = nodes[1:]

                schedule: dict = nodes[index]
                start_time: datetime = isoparse(schedule["startTime"])
                end_time: datetime = isoparse(schedule["endTime"])
                timeslots: list[TimeSlotData] = TimeSlotData.from_nodes(nodes, mode)

                match_settings: dict = schedule["setting"]

                files.append(("weapons.png", await self._make_salmon_run_thumbnail(match_settings["weapons"])))

                embed: Embed = (
                    Embed(
                        title="Salmon Run",
                        color=SALMON_RUN_COLOR,
                    )
                    .set_thumbnail(
                        url="attachment://weapons.png"
                    )
                    .add_field(
                        name="Start Time",
                        value=format_dt(start_time, "R")
                    )
                    .add_field(
                        name="End Time",
                        value=format_dt(end_time, "R")
                    )
                    .add_field(
                        name="Stage",
                        value=match_settings["coopStage"]["name"],
                    )
                    .set_image(
                        url=match_settings["coopStage"]["image"]["url"]
                    )
                    .set_footer(
                        text="Powered by https://splatoon3.ink/",
                        icon_url="attachment://favicon.png"
                    )
                )

                for index, weapon in enumerate(match_settings["weapons"]):
                    embed = embed.add_field(
                        name=f"Weapon {index + 1}",
                        value=weapon["name"],
                        inline=False,
                    )
            case _:  # All other modes
                nodes: list[dict[str, Any]] = self.cached_schedules[MODE_DATA_SLOTS[mode]]["nodes"]

                if isoparse(nodes[0]["endTime"]) < datetime.now(tzutc()):
                    nodes = nodes[1:]

                timeslots: list[TimeSlotData] = TimeSlotData.from_nodes(nodes, mode)

                schedule: dict = nodes[index]
                start_time: datetime = isoparse(schedule["startTime"])
                end_time: datetime = isoparse(schedule["endTime"])

                color: int = MODE_COLORS[mode]

                if mode == "Splatfest Battle" and self.cached_schedules["currentFest"] is not None:
                    color = splatfest_color(choice(self.cached_schedules["currentFest"]["teams"])["color"])

                match_settings: list[dict] | None = schedule[MODE_SETTINGS_NAME[mode]]

                if match_settings is None:
                    embed = (
                        Embed(
                            title=mode,
                            color=color,
                            description="This game mode is not currently available.",
                        )
                        .set_footer(
                            text="Powered by https://splatoon3.ink/",
                            icon_url="attachment://favicon.png"
                        )
                    )
                else:
                    if mode == "Anarchy Battle (Series)":
                        match_settings: dict = match_settings[0]
                    elif mode == "Anarchy Battle (Open)":
                        match_settings: dict = match_settings[1]

                    rule: str = match_settings["vsRule"]["rule"]
                    rule_name: str = match_settings["vsRule"]["name"]

                    files.append(("stages.png", await self._make_two_stage_image(match_settings["vsStages"])))

                    embed = (
                        Embed(
                            title=f"{mode} "
                                  f"{ctx.bot.get_custom_emoji(f'{MODE_EMOJI_NAME[mode]}.png') or ''}",
                            color=color,
                            description=f"{rule_name} "
                                        f"{ctx.bot.get_custom_emoji(f'{_convert_rule_name_emoji(rule.lower())}.png') or ''}",
                        )
                        .add_field(
                            name="Start Time",
                            value=format_dt(start_time, "R")
                        )
                        .add_field(
                            name="End Time",
                            value=format_dt(end_time, "R")
                        )
                        .add_field(
                            name="Stage 1",
                            value=match_settings["vsStages"][0]["name"],
                            inline=False,
                        )
                        .add_field(
                            name="Stage 2",
                            value=match_settings["vsStages"][1]["name"],
                        )
                        .set_image(
                            url="attachment://stages.png"
                        )
                        .set_footer(
                            text="Powered by https://splatoon3.ink/",
                            icon_url="attachment://favicon.png"
                        )
                    )

        return await send(
            embed=embed,
            files=[File(fp=BytesIO(data), filename=name) for name, data in files] if len(files) > 0 else None,
        )

    async def send_splatfest(
            self,
            ctx: CustomContext,
            current: bool = True,
            index: int = 0,
            region: REGION_LITERAL = DEFAULT_REGION,
            send: Callable[..., Awaitable[Message]] = MISSING,
    ) -> Message:
        if send is MISSING:
            send = ctx.send

        if current:
            assert index == 0

        nodes: list[dict[str, Any]] = self.cached_festivals[region]["data"]["festRecords"]["nodes"]
        files: list[tuple[str, bytes]] = []
        historic_splatfests: list[SplatfestData] = SplatfestData.from_nodes(nodes)

        async with aopen(join(getcwd(), "resources", "images", "splatoon3", "favicon.png"), "rb") as fp:
            files.append(("favicon.png", await fp.read()))

        if current and self.cached_schedules["currentFest"] is None:
            embed: Embed = (
                Embed(
                    title="Splatfest",
                    color=SPLATFEST_UNSTARTED_COLOR,
                    description="There is no Splatfest currently running.",
                )
                .set_footer(
                    text="Powered by https://splatoon3.ink/",
                    icon_url="attachment://favicon.png"
                )
            )
        else:
            current_splatfest_info: dict | None = self.cached_schedules["currentFest"] if current else None
            historic_splatfest_info: dict = nodes[index]

            start_time: datetime = isoparse(historic_splatfest_info["startTime"])
            end_time: datetime = isoparse(historic_splatfest_info["endTime"])
            title: str = historic_splatfest_info["title"]
            state: SPLATFEST_STATES = historic_splatfest_info["state"]

            is_scheduled: bool = state == "scheduled"

            color: int = (
                SPLATFEST_UNSTARTED_COLOR
                if is_scheduled else
                splatfest_color(choice(historic_splatfest_info["teams"])["color"])
            )

            embed: Embed = (
                Embed(
                    title=title,
                    description=state.replace("_", " ").title(),
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
                    icon_url="attachment://favicon.png"
                )
            )

            if current:
                midterm: datetime = isoparse(current_splatfest_info["midtermTime"])
                # Midterm & tricolor data is only available for the current splatfest

                embed = (
                    embed.add_field(
                        name="Midterm Time",
                        value=format_dt(midterm, "R" if current else "D"),
                    )
                    .add_field(
                        name="Tricolor Stage",
                        value=historic_splatfest_info["tricolorStage"]["name"],
                        inline=False,
                    )
                )
            else:
                midterm: datetime = start_time + (end_time - start_time) / 2
                # approx. since we do not have exact

                embed = (
                    embed.add_field(
                        name="Midterm Time",
                        value=f"{format_dt(midterm, 'D')} (approx.)",
                    )
                    .add_field(
                        name="Tricolor Stage",
                        value="This data is not stored for previous Splatfests.",
                        inline=False,
                    )
                )

            test_team_shiver: dict = historic_splatfest_info["teams"][0]
            # Probably shiver's team in most cases, just named this for making code tidier.
            # Would still work (I think) if it wasn't shiver's team

            has_results: bool = "result" in test_team_shiver.keys() and test_team_shiver["result"] is not None
            # This is needlessly complicated, but oh well.

            if not current and has_results:
                for index, team in enumerate(historic_splatfest_info["teams"]):
                    if team['result']['isWinner']:
                        embed.color = splatfest_color(team['color'])  # type: ignore

                    line1: str = f"Was victorious: {'Yes' if team['result']['isWinner'] else 'No'}"
                    line2: str = f"Vote Percentage: `{team['result']['voteRatio'] * 100:.2f}`%"
                    line3: str = f"Pro Win Rate: `{team['result']['horagaiRatio'] * 100:.2f}`%"
                    line4: str = f"Open/Tricolor Win Rate: `{team['result']['regularContributionRatio'] * 100:.2f}`%"

                    embed = embed.add_field(
                        name=team["teamName"],
                        value=f"Color: `{rgb_human_readable(*splatfest_rgb(team['color']))}`\n"
                              f"{bold(line1, team['result']['isWinner'])}\n"
                              f"{bold(line2, team['result']['isVoteRatioTop'])}\n"
                              f"{bold(line3, team['result']['isHoragaiRatioTop'])}\n"
                              f"{bold(line4, team['result']['isRegularContributionRatioTop'])}",
                        inline=True,
                    )
            else:
                for index, team in enumerate(historic_splatfest_info["teams"]):
                    embed = embed.add_field(
                        name=team["teamName"],
                        value=f"Color: `{rgb_human_readable(*splatfest_rgb(team['color']))}`",
                        inline=True,
                    )

            if current:
                async with self.cs.get(current_splatfest_info["tricolorStage"]["image"]["url"]) as resp:
                    tricolor_stage_png: bytes = await resp.read()

                async with self.cs.get(historic_splatfest_info["image"]["url"]) as resp:
                    historic_splatfest_png: bytes = await resp.read()

                final_png: bytes = await self.bot.loop.run_in_executor(
                    None,
                    vrt_concat_pngs,
                    historic_splatfest_png,
                    tricolor_stage_png
                )

                files.append(("image.png", final_png))

                embed = embed.set_image(
                    url="attachment://image.png"
                )
            else:
                embed = embed.set_image(url=historic_splatfest_info["image"]["url"])

        return await send(
            embed=embed,
            files=[File(fp=BytesIO(data), filename=name) for name, data in files] if len(files) > 0 else None,
        )

    @group(
        aliases=[
            "splat",
            "splatoon",
            "sp",
            "sp3"
        ],
        fallback="schedule"
    )
    async def splatoon3(self, ctx: CustomContext, index: int = 0, *, mode: MODE_LITERAL = "Regular Battle") -> None:
        """
        Get information about the current scheduele of different game modes in Splatoon 3.
        Powered by https://splatoon3.ink/
        """
        async with ctx.typing():
            await self.send_schedule(ctx, mode, index)  # Patched in index for self

    # Todo: current version command? setup bs4 for scraping inkpedia but didnt finish

    @splatoon3.command()
    async def splatfest(
            self,
            ctx: CustomContext,
            current: bool = True,
            *,
            region: REGION_LITERAL = DEFAULT_REGION
    ) -> None:
        """
        Get information on the current splatfest or historical information on a splatfest.
        Powered by https://splatoon3.ink/
        """
        async with ctx.typing():
            await self.send_splatfest(ctx, current, 0, region)

    @splatoon3.command()
    async def salmon_run_gear(self, ctx: CustomContext) -> None:
        """
        Get information on this month's Salmon Run gear.
        Powered by https://splatoon3.ink/
        """
        async with ctx.typing():
            monthly_gear_info: dict[str, str | dict[str, str]] = self.cached_coop["monthlyGear"]

            embed: Embed = (
                Embed(
                    title="Salmon Run Gear",
                    color=SALMON_RUN_COLOR
                )
                .add_field(
                    name="Name",
                    value=monthly_gear_info["name"],
                )
                .add_field(
                    name="Slot",
                    value=monthly_gear_info["__typename"],
                )
                .set_image(
                    url=monthly_gear_info["image"]["url"]
                )
                .set_footer(
                    text="Powered by https://splatoon3.ink/",
                    icon_url="attachment://favicon.png"
                )
            )
            await ctx.send(embed=embed, file=File(join(getcwd(), "resources", "images", "splatoon3", "favicon.png")))

    @splatoon3.command()
    async def gear(self, ctx: CustomContext) -> None:
        """
        Get information on the currently available gear on SplatNet.
        Powered by https://splatoon3.ink/
        """
        await ctx.send("This command is a placeholder. Check back later for full support!", ephemeral=True)  # TODO


async def setup(bot: BOT_TYPES) -> None:
    await bot.add_cog(Splatoon3(bot))

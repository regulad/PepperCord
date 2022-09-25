from asyncio import gather
from datetime import datetime, tzinfo
from io import BytesIO
from random import choice
from typing import Literal, Any, cast, Type, Awaitable, Callable

from aiohttp import ClientSession
from dateutil.parser import isoparse
from dateutil.tz import tzutc
from discord import Embed, File, SelectOption, Interaction, Message
from discord.app_commands import describe
from discord.ext import tasks
from discord.ext.commands import Cog, hybrid_group, CheckFailure
from discord.ui import Select, View
from discord.utils import format_dt

from utils.bots import BOT_TYPES, CustomContext
from utils.consts import TIME_EMOJIS
from utils.images import svg2png, vrt_concat_pngs, hrz_concat_pngs
from utils.misc import rgb_human_readable

SPLATFEST_UNSTARTED_COLOR: int = 0x666775
REGULAR_BATTLE_COLOR: int = 0xcff622
RANKED_BATTLE_COLOR: int = 0xf54910
SALMON_RUN_COLOR: int = 0xff5600

TIMESLOT_LONG: str = "%m/%d"
TIMESLOT_SHORT: str = "%I:%M %p"
TIMESLOT_TZ: str = "%Z"

SPLATFEST_STATES: Type = Literal["SCHEDULED", "FIRST_HALF", "SECOND_HALF"]

MODE_LITERAL: Type = Literal[
    "Regular Battle",
    "Anarchy Battle (Series)",
    "Anarchy Battle (Open)",
    "Salmon Run",
    "Splatfest Battle",
]

REGION_LITERAL: Type = Literal[
    "US",
    "EU",
    "JP",
    "AP"
]
REGION_FULL_NAME: dict[REGION_LITERAL, str] = {
    "US": "The Americas, Australia, New Zealand",
    "EU": "Europe",
    "JP": "Japan",
    "AP": "Hong Kong, South Korea (Asia/Pacific)"
}
REGION_EMOJI: dict[REGION_LITERAL, str] = {
    "US": "🇺🇸",
    "EU": "🇪🇺",
    "JP": "🇯🇵",
    "AP": "🇭🇰"
}
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


def convert_mode_name(english: str) -> str:
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
        out: str = f"{self.start.astimezone(ctz).strftime(TIMESLOT_SHORT)} " \
                   f"- {self.end.astimezone(ctz).strftime(TIMESLOT_SHORT)} "
        if self.mode == "Salmon Run":
            out += f"({self.index + 1})"
        # Salmon run tends to run a lot longer. This is protection against two being the same
        return out

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


def send_wrap(send, *args, **kwargs) -> Any:
    if "files" in kwargs:
        if kwargs["files"] is not None:
            kwargs["attachments"] = kwargs["files"]
        else:
            kwargs["attachments"] = []
        del kwargs["files"]
    return send(*args, **kwargs)


class ScheduleSelectionMenu(Select):
    def __init__(self, ctx: CustomContext, data: list[TimeSlotData], mode: MODE_LITERAL, **attrs) -> None:
        self.ctx: CustomContext = ctx
        self.data: list[TimeSlotData] = data
        self.game: MODE_LITERAL = mode

        self.splatoon_3_cog: "Splatoon3" = cast("Splatoon3", self.ctx.bot.get_cog("Splatoon3"))

        options: list[SelectOption] = [
            SelectOption(
                label=timeslot.name,
                emoji=timeslot.emoji,
                description=timeslot.description,
            ) for timeslot in data
        ]

        super().__init__(placeholder="Timeslots", options=options, min_values=1, max_values=1, **attrs)

    def _get_timeslot(self, name: str) -> TimeSlotData | None:
        """
        Helper to get the timeslot info.
        """
        for timeslot in self.data:
            if timeslot.name == name:
                return timeslot
        else:
            return None

    async def callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()

        timeslot: TimeSlotData = self._get_timeslot(interaction.data["values"][0])

        await self.splatoon_3_cog.send_schedule(
            self.ctx,
            self.game,
            timeslot.index,
            lambda *args, **kwargs: send_wrap(self.ctx["response"].edit, *args, **kwargs)
        )


class ScheduleView(View):
    def __init__(self, ctx: CustomContext, data: list[TimeSlotData], mode: MODE_LITERAL, **attrs) -> None:
        self.ctx: CustomContext = ctx
        self.data: list[TimeSlotData] = data
        self.game: MODE_LITERAL = mode

        super().__init__(**attrs)

        self.add_item(ScheduleSelectionMenu(ctx, data, mode))


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

    async def _make_mode_rule_thumbnail(self, mode: str, rule: str) -> bytes:
        rule: str = convert_mode_name(rule)
        mode_url: str = f"https://github.com/misenhower/splatoon3.ink/raw/main/src/assets/img/modes/{mode}.svg"
        rule_url: str = f"https://github.com/misenhower/splatoon3.ink/raw/main/src/assets/img/rules/{rule}.svg"

        async with self.cs.get(mode_url) as resp:
            mode_svg: bytes = await resp.read()

        mode_png: bytes = await self.bot.loop.run_in_executor(None, svg2png, mode_svg)

        async with self.cs.get(rule_url) as resp:
            rule_svg: bytes = await resp.read()

        rule_png: bytes = await self.bot.loop.run_in_executor(None, svg2png, rule_svg)

        return await self.bot.loop.run_in_executor(None, vrt_concat_pngs, mode_png, rule_png)

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

    async def _compose_schedule_message(self, mode: MODE_LITERAL = "Regular Battle", index: int = 0) -> tuple[
        Embed | None,
        list[tuple[str, bytes]],
        list[TimeSlotData]
    ]:
        """
        Composes a message about the current schedule.
        """

        files: list[tuple[str, bytes]] = []

        match mode:
            case "Regular Battle":
                nodes: list[dict[str, Any]] = self.cached_schedules["regularSchedules"]["nodes"]

                if isoparse(nodes[0]["endTime"]) < datetime.now(tzutc()):
                    nodes = nodes[1:]

                schedule: dict = nodes[index]
                start_time: datetime = isoparse(schedule["startTime"])
                end_time: datetime = isoparse(schedule["endTime"])
                match_settings: dict | None = schedule["regularMatchSetting"]
                timeslots: list[TimeSlotData] = TimeSlotData.from_nodes(nodes, mode)

                if match_settings is None:
                    return (
                               Embed(
                                   title=mode,
                                   color=REGULAR_BATTLE_COLOR,
                                   description="This game mode is not currently available.",
                               )
                           ), files, timeslots
                else:
                    files.append(("thumbnail.png",
                                  await self._make_mode_rule_thumbnail("regular",
                                                                       match_settings["vsRule"]["rule"].lower())))
                    files.append(("stages.png", await self._make_two_stage_image(match_settings["vsStages"])))

                    return (
                               Embed(
                                   title=mode,
                                   color=REGULAR_BATTLE_COLOR,
                                   description=match_settings["vsRule"]["name"],
                               )
                               .set_thumbnail(
                                   url="attachment://thumbnail.png"
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
                           ), files, timeslots
            case "Anarchy Battle (Series)" | "Anarchy Battle (Open)":
                nodes: list[dict[str, Any]] = self.cached_schedules["bankaraSchedules"]["nodes"]

                if isoparse(nodes[0]["endTime"]) < datetime.now(tzutc()):
                    nodes = nodes[1:]

                schedule: dict = nodes[index]
                start_time: datetime = isoparse(schedule["startTime"])
                end_time: datetime = isoparse(schedule["endTime"])
                match_settings: list[dict] | None = schedule["bankaraMatchSettings"]
                timeslots: list[TimeSlotData] = TimeSlotData.from_nodes(nodes, mode)

                if match_settings is None:
                    return (
                               Embed(
                                   title=mode,
                                   color=RANKED_BATTLE_COLOR,
                                   description="This game mode is not currently available.",
                               )
                           ), files, timeslots
                else:
                    match_settings: dict = match_settings[0 if mode == "Anarchy Battle (Series)" else 1]

                    files.append(("thumbnail.png",
                                  await self._make_mode_rule_thumbnail("bankara",
                                                                       match_settings["vsRule"]["rule"].lower())))
                    files.append(("stages.png", await self._make_two_stage_image(match_settings["vsStages"])))

                    return (
                               Embed(
                                   title=mode,
                                   color=RANKED_BATTLE_COLOR,
                                   description=match_settings["vsRule"]["name"],
                               )
                               .set_thumbnail(
                                   url="attachment://thumbnail.png"
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
                           ), files, timeslots
            case "Splatfest Battle":
                if self.cached_schedules["currentFest"] is None:
                    return (
                               Embed(
                                   title=mode,
                                   color=SPLATFEST_UNSTARTED_COLOR,
                                   description="There is no Splatfest currently running.",
                               )
                           ), files, []
                else:
                    nodes: list[dict[str, Any]] = self.cached_schedules["festSchedules"]["nodes"]

                    if isoparse(nodes[0]["endTime"]) < datetime.now(tzutc()):
                        nodes = nodes[1:]

                    schedule: dict = nodes[index]
                    start_time: datetime = isoparse(schedule["startTime"])
                    end_time: datetime = isoparse(schedule["endTime"])
                    match_settings: dict | None = schedule["festMatchSetting"]
                    color: int = splatfest_color(choice(self.cached_schedules["currentFest"]["teams"])["color"])
                    timeslots: list[TimeSlotData] = TimeSlotData.from_nodes(nodes, mode)

                    if match_settings is None:
                        return (
                                   Embed(
                                       title=mode,
                                       color=color,
                                       description="The Splatfest has not yet started. Try looking in the future.",
                                   )
                               ), files, timeslots
                    else:
                        # I don't think there are any special assets for a splatfest, so this is fine?

                        files.append(("thumbnail.png",
                                      await self._make_mode_rule_thumbnail("regular",
                                                                           match_settings["vsRule"]["rule"].lower())))
                        files.append(("stages.png", await self._make_two_stage_image(match_settings["vsStages"])))

                        return (
                                   Embed(
                                       title=mode,
                                       color=color,
                                       description=match_settings["vsRule"]["name"],
                                   )
                                   .set_thumbnail(
                                       url="attachment://thumbnail.png"
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
                               ), files, timeslots
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
                )

                for index, weapon in enumerate(match_settings["weapons"]):
                    embed = embed.add_field(
                        name=f"Weapon {index + 1}",
                        value=weapon["name"],
                        inline=False,
                    )

                return embed, files, timeslots
            case _:
                return None, files, []

    async def send_schedule(
            self,
            ctx: CustomContext,
            mode: MODE_LITERAL,
            index: int,
            send: Callable[..., Awaitable[Message]]
            # my ass CANNOT be bothered to typehint this properly, this is good enough
    ) -> Message:
        # Slightly bodged, but it works real nice. TODO: Do something similar for splatfest history & splatnet gear
        """Send a schedule message with embed, file, and view."""

        embed, files, timeslots = await self._compose_schedule_message(mode, index)

        embed: Embed | None
        files: list[tuple[str, bytes]]
        timeslots: list[TimeSlotData]

        return await send(
            embed=embed,
            files=[File(fp=BytesIO(data), filename=name) for name, data in files] if len(files) > 0 else None,
            view=ScheduleView(ctx, timeslots, mode) if len(timeslots) > 0 else None,
        )

    @hybrid_group(
        aliases=[
            "splat",
            "splatoon",
            "sp",
            "sp3"
        ],
        fallback="schedule"
    )
    @describe(mode="The game mode to get information about.")
    async def splatoon3(self, ctx: CustomContext, *, mode: MODE_LITERAL = "Regular Battle") -> None:
        """
        Get information about the current scheduele of different game modes in Splatoon 3.
        Powered by https://splatoon3.ink/
        """
        async with ctx.typing():
            await self.send_schedule(ctx, mode, 0, ctx.send)

    # Todo: current version command? setup bs4 for scraping inkpedia but didnt finish

    @splatoon3.command()
    async def current_splatfest(self, ctx: CustomContext, region: REGION_LITERAL = DEFAULT_REGION) -> None:
        """
        Get information on the currently running Splatfest, if there is one.
        Powered by https://splatoon3.ink/
        """
        async with ctx.typing():
            splatfest_info: dict | None = self.cached_schedules["currentFest"]
            if splatfest_info is None:
                embed: Embed = (
                    Embed(
                        title="Splatfest",
                        color=SPLATFEST_UNSTARTED_COLOR,
                        description="There is no Splatfest currently running.",
                    )
                )

                await ctx.send(embed=embed)
            else:
                historic_splatfest_info: dict = self.cached_festivals[region]["data"]["festRecords"]["nodes"][0]

                start_time: datetime = isoparse(splatfest_info["startTime"])
                end_time: datetime = isoparse(splatfest_info["endTime"])
                midterm: datetime = isoparse(splatfest_info["midtermTime"])
                title: str = splatfest_info["title"]
                state: SPLATFEST_STATES = splatfest_info["state"]

                is_scheduled: bool = state == "scheduled"

                color: int = (
                    SPLATFEST_UNSTARTED_COLOR
                    if is_scheduled else
                    splatfest_color(choice(splatfest_info["teams"])["color"])
                )

                # This doesn't include team names, and I have zero idea why. Oh, well!

                embed: Embed = (
                    Embed(
                        title=title,
                        description=state.replace("_", " ").title(),
                        color=color,
                    )
                    .add_field(
                        name="Start Time",
                        value=format_dt(start_time, "R"),
                    )
                    .add_field(
                        name="End Time",
                        value=format_dt(end_time, "R"),
                    )
                    .add_field(
                        name="Midterm Time",
                        value=format_dt(midterm, "R"),
                    )
                    .add_field(
                        name="Tricolor Stage",
                        value=splatfest_info["tricolorStage"]["name"],
                        inline=False,
                    )
                    .set_image(
                        url="attachment://image.png"
                    )
                )

                # Image
                for index, team in enumerate(historic_splatfest_info["teams"]):
                    embed = embed.add_field(
                        name=team["teamName"],
                        value=f"Color: `{rgb_human_readable(*splatfest_rgb(team['color']))}`",
                        inline=True,
                    )

                async with self.cs.get(splatfest_info["tricolorStage"]["image"]["url"]) as resp:
                    tricolor_stage_png: bytes = await resp.read()

                async with self.cs.get(historic_splatfest_info["image"]["url"]) as resp:
                    historic_splatfest_png: bytes = await resp.read()

                final_png: bytes = await self.bot.loop.run_in_executor(None, vrt_concat_pngs, historic_splatfest_png,
                                                                       tricolor_stage_png)

                with BytesIO(final_png) as image_fp:
                    await ctx.send(
                        embed=embed,
                        file=File(fp=image_fp, filename="image.png"),
                    )

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
            )
            await ctx.send(embed=embed)

    @splatoon3.command()
    async def gear(self, ctx: CustomContext) -> None:
        """
        Get information on the currently available gear on SplatNet.
        Powered by https://splatoon3.ink/
        """
        await ctx.send("This command is a placeholder. Check back later for full support!", ephemeral=True)  # TODO

    @splatoon3.command()
    async def splatfest_history(self, ctx: CustomContext, *, region: REGION_LITERAL = DEFAULT_REGION) -> None:
        """
        Get information on previous Splatfests.
        Powered by https://splatoon3.ink/
        """
        await ctx.send("This command is a placeholder. Check back later for full support!", ephemeral=True)  # TODO


class Splatoon2(Cog):
    """
    Get information about the current status of Splatoon 2.
    Powered by https://splatoon2.ink/ and https://splatoonwiki.org/wiki/
    """

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot
        self.cs: ClientSession | None = None

        self.cached_schedules: Any | None = None
        self.cached_coop_schedules: Any | None = None
        self.cached_merchandises: Any | None = None
        self.cached_festivals: Any | None = None
        self.cached_timeline: Any | None = None

    @tasks.loop(hours=1)
    async def update_cache(self) -> None:
        # https://github.com/misenhower/splatoon2.ink/wiki/Data-access-policy recommends caching, so we will cache.
        if self.cs is not None and not self.cs.closed:
            async with self.cs.get("https://splatoon2.ink/data/schedules.json") as resp:
                self.cached_schedules = await resp.json()
            async with self.cs.get("https://splatoon2.ink/data/coop-schedules.json") as resp:
                self.cached_coop_schedules = await resp.json()
            async with self.cs.get("https://splatoon2.ink/data/merchandises.json") as resp:
                self.cached_merchandises = await resp.json()
            async with self.cs.get("https://splatoon2.ink/data/festivals.json") as resp:
                self.cached_festivals = await resp.json()
            async with self.cs.get("https://splatoon2.ink/data/timeline.json") as resp:
                self.cached_timeline = await resp.json()
            # TODO: find the useful parts of this data

    async def get_splatfest_ranking(self, region: REGION_LITERAL, festival_id: str) -> Any:
        async with self.cs.get(f"https://splatoon2.ink/data/festivals/{region}-{festival_id}-rankings.json") as resp:
            return await resp.json()

    @property
    def is_ready(self) -> bool:
        return all(
            (
                self.cached_schedules is not None,
                self.cached_coop_schedules is not None,
                self.cached_merchandises is not None,
                self.cached_festivals is not None,
                self.cached_timeline is not None
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

    # TODO: All of this. Maybe. Going to finish all of the Splatoon 3 stuff first, though.


async def setup(bot: BOT_TYPES) -> None:
    await gather(bot.add_cog(Splatoon3(bot)), bot.add_cog(Splatoon2(bot)))

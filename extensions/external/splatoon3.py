from datetime import datetime, timezone, tzinfo
from io import BytesIO
from random import choice
from typing import Literal, Any, cast, Type

from PIL import Image
from aiohttp import ClientSession
from dateutil.parser import isoparse
from dateutil.tz import tzutc
from discord import Embed, File, SelectOption, Interaction
from discord.app_commands import describe
from discord.ext import tasks
from discord.ext.commands import Cog, hybrid_group
from discord.ui import Select, View
from discord.utils import format_dt
from reportlab.graphics.renderPM import drawToFile
from reportlab.graphics.shapes import Drawing
from svglib.svglib import svg2rlg

from utils.bots import BOT_TYPES, CustomContext

SPLATFEST_UNSTARTED_COLOR: int = 0x666775
REGULAR_BATTLE_COLOR: int = 0xcff622
RANKED_BATTLE_COLOR: int = 0xf54910
SALMON_RUN_COLOR: int = 0xff5600

TIMESLOT_LONG: str = "%m/%d"
TIMESLOT_SHORT: str = "%I:%M %p"
TIMESLOT_TZ: str = "%Z"
TIMESLOT_EMOJIS: dict[int, str] = {
    0: "🕛",
    1: "🕐",
    2: "🕑",
    3: "🕒",
    4: "🕓",
    5: "🕔",
    6: "🕕",
    7: "🕖",
    8: "🕗",
    9: "🕘",
    10: "🕙",
    11: "🕚",
}

MODE_LITERAL: Type = Literal[
        "Regular Battle",
        "Anarchy Battle (Series)",
        "Anarchy Battle (Open)",
        "Salmon Run",
        "Splatfest Battle",

        "regular",
        "open",
        "series",
        "salmon",
        "splatfest"
    ]


def splatfest_color(colors: dict[str, float]) -> int:
    r: int = int(colors["r"] * 255)
    g: int = int(colors["g"] * 255)
    b: int = int(colors["b"] * 255)
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


def svg2png(svg: bytes) -> bytes:
    with BytesIO(svg) as svg_file, BytesIO() as png_file:
        drawing: Drawing = svg2rlg(svg_file)
        drawToFile(drawing, png_file, "png",
                   bg=0x000000)  # Transparent background doesn't want to work with this library.
        png_file.seek(0)
        return png_file.read()


def concat_pngs(png1: bytes, png2: bytes) -> bytes:
    with BytesIO(png1) as png1_file, BytesIO(png2) as png2_file, BytesIO() as buffer:
        image1: Image.Image = Image.open(png1_file)
        image2: Image.Image = Image.open(png2_file)

        if image2.size != image1.size:
            image2: Image.Image = image2.resize((image1.width, image1.height), Image.ANTIALIAS)

        buffer_img: Image.Image = Image.new("RGBA", (image1.width, image1.height + image2.height))
        buffer_img.paste(image1, (0, 0))
        buffer_img.paste(image2, (0, image1.height))

        buffer_img.save(buffer, "PNG")
        buffer.seek(0)
        return buffer.read()


class TimeSlotData:  # This could probably extend SelectOption, but this is separate for the sake of selfbot support.
    def __init__(self, start: datetime, end: datetime, index: int) -> None:
        self.start: datetime = start
        self.end: datetime = end
        self.index: int = index

    @classmethod
    def from_nodes(cls, nodes: list[dict[str, Any]]) -> list["TimeSlotData"]:
        return [cls(isoparse(node["startTime"]), isoparse(node["endTime"]), index) for index, node in enumerate(nodes)]

    __slots__ = ("start", "end", "index")

    @property
    def name(self) -> str:
        now: datetime = datetime.now()
        ctz: tzinfo = now.tzinfo
        now = now.astimezone(ctz)  # weird.
        return f"{self.start.astimezone(ctz).strftime(TIMESLOT_SHORT)} " \
               f"- {self.end.astimezone(ctz).strftime(TIMESLOT_SHORT)} "

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

        if hour > 11:
            hour -= 12

        return TIMESLOT_EMOJIS[hour]

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
    """Get information about the current status of Splatoon 3. Powered by https://splatoon3.ink/"""

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

    async def _make_thumbnail(self, mode: str, rule: str) -> bytes:
        rule: str = convert_mode_name(rule)
        mode_url: str = f"https://github.com/misenhower/splatoon3.ink/raw/main/src/assets/img/modes/{mode}.svg"
        rule_url: str = f"https://github.com/misenhower/splatoon3.ink/raw/main/src/assets/img/rules/{rule}.svg"

        async with self.cs.get(mode_url) as resp:
            mode_svg: bytes = await resp.read()

        mode_png: bytes = await self.bot.loop.run_in_executor(None, svg2png, mode_svg)

        async with self.cs.get(rule_url) as resp:
            rule_svg: bytes = await resp.read()

        rule_png: bytes = await self.bot.loop.run_in_executor(None, svg2png, rule_svg)

        return await self.bot.loop.run_in_executor(None, concat_pngs, mode_png, rule_png)

    async def _two_stage_thumbnail(self, vs_stages: list[dict[str, Any | dict[str, str]]]) -> bytes:
        stage1_url: str = vs_stages[0]["image"]["url"]
        stage2_url: str = vs_stages[1]["image"]["url"]

        async with self.cs.get(stage1_url) as resp:
            stage1_png: bytes = await resp.read()

        async with self.cs.get(stage2_url) as resp:
            stage2_png: bytes = await resp.read()

        return await self.bot.loop.run_in_executor(None, concat_pngs, stage1_png, stage2_png)

    async def _compose_schedule_message(self, game: MODE_LITERAL = "Regular Battle", index: int = 0) -> tuple[
        Embed | None,
        list[tuple[str, bytes]],
        list[TimeSlotData]
    ]:
        """
        Composes a message about the current schedule.
        """

        files: list[tuple[str, bytes]] = []

        match game:
            case "Regular Battle" | "regular":
                game: str = "Regular Battle"

                nodes: list[dict[str, Any]] = self.cached_schedules["regularSchedules"]["nodes"]

                if isoparse(nodes[0]["endTime"]) < datetime.now(tzutc()):
                    nodes = nodes[1:]

                schedule: dict = nodes[index]
                start_time: datetime = isoparse(schedule["startTime"])
                end_time: datetime = isoparse(schedule["endTime"])
                match_settings: dict | None = schedule["regularMatchSetting"]
                timeslots: list[TimeSlotData] = TimeSlotData.from_nodes(nodes)

                if match_settings is None:
                    return (
                               Embed(
                                   title=game,
                                   color=REGULAR_BATTLE_COLOR,
                                   description="This game mode is not currently available.",
                               )
                           ), files, timeslots
                else:
                    files.append(("thumbnail.png",
                                  await self._make_thumbnail("regular", match_settings["vsRule"]["rule"].lower())))
                    files.append(("stages.png", await self._two_stage_thumbnail(match_settings["vsStages"])))

                    return (
                               Embed(
                                   title=game,
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
            case "Anarchy Battle (Series)" | "Anarchy Battle (Open)" | "open" | "series":
                game: str = "Anarchy Battle (Series)" if game == "series" or game == "Anarchy Battle (Series)" else "Anarchy Battle (Open)"

                nodes: list[dict[str, Any]] = self.cached_schedules["bankaraSchedules"]["nodes"]

                if isoparse(nodes[0]["endTime"]) < datetime.now(tzutc()):
                    nodes = nodes[1:]

                schedule: dict = nodes[index]
                start_time: datetime = isoparse(schedule["startTime"])
                end_time: datetime = isoparse(schedule["endTime"])
                match_settings: list[dict] | None = schedule["bankaraMatchSettings"]
                timeslots: list[TimeSlotData] = TimeSlotData.from_nodes(nodes)

                if match_settings is None:
                    return (
                               Embed(
                                   title=game,
                                   color=RANKED_BATTLE_COLOR,
                                   description="This game mode is not currently available.",
                               )
                           ), files, timeslots
                else:
                    match_settings: dict = match_settings[0 if game == "Anarchy Battle (Series)" else 1]

                    files.append(("thumbnail.png",
                                  await self._make_thumbnail("bankara", match_settings["vsRule"]["rule"].lower())))
                    files.append(("stages.png", await self._two_stage_thumbnail(match_settings["vsStages"])))

                    return (
                               Embed(
                                   title=game,
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
            case "Splatfest Battle" | "splatfest":
                game: str = "Splatfest Battle"

                if self.cached_schedules["currentFest"] is None:
                    return (
                               Embed(
                                   title=game,
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
                    timeslots: list[TimeSlotData] = TimeSlotData.from_nodes(nodes)

                    if match_settings is None:
                        return (
                                   Embed(
                                       title=game,
                                       color=color,
                                       description="The Splatfest has not yet started. Try looking in the future.",
                                   )
                               ), files, timeslots
                    else:
                        # I don't think there are any special assets for a splatfest, so this is fine?

                        files.append(("thumbnail.png",
                                      await self._make_thumbnail("regular", match_settings["vsRule"]["rule"].lower())))
                        files.append(("stages.png", await self._two_stage_thumbnail(match_settings["vsStages"])))

                        return (
                                   Embed(
                                       title=game,
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
            # case "Salmon Run" | "salmon":
            #     schedule: dict = self.cached_schedules["coopGroupingSchedule"]["regularSchedules"][index]
            #     embed: Embed = (
            #         Embed(
            #             title="Salmon Run",
            #             color=SALMON_RUN_COLOR,
            #         )
            #     )
            case _:
                return None, files, []

    async def send_schedule(self, ctx: CustomContext, mode: MODE_LITERAL, index: int, send) -> Any | None:
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
        # This could be a memory leak, but it should be cleaned up after the 180.0 second timeout.

    @hybrid_group(aliases=["splat", "splatoon3", "sp"], fallback="schedule")
    @describe(mode="The game mode to get information about.")
    async def splatoon(
            self,
            ctx: CustomContext,
            mode: MODE_LITERAL = "Regular Battle",
    ) -> None:
        """
        Get information about the current status of different game modes in Splatoon 3.
        Powered by https://splatoon3.ink/
        """
        if self.cached_schedules is None:
            await ctx.send("The cache has not been initialized yet. Please try again in a few seconds.", ephemeral=True)
            return

        async with ctx.typing():
            await self.send_schedule(ctx, mode, 0, ctx.send)

    @splatoon.command()
    async def splatfestinfo(self, ctx: CustomContext) -> None:
        """
        Get information on the currently running Splatfest, if there is one.
        Powered by https://splatoon3.ink/
        """
        if self.cached_schedules is None:
            await ctx.send("The cache has not been initialized yet. Please try again in a few seconds.", ephemeral=True)
            return

        splatfest_info: dict | None = self.cached_schedules["currentFest"]
        if splatfest_info is None:
            embed: Embed = (
                Embed(
                    title="Splatfest",
                    color=SPLATFEST_UNSTARTED_COLOR,
                    description="There is no Splatfest currently running.",
                )
            )
        else:
            start_time: datetime = isoparse(splatfest_info["startTime"])
            end_time: datetime = isoparse(splatfest_info["endTime"])
            midterm: datetime = isoparse(splatfest_info["midtermTime"])
            title: str = splatfest_info["title"]
            state: Literal["SCHEDULED", "FIRST_HALF", "SECOND_HALF"] = splatfest_info["state"]

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
                    name="Stage",
                    value=splatfest_info["tricolorStage"]["name"],
                    inline=False,
                )
                .set_image(
                    url=splatfest_info["tricolorStage"]["image"]["url"]
                )
            )
        await ctx.send(embed=embed)

    @splatoon.command()
    async def salmonrungear(self, ctx: CustomContext) -> None:
        """
        Get information on this month's Salmon Run gear.
        Powered by https://splatoon3.ink/
        """
        if self.cached_coop is None:
            await ctx.send("The cache has not been initialized yet. Please try again in a few seconds.", ephemeral=True)
            return

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

    # @splatoon.command()
    # async def gear(self, ctx: CustomContext) -> None:
    #     """
    #     Get information on the currently available gear on SplatNet.
    #     Powered by https://splatoon3.ink/
    #     """
    #     pass  # TODO: This will be a nightmare with Views, oh my!


async def setup(bot: BOT_TYPES) -> None:
    await bot.add_cog(Splatoon3(bot))

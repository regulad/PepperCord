from datetime import datetime
from io import BytesIO
from random import choice
from typing import Literal, Any

from PIL import Image
from aiohttp import ClientSession
from dateutil.parser import isoparse
from dateutil.tz import tz
from discord import Embed, File
from discord.ext import tasks
from discord.ext.commands import Cog, group
from discord.utils import format_dt
from reportlab.graphics.renderPM import drawToFile
from reportlab.graphics.shapes import Drawing
from svglib.svglib import svg2rlg

from utils.bots import BOT_TYPES, CustomContext


SPLATFEST_UNSTARTED_COLOR: int = 0x666775
REGULAR_BATTLE_COLOR: int = 0xcff622
RANKED_BATTLE_COLOR: int = 0xf54910
SALMON_RUN_COLOR: int = 0xff5600


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

    @group(aliases=["splat", "splatoon3", "sp"])
    async def splatoon(
            self,
            ctx: CustomContext,
            game: Literal[
                "Regular Battle",
                "Anarchy Battle (Series)",
                "Anarchy Battle (Open)",
                "Salmon Run",
                "Splatfest Battle",
                "Tricolor Battle",

                "regular",
                "open",
                "series",
                "salmon",
                "splatfest",
                "tricolor"
            ] = "Regular Battle",
            index: Literal[
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                10,
                11,
            ] = 0
    ) -> None:
        """
        Get information about the current status of different game modes in Splatoon 3.
        Powered by https://splatoon3.ink/
        """
        if self.cached_schedules is None:
            await ctx.send("The cache has not been initialized yet. Please try again in a few seconds.", ephemeral=True)
            return

        if game == "Salmon Run" and index > 4:
            await ctx.send("Salmon Run only has 5 stages sent in advance. Please reenter your command.", ephemeral=True)
            return
        # We *could* cache the whole embed and the images that are generated, but we don't really need to.

        final_thumbnail_png: bytes | None = None
        final_stage_png: bytes | None = None

        match game:
            case "Regular Battle" | "regular":
                game: str = "Regular Battle"

                schedule: dict = self.cached_schedules["regularSchedules"]["nodes"][index]
                start_time: datetime = isoparse(schedule["startTime"])
                end_time: datetime = isoparse(schedule["endTime"])
                match_settings: dict = schedule["regularMatchSetting"]

                thumbnail_url: str = "https://github.com/misenhower/splatoon3.ink/raw/main/src/assets/img/modes/regular.svg"
                mode_url: str = f"https://github.com/misenhower/splatoon3.ink/raw/main/src/assets/img/rules/{convert_mode_name(match_settings['vsRule']['rule'].lower())}.svg"
                embed: Embed

                # Thumbnail code
                async with self.cs.get(thumbnail_url) as resp:
                    thumbnail_svg: bytes = await resp.read()
                    # This could be cached, but I can't be bothered to implement a cache for this.

                thumbnail_png: bytes = await ctx.bot.loop.run_in_executor(None, svg2png, thumbnail_svg)

                async with self.cs.get(mode_url) as resp:
                    mode_svg: bytes = await resp.read()
                    # This could be cached, but I can't be bothered to implement a cache for this.

                mode_png: bytes = await ctx.bot.loop.run_in_executor(
                    None,
                    svg2png,
                    mode_svg
                )

                final_thumbnail_png: bytes = await ctx.bot.loop.run_in_executor(
                    None,
                    concat_pngs,
                    thumbnail_png,
                    mode_png
                )

                # Stage code
                stage1_url: str = match_settings["vsStages"][0]["image"]["url"]
                stage2_url: str = match_settings["vsStages"][1]["image"]["url"]

                async with self.cs.get(stage1_url) as resp:
                    stage1_png: bytes = await resp.read()
                    # This could be cached, but I can't be bothered to implement a cache for this.

                async with self.cs.get(stage2_url) as resp:
                    stage2_png: bytes = await resp.read()

                final_stage_png: bytes = await ctx.bot.loop.run_in_executor(None, concat_pngs, stage1_png, stage2_png)

                embed: Embed = (
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
                )
            case "Anarchy Battle (Series)" | "Anarchy Battle (Open)" | "open" | "series":
                game: str = "Anarchy Battle (Series)" if game == "series" or game == "Anarchy Battle (Series)" else "Anarchy Battle (Open)"

                schedule: dict = self.cached_schedules["bankaraSchedules"]["nodes"][index]
                start_time: datetime = isoparse(schedule["startTime"])
                end_time: datetime = isoparse(schedule["endTime"])
                match_settings: dict = schedule["bankaraMatchSettings"][0 if game == "Anarchy Battle (Series)" else 1]

                thumbnail_url: str = "https://github.com/misenhower/splatoon3.ink/raw/main/src/assets/img/modes/bankara.svg"
                mode_url: str = f"https://github.com/misenhower/splatoon3.ink/raw/main/src/assets/img/rules/{convert_mode_name(match_settings['vsRule']['rule'].lower())}.svg"

                # Thumbnail code
                async with self.cs.get(thumbnail_url) as resp:
                    thumbnail_svg: bytes = await resp.read()
                    # This could be cached, but I can't be bothered to implement a cache for this.

                thumbnail_png: bytes = await ctx.bot.loop.run_in_executor(None, svg2png, thumbnail_svg)

                async with self.cs.get(mode_url) as resp:
                    mode_svg: bytes = await resp.read()
                    # This could be cached, but I can't be bothered to implement a cache for this.

                mode_png: bytes = await ctx.bot.loop.run_in_executor(
                    None,
                    svg2png,
                    mode_svg
                )

                final_thumbnail_png: bytes = await ctx.bot.loop.run_in_executor(
                    None,
                    concat_pngs,
                    thumbnail_png,
                    mode_png
                )

                # Stage code
                stage1_url: str = match_settings["vsStages"][0]["image"]["url"]
                stage2_url: str = match_settings["vsStages"][1]["image"]["url"]

                async with self.cs.get(stage1_url) as resp:
                    stage1_png: bytes = await resp.read()
                    # This could be cached, but I can't be bothered to implement a cache for this.

                async with self.cs.get(stage2_url) as resp:
                    stage2_png: bytes = await resp.read()

                final_stage_png: bytes = await ctx.bot.loop.run_in_executor(None, concat_pngs, stage1_png, stage2_png)

                embed: Embed = (
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
                )
            case "Splatfest Battle" | "splatfest":
                game: str = "Splatfest Battle"

                if self.cached_schedules["currentFest"] is None:
                    embed: Embed = (
                        Embed(
                            title=game,
                            description="There is no Splatfest currently running.",
                        )
                    )
                else:
                    schedule: dict = self.cached_schedules["festSchedules"]["nodes"][index]
                    start_time: datetime = isoparse(schedule["startTime"])
                    end_time: datetime = isoparse(schedule["endTime"])
                    match_settings: dict | None = schedule["festMatchSetting"]
                    color: int = splatfest_color(choice(self.cached_schedules["currentFest"]["teams"])["color"])

                    if match_settings is None:
                        embed: Embed = (
                            Embed(
                                title=game,
                                color=color,
                                description="The Splatfest has not yet started. Try looking in the future.",
                            )
                        )
                    else:
                        # fixme: Splatfest assets aren't available yet, add this when they are
                        # thumbnail_url: str = "https://github.com/misenhower/splatoon3.ink/raw/main/src/assets/img/modes/regular.svg"  # update
                        # mode_url: str = f"https://github.com/misenhower/splatoon3.ink/raw/main/src/assets/img/rules/{convert_mode_name(match_settings['vsRule']['rule'].lower())}.svg"
                        #
                        # # Thumbnail code
                        # async with self.cs.get(thumbnail_url) as resp:
                        #     thumbnail_svg: bytes = await resp.read()
                        #     # This could be cached, but I can't be bothered to implement a cache for this.
                        #
                        # thumbnail_png: bytes = await ctx.bot.loop.run_in_executor(None, svg2png, thumbnail_svg)
                        #
                        # async with self.cs.get(mode_url) as resp:
                        #     mode_svg: bytes = await resp.read()
                        #     # This could be cached, but I can't be bothered to implement a cache for this.
                        #
                        # mode_png: bytes = await ctx.bot.loop.run_in_executor(
                        #     None,
                        #     svg2png,
                        #     mode_svg
                        # )
                        #
                        # final_thumbnail_png: bytes = await ctx.bot.loop.run_in_executor(
                        #     None,
                        #     concat_pngs,
                        #     thumbnail_png,
                        #     mode_png
                        # )

                        stage1_url: str = match_settings["vsStages"][0]["image"]["url"]
                        stage2_url: str = match_settings["vsStages"][1]["image"]["url"]

                        async with self.cs.get(stage1_url) as resp:
                            stage1_png: bytes = await resp.read()
                            # This could be cached, but I can't be bothered to implement a cache for this.

                        async with self.cs.get(stage2_url) as resp:
                            stage2_png: bytes = await resp.read()

                        final_stage_png: bytes = await ctx.bot.loop.run_in_executor(None, concat_pngs, stage1_png,
                                                                                    stage2_png)

                        embed: Embed = (
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
                        )
            case "Tricolor Battle" | "tricolor":
                game: str = "Tricolor Battle"

                if self.cached_schedules["currentFest"] is None:
                    embed: Embed = (
                        Embed(
                            title=game,
                            description="There is no Splatfest currently running.",
                        )
                    )
                else:
                    color: int = splatfest_color(choice(self.cached_schedules["currentFest"]["teams"])["color"])
                    midterm: datetime = isoparse(self.cached_schedules["currentFest"]["midtermTime"])
                    has_started: bool = datetime.now(tz.tzutc()) > midterm
                    embed: Embed = (
                        Embed(
                            title=game,
                            color=color,
                            description="The Tricolor Battle has not yet started."
                                        if not has_started else "Tricolor Battle is currently running!",
                        )
                        .add_field(
                            name="Start Time",
                            value=format_dt(midterm, "R"),
                            inline=False,
                        )
                        .add_field(
                            name="Stage",
                            value=self.cached_schedules["currentFest"]["tricolorStage"]["name"],
                            inline=False,
                        )
                        .set_image(
                            url=self.cached_schedules["currentFest"]["tricolorStage"]["image"]["url"]
                        )
                    )
            # case "Salmon Run" | "salmon":
            #     schedule: dict = self.cached_schedules["coopGroupingSchedule"]["regularSchedules"][index]
            #     embed: Embed = (
            #         Embed(
            #             title="Salmon Run",
            #             color=SALMON_RUN_COLOR,
            #         )
            #     )
            case _:
                await ctx.send(
                    "Invalid game mode. Salmon Run and Big Run information is not yet available through this command.",
                    ephemeral=True
                )
                return

        async with ctx.typing():
            if final_thumbnail_png is not None and final_stage_png is not None:
                with BytesIO(final_thumbnail_png) as thumbnail_fp, BytesIO(final_stage_png) as stage_fp:
                    thumbnail_file: File = File(thumbnail_fp, filename="thumbnail.png")
                    stage_file: File = File(stage_fp, filename="stages.png")
                    await ctx.send(embed=embed, files=[thumbnail_file, stage_file])
            elif final_thumbnail_png is not None and final_stage_png is None:
                with BytesIO(final_thumbnail_png) as thumbnail_fp:
                    thumbnail_file: File = File(thumbnail_fp, filename="thumbnail.png")
                    await ctx.send(embed=embed, files=[thumbnail_file,])
            elif final_thumbnail_png is None and final_stage_png is not None:
                with BytesIO(final_stage_png) as stage_fp:
                    stage_file: File = File(stage_fp, filename="stages.png")
                    await ctx.send(embed=embed, files=[stage_file,])
            else:
                await ctx.send(embed=embed)

    @splatoon.command()
    async def splatfestinfo(self, ctx: CustomContext) -> None:
        """
        Get information on the currently running Splatfest, if there is one.
        Powered by https://splatoon3.ink/
        """
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
            state: str = splatfest_info["state"]

            is_scheduled: bool = state == "scheduled"

            color: int = (
                SPLATFEST_UNSTARTED_COLOR
                if is_scheduled else
                splatfest_color(choice(splatfest_info["teams"])["color"])
            )

            # This doesn't include team names, and I have zero idea why.

            # I have choesn to have the tricolor to be part of the schedules and not the splatfest info to avoid spoilers.

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
            )
        await ctx.send(embed=embed)


    @splatoon.command()
    async def salmonrungear(self, ctx: CustomContext) -> None:
        """
        Get information on this month's Salmon Run gear.
        Powered by https://splatoon3.ink/
        """
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

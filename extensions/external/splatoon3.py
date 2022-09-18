from datetime import datetime
from io import BytesIO
from typing import Literal, Any

from PIL import Image
from aiohttp import ClientSession
from dateutil.parser import isoparse
from discord import Embed, File
from discord.ext import tasks
from discord.ext.commands import Cog, group
from discord.utils import format_dt
from reportlab.graphics.renderPM import drawToFile
from reportlab.graphics.shapes import Drawing
from svglib.svglib import svg2rlg

from utils.bots import BOT_TYPES, CustomContext


def convert_mode_name(english: str) -> str:
    match english:
        case "clam":
            return "asari"
        case "loft":
            return "yagura"
        case "goal":
            return "hoko"
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
                self.cached_gear = await resp.json()
            async with self.cs.get("https://splatoon3.ink/data/coop.json") as resp:
                self.cached_coop = await resp.json()
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

    @group(aliases=["splat", "splatoon3"])
    async def splatoon(
            self,
            ctx: CustomContext,
            game: Literal[
                "Regular Battle",
                "Anarchy Battle (Series)",
                "Anarchy Battle (Open)",
                "Salmon Run",
                "Splatfest"
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

        if game == "Splatfest" and self.cached_schedules["currentFest"] is None:
            await ctx.send("There is no Splatfest currently running.", ephemeral=True)
            return
        # We *could* cache the whole embed and the images that are generated, but we don't really need to.

        match game:
            case "Regular Battle":
                schedule: dict = self.cached_schedules["regularSchedules"]["nodes"][index]
                start_time: datetime = isoparse(schedule["startTime"])
                end_time: datetime = isoparse(schedule["endTime"])
                match_settings: dict = schedule["regularMatchSetting"]
                thumbnail_svg_url: str = "https://github.com/misenhower/splatoon3.ink/raw/main/src/assets/img/modes/regular.svg"
                alt_thumbnail_svg_url: str | None = None
                stage1_url: str = match_settings["vsStages"][0]["image"]["url"]
                stage2_url: str = match_settings["vsStages"][1]["image"]["url"]
                embed: Embed = (
                    Embed(
                        title="Regular Battle",
                        color=0xcff622,
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
            case "Anarchy Battle (Series)":
                schedule: dict = self.cached_schedules["bankaraSchedules"]["nodes"][index]
                start_time: datetime = isoparse(schedule["startTime"])
                end_time: datetime = isoparse(schedule["endTime"])
                match_settings: dict = schedule["bankaraMatchSettings"][0]
                thumbnail_svg_url: str = "https://github.com/misenhower/splatoon3.ink/raw/main/src/assets/img/modes/bankara.svg"
                alt_thumbnail_svg_url: str | None = f"https://github.com/misenhower/splatoon3.ink/raw/main/src/assets/img/rules/{convert_mode_name(match_settings['vsRule']['rule'].lower())}.svg"
                stage1_url: str = match_settings["vsStages"][0]["image"]["url"]
                stage2_url: str = match_settings["vsStages"][1]["image"]["url"]
                embed: Embed = (
                    Embed(
                        title="Anarchy Battle (Series)",
                        color=0xf54910,
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
            case "Anarchy Battle (Open)":
                schedule: dict = self.cached_schedules["bankaraSchedules"]["nodes"][index]
                start_time: datetime = isoparse(schedule["startTime"])
                end_time: datetime = isoparse(schedule["endTime"])
                match_settings: dict = schedule["bankaraMatchSettings"][1]
                thumbnail_svg_url: str = "https://github.com/misenhower/splatoon3.ink/raw/main/src/assets/img/modes/bankara.svg"
                alt_thumbnail_svg_url: str | None = f"https://github.com/misenhower/splatoon3.ink/raw/main/src/assets/img/rules/{convert_mode_name(match_settings['vsRule']['rule'].lower())}.svg"
                stage1_url: str = match_settings["vsStages"][0]["image"]["url"]
                stage2_url: str = match_settings["vsStages"][1]["image"]["url"]
                embed: Embed = (
                    Embed(
                        title="Anarchy Battle (Open)",
                        color=0xf54910,
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
            # case "Salmon Run":
            #     schedule: dict = self.cached_schedules["coopGroupingSchedule"]["regularSchedules"][index]
            #     embed: Embed = (
            #         Embed(
            #             title="Salmon Run",
            #         )
            #     )
            # case "Splatfest":
            #     schedule: dict = self.cached_schedules["festSchedules"][index]
            #     embed: Embed = (
            #         Embed(
            #             title="Splatfest",
            #         )
            #     )
            # There are also "xSchedules" and "leagueSchedules" but I have no idea what they do in Splatoon 3.
            # Salmon Runs and Splatfests are not implemented yet. Saving this code for later.
            case _:
                await ctx.send("Invalid game mode. Salmon Run and Splatfests are not yet implemented.", ephemeral=True)
                return

        async with ctx.typing():
            # Thumbnail code
            async with self.cs.get(thumbnail_svg_url) as resp:
                thumbnail_svg: bytes = await resp.read()
                # This could be cached, but I can't be bothered to implement a cache for this.

            thumbnail_png: bytes = await ctx.bot.loop.run_in_executor(None, svg2png, thumbnail_svg)

            if alt_thumbnail_svg_url is not None:
                async with self.cs.get(alt_thumbnail_svg_url) as resp:
                    alt_thumbnail_svg: bytes = await resp.read()
                    # This could be cached, but I can't be bothered to implement a cache for this.

                alt_thumbnail_png: bytes = await ctx.bot.loop.run_in_executor(
                    None,
                    svg2png,
                    alt_thumbnail_svg
                )

                final_thumbnail_png: bytes = await ctx.bot.loop.run_in_executor(
                    None,
                    concat_pngs,
                    thumbnail_png,
                    alt_thumbnail_png
                )
            else:
                final_thumbnail_png: bytes = thumbnail_png

            # Stage image code
            async with self.cs.get(stage1_url) as resp:
                stage1_png: bytes = await resp.read()
                # This could be cached, but I can't be bothered to implement a cache for this.

            async with self.cs.get(stage2_url) as resp:
                stage2_png: bytes = await resp.read()

            final_stage_png: bytes = await ctx.bot.loop.run_in_executor(None, concat_pngs, stage1_png, stage2_png)

            with BytesIO(final_thumbnail_png) as thumbnail_fp, BytesIO(final_stage_png) as stage_fp:
                thumbnail_file: File = File(thumbnail_fp, filename="thumbnail.png")
                stage_file: File = File(stage_fp, filename="stages.png")
                await ctx.send(embed=embed, files=[thumbnail_file, stage_file])


async def setup(bot: BOT_TYPES) -> None:
    await bot.add_cog(Splatoon3(bot))

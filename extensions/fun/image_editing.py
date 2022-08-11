from functools import partial
from io import BytesIO
from typing import Optional

import discord
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands
from discord.ext.commands import command

from utils.bots import CustomContext, BOT_TYPES


def pins_left_executor(pins_left: int) -> BytesIO:
    buffer = BytesIO()
    save_image = Image.open("resources/images/blank.png")
    arial_narrow_bold_font = ImageFont.truetype(
        "resources/images/arial-narrow-bold.ttf", 72
    )
    image_draw = ImageDraw.Draw(save_image)
    image_draw.text(
        xy=(650, 490),
        text=f"-{pins_left} {'Pins' if pins_left != 1 else 'Pin'} {'Remain' if pins_left != 1 else 'Remains'}-",
        stroke_fill="#FFFFFF",
        font=arial_narrow_bold_font,
        anchor="ms",
    )
    save_image.save(buffer, "PNG")
    buffer.seek(0)
    return buffer


class Images(commands.Cog):
    """Tools to edit images, and make things with them."""

    def __init__(self, bot: BOT_TYPES):
        self.bot: BOT_TYPES = bot

    @command()
    @commands.cooldown(1, 40, commands.BucketType.channel)
    async def pinsleft(
            self,
            ctx: CustomContext,
            *,
            channel: Optional[discord.TextChannel],
    ) -> None:
        """Shows how many pins are left in a channel in a wonderfully flashy way."""
        channel: discord.TextChannel = channel or ctx.channel
        async with ctx.typing():
            pins_left = 50 - len(await channel.pins())
            with await ctx.bot.loop.run_in_executor(
                    None, partial(pins_left_executor, pins_left)
            ) as buffer:
                await ctx.send(file=discord.File(buffer, "pinsleft.png"))


async def setup(bot: BOT_TYPES) -> None:
    await bot.add_cog(Images(bot))

import typing
from io import BytesIO

import discord
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands


def pins_left_executor(pins_left: int) -> BytesIO:
    buffer: BytesIO = BytesIO()
    save_image = Image.open("resources/blank.png")
    arial_narrow_bold_font = ImageFont.truetype("resources/arial-narrow-bold.ttf", 72)
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

    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="pinsleft",
        description="Shows the amount of pins left, in a rather flashy way.",
        brief="Shows the amount of pins left.",
        usage="[Channel]",
    )
    @commands.cooldown(1, 40, commands.BucketType.channel)
    async def pins_left(self, ctx, *, channel: typing.Optional[discord.TextChannel]):
        async with ctx.typing():
            channel = channel or ctx.channel
            pins_left = 50 - len(await channel.pins())
            # It's possible that discord could change the max pins for boosted servers, breaking this.
            buffer = await ctx.bot.loop.run_in_executor(None, lambda: pins_left_executor(pins_left))
            file = discord.File(buffer, "majora.png")
            await ctx.send(file=file)


def setup(bot):
    bot.add_cog(Images(bot))

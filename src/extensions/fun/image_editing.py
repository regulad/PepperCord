from functools import partial
from io import BytesIO
from typing import Optional

import discord
from PIL import Image, ImageDraw, ImageFont
from discord import Member, File
from discord.app_commands import describe
from discord.ext import commands
from discord.ext.commands import hybrid_command

from utils.bots import CustomContext, BOT_TYPES


def pins_left_executor(pins_left: int) -> BytesIO:
    buffer = BytesIO()
    save_image = Image.open("resources/images/blank.png")
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


def santa_hat_executor(
    pfp: bytes,
    x_offset: int,
    y_offset: int,
    flip: bool,
    size: int,
) -> bytes:
    pfp_image: Image = Image.open(BytesIO(pfp)).convert("RGBA")

    # The scalar is needed to keep everything relative to the size of the pfp
    scalar: float = pfp_image.height / 100

    pfp_size_float: float = 100 * scalar
    pfp_size: int = round(pfp_size_float)
    santa_size: int = round(size * scalar)

    pfp_image = pfp_image.resize(
        (round(pfp_image.height / pfp_image.width * pfp_size_float), pfp_size)
    )
    pfp_image.thumbnail(
        (pfp_size, pfp_size)
    )  # serves to center image if it is wider than it is tall

    x_offset: int = round(x_offset * scalar)
    y_offset: int = round(y_offset * scalar)

    santa_hat_image = Image.open("resources/images/santa.png")
    if flip:
        santa_hat_image = santa_hat_image.transpose(Image.FLIP_LEFT_RIGHT)
    santa_hat_image.thumbnail((santa_size, santa_size))

    pfp_image.paste(santa_hat_image, (x_offset, y_offset), santa_hat_image)

    buffer: BytesIO = BytesIO()
    pfp_image.save(buffer, "PNG")
    buffer.seek(0)
    return buffer.read()


class Images(commands.Cog):
    """Tools to edit images, and make things with them."""

    def __init__(self, bot: BOT_TYPES):
        self.bot: BOT_TYPES = bot

    @hybrid_command(aliases=["santa"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    @describe(
        member="The member of the server to put the Santa Hat on.",
        x_offset="The x offset of the Santa Hat, from 0 to 100, moving from left to right. The default value is 0.",
        y_offset="The y offset of the Santa Hat, from 0 to 100, moving from top to bottom. The default value is -10.",
        flip='Whether to flip the Santa Hat left-right. This is on ("True") by default.',
        size="The size of the Santa Hat. The default value is 70. (70% of the PFP size)",
    )
    async def santa_hat(
        self,
        ctx: CustomContext,
        member: Member | None = None,
        x_offset: int = 0,
        y_offset: int = -10,
        flip: bool = True,
        size: int = 70,
    ) -> None:
        """Put a Santa Hat on a member."""
        member: Member = member or ctx.author
        async with ctx.typing():
            pfp_bytes: bytes = await member.display_avatar.read()
            hat_bytes: bytes = await ctx.bot.loop.run_in_executor(
                None,
                partial(santa_hat_executor, pfp_bytes, x_offset, y_offset, flip, size),
            )
            with BytesIO(hat_bytes) as buffer:
                await ctx.send(file=File(buffer, "santa.png"))

    @hybrid_command(aliases=["pins"])
    @commands.cooldown(1, 40, commands.BucketType.channel)
    @describe(channel="The channel that will have it's pins displayed. ")
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

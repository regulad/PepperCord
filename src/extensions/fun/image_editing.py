import math
from functools import partial
from io import BytesIO
from typing import Optional

import discord
from PIL import Image, ImageDraw, ImageFont
from PIL.Image import Image as ImageType, Transpose
from discord import Member, File, Attachment, User
from discord.app_commands import describe
from discord.ext import commands
from discord.ext.commands import hybrid_command

from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext


DISCORD_MAX_PINS = 250  # up-to-date as of 11/9/25


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
    pfp_image = Image.open(BytesIO(pfp)).convert("RGBA")
    santa_hat_image: ImageType = Image.open("resources/images/santa.png")

    if flip:
        santa_hat_image = santa_hat_image.transpose(Transpose.FLIP_LEFT_RIGHT)

    # The scalar is needed to keep everything relative to the size of the pfp
    pfp_small_dimension = min(pfp_image.size)
    scalar: float = pfp_small_dimension / 100

    # Prepare the pfp
    pfp_image.thumbnail(
        (pfp_small_dimension, pfp_small_dimension)
    )  # takes square out of the middle of the image

    # Get the dimensions of the santa hat
    santa_hat_size = math.floor(size * scalar)
    santa_hat_original_small_dimension = min(santa_hat_image.size)

    # Prepare the santa hat
    santa_hat_image.thumbnail(
        (santa_hat_original_small_dimension, santa_hat_original_small_dimension)
    )  # thumbnail only makes things smaller, lets make it the proper aspect ratio since resize cant
    santa_hat_image = santa_hat_image.resize((santa_hat_size, santa_hat_size))

    # Paste the santa hat onto the pfp
    x_offset = math.floor(x_offset * scalar)
    y_offset = math.floor(y_offset * scalar)
    pfp_image.paste(santa_hat_image, (x_offset, y_offset), santa_hat_image)

    # Save the image
    buffer: BytesIO = BytesIO()
    pfp_image.save(buffer, "PNG")
    buffer.seek(0)
    return buffer.read()


class Images(commands.Cog):
    """Tools to edit images, and make things with them."""

    def __init__(self, bot: CustomBot):
        self.bot = bot

    @hybrid_command(aliases=["santa"])  # type: ignore[arg-type]  # bad types in d.py
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
        member: Member | User | None = None,
        x_offset: int = 0,
        y_offset: int = -10,
        flip: bool = True,
        size: int = 70,
    ) -> None:
        """Put a Santa Hat on a member."""
        async with ctx.typing():
            pfp_bytes: bytes
            if isinstance(member, (Member, User)):
                pfp_bytes = await member.display_avatar.read()
            elif (
                member is None and ctx.message.attachments
            ):  # special case for message commands
                pfp_bytes = await ctx.message.attachments[0].read()
            elif member is None:
                pfp_bytes = await ctx.author.display_avatar.read()

            hat_bytes: bytes = await ctx.bot.loop.run_in_executor(
                None,
                partial(santa_hat_executor, pfp_bytes, x_offset, y_offset, flip, size),
            )
            with BytesIO(hat_bytes) as buffer:
                await ctx.send(file=File(buffer, "santa.png"))

    @hybrid_command(aliases=["santa2"])  # type: ignore[arg-type]  # bad types in d.py
    @commands.cooldown(1, 10, commands.BucketType.user)
    @describe(
        member="The member of the server to put the Santa Hat on.",
        x_offset="The x offset of the Santa Hat, from 0 to 100, moving from left to right. The default value is 0.",
        y_offset="The y offset of the Santa Hat, from 0 to 100, moving from top to bottom. The default value is -10.",
        flip='Whether to flip the Santa Hat left-right. This is on ("True") by default.',
        size="The size of the Santa Hat. The default value is 70. (70% of the PFP size)",
    )
    async def santa_hat_file(
        self,
        ctx: CustomContext,
        member: Attachment | None = None,
        x_offset: int = 0,
        y_offset: int = -10,
        flip: bool = True,
        size: int = 70,
    ) -> None:
        """Put a Santa Hat on a file."""
        async with ctx.typing():
            pfp_bytes: bytes
            if isinstance(member, Attachment):
                pfp_bytes = await member.read()
            elif (
                member is None and ctx.message.attachments
            ):  # special case for message commands
                pfp_bytes = await ctx.message.attachments[0].read()
            elif member is None:
                pfp_bytes = await ctx.author.display_avatar.read()

            hat_bytes: bytes = await ctx.bot.loop.run_in_executor(
                None,
                partial(santa_hat_executor, pfp_bytes, x_offset, y_offset, flip, size),
            )
            with BytesIO(hat_bytes) as buffer:
                await ctx.send(file=File(buffer, "santa.png"))

    @hybrid_command(aliases=["pins"])  # type: ignore[arg-type]  # bad d.py exported type
    @commands.cooldown(1, 40, commands.BucketType.channel)
    @commands.bot_has_guild_permissions(view_channel=True, read_message_history=True)
    @describe(channel="The channel that will have it's pins displayed. ")
    async def pinsleft(
        self,
        ctx: CustomContext,
        *,
        channel: Optional[discord.TextChannel],
    ) -> None:
        """Shows how many pins are left in a channel in a wonderfully flashy way."""
        query_channel = channel or ctx.channel
        async with ctx.typing():
            pins_left = DISCORD_MAX_PINS - len(
                await query_channel.pins(limit=DISCORD_MAX_PINS)
            )
            with await ctx.bot.loop.run_in_executor(
                None, partial(pins_left_executor, pins_left)
            ) as buffer:
                await ctx.send(file=discord.File(buffer, "pinsleft.png"))


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(Images(bot))

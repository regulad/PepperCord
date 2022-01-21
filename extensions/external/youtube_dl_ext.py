from functools import partial
from typing import Optional
from io import BytesIO
from os.path import splitext, split

import discord
from discord.ext import commands
from youtube_dl import YoutubeDL
from discord import File
from aiohttp import ClientSession

from utils.bots import BOT_TYPES, CustomContext
from utils.validators import str_is_url
from utils.audio import YTDL_FORMAT_OPTIONS
from utils.misc import FrozenDict


class FileTooLong(commands.CommandError):
    pass


class MiscHTTPException(discord.HTTPException):
    pass


class BadVideo(commands.CommandError):
    pass


ytdl_format_options_clone: dict = dict(YTDL_FORMAT_OPTIONS)
ytdl_format_options_clone["format"] = "best"
YTDL_FORMAT_OPTIONS_VIDEO = FrozenDict(ytdl_format_options_clone)


class YoutubeDLCog(commands.Cog, name="YoutubeDL"):
    """Tools for utilizing YoutubeDL."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot
        self.ytdl: YoutubeDL = YoutubeDL(YTDL_FORMAT_OPTIONS_VIDEO)

        self.downloader: Optional[ClientSession] = None

    async def secure_session(self) -> None:
        if self.downloader is None:
            self.downloader = ClientSession()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await self.secure_session()

    async def cog_before_invoke(self, ctx: CustomContext) -> None:
        await self.secure_session()

    @commands.command()
    @commands.cooldown(2, 120, commands.BucketType.channel)
    @commands.cooldown(1, 120, commands.BucketType.user)
    @commands.cooldown(3, 120, commands.BucketType.guild)
    @commands.cooldown(5, 360, commands.BucketType.default)
    async def download(
            self,
            ctx: CustomContext,
            *,
            query: str = commands.Option(description="The query for youtubedl")
    ) -> None:
        """Download a video using YoutubeDL."""
        await ctx.defer()

        if str_is_url(query):
            url: str = query
        else:
            url: str = f"ytsearch:{query}"

        info: dict = await ctx.bot.loop.run_in_executor(None, partial(self.ytdl.extract_info, url, download=False))

        if info.get("url") is None:
            if info.get("entries") is not None and len(info["entries"]) > 0:
                info = info["entries"][-1]
            else:
                raise BadVideo("This video cannot be downloaded")

        if (info.get("duration") is not None and info["duration"] > 600) and not await ctx.bot.is_owner(ctx.author):
            raise FileTooLong(
                f"Cannot download this video, it is over 5 minutes in length, "
                f"as it is {info['duration'] / 60} minutes long."
            )

        if info.get("filesize") is not None and info["filesize"] > ctx.guild.filesize_limit:  # Save time.
            await ctx.send(
                "I cannot send a video of this size in this server. Consider boosting it to allow larger files."
            )
        else:
            async with self.downloader.get(info["url"]) as response:
                if response.status != 200:
                    raise MiscHTTPException(response, None)
                else:
                    with BytesIO(await response.read()) as buffer:
                        base_file_name: str = response.url.path.strip().removeprefix("/")
                        split_ext_tuple: tuple[str, str] = splitext(base_file_name)
                        if not split_ext_tuple[-1]:
                            # No extension! We need to do something.
                            real_ext: str = split(response.content_type)[-1]
                            split_ext_tuple = (split_ext_tuple[0], f".{real_ext}")
                        await ctx.send(file=File(buffer, filename=(split_ext_tuple[0] + split_ext_tuple[-1])))


def setup(bot: BOT_TYPES) -> None:
    bot.add_cog(YoutubeDLCog(bot))


__all__: list[str] = [
    "YoutubeDLCog",
    "setup"
]
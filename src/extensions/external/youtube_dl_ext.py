from functools import partial
from io import BytesIO
from os.path import splitext, split
from typing import Optional

import discord
from aiohttp import ClientSession
from discord import File
from discord.app_commands import describe
from discord.ext import commands
from discord.ext.commands import hybrid_command

from utils.attachments import MediaTooLong
from utils.bots import BOT_TYPES, CustomContext
from utils.misc import FrozenDict
from utils.validators import str_is_url

try:
    from yt_dlp import YoutubeDL  # type: ignore
except ImportError:
    from youtube_dl import YoutubeDL  # type: ignore


class MiscHTTPException(discord.HTTPException):
    pass


class BadVideo(commands.CommandError):
    pass


YTDL_FORMAT_OPTIONS: FrozenDict = FrozenDict(
    {
        "format": "best",
        "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
        "restrictfilenames": True,
        "nocheckcertificate": True,
        "ignoreerrors": False,
        "logtostderr": False,
        "prefer_ffmpeg": True,
        "quiet": True,
        "no_warnings": True,
        "default_search": "auto",
        "source_address": "0.0.0.0",  # bind to ipv4 since ipv6 addresses cause issues sometimes
    }
)


class YoutubeDLCog(commands.Cog, name="YoutubeDL"):
    """Tools for utilizing YoutubeDL."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot
        self.downloader: Optional[ClientSession] = None

    async def cog_load(self) -> None:
        self.downloader = ClientSession()

    async def cog_unload(self) -> None:
        if self.downloader is not None and not self.downloader.closed:
            await self.downloader.close()

    @hybrid_command(aliases=["yt", "dl", "ytdl"])
    @commands.cooldown(2, 120, commands.BucketType.channel)
    @commands.cooldown(1, 120, commands.BucketType.user)
    @commands.cooldown(3, 120, commands.BucketType.guild)
    @commands.cooldown(5, 360, commands.BucketType.default)
    @describe(query="The query for youtubedl")
    async def download(
        self,
        ctx: CustomContext,
        *,
        query: str,
    ) -> None:
        """Download a video using YoutubeDL."""

        async with ctx.typing():
            ytdl = YoutubeDL(params=dict(YTDL_FORMAT_OPTIONS))

            url: str
            if str_is_url(query):
                url = query
            else:
                url = f"ytsearch:{query}"

            info: dict = await ctx.bot.loop.run_in_executor(
                None, partial(ytdl.extract_info, url, download=False)
            )

            if info.get("url") is None:
                if info.get("entries") is not None and len(info["entries"]) > 0:
                    info = info["entries"][-1]
                else:
                    raise BadVideo("This video cannot be downloaded")

            if (
                info.get("duration") is not None and info["duration"] > 600
            ) and not await ctx.bot.is_owner(ctx.author):
                raise MediaTooLong(
                    f"Cannot download this video, it is over 5 minutes in length, "
                    f"as it is {info['duration'] / 60} minutes long."
                )

            if (
                info.get("filesize") is not None
                and info["filesize"] > ctx.guild.filesize_limit
            ):  # Save time.
                await ctx.send(
                    "I cannot send a video of this size in this server. Consider boosting it to allow larger files."
                )
            else:
                async with self.downloader.get(info["url"]) as response:
                    if response.status != 200:
                        raise MiscHTTPException(response, None)
                    else:
                        with BytesIO(await response.read()) as buffer:
                            base_file_name: str = (
                                response.url.path.strip().removeprefix("/")
                            )
                            split_ext_tuple: tuple[str, str] = splitext(base_file_name)
                            if not split_ext_tuple[-1]:
                                # No extension! We need to do something.
                                real_ext: str = split(response.content_type)[-1]
                                split_ext_tuple = (split_ext_tuple[0], f".{real_ext}")
                            await ctx.send(
                                file=File(
                                    buffer,
                                    filename=(split_ext_tuple[0] + split_ext_tuple[-1]),
                                )
                            )


async def setup(bot: BOT_TYPES) -> None:
    await bot.add_cog(YoutubeDLCog(bot))


__all__: list[str] = ["YoutubeDLCog", "setup"]

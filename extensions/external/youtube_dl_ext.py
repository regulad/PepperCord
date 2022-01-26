from functools import partial
from io import BytesIO
from os.path import splitext, split
from typing import Optional

import discord
from aiohttp import ClientSession
from discord import File
from discord.ext import commands, tasks
from youtube_dl import YoutubeDL

from utils.attachments import MediaTooLong
from utils.bots import BOT_TYPES, CustomContext
from utils.misc import FrozenDict
from utils.validators import str_is_url


class MiscHTTPException(discord.HTTPException):
    pass


class BadVideo(commands.CommandError):
    pass


YTDL_FORMAT_OPTIONS: FrozenDict = FrozenDict({
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
})


class YoutubeDLCog(commands.Cog, name="YoutubeDL"):
    """Tools for utilizing YoutubeDL."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot
        self.ytdl: Optional[YoutubeDL] = None
        self.assemble_downloader()

        self.reassemble_downloader.start()

        self.downloader: Optional[ClientSession] = None

    def assemble_downloader(self) -> None:
        self.ytdl = YoutubeDL(YTDL_FORMAT_OPTIONS)

    def cog_unload(self) -> None:
        self.reassemble_downloader.cancel()

    @tasks.loop(hours=12)
    async def reassemble_downloader(self) -> None:
        await self.bot.loop.run_in_executor(None, self.assemble_downloader)

    @reassemble_downloader.before_loop
    async def wait(self) -> None:
        await self.bot.wait_until_ready()

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
            raise MediaTooLong(
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

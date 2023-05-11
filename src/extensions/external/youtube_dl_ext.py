import os
from functools import partial
from os import sep

import discord
from aiofiles.tempfile import TemporaryDirectory
from discord import File
from discord.app_commands import describe
from discord.ext import commands
from discord.ext.commands import hybrid_command

from utils.bots import BOT_TYPES, CustomContext
from utils.misc import FrozenDict
from utils.validators import str_is_url

try:
    from yt_dlp import YoutubeDL, DownloadError  # type: ignore
except ImportError:
    from youtube_dl import YoutubeDL, DownloadError  # type: ignore


class MiscHTTPException(discord.HTTPException):
    pass


class BadVideo(commands.CommandError):
    pass


BEST_VIDEO = (
    "best[ext=mp4][filesize<={filesize}]"
    "/best[ext=webm][filesize<={filesize}]"
    "/worst[ext=mp4]"
    "/worst[ext=webm]"
)
BEST_AUDIO = (
    "bestaudio[ext=m4a][filesize<={filesize}]"
    "/bestaudio[ext=ogg][filesize<={filesize}]"
    "/bestaudio[ext=wav][filesize<={filesize}]"
    "/bestaudio[ext=flac][filesize<={filesize}]"
    "/worstaudio[ext=m4a]"
    "/worstaudio[ext=ogg]"
    "/worstaudio[ext=wav]"
    "/worstaudio[ext=flac]"
)

YTDL_FORMAT_INITIAL_OPTIONS: FrozenDict = FrozenDict(
    {
        "format": BEST_VIDEO,  # favor MP4s
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
        "outtmpl_na_placeholder": "mp4",  # default to mp4 if we have no idea what something is
    }
)


class YoutubeDLCog(commands.Cog, name="YoutubeDL"):
    """Tools for utilizing YoutubeDL."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot

    @hybrid_command(aliases=["yt", "dl", "ytdl"])
    @commands.cooldown(4, 120, commands.BucketType.channel)
    @commands.cooldown(10, 120, commands.BucketType.guild)
    @describe(
        query="The query for youtubedl",
        audio_only="Download only the audio of the video. Useful for soundboards.",
    )
    async def download(
        self,
        ctx: CustomContext,
        audio_only: bool = False,
        *,
        query: str,
    ) -> None:
        """Download a video using YoutubeDL."""

        async with ctx.typing():
            ytdl_params = dict(YTDL_FORMAT_INITIAL_OPTIONS)

            filesize_bytes = ctx.guild.filesize_limit
            filesize_mi_b = round(filesize_bytes / 1.049e6)  # Mebibytes, not megabytes!

            if audio_only:
                ytdl_params["format"] = BEST_AUDIO
            else:
                ytdl_params["format"] = BEST_VIDEO
            # else, just let ytdl figure it out

            if "format" in ytdl_params:
                ytdl_params["format"] = ytdl_params["format"].format(
                    filesize=f"{filesize_mi_b}M"
                )

            async with TemporaryDirectory() as tempdir:  # type: str
                ytdl_params["outtmpl"] = tempdir + sep + ytdl_params["outtmpl"]

                ytdl = YoutubeDL(params=ytdl_params)

                url: str
                if str_is_url(query):
                    url = query
                else:
                    url = f"ytsearch:{query}"

                try:
                    info_dict: dict = await ctx.bot.loop.run_in_executor(
                        None, partial(ytdl.extract_info, url)
                    )
                except DownloadError as e:
                    if "Requested format" in e.msg:
                        e.msg += (
                            "\n\n"
                            "NOTE: This can also occur if PepperCord couldn't find a file small enough to send in "
                            "your server with respect to the maximum file size. Boosting your server could mitigate"
                            "this error in the future."
                        )

                    raise

                # No check for an oversize file should be required, since YTDL won't fetch one.

                files = list(os.listdir())

                if len(files) == 0:
                    await ctx.send(
                        "Sorry, but I couldn't find anything for that! Please try with another link."
                    )

                discord_files: list[File] = []

                for file in os.listdir(tempdir):
                    discord_files.append(File(fp=tempdir + sep + file))

                try:
                    await ctx.send(files=discord_files)
                finally:
                    for file in discord_files:
                        file.close()  # need to do this because they own the fp


async def setup(bot: BOT_TYPES) -> None:
    await bot.add_cog(YoutubeDLCog(bot))


__all__: list[str] = ["YoutubeDLCog", "setup"]

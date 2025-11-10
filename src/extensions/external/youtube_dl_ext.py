import os
from functools import partial
from os import sep
from typing import cast

from aiofiles.tempfile import TemporaryDirectory
from discord import File, Guild, HTTPException
from discord.app_commands import describe
from discord.ext.commands import (
    hybrid_command,
    guild_only,
    Cog,
    CommandError,
    cooldown,
    BucketType,
)

from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext
from utils.misc import FrozenDict
from utils.sources.common import YTDLOptionsType
from utils.sources.ytdl import YTDLInfo
from utils.validators import str_is_url

from yt_dlp import YoutubeDL


class MiscHTTPException(HTTPException):
    pass


class BadVideo(CommandError):
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

YTDL_FORMAT_INITIAL_OPTIONS: YTDLOptionsType = FrozenDict(
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


class YoutubeDLCog(Cog, name="YoutubeDL"):
    """Tools for utilizing YoutubeDL."""

    def __init__(self, bot: CustomBot) -> None:
        self.bot = bot

    @hybrid_command(aliases=["yt", "dl", "ytdl"])  # type: ignore[arg-type]  # broken fsr
    @cooldown(4, 120, BucketType.channel)
    @cooldown(10, 120, BucketType.guild)
    @guild_only()
    @describe(
        query="The query for youtubedl",
        audio_only="Download only the audio of the video. Useful for soundboards.",
    )
    async def download(
        self,
        ctx: CustomContext,
        query: str,
        audio_only: bool = False,
    ) -> None:
        """Download a video using YoutubeDL."""

        async with ctx.typing():
            ytdl_params = dict(YTDL_FORMAT_INITIAL_OPTIONS)

            filesize_max_bytes = cast(
                Guild, ctx.guild
            ).filesize_limit  # guaranteed at runtime
            filesize_max_mi_b = round(
                filesize_max_bytes / 1.049e6
            )  # Mebibytes, not megabytes!

            if audio_only:
                ytdl_params["format"] = BEST_AUDIO
            else:
                ytdl_params["format"] = BEST_VIDEO
            # else, just let ytdl figure it out

            ytdl_params["format"] = ytdl_params["format"].format(  # type: ignore[union-attr]  # type is proven no less than 5 lines above
                filesize=f"{filesize_max_mi_b}M"
            )

            async with TemporaryDirectory() as tempdir:  # type: str
                ytdl_params["outtmpl"] = (
                    tempdir + sep + cast(str, ytdl_params["outtmpl"])
                )

                ytdl = YoutubeDL(params=ytdl_params)

                url: str
                if str_is_url(query):
                    url = query
                else:
                    url = f"ytsearch:{query}"

                try:
                    info_dict: YTDLInfo = await ctx.bot.loop.run_in_executor(
                        None, partial(ytdl.extract_info, url)
                    )
                except Exception as e:
                    if (
                        hasattr(e, "msg")
                        and isinstance(e.msg, str)
                        and "Requested format" in e.msg
                    ):
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
                    for dfile in discord_files:
                        dfile.close()  # need to do this because they own the fp


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(YoutubeDLCog(bot))


__all__: list[str] = ["YoutubeDLCog", "setup"]

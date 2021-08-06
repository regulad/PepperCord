from io import BytesIO
import asyncio
from typing import Optional

import discord
from aiohttp import ClientSession, hdrs
from discord.ext import commands
from youtube_dl import YoutubeDL

from utils.attachments import MediaTooLarge, MediaTooLong
from utils.validators import str_is_url

MAX_TIME = 600  # 10 Minutes

ytdl_format_options = {
    "format": "worst",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",  # bind to ipv4 since ipv6 addresses cause issues sometimes
}


class YoutubeDLCog(commands.Cog, name="YoutubeDL"):
    """Download videos from almost anywhere on the internet with YoutubeDL."""

    def __init__(self, bot):
        self.bot = bot

        self.client_session = ClientSession()
        self.file_downloader = YoutubeDL(ytdl_format_options)

    @commands.command(
        name="download",
        aliases=["ytdl"],
        brief="Download a video.",
        description="Download a video from YoutubeDL.",
        usage="<Query>",
    )
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def download(self, ctx, query: str):
        async with ctx.typing():
            if not str_is_url(query):
                query: str = f"ytsearch:{query}"

            info: dict = await ctx.bot.loop.run_in_executor(
                None, lambda: self.file_downloader.extract_info(query, download=False)
            )

            if "entries" in info:
                info: dict = info["entries"][0]

            if info["duration"] > MAX_TIME:
                raise MediaTooLong(f"Maximum is {MAX_TIME}, actual duration was {info['duration']}.")

            buffer: BytesIO = BytesIO()

            async with self.client_session.get(info['url']) as response:
                if int(response.headers[hdrs.CONTENT_LENGTH]) > 8000000:
                    raise MediaTooLarge(
                        f"{round((int(response.headers[hdrs.CONTENT_LENGTH]) - 8000000) / 8000000, 2)}MB over"
                    )
                else:
                    while True:
                        chunk = await response.content.read(800000)

                        if not chunk:
                            break
                        else:
                            buffer.write(chunk)
                        await asyncio.sleep(0.5)

            buffer.seek(0)
            file: discord.File = discord.File(buffer, f"download.{info['ext']}")
            await ctx.send(ctx.author.mention, files=[file])


def setup(bot):
    bot.add_cog(YoutubeDLCog(bot))

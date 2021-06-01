import asyncio
from typing import Union

import discord
from youtube_dl import YoutubeDL


ytdl_format_options = {
    "format": "bestaudio/best",
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

ffmpeg_options = {"options": "-vn"}


class YTDLSource(discord.PCMVolumeTransformer):
    """Represents a source from YoutubeDL that has the ability to have it's volume changed."""

    def __init__(self, source: discord.FFmpegPCMAudio, volume=0.5, *, info, invoker, file_downloader):
        super().__init__(source, volume)

        self.file_downloader = file_downloader
        self.info = info
        self.invoker = invoker

    @property
    def url(self):
        return self.info["webpage_url"]

    @classmethod
    async def from_url(cls, file_downloader: YoutubeDL, url: str, invoker: Union[discord.Member, discord.User]):
        """Returns a list of YTDLSources from a playlist or song."""

        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, lambda: file_downloader.extract_info(url, download=False))

        tracks = []

        if info.setdefault("entries", None):
            # Url refers to a playlist, so a list of instances must be returned.

            for entry in info["entries"]:
                track = cls(
                    discord.FFmpegPCMAudio(entry["url"], **ffmpeg_options), info=entry,
                    invoker=invoker, file_downloader=file_downloader
                )
                tracks.append(track)

        else:
            # Url refers to a single track, so a list containing only a single instance must be returned.

            track = cls(
                discord.FFmpegPCMAudio(info["url"], **ffmpeg_options), info=info,
                invoker=invoker, file_downloader=file_downloader
            )
            tracks.append(track)

        return tracks

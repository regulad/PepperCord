import asyncio
from typing import Union

import discord
from youtube_dl import YoutubeDL

from utils.audio import ffmpeg_options
from .common import QueueSource


class YTDLSource(QueueSource):
    """Represents a source from YoutubeDL that has the ability to have it's volume changed."""

    def __init__(self, source: discord.FFmpegPCMAudio, volume=0.5, *, info, file_downloader, invoker):
        self.file_downloader = file_downloader
        self.info = info

        super().__init__(source, volume, invoker=invoker)

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


__all__ = ["YTDLSource"]

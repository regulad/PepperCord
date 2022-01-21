import asyncio
import datetime
from typing import Union

import discord
from youtube_dl import YoutubeDL

from utils.audio import FFMPEG_OPTIONS
from .common import QueueSource


class YTDLSource(QueueSource):
    """Represents a source from YoutubeDL that has the ability to have it's volume changed."""

    def __init__(
            self,
            source: discord.FFmpegPCMAudio,
            volume=0.5,
            *,
            info: dict,
            file_downloader: YoutubeDL,
            invoker: Union[discord.Member, discord.User],
    ):
        self.file_downloader: YoutubeDL = file_downloader
        self.info: dict = info
        self._created: datetime.datetime = datetime.datetime.now()

        super().__init__(source, volume, invoker=invoker)

    @property
    def created(self) -> datetime.datetime:
        return self._created

    @property
    def url(self):
        return self.info["webpage_url"]

    async def refresh(self):
        """Regrabs audio from site. Useful if video is time limited."""

        return await self.from_url_single(self.file_downloader, self.url, self.invoker)

    @classmethod
    async def from_url_single(
            cls,
            file_downloader: YoutubeDL,
            url: str,
            invoker: Union[discord.Member, discord.User],
            *,
            loop: asyncio.AbstractEventLoop = asyncio.get_event_loop(),
    ):
        info: dict = await loop.run_in_executor(
            None, lambda: file_downloader.extract_info(url, download=False)
        )

        if info.get("entries") is not None:
            raise RuntimeError("Multiple tracks")
        else:
            return cls(
                discord.FFmpegPCMAudio(info["url"], **FFMPEG_OPTIONS),
                info=info,
                invoker=invoker,
                file_downloader=file_downloader,
            )

    @classmethod
    async def from_url(
            cls,
            file_downloader: YoutubeDL,
            url: str,
            invoker: Union[discord.Member, discord.User],
            *,
            loop: asyncio.AbstractEventLoop = asyncio.get_event_loop(),
    ):
        """Returns a list of YTDLSources from a playlist or song."""

        info: dict = await loop.run_in_executor(
            None, lambda: file_downloader.extract_info(url, download=False)
        )

        tracks = []

        if info.get("entries") is not None:
            # Url refers to a playlist, so a list of instances must be returned.

            for entry in info["entries"]:
                track = cls(
                    discord.FFmpegPCMAudio(entry["url"], **FFMPEG_OPTIONS),
                    info=entry,
                    invoker=invoker,
                    file_downloader=file_downloader,
                )
                tracks.append(track)
        else:
            # Url refers to a single track, so a list containing only a single instance must be returned.

            track = cls(
                discord.FFmpegPCMAudio(info["url"], **FFMPEG_OPTIONS),
                info=info,
                invoker=invoker,
                file_downloader=file_downloader,
            )
            tracks.append(track)
        return tracks


__all__ = ["YTDLSource"]

from asyncio import AbstractEventLoop
from datetime import datetime, timedelta
from typing import Optional

from discord import abc, FFmpegPCMAudio

try:
    from yt_dlp import YoutubeDL  # type: ignore
except ImportError:
    from youtube_dl import YoutubeDL  # type: ignore

from utils.bots import CustomVoiceClient
from .common import *


class YTDLSource(EnhancedSourceWrapper):
    """Represents a source from YoutubeDL that has the ability to have it's volume changed."""

    def __init__(
        self,
        source: FFmpegPCMAudio,
        volume=0.5,
        *,
        info: dict,
        file_downloader: YoutubeDL,
        invoker: abc.User,
    ):
        self.file_downloader: YoutubeDL = file_downloader
        self.info: dict = info
        self._created: datetime = datetime.now()

        super().__init__(source, volume, invoker=invoker)

    @property
    def duration(self) -> Optional[int]:
        return (
            (self.info["duration"] * 1000)
            if self.info.get("duration") is not None
            else None
        )

    @property
    def name(self) -> str:
        return self.info["title"]

    @property
    def description(self) -> str:
        return self.info["webpage_url"]

    async def refresh(self, voice_client: CustomVoiceClient) -> "YTDLSource":
        """Regrabs audio from site. Useful if video is time limited."""

        if (self._created + timedelta(minutes=1)) > datetime.now():
            return await self.from_url_single(
                self.file_downloader,
                self.info["webpage_url"],
                self.invoker,
                loop=voice_client.loop,
            )

    @classmethod
    async def from_url_single(
        cls,
        file_downloader: YoutubeDL,
        url: str,
        invoker: abc.User,
        cached_info: Optional[dict] = None,
        *,
        loop: AbstractEventLoop,
    ) -> "YTDLSource":
        info: dict = cached_info or await loop.run_in_executor(
            None, lambda: file_downloader.extract_info(url, download=False)
        )

        if info.get("entries") is not None:
            raise RuntimeError("Multiple tracks")
        else:
            return cls(
                FFmpegPCMAudio(info["url"], **FFMPEG_OPTIONS),
                info=info,
                invoker=invoker,
                file_downloader=file_downloader,
            )

    @classmethod
    async def from_url(
        cls,
        file_downloader: YoutubeDL,
        url: str,
        invoker: abc.User,
        *,
        loop: AbstractEventLoop,
    ) -> list["YTDLSource"]:
        """Returns a list of YTDLSources from a playlist or song."""

        info: dict = await loop.run_in_executor(
            None, lambda: file_downloader.extract_info(url, download=False)
        )

        if info.get("entries") is not None:
            # Url refers to a playlist, so a list of instances must be returned.
            tracks = []
            for entry in info["entries"]:
                tracks.append(
                    await cls.from_url_single(
                        file_downloader, entry["webpage_url"], invoker, entry, loop=loop
                    )
                )
            return tracks
        else:
            # Url refers to a single track, so a list containing only a single instance must be returned.
            return [
                await cls.from_url_single(
                    file_downloader, info["webpage_url"], invoker, info, loop=loop
                )
            ]


__all__: list[str] = ["YTDLSource"]

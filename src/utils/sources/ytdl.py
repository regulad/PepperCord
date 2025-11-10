from asyncio import AbstractEventLoop
from datetime import datetime, timedelta
from typing import NotRequired, Optional, Self, TypedDict, cast

from discord import abc, FFmpegPCMAudio

from yt_dlp import YoutubeDL
from utils.bots.audio import CustomVoiceClient
from utils.sources.common import *


class YTDLInfo(TypedDict):
    """
    Represents the return type from YoutubeDL.extract_info
    """

    title: str
    url: str  # URL that can be opened by ffmpeg
    webpage_url: str
    entries: NotRequired[list[YTDLInfo]]
    duration: NotRequired[int]


class YTDLSource(EnhancedPCMVolumeTransformer[FFmpegPCMAudio]):
    """Represents a source from YoutubeDL that has the ability to have it's volume changed."""

    def __init__(
        self,
        source: FFmpegPCMAudio,
        volume: float = 0.5,
        *,
        info: YTDLInfo,
        file_downloader: YoutubeDL,
        invoker: abc.User,
    ) -> None:
        self.file_downloader = file_downloader
        self.info = info
        self._created = datetime.now()

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

    async def refresh(self, voice_client: CustomVoiceClient) -> Self:
        """Regrabs audio from site. Useful if video is time limited."""

        if (self._created + timedelta(minutes=1)) > datetime.now():
            return await self.from_url_single(
                self.file_downloader,
                self.info["webpage_url"],
                self.invoker,
                cached_info=None,  # force a refetch
                loop=voice_client.loop,
            )
        else:
            return self

    @classmethod
    async def from_url_single(
        cls,
        file_downloader: YoutubeDL,
        url: str,
        invoker: abc.User,
        cached_info: Optional[YTDLInfo] = None,
        *,
        loop: AbstractEventLoop,
    ) -> Self:
        info = cached_info or (
            cast(
                YTDLInfo,  # cast here is because mypy doesn't get the run_in_executor type
                await loop.run_in_executor(
                    None, lambda: file_downloader.extract_info(url, download=False)
                ),
            )
        )

        if info.get("entries") is not None:
            raise RuntimeError("Multiple tracks")
        else:
            return cls(
                FFmpegPCMAudio(
                    info["url"], options="-vn"
                ),  # -vn: "Video No" -> disables video stream
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

        info = cast(
            YTDLInfo,  # cast here is because mypy doesn't get the run_in_executor type
            await loop.run_in_executor(
                None, lambda: file_downloader.extract_info(url, download=False)
            ),
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

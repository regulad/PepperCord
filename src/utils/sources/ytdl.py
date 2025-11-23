from abc import ABC
from asyncio import AbstractEventLoop, get_running_loop
from datetime import datetime, timedelta
from os import sep
import os
from tarfile import data_filter
from tempfile import TemporaryDirectory, tempdir
from typing import (
    Annotated,
    Awaitable,
    Callable,
    NotRequired,
    Optional,
    Self,
    TypedDict,
    cast,
)

from discord import abc, FFmpegPCMAudio

from yt_dlp import YoutubeDL
from utils.audio import CustomVoiceClient
from utils.sources.common import *


type FileDownloaderFactory = Callable[[str | None], YoutubeDL]
# must be passed to check to see if an info can be downloaded. might be rejected because too long
type InfoCheckType = Callable[[YTDLInfo], Awaitable[bool]]


# After this amount of time, the stream is marked "stale" and no longer available for streaming. The refresh method of the stream must be called before it can be played.
STREAM_SOURCE_EXPIRATION_TIMEDELTA = timedelta(minutes=1)


def default_file_downloader_factory(tempdir: str | None) -> YoutubeDL:
    ytdl_params = dict(YTDL_AUDIO_FORMAT_INITIAL_OPTIONS)
    if tempdir is not None:
        ytdl_params["outtmpl"] = tempdir + sep + cast(str, ytdl_params["outtmpl"])
    return YoutubeDL(params=ytdl_params)


async def default_info_checker(ytdlinfo: YTDLInfo) -> bool:
    return True


class YTDLInfo(TypedDict):
    """
    Represents the return type from YoutubeDL.extract_info
    """

    title: str
    url: str  # URL that can be opened by ffmpeg
    webpage_url: str
    entries: NotRequired[list[YTDLInfo]]
    duration: NotRequired[int]


class YTDLSource(EnhancedPCMVolumeTransformer[FFmpegPCMAudio], ABC):
    """
    Represents a streamed source from YoutubeDL that has the ability to have it's volume changed.
    """

    def __init__(
        self,
        source: FFmpegPCMAudio,
        volume: float = 0.5,
        *,
        info: YTDLInfo,
        invoker: abc.User,
    ) -> None:
        self.info = info
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

    @staticmethod
    async def _do_load(
        url: str,
        invoker: abc.User,
        *,
        stream: bool = False,
        file_downloader: YoutubeDL | None = None,
        cached_info: YTDLInfo | None = None,
        loop: AbstractEventLoop = get_running_loop(),
        factory: FileDownloaderFactory = default_file_downloader_factory,
        preload_checker: InfoCheckType = default_info_checker,
    ) -> "YTDLSource":
        predownloader = file_downloader or factory(None)
        preinfo = cached_info or (
            cast(
                YTDLInfo,  # cast here is because mypy doesn't get the run_in_executor type
                await loop.run_in_executor(
                    None, (lambda: predownloader.extract_info(url, download=False))
                ),
            )
        )

        # If the preinfo check fails, we will just stream.
        if stream or not await preload_checker(preinfo):
            # No need to do further processing
            return _YTDLStreamSource(
                FFmpegPCMAudio(
                    preinfo["url"], options="-vn"
                ),  # -vn: "Video No" -> disables video stream
                info=preinfo,
                invoker=invoker,
                file_downloader=predownloader,
            )

        # now we actually do the downloading
        tempdir = TemporaryDirectory()
        final_downloader = factory(tempdir.name)
        final_info = cast(
            YTDLInfo,  # cast here is because mypy doesn't get the run_in_executor type
            await loop.run_in_executor(
                None, lambda: final_downloader.extract_info(url)
            ),
        )

        # now, we need to find all of the files in tempdir and see if there is only one
        downloaded_files = os.listdir(tempdir.name)

        if len(downloaded_files) != 1:
            tempdir.cleanup()
            raise RuntimeError("A weird amount of files was downloaded!")

        filepath = os.path.join(tempdir.name, downloaded_files[0])

        if not os.path.isfile(filepath):
            tempdir.cleanup()
            raise RuntimeError("A non-file was downloaded!")

        return _YTDLPreloadSource(
            FFmpegPCMAudio(
                filepath, options="-vn"
            ),  # -vn: "Video No" -> disables video stream
            info=final_info,
            invoker=invoker,
            tempdir=tempdir,
        )

    @classmethod
    async def from_url(
        cls,
        url: str,
        invoker: abc.User,
        *,
        file_downloader: YoutubeDL | None = None,
        loop: AbstractEventLoop = get_running_loop(),
        factory: FileDownloaderFactory = default_file_downloader_factory,
        preload_checker: InfoCheckType = default_info_checker,
    ) -> list["YTDLSource"]:
        """Returns a list of YTDLSources from a playlist or song."""
        predownloader = file_downloader or factory(None)
        preinfo = cast(
            YTDLInfo,  # cast here is because mypy doesn't get the run_in_executor type
            await loop.run_in_executor(
                None, (lambda: predownloader.extract_info(url, download=False))
            ),
        )

        if preinfo.get("entries") is not None:
            # Url refers to a playlist, so a list of instances must be returned.
            tracks = []
            for entry in preinfo["entries"]:
                tracks.append(
                    await cls._do_load(
                        entry["webpage_url"],
                        invoker,
                        file_downloader=file_downloader,
                        cached_info=entry,
                        loop=loop,
                        preload_checker=preload_checker,
                    )
                )
            return tracks
        else:
            # Url refers to a single track, so a list containing only a single instance must be returned.
            return [
                await cls._do_load(
                    preinfo["webpage_url"],
                    invoker,
                    file_downloader=file_downloader,
                    cached_info=preinfo,
                    loop=loop,
                    preload_checker=preload_checker,
                )
            ]


class _YTDLStreamSource(YTDLSource):
    def __init__(
        self,
        source: FFmpegPCMAudio,
        volume: float = 0.5,
        *,
        file_downloader: YoutubeDL,
        info: YTDLInfo,
        invoker: abc.User,
    ) -> None:
        self.info = info
        self._created = datetime.now()
        self._file_downloader = file_downloader
        super().__init__(source, volume, invoker=invoker, info=info)

    async def refresh(self, voice_client: CustomVoiceClient) -> Self:
        """Regrabs audio from site. Useful if video is time limited."""

        if (self._created + STREAM_SOURCE_EXPIRATION_TIMEDELTA) > datetime.now():
            return cast(
                Self,
                await YTDLSource._do_load(
                    self.info["webpage_url"],
                    self.invoker,
                    file_downloader=self._file_downloader,
                    stream=True,
                    cached_info=None,  # force a refetch
                    loop=voice_client.loop,
                ),
            )
        else:
            return self


class _YTDLPreloadSource(YTDLSource):
    def __init__(
        self,
        source: FFmpegPCMAudio,
        volume: float = 0.5,
        *,
        tempdir: TemporaryDirectory[str],
        info: YTDLInfo,
        invoker: abc.User,
    ) -> None:
        self.info = info
        self._tempdir = tempdir
        super().__init__(source, volume, invoker=invoker, info=info)

    def cleanup(self) -> None:
        self._tempdir.cleanup()
        return super().cleanup()


__all__ = ("YTDLSource", "FileDownloaderFactory", "InfoCheckType")

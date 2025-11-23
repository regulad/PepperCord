from typing import TypeVar
from discord import AudioSource, abc, PCMVolumeTransformer

from utils.audio import EnhancedSource
from utils.misc import FrozenDict

YTDLOptionsType = FrozenDict[str, str | bool]

YTDL_AUDIO_FORMAT_INITIAL_OPTIONS: YTDLOptionsType = FrozenDict(
    {
        "format": "bestaudio/best",
        "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
        "restrictfilenames": True,
        "ignoreerrors": False,
        "logtostderr": False,
        "prefer_ffmpeg": True,
        "quiet": True,
        "no_warnings": True,
        "default_search": "auto",
        "source_address": "0.0.0.0",
        # bind to ipv4 since ipv6 addresses cause issues sometimes
        # TODO: Why do we need to bind to ipv4 listener only?
        "outtmpl_na_placeholder": "m4a",  # default to m4a if we have no idea what something is
    }
)


S = TypeVar("S", bound="AudioSource")


class EnhancedPCMVolumeTransformer(PCMVolumeTransformer[S], EnhancedSource):
    def __init__(self, source: S, volume: float = 0.5, *, invoker: abc.User) -> None:
        self._invoker: abc.User = invoker

        super().__init__(source, volume)

    @property
    def invoker(self) -> abc.User:
        return self._invoker


__all__: list[str] = [
    "YTDL_AUDIO_FORMAT_INITIAL_OPTIONS",
    "YTDLOptionsType",
    "EnhancedPCMVolumeTransformer",
]

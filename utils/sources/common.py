from discord import abc, PCMVolumeTransformer, AudioSource

from utils.bots import EnhancedSource
from utils.misc import FrozenDict

YTDL_FORMAT_OPTIONS: FrozenDict = FrozenDict({
    "format": "bestaudio/best",
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
})

FFMPEG_OPTIONS: FrozenDict = FrozenDict({"options": "-vn"})


class EnhancedSourceWrapper(PCMVolumeTransformer, EnhancedSource):
    def __init__(
            self,
            source: AudioSource,
            volume=0.5,
            *,
            invoker: abc.User
    ) -> None:
        self._invoker: abc.User = invoker

        super().__init__(source, volume)

    @property
    def invoker(self) -> abc.User:
        return self._invoker


__all__: list[str] = [
    "YTDL_FORMAT_OPTIONS",
    "FFMPEG_OPTIONS",
    "EnhancedSourceWrapper",
]

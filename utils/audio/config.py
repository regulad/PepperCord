from utils.misc import FrozenDict

YTDL_FORMAT_OPTIONS: FrozenDict = FrozenDict({
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
})

FFMPEG_OPTIONS: FrozenDict = FrozenDict({"options": "-vn"})

__all__: list[str] = [
    "YTDL_FORMAT_OPTIONS",
    "FFMPEG_OPTIONS"
]

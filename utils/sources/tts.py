from io import BytesIO
from typing import Union
from easygTTS import AsyncEasyGTTSSession

import discord

from ._fixes import FFmpegPCMAudio


class TTSSource(discord.PCMVolumeTransformer):
    def __init__(
        self, source: FFmpegPCMAudio, volume=0.7, *, text: str, invoker: Union[discord.Member, discord.User]
    ):
        super().__init__(source, volume)

        self.text = text
        self.invoker = invoker

    @classmethod
    async def from_text(
        cls, text: str, tts_session: AsyncEasyGTTSSession, invoker: Union[discord.Member, discord.User]
    ):
        audio_bytes = await tts_session.synthesize(text)
        with BytesIO(audio_bytes) as buffer:
            buffer.seek(0)
            source = FFmpegPCMAudio(buffer.read(), pipe=True)
            return cls(source, text=text, invoker=invoker)


__all__ = ["TTSSource"]

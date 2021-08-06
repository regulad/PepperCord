from io import BytesIO
from typing import Union
from asyncgTTS import (
    AsyncGTTSSession,
    TextSynthesizeRequestBody,
    SynthesisInput,
    VoiceSelectionParams,
)

import discord

from ._fixes import FFmpegPCMAudio


class TTSSource(discord.PCMVolumeTransformer):
    def __init__(
        self,
        source: FFmpegPCMAudio,
        volume=0.7,
        *,
        text: str,
        invoker: Union[discord.Member, discord.User]
    ):
        super().__init__(source, volume)

        self.text = text
        self.invoker = invoker

    @classmethod
    async def from_text(
        cls,
        text: str,
        voice: str,
        tts_session: AsyncGTTSSession,
        invoker: Union[discord.Member, discord.User],
    ):
        synthesis_input: SynthesisInput = SynthesisInput(text)
        voice_selection_params: VoiceSelectionParams = VoiceSelectionParams(
            "en-US", voice
        )
        text_synthesize_request_body: TextSynthesizeRequestBody = (
            TextSynthesizeRequestBody(
                synthesis_input, voice_input=voice_selection_params
            )
        )
        audio_bytes = await tts_session.synthesize(text_synthesize_request_body)
        with BytesIO(audio_bytes) as buffer:
            buffer.seek(0)
            source = FFmpegPCMAudio(buffer.read(), pipe=True)
            return cls(source, text=text, invoker=invoker)


__all__ = ["TTSSource"]

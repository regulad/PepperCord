from typing import Union

import discord


class QueueSource(discord.PCMVolumeTransformer):
    """Represents a source on the AudioQueue that was invoked by a certain user."""

    def __init__(
            self,
            source: discord.FFmpegPCMAudio,
            volume=0.5,
            *,
            invoker: Union[discord.Member, discord.User]
    ) -> None:
        self.invoker = invoker

        super().__init__(source, volume)


__all__ = ["QueueSource"]

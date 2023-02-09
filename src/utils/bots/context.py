import abc
from typing import Dict, Any, Optional, cast, TYPE_CHECKING, Coroutine

import discord
from discord import Interaction, Message, NotFound
from discord.ext import commands

from .audio import *

if TYPE_CHECKING:
    from .bot import BOT_TYPES


class SendHandler(abc.ABC):
    async def send(self, *args, **kwargs) -> discord.Message:
        raise NotImplementedError


class _DefaultSendHandler(SendHandler):
    def __init__(self, ctx: "CustomContext"):
        self.ctx: "CustomContext" = ctx

    async def send(self, *args, **kwargs) -> discord.Message:
        message: discord.Message
        if self.ctx.interaction is None:
            if kwargs.get("ephemeral") is not None:
                del kwargs["ephemeral"]
            if kwargs.get("reference") is None:
                kwargs["reference"] = self.ctx.message
            message = await self.ctx.send_bare(*args, **kwargs)
        else:
            try:
                message = await self.ctx.send_bare(*args, **kwargs)
            except NotFound:
                try:
                    message = await self.ctx.interaction.followup.send(*args, **kwargs)
                except NotFound:
                    if kwargs.get("ephemeral") is not None:
                        del kwargs["ephemeral"]
                    message = await self.ctx.channel.send(*args, **kwargs)  # Worst case
        self.ctx["response"] = message  # this is both neat and kinda broken
        return message


class CustomContext(commands.Context):
    bot: "BOT_TYPES"

    def __init__(self, **attrs):
        self._custom_state: Dict[Any, Any] = {}
        self.send_handler: SendHandler = _DefaultSendHandler(self)
        super().__init__(**attrs)

    @classmethod
    async def from_interaction(cls, interaction: Interaction, /) -> "CustomContext":
        """Creates a Context from an interaction with the CustomBotBase hooks intact."""
        ctx: "CustomContext" = await super().from_interaction(interaction)
        if hasattr(ctx.bot, "wait_for_dispatch"):
            await ctx.bot.wait_for_dispatch("context_creation", ctx)
        return ctx

    def __getitem__(self, item: Any) -> Any:
        return self._custom_state[item]

    def __setitem__(self, key: Any, value: Any) -> None:
        self._custom_state[key] = value

    def __delitem__(self, key: Any) -> None:
        del self._custom_state[key]

    @property
    def voice_client(self) -> Optional[CustomVoiceClient]:
        return cast(CustomVoiceClient, super().voice_client)  # Maybe dangerous.

    async def get_or_create_voice_client(self, **kwargs) -> CustomVoiceClient:
        """
        Shortcut to creating a custom voice client for the author's channel.
        If a client is already present, return that.
        """

        return (
            self.voice_client
            if self.voice_client is not None
            else (await CustomVoiceClient.create(self.author.voice.channel, **kwargs))
        )

    def send(self, *args, **kwargs) -> Coroutine[Any, Any, Message]:
        return self.send_handler.send(*args, **kwargs)

    def send_bare(self, *args, **kwargs) -> Coroutine[Any, Any, Message]:
        return super().send(*args, **kwargs)


__all__: list[str] = [
    "CustomContext",
    "SendHandler",
]

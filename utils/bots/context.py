import abc
from typing import Dict, Any

import discord
from discord.ext import commands


class SendHandler(abc.ABC):
    async def send(self, *args, **kwargs) -> discord.Message:
        raise NotImplementedError


class _DefaultSendHandler(SendHandler):
    def __init__(self, ctx: "CustomContext"):
        self.ctx: "CustomContext" = ctx

    async def send(self, *args, **kwargs) -> discord.Message:
        if self.ctx.interaction is None:
            if kwargs.get("ephemeral") is not None:
                del kwargs["ephemeral"]
            if kwargs.get("return_message") is not None:
                del kwargs["return_message"]
            if kwargs.get("reference") is None:
                kwargs["reference"] = self.ctx.message
            return await super(CustomContext, self.ctx).send(*args, **kwargs)
        try:
            return await super(CustomContext, self.ctx).send(*args, **kwargs)
        except discord.NotFound:
            if self.ctx.interaction is not None:
                return await self.ctx.interaction.followup.send(*args, **kwargs)
            else:
                raise
        except Exception:
            raise


class CustomContext(commands.Context):
    def __init__(self, **attrs):
        self._custom_state: Dict[Any, Any] = {}
        self.send_handler: SendHandler = _DefaultSendHandler(self)
        super().__init__(**attrs)

    def __getitem__(self, item: Any) -> Any:
        return self._custom_state[item]

    def __setitem__(self, key: Any, value: Any) -> None:
        self._custom_state[key] = value

    def __delitem__(self, key: Any) -> None:
        del self._custom_state[key]

    async def defer(self, *, ephemeral: bool = False, trigger_typing: bool = True) -> None:
        try:
            return await super().defer(ephemeral=ephemeral, trigger_typing=trigger_typing)
        except discord.NotFound:
            if self.interaction is not None:
                await super().channel.trigger_typing()
            else:
                raise
        except Exception:
            raise

    async def send(self, *args, **kwargs) -> discord.Message:
        return await self.send_handler.send(*args, **kwargs)


__all__: list[str] = [
    "CustomContext",
    "SendHandler",
]

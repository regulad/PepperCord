from typing import Dict, Any

import discord
from discord.ext import commands


class CustomContext(commands.Context):
    def __init__(self, **attrs):
        self._custom_state: Dict[Any, Any] = {}
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

    async def send(self, *args, **kwargs) -> None:
        if self.interaction is None:
            if kwargs.get("ephemeral") is not None:
                del kwargs["ephemeral"]
            if kwargs.get("return_message") is not None:
                del kwargs["return_message"]
            if kwargs.get("reference") is None:
                kwargs["reference"] = self.message
            return await super().send(*args, **kwargs)
        try:
            return await super().send(*args, **kwargs)
        except discord.NotFound:
            if self.interaction is not None:
                await self.interaction.followup.send(*args, **kwargs)
            else:
                raise
        except Exception:
            raise

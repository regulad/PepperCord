from typing import Dict, Any

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

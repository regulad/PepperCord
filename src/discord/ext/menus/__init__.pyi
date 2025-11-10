# -*- coding: utf-8 -*-

"""
Type stub file for discord.ext.menus
This stub was generated using data from the Claude LLM, in addition to my own code.
It is accurate with discord-ext-menus (1.0.0a32+g8686b5d 8686b5d) and discord-py 2.6.4
"""

from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Literal,
    Mapping,
    Optional,
    Self,
    Sequence,
    Union,
)
from collections import OrderedDict
import discord
from discord.ext import commands

__version__: str

class MenuError(Exception): ...

class CannotEmbedLinks(MenuError):
    def __init__(self) -> None: ...

class CannotSendMessages(MenuError):
    def __init__(self) -> None: ...

class CannotAddReactions(MenuError):
    def __init__(self) -> None: ...

class CannotReadMessageHistory(MenuError):
    def __init__(self) -> None: ...

class Position:
    bucket: int
    number: int

    def __init__(self, number: int, *, bucket: int = ...) -> None: ...
    def __lt__(self, other: Position) -> bool: ...
    def __eq__(self, other: object) -> bool: ...
    def __le__(self, other: Position) -> bool: ...
    def __gt__(self, other: Position) -> bool: ...
    def __ge__(self, other: Position) -> bool: ...
    def __repr__(self) -> str: ...

class Last(Position):
    def __init__(self, number: int = ...) -> None: ...

class First(Position):
    def __init__(self, number: int = ...) -> None: ...

def _cast_emoji(obj: Union[str, discord.PartialEmoji]) -> discord.PartialEmoji: ...

_ActionCallback = Callable[[Any, discord.RawReactionActionEvent], Awaitable[Any]]
_SkipIfCallback = Callable[[Any], bool]

class Button[
    _BotT: commands.Bot, _ContextT: commands.Context[Any], _MenuT: Menu[Any, Any]
]:  # TODO: _ContextT is really commands.Context[_BotT], _MenuT is really Menu[_BotT, _ContextT]
    emoji: discord.PartialEmoji
    position: Position
    lock: bool

    def __init__(
        self,
        emoji: Union[str, discord.PartialEmoji],
        action: Callable[[_MenuT, discord.RawReactionActionEvent], Awaitable[Any]],
        *,
        skip_if: Optional[Callable[[_MenuT], bool]] = ...,
        position: Optional[Position] = ...,
        lock: bool = ...,
    ) -> None: ...
    @property
    def skip_if(self) -> Callable[[_MenuT], bool]: ...
    @skip_if.setter
    def skip_if(self, value: Optional[Callable[[_MenuT], bool]]) -> None: ...
    @property
    def action(
        self,
    ) -> Callable[[_MenuT, discord.RawReactionActionEvent], Awaitable[Any]]: ...
    @action.setter
    def action(
        self, value: Callable[[_MenuT, discord.RawReactionActionEvent], Awaitable[Any]]
    ) -> None: ...
    def __call__(
        self, menu: _MenuT, payload: discord.RawReactionActionEvent
    ) -> Optional[Awaitable[Any]]: ...
    def __str__(self) -> str: ...
    def is_valid(self, menu: _MenuT) -> bool: ...

def button[_F: Callable[..., Awaitable[Any]]](
    emoji: Union[str, discord.PartialEmoji],
    **kwargs: Any,
) -> Callable[[_F], _F]: ...

# TODO: There is no way to make a typevar that is dependent on another typevar, unfortunately.
class Menu[
    _BotT: commands.Bot, _ContextT: commands.Context[Any]
]:  # _ContextT's Any generic is really _BotT

    timeout: float
    delete_message_after: bool
    clear_reactions_after: bool
    check_embeds: bool
    message: Optional[discord.Message]
    ctx: Optional[_ContextT]
    bot: Optional[_BotT]

    def __init__(
        self,
        *,
        timeout: float = ...,
        delete_message_after: bool = ...,
        clear_reactions_after: bool = ...,
        check_embeds: bool = ...,
        message: Optional[discord.Message] = ...,
    ) -> None: ...
    @property
    def buttons(
        self,
    ) -> Mapping[discord.PartialEmoji, Button[_BotT, _ContextT, Self]]: ...
    def add_button(
        self, button: Button[_BotT, _ContextT, Self], *, react: bool = False
    ) -> None | Awaitable[None]: ...
    def remove_button(
        self,
        emoji: Union[Button[_BotT, _ContextT, Self], str, discord.PartialEmoji],
        *,
        react: bool = False,
    ) -> None: ...
    def clear_buttons(self, *, react: bool = False) -> None | Awaitable[None]: ...
    def should_add_reactions(self) -> bool: ...
    def reaction_check(self, payload: discord.RawReactionActionEvent) -> bool: ...
    async def update(self, payload: discord.RawReactionActionEvent) -> None: ...
    async def on_menu_button_error(self, exc: Exception) -> None: ...
    async def start(
        self,
        ctx: _ContextT,
        *,
        channel: Optional[discord.abc.Messageable] = ...,
        wait: bool = ...,
    ) -> None: ...
    async def finalize(self, timed_out: bool) -> None: ...
    async def send_initial_message(
        self,
        ctx: _ContextT,
        channel: discord.abc.Messageable,
    ) -> discord.Message: ...
    def stop(self) -> None: ...
    @classmethod
    def get_buttons(
        cls,
    ) -> OrderedDict[discord.PartialEmoji, Button[_BotT, _ContextT, Self]]: ...

class PageSource[_PageT, _MenuPagesT: MenuPages[Any, Any, Any]]:
    async def prepare(self) -> None: ...
    def is_paginating(self) -> bool: ...
    def get_max_pages(self) -> Optional[int]: ...
    async def get_page(self, page_number: int) -> _PageT: ...
    async def format_page(
        self,
        menu: _MenuPagesT,
        page: _PageT,
    ) -> Union[
        str, discord.Embed, Dict[str, Any]
    ]: ...  # TODO: Dict[str, Any] is the kwargs to discord.abc.Messageable.send

class MenuPages[
    _BotT: commands.Bot, _ContextT: commands.Context[Any], _Source: PageSource[Any, Any]
](
    Menu[_BotT, _ContextT]
):  # TODO: _ContextT is really commands.Context[_BotT], _Source: PageSource[Any, Self]
    current_page: int

    def __init__(self, source: _Source, **kwargs: Any) -> None: ...
    @property
    def source(self) -> _Source: ...
    async def change_source(self, source: _Source) -> None: ...
    def should_add_reactions(self) -> bool: ...
    async def show_page(self, page_number: int) -> None: ...
    async def send_initial_message(
        self,
        ctx: _ContextT,
        channel: discord.abc.Messageable,
    ) -> discord.Message: ...
    async def start(
        self,
        ctx: _ContextT,
        *,
        channel: Optional[discord.abc.Messageable] = ...,
        wait: bool = ...,
    ) -> None: ...
    async def show_checked_page(self, page_number: int) -> None: ...
    async def show_current_page(self) -> None: ...
    async def go_to_first_page(
        self, payload: discord.RawReactionActionEvent
    ) -> None: ...
    async def go_to_previous_page(
        self, payload: discord.RawReactionActionEvent
    ) -> None: ...
    async def go_to_next_page(
        self, payload: discord.RawReactionActionEvent
    ) -> None: ...
    async def go_to_last_page(
        self, payload: discord.RawReactionActionEvent
    ) -> None: ...
    async def stop_pages(self, payload: discord.RawReactionActionEvent) -> None: ...

class ListPageSource[_T, _MenuPagesT: MenuPages[Any, Any, Any]](
    PageSource[Union[_T, List[_T]], _MenuPagesT]
):  # MenuPagesT 3rd generic will always be Self, but can't pass it in
    entries: Sequence[_T]
    per_page: int

    def __init__(self, entries: Sequence[_T], *, per_page: int) -> None: ...
    def is_paginating(self) -> bool: ...
    def get_max_pages(self) -> int: ...
    async def get_page(self, page_number: int) -> Union[_T, List[_T]]: ...

class _GroupByEntry[_T]:
    key: Any
    items: List[_T]

class GroupByPageSource[_T, _MenuPagesT: MenuPages[Any, Any, Any]](
    ListPageSource[_T, _MenuPagesT]
):
    nested_per_page: int

    def __init__(
        self,
        entries: Sequence[_T],
        *,
        key: Callable[[_T], Any],
        per_page: int,
        sort: bool = ...,
    ) -> None: ...

class AsyncIteratorPageSource[_T, _MenuPagesT: MenuPages[Any, Any, Any]](
    PageSource[Union[_T, List[_T]], _MenuPagesT]
):
    iterator: AsyncIterator[_T]
    per_page: int

    def __init__(self, iterator: AsyncIterator[_T], *, per_page: int) -> None: ...
    async def prepare(self) -> None: ...
    def is_paginating(self) -> bool: ...
    async def get_page(self, page_number: int) -> Union[_T, List[_T]]: ...

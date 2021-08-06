from typing import List, Union, Optional

import discord
from discord.ext import menus, commands
from pretty_help import Paginator, PrettyMenu

from utils.bots import CustomContext


class PlainListPageSource(menus.ListPageSource):
    async def format_page(self, menu, page):
        return page


class BetterMenu(PrettyMenu):
    async def send_pages(
        self,
        ctx: CustomContext,
        destination: discord.abc.Messageable,
        pages: List[discord.Embed],
    ) -> None:
        (
            await menus.MenuPages(
                PlainListPageSource(pages, per_page=1), delete_message_after=True
            ).start(ctx, channel=destination)
        )


class BetterPaginator(Paginator):
    def __init__(
        self,
        show_index: bool = True,
        color: Union[int, discord.Colour] = 0,
        *,
        ending_note: Optional[str] = None,
        char_limit: int = 6000,
        field_limit: int = 25,
        prefix: str = "```",
        suffix: str = "```",
    ) -> None:  # To be honest, I'm not sure why I did this. This library sucks big time.
        super().__init__(show_index, color)
        if ending_note is not None:
            self.ending_note = ending_note
        if char_limit != 6000:
            self.char_limit = char_limit
        if field_limit != 25:
            self.field_limit = field_limit
        if prefix != "```":
            self.prefix = prefix
        if suffix != "```":
            self.suffix = suffix


__all__ = ["BetterMenu", "BetterPaginator"]

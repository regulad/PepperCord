from typing import List

import discord
from discord.ext import menus
from pretty_help import PrettyMenu

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
            await menus.ViewMenuPages(
                PlainListPageSource(pages, per_page=1), delete_message_after=True
            ).start(
                ctx, ephemeral=True
            )  # This could be changed, maybe.
        )


__all__ = ["BetterMenu"]

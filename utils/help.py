import asyncio
from typing import List

import discord
from discord.ext import commands, menus
from discord.ext.menus import views
from pretty_help import PrettyHelp, PrettyMenu

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
        await views.ViewMenuPages(PlainListPageSource(pages, per_page=1), delete_message_after=True).start(ctx, channel=destination)


__all__ = ["BetterMenu"]

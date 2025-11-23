from __future__ import annotations

from asyncio import sleep
from typing import TYPE_CHECKING, Optional, Union, cast

from discord import Embed, Guild
from discord.ext.commands import Cog, guild_only, CheckFailure, command
from discord.ext.menus import ListPageSource, MenuPages

from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext


class MessageOfTheDay(Cog):
    """
    Tools used to communicate regular information with the bot's users.
    No user-facing commands.
    """

    def __init__(self, bot: CustomBot) -> None:
        self.bot = bot
        self._motd_channel_id = int(bot.config["PEPPERCORD_MOTD_CHANNEL"])
        self._motd_min_invocations = int(bot.config["PEPPERCORD_MOTD_MIN_INVOCATIONS"])

    @Cog.listener()
    async def on_after_invocation_nonblocking(self, context: CustomContext) -> None:
        await context["author_document"].update_db({"$inc": {"loyalty": 1}})
        # I'd like to see someone manage to cause an integer overflow with this.
        total_invocations = int(
            await context["author_document"].safe_subscript("loyalty")
        )
        # TODO: rest of this code

    @Cog.listener()
    async def on_ready(self) -> None:
        pass


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(MessageOfTheDay(bot))

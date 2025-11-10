from typing import Any, cast

from discord.ext import commands

from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext


class DocumentCog(commands.Cog):
    """Adds document keys to each document."""

    def __init__(self, bot: CustomBot):
        self.bot = bot

    @commands.Cog.listener("on_context_creation")
    async def append_guild_document(self, ctx: commands.Context[Any]) -> None:
        custom_ctx: CustomContext = cast(CustomContext, ctx)
        custom_ctx["guild_document"] = (
            await custom_ctx.bot.get_guild_document(custom_ctx.guild)
            if custom_ctx.guild is not None
            else {}
        )

    @commands.Cog.listener("on_context_creation")
    async def append_user_document(self, ctx: commands.Context[Any]) -> None:
        custom_ctx: CustomContext = cast(CustomContext, ctx)
        custom_ctx["author_document"] = await custom_ctx.bot.get_user_document(
            custom_ctx.author
        )


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(DocumentCog(bot))

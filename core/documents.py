from typing import cast

from discord.ext import commands

from utils.bots import BOT_TYPES, CustomContext
from utils.localization import Locale


class DocumentCog(commands.Cog):
    """Adds document keys to each document."""

    def __init__(self, bot: BOT_TYPES):
        self.bot = bot

    @commands.Cog.listener("on_context_creation")
    async def append_guild_document(self, ctx: commands.Context):
        ctx: CustomContext = cast(CustomContext, ctx)
        ctx["guild_document"] = await ctx.bot.get_guild_document(ctx.guild)
        # May be split off into localization cog.
        ctx["locale"] = Locale[ctx["guild_document"].get("locale", "en_US")]

    @commands.Cog.listener("on_context_creation")
    async def append_user_document(self, ctx: commands.Context):
        ctx: CustomContext = cast(CustomContext, ctx)
        ctx["user_document"] = await ctx.bot.get_user_document(ctx.author)


def setup(bot: BOT_TYPES) -> None:
    bot.add_cog(DocumentCog(bot))

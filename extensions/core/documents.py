from typing import cast

from discord.ext import commands

from utils.bots import BOT_TYPES, CustomContext


class DocumentCog(commands.Cog):
    """Adds document keys to each document."""

    def __init__(self, bot: BOT_TYPES):
        self.bot = bot

    @commands.Cog.listener("on_context_creation")
    async def append_guild_document(self, ctx: commands.Context):
        ctx: CustomContext = cast(CustomContext, ctx)
        ctx["guild_document"] = (
            await ctx.bot.get_guild_document(ctx.guild) if ctx.guild is not None else {}
        )

    @commands.Cog.listener("on_context_creation")
    async def append_user_document(self, ctx: commands.Context):
        ctx: CustomContext = cast(CustomContext, ctx)
        ctx["author_document"] = await ctx.bot.get_user_document(ctx.author)


async def setup(bot: BOT_TYPES) -> None:
    await bot.add_cog(DocumentCog(bot))

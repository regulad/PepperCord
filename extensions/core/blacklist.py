from typing import Optional, Union

import discord
from discord.ext import commands

from utils import checks
from utils.bots import CustomContext, BOT_TYPES


class Blacklist(commands.Cog):
    """The blacklist system allows the bots owner to take abuse matters into their own hands and prevent a malicious
    user or guild from abusing the bots."""

    def __init__(self, bot: BOT_TYPES):
        self.bot: BOT_TYPES = bot

    async def bot_check(self, ctx: CustomContext) -> bool:
        if await checks.is_blacklisted(ctx):
            raise checks.Blacklisted()
        else:
            return True

    async def cog_check(self, ctx: CustomContext) -> bool:
        return await ctx.bot.is_owner(ctx.author)

    @commands.command(
        name="blacklists",
    )
    async def blacklist(
        self,
        ctx: CustomContext,
        *,
        entity: Optional[Union[discord.User, discord.Member, discord.Guild]],
    ) -> None:
        """Disallows a user, member, or a guild from using the bot."""
        entity: Union[discord.User, discord.Member, discord.Guild] = entity or ctx.guild
        if isinstance(entity, discord.Guild):
            document = await ctx.bot.get_guild_document(entity)
        else:
            document = await ctx.bot.get_user_document(entity)
        await document.update_db({"$set": {"blacklisted": True}})
        await ctx.send(f"Blacklisted {entity.name}.", ephemeral=True)

    @commands.command(
        name="unblacklist",
    )
    async def unblacklist(
        self,
        ctx: CustomContext,
        *,
        entity: Optional[Union[discord.User, discord.Member, discord.Guild]],
    ) -> None:
        """Allows a user, member, or a guild to use the bot"""
        entity: Union[discord.User, discord.Member, discord.Guild] = entity or ctx.guild
        if isinstance(entity, discord.Guild):
            document = await ctx.bot.get_guild_document(entity)
        elif isinstance(entity, (discord.Member, discord.User)):
            document = await ctx.bot.get_user_document(entity)
        await document.update_db({"$set": {"blacklisted": False}})
        await ctx.send(f"Unblacklisted {entity.name}.", ephemeral=True)


def setup(bot: BOT_TYPES):
    bot.add_cog(Blacklist(bot))

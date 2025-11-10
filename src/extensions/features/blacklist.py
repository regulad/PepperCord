from typing import Optional, Union

import discord
from discord.ext import commands

from utils.checks.blacklisted import is_blacklisted, EBlacklisted
from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext


class Blacklist(commands.Cog):
    """The blacklist system allows the bots owner to take abuse matters into their own hands and prevent a malicious
    user or guild from abusing the bots."""

    def __init__(self, bot: CustomBot) -> None:
        self.bot = bot

    async def bot_check(self, ctx: CustomContext) -> bool:  # type: ignore[override]  # bad types exported
        if await is_blacklisted(ctx) or (
            ctx.bot.config.get("PEPPERCORD_TESTGUILDS") is not None
            and ctx.guild is not None
            and ctx.guild.id
            not in [
                int(guild)
                for guild in ctx.bot.config["PEPPERCORD_TESTGUILDS"].split(",")
            ]
        ):
            raise EBlacklisted()
        else:
            return True

    async def cog_check(self, ctx: CustomContext) -> bool:  # type: ignore[override]  # bad types exported
        return await ctx.bot.is_owner(ctx.author)

    @commands.command()
    async def blacklist(
        self,
        ctx: CustomContext,
        *,
        entity: Optional[Union[discord.User, discord.Member, discord.Guild]],
    ) -> None:
        """Disallows a user, member, or a guild from using the bot."""
        entity = entity or ctx.guild
        if entity is None:
            raise RuntimeError("No entity could be determined!")
        if isinstance(entity, discord.Guild):
            document = await ctx.bot.get_guild_document(entity)
        else:
            document = await ctx.bot.get_user_document(entity)
        await document.update_db({"$set": {"blacklisted": True}})
        await ctx.send(f"Blacklisted {entity.name}.", ephemeral=True)

    @commands.command()
    async def unblacklist(
        self,
        ctx: CustomContext,
        *,
        entity: Optional[Union[discord.User, discord.Member, discord.Guild]],
    ) -> None:
        """Allows a user, member, or a guild to use the bot"""
        entity = entity or ctx.guild
        if entity is None:
            raise RuntimeError("No entity could be determined!")
        if isinstance(entity, discord.Guild):
            document = await ctx.bot.get_guild_document(entity)
        elif isinstance(entity, (discord.Member, discord.User)):
            document = await ctx.bot.get_user_document(entity)
        await document.update_db({"$set": {"blacklisted": False}})
        await ctx.send(f"Unblacklisted {entity.name}.", ephemeral=True)


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(Blacklist(bot))

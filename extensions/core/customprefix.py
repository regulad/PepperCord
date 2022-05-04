from typing import Optional

import discord
from discord.app_commands import guild_only
from discord.ext import commands

from utils.bots import BOT_TYPES, CustomContext
from utils.database import Document


async def get_prefix(bot: BOT_TYPES, message: discord.Message) -> list[str]:
    prefix: str = bot.config.get("PEPPERCORD_PREFIX", "?")
    if message.guild is not None:
        if not hasattr(bot, "__p_cache"):
            bot.__p_cache = {}

        if bot.__p_cache.get(message.guild.id) is None:
            guild_document: Document = await bot.get_guild_document(message.guild)
            prefix: str = guild_document.get("prefix", prefix)
            bot.__p_cache[message.guild.id] = prefix
        else:
            prefix: str = bot.__p_cache[message.guild.id]
    return commands.when_mentioned_or(f"{prefix} ", prefix)(bot, message)


class CustomPrefix(commands.Cog):
    """Allows you to have a custom prefix for commands just in this guild."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot

    @commands.command()
    @guild_only()
    @commands.has_permissions(administrator=True)
    async def prefix(
            self,
            ctx: CustomContext,
            *,
            prefix: Optional[str],
    ) -> None:
        """Changes the bot's prefix. This is only for message commands."""
        if prefix is not None:
            if prefix == ctx.bot.config.get("PEPPERCORD_PREFIX", "?"):
                await ctx["guild_document"].update_db({"$unset": {"prefix": 1}})
            else:
                await ctx["guild_document"].update_db({"$set": {"prefix": prefix}})
        await ctx.send(
            f"The prefix is now "
            f"{ctx['guild_document'].get('prefix', ctx.bot.config.get('PEPPERCORD_PREFIX', '?'))}."
        )
        if not hasattr(ctx.bot, "__p_cache"):
            ctx.bot.__p_cache = {}
        ctx.bot.__p_cache[ctx.guild.id] = ctx['guild_document'].get('prefix',
                                                                    ctx.bot.config.get('PEPPERCORD_PREFIX', '?'))


async def setup(bot: BOT_TYPES) -> None:
    bot.command_prefix = get_prefix
    await bot.add_cog(CustomPrefix(bot))


async def teardown(bot: BOT_TYPES) -> None:
    bot.command_prefix = bot.config.get("PEPPERCORD_PREFIX", "?")
    await bot.remove_cog("CustomPrefix")

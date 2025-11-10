from typing import Iterable, Optional, Sequence

import discord
from discord.app_commands import guild_only
from discord.ext import commands

from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext
from utils.database import PCDocument


async def get_prefix(bot: CustomBot, message: discord.Message) -> Iterable[str]:
    prefix: str = bot.config.get("PEPPERCORD_PREFIX", "?")
    if message.guild is not None:
        if bot["prefix_cache"].get(message.guild.id) is None:
            guild_document: PCDocument = await bot.get_guild_document(message.guild)
            prefix = guild_document.get("prefix", prefix)
            bot["prefix_cache"][message.guild.id] = prefix
        else:
            prefix = bot["prefix_cache"][message.guild.id]
    return commands.when_mentioned_or(f"{prefix} ", prefix)(bot, message)


class CustomPrefix(commands.Cog):
    """Allows you to have a custom prefix for commands just in this guild."""

    def __init__(self, bot: CustomBot) -> None:
        self.bot = bot

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
        ctx.bot["prefix_cache"][ctx.guild.id] = ctx["guild_document"].get(  # type: ignore[union-attr]  # guaranteed at runtime
            "prefix", ctx.bot.config.get("PEPPERCORD_PREFIX", "?")
        )


async def setup(bot: CustomBot) -> None:
    bot["prefix_cache"] = {}
    bot.command_prefix = get_prefix  # type: ignore[assignment]  # this does work
    await bot.add_cog(CustomPrefix(bot))


async def teardown(bot: CustomBot) -> None:
    del bot["prefix_cache"]
    bot.command_prefix = bot.config.get("PEPPERCORD_PREFIX", "?")
    await bot.remove_cog("CustomPrefix")

from typing import Optional

import discord
from discord.ext import commands

from utils.bots import BOT_TYPES, CustomContext
from utils.database import Document


async def get_prefix(bot: BOT_TYPES, message: discord.Message) -> list[str]:
    prefix: str = bot.config.get("PEPPERCORD_PREFIX", "?")
    if message.guild is not None:
        guild_document: Document = await bot.get_guild_document(message.guild)
        prefix: str = guild_document.get("prefix", prefix)
    return commands.when_mentioned_or(f"{prefix} ", prefix)(bot, message)


class CustomPrefix(commands.Cog):
    """Allows you to have a custom prefix for commands just in this guild."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def prefix(
            self,
            ctx: CustomContext,
            *,
            prefix: Optional[str] = commands.Option(description="The new prefix to set.")
    ) -> None:
        """Changes the bot's prefix. This is only for message commands."""
        if ctx.interaction is None:
            if prefix is not None:
                if prefix == ctx.bot.config.get("PEPPERCORD_PREFIX", "?"):
                    await ctx["guild_document"].update_db({"$unset": {"prefix": 1}})
                else:
                    await ctx["guild_document"].update_db({"$set": {"prefix": prefix}})
            await ctx.send(f"The prefix is now "
                           f"{ctx['guild_document'].get('prefix', ctx.bot.config.get('PEPPERCORD_PREFIX', '?'))}.")
        else:
            await ctx.send("You cannot set a prefix for slash messages.")


def setup(bot: BOT_TYPES) -> None:
    bot.command_prefix = get_prefix
    bot.add_cog(CustomPrefix(bot))


def teardown(bot: BOT_TYPES) -> None:
    bot.command_prefix = bot.config.get("PEPPERCORD_PREFIX", "?")
    bot.remove_cog("CustomPrefix")

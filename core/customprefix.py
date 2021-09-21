import discord
from discord.ext import commands

from utils import checks
from utils.bots import BOT_TYPES, CustomContext
from utils.database import Document
from utils.localization import Message


async def get_prefix(bot: BOT_TYPES, message: discord.Message) -> str:
    default_prefix: str = bot.config.get("PEPPERCORD_PREFIX", "?")
    if message.guild is None:
        return commands.when_mentioned_or(f"{default_prefix} ", default_prefix)(
            bot, message
        )
    else:
        guild_document: Document = await bot.get_guild_document(message.guild)
        prefix: str = guild_document.get("prefix", default_prefix)
        return commands.when_mentioned_or(f"{prefix} ", prefix)(bot, message)


class CustomPrefix(commands.Cog):
    """Allows you to have a custom prefix for commands just in this guild."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot

    @commands.command(
        name="prefix",
        description="Sets the bot's prefix.\n"
                    "It can be any string, and will only apply to this server.",
    )
    @checks.check_is_admin
    async def prefix(self, ctx: CustomContext, *, prefix: str) -> None:
        if prefix == ctx.bot.config.get("PEPPERCORD_PREFIX", "?"):
            await ctx["guild_document"].update_db({"$unset": {"prefix": 1}})
        else:
            await ctx["guild_document"].update_db({"$set": {"prefix": prefix}})

    @commands.command(
        name="getprefix",
        description="Gets the bot's prefix in this server.",
    )
    async def prefix(self, ctx: CustomContext) -> None:
        await ctx.send(
            ctx["locale"].get_message(Message.PREFIX_GET).format(
                prefix=str(await get_prefix(ctx.bot, ctx.message))
            )
        )


def setup(bot: BOT_TYPES) -> None:
    bot.command_prefix = get_prefix
    bot.add_cog(CustomPrefix(bot))


def teardown(bot: BOT_TYPES) -> None:
    bot.command_prefix = bot.config.get("PEPPERCORD_PREFIX", "?")
    bot.remove_cog("CustomPrefix")

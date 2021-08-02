from discord.ext import commands

from utils.checks import LowPrivilege, has_permission_level
from utils.permissions import Permission, get_permission
from utils import checks


async def get_prefix(bot, message):
    default_prefix = bot.config.get("PEPPERCORD_PREFIX", "?")
    if message.guild is None:
        return commands.when_mentioned_or(f"{default_prefix} ", default_prefix)(bot, message)
    else:
        guild_document = await bot.get_guild_document(message.guild)
        prefix = guild_document.get("prefix", default_prefix)
        return commands.when_mentioned_or(f"{prefix} ", prefix)(bot, message)


class CustomPrefix(commands.Cog):
    """Allows you to have a custom prefix for commands just in this guild."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        if not await has_permission_level(ctx, Permission.ADMINISTRATOR):
            raise LowPrivilege(Permission.ADMINISTRATOR, get_permission(ctx))
        else:
            return True

    @commands.command(
        name="prefix",
        brief="Sets the bots's prefix.",
        description="Sets the bots's prefix. It can be any string, and will only apply to this server.",
    )
    async def prefix(self, ctx, *, prefix: str):
        if prefix == ctx.bot.config.get("PEPPERCORD_PREFIX", "?"):
            await ctx.guild_document.update_db({"$unset": {"prefix": 1}})
        else:
            await ctx.guild_document.update_db({"$set": {"prefix": prefix}})


def setup(bot):
    bot.command_prefix = get_prefix
    bot.add_cog(CustomPrefix(bot))


def teardown(bot):
    bot.command_prefix = bot.config.get("PEPPERCORD_PREFIX", "?")
    bot.remove_cog("CustomPrefix")

from discord.ext import commands

from utils import checks


async def get_prefix(bot, message):
    guild_document = await bot.get_document(message.guild)
    default_prefix = bot.config.get("PEPPERCORD_PREFIX", "?")
    if message.guild is None:
        return commands.when_mentioned_or(f"{default_prefix} ", default_prefix)(bot, message)
    else:
        prefix = guild_document.setdefault("prefix", default_prefix)
        return commands.when_mentioned_or(f"{prefix} ", prefix)(bot, message)


class CustomPrefix(commands.Cog):
    """Allows you to have a custom prefix for commands just in this guild."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await checks.is_admin(ctx)

    @commands.command(
        name="prefix",
        brief="Sets the bots's prefix.",
        description="Sets the bots's prefix. It can be any string, and will only apply to this server.",
    )
    async def prefix(self, ctx, *, prefix: str):
        if prefix == ctx.bot.config.get("PEPPERCORD_PREFIX", "?"):
            del ctx.guild_document["prefix"]
        else:
            ctx.guild_document["prefix"] = prefix
        await ctx.guild_document.replace_db()


def setup(bot):
    bot.command_prefix = get_prefix
    bot.add_cog(CustomPrefix(bot))


def teardown(bot):
    bot.command_prefix = bot.config.get("PEPPERCORD_PREFIX", "?")
    bot.remove_cog("CustomPrefix")

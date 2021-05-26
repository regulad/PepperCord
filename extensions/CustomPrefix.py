from discord.ext import commands
from utils import checks
from utils.database import Document


async def get_prefix(bot, message):
    document = await Document.get_from_id(bot.database["guild"], message.guild.id)
    default_prefix = bot.config["discord"]["commands"]["prefix"]
    if message.guild is None:
        return commands.when_mentioned_or(f"{default_prefix} ", default_prefix)(bot, message)
    else:
        prefix = document.setdefault("prefix", default_prefix)
        return commands.when_mentioned_or(f"{prefix} ", prefix)(bot, message)


class CustomPrefix(commands.Cog):
    """Allows you to have a custom prefix for commands just in this guild."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await checks.is_admin(ctx)

    @commands.command(
        name="prefix",
        brief="Sets the bot's prefix.",
        description="Sets the bot's prefix. It can be any string, and will only apply to this server.",
    )
    async def prefix(self, ctx, *, prefix: str):
        if prefix == self.bot.config["discord"]["commands"]["prefix"]:
            del ctx.guild_doc["prefix"]
        else:
            ctx.guild_doc["prefix"] = prefix
        await ctx.guild_doc.replace_db()


def setup(bot):
    bot.command_prefix = get_prefix
    bot.add_cog(CustomPrefix(bot))


def teardown(bot):
    bot.command_prefix = bot.config["discord"]["commands"]["prefix"]
    bot.remove_cog("CustomPrefix")

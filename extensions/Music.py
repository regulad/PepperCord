from discord.ext import commands

from utils import checks, errors


class Music(commands.Cog):
    """Listen to your favorite tracks in a voice channel."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await checks.is_alone_or_manager(ctx)


def setup(bot):
    bot.add_cog(Music(bot))

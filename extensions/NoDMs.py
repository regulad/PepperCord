from discord.ext import commands


class NoDMs(commands.Cog):
    """Disables use of the bots in DMs."""

    def __init__(self, bot):
        self.bot = bot

    async def bot_check_once(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage
        return True


def setup(bot):
    bot.add_cog(NoDMs(bot))

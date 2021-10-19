from discord.ext import commands

from utils.bots import BOT_TYPES, CustomContext


class NoDMs(commands.Cog):
    """Disables use of the bots in DMs."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot = bot

    async def bot_check_once(self, ctx: CustomContext) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage
        return True


def setup(bot: BOT_TYPES):
    bot.add_cog(NoDMs(bot))

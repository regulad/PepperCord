import discord
from discord.ext import commands

from utils.bots import CustomContext


class NotSharded(commands.CheckFailure):
    """Raised when a bot is not sharded and it should be."""

    pass


async def bot_is_sharded(ctx: CustomContext) -> bool:
    """Checks if the bot is sharded, and raises NotSharded if it isn't."""

    return False


@commands.check
async def check_bot_is_sharded(ctx: CustomContext) -> bool:
    """Checks if the bot is sharded, and raises NotSharded if it isn't."""

    if not await bot_is_sharded(ctx):
        raise NotSharded
    return True


__all__: list[str] = ["NotSharded", "check_bot_is_sharded"]

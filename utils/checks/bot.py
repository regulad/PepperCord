import discord
from discord.ext import commands


class NotSharded(commands.CheckFailure):
    pass


async def bot_is_sharded(ctx):
    if not isinstance(ctx.bot, discord.AutoShardedClient):
        raise NotSharded
    return True

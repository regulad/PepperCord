import discord
from aiohttp import ClientSession
from discord.ext import commands
from discord.ext.commands import command

from utils import bots


class APIs(commands.Cog):
    """Gets information from all over the internet."""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot = bot
        self.aiohttp_cs = ClientSession()

    async def cog_unload(self) -> None:
        await self.aiohttp_cs.close()

    @command()
    async def bored(self, ctx: bots.CustomContext) -> None:
        """Gives you something to do to stop you from being bored."""
        await ctx.defer()
        async with self.aiohttp_cs.get(
                "https://www.boredapi.com/api/activity/"
        ) as request:
            result = await request.json()
        embed = discord.Embed(
            title=f"Category: {result['type'].title()}", description=result["activity"]
        )
        await ctx.send(embed=embed)


async def setup(bot: bots.BOT_TYPES) -> None:
    await bot.add_cog(APIs(bot))

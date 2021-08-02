from json import JSONDecodeError

from aiohttp import ClientSession, ContentTypeError
import discord
from discord.ext import commands

from utils import bots


class APIs(commands.Cog):
    """Gets information from all over the internet."""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot = bot
        self.aiohttp_cs = ClientSession()

    def cog_unload(self) -> None:
        self.bot.loop.create_task(self.aiohttp_cs.close())

    @commands.command(name="bored", description="Do something, stop being bored!", brief="Anti-boredom.")
    async def bored(self, ctx: bots.CustomContext) -> None:
        async with self.aiohttp_cs.get("https://www.boredapi.com/api/activity/") as request:
            result = await request.json()
        embed = discord.Embed(title=f"Category: {result['type'].title()}", description=result["activity"])
        await ctx.send(embed=embed)

    """
    @commands.command(name="quote", description="Get inspired from a random quote.", brief="Get inspired!")
    async def quote(self, ctx: bots.CustomContext) -> None:
        while True:  # This API fucking sucks.
            async with self.aiohttp_cs.get("https://api.forismatic.com/api/1.0/?method=getQuote&format=json&lang=en") \
                    as request:
                try:
                    result = await request.json()
                except ContentTypeError or JSONDecodeError:
                    continue
                else:
                    break
        embed = discord.Embed(title=result["quoteText"]).set_author(name=result["quoteAuthor"])
        await ctx.send(embed=embed)
    """  # API is a mess. TODO: Find a new one.


def setup(bot: bots.BOT_TYPES) -> None:
    bot.add_cog(APIs(bot))

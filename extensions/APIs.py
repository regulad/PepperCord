import aiohttp
import discord
from discord.ext import commands


class APIs(
    commands.Cog,
    name="APIs",
    description="Gets random information from all over the internet and beyond.",
):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="bored", description="Do something, stop being bored!", brief="Anti-boredom.")
    async def bored(self, ctx):
        async with aiohttp.ClientSession() as client:
            async with client.get("https://www.boredapi.com/api/activity/") as request:
                result = await request.json()
        embed = discord.Embed(title=result["type"], description=result["activity"])
        await ctx.send(embed=embed)

    @commands.command(name="quote", description="Get inspired from a random quote.", brief="Get inspired!")
    async def quote(self, ctx):
        async with aiohttp.ClientSession() as client:
            async with client.get("https://api.forismatic.com/api/1.0/?method=getQuote&format=json&lang=en") as request:
                result = await request.json()
        embed = discord.Embed(title=result["quoteText"]).set_author(name=result["quoteAuthor"])
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(APIs(bot))

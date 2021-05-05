import discord
from discord.ext import commands
from discord_slash import cog_ext, SlashContext

class test(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @cog_ext.cog_slash(name='test', description=['Humorous testing command'])
    async def test(self, ctx: SlashContext):
        embed = discord.Embed(title="You Smell")
        await ctx.send(embeds=[embed])

def setup(bot):
    bot.add_cog(test(bot))

from art import text2art
from discord.ext import commands

class textDecoration(commands.Cog, name='Art', description='Convert text into art using art from PyPI'):
  def __init__(self, bot):
    self.bot = bot

  @commands.command(name='asciiArt', aliases=['ascii'], description='Turn any text into ascii art!', usage='<Text>')
  async def asciiArt(self, ctx, *, text):
    art = text2art(text, font='rnd-medium')
    await ctx.send(f'```{art}```')

def setup(bot):
  bot.add_cog(textDecoration(bot))

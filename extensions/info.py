import discord
from discord.ext import commands

class info(commands.Cog, name='Metrics', description='Shows data on the bot, servers, and users.'):
  def __init__(self, bot):
    self.bot = bot
  
  @commands.command(name='serverInfo', description='Displays information about the server the bot is in.',breif='Get server info.', usage='[Guild ID]')
  async def serverInfo(self, ctx, *, guild: discord.Guild = None):
    try:
      if not guild:
        guild = ctx.guild
    except Exception as e:
      ctx.send('Couldn\'t find the server. If you are in a DM, you must specify the guild ID.')
      raise Exception(e)
    embed = discord.Embed(title=f'Info for {guild.name}\n({guild.id})').set_thumbnail(url=guild.icon_url).add_field(name=f'{len}')
    await ctx.send(embed=embed)
  
  @commands.command(name='userInfo', description='Displays information about a user.',breif='Get user info.', usage='[User (ID/Mention/Name)]')
  async def userInfo(self, ctx, *, user: discord.User = None):
    if not user:
      user = ctx.author
    embed = discord.Embed(title=f'Info for {user.name}\n({user.id})').set_thumbnail(url=user.avatar_url)
    await ctx.send(embed=embed)

def setup(bot):
  bot.add_cog(info(bot))

import discord
from discord.ext import commands

class info(commands.Cog, name='Metrics', description='Shows data on the bot, servers, and users.'):
  def __init__(self, bot):
    self.bot = bot
  
    self.activityUpdate.start()
  
  def cog_unload(self):
    self.activityUpdate.stop()
  
  @tasks.loop(seconds=60)
  async def activityUpdate(self):
    watchingString = f'with {len(self.bot.users)} users in {len(self.bot.guilds)} servers'
    await self.bot.change_presence(activity=discord.Game(name=watchingString))
  
  @activityUpdate.before_loop
  async def beforeActivyUpdate(self):
    await self.bot.wait_until_ready()

  @commands.command(name='serverInfo', aliases=['guildInfo', 'server', 'guild'], description='Displays information about the server the bot is in.', brief='Get server info.', usage='[Guild ID]')
  @commands.guild_only()
  async def serverInfo(self, ctx, *, guild: discord.Guild = None):
    try:
      if not guild:
        guild = ctx.guild
    except Exception as e:
      ctx.send('Couldn\'t find the server. If you are in a DM, you must specify the guild ID.')
      raise Exception(e)
    embed = discord.Embed(title=f'Info for {guild.name}\n({guild.id})').set_thumbnail(url=guild.icon_url).add_field(name=f'{len}')
    await ctx.send(embed=embed)
  
  @commands.command(name='userInfo', brief='Displays information about a user.',brief='Get user info.', usage='[User (ID/Mention/Name)]')
  async def userInfo(self, ctx, *, user: discord.User = None):
    if not user:
      user = ctx.author
    embed = discord.Embed(title=f'Info for {user.name}\n({user.id})').set_thumbnail(url=user.avatar_url)
    await ctx.send(embed=embed)

def setup(bot):
  bot.add_cog(info(bot))

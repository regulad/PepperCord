import discord, time, copy, io, contextlib, asyncio, typing
from errors import SubcommandNotFound
from discord.ext import commands

class dev(commands.Cog, name='Development', description='Dev-only commands. Users cannot execute these commands.'):
  def __init__(self, bot):
    self.bot = bot
  
  async def cog_check(self, ctx):
    return await self.bot.is_owner(ctx.author)

  @commands.command(name='nuke', aliases=['deleteserver'], brief='Effectively deletes server.', description='Removes all channels, roles, and members. Use with caution.', usage='[Guild ID]')
  @commands.guild_only()
  async def nuke(self, ctx, *, guild: discord.Guild = ''):
    if not guild:
      guild = ctx.guild
    message: discord.Message = await ctx.send(f"<a:alarm:841128716507676682> **Warning:** This action is destructive. *Please* only continue if you know what you are doing. <a:alarm:841128716507676682>")
    await message.add_reaction(emoji='\U00002705')
    await message.add_reaction(emoji='\U0000274c')
    def checkForReaction(reaction: discord.reaction, user: typing.Union[discord.Member, discord.User]):
      return bool((user.id == ctx.author.id) and (reaction.message == message) and (str(reaction.emoji) in ["\U00002705", "\U0000274c"]))
    try:
      reaction: discord.Reaction = await self.bot.wait_for(event='reaction_add', check=checkForReaction, timeout=20.0)
    except asyncio.TimeoutError:
      await message.clear_reaction(emoji='\U00002705')
      await message.clear_reaction(emoji='\U0000274c')
      await message.edit(content='Command timed out.')
      return
    else:
      if str(reaction[0].emoji) == "\U00002705":
        await message.edit(content='<a:alarm:841128716507676682> Nuking... <a:alarm:841128716507676682>')
      if str(reaction[0].emoji) == "\U0000274c":
        await message.clear_reaction(emoji='\U00002705')
        await message.clear_reaction(emoji='\U0000274c')
        await message.edit(content='Command disabled.')
        return
    fails = 0
    emojis = 0
    for emoji in guild.emojis:
      try:
        await emoji.delete()
      except:
        fails += 1
      else:
        emojis += 1
    roles = 0
    for role in guild.roles:
      try:
        await role.delete()
      except:
        fails += 1
      else:
        roles += 1
    channels = 0
    for channel in guild.channels:
      try:
        await channel.delete()
      except:
        fails += 1
      else:
        channels += 1
    members = 0
    for member in guild.members:
      try:
        await guild.ban(member.id)
      except:
        fails += 1
      else:
        members += 1
    await ctx.author.send(f'Done. Casualties: {roles} role(s), {emojis} emoji(s), {channels} channel(s), and {members} member(s). Unable to delete {fails} models.')

  @commands.command(name='message', brief='Send a message as the bot.', description='Send a message as the bot in any channel that you want.', usage='<Channel> <Message>')
  async def doMessage(self, ctx, channel: discord.TextChannel, *, text: str):
    channel = self.bot.get_channel(channel.id)
    await channel.send(text)
  
  @commands.command(name='nick', aliases=['nickname'], brief='Set bot\'s username.', description='Sets the bot\'s username itself.', usage='<Nickname>')
  async def nick(self, ctx, *, nick: str):
    await ctx.guild.me.edit(nick=nick)

def setup(bot):
  bot.add_cog(dev(bot))

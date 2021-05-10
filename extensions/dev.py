import discord, time, copy, io, contextlib, asyncio, typing
from main import activeConfigManager, activeExtensionManager
from tools.errors import SubcommandNotFound
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

  @commands.command(name='execute', aliases=['evalCode', 'validateCode', 'eval', 'exec'], brief='Evaluate Python code.', description='Evaluate Python code using eval().', usage='<Python Code>')
  async def execute(self, ctx, *, code: str = ''):
    if code.startswith('```') and code.endswith('```'):
      code = code.strip('```')
    try:
      exec(code)
    except Exception:
      await ctx.message.add_reaction('❌')
      return
    else:
      await ctx.message.add_reaction('✅')
  
  @commands.group(invoke_without_command=True, case_insensitive=True, name='extension', aliases=['extensions','cog', 'cogs'], brief='Manages extensions.', description='Manages discord.ext extensions.')
  async def extension(self, ctx):
    raise SubcommandNotFound()

  @extension.command(name='list', brief='Lists loaded extensions', description='Lists all extensions loaded by the main extensionManager instance.')
  async def listExtensions(self, ctx):
    await ctx.send(activeExtensionManager.listExtensions())

  @extension.command(name='load', brief='Loads extension or directory of extensions', description='Loads extension or directory of extensions present in the extensions folder.', usage='[Path]')
  async def loadExtension(self, ctx, *, extension: str = ''):
    try:
      extensionLoader = activeExtensionManager.loadExtension(extension)
    except Exception as e:
      await ctx.send(f'Failed to load extension: ```{e}```')
    else:
      if extensionLoader and (len(extensionLoader) > 0):
        await ctx.send(f'Finished loading extension(s). {extensionLoader} failed to load.')
      else:
        await ctx.send(f'Successfully loaded extension(s).')
  
  @extension.command(name='unload', brief='Unloads extension or directory of extensions', description='Unloads extension or directory of extensions present in the extensions folder.', usage='[Path]')
  async def unloadExtension(self, ctx, *, extension: str = ''):
    try:
      extensionLoader = activeExtensionManager.unloadExtension(extension)
    except Exception as e:
      await ctx.send(f'Failed to unload extension: ```{e}```')
    else:
      if extensionLoader and (len(extensionLoader) > 0):
        await ctx.send(f'Finished unloading extension(s). {extensionLoader} failed to load.')
      else:
        await ctx.send(f'Successfully unloaded extension(s).')
  
  @extension.command(name='reload', brief='Reloads extension or directory of extensions', description='Reloads extension or directory of extensions present in the extensions folder.', usage='[Path]')
  async def reloadExtension(self, ctx, *, extension: str = ''):
    try:
      extensionLoader = activeExtensionManager.reloadExtension(extension)
    except Exception as e:
      await ctx.send(f'Failed to reload extension: ```{e}```')
    else:
      if extensionLoader and (len(extensionLoader) > 0):
        await ctx.send(f'Finished reloading extension(s). {extensionLoader} failed to load.')
      else:
        await ctx.send(f'Successfully reloaded extension(s).')
  
  @commands.group(invoke_without_command=True, case_insensitive=True, name='config', aliases=['configuration', 'yaml'], brief='Manages configuration.', description='Manages bot configuration using the active configManager instance.')
  async def config(self, ctx):
    raise SubcommandNotFound()
  
  @config.command(name='readKey', aliases=['read'], brief='Reads YAML key.', description='Reads YAML key present in configuration.')
  async def readKey(self, ctx, key: str = ''):
    try:
      readKey = activeConfigManager.readKey(key)
    except Exception as e:
      await ctx.send(f'```{e}```')
    else:
      await ctx.send(f'```{readKey}```')
  
  @commands.command(name='rateLimited', aliases=['rate', 'limited'], brief='Checks if the bot is currently rate-limited.', description='Checks if the bot\'s websocket is currently rate-limited')
  async def rateLimited(self, ctx):
    if self.bot.is_ws_ratelimited():
      await ctx.message.add_reaction('✅')
    else:
      await ctx.message.add_reaction('❌')
  
  @commands.group(invoke_without_command=True, case_insensitive=True, name='sudo', aliases=['doAs'], brief='Do something as somebody else.', description='Do a task as somebody else.')
  async def sudo(self, ctx):
    raise SubcommandNotFound()
  
  @sudo.command(name='message', aliases=['bot'], brief='Send a message as the bot.', description='Send a message as the bot in any channel that you want.', usage='<Channel> <Message>')
  async def doMessage(self, ctx, channel: discord.TextChannel, *, text: str):
    channel = self.bot.get_channel(channel.id)
    await channel.send(text)
  
  @sudo.command(name='user', aliases=['superuser'], brief='Execute a command as another person.', description='Emulate sending a command as another user.', usage='<User> <Command>')
  async def doUser(self, ctx, user: typing.Union[discord.Member, discord.User], *, command: str):
    msg = copy.copy(ctx.message)
    msg.author = user
    msg.content = ctx.prefix + command
    newCtx = await self.bot.get_context(msg, cls=type(ctx))
    await self.bot.invoke(newCtx)

def setup(bot):
  bot.add_cog(dev(bot))

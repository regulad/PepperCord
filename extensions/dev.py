import time, copy, io, contextlib
from main import activeConfigManager, activeExtensionManager
from discord.ext import commands

class dev(commands.Cog, name='Development', description='Dev-only commands. Users cannot execute these commands.'):
  def __init__(self, bot):
    self.bot = bot
  
  async def cog_check(self, ctx):
    return await self.bot.is_owner(ctx.author)

  @commands.command(name='evaluateCode', aliases=['evalCode', 'validateCode', 'eval'], brief='Evaluate Python code.', description='Evaluate Python code using eval().', usage='<Python Code>')
  async def evalCode(self, ctx, *, code: str = ''):
    if code.startswith('```') and code.endswith('```'):
      code = code.strip('```')
    discordOut = io.StringIO()
    try:
      perfBefore = copy.deepcopy(time.perf_counter())
      with contextlib.redirect_stdout(discordOut):
        eval(code)
    except Exception as e:
      await ctx.send(f'{e.__class__.__name__} caused the code to fail eval. See: ```{e}```')
    else:
      await ctx.send(f'Code ran successfully.')
    perfAfter = copy.deepcopy(time.perf_counter())
    totalTime = perfAfter - perfBefore
    await ctx.send(f'Total time: {totalTime}s\nConsole output: ```{discordOut.getvalue()}```')
  
  @commands.group(invoke_without_command=True, case_insensitive=True, name='extension', aliases=['extensions','cog', 'cogs'], brief='Manages extensions.', description='Manages discord.ext extensions.')
  async def extension(self, ctx):
    await ctx.send('You must execute a valid command.')

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
    await ctx.send('You must execute a valid command.')
  
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
      await ctx.message.add_reaction('\N{check mark}')
    else:
      await ctx.message.add_reaction('\N{cross mark}')

def setup(bot):
  bot.add_cog(dev(bot))

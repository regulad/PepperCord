import time, copy, io, contextlib
from main import activeConfigManager, activeExtensionManager
from discord.ext import commands

class dev(commands.Cog, name='Development', description='Dev-only commands. Users cannot execute these commands.'):
  def __init__(self, bot):
    self.bot = bot
  
  async def cog_check(self, ctx):
    return await self.bot.is_owner(ctx.author)

  @commands.command(name='evaluateCode', aliases=['evalCode', 'validateCode', 'eval'], description='Evaluate Python code.', usage='<Python Code>')
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
  
  @commands.group(invoke_without_command=True, case_insensitive=True, name='extension', aliases=['extensions','cog', 'cogs'], description='Manages extensions.')
  async def extension(self, ctx):
    await ctx.send('You must execute a valid command.')

  @extension.command(name='list', description='Lists loaded extensions')
  async def listExtensions(self, ctx):
    await ctx.send(activeExtensionManager.listExtensions())

  @extension.command(name='load', description='Loads extension or directory of extensions', usage='[Path]')
  async def loadExtension(self, ctx, *, extension: str = ''):
    try:
      await ctx.send(activeExtensionManager.loadExtension(extension))
    except Exception as e:
      await ctx.send(f'Failed to load extension: ```{e}```')
  
  @extension.command(name='unload', description='Loads extension or directory of extensions', usage='[Path]')
  async def unloadExtension(self, ctx, *, extension: str = ''):
    try:
      await ctx.send(activeExtensionManager.unloadExtension(extension))
    except Exception as e:
      await ctx.send(f'Failed to unload extension: ```{e}```')
  
  @extension.command(name='reload', description='Reloads extension or directory of extensions', usage='[Path]')
  async def reloadExtension(self, ctx, *, extension: str = ''):
    try:
      await ctx.send(activeExtensionManager.reloadExtension(extension))
    except Exception as e:
      await ctx.send(f'Failed to reload extension: ```{e}```')
  
  @commands.group(invoke_without_command=True, case_insensitive=True, name='config', aliases=['configuration', 'yaml'], description='Manages extensions.')
  async def config(self, ctx):
    await ctx.send('You must execute a valid command.')
  
  @config.command(name='readKey', aliases=['read'], description='Reads YAML key present in the config.')
  async def readKey(self, ctx, key: str = ''):
    try:
      readKey = activeConfigManager.readKey(key)
    except Exception as e:
      await ctx.send(f'```{e}```')
    else:
      await ctx.send(f'```{readKey}```')

def setup(bot):
  bot.add_cog(dev(bot))

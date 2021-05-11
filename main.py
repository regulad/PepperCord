import copy
from bot import bot, activeConfigManager
from tools.managers import ExtensionManager
from art import tprint

activeExtensionManager = ExtensionManager(bot)

@bot.event
async def on_ready():
  tprint('PepperCord', font = 'xsans')
  print(f'Logged in as {bot.user.name}#{bot.user.discriminator} ({bot.user.id})')

if __name__ == '__main__':
  bot.load_extension('jishaku')
  extensionLoader = activeExtensionManager.loadExtension()
  if extensionLoader and (len(extensionLoader) > 0):
    print(f'{extensionLoader} failed to load.')
  print(activeExtensionManager.listExtensions())
  bot.run(activeConfigManager.readKey('discord.api.token'))

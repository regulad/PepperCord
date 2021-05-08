import copy
from bot import bot, activeConfigManager
from tools.managers import extensionManager
from art import tprint

activeExtensionManager = extensionManager(bot)

@bot.event
async def on_ready():
  tprint('PepperCord', font = 'xsans')
  print(f'Logged in as {bot.user.name}#{bot.user.discriminator} ({bot.user.id})')

if __name__ == '__main__':
  extensionLoader = copy.deepcopy(activeExtensionManager.loadExtension())
  if len(extensionLoader) > 0:
    print(f'{extensionLoader} failed to load.')
  print(activeExtensionManager.listExtensions())
  bot.run(activeConfigManager.readKey('discord.api.token'))

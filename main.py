import os
from extensionManager import extensionManager
from art import tprint
from bot import bot

extensionPath = 'extensions/'
activeExtensionManager = extensionManager(extensionPath)

@bot.event
async def on_ready():
  tprint('PepperCord', font = 'xsans')
  print(f'Logged in as {bot.user.name} ({bot.user.id})')

if __name__ == '__main__':
  print(activeExtensionManager.loadExtension())
  print(activeExtensionManager.listExtensions())
  bot.run(os.environ['BOT_TOKEN'])

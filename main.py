import os
from discord.ext import commands
from discord_slash import SlashCommand
from art import tprint

bot = commands.Bot(command_prefix='?')
slash = SlashCommand(bot, override_type = True, sync_commands = True)
loadedExtensions = []

# Adds extension
def addExtension(entry):
  try:
    bot.load_extension("extensions.{}".format(entry))
    loadedExtensions.append(entry)
  except Exception as e:
    print(e)
    return False
  else:
    print(f'Succesfully loaded extension {entry}')
    return True
# Load all extensions initially
def loadExtensions():
  print('Loading all present extensions...')
  for entry in os.listdir('extensions'):
    if entry.endswith('.py') and os.path.isfile('extensions/{}'.format(entry)):
      addExtension(entry[:-3])
# Splash
def splash():
  tprint('PepperCord', font = 'univers')
  print(f'Logged in as {bot.user.name} ({bot.user.id})')
  
# When bot is ready
@bot.event
async def on_ready():
  splash()
  loadExtensions()
  print(f'Loaded extensions: {str(loadedExtensions)}')

# Connect to Discord using token in Environment variables
bot.run(os.environ['BOT_TOKEN'])

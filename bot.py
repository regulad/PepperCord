from tools.managers import configManager
from discord.ext import commands

activeConfigManager = configManager()
bot = commands.Bot(command_prefix=activeConfigManager.readKey('discord.prefix'), case_insensitive=True)

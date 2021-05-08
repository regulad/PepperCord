from tools.managers import configManager
from discord import Colour
from discord.ext import commands
from pretty_help import PrettyHelp

activeConfigManager = configManager()
bot = commands.Bot(command_prefix=activeConfigManager.readKey('discord.prefix'), case_insensitive=True)
bot.help_command = PrettyHelp(color=Colour.orange())

from tools.managers.configManager import configManager
import discord
from discord.ext import commands
from pretty_help import PrettyHelp

activeConfigManager = configManager()
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix=activeConfigManager.readKey('discord.prefix'), case_insensitive=True, intents=intents)
bot.help_command = PrettyHelp(color=discord.Colour.orange())

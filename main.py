"""
Regulad's PepperCord
https://github.com/regulad/PepperCord
"""

import json
import os

import discord
import jsonschema
import motor.motor_asyncio
import yaml
from discord.ext import commands
from pretty_help import PrettyHelp

from utils import bot, database


config = yaml.load(open("config/config.yml"), Loader=yaml.FullLoader)
config_schema = json.load(open("resources/config.json"))

# Make sure the config is valid.
jsonschema.validate(
    instance=config,
    schema=config_schema,
)

# Configure the database
db_client = motor.motor_asyncio.AsyncIOMotorClient(config["db"]["uri"])
db = db_client[config["db"]["name"]]


async def get_prefix(bot, message):
    document = await database.Document.get_document(bot.database["guild"], {"_id": message.guild.id})
    default_prefix = bot.config["discord"]["commands"]["prefix"]
    if message.guild is None:
        return commands.when_mentioned_or(f"{default_prefix} ", default_prefix)(bot, message)
    else:
        guild_prefix = document.setdefault("prefix", default_prefix)
        return commands.when_mentioned_or(f"{guild_prefix} ", guild_prefix)(bot, message)


intents = discord.Intents.default()
intents.members = True
intents.presences = True

bot = bot.CustomBot(
    command_prefix=get_prefix,
    case_insensitive=True,
    intents=intents,
    description="https://github.com/regulad/PepperCord",
    help_command=PrettyHelp(color=discord.Colour.orange()),
    database=db,
    config=config,
)

if __name__ == "__main__":
    for file in os.listdir("extensions/"):
        if file.endswith(".py"):
            full_path = "extensions/" + file
            try:
                bot.load_extension(os.path.splitext(full_path)[0].replace("/", "."))
            except Exception as e:
                print(f"Could not load {full_path}: {e}, continuing recursively")
            else:
                print(f"Loaded {full_path}")
    bot.run(config["discord"]["api"]["token"])

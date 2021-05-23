"""
Regulad's PepperCord
https://github.com/regulad/PepperCord
"""

import json
import os
import pathlib
import shutil

import discord
import jsonschema
import motor.motor_asyncio
import yaml
from discord.ext import commands
from pretty_help import PrettyHelp

from utils import bot, database

# Copy the example config file if no config file exists.
if not pathlib.Path("config/config.yml").exists():
    shutil.copyfile("resources/config.example.yml", "config/config.yml")

config = yaml.load(open("config/config.yml"), Loader=yaml.FullLoader)
config_schema = json.load(open("resources/config.json"))

# Make sure the config is valid.
jsonschema.validate(
    instance=config,
    schema=config_schema,
)

# Configure the database
database_client = motor.motor_asyncio.AsyncIOMotorClient(config["db"]["uri"])
db = database_client[config["db"]["name"]]
col = db[config["db"]["col"]]


async def get_prefix(bot, message):
    document = database.Document(bot.collection, {"_id": message.guild.id})
    default_prefix = bot.config["discord"]["commands"]["prefix"]
    if message.guild is None:
        return commands.when_mentioned_or(default_prefix)(bot, message)
    else:
        guild_prefix = document.set_default("prefix", "?")
        return commands.when_mentioned_or(f"{guild_prefix} ", guild_prefix)(bot, message)


bot = bot.CustomBot(
    command_prefix=get_prefix,
    case_insensitive=True,
    intents=discord.Intents.all(),
    description="https://github.com/regulad/PepperCord",
    help_command=PrettyHelp(color=discord.Colour.orange()),
    collection=col,
    config=config,
)

if __name__ == "__main__":
    for file in os.listdir("extensions/"):
        if file.endswith(".py"):
            full_path = "extensions/" + file
            try:
                bot.load_extension(full_path.strip(".py").replace("/", "."))
            except Exception as e:
                print(f"Could not load {full_path}: {e}, continuing recursively")
            else:
                print(f"Loaded {full_path}")
    bot.run(config["discord"]["api"]["token"])

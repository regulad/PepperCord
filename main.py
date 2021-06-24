"""
Regulad's PepperCord
https://github.com/regulad/PepperCord
"""

import os
import logging

import discord
import motor.motor_asyncio
from pretty_help import PrettyHelp

from utils import bots

# Creates the config directory if it doesn't exist. Used by things like TTS.
if not os.path.exists("config/"):
    os.mkdir("config/")

# Configure the database
db_client = motor.motor_asyncio.AsyncIOMotorClient(os.environ.get("PEPPERCORD_URI", "mongodb://mongo"))
db = db_client[os.environ.get("PEPPERCORD_DB_NAME", "peppercord")]

# Configure Sharding
shards = int(os.environ.get("PEPPERCORD_SHARDS", "0"))
if shards > 0:
    bot_class = bots.CustomAutoShardedBot
elif shards == -1:
    bot_class = bots.CustomAutoShardedBot
    shards = None
else:
    bot_class = bots.CustomBot
    shards = None

# Configure bot
bot = bot_class(
    command_prefix=os.environ.get("PEPPERCORD_PREFIX", "?"),
    case_insensitive=True,
    help_command=PrettyHelp(color=discord.Colour.orange()),
    intents=discord.Intents.all(),  # TODO: Add ability to selectively disable intents via environment variables.
    database=db,
    config=os.environ,
    shard_count=shards,
)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(name)s: %(message)s")
    
    for file in os.listdir("extensions/"):
        if file.endswith(".py"):
            full_path = "extensions/" + file
            bot.load_extension(os.path.splitext(full_path)[0].replace("/", "."))

    bot.run(bot.config.get("PEPPERCORD_TOKEN"))

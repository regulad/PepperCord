"""
Regulad's PepperCord
https://github.com/regulad/PepperCord
"""

from typing import Optional
import os

import discord
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pretty_help import PrettyHelp

from utils import bots, help

# Creates the config directory if it doesn't exist. Used by things like TTS.
if not os.path.exists("config/"):
    os.mkdir("config/")

# Configure the database
db_client: AsyncIOMotorClient = AsyncIOMotorClient(os.environ.get("PEPPERCORD_URI", "mongodb://mongo"))
db: AsyncIOMotorDatabase = db_client[os.environ.get("PEPPERCORD_DB_NAME", "peppercord")]

# Configure Sharding
shards: Optional[int] = int(os.environ.get("PEPPERCORD_SHARDS", "0"))
if shards > 0:
    bot_class = bots.CustomAutoShardedBot
elif shards == -1:
    bot_class = bots.CustomAutoShardedBot
    shards = None
else:
    bot_class = bots.CustomBot
    shards = None

# Configure bot
bot: bots.BOT_TYPES = bot_class(
    command_prefix=os.environ.get("PEPPERCORD_PREFIX", "?"),
    case_insensitive=True,
    help_command=PrettyHelp(color=discord.Colour.orange(), menu=help.BetterMenu()),
    intents=discord.Intents.all(),
    database=db,
    config=os.environ,
    shard_count=shards,
)

if __name__ == "__main__":
    for file in os.listdir("extensions/"):
        if file.endswith(".py"):
            full_path: str = "extensions/" + file
            bot.load_extension(os.path.splitext(full_path)[0].replace("/", "."))

    bot.run(bot.config.get("PEPPERCORD_TOKEN"))

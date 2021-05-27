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
from pretty_help import PrettyHelp

from utils import bot

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

# Configure Intents
intents = discord.Intents.default()
intents.members = True
intents.presences = True

# Configure Sharding
shards = config["discord"]["api"].setdefault("shards", 0)
if shards > 0:
    bot_class = bot.CustomAutoShardedBot
elif shards == -1:
    bot_class = bot.CustomAutoShardedBot
    shards = None
else:
    bot_class = bot.CustomBot
    shards = None

# Configure bot
bot_instance = bot_class(
    command_prefix=config["discord"]["commands"]["prefix"],
    case_insensitive=True,
    intents=intents,
    description="https://github.com/regulad/PepperCord",
    help_command=PrettyHelp(color=discord.Colour.orange()),
    database=db,
    config=config,
    shard_count=shards,
)

if __name__ == "__main__":
    for file in os.listdir("extensions/"):
        if file.endswith(".py"):
            full_path = "extensions/" + file
            try:
                bot_instance.load_extension(os.path.splitext(full_path)[0].replace("/", "."))
            except Exception as e:
                print(f"Could not load {full_path}: {e}, continuing recursively")
            else:
                print(f"Loaded {full_path}")
    bot_instance.run(bot_instance.config["discord"]["api"]["token"])

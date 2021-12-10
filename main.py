"""
Regulad's PepperCord
https://github.com/regulad/PepperCord
"""

import asyncio
import logging
import os
from typing import Optional, List, Tuple, Type

import discord
import art
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pretty_help import PrettyHelp

from utils import bots, help


if __name__ == "__main__":
    if not os.path.exists("config/"):
        os.mkdir("config/")

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s:%(levelname)s:%(name)s: %(message)s"
    )

    # Configure the database
    db_client: AsyncIOMotorClient = AsyncIOMotorClient(
        os.environ.get("PEPPERCORD_URI", "mongodb://mongo")
    )
    db: AsyncIOMotorDatabase = db_client[
        os.environ.get("PEPPERCORD_DB_NAME", "peppercord")
    ]

    # Configure Sharding
    bot_class: Type[bots.BOT_TYPES]
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
        help_command=PrettyHelp(
            color=discord.Colour.orange(),
            menu=help.BetterMenu(),
            paginator=help.BetterPaginator(True, color=discord.Colour.orange()),
        ),
        intents=discord.Intents.all(),
        database=db,
        config=os.environ,
        shard_count=shards,
        slash_commands=True,
        message_commands=False,
        slash_command_guilds=([int(testguild) for testguild in os.environ["PEPPERCORD_TESTGUILDS"].split(", ")] if os.environ.get("PEPPERCORD_TESTGUILDS") is not None else None)
    )

    directories: List[str] = [entry[0] for entry in os.walk("extensions")]

    if os.name == "nt":
        directories: List[str] = [entry.replace("\\", "/") for entry in directories]

    for directory in directories:
        if (directory == "extensions/debug" or directory == "extensions\\debug") and not bool(os.environ.get("PEPPERCORD_DEBUG")):
            continue
        for file in os.listdir(f"{directory}/"):
            if file.endswith(".py"):
                full_path: str = f"{directory}/" + file
                bot.load_extension(os.path.splitext(full_path)[0].replace("/", "."))

    logging.info("Ready.")
    logging.info(f"\n{art.text2art('PepperCord', font='rnd-large')}")

    bot.run(os.environ.get("PEPPERCORD_TOKEN"))

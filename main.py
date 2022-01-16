"""
Regulad's PepperCord
https://github.com/regulad/PepperCord
"""

import logging
import os
from typing import Optional, List, Type, MutableMapping

import art
import discord
from dislog import DiscordWebhookHandler
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pretty_help import PrettyHelp

from utils import bots, help

default_log_level: int = logging.INFO

if __name__ == "__main__":
    if os.path.exists(".env"):
        load_dotenv()

    config_source: MutableMapping = os.environ

    debug: bool = config_source.get("PEPPERCORD_DEBUG") is not None

    logging.basicConfig(
        level=logging.DEBUG if debug else default_log_level, format="%(asctime)s:%(levelname)s:%(name)s: %(message)s"
    )

    maybe_webhook: Optional[str] = config_source.get("PEPPERCORD_WEBHOOK")

    if maybe_webhook is not None:
        logging.root.addHandler(DiscordWebhookHandler(maybe_webhook, level=default_log_level))

    if not os.path.exists("config/"):
        os.mkdir("config/")

    logging.info("Configuring database connection...")
    # Configure the database
    db_client: AsyncIOMotorClient = AsyncIOMotorClient(
        config_source.get("PEPPERCORD_URI", "mongodb://mongo")
    )
    db: AsyncIOMotorDatabase = db_client[
        config_source.get("PEPPERCORD_DB_NAME", "peppercord")
    ]
    logging.info("Done.")

    logging.info("Configuring bot...")
    # Configure Sharding
    bot_class: Type[bots.BOT_TYPES]
    shards: Optional[int] = int(config_source.get("PEPPERCORD_SHARDS", "0"))
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
        command_prefix=config_source.get("PEPPERCORD_PREFIX", "?"),
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
        message_commands=debug,
        slash_command_guilds=(
            [
                int(testguild)
                for testguild in config_source["PEPPERCORD_TESTGUILDS"].split(", ")
            ]
            if config_source.get("PEPPERCORD_TESTGUILDS") is not None
            else None
        ),
    )
    logging.info("Done.")

    logging.info("Loading extensions...")
    directories: List[str] = [entry[0] for entry in os.walk("extensions")]
    if os.name == "nt":
        directories: List[str] = [entry.replace("\\", "/") for entry in directories]
    for directory in directories:
        if directory == "extensions/disabled" or directory == "extensions\\disabled":
            continue
        for file in os.listdir(f"{directory}/"):
            if file.endswith(".py"):
                full_path: str = f"{directory}/" + file
                bot.load_extension(os.path.splitext(full_path)[0].replace("/", "."))
    if debug:
        bot.load_extension("jishaku")

    logging.info("Done.")

    logging.info("Ready.")
    logging.info(f"\n{art.text2art('PepperCord', font='rnd-large')}")

    bot.run(config_source.get("PEPPERCORD_TOKEN"))

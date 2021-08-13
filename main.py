"""
Regulad's PepperCord
https://github.com/regulad/PepperCord
"""

import asyncio
import logging
import os
from typing import Optional, List, Tuple, Type

import discord
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pretty_help import PrettyHelp

from utils import bots, help


def add_bot(
        config_provider: bots.CONFIGURATION_PROVIDERS,
        *,
        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop(),
        key_prefix: str = "PEPPERCORD",
        **kwargs
) -> Tuple[bots.BOT_TYPES, asyncio.Task]:
    # Configure the database
    db_client: AsyncIOMotorClient = AsyncIOMotorClient(
        config_provider.get(f"{key_prefix.upper()}_URI", "mongodb://mongo")
    )
    db: AsyncIOMotorDatabase = db_client[config_provider.get("PEPPERCORD_DB_NAME", "peppercord")]

    # Configure Sharding
    bot_class: Type[bots.BOT_TYPES]
    shards: Optional[int] = int(config_provider.get(f"{key_prefix.upper()}_SHARDS", "0"))
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
        command_prefix=config_provider.get(f"{key_prefix.upper()}_PREFIX", "?"),
        case_insensitive=True,
        help_command=PrettyHelp(
            color=discord.Colour.orange(),
            menu=help.BetterMenu(),
            paginator=help.BetterPaginator(True, color=discord.Colour.orange()),
        ),
        intents=discord.Intents.all(),
        database=db,
        config=config_provider,
        shard_count=shards,
        loop=loop,
    )

    directories: List[str] = (
        config_provider.get(f"{key_prefix.upper()}_FOLDERS", "extensions")
            .lower()
            .strip()
            .split(", ")
    )
    if "core" not in directories:
        directories.append("core")

    for directory in directories:
        for file in os.listdir(f"{directory}/"):
            if file.endswith(".py"):
                full_path: str = f"{directory}/" + file
                bot.load_extension(os.path.splitext(full_path)[0].replace("/", "."))

    logging.info(f"Added a bot ({bot})")

    return bot, loop.create_task(bot.start(config_provider.get(f"{key_prefix.upper()}_TOKEN"), **kwargs))


if __name__ == "__main__":
    if not os.path.exists("config/"):
        os.mkdir("config/")

    loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s:%(levelname)s:%(name)s: %(message)s"
    )

    peppercord_instances: List[Tuple[bots.BOT_TYPES, asyncio.Task]] = [add_bot(os.environ, loop=loop)]
    # More can be added. For future use.

    try:
        logging.info("Running...")

        loop.run_forever()
    except KeyboardInterrupt:
        for bot, task in peppercord_instances:
            loop.run_until_complete(bot.close())
            task.cancel()
    except Exception:
        raise

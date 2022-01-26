"""
Regulad's PepperCord
https://github.com/regulad/PepperCord
"""

import logging
import os
import traceback
from typing import Optional, Type, MutableMapping, Any

import art
import discord
from dislog import DiscordWebhookHandler
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pretty_help import PrettyHelp
from replutil import ReplKeepAlive, is_repl

from utils import bots, help, misc

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
        slash_commands=os.environ.get("PEPPERCORD_SLASH_COMMANDS") is None,
        message_commands=os.environ.get("PEPPERCORD_MESSAGE_COMMANDS") is None or debug,
        slash_command_guilds=(
            [
                int(testguild)
                for testguild in config_source["PEPPERCORD_TESTGUILDS"].split(",")
            ]
            if config_source.get("PEPPERCORD_TESTGUILDS") is not None
            else None
        ),
    )

    client_logger: logging.Logger = logging.getLogger(discord.client.__name__)


    async def on_error(event_method: str, *args: Any, **kwargs: Any) -> None:
        client_logger.critical(f"Ignoring exception in {event_method}")
        client_logger.critical(traceback.format_exc())


    logging.info("Replacing error handler...")

    bot.on_error = on_error

    logging.info("Done.")

    logging.info("Loading extensions...")
    for extension in misc.get_python_modules("extensions"):
        bot.load_extension(extension)
    if debug:
        bot.load_extension("jishaku")

    logging.info("Done.")

    logging.info("Ready.")
    logging.info(f"\n{art.text2art('PepperCord', font='rnd-large')}")

    if is_repl() and config_source.get("PEPPERCORD_UPTIMEROBOT") is not None:
        with ReplKeepAlive(config_source["PEPPERCORD_UPTIMEROBOT"]):
            bot.run(config_source["PEPPERCORD_TOKEN"])
    else:
        bot.run(config_source["PEPPERCORD_TOKEN"])


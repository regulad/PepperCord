"""
Regulad's PepperCord
https://github.com/regulad/PepperCord
"""

import locale
import logging
import os
from asyncio import run, gather, AbstractEventLoop, get_event_loop
from typing import Optional, Type, MutableMapping, Coroutine

import art
import discord
from discord import Object, Game, Forbidden
from dislog import DiscordWebhookHandler
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pretty_help import PrettyHelp

from utils import bots, misc
from utils.help import BetterMenu

DEFUALT_LOG_LEVEL: int = logging.INFO

locale.setlocale(locale.LC_ALL, "")


async def async_main() -> None:
    loop: AbstractEventLoop = get_event_loop()

    if os.path.exists(".env"):
        load_dotenv()

    config_source: MutableMapping = os.environ

    debug: bool = config_source.get("PEPPERCORD_DEBUG") is not None

    logging.basicConfig(
        level=logging.DEBUG if debug else DEFUALT_LOG_LEVEL,
        format="%(asctime)s:%(levelname)s:%(name)s: %(message)s",
    )

    maybe_webhook: Optional[str] = config_source.get("PEPPERCORD_WEBHOOK")

    if maybe_webhook is not None:
        logging.root.addHandler(
            DiscordWebhookHandler(maybe_webhook, level=DEFUALT_LOG_LEVEL)
        )

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
    bot_class: Type[bots.BOT_TYPES] = bots.CustomBot
    # Configure bot
    bot: bots.BOT_TYPES = bot_class(
        command_prefix=config_source.get("PEPPERCORD_PREFIX", "?"),
        case_insensitive=True,
        help_command=PrettyHelp(
            color=discord.Colour.orange(),
            menu=BetterMenu(),
        ),
        database=db,
        config=os.environ,
        activity=Game("PepperCord"),
    )

    logging.info("Loading extensions...")
    extension_coros: list[Coroutine] = [
        bot.load_extension(ext) for ext in misc.get_python_modules("extensions")
    ]

    await gather(*extension_coros)
    logging.info("Done.")

    logging.info("Ready.")
    logging.info(f"\n{art.text2art('PepperCord', font='rnd-large')}")

    async with bot:
        await bot.start(config_source["PEPPERCORD_TOKEN"])


if __name__ == "__main__":
    run(async_main())

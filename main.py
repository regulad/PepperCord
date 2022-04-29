"""
Regulad's PepperCord
https://github.com/regulad/PepperCord
"""

import logging
import os
import traceback
from asyncio import run, gather, AbstractEventLoop, get_event_loop, Task
from typing import Optional, Type, MutableMapping, Any, Coroutine

import art
import discord
from discord import Object, Game
from dislog import DiscordWebhookHandler
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pretty_help import PrettyHelp

from utils import bots, misc
from utils.help import BetterMenu

default_log_level: int = logging.INFO


async def async_main() -> None:
    loop: AbstractEventLoop = get_event_loop()

    if os.path.exists(".env"):
        load_dotenv()

    config_source: MutableMapping = os.environ

    debug: bool = config_source.get("PEPPERCORD_DEBUG") is not None

    logging.basicConfig(
        level=logging.DEBUG if debug else default_log_level,
        format="%(asctime)s:%(levelname)s:%(name)s: %(message)s",
    )

    maybe_webhook: Optional[str] = config_source.get("PEPPERCORD_WEBHOOK")

    if maybe_webhook is not None:
        logging.root.addHandler(
            DiscordWebhookHandler(maybe_webhook, level=default_log_level)
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
            menu=BetterMenu(),
        ),
        intents=discord.Intents.all(),
        database=db,
        config=os.environ,
        shard_count=shards,
        loop=loop,
        activity=Game("PepperCord"),
    )

    client_logger: logging.Logger = logging.getLogger(discord.client.__name__)

    async def on_error(event_method: str, *args: Any, **kwargs: Any) -> None:
        client_logger.critical(f"Ignoring exception in {event_method}")
        client_logger.critical(traceback.format_exc())

    logging.info("Replacing error handler...")

    bot.on_error = on_error

    logging.info("Done.")

    logging.info("Loading extensions...")
    extension_coros: list[Coroutine] = [
        bot.load_extension(ext) for ext in misc.get_python_modules("extensions")
    ]
    extension_coros.append(bot.load_extension("jishaku"))

    tasks: list[Task] = [loop.create_task(coro) for coro in extension_coros]

    await gather(*tasks)
    logging.info("Done.")

    logging.info("Ready.")
    logging.info(f"\n{art.text2art('PepperCord', font='rnd-large')}")

    async with bot:

        @bot.listen("on_ready")
        async def setup_commands() -> None:
            if bot.config.get("PEPPERCORD_TESTGUILDS"):
                testguilds: list[Object] = [
                    Object(id=int(testguild))
                    for testguild in bot.config["PEPPERCORD_TESTGUILDS"].split(",")
                ]
                for guild in testguilds:
                    bot.tree.copy_global_to(guild=guild)
                bot.tree.clear_commands(guild=None)
                await gather(*[bot.tree.sync(guild=guild) for guild in testguilds])
                await bot.tree.sync()
                logging.info("Finished syncing guild commands.")
            elif bot.config.get("PEPPERCORD_SLASH_COMMANDS") is None:
                await bot.tree.sync()
                for guild in bot.guilds:  # THIS is the reason this cannot be a setup hook. It must be after the bot is ready, and the guilds are populated.
                    await bot.tree.sync(guild=guild)
                logging.info("Synced global commands.")

        await bot.start(config_source["PEPPERCORD_TOKEN"])


if __name__ == "__main__":
    run(async_main())

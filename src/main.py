"""
Regulad's PepperCord
https://github.com/regulad/PepperCord
"""

import locale
import logging
import os
from asyncio import run, gather, AbstractEventLoop, get_event_loop
from typing import Sequence

from discord import Intents, Object, Game, Forbidden
from dotenv import load_dotenv
from pymongo import AsyncMongoClient
from redis.asyncio import Redis, ConnectionPool

from utils import misc
from utils.bots.bot import CustomBot
from utils.database import PCInternalDocument
from utils.version import get_version

DEFAULT_LOG_LEVEL: int = logging.INFO

locale.setlocale(locale.LC_ALL, "")

logger: logging.Logger = logging.getLogger(__name__)
logging.getLogger("discord").setLevel(
    logging.WARNING
)  # We aren't debugging discord.py; just our program
logging.getLogger("pymongo").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)


async def async_main() -> None:
    event_loop: AbstractEventLoop = get_event_loop()

    if os.path.exists(".env"):
        load_dotenv()

    config_source = os.environ

    debug: bool = config_source.get("PEPPERCORD_DEBUG") is not None

    logging.basicConfig(
        level=logging.DEBUG if debug else DEFAULT_LOG_LEVEL,
        format="%(asctime)s:%(levelname)s:%(name)s: %(message)s",
    )

    logger.info("Configuring database connection...")

    cdb_uri = config_source["PEPPERCORD_CACHEDB_URI"]
    cdb_pool = ConnectionPool.from_url(cdb_uri)
    cdb = Redis(connection_pool=cdb_pool, protocol=3, auto_close_connection_pool=True)

    ddb_uri = config_source["PEPPERCORD_DOCUMENTDB_URI"]
    ddb_client = AsyncMongoClient(ddb_uri, document_class=PCInternalDocument)

    # Configure the database
    async with ddb_client, cdb:
        # DB context manager: enables auto-close
        ddb = ddb_client[config_source.get("PEPPERCORD_DB_NAME", "peppercord")]
        logger.info("Done.")

        # Configure bot
        logger.info("Configuring bot...")
        # Peppercord used to support running without all intents, but I no longer want to maintain two versions of the bot (one with privileged intents, and one without)
        bot = CustomBot(
            # Explicitly handled in type
            ddb=ddb,
            cdb=cdb,
            config=config_source,
            # Implicitly handled in type
            case_insensitive=True,
            intents=Intents.all(),
            loop=event_loop,
            activity=Game("Starting PepperCord..."),
        )

        async def load_with_safety(ext: str) -> None:
            try:
                await bot.load_extension(ext.strip())
            except Exception as e:
                logger.exception(f"Failed to load extension {ext}", exc_info=e)
                raise e
            else:
                logger.debug(f"Loaded extension {ext}")

        logger.info("Loading extensions...")
        extension_coros = [
            load_with_safety(ext) for ext in misc.get_python_modules("extensions")
        ]
        extension_coros.append(load_with_safety("jishaku"))

        await gather(*extension_coros)
        logger.info(
            f"Done loading {len(bot.extensions)} extensions with {len(bot.commands)} root commands."
        )

        # ready
        version, commit = get_version()
        logger.info(f"Ready. Started PepperCord version {version}@{commit}")

        async with bot:

            @bot.listen("on_ready")
            async def setup_commands() -> None:
                if bot.config.get("PEPPERCORD_TESTGUILDS"):
                    testguilds: Sequence[Object] = [
                        Object(id=int(testguild))
                        for testguild in bot.config["PEPPERCORD_TESTGUILDS"].split(",")
                    ]
                    for guild in testguilds:
                        bot.tree.copy_global_to(guild=guild)
                    bot.tree.clear_commands(guild=None)
                    await gather(*[bot.tree.sync(guild=guild) for guild in testguilds])
                    await bot.tree.sync()
                    logger.info("Finished syncing guild commands.")
                else:
                    await bot.tree.sync()
                    if debug:
                        try:
                            await gather(
                                *[bot.tree.sync(guild=guild) for guild in bot.guilds]
                            )
                        except Forbidden:
                            pass
                    logger.info("Synced global commands.")

            @bot.listen("on_ready")
            async def setup_emojis() -> None:
                if bot.home_server is not None:
                    await gather(
                        *[
                            bot.fetch_or_upload_custom_emoji(emoji)
                            for emoji in os.listdir(
                                os.path.join(os.getcwd(), "resources", "emojis")
                            )
                        ]
                    )
                    logger.info("Finished uploading emojis.")

            await bot.wait_for_dispatch("startup")
            await bot.start(config_source["PEPPERCORD_TOKEN"])


if __name__ == "__main__":
    run(async_main())

"""
Regulad's PepperCord
https://github.com/regulad/PepperCord
"""

import locale
import logging
import os
from asyncio import run, gather, AbstractEventLoop, get_event_loop
from typing import Optional, Type, MutableMapping, Coroutine, TYPE_CHECKING

import art
import discord
from discord import Object, Game, Forbidden
from dislog import DiscordWebhookHandler
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pretty_help import PrettyHelp

from utils import bots, misc
from utils.help import BetterMenu

DEFAULT_LOG_LEVEL: int = logging.INFO

locale.setlocale(locale.LC_ALL, "")


logger: logging.Logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase


async def async_main() -> None:
    loop: AbstractEventLoop = get_event_loop()

    if os.path.exists(".env"):
        load_dotenv()

    config_source: MutableMapping = os.environ

    debug: bool = config_source.get("PEPPERCORD_DEBUG") is not None

    logging.basicConfig(
        level=logging.DEBUG if debug else DEFAULT_LOG_LEVEL,
        format="%(asctime)s:%(levelname)s:%(name)s: %(message)s",
    )

    maybe_webhook: Optional[str] = config_source.get("PEPPERCORD_WEBHOOK")

    if maybe_webhook is not None:
        logging.root.addHandler(
            DiscordWebhookHandler(maybe_webhook, level=DEFAULT_LOG_LEVEL)
        )

    if not os.path.exists("config/"):
        os.mkdir("config/")

    logger.info("Configuring database connection...")
    # Configure the database
    db_client: AsyncIOMotorClient = AsyncIOMotorClient(
        config_source.get("PEPPERCORD_URI", "mongodb://mongo")
    )
    db: "AsyncIOMotorDatabase" = db_client[
        config_source.get("PEPPERCORD_DB_NAME", "peppercord")
    ]
    logger.info("Done.")

    logger.info("Configuring bot...")
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
    # Build intents
    intents: discord.Intents = discord.Intents.default()
    intents.presences = (config_source.get("PEPPERCORD_PRESENCES") is not None) or debug
    intents.members = (config_source.get("PEPPERCORD_MEMBERS") is not None) or debug
    intents.message_content = (config_source.get("PEPPERCORD_MESSAGE_CONTENT") is not None) or debug

    if intents.presences:
        logger.info("Presences are enabled.")
    else:
        logger.warning("Presences are disabled.")

    if intents.members:
        logger.info("Members are enabled.")
    else:
        logger.warning("Members are disabled.")

    if intents.message_content:
        logger.info("Message content is enabled.")
    else:
        logger.warning("Message content is disabled.")

    # Configure bot
    bot: bots.BOT_TYPES = bot_class(
        command_prefix=config_source.get("PEPPERCORD_PREFIX", "?"),
        case_insensitive=True,
        help_command=PrettyHelp(
            color=discord.Colour.orange(),
            menu=BetterMenu(),
        ),
        intents=intents,
        database=db,
        config=os.environ,
        shard_count=shards,
        loop=loop,
        activity=Game("Starting PepperCord..."),
    )

    logger.info("Loading extensions...")
    extension_coros: list[Coroutine] = [
        bot.load_extension(ext) for ext in misc.get_python_modules("extensions")
    ]
    extension_coros.append(bot.load_extension("jishaku"))

    await gather(*extension_coros)
    logger.info("Done.")

    logger.info("Ready.")
    logger.info(f"\n{art.text2art('PepperCord', font='rnd-large')}")

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
                logger.info("Finished syncing guild commands.")
            elif bot.config.get("PEPPERCORD_SLASH_COMMANDS") is None:
                await bot.tree.sync()
                if debug:
                    try:
                        await gather(*[bot.tree.sync(guild=guild) for guild in bot.guilds])
                    except Forbidden:
                        pass
                logger.info("Synced global commands.")

        @bot.listen("on_ready")
        async def setup_emojis() -> None:
            if bot.home_server is not None:
                await gather(
                    *[
                        bot.fetch_or_upload_custom_emoji(emoji)
                        for emoji
                        in os.listdir(os.path.join(os.getcwd(), "resources", "emojis"))
                    ]
                )
                logger.info("Finished uploading emojis.")

        await bot.start(config_source["PEPPERCORD_TOKEN"])


if __name__ == "__main__":
    run(async_main())

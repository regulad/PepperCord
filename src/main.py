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
from discord.ext.commands import Command
from dislog import DiscordWebhookHandler
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pretty_help import PrettyHelp

from utils import bots, misc
from utils.help import BetterMenu
from utils.misc import name_of_func
from utils.version import get_version

DEFAULT_LOG_LEVEL: int = logging.INFO

locale.setlocale(locale.LC_ALL, "")

logger: logging.Logger = logging.getLogger(__name__)
logging.getLogger("discord").setLevel(
    logging.WARNING
)  # We aren't debugging discord.py; just our program

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
            DiscordWebhookHandler(
                maybe_webhook, level=DEFAULT_LOG_LEVEL, run_async=True
            )
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

    presence_ok = config_source.get("PEPPERCORD_PRESENCES") is not None
    member_ok = config_source.get("PEPPERCORD_MEMBERS") is not None
    content_ok = config_source.get("PEPPERCORD_MESSAGE_CONTENT") is not None

    intents.presences = presence_ok or debug
    intents.members = member_ok or debug
    intents.message_content = content_ok or debug

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

    async def load_with_safety(ext: str) -> None:
        try:
            await bot.load_extension(ext.strip())
        except Exception as e:
            logger.exception(f"Failed to load extension {ext}", exc_info=e)
        else:
            logger.debug(f"Loaded extension {ext}")

    logger.info("Loading extensions...")
    extension_coros: list[Coroutine] = [
        load_with_safety(ext) for ext in misc.get_python_modules("extensions")
    ]
    extension_coros.append(load_with_safety("jishaku"))

    await gather(*extension_coros)
    logger.info(
        f"Done loading {len(bot.extensions)} extensions with {len(bot.commands)} root commands."
    )

    # filter out unusable commands/cogs/extensions
    logger.info("Checking for unusable cogs...")
    prunable_command_count = 0
    pruned_command_count = 0
    for command in bot.walk_commands():
        should_remove = False
        for check in command.checks:
            match name_of_func(check):
                case "check_message_content_enabled":
                    should_remove = not intents.message_content
                case "check_members_enabled":
                    should_remove = not intents.members
                case "check_presences_enabled":
                    should_remove = not intents.presences

            if should_remove:
                break
        if should_remove:
            prunable_command_count += 1

            removed_command: Command
            if command.parent is not None:
                removed_command = command.parent.remove_command(command.name)
            else:
                removed_command = bot.remove_command(command.qualified_name)

            if removed_command is not None:
                pruned_command_count += 1
    logger.info(
        f"Pruned {pruned_command_count}/{prunable_command_count} unusable commands."
    )

    logger.info("Checking for empty cogs...")
    prunable_cog_count = 0
    pruned_cog_count = 0
    for cog in set(bot.cogs.values()):  # can't iterate over dict while removing items
        full_module_name = cog.__class__.__module__

        if not full_module_name.startswith("extensions."):
            continue  # this is a special cog, not a command cog (i.e. jishaku)

        cog_module_name_components = full_module_name.split(".")

        assert (
            len(cog_module_name_components) >= 3
        ), f"Cog module name {full_module_name} is too short!"

        if cog_module_name_components[1] not in [
            "features",
            "fun",
            "games",
            "external",
        ]:
            continue  # this is a special cog, not a command cog (i.e. a util)

        cog_has_registered_commands = False

        for command in cog.walk_commands():
            if command.parent is None and command in bot.commands:
                cog_has_registered_commands = True
                break

        if not cog_has_registered_commands:
            prunable_cog_count += 1
            removed_cog = await bot.remove_cog(cog.qualified_name)

            if removed_cog is not None:
                pruned_cog_count += 1
    logger.info(f"Pruned {pruned_cog_count}/{prunable_cog_count} empty cogs.")

    # ready
    version, commit = get_version()
    logger.info(
        f"Ready. Loading PepperCord version {version}@{commit}\n{art.text2art('PepperCord', font='rnd-large')}"
    )

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

import logging

from discord.ext import commands

from utils.bots import BOT_TYPES

logger: logging.Logger = logging.getLogger(__name__)


class Startup(commands.Cog):
    """Things to do on startup."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot

    @commands.Cog.listener("on_startup")
    async def list_extensions(self) -> None:
        is_debug_level = logger.getEffectiveLevel() <= logging.DEBUG
        extensions: str = "\n".join(
            f"    * {extension_name}" for extension_name in self.bot.extensions.keys()
        )
        logger.info(
            f"{len(self.bot.extensions)} extensions loaded"
            + (f":\n{extensions}" if is_debug_level else ".")
        )

    @commands.Cog.listener("on_startup")
    async def list_cogs(self) -> None:
        is_debug_level = logger.getEffectiveLevel() <= logging.DEBUG
        cogs: str = "\n".join(f"    * {cog_name}" for cog_name in self.bot.cogs.keys())
        logger.info(
            f"{len(self.bot.cogs)} cogs loaded"
            + (f":\n{cogs}" if is_debug_level else ".")
        )

    @commands.Cog.listener("on_ready")
    async def describe_user(self) -> None:
        logger.info(
            f"Logged in as {self.bot.user.display_name}#{self.bot.user.discriminator} ({self.bot.user.id}), "
            f"in {len(self.bot.guilds)} {'guild' if len(self.bot.guilds) == 1 else 'guilds'}"
        )


async def setup(bot: BOT_TYPES) -> None:
    await bot.add_cog(Startup(bot))

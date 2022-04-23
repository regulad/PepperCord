import logging

from discord.ext import commands

from utils.bots import BOT_TYPES


class Startup(commands.Cog):
    """Things to do on startup."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot

    @commands.Cog.listener("on_ready")
    async def list_extensions(self) -> None:
        extensions: str = "\n".join(
            f"    * {extension_name}" for extension_name in self.bot.extensions.keys()
        )
        # Why is this a thing in python?
        logging.info(f"{len(self.bot.extensions)} extensions loaded:\n" + extensions)

    @commands.Cog.listener("on_ready")
    async def describe_user(self) -> None:
        logging.info(
            f"Logged in as {self.bot.user.display_name}#{self.bot.user.discriminator} ({self.bot.user.id}), "
            f"in {len(self.bot.guilds)} {'guild' if len(self.bot.guilds) == 1 else 'guilds'}"
        )


async def setup(bot: BOT_TYPES) -> None:
    await bot.add_cog(Startup(bot))

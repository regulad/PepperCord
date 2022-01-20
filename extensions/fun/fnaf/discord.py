from typing import Optional

from discord.ext import commands

from utils import bots
from .abstract import *


# from .render import *


class FiveNightsAtFreddys(commands.Cog):
    """Play Five Night's At Freddys in Discord"""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot: bots.BOT_TYPES = bot

    @commands.command()
    async def fnaf(
            self,
            ctx: bots.CustomContext,
            freddy: Optional[int] = commands.Option(
                description="The difficulty for Freddy.",
                default=Animatronic.FREDDY.default_diff
            ),
            bonnie: Optional[int] = commands.Option(
                description="The difficulty for Bonnie.",
                default=Animatronic.BONNIE.default_diff
            ),
            chica: Optional[int] = commands.Option(
                description="The difficulty for Chica.",
                default=Animatronic.CHICA.default_diff
            ),
            foxy: Optional[int] = commands.Option(
                description="The difficulty for Foxy.",
                default=Animatronic.FOXY.default_diff
            ),
    ) -> None:
        pass


def setup(bot: bots.BOT_TYPES) -> None:
    bot.add_cog(FiveNightsAtFreddys(bot))


__all__: list[str] = [
    "FiveNightsAtFreddys",
    "setup"
]

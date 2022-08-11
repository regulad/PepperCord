from random import choice

from discord import Forbidden
from discord.ext.commands import (
    Cog,
    has_permissions,
    bot_has_permissions,
    command, guild_only,
)

from utils.bots import BOT_TYPES, CustomContext

TITLE: list[str] = [
    "Regal",
    "Sir",
    "Lord",
    "Duke",
    "Baron",
    "Count",
    "King",
    "Queen",
    "Prince",
    "Princess",
    "Dame",
    "Lady",
    "Madame",
    "Knight",
]

PLACES: list[str] = [
    "Scunderland",
    "Lancaster",
    "York",
    "Luxembourg",
    "Scotland",
    "France",
    "Germany",
    "England",
    "Ireland",
    "Wales",
]

SUFFIXES: list[str] = [
    "the Great",
    "the Wise",
    "the Bold",
    "XIV",
    "XVI",
    "XVII",
    "The Third",
    "The Fourth",
]

MAX_LEN: int = 32


def regalize(name: str) -> str:
    """Generate a regal name."""
    current: str = name

    title: str = choice(TITLE)
    maybe_title: str = title + " " + current
    if len(maybe_title) <= MAX_LEN:
        current = maybe_title

    suffix: str = choice(SUFFIXES)
    maybe_suffix: str = current + " " + suffix
    if len(maybe_suffix) <= MAX_LEN:
        current = maybe_suffix

    place: str = choice(PLACES)
    maybe_place: str = current + " of " + place
    if len(maybe_place) <= MAX_LEN:
        current = maybe_place

    return current


class Regal(Cog):
    """Get regal!"""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot

    @command(name="regal", aliases=["regalize"])
    @has_permissions(manage_nicknames=True)
    @bot_has_permissions(manage_nicknames=True)
    @guild_only()
    async def regalize(self, ctx: CustomContext) -> None:
        """Make all the members of the server regal."""
        async with ctx.typing(ephemeral=True):
            for member in ctx.guild.members:
                display_name_regal: str = regalize(member.display_name)
                try:
                    await member.edit(
                        nick=display_name_regal
                        if member.display_name != display_name_regal
                        else regalize(member.name)
                    )
                except Forbidden:
                    continue
            await ctx.send("Done!", ephemeral=True)


async def setup(bot: BOT_TYPES) -> None:
    """Load the cog."""
    await bot.add_cog(Regal(bot))

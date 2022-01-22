"""Checks for permissions."""

from discord.ext import commands

from utils.bots import CustomContext


class Blacklisted(commands.CheckFailure):
    """Raised when a context is blacklisted from executing."""

    pass


async def is_blacklisted(ctx: CustomContext) -> bool:
    """Checks if a context is blacklisted from executing commands."""

    return (
                   ctx.guild is not None and ctx["guild_document"].get("blacklisted", False)
           ) or ctx["author_document"].get("blacklisted", False)


__all__: list[str] = [
    "Blacklisted",
    "is_blacklisted",
]

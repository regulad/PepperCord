"""Checks for permissions."""

from typing import Any
from discord.ext import commands
from discord.ext.commands import Context

from utils.bots.context import CustomContext


class EBlacklisted(commands.CheckFailure):
    """Raised when a context is blacklisted from executing."""

    pass


async def is_blacklisted(ctx: Context[Any]) -> bool:
    """Checks if a context is blacklisted from executing commands."""
    if isinstance(ctx, CustomContext):
        return (
            ctx.guild is not None
            and bool(
                await ctx["guild_document"].safe_get("blacklisted", False)
            )  # TODO: NamedDict compliance
            or bool(
                await ctx["author_document"].safe_get("blacklisted", False)
            )  # TODO: NamedDict compliance
        )
    else:
        return False


__all__: list[str] = [
    "EBlacklisted",
    "is_blacklisted",
]

"""Checks for permissions."""

from typing import Optional

from discord.ext import commands

from utils.bots import CustomContext
from utils.permissions import Permission, get_permission


class Blacklisted(commands.CheckFailure):
    """Raised when a context is blacklisted from executing."""

    pass


class LowPrivilege(commands.CheckFailure):
    """Raised when permissions are missing."""

    def __init__(self, needs: Permission, has: Optional[Permission]):
        super().__init__(f"Needs {needs}, has {has}.")

    pass


async def is_blacklisted(ctx: CustomContext) -> bool:
    """Checks if a context is blacklisted from executing commands."""

    return (
        ctx.guild is not None and ctx["guild_document"].get("blacklisted", False)
    ) or ctx["author_document"].get("blacklisted", False)


@commands.check
async def check_if_blacklisted(ctx: CustomContext) -> bool:
    if is_blacklisted(ctx):
        raise Blacklisted()
    else:
        return True


async def has_permission_level(ctx: CustomContext, value: Permission):
    if ctx.guild is None:
        raise commands.NoPrivateMessage

    permission_level: Optional[Permission] = get_permission(ctx)

    return (
        permission_level >= value if permission_level is not None else False
    ) or ctx.author.guild_permissions.administrator


@commands.check
async def check_is_admin(ctx: CustomContext) -> bool:
    if not await has_permission_level(ctx, Permission.ADMINISTRATOR):
        raise LowPrivilege(Permission.ADMINISTRATOR, get_permission(ctx))
    else:
        return True


@commands.check
async def check_is_mod(ctx: CustomContext) -> bool:
    if not await has_permission_level(ctx, Permission.MODERATOR):
        raise LowPrivilege(Permission.MODERATOR, get_permission(ctx))
    else:
        return True


@commands.check
async def check_is_man(ctx: CustomContext) -> bool:
    if not await has_permission_level(ctx, Permission.MANAGER):
        raise LowPrivilege(Permission.MANAGER, get_permission(ctx))
    else:
        return True


@commands.check
async def check_is_allowed_nsfw(ctx: CustomContext) -> bool:
    if ctx.channel.id in ctx["guild_document"].get("customnsfw", []) or ctx.channel.nsfw:
        return True
    else:
        raise commands.NSFWChannelRequired(ctx.channel)



__all__ = [
    "Blacklisted",
    "LowPrivilege",
    "is_blacklisted",
    "has_permission_level",
    "check_is_admin",
    "check_is_mod",
    "check_is_man",
    "check_is_allowed_nsfw",
]

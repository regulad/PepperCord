"""Checks for permissions."""

from discord.ext import commands

import utils.permissions


class Blacklisted(commands.CheckFailure):
    pass


class LowPrivilege(commands.CheckFailure):
    pass


async def is_blacklisted(ctx):
    if ctx.guild is not None and ctx.guild_document.get("blacklisted", False):
        raise Blacklisted
    elif ctx.author_document.get("blacklisted", False):
        raise Blacklisted
    else:
        return True


async def has_permission_level(ctx, value: utils.permissions.Permissions):
    if ctx.guild is None:
        raise commands.NoPrivateMessage
    value = value.value or 3
    has = await utils.permissions.GuildPermissionManager(ctx).read(ctx.author)
    if (has >= value) or await guild_privileged(ctx):
        return True
    else:
        raise LowPrivilege(f"Has {has}, needs {value}. ({value - has})")


async def is_admin(ctx):
    return await has_permission_level(ctx, utils.permissions.Permissions.ADMINISTRATOR)


async def is_mod(ctx):
    return await has_permission_level(ctx, utils.permissions.Permissions.MODERATOR)


async def is_man(ctx):
    return await has_permission_level(ctx, utils.permissions.Permissions.MANAGER)


async def guild_privileged(ctx):
    if ctx.author.guild_permissions.administrator or (ctx.author.id == ctx.guild.owner_id):
        return True
    else:
        return False

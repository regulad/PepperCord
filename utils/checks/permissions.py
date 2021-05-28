"""Checks for permissions."""

from discord.ext import commands

import utils.errors as errors
import utils.permissions as permissions


async def has_permission_level(ctx, value: permissions.Permissions):
    if ctx.guild is None:
        raise commands.NoPrivateMessage()
    value = value.value or 3
    has = await permissions.GuildPermissionManager(ctx).read(ctx.author)
    if (has >= value) or await guild_privileged(ctx):
        return True
    else:
        raise errors.LowPrivilege(f"Has {has}, needs {value}. ({value - has})")


async def is_admin(ctx):
    return await has_permission_level(ctx, permissions.Permissions.ADMINISTRATOR)


async def is_mod(ctx):
    return await has_permission_level(ctx, permissions.Permissions.MODERATOR)


async def is_man(ctx):
    return await has_permission_level(ctx, permissions.Permissions.MANAGER)


async def guild_privileged(ctx):
    if ctx.author.guild_permissions.administrator or (ctx.author.id == ctx.guild.owner_id):
        return True
    else:
        return False

from .permissions import *
from .errors import *

from discord.ext import commands
import discord


async def has_permission_level(ctx, value: Permissions):
    if not ctx.guild:
        return False
    value = value or 3
    if (
        (await GuildPermissionManager(ctx).read(ctx.author) >= value.value)
        or await guild_privledged(ctx)
        or await commands.is_owner(ctx.author)
    ):
        return True
    else:
        raise LowPrivilege()


async def is_admin(ctx):
    return await has_permission_level(ctx, Permissions.ADMINISTRATOR)


async def is_mod(ctx):
    return await has_permission_level(ctx, Permissions.MODERATOR)


async def is_man(ctx):
    return await has_permission_level(ctx, Permissions.MANAGER)


async def guild_privledged(ctx):
    if (ctx.author.guild_permissions.administrator) or (ctx.author.id == ctx.guild.owner_id):
        return True
    else:
        raise commands.MissingPermissions(discord.Permissions(permissions=8))

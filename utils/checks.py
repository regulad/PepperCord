import instances
from discord.ext import commands

from .permissions import *


async def has_permission_level(ctx: commands.Context, value: Permissions):
    if not ctx.guild:
        return False
    value = value or 1
    permission_manager = GuildPermissionManager(ctx.guild, instances.guild_collection)
    await permission_manager.fetch_document()
    if (
        (await permission_manager.read(ctx.author) >= value.value)
        or (ctx.author.guild_permissions.administrator)
        or (ctx.author.id == ctx.guild.owner_id)
    ):
        return True
    else:
        raise commands.MissingPermissions()


async def is_admin(ctx):
    return await has_permission_level(ctx, Permissions.ADMINISTRATOR)


async def is_mod(ctx):
    return await has_permission_level(ctx, Permissions.MODERATOR)


async def is_man(ctx):
    return await has_permission_level(ctx, Permissions.MANAGER)

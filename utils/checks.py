from .permissions import *
from .errors import *


async def has_permission_level(ctx, value: Permissions):
    if not ctx.guild:
        return False
    value = value.value or 3
    has = await GuildPermissionManager(ctx).read(ctx.author)
    if (has >= value) or await guild_privileged(ctx):
        return True
    else:
        raise LowPrivilege(f"Has {has}, needs {value}. ({value - has})")


async def is_admin(ctx):
    return await has_permission_level(ctx, Permissions.ADMINISTRATOR)


async def is_mod(ctx):
    return await has_permission_level(ctx, Permissions.MODERATOR)


async def is_man(ctx):
    return await has_permission_level(ctx, Permissions.MANAGER)


async def guild_privileged(ctx):
    if ctx.author.guild_permissions.administrator or (ctx.author.id == ctx.guild.owner_id):
        return True
    else:
        return False

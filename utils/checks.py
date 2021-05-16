import instances

from .managers import GuildPermissionManager


async def has_permission_level(ctx, value: int):
    if ctx.guild == None:  # User must be in DM
        return False
    if (
        (GuildPermissionManager(ctx.guild, instances.guild_collection).read(ctx.author) >= value)
        or (ctx.author.guild_permissions.administrator)
        or (ctx.author.id == ctx.guild.owner_id)
    ):
        return True
    else:
        return False

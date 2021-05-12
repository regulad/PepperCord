from instances import activeDatabase

from .managers import GuildPermissionManager


def has_permission_level(ctx, value: int):
    if ctx.guild == None:  # User must be in DM
        return False
    if (
        (GuildPermissionManager(ctx.guild, activeDatabase["servers"]).read(ctx.author) >= value)
        or (ctx.author.guild_permissions.administrator)
        or (ctx.author.id == ctx.guild.owner_id)
    ):
        return True
    else:
        return False

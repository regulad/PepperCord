from typing import Optional, Union, cast

import discord
from discord.ext import commands

from utils import bots, permissions
from utils.checks import LowPrivilege, has_permission_level
from utils.converters import PermissionConverter
from utils.permissions import Permission, get_permission


class Privileges(commands.Cog):
    """System for controlling privileges for executing commands in a guild."""

    def __init__(self, bot: bots.BOT_TYPES):
        self.bot: bots.BOT_TYPES = bot

    async def cog_check(self, ctx: bots.CustomContext) -> bool:
        if not (
            await has_permission_level(ctx, Permission.ADMINISTRATOR)
            or ctx.author.guild_permissions.administrator
        ):
            raise LowPrivilege(Permission.ADMINISTRATOR, get_permission(ctx))
        else:
            return True

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="permissions",
        aliases=["perms", "priv", "privileges"],
        brief="Change server permissions.",
        description="Read & write permissions of various entities on the server. "
        "Level 0 means that the entity has no permissions, "
        "level 1 means that they have manager permissions (think controlling music or reading audit logs), "
        "level 2 means that they have moderator privileges, "
        "and level 3 means that they have administrator privileges.",
    )
    async def permissions(self, ctx: bots.CustomContext) -> None:
        pass

    @permissions.command(
        name="disable",
        aliases=["off", "delete"],
        brief="Deletes permission data.",
        description="Deletes all permission data. This reverts permissions to their initial state.",
    )
    async def sdisable(self, ctx: bots.CustomContext) -> None:
        if ctx["guild_document"] is None:
            raise bots.NotConfigured
        else:
            await ctx["guild_document"].update_db({"$unset": {"permissions": 1}})

    @permissions.command(
        name="read",
        brief="Displays permission level of entity.",
        description="Gets raw permission level from member or role.",
        usage="[Member|Role]",
    )
    async def read(self, ctx, *, entity: Optional[Union[discord.Member, discord.Role]]):
        entity = entity or ctx.author
        await ctx.send(
            f"{entity.name} has permission level `{await permissions.get_permission(ctx, entity)}`"
        )

    @permissions.command(
        name="write",
        brief="Write permission level of a role.",
        description="Writes given permission level into a role. "
        "Valid options include: Manager, Moderator, and Administrator.",
        usage="[Permission Level (Admin)] <Role>",
    )
    async def write(
        self,
        ctx: bots.CustomContext,
        value: PermissionConverter,
        *,
        entity: discord.Role,
    ) -> None:
        permission: permissions.Permission = cast(permissions.Permission, value)
        await permissions.write_permission(ctx, entity, permission)


def setup(bot: bots.BOT_TYPES):
    bot.add_cog(Privileges(bot))

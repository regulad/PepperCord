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

    @commands.group()
    async def permissions(self, ctx: bots.CustomContext) -> None:
        pass

    @permissions.command()
    async def sdisable(self, ctx: bots.CustomContext) -> None:
        """Disables the permission system in this server."""
        if ctx["guild_document"] is None:
            raise bots.NotConfigured
        else:
            await ctx["guild_document"].update_db({"$unset": {"permissions": 1}})
        await ctx.send("Disabled.", ephemeral=True)

    @permissions.command()
    async def read(
        self,
        ctx: bots.CustomContext,
        *,
        entity: Optional[Union[discord.Member, discord.Role]] = commands.Option(
            description="The role or member that will have it's permissions read."
        ),
    ):
        """Reads the permission level of a member or role."""
        entity = entity or ctx.author
        await ctx.send(
            f"{entity.name} has permission level `{permissions.get_permission(ctx, entity)}`",
            ephemeral=True,
        )

    @permissions.command()
    async def write(
        self,
        ctx: bots.CustomContext,
        permission: PermissionConverter = commands.Option(
            description="The permission that the role will inherit. Admin, Moderator, or Manager."
        ),
        *,
        role: discord.Role = commands.Option(
            description="The role that will have it's permission changed."
        ),
    ) -> None:
        """Writes a permission of Admin, Moderator, or Manager to a role."""
        permission: permissions.Permission = cast(permissions.Permission, permission)
        await permissions.write_permission(ctx, role, permission)


def setup(bot: bots.BOT_TYPES):
    bot.add_cog(Privileges(bot))

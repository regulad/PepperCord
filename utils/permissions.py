import enum
import typing

import discord


class Permissions(enum.Enum):
    MANAGER = 1
    MODERATOR = 2
    ADMINISTRATOR = 3


class GuildPermissionManager:
    def __init__(self, ctx):
        self.ctx = ctx

    async def read(self, entity: typing.Union[discord.Member, discord.Role]):
        """Gets the max permission level of a member or role"""
        # Configures guild document
        # Gets role from member
        if isinstance(entity, discord.Member):
            entity = entity.top_role
        # Create a list of all roles below the current role
        below_roles = []
        for role in self.ctx.guild.roles:
            if role <= entity:
                below_roles.append(role)
        # Gets permission level for each role
        permission_levels = []
        for role in below_roles:
            active_item = self.ctx.guild_document.get("permissions", {}).get(str(role.id))
            if not active_item:
                active_item = 0
            permission_levels.append(active_item)
        # Returns the highest permission level
        return max(permission_levels)

    async def write(self, role: discord.Role, level: Permissions):
        """Writes a permission level into a role in a guild document"""
        value = level.value
        await self.ctx.guild_document.update_db({"$set": {f"permissions.{role.id}": value}})


__all__ = ["Permissions", "GuildPermissionManager"]

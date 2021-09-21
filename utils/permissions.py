from enum import Enum
from typing import Union, Optional, List

import discord

from utils.bots import CustomContext


class Permission(Enum):
    """A class enumerating different permission levels in the scope of a guild."""

    MANAGER = 1
    MODERATOR = 2
    ADMINISTRATOR = 3

    def __lt__(self, other) -> bool:
        return self.value < other.value

    def __le__(self, other) -> bool:
        return self.value <= other.value

    def __ge__(self, other) -> bool:
        return self.value >= other.value

    def __gt__(self, other) -> bool:
        return self.value > other.value


async def write_permission(
        ctx: CustomContext, role: discord.Role, permission: Permission
) -> None:
    await ctx["guild_document"].update_db(
        {"$set": {f"permissions.{role.id}": permission.value}}
    )


def get_permission(
        ctx: CustomContext, scope: Optional[Union[discord.Member, discord.Role]] = None
) -> Optional[Permission]:
    """Read the top permission level of an entity."""

    scope = scope or ctx.author

    if isinstance(scope, discord.Member):
        scope = scope.top_role

    # Create a list of all roles below the current role
    below_roles: List[discord.Role] = []
    for role in scope.guild.roles:
        if scope >= role:
            below_roles.append(role)

    # Gets permission level for each role
    permission_levels: List[int] = []
    for role in below_roles:
        active_item: Optional[int] = ctx["guild_document"].get("permissions", {}).get(
            str(role.id)
        )
        permission_levels.append(active_item if active_item is not None else 0)

    max_permission_level: int = max(permission_levels)
    return Permission(max_permission_level) if max_permission_level > 0 else None


__all__ = ["Permission", "get_permission", "write_permission"]

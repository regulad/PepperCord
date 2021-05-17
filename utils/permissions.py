import copy
import enum
import typing

import discord
import pymongo

from .managers import CommonConfigManager


class Permissions(enum.Enum):
    MANAGER = 1
    MODERATOR = 2
    ADMINISTRATOR = 3


class BlacklistManager(CommonConfigManager):
    def __init__(
        self, model: typing.Union[discord.Guild, discord.Member, discord.User], collection: pymongo.collection.Collection
    ):
        super().__init__(model, collection, "blacklisted", False)

    def write(self, value: bool):
        super().write(value)


class GuildPermissionManager(CommonConfigManager):
    def __init__(self, guild: discord.Guild, collection: pymongo.collection.Collection):
        super().__init__(guild, collection, "permissions", {})

    def read(self, entity: typing.Union[discord.Member, discord.Role]):
        if isinstance(entity, discord.Member):
            entity = entity.top_role
        below_roles = []
        for role in self.model.roles:
            if role <= entity:
                below_roles.append(role)
        permission_levels = []
        for role in below_roles:
            active_item = self.active_key.get(str(role.id))
            if not active_item:
                active_item = 0
            permission_levels.append(active_item)
        return max(permission_levels)

    def write(self, role: discord.Role, level: Permissions):
        working_key = copy.deepcopy(self.active_key)
        working_key.update({str(role.id): level.value})
        super().write(working_key)

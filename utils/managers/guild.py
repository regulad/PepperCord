import copy
import typing

import discord
import pymongo

from .common import CommonConfigManager


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
            if active_item == None:
                active_item = 0
            else:
                active_item = int(active_item)
            permission_levels.append(active_item)
        return max(permission_levels)

    def write(self, role: discord.Role, level: int):
        working_key = copy.deepcopy(self.active_key)
        working_key.update({str(role.id): level})
        super().write(working_key)

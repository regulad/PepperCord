from os import write
import copy
import typing

import discord
import pymongo


class GuildManager:
    def __init__(self, guild: discord.Guild, collection: pymongo.collection.Collection):
        self.guild = guild
        self.collection = collection

        guild_dict = collection.find_one({"_id": str(guild.id)})
        if not guild_dict:
            self.guild_dict = {"_id": str(guild.id)}
            collection.insert_one(self.guild_dict)
        else:
            self.guild_dict = collection.find_one({"_id": str(guild.id)})


class GuildConfigManager(GuildManager):
    def __init__(
        self,
        guild: discord.Guild,
        collection: pymongo.collection.Collection,
        key_name: str,
        key_value: typing.Union[str, dict],
    ):
        super().__init__(guild, collection)

        self.key_name = key_name
        self.key_value = key_value

        self.active_key = self.guild_dict.setdefault(key_name, key_value)

    def read(self):
        return self.active_key

    def write(self, key_value: typing.Union[str, dict]):
        working_dict = copy.deepcopy(self.guild_dict)
        working_dict.update({self.key_name: key_value})
        write_query = {"$set": working_dict}
        self.collection.update_one({"_id": str(self.guild.id)}, write_query)


class GuildPermissionManager(GuildConfigManager):
    def __init__(self, guild: discord.Guild, collection: pymongo.collection.Collection):
        super().__init__(guild, collection, "permissions", {})

    def read(self, entity: typing.Union[discord.Member, discord.Role]):
        if isinstance(entity, discord.Member):
            entity = entity.top_role
        below_roles = []
        for role in self.guild.roles:
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
        working_dict = copy.deepcopy(self.guild_dict)
        working_key.update({str(role.id): str(level)})
        working_dict["permissions"].update(working_key)
        write_query = {"$set": working_dict}
        self.collection.update_one({"_id": str(self.guild.id)}, write_query)

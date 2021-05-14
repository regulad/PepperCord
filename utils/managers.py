import copy
import time
import typing

import discord
import pymongo


class CommonConfigManager:
    def __init__(
        self,
        model: typing.Union[discord.Guild, discord.Member, discord.User],
        collection: pymongo.collection.Collection,
        key_name: str,
        key_value,
    ):
        self.model = model
        self.collection = collection

        active_dict = collection.find_one({"_id": model.id})
        if not active_dict:
            self.active_dict = {"_id": model.id}
            collection.insert_one(self.active_dict)
        else:
            self.active_dict = collection.find_one({"_id": model.id})

        self.key_name = key_name
        self.key_value = key_value

        self.active_key = self.active_dict.setdefault(key_name, key_value)

    def read(self):
        return self.active_key

    def write(self, key_value):
        working_dict = {str(self.key_name): key_value}
        write_query = {"$set": working_dict}
        self.collection.update_one({"_id": self.active_dict["_id"]}, write_query)

    def delete(self, key_value):
        working_dict = {str(self.key_name): key_value}
        write_query = {"$unset": working_dict}
        self.collection.update_one({"_id": self.active_dict["_id"]}, write_query)


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


class GuildMessageManager(CommonConfigManager):
    def __init__(self, guild: discord.Guild, collection: pymongo.collection.Collection):
        super().__init__(guild, collection, "messages", {})

    def read(self, message_type: str):
        return_dict = self.active_key[message_type]
        return return_dict

    def write(self, message_type: str, channel: discord.TextChannel, message: str):
        working_key = copy.deepcopy(self.active_key)
        working_key.update({message_type: {str(channel.id): message}})
        super().write(working_key)


class GuildPunishmentManager(CommonConfigManager):
    def __init__(self, guild: discord.Guild, collection: pymongo.collection.Collection):
        super().__init__(guild, collection, "punishments", {})

    def write(self, punishment_type: str, member: discord.Member, punishment_time: typing.Union[int, float]):
        unpunishtime = time.time() + punishment_time
        working_key = copy.deepcopy(self.active_key)
        working_key.update({str(member.id): {punishment_type: unpunishtime}})
        super().write(working_key)

    def delete(self, member: discord.Member):
        working_key = copy.deepcopy(self.active_key)
        working_key.update({str(member.id): 1})
        super().delete(working_key)


class GuildReactionManager(CommonConfigManager):
    def __init__(self, guild: discord.Guild, collection: pymongo.collection.Collection):
        super().__init__(guild, collection, "reactions", {})

    def write(
        self,
        channel: discord.TextChannel,
        message: typing.Union[discord.Message, discord.PartialMessage],
        emoji: typing.Union[discord.Emoji, discord.PartialEmoji, str],
        role: discord.Role,
    ):
        if isinstance(emoji, (discord.Emoji, discord.PartialEmoji)):
            emoji_name = emoji.name
        elif isinstance(emoji, str):
            emoji_name = emoji
        working_key = copy.deepcopy(self.active_key)
        working_key.update({str(channel.id): {str(message.id): {emoji_name: role.id}}})
        super().write(working_key)

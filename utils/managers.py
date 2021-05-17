import copy
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

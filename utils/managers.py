import typing

import discord
import motor.motor_asyncio


class CommonConfigManager:
    def __init__(
        self,
        model: typing.Union[discord.Guild, discord.Member, discord.User],
        collection: motor.motor_asyncio.AsyncIOMotorCollection,
        key_name: str,
        key_value,
    ):
        self.model = model
        self.collection = collection
        self.key_name = key_name
        self.key_value = key_value

    async def fetch_document(self):
        self.active_dict = await self.collection.find_one({"_id": self.model.id})
        if not self.active_dict:
            self.active_dict = {"_id": self.model.id}
            await self.collection.insert_one(self.active_dict)
        self.active_key = self.active_dict.setdefault(self.key_name, self.key_value)

    async def read(self):
        return self.active_key

    async def write(self, key_value):
        working_dict = {str(self.key_name): key_value}
        write_query = {"$set": working_dict}
        await self.collection.update_one({"_id": self.active_dict["_id"]}, write_query)

    async def delete(self, key_value):
        working_dict = {str(self.key_name): key_value}
        write_query = {"$unset": working_dict}
        await self.collection.update_one({"_id": self.active_dict["_id"]}, write_query)

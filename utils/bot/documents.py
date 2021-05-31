from typing import Union

import discord
import motor.motor_asyncio

from utils.database import Document


class ModelDocument(Document):
    """Represents a document fetched via a model."""

    def __init__(
            self,
            *args,
            collection: motor.motor_asyncio.AsyncIOMotorCollection,
            query: dict,
            model: Union[discord.Guild, discord.Member, discord.User],
            **kwargs
    ):
        self._model = model

        super().__init__(*args, collection=collection, query=query, **kwargs)

    @classmethod
    async def get_from_model(
            cls,
            collection: motor.motor_asyncio.AsyncIOMotorCollection,
            model: Union[discord.Guild, discord.Member, discord.User],
    ):
        query = {"_id": model.id}
        document = (await collection.find_one(query)) or query
        return cls(document, collection=collection, query=query, model=model)

    @property
    def model(self):
        return self._model

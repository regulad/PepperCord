import asyncio
import copy

import motor.motor_asyncio

from .misc import dict_difference


class Document(dict):
    """Represents a single MonogDB document.
    .collection: MongoDB collection the document is stored in.
    .query: Query used to find the document."""

    def __init__(self, *args, collection: motor.motor_asyncio.AsyncIOMotorCollection, query: dict, **kwargs):
        self._collection = collection
        self._query = query
        super().__init__(*args, **kwargs)

    @classmethod
    async def find_one_or_insert_document(cls, collection: motor.motor_asyncio.AsyncIOMotorCollection, query: dict):
        document = await collection.find_one(query)
        if not document:
            await collection.insert_one(query)
            document = query
        return cls(document, collection=collection, query=query)

    @classmethod
    async def find_one_document(cls, collection: motor.motor_asyncio.AsyncIOMotorCollection, query: dict):
        document = await collection.find_one(query)
        return cls(document, collection=collection, query=query)

    @property
    def collection(self):
        return self._collection

    @property
    def query(self):
        return self._query

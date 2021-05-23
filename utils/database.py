import asyncio
from builtins import _KT, _VT

import motor.motor_asyncio


class Document(dict):
    """Represents a single MonogDB document."""

    @classmethod
    async def find_one_or_insert_document(cls, collection: motor.motor_asyncio.AsyncIOMotorCollection, query: dict):
        document = await collection.find_one(query)
        if not document:
            await collection.insert_one(query)
            document = query
        return cls(document)

    @classmethod
    async def find_one_document(cls, collection: motor.motor_asyncio.AsyncIOMotorCollection, query: dict):
        document = await collection.find_one(query)
        return cls(document)

    def __setitem__(self, k: _KT, v: _VT) -> None:
        return super().__setitem__(k, v)

    def __delitem__(self, v: _KT) -> None:
        asyncio.create_task()
        return super().__delitem__(v)

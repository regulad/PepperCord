import copy

import motor.motor_asyncio


class Document(dict):
    """Represents a single MonogDB document.
    .collection: MongoDB collection the document is stored in.
    .query: Query used to find the document."""

    def __init__(self, *args, collection: motor.motor_asyncio.AsyncIOMotorCollection, query: dict, before: dict, **kwargs):
        self._collection = collection
        self._query = query
        self._before = before
        super().__init__(*args, **kwargs)

    @classmethod
    async def find_one_or_insert_document(cls, collection: motor.motor_asyncio.AsyncIOMotorCollection, query: dict):
        document = (await collection.find_one(query)) or query
        before = copy.deepcopy(document)
        return cls(document, collection=collection, query=query, before=before)

    async def update_db(self):
        """Gets the remote document up-to-date with the remote."""
        if dict(self) != self._before:
            return await self._collection.replace_one(self._query, dict(self), upsert=True)

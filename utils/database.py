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
    async def get_document(cls, collection: motor.motor_asyncio.AsyncIOMotorCollection, query: dict):
        document = (await collection.find_one(query)) or query
        before = copy.deepcopy(document)
        return cls(document, collection=collection, query=query, before=before)

    @classmethod
    async def get_from_id(cls, collection: motor.motor_asyncio.AsyncIOMotorCollection, id: int):
        query = {"_id": id}
        return await cls.get_document(collection, query)

    async def replace_db(self):
        """Gets the local document up-to-date with the database by replacing it."""
        if dict(self) != self._before:
            return await self._collection.replace_one(self._query, dict(self), upsert=True)

    async def update_db(self, action):
        """Gets the database up-to-date with the local document by updating the document on the database."""
        if dict(self) != self._before:
            return await self._collection.update_one(
                self._query, {action: dict(set(self._before.items()) - set(self.items()))}, upsert=True
            )

    async def delete_db(self):
        """Deletes the document from the remote database."""
        return await self._collection.delete_one(self._query)

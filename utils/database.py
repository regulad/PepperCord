from typing import Optional
from motor.motor_asyncio import AsyncIOMotorCollection


class Document(dict):
    """Represents a single MongoDB document."""

    def __init__(self, *args, collection: AsyncIOMotorCollection, query: dict, **kwargs):
        self._collection = collection
        self._query = query
        super().__init__(*args, **kwargs)

    @classmethod
    async def get_document(cls, collection: AsyncIOMotorCollection, query: dict, **kwargs):
        """Gets a document from the database with a query, or returns a new one with the content of the query."""

        return cls((await collection.find_one(query)) or query, collection=collection, query=query, **kwargs)

    @classmethod
    async def find_document(cls, collection: AsyncIOMotorCollection, query: dict, **kwargs) -> Optional:
        """Gets a document from a database if it exists, else None."""

        document: Optional[dict] = await collection.find_one(query)
        return cls(document, collection=collection, query=query, **kwargs) if document is not None else None

    async def update_db(self, query: dict) -> None:
        """Performs an update query on the database with the document."""

        async with await self._collection.database.client.start_session() as session:
            async with session.start_transaction():
                await self._collection.update_one(self._query, query, upsert=True)
                self.clear()
                self.update(await self._collection.find_one(self._query))

    async def replace_db(self) -> None:
        """Replaces the document on the database with this document."""

        await self._collection.replace_one(self._query, dict(self), upsert=True)

    async def delete_db(self) -> None:
        """Deletes the document from the database."""

        async with await self._collection.database.client.start_session() as session:
            async with session.start_transaction():
                await self._collection.delete_one(self._query)
                self.clear()
                self.update(self._query)


__all__ = ["Document"]

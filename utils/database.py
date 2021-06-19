from typing import Optional


class Document(dict):
    """Represents a single MongoDB document.
    .collection: MongoDB collection the document is stored in.
    .query: Query used to find the document."""

    def __init__(self, *args, collection, query: dict, **kwargs):
        self._collection = collection
        self._query = query
        super().__init__(*args, **kwargs)

    @classmethod
    async def get_document(cls, collection, query: dict, **kwargs):
        """Gets a document from the database with a query, or returns a new one."""

        document: dict = (await collection.find_one(query)) or query
        return cls(document, collection=collection, query=query, **kwargs)

    @classmethod
    async def find_document(cls, collection, query: dict, **kwargs):
        """Gets a document from a database, or returns nothing."""

        document: Optional[dict] = await collection.find_one(query)
        return cls(document, collection=collection, query=query, **kwargs) if document is not None else None

    async def update_db(self, query: dict) -> None:
        """Performs an update on the database with the document."""

        async with await self._collection.database.client.start_session() as session:
            async with session.start_transaction():
                await self._collection.update_one(self._query, query, upsert=True)
                new_document: dict = await self._collection.find_one(self._query)

        self.clear()
        self.update(new_document)

    async def replace_db(self) -> None:
        """Gets the local document up-to-date with the database by replacing it."""

        await self._collection.replace_one(self._query, dict(self), upsert=True)

    async def delete_db(self) -> None:
        """Deletes the document from the remote database."""

        async with await self._collection.database.client.start_session() as session:
            async with session.start_transaction():
                await self._collection.delete_one(self._query)
                await self._collection.find_one(self._query)

        self.clear()
        self.update(self._query)


__all__ = ["Document"]

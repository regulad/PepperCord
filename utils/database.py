from motor.motor_asyncio import AsyncIOMotorCollection


class Document(dict):
    """Represents a single MongoDB document.
    .collection: MongoDB collection the document is stored in.
    .query: Query used to find the document."""

    def __init__(self, *args, collection: AsyncIOMotorCollection, query: dict, **kwargs):
        self._collection = collection
        self._query = query
        super().__init__(*args, **kwargs)

    @classmethod
    async def get_document(cls, collection: AsyncIOMotorCollection, query: dict):
        document = (await collection.find_one(query)) or query
        return cls(document, collection=collection, query=query)

    @classmethod
    async def get_from_id(cls, collection: AsyncIOMotorCollection, id_query):
        query = {"_id": id_query}
        return await cls.get_document(collection, query)

    @property
    def collection(self) -> AsyncIOMotorCollection:
        return self._collection

    @property
    def query(self) -> dict:
        return self._query

    async def find_db(self) -> None:
        """Update the document to the version on the database."""

        self.clear()
        self.update(await self.collection.find_one(self.query))

    async def update_db(self, query: dict) -> None:
        """Performs an update on the database with the document."""

        await self.collection.update_one(self.query, query, upsert=True)
        await self.find_db()

    async def replace_db(self) -> None:
        """Gets the local document up-to-date with the database by replacing it."""

        await self.collection.replace_one(self.query, dict(self), upsert=True)
        await self.find_db()

    async def delete_db(self):
        """Deletes the document from the remote database."""

        await self.collection.delete_one(self._query)
        self.clear()
        self.update(self.query)

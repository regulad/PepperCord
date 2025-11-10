from typing import Any, Mapping, Self, Sequence

from pymongo.asynchronous.collection import AsyncCollection


# Our code doesn't consistently use any type for the actual data for the document, so this is what we use.
UPSTREAM_DICT_TYPE = dict[str, Any]


# PyMongo/BSON *does* instantiate the class, however it does not pass through the collection nor the filter/query
class PCInternalDocument(UPSTREAM_DICT_TYPE):
    """
    The internal document type returned by the async pymongo client. It should be "wrapped" before being returned to extensions.
    """

    def wrap(
        self, collection: AsyncCollection[PCInternalDocument], filter: Any
    ) -> PCDocument:
        return PCDocument(collection, filter, **self)


class PCDocument(UPSTREAM_DICT_TYPE):
    """Represents a single MongoDB document."""

    def __init__(
        self,
        collection: AsyncCollection[PCInternalDocument],
        filter: Any,
        **kwargs: Any
    ):
        self._collection = collection
        self._filter = filter
        super().__init__(**kwargs)

    @classmethod
    async def get_document(
        cls, collection: AsyncCollection[PCInternalDocument], filter: Any
    ) -> PCDocument:
        """Gets a document from the database with a query, or returns a new one with the content of the query."""

        maybe_internal_doc = await collection.find_one(filter)

        if maybe_internal_doc is not None:
            return maybe_internal_doc.wrap(collection, filter)

        # Document doesn't exist, we will be making it a-new
        return cls(collection, filter, **filter)

    @classmethod
    async def find_document(
        cls, collection: AsyncCollection[PCInternalDocument], filter: Any
    ) -> PCDocument | None:
        """Gets a document from a database if it exists, else None."""

        maybe_internal_doc = await collection.find_one(filter)

        if maybe_internal_doc is not None:
            return maybe_internal_doc.wrap(collection, filter)

        return None

    # The only Document kwarg actually used in application code is array_filters. More may be added?
    async def update_db(
        self,
        update: Mapping[str, Any],
        *,
        array_filters: Sequence[Mapping[str, Any]] | None = None
    ) -> None:
        """Performs an update query on the database with the document."""

        async with self._collection.database.client.start_session() as session:
            async with await session.start_transaction():
                await self._collection.update_one(
                    self._filter, update, array_filters=array_filters, upsert=True
                )

        self.clear()

        new_int_doc = await self._collection.find_one(self._filter)

        if new_int_doc is None:
            raise RuntimeError("Document didn't exist, right after upserting it!")

        self.update(new_int_doc)

    async def replace_db(self) -> None:
        """Replaces the document on the database with this document."""

        await self._collection.replace_one(self._filter, dict(self), upsert=True)

    async def delete_db(self) -> None:
        """Deletes the document from the database."""

        async with self._collection.database.client.start_session() as session:
            async with await session.start_transaction():
                await self._collection.delete_one(self._filter)
                self.clear()
                self.update(self._filter)


__all__ = ("PCDocument", "PCInternalDocument")

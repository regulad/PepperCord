from asyncio import Lock
from collections.abc import KeysView, ValuesView, ItemsView
import logging
from typing import Any, Iterator, Mapping, Never, Sequence, TypeVar
import warnings

from aiorwlock import RWLock
from pymongo.asynchronous.collection import AsyncCollection


logger = logging.getLogger(__name__)


# Our code doesn't consistently use any type for the actual data for the document, so this is what we use.
UPSTREAM_DICT_TYPE = dict[str, Any]
K = TypeVar("K", bound=str)
V = TypeVar("V", bound=Any)


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
    """
    Represents a single MongoDB document.
    The existence of a PCDocument does not guarantee a document in MongoDB exists that tracks the PCDocument.
    Update document with an upsert must be called.
    """

    def __init__(
        self,
        collection: AsyncCollection[PCInternalDocument],
        filter: Any,
        **kwargs: Any
    ):
        self._collection = collection
        self._filter = filter
        self._write_in_flight_lock = RWLock()
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

        async with self._write_in_flight_lock.writer_lock:
            async with self._collection.database.client.start_session() as session:
                async with await session.start_transaction():
                    await self._collection.update_one(
                        self._filter, update, array_filters=array_filters, upsert=True
                    )

            super().clear()

            new_int_doc = await self._collection.find_one(self._filter)

            if new_int_doc is None:
                raise RuntimeError("Document didn't exist, right after upserting it!")

            super().update(new_int_doc)

    async def replace_db(self) -> None:
        """Replaces the document on the database with this document."""
        async with self._write_in_flight_lock.writer_lock:
            await self._collection.replace_one(self._filter, dict(self), upsert=True)

    async def delete_db(self) -> None:
        """Deletes the document from the database."""
        async with self._write_in_flight_lock.writer_lock:
            async with self._collection.database.client.start_session() as session:
                async with await session.start_transaction():
                    await self._collection.delete_one(self._filter)
                    super().clear()
                    super().update(self._filter)

    # State retrievers

    async def safe_subscript(self, key: str) -> Any:
        """
        Gets an item from the PCDocument while guaranteeing no write is in flight.
        This should be used over the __getitem__ method to prevent race conditions when a write may be in flight.
        """
        async with self._write_in_flight_lock.reader_lock:
            return super().__getitem__(key)

    @warnings.deprecated(
        "Tried to read a PCDocument from a sync context with #__getitem__! Migrate to #safe_subscript to avoid runtime errors!"
    )
    def __getitem__(self, key: str) -> Any:
        if self._write_in_flight_lock.writer_lock.locked:
            raise RuntimeError(
                "Tried to read a PCDocument that is currently being updated!"
            )
        return super().__getitem__(key)

    async def safe_get(self, key: str, default: Any = None) -> Any:
        """
        Gets an item from the PCDocument with optional default while guaranteeing no write is in flight.
        This should be used over the get method to prevent race conditions when a write may be in flight.
        """
        async with self._write_in_flight_lock.reader_lock:
            return super().get(key, default)

    @warnings.deprecated(
        "Tried to read a PCDocument from a sync context with #get! Migrate to #safe_get to avoid runtime errors!"
    )
    def get(self, key: str, default: Any = None) -> Any:
        if self._write_in_flight_lock.writer_lock.locked:
            raise RuntimeError(
                "Tried to read a PCDocument that is currently being updated!"
            )
        return super().get(key, default)

    async def safe_keys(self) -> KeysView[str]:
        """
        Gets keys view from the PCDocument while guaranteeing no write is in flight.
        This should be used over the keys method to prevent race conditions when a write may be in flight.
        """
        async with self._write_in_flight_lock.reader_lock:
            return super().keys()

    @warnings.deprecated(
        "Tried to read a PCDocument from a sync context with #keys! Migrate to #safe_keys to avoid runtime errors!"
    )
    def keys(self) -> KeysView[str]:  # type: ignore[override]  # private
        if self._write_in_flight_lock.writer_lock.locked:
            raise RuntimeError(
                "Tried to read a PCDocument that is currently being updated!"
            )
        return super().keys()

    async def safe_values(self) -> ValuesView[Any]:
        """
        Gets values view from the PCDocument while guaranteeing no write is in flight.
        This should be used over the values method to prevent race conditions when a write may be in flight.
        """
        async with self._write_in_flight_lock.reader_lock:
            return super().values()

    @warnings.deprecated(
        "Tried to read a PCDocument from a sync context with #values! Migrate to #safe_values to avoid runtime errors!"
    )
    def values(self) -> ValuesView[Any]:  # type: ignore[override]  # private
        if self._write_in_flight_lock.writer_lock.locked:
            raise RuntimeError(
                "Tried to read a PCDocument that is currently being updated!"
            )
        return super().values()

    async def safe_items(self) -> ItemsView[str, Any]:
        """
        Gets items view from the PCDocument while guaranteeing no write is in flight.
        This should be used over the items method to prevent race conditions when a write may be in flight.
        """
        async with self._write_in_flight_lock.reader_lock:
            return super().items()

    @warnings.deprecated(
        "Tried to read a PCDocument from a sync context with #items! Migrate to #safe_items to avoid runtime errors!"
    )
    def items(self) -> ItemsView[str, Any]:  # type: ignore[override]  # private
        if self._write_in_flight_lock.writer_lock.locked:
            raise RuntimeError(
                "Tried to read a PCDocument that is currently being updated!"
            )
        return super().items()

    async def safe_contains(self, key: str) -> bool:
        """
        Checks if key exists in the PCDocument while guaranteeing no write is in flight.
        This should be used over the __contains__ method to prevent race conditions when a write may be in flight.
        """
        async with self._write_in_flight_lock.reader_lock:
            return super().__contains__(key)

    @warnings.deprecated(
        "Tried to read a PCDocument from a sync context with #__contains__! Migrate to #safe_contains to avoid runtime errors!"
    )
    def __contains__(self, key: object) -> bool:
        if self._write_in_flight_lock.writer_lock.locked:
            raise RuntimeError(
                "Tried to read a PCDocument that is currently being updated!"
            )
        return super().__contains__(key)

    async def safe_len(self) -> int:
        """
        Gets the length of the PCDocument while guaranteeing no write is in flight.
        This should be used over the __len__ method to prevent race conditions when a write may be in flight.
        """
        async with self._write_in_flight_lock.reader_lock:
            return super().__len__()

    @warnings.deprecated(
        "Tried to read a PCDocument from a sync context with #__len__! Migrate to #safe_len to avoid runtime errors!"
    )
    def __len__(self) -> int:
        if self._write_in_flight_lock.writer_lock.locked:
            raise RuntimeError(
                "Tried to read a PCDocument that is currently being updated!"
            )
        return super().__len__()

    async def safe_iter(self) -> Iterator[str]:
        """
        Gets an iterator over keys from the PCDocument while guaranteeing no write is in flight.
        This should be used over the __iter__ method to prevent race conditions when a write may be in flight.
        """
        async with self._write_in_flight_lock.reader_lock:
            # Return a list to avoid iterator invalidation issues
            return iter(list(super().keys()))

    @warnings.deprecated(
        "Tried to read a PCDocument from a sync context with #__iter__! Migrate to #safe_iter to avoid runtime errors!"
    )
    def __iter__(self) -> Iterator[str]:
        if self._write_in_flight_lock.writer_lock.locked:
            raise RuntimeError(
                "Tried to read a PCDocument that is currently being updated!"
            )
        return super().__iter__()

    # State setters

    @warnings.deprecated("This method is not supported on this subclass.")
    def __setitem__(self, *args: Any, **kwargs: Any) -> Never:
        raise NotImplementedError("Use #update_db!")

    @warnings.deprecated("This method is not supported on this subclass.")
    def __delitem__(self, *args: Any, **kwargs: Any) -> Never:
        raise NotImplementedError("Use #update_db!")

    @warnings.deprecated("This method is not supported on this subclass.")
    def update(self, *args: Any, **kwargs: Any) -> Never:
        raise NotImplementedError("Use #update_db!")

    @warnings.deprecated("This method is not supported on this subclass.")
    def setdefault(self, *args: Any, **kwargs: Any) -> Never:
        raise NotImplementedError("Use #update_db!")

    @warnings.deprecated("This method is not supported on this subclass.")
    def pop(self, *args: Any, **kwargs: Any) -> Never:
        raise NotImplementedError("Use #update_db!")

    @warnings.deprecated("This method is not supported on this subclass.")
    def popitem(self, *args: Any, **kwargs: Any) -> Never:
        raise NotImplementedError("Use #update_db!")

    @warnings.deprecated("This method is not supported on this subclass.")
    def clear(self, *args: Any, **kwargs: Any) -> Never:
        raise NotImplementedError("Use #update_db!")


__all__ = ("PCDocument", "PCInternalDocument")

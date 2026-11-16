"""WatchStore against a real MongoDB, whose update operators the in-memory store in test_watch.py stands in for.

Set PEPPERCORD_TEST_MONGO_URI to a throwaway MongoDB to run these, as CI does: each test uses a database of its own and
drops it afterwards.
"""

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import pytest
from discord import Embed
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from utils.bots.bot import CustomBot
from utils.database import PCDocument, PCInternalDocument
from utils.watch import DELIVERED_PER_TOPIC, Rendered, Watch, WatchEvent, WatchStore

MONGO_URI = os.environ.get("PEPPERCORD_TEST_MONGO_URI")
pytestmark = pytest.mark.skipif(
    MONGO_URI is None, reason="set PEPPERCORD_TEST_MONGO_URI to run against MongoDB"
)

NOW = datetime(2026, 11, 16, 10, tzinfo=UTC)


@pytest.fixture
async def ddb() -> AsyncIterator[AsyncDatabase[PCInternalDocument]]:
    client: AsyncMongoClient[PCInternalDocument] = AsyncMongoClient(
        cast(str, MONGO_URI), document_class=PCInternalDocument
    )
    database = client[f"peppercord-test-{uuid4().hex}"]
    try:
        yield database
    finally:
        await client.drop_database(database.name)
        await client.close()


class Bot:
    """Sees no guilds or users, so the store wraps each document itself."""

    def __init__(self, ddb: AsyncDatabase[PCInternalDocument]) -> None:
        self.ddb = ddb

    def get_guild(self, guild_id: int) -> None:
        return None

    def get_user(self, user_id: int) -> None:
        return None


def event(key: str, topic: str = "rotations") -> WatchEvent:
    async def render() -> Rendered:
        return Rendered(key, Embed())

    return WatchEvent.dated(key, topic, NOW, render)


async def test_adds_records_and_removes_watches(
    ddb: AsyncDatabase[PCInternalDocument],
) -> None:
    store = WatchStore(cast(CustomBot, Bot(ddb)), "test")
    guild = await PCDocument.get_document(ddb["guild"], {"_id": 1})
    user = await PCDocument.get_document(ddb["user"], {"_id": 2})

    async def channel(channel_id: int) -> Watch:
        # Reread from the database: the store wrote through documents of its own.
        fresh = await PCDocument.get_document(ddb["guild"], {"_id": 1})
        return next(
            w for w in await store.in_document(fresh) if w.channel_id == channel_id
        )

    await ddb["guild"].insert_one(cast(Any, {"_id": 3}))  # a guild without watches

    await store.add(guild, 10, "rotations", 99, ["seen"])
    await store.add(guild, 10, "news", None, [])  # a second topic keeps the role
    await store.add(guild, 11, "rotations", None, [])
    await store.add(user, 20, "news", None, [])

    watches = {watch.channel_id: watch for watch in await store.everywhere()}
    assert set(watches) == {10, 11, 20}
    assert watches[10].topics == {"rotations", "news"}
    assert watches[10].role_id == 99
    # What was due when the watch was added counts as sent.
    assert not watches[10].wants(event("seen"))
    assert watches[10].wants(event("new"))

    for i in range(DELIVERED_PER_TOPIC + 1):
        await store.mark_delivered(watches[11], event(f"e{i}"))
    eleven = await channel(11)
    assert len(eleven.delivered["rotations"]) == DELIVERED_PER_TOPIC
    assert "e0" not in eleven.delivered["rotations"]

    await store.pause(watches[10])
    ten = await channel(10)
    assert ten.paused and not ten.wants(event("new"))
    await store.add(guild, 10, "rotations", None, [])  # adding a topic again resumes it
    assert not (await channel(10)).paused

    assert await store.remove(guild, 10, "news")
    assert not await store.remove(guild, 10, "news")
    ten = await channel(10)
    assert ten.topics == {"rotations"} and "news" not in ten.delivered

    assert await store.remove(guild, 10, "rotations")  # its last topic: the watch goes
    await store.delete(watches[11])
    await store.remove(user, 20, None)
    assert await store.everywhere() == []

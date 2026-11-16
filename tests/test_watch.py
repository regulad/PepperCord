from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

import pytest
from discord import Embed, Forbidden, HTTPException, NotFound
from discord.abc import Messageable

from utils.bots.bot import CustomBot
from utils.database import PCDocument
from utils.watch import (
    DELIVERED_PER_TOPIC,
    FirstSeen,
    Rendered,
    Watch,
    WatchEvent,
    Watcher,
    WatchStore,
)

NOW = datetime(2026, 11, 16, 10, 0, tzinfo=UTC)


def http_error(cls: type[HTTPException], status: int) -> HTTPException:
    return cls(cast(Any, SimpleNamespace(status=status, reason="")), "")


class FakeChannel(Messageable):
    def __init__(
        self, channel_id: int, failures: list[HTTPException] | None = None
    ) -> None:
        self.id = channel_id
        self.failures = failures or []
        self.sent: list[str] = []

    async def send(self, content: Any = None, **kwargs: Any) -> Any:
        if self.failures:
            raise self.failures.pop(0)
        self.sent.append(content)

    async def _get_channel(self) -> Any:
        return self


class FakeBot:
    def __init__(self, channels: list[FakeChannel]) -> None:
        self.channels = {channel.id: channel for channel in channels}

    def get_channel(self, channel_id: int) -> FakeChannel | None:
        return self.channels.get(channel_id)

    async def fetch_channel(self, channel_id: int) -> FakeChannel:
        raise http_error(NotFound, 404)


class FakeStore(WatchStore):
    """Watches in memory, as WatchStore keeps them in documents."""

    def __init__(self, entries: dict[int, dict[str, Any]]) -> None:
        super().__init__(cast(CustomBot, None), "test")
        self.entries = entries
        self.reads = 0

    async def everywhere(self) -> list[Watch]:
        self.reads += 1
        return [
            Watch(
                document=cast(PCDocument, None),
                channel_id=channel_id,
                topics=frozenset(entry["topics"]),
                role_id=None,
                paused=entry.get("paused", False),
                delivered={
                    topic: frozenset(keys)
                    for topic, keys in entry.get("delivered", {}).items()
                },
            )
            for channel_id, entry in self.entries.items()
        ]

    async def mark_delivered(self, watch: Watch, event: WatchEvent) -> None:
        keys = (
            self.entries[watch.channel_id]
            .setdefault("delivered", {})
            .setdefault(event.topic, [])
        )
        keys.append(event.key)
        del keys[:-DELIVERED_PER_TOPIC]

    async def pause(self, watch: Watch) -> None:
        self.entries[watch.channel_id]["paused"] = True

    async def delete(self, watch: Watch) -> None:
        del self.entries[watch.channel_id]


class FakeSource:
    namespace = "test"
    name = "Test"
    topics = {"rotations": "Each new rotation", "news": "News"}

    def __init__(self, events: list[WatchEvent]) -> None:
        self.list = events
        self.renders = 0

    def events(self, now: datetime) -> list[WatchEvent]:
        return self.list


def event(
    key: str,
    topic: str = "rotations",
    at: datetime = NOW,
    source: FakeSource | None = None,
) -> WatchEvent:
    async def render() -> Rendered:
        if source is not None:
            source.renders += 1
        return Rendered(f"posted {key}", Embed(title=key))

    return WatchEvent.dated(key, topic, at, render)


def watcher(
    source: FakeSource, store: FakeStore, channels: list[FakeChannel]
) -> Watcher:
    return Watcher(cast(CustomBot, FakeBot(channels)), source, store)


def test_an_event_is_due_from_when_it_happens_until_it_expires() -> None:
    dated = event("rotation", at=NOW)

    assert not dated.is_due(NOW - timedelta(seconds=1))
    assert dated.is_due(NOW)
    assert not dated.is_due(NOW + timedelta(hours=2))
    assert WatchEvent.dated(
        "short", "rotations", NOW, dated.render, ends=NOW + timedelta(minutes=5)
    ).expires == (NOW + timedelta(minutes=5))


async def test_posts_each_event_once_to_each_watch_that_wants_it() -> None:
    source = FakeSource([])
    source.list = [event("a", source=source), event("b", "news", source=source)]
    store = FakeStore(
        {
            1: {"topics": ["rotations"]},
            2: {"topics": ["rotations", "news"]},
            3: {"topics": ["other"]},
        }
    )
    channels = [FakeChannel(1), FakeChannel(2), FakeChannel(3)]
    posting = watcher(source, store, channels)

    await posting.dispatch(NOW)

    assert [channel.sent for channel in channels] == [
        ["posted a"],
        ["posted a", "posted b"],
        [],
    ]
    assert source.renders == 2  # once per event, however many channels get it
    assert store.entries[2]["delivered"] == {"rotations": ["a"], "news": ["b"]}

    # Both events are settled, so the next minute neither reads watches nor posts.
    await posting.dispatch(NOW + timedelta(minutes=1))
    assert store.reads == 1

    # A restart forgets what's settled, but each watch remembers what it was sent.
    await watcher(source, store, channels).dispatch(NOW + timedelta(minutes=2))
    assert [len(channel.sent) for channel in channels] == [1, 2, 0]


async def test_skips_events_that_are_not_due() -> None:
    source = FakeSource(
        [
            event("old", at=NOW - timedelta(hours=3)),
            event("soon", at=NOW + timedelta(minutes=1)),
        ]
    )
    store = FakeStore({1: {"topics": ["rotations"]}})
    channel = FakeChannel(1)

    await watcher(source, store, [channel]).dispatch(NOW)

    assert channel.sent == []
    assert store.reads == 0


async def test_pauses_a_watch_it_may_not_post_to_and_removes_one_whose_channel_is_gone() -> (
    None
):
    source = FakeSource([event("a"), event("b", at=NOW + timedelta(seconds=1))])
    store = FakeStore(
        {
            1: {"topics": ["rotations"]},
            2: {"topics": ["rotations"]},
            3: {"topics": ["rotations"]},
        }
    )
    blocked = FakeChannel(1, [http_error(Forbidden, 403)])
    fine = FakeChannel(3)
    posting = watcher(source, store, [blocked, fine])  # channel 2 was deleted

    await posting.dispatch(NOW + timedelta(seconds=1))

    assert store.entries[1]["paused"] is True
    assert 2 not in store.entries
    assert blocked.sent == []  # not tried again for the second event
    assert fine.sent == ["posted a", "posted b"]

    # A paused watch gets nothing until it's resumed.
    source.list.append(event("c", at=NOW + timedelta(seconds=2)))
    await posting.dispatch(NOW + timedelta(seconds=2))
    assert blocked.sent == []


async def test_tries_a_failed_post_again_next_minute() -> None:
    source = FakeSource([event("a")])
    store = FakeStore({1: {"topics": ["rotations"]}})
    flaky = FakeChannel(1, [http_error(HTTPException, 500)])
    posting = watcher(source, store, [flaky])

    await posting.dispatch(NOW)
    assert flaky.sent == []

    await posting.dispatch(NOW + timedelta(minutes=1))
    assert flaky.sent == ["posted a"]


async def test_an_event_that_cannot_render_is_not_tried_again() -> None:
    async def broken() -> Rendered:
        raise ValueError("no")

    source = FakeSource([WatchEvent.dated("a", "rotations", NOW, broken)])
    store = FakeStore({1: {"topics": ["rotations"]}})
    posting = watcher(source, store, [FakeChannel(1)])

    await posting.dispatch(NOW)
    await posting.dispatch(NOW + timedelta(minutes=1))

    assert store.reads == 1


def test_first_seen_remembers_when_each_key_was_first_noticed() -> None:
    first_seen = FirstSeen()

    assert first_seen("a", NOW) == NOW
    assert first_seen("a", NOW + timedelta(hours=1)) == NOW

    first_seen.forget_all_but(["b"])
    assert first_seen("a", NOW + timedelta(hours=1)) == NOW + timedelta(hours=1)


@pytest.mark.parametrize("delivered", [0, DELIVERED_PER_TOPIC + 5])
async def test_a_watch_remembers_only_the_latest_events_per_topic(
    delivered: int,
) -> None:
    source = FakeSource(
        [event(f"e{i}", at=NOW + timedelta(seconds=i)) for i in range(delivered)]
    )
    store = FakeStore({1: {"topics": ["rotations"]}})

    await watcher(source, store, [FakeChannel(1)]).dispatch(
        NOW + timedelta(seconds=delivered)
    )

    assert len(store.entries[1].get("delivered", {}).get("rotations", [])) == min(
        delivered, DELIVERED_PER_TOPIC
    )

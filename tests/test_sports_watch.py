"""LeagueWatcher posting games and sending their threads updates, against fake Discord channels and an in-memory store,
and LeagueWatchStore against a real MongoDB when PEPPERCORD_TEST_MONGO_URI names one, as in test_watch_store.py.
"""

import os
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from itertools import count
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from aioespn import ESPNClient, Event, Play, Scoreboard, State, Summary
from aioespn.scoreboard import Status, StatusType
from aioespn.summary import SummaryHeader
from discord import Embed, Forbidden, Guild, HTTPException, NotFound, TextChannel
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from utils.bots.bot import CustomBot
from utils.database import PCDocument, PCInternalDocument
from utils.sports_watch import (
    DELIVERED_PER_GAME,
    LeagueWatch,
    LeagueWatcher,
    LeagueWatchStore,
    PostedGame,
)

FIXTURES = Path(__file__).parent / "fixtures" / "espn"
G_LEAGUE = "basketball/nba-development"
MLB = "baseball/mlb"
CHANNEL = 10


def http_error(cls: type[HTTPException], status: int) -> HTTPException:
    return cls(cast(Any, SimpleNamespace(status=status, reason="")), "")


def scoreboard(name: str) -> Scoreboard:
    return Scoreboard.model_validate_json(
        (FIXTURES / f"scoreboard-{name}.json").read_bytes()
    )


def live_game() -> Event:
    """A G League game in its third quarter: tipped off, with two quarters ended."""
    return scoreboard("basketball-nba-development-live").events[0]


def scheduled(event: Event, starts: datetime) -> Event:
    status = Status(
        period=0,
        type=StatusType(
            name="STATUS_SCHEDULED", state=State.PRE, description="Scheduled"
        ),
    )
    competitions = tuple(
        c.model_copy(update={"status": status}) for c in event.competitions
    )
    return event.model_copy(
        update={"status": status, "competitions": competitions, "date": starts}
    )


NOW = live_game().date


class FakeThread:
    def __init__(self, thread_id: int) -> None:
        self.id = thread_id
        self.sent: list[Embed] = []
        self.lines: list[str] = []
        self.failures: list[HTTPException] = []

    async def send(self, content: str, *, embed: Embed, **kwargs: Any) -> None:
        if self.failures:
            raise self.failures.pop(0)
        self.sent.append(embed)
        self.lines.append(content)

    @property
    def titles(self) -> list[str | None]:
        return [embed.title for embed in self.sent]


class FakeMessage:
    def __init__(self, bot: "FakeBot", message_id: int) -> None:
        self.bot = bot
        self.id = message_id

    async def create_thread(
        self, *, name: str, auto_archive_duration: int
    ) -> FakeThread:
        if self.bot.thread_failures:
            raise self.bot.thread_failures.pop(0)
        thread = FakeThread(next(self.bot.ids))
        self.bot.threads[thread.id] = thread
        self.bot.thread_names[thread.id] = name
        return thread


class FakeRole:
    id = 5
    mention = "<@&5>"


class FakeGuild:
    def get_role(self, role_id: int) -> FakeRole | None:
        return FakeRole() if role_id == FakeRole.id else None


class FakeChannel(TextChannel):
    """A text channel that keeps what it's sent. TextChannel's own constructor needs a connection to Discord."""

    def __init__(self, bot: "FakeBot", channel_id: int) -> None:
        self.id = channel_id
        self.guild = cast(Guild, FakeGuild())
        self.bot = bot
        self.sent: list[tuple[str | None, Embed, Any]] = []
        self.failures: list[HTTPException] = []

    async def send(self, content: Any = None, **kwargs: Any) -> Any:
        if self.failures:
            raise self.failures.pop(0)
        self.sent.append((content, kwargs["embed"], kwargs.get("allowed_mentions")))
        return FakeMessage(self.bot, next(self.bot.ids))

    def get_partial_message(self, message_id: int, /) -> Any:
        return FakeMessage(self.bot, message_id)


class FakeBot:
    def __init__(self) -> None:
        self.ids = count(1000)
        self.channels: dict[int, FakeChannel] = {}
        self.threads: dict[int, FakeThread] = {}
        self.thread_names: dict[int, str] = {}
        self.thread_failures: list[HTTPException] = []

    def get_channel(self, channel_id: int) -> FakeChannel | None:
        return self.channels.get(channel_id)

    async def fetch_channel(self, channel_id: int) -> FakeChannel:
        raise http_error(NotFound, 404)

    def get_custom_emoji(self, name: str) -> Any:
        return SimpleNamespace(url=f"https://cdn.discordapp.com/emojis/{name}.png")

    def get_partial_messageable(
        self, thread_id: int, *, type: Any = None
    ) -> FakeThread:
        return self.threads.setdefault(thread_id, FakeThread(thread_id))


class FakeClient:
    """Serves set scoreboards and summaries, and counts the requests."""

    def __init__(self) -> None:
        self.boards: dict[str, Scoreboard] = {}
        self.dated: dict[tuple[str, date], Scoreboard] = {}
        self.summaries: dict[str, Summary] = {}
        self.requests: list[tuple[str, str, object]] = []

    async def scoreboard(
        self, sport: str, slug: str, *, dates: date | None = None
    ) -> Scoreboard:
        key = f"{sport}/{slug}"
        self.requests.append(("scoreboard", key, dates))
        if dates is not None:
            return self.dated.get((key, dates), Scoreboard())
        return self.boards.get(key, Scoreboard())

    async def summary(self, sport: str, slug: str, event_id: str) -> Summary:
        self.requests.append(("summary", f"{sport}/{slug}", event_id))
        # A game without a set summary has one with no plays, as a game just begun does.
        return self.summaries.get(event_id, Summary(header=SummaryHeader(id=event_id)))


class FakeStore(LeagueWatchStore):
    """Watches in memory, as LeagueWatchStore keeps them in guild documents."""

    def __init__(self, entries: dict[int, dict[str, Any]]) -> None:
        super().__init__(cast(CustomBot, None))
        self.entries = entries

    async def everywhere(self) -> list[LeagueWatch]:
        return [
            LeagueWatch(
                document=cast(PCDocument, None),
                channel_id=channel_id,
                leagues=frozenset(entry["leagues"]),
                role_id=entry.get("role"),
                paused=entry.get("paused", False),
                games={
                    k: PostedGame.from_entry(v)
                    for k, v in entry.get("games", {}).items()
                },
            )
            for channel_id, entry in self.entries.items()
        ]

    def game(self, event_id: str, channel_id: int = CHANNEL) -> dict[str, Any]:
        return cast(dict[str, Any], self.entries[channel_id]["games"][event_id])

    async def record_game(
        self, watch: LeagueWatch, event_id: str, game: PostedGame
    ) -> None:
        self.entries[watch.channel_id].setdefault("games", {})[event_id] = game.entry()

    async def mark_delivered(
        self, watch: LeagueWatch, event_id: str, keys: Any
    ) -> None:
        self.game(event_id, watch.channel_id)["delivered"] += list(keys)

    async def set_thread(
        self, watch: LeagueWatch, event_id: str, thread_id: int
    ) -> None:
        self.game(event_id, watch.channel_id)["thread"] = thread_id

    async def close_game(self, watch: LeagueWatch, event_id: str) -> None:
        self.game(event_id, watch.channel_id)["closed"] = True

    async def forget(self, watch: LeagueWatch, event_ids: Any) -> None:
        for event_id in event_ids:
            del self.entries[watch.channel_id]["games"][event_id]

    async def pause(self, watch: LeagueWatch) -> None:
        self.entries[watch.channel_id]["paused"] = True

    async def delete(self, watch: LeagueWatch) -> None:
        del self.entries[watch.channel_id]


def setup(
    *leagues: str, games: dict[str, Any] | None = None, role: int | None = None
) -> tuple[LeagueWatcher, FakeBot, FakeClient, FakeStore]:
    bot = FakeBot()
    bot.channels[CHANNEL] = FakeChannel(bot, CHANNEL)
    client = FakeClient()
    store = FakeStore(
        {CHANNEL: {"leagues": list(leagues), "role": role, "games": games or {}}}
    )
    watcher = LeagueWatcher(
        cast(CustomBot, bot), cast(ESPNClient, client), lambda: None, store
    )
    return watcher, bot, client, store


def posted(
    event_id: str,
    league: str,
    thread: int | None,
    at: datetime,
    *delivered: str,
    starts: datetime | None = None,
) -> dict[str, Any]:
    game = PostedGame(league, 1, thread, at, starts, False, frozenset(delivered))
    return {event_id: game.entry()}


async def test_posts_a_game_before_it_starts_and_then_its_updates() -> None:
    watcher, bot, client, store = setup(G_LEAGUE)
    game = live_game()
    client.boards[G_LEAGUE] = Scoreboard(
        events=(scheduled(game, NOW + timedelta(hours=2)),)
    )
    await watcher.dispatch(NOW)
    assert bot.channels[CHANNEL].sent == []  # not due yet

    client.boards[G_LEAGUE] = Scoreboard(
        events=(scheduled(game, NOW + timedelta(minutes=30)),)
    )
    await watcher.dispatch(NOW)
    [(content, embed, _)] = bot.channels[CHANNEL].sent
    assert content is None and embed.title == game.name
    assert embed.footer.icon_url == "https://cdn.discordapp.com/emojis/espn.png"
    [(thread_id, name)] = bot.thread_names.items()
    assert name == "RAP @ CAP"
    assert bot.threads[thread_id].sent == []
    assert store.game(game.id)["thread"] == thread_id

    client.boards[G_LEAGUE] = Scoreboard(events=(game,))
    await watcher.dispatch(NOW + timedelta(hours=1))
    assert bot.threads[thread_id].titles == [
        "Tip-off",
        "End of the 1st quarter",
        "Halftime",
    ]
    assert bot.threads[thread_id].lines == [
        "RAP 0 – 0 CAP; Tip-off",
        "RAP 33 – 22 CAP; End of 1st",
        "RAP 65 – 59 CAP; Halftime",
    ]
    assert set(store.game(game.id)["delivered"]) == {"start", "period:1", "period:2"}

    # Nothing new: nothing sent, and the game isn't posted again.
    await watcher.dispatch(NOW + timedelta(hours=1, minutes=1))
    assert len(bot.threads[thread_id].sent) == 3
    assert len(bot.channels[CHANNEL].sent) == 1


async def test_joins_a_game_under_way_where_it_stands() -> None:
    watcher, bot, client, store = setup(G_LEAGUE)
    game = live_game()
    client.boards[G_LEAGUE] = Scoreboard(events=(game,))
    await watcher.dispatch(NOW)
    [thread] = bot.threads.values()
    # What came before is skipped: the thread says only where the game stands.
    assert thread.titles == ["Under way"]
    assert thread.lines == ["RAP 74 – 61 CAP; 9:49 - 3rd"]
    assert set(store.game(game.id)["delivered"]) == {
        "start",
        "period:1",
        "period:2",
        "joined",
    }
    await watcher.dispatch(NOW + timedelta(minutes=1))
    assert len(thread.sent) == 1


async def test_mentions_the_role() -> None:
    watcher, bot, client, _ = setup(G_LEAGUE, role=FakeRole.id)
    client.boards[G_LEAGUE] = Scoreboard(events=(live_game(),))
    await watcher.dispatch(NOW)
    [(content, _, mentions)] = bot.channels[CHANNEL].sent
    assert content == FakeRole.mention
    assert [role.id for role in mentions.roles] == [FakeRole.id]


async def test_pauses_a_watch_it_may_not_post_in() -> None:
    watcher, bot, client, store = setup(G_LEAGUE)
    client.boards[G_LEAGUE] = Scoreboard(events=(live_game(),))
    bot.channels[CHANNEL].failures.append(http_error(Forbidden, 403))
    await watcher.dispatch(NOW)
    assert store.entries[CHANNEL]["paused"] and store.entries[CHANNEL]["games"] == {}
    await watcher.dispatch(NOW + timedelta(minutes=1))
    assert bot.channels[CHANNEL].sent == []  # paused watches post nothing


async def test_pauses_a_watch_it_may_not_open_threads_in() -> None:
    watcher, bot, client, store = setup(G_LEAGUE)
    game = live_game()
    client.boards[G_LEAGUE] = Scoreboard(events=(game,))
    bot.thread_failures.append(http_error(Forbidden, 403))
    await watcher.dispatch(NOW)
    # The message went out, so the game is kept, to be posted only once.
    assert store.entries[CHANNEL]["paused"] and store.game(game.id)["thread"] is None


async def test_removes_the_watch_of_a_deleted_channel() -> None:
    watcher, bot, client, store = setup(G_LEAGUE)
    client.boards[G_LEAGUE] = Scoreboard(events=(live_game(),))
    del bot.channels[CHANNEL]
    await watcher.dispatch(NOW)
    assert store.entries == {}


async def test_stops_a_game_whose_thread_is_gone() -> None:
    game = live_game()
    watcher, bot, client, store = setup(
        G_LEAGUE, games=posted(game.id, G_LEAGUE, 77, NOW, "start")
    )
    client.boards[G_LEAGUE] = Scoreboard(events=(game,))
    bot.get_partial_messageable(77).failures.append(http_error(NotFound, 404))
    await watcher.dispatch(NOW)
    assert store.game(game.id)["closed"]
    await watcher.dispatch(NOW + timedelta(minutes=1))
    assert bot.threads[77].sent == []


async def test_opens_a_thread_that_failed_to_open() -> None:
    watcher, bot, client, store = setup(G_LEAGUE)
    game = live_game()
    client.boards[G_LEAGUE] = Scoreboard(events=(scheduled(game, NOW),))
    bot.thread_failures.append(http_error(HTTPException, 500))
    await watcher.dispatch(NOW)
    assert store.game(game.id)["thread"] is None and not store.entries[CHANNEL].get(
        "paused"
    )

    client.boards[G_LEAGUE] = Scoreboard(events=(game,))
    await watcher.dispatch(NOW + timedelta(minutes=1))
    [(thread_id, thread)] = bot.threads.items()
    assert store.game(game.id)["thread"] == thread_id
    assert thread.titles == ["Tip-off", "End of the 1st quarter", "Halftime"]


async def test_retries_an_update_that_failed_to_send() -> None:
    game = live_game()
    watcher, bot, client, store = setup(
        G_LEAGUE, games=posted(game.id, G_LEAGUE, 77, NOW, "start")
    )
    client.boards[G_LEAGUE] = Scoreboard(events=(game,))
    thread = bot.get_partial_messageable(77)
    thread.failures.append(http_error(HTTPException, 500))
    await watcher.dispatch(NOW)
    assert thread.sent == [] and store.game(game.id)["delivered"] == ["start"]
    await watcher.dispatch(NOW + timedelta(minutes=1))
    assert thread.titles == ["End of the 1st quarter", "Halftime"]


async def test_forgets_games_once_off_the_scoreboard() -> None:
    games = {
        **posted("1", G_LEAGUE, 77, NOW - timedelta(hours=19), "start", "final"),
        **posted("2", G_LEAGUE, 78, NOW - timedelta(hours=1), "start", "final"),
        **posted("3", "basketball/nba", 79, NOW, "start"),  # a league no longer watched
    }
    watcher, _, client, store = setup(G_LEAGUE, games=games)
    client.boards[G_LEAGUE] = Scoreboard(events=(live_game(),))
    await watcher.dispatch(NOW)
    assert set(store.entries[CHANNEL]["games"]) == {"2", live_game().id}


async def test_follows_a_game_that_left_the_scoreboard_unfinished() -> None:
    game = live_game()
    starts = datetime(
        2026, 11, 17, 3, 30, tzinfo=UTC
    )  # 10:30 PM in New York, on the 16th
    watcher, bot, client, store = setup(
        G_LEAGUE, games=posted(game.id, G_LEAGUE, 77, NOW, "start", starts=starts)
    )
    client.dated[(G_LEAGUE, date(2026, 11, 16))] = Scoreboard(events=(game,))
    await watcher.dispatch(NOW)
    assert ("scoreboard", G_LEAGUE, date(2026, 11, 16)) in client.requests
    assert bot.threads[77].titles == ["End of the 1st quarter", "Halftime"]
    assert game.id in store.entries[CHANNEL]["games"]


async def test_fetches_a_summary_only_when_the_game_moves_on() -> None:
    game = scoreboard("baseball-mlb").events[0]
    summary = Summary.model_validate_json(
        (FIXTURES / "summary-baseball-mlb.json").read_bytes()
    )
    watcher, bot, client, store = setup(
        MLB, games=posted(game.id, MLB, 77, NOW, "start")
    )
    client.boards[MLB] = Scoreboard(events=(game,))
    client.summaries[game.id] = summary
    await watcher.dispatch(NOW)
    titles = bot.threads[77].titles
    assert len(titles) == 6 and titles[-1] == "Final"
    assert all(
        title is not None and title.startswith("Play Result") for title in titles[:5]
    )

    await watcher.dispatch(NOW + timedelta(minutes=1))
    assert [request for request in client.requests if request[0] == "summary"] == [
        ("summary", MLB, game.id)
    ]
    assert len(bot.threads[77].sent) == 6


async def test_fetches_a_live_games_summary_every_minute() -> None:
    # A foul or a penalty doesn't change the scoreboard, so a game under way is read again each minute regardless.
    game = live_game()
    watcher, _, client, _ = setup(
        G_LEAGUE, games=posted(game.id, G_LEAGUE, 77, NOW, "start")
    )
    client.boards[G_LEAGUE] = Scoreboard(events=(game,))
    await watcher.dispatch(NOW)
    await watcher.dispatch(NOW + timedelta(minutes=1))
    assert [r for r in client.requests if r[0] == "summary"] == [
        ("summary", G_LEAGUE, game.id)
    ] * 2


NHL = "hockey/nhl"


def hockey(montreal: int, rangers: int = 0) -> Event:
    """Montreal at the Rangers, under way, with this score."""
    game = scoreboard("hockey-nhl").events[0]
    status = Status(
        period=2,
        display_clock="12:00",
        type=StatusType(
            name="STATUS_IN_PROGRESS", state=State.IN, short_detail="12:00 - 2nd"
        ),
    )
    scores = {"10": str(montreal), "13": str(rangers)}
    competition = game.competitions[0]
    competitors = tuple(
        c.model_copy(update={"score": scores[c.id]}) for c in competition.competitors
    )
    competition = competition.model_copy(
        update={"status": status, "competitors": competitors}
    )
    return game.model_copy(update={"status": status, "competitions": (competition,)})


def goal_summary(event_id: str, *, goal: bool) -> Summary:
    plays = (
        Play.model_validate_json(
            """{"id": "401892726000005550", "type": {"id": "505", "text": "Goal"},
                "text": "Phillip Danault Goal (3) Tip-In, assists: Lane Hutson (16)", "awayScore": 1,
                "homeScore": 0, "period": {"number": 2}, "clock": {"displayValue": "7:59"},
                "scoringPlay": true, "scoreValue": 1, "team": {"id": "10"}}"""
        ),
    )
    return Summary(header=SummaryHeader(id=event_id), plays=plays if goal else ())


async def test_says_when_a_goal_is_called_back() -> None:
    game = hockey(1)
    watcher, bot, client, _ = setup(NHL, games=posted(game.id, NHL, 77, NOW, "start"))
    client.boards[NHL] = Scoreboard(events=(game,))
    client.summaries[game.id] = goal_summary(game.id, goal=True)
    await watcher.dispatch(NOW)
    thread = bot.threads[77]
    assert thread.lines == ["MTL 1 – 0 NYR; 7:59 - 2nd"]

    # A review takes the goal back: ESPN drops it from the play-by-play, and Montreal's score falls.
    client.boards[NHL] = Scoreboard(events=(hockey(0),))
    client.summaries[game.id] = goal_summary(game.id, goal=False)
    await watcher.dispatch(NOW + timedelta(minutes=1))
    assert (
        len(thread.lines) == 1
    )  # not until the score has stayed down for a second check
    await watcher.dispatch(NOW + timedelta(minutes=2))
    assert thread.titles[-1] == "Goal called back: Montreal Canadiens"
    assert thread.lines[-1] == (
        "MTL 0 – 0 NYR; 12:00 - 2nd\nCalled back: Phillip Danault Goal (3) Tip-In, assists: Lane Hutson (16)"
    )
    await watcher.dispatch(NOW + timedelta(minutes=3))
    assert len(thread.lines) == 2


async def test_takes_a_one_minute_blip_in_the_score_for_nothing() -> None:
    game = hockey(1)
    watcher, bot, client, _ = setup(NHL, games=posted(game.id, NHL, 77, NOW, "start"))
    client.summaries[game.id] = goal_summary(game.id, goal=True)
    for minute, montreal in enumerate((1, 0, 1, 1)):
        client.boards[NHL] = Scoreboard(events=(hockey(montreal),))
        await watcher.dispatch(NOW + timedelta(minutes=minute))
    assert bot.threads[77].lines == ["MTL 1 – 0 NYR; 7:59 - 2nd"]


async def test_forgets_a_game_posted_before_it_had_a_date() -> None:
    # A game with no teams yet, which ESPN dates 1993, as a watch could post before it knew better.
    board = scoreboard("football-college-football-2026")
    undecided = next(e for e in board.events if e.short_name == "TBD @ TBD")
    league = "football/college-football"
    watcher, bot, client, store = setup(
        league, games=posted(undecided.id, league, 77, NOW, "start")
    )
    client.boards[league] = board
    await watcher.dispatch(NOW)
    assert undecided.id not in store.entries[CHANNEL]["games"]
    # Nor is it posted again until ESPN gives it a date.
    await watcher.dispatch(NOW + timedelta(minutes=1))
    assert undecided.id not in store.entries[CHANNEL]["games"]
    assert all(
        "TBD" not in (embed.title or "") for _, embed, _ in bot.channels[CHANNEL].sent
    )


async def test_posts_nothing_for_paused_watches_but_still_forgets() -> None:
    games = posted("1", G_LEAGUE, 77, NOW - timedelta(days=30), "start")
    watcher, bot, client, store = setup(G_LEAGUE, games=games)
    store.entries[CHANNEL]["paused"] = True
    client.boards[G_LEAGUE] = Scoreboard(events=(live_game(),))
    await watcher.dispatch(NOW)
    assert bot.channels[CHANNEL].sent == [] and store.entries[CHANNEL]["games"] == {}
    assert client.requests == []  # no league is fetched for paused watches alone


# LeagueWatchStore against MongoDB.

MONGO_URI = os.environ.get("PEPPERCORD_TEST_MONGO_URI")
needs_mongo = pytest.mark.skipif(
    MONGO_URI is None, reason="set PEPPERCORD_TEST_MONGO_URI to run against MongoDB"
)


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
    """Sees no guilds, so the store wraps each document itself."""

    def __init__(self, ddb: AsyncDatabase[PCInternalDocument]) -> None:
        self.ddb = ddb

    def get_guild(self, guild_id: int) -> None:
        return None


@needs_mongo
async def test_store_keeps_watches_and_their_games(
    ddb: AsyncDatabase[PCInternalDocument],
) -> None:
    store = LeagueWatchStore(cast(CustomBot, Bot(ddb)))
    guild = await PCDocument.get_document(ddb["guild"], {"_id": 1})

    async def watch(channel_id: int) -> LeagueWatch:
        fresh = await PCDocument.get_document(ddb["guild"], {"_id": 1})
        return next(
            w for w in await store.in_document(fresh) if w.channel_id == channel_id
        )

    await store.add(guild, 10, "soccer/eng.1", 99)
    await store.add(guild, 10, "football/nfl", None)  # a second league keeps the role
    await store.add(guild, 11, "soccer/eng.1", None)
    watches = {w.channel_id: w for w in await store.everywhere()}
    assert set(watches) == {10, 11}
    assert (
        watches[10].leagues == {"soccer/eng.1", "football/nfl"}
        and watches[10].role_id == 99
    )

    game = PostedGame("soccer/eng.1", 500, None, NOW, NOW, False, frozenset({"start"}))
    await store.record_game(watches[10], "401", game)
    assert (await watch(10)).games["401"] == game
    await store.set_thread(watches[10], "401", 600)
    await store.mark_delivered(
        watches[10], "401", [f"play:{i}" for i in range(DELIVERED_PER_GAME)]
    )
    stored = (await watch(10)).games["401"]
    assert stored.thread_id == 600
    assert (
        len(stored.delivered) == DELIVERED_PER_GAME and "start" not in stored.delivered
    )
    await store.close_game(watches[10], "401")
    assert (await watch(10)).games["401"].closed
    await store.forget(watches[10], ["401"])
    assert (await watch(10)).games == {}

    await store.pause(watches[10])
    assert (await watch(10)).paused
    await store.add(
        guild, 10, "soccer/eng.1", None
    )  # adding a league again resumes the watch
    assert not (await watch(10)).paused

    assert await store.remove(guild, 10, "football/nfl")
    assert not await store.remove(guild, 10, "football/nfl")
    assert (await watch(10)).leagues == {"soccer/eng.1"}
    assert await store.remove(
        guild, 10, "soccer/eng.1"
    )  # its last league: the watch goes
    await store.delete(watches[11])
    assert await store.everywhere() == []

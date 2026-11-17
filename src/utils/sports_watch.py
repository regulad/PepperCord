"""League watches: a channel's standing request to be sent each of a league's games as one message, with a thread under
it that is sent the game's updates, such as each score, as it's played.

The message says only who is playing, when and where, and is never edited, so someone avoiding the score can keep the
channel and skip the thread. A :class:`LeagueWatcher` checks the watched leagues' scoreboards every minute: it posts each
game an hour before it starts, or as soon as it notices one under way, and sends each thread what's new.

Watches live in the guild's document under ``sports_watches.<channel id>``:

    {"leagues": ["football/nfl", ...], "role": <role id or null>, "paused": false,
     "games": {"<event id>": {"league": "football/nfl", "message": <id>, "thread": <id or null>, "posted": <unix time>,
                              "starts": <unix time>, "closed": false, "delivered": [<update keys>]}}}

Each game keeps the keys of the updates its thread was sent, so neither a retry nor a restart sends one twice, and a bot
that was down catches its threads up. A game is forgotten once it drops off its league's scoreboard.
"""

import logging
from asyncio import Semaphore, TaskGroup
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any, Final, cast

import pytz
from aioespn import ESPNClient, Event, Scoreboard, Sport, State, Summary
from aiohttp import ClientError
from discord import (
    AllowedMentions,
    ChannelType,
    Forbidden,
    HTTPException,
    Message,
    NotFound,
    PartialMessage,
    TextChannel,
)
from discord.abc import Messageable
from discord.ext import tasks
from pydantic import ValidationError

from utils.bots.bot import CustomBot
from utils.database import PCDocument, PCInternalDocument
from utils.sports import (
    CREDIT_EMOJI,
    Directory,
    GameUpdate,
    called_back,
    date_known,
    credit,
    game_message,
    game_updates,
    joined_update,
    needs_summary,
    parse_key,
    thread_name,
)

logger = logging.getLogger(__name__)

FIELD: Final = "sports_watches"

PREGAME: Final = timedelta(hours=1)
"""How long before a game starts its message is posted."""

LATE: Final = timedelta(hours=12)
"""How late a game can be, as one held up by the weather is, and still be posted when it's yet to start."""

FORGET_AFTER: Final = timedelta(hours=18)
"""How long after its message a game is kept once it's off its league's scoreboard."""

KEEP_AT_MOST: Final = timedelta(days=21)
"""How long a game is kept at all: long enough for a tennis major."""

DELIVERED_PER_GAME: Final = 500
"""How many of a game's updates are remembered, which a tennis major's matches come closest to."""

SEND_CONCURRENCY: Final = 5
FETCH_CONCURRENCY: Final = 4

EASTERN: Final = pytz.timezone("America/New_York")
"""The time zone ESPN's scoreboards count their days in."""


def _time(value: Any) -> datetime | None:
    return (
        datetime.fromtimestamp(value, UTC) if isinstance(value, (int, float)) else None
    )


@dataclass(frozen=True)
class PostedGame:
    """A game a watch has posted, and what its thread has been sent."""

    league: str
    message_id: int
    thread_id: int | None
    """None until the thread is opened, which is retried should it fail."""
    posted: datetime
    starts: datetime | None
    closed: bool
    """Whether the thread or message is gone, or can't be posted in: the game is sent nothing more."""
    delivered: frozenset[str]

    @property
    def finished(self) -> bool:
        return "final" in self.delivered or any(
            key.startswith("status:") for key in self.delivered
        )

    @classmethod
    def from_entry(cls, entry: Mapping[str, Any]) -> "PostedGame":
        return cls(
            league=str(entry.get("league", "")),
            message_id=int(entry["message"]),
            thread_id=int(entry["thread"]) if entry.get("thread") else None,
            posted=_time(entry.get("posted")) or datetime.fromtimestamp(0, UTC),
            starts=_time(entry.get("starts")),
            closed=bool(entry.get("closed", False)),
            delivered=frozenset(entry.get("delivered", ())),
        )

    def entry(self) -> dict[str, Any]:
        return {
            "league": self.league,
            "message": self.message_id,
            "thread": self.thread_id,
            "posted": self.posted.timestamp(),
            "starts": self.starts.timestamp() if self.starts is not None else None,
            "closed": self.closed,
            "delivered": sorted(self.delivered),
        }


@dataclass(frozen=True)
class LeagueWatch:
    """A channel's watch on one or more leagues."""

    document: PCDocument
    channel_id: int
    leagues: frozenset[str]
    role_id: int | None
    paused: bool
    games: Mapping[str, PostedGame]


class LeagueWatchStore:
    """Reads and writes league watches in guild documents."""

    def __init__(self, bot: CustomBot) -> None:
        self.bot = bot

    @staticmethod
    def _path(channel_id: int, *parts: str) -> str:
        # Channel and event IDs are digits, so they're safe in a field path. League keys, with their dots, are only
        # ever values.
        return ".".join((FIELD, str(channel_id), *parts))

    async def in_document(self, document: PCDocument) -> list[LeagueWatch]:
        entries = cast(dict[str, dict[str, Any]], await document.safe_get(FIELD, {}))
        return [
            LeagueWatch(
                document=document,
                channel_id=int(channel_id),
                leagues=frozenset(entry.get("leagues", ())),
                role_id=entry.get("role"),
                paused=bool(entry.get("paused", False)),
                games={
                    event_id: PostedGame.from_entry(game)
                    for event_id, game in entry.get("games", {}).items()
                },
            )
            for channel_id, entry in entries.items()
        ]

    async def everywhere(self) -> list[LeagueWatch]:
        watches: list[LeagueWatch] = []
        collection = self.bot.ddb.get_collection("guild")
        for raw in await collection.find({FIELD: {"$exists": True}}).to_list(
            length=None
        ):
            watches += await self.in_document(await self._document(raw))
        return watches

    async def _document(self, raw: PCInternalDocument) -> PCDocument:
        # The bot's cached documents reload after each write, so writing through them keeps what commands read current.
        if guild := self.bot.get_guild(raw["_id"]):
            return await self.bot.get_guild_document(guild)
        # A guild the bot left. Wrapped by the query that found it, every write would go to the first document found.
        return raw.wrap(self.bot.ddb.get_collection("guild"), {"_id": raw["_id"]})

    async def add(
        self, document: PCDocument, channel_id: int, league: str, role_id: int | None
    ) -> None:
        """Add a league to a channel's watch, and resume the watch."""
        update: dict[str, Any] = {
            "$addToSet": {self._path(channel_id, "leagues"): league},
            "$set": {self._path(channel_id, "paused"): False},
        }
        if role_id is not None:
            update["$set"][self._path(channel_id, "role")] = role_id
        await document.update_db(update)

    async def remove(
        self, document: PCDocument, channel_id: int, league: str | None
    ) -> bool:
        """Remove a league from a channel's watch, or every league if None. Returns whether there was one to remove."""
        watch = next(
            (w for w in await self.in_document(document) if w.channel_id == channel_id),
            None,
        )
        if watch is None or (league is not None and league not in watch.leagues):
            return False
        if league is None or watch.leagues == {league}:
            await document.update_db({"$unset": {self._path(channel_id): True}})
        else:
            await document.update_db(
                {"$pull": {self._path(channel_id, "leagues"): league}}
            )
        return True

    async def record_game(
        self, watch: LeagueWatch, event_id: str, game: PostedGame
    ) -> None:
        await watch.document.update_db(
            {"$set": {self._path(watch.channel_id, "games", event_id): game.entry()}}
        )

    async def mark_delivered(
        self, watch: LeagueWatch, event_id: str, keys: Iterable[str]
    ) -> None:
        await watch.document.update_db(
            {
                "$push": {
                    self._path(watch.channel_id, "games", event_id, "delivered"): {
                        "$each": list(keys),
                        "$slice": -DELIVERED_PER_GAME,
                    }
                }
            }
        )

    async def set_thread(
        self, watch: LeagueWatch, event_id: str, thread_id: int
    ) -> None:
        await watch.document.update_db(
            {
                "$set": {
                    self._path(watch.channel_id, "games", event_id, "thread"): thread_id
                }
            }
        )

    async def close_game(self, watch: LeagueWatch, event_id: str) -> None:
        await watch.document.update_db(
            {"$set": {self._path(watch.channel_id, "games", event_id, "closed"): True}}
        )

    async def forget(self, watch: LeagueWatch, event_ids: Iterable[str]) -> None:
        paths = {
            self._path(watch.channel_id, "games", event_id): True
            for event_id in event_ids
        }
        if paths:
            await watch.document.update_db({"$unset": paths})

    async def pause(self, watch: LeagueWatch) -> None:
        await watch.document.update_db(
            {"$set": {self._path(watch.channel_id, "paused"): True}}
        )

    async def delete(self, watch: LeagueWatch) -> None:
        await watch.document.update_db({"$unset": {self._path(watch.channel_id): True}})


def should_post(event: Event, now: datetime) -> bool:
    """Whether a game a watch hasn't posted yet is due: it starts within the hour, or it's under way.

    A game yet to start that ESPN has no date for, or that should have started more than :data:`LATE` ago, isn't.
    """
    status = event.current_status
    if status is None:
        return False
    if status.state is State.IN:
        return True
    return (
        status.state is State.PRE
        and date_known(event)
        and -LATE <= event.date - now <= PREGAME
    )


def _live(event: Event) -> bool:
    status = event.current_status
    return status is not None and status.state is State.IN


class _Stopped(Exception):
    """The watch was paused or removed: nothing more is posted for it this minute."""


async def _gather[K, V](
    keys: Iterable[K], fetch: Callable[[K], Awaitable[V]], limit: int
) -> dict[K, V]:
    semaphore = Semaphore(limit)

    async def one(key: K) -> V:
        async with semaphore:
            return await fetch(key)

    async with TaskGroup() as group:
        tasks_by_key = {key: group.create_task(one(key)) for key in keys}
    return {key: task.result() for key, task in tasks_by_key.items()}


class LeagueWatcher:
    """Posts watched leagues' games, and sends their threads updates, checking every minute."""

    def __init__(
        self,
        bot: CustomBot,
        client: ESPNClient,
        directory: Callable[[], Directory | None],
        store: LeagueWatchStore | None = None,
    ) -> None:
        self.bot = bot
        self.client = client
        self.directory = directory
        self.store = store if store is not None else LeagueWatchStore(bot)
        # Each game's latest summary, and the scoreboard's state of the game when its summary last caught up with it,
        # so a finished game's summary is fetched again only when the scoreboard has moved on.
        self._summaries: dict[str, Summary] = {}
        self._summarized: dict[str, tuple[str, ...]] = {}
        # For each game under way: each team's highest score so far, how many checks in a row it has been lower, every
        # scoring play seen, and the scores found to have been taken back, as when a review disallows a goal.
        self._highs: dict[str, dict[str, int]] = {}
        self._lower: dict[tuple[str, str], int] = {}
        self._scores: dict[str, dict[str, GameUpdate]] = {}
        self._called_back: dict[str, list[GameUpdate]] = {}
        self._loop = tasks.loop(minutes=1)(self._tick)

    def start(self) -> None:
        if not self._loop.is_running():
            self._loop.start()

    def stop(self) -> None:
        self._loop.cancel()

    async def _tick(self) -> None:
        # A tasks.loop stops for good on an error it doesn't treat as a dropped connection.
        try:
            await self.dispatch(datetime.now(UTC))
        except Exception:
            logger.exception("Couldn't post sports updates to league watches.")

    # Fetching. ESPN being down or slow is expected now and then, and is logged as a warning rather than reported.

    async def _scoreboard(
        self, league: str, day: date | None = None
    ) -> Scoreboard | None:
        sport, slug = parse_key(league)
        try:
            return await self.client.scoreboard(sport, slug, dates=day)
        except (ClientError, TimeoutError) as error:
            logger.warning(f"Couldn't fetch ESPN's {league} scoreboard: {error!r}")
        except ValidationError:
            logger.exception(f"ESPN's {league} scoreboard isn't shaped as expected.")
        return None

    @staticmethod
    def _state(event: Event) -> tuple[str, ...]:
        status = event.current_status
        competition = event.competition
        scores = [c.score or "" for c in competition.competitors] if competition else []
        if status is None:
            return tuple(scores)
        return (status.type.name, str(status.period), *scores)

    @staticmethod
    def _caught_up(summary: Summary, event: Event) -> bool:
        """Whether the summary has the game as the scoreboard does, and so has every scoring play the scoreboard knows."""
        mine, theirs = summary.competition, event.competition
        if (
            mine is None
            or theirs is None
            or mine.status is None
            or theirs.status is None
        ):
            return False
        if mine.status.type.name != theirs.status.type.name:
            return False
        scores = {c.id: c.score for c in theirs.competitors}
        return all(scores.get(c.id) == c.score for c in mine.competitors)

    async def _summary(self, league: str, event: Event) -> Summary | None:
        state = self._state(event)
        # A game under way moves on without its scoreboard changing, as a penalty or a punt does, so its summary is
        # fetched every minute. A finished game's is fetched until it has caught up with the scoreboard.
        if not _live(event) and self._summarized.get(event.id) == state:
            return self._summaries.get(event.id)
        sport, slug = parse_key(league)
        try:
            summary = await self.client.summary(sport, slug, event.id)
        except (ClientError, TimeoutError) as error:
            logger.warning(
                f"Couldn't fetch ESPN's summary of {league} game {event.id}: {error!r}"
            )
            return self._summaries.get(event.id)
        except ValidationError:
            logger.exception(
                f"ESPN's summary of {league} game {event.id} isn't shaped as expected."
            )
            return self._summaries.get(event.id)
        self._summaries[event.id] = summary
        if self._caught_up(summary, event):
            self._summarized[event.id] = state
        return summary

    async def dispatch(self, now: datetime) -> None:
        watches = await self.store.everywhere()
        active = [watch for watch in watches if not watch.paused]
        leagues = sorted({league for watch in active for league in watch.leagues})
        boards = await _gather(leagues, self._scoreboard, FETCH_CONCURRENCY)

        # A game can drop off its league's scoreboard before it's over, such as a late game once ESPN's day has turned
        # over. A watch that posted it follows it on the scoreboard of the day it started.
        events: dict[str, dict[str, Event]] = {
            league: {event.id: event for event in board.events}
            for league, board in boards.items()
            if board is not None
        }
        missing = {
            (game.league, game.starts.astimezone(EASTERN).date())
            for watch in active
            for event_id, game in watch.games.items()
            if game.league in events
            and event_id not in events[game.league]
            and game.starts is not None
            and not (game.closed or game.finished)
            and now - game.posted <= FORGET_AFTER
        }
        for (league, day), board in (
            await _gather(
                missing, lambda key: self._scoreboard(*key), FETCH_CONCURRENCY
            )
        ).items():
            for event in board.events if board is not None else ():
                events[league].setdefault(event.id, event)

        # Football's, hockey's, baseball's and basketball's plays are only in each game's summary, which is fetched for
        # games under way and for those a watch hasn't sent the end of.
        unfinished = {
            event_id
            for watch in active
            for event_id, game in watch.games.items()
            if not (game.closed or game.finished)
        }
        wanted = {
            event.id: (league, event)
            for league, by_id in events.items()
            for event in by_id.values()
            if needs_summary(parse_key(league)[0], event)
            and (_live(event) or event.id in unfinished)
        }
        summaries = await _gather(
            wanted, lambda event_id: self._summary(*wanted[event_id]), FETCH_CONCURRENCY
        )
        updates = {
            event.id: game_updates(
                parse_key(league)[0],
                parse_key(league)[1],
                event,
                summaries.get(event.id),
            )
            for league, by_id in events.items()
            for event in by_id.values()
        }

        for league, by_id in events.items():
            for event in by_id.values():
                updates[event.id] += self._taken_back(
                    parse_key(league)[0], event, updates[event.id]
                )

        current = {event_id for by_id in events.values() for event_id in by_id}
        self._summaries = {k: v for k, v in self._summaries.items() if k in current}
        self._summarized = {k: v for k, v in self._summarized.items() if k in current}
        self._highs = {k: v for k, v in self._highs.items() if k in current}
        self._lower = {k: v for k, v in self._lower.items() if k[0] in current}
        self._scores = {k: v for k, v in self._scores.items() if k in current}
        self._called_back = {k: v for k, v in self._called_back.items() if k in current}

        semaphore = Semaphore(SEND_CONCURRENCY)

        async def serve(watch: LeagueWatch) -> None:
            async with semaphore:
                try:
                    if not watch.paused:
                        await self._serve(watch, boards, events, updates, now)
                    await self._prune(watch, boards, now)
                except _Stopped:
                    pass
                except Exception:
                    logger.exception(
                        f"Couldn't post sports updates in channel {watch.channel_id}."
                    )

        async with TaskGroup() as group:
            for watch in watches:
                group.create_task(serve(watch))

    def _taken_back(
        self, sport: Sport, event: Event, updates: list[GameUpdate]
    ) -> list[GameUpdate]:
        """The scores taken back in a game under way, as when a review disallows a goal.

        ESPN's play-by-play drops such a goal without a word, so a team's score falling is what shows it. It has to stay
        down for two checks in a row, so a blip in ESPN's scoreboard isn't taken for one. The update names the score
        taken back where this bot has seen it: the latest of the team's scores that took it above where it is now.
        """
        scores = self._scores.setdefault(event.id, {})
        for update in updates:
            if update.team_score is not None:
                scores[update.key] = update
        competition = event.competition
        if _live(event) and competition is not None:
            highs = self._highs.setdefault(event.id, {})
            for side in competition.competitors:
                team = side.team.id if side.team is not None else side.id
                try:
                    score = int(side.score or 0)
                except ValueError:
                    continue
                high = highs.setdefault(team, score)
                if score >= high:
                    highs[team] = score
                    self._lower.pop((event.id, team), None)
                    continue
                lower = self._lower[(event.id, team)] = (
                    self._lower.get((event.id, team), 0) + 1
                )
                if lower < 2:
                    continue
                goal = next(
                    (
                        update
                        for update in reversed(scores.values())
                        if update.team == team
                        and update.team_score is not None
                        and update.team_score > score
                    ),
                    None,
                )
                self._called_back.setdefault(event.id, []).append(
                    called_back(sport, event, team, high, score, goal)
                )
                highs[team] = score
                del self._lower[(event.id, team)]
        return self._called_back.get(event.id, [])

    async def _serve(
        self,
        watch: LeagueWatch,
        boards: Mapping[str, Scoreboard | None],
        events: Mapping[str, Mapping[str, Event]],
        updates: Mapping[str, list[GameUpdate]],
        now: datetime,
    ) -> None:
        channel = await self._channel(watch)

        # The games already posted catch up first, then new games are posted, each in the scoreboard's order.
        for event_id, game in watch.games.items():
            event = events.get(game.league, {}).get(event_id)
            if game.closed or event is None or game.league not in watch.leagues:
                continue
            new = [u for u in updates.get(event_id, ()) if u.key not in game.delivered]
            if new:
                await self._send_updates(watch, channel, event, game, new)

        for league in sorted(watch.leagues):
            board = boards.get(league)
            for event in board.events if board is not None else ():
                if (
                    event.id not in watch.games
                    and event.id.isdigit()
                    and should_post(event, now)
                ):
                    await self._post_game(
                        watch, channel, league, event, updates.get(event.id, []), now
                    )

    async def _channel(self, watch: LeagueWatch) -> TextChannel:
        try:
            channel = self.bot.get_channel(
                watch.channel_id
            ) or await self.bot.fetch_channel(watch.channel_id)
        except NotFound:
            logger.info(
                f"Removed the league watch in channel {watch.channel_id}: the channel is gone."
            )
            await self.store.delete(watch)
            raise _Stopped
        except Forbidden:
            logger.warning(
                f"Paused the league watch in channel {watch.channel_id}: no longer allowed to see it."
            )
            await self.store.pause(watch)
            raise _Stopped
        if not isinstance(channel, TextChannel):
            logger.info(
                f"Removed the league watch in channel {watch.channel_id}: it can't have threads."
            )
            await self.store.delete(watch)
            raise _Stopped
        return channel

    def _thread(self, thread_id: int) -> Messageable:
        # Sending to an archived thread brings it back, so a game's thread needn't be fetched first.
        return self.bot.get_partial_messageable(
            thread_id, type=ChannelType.public_thread
        )

    async def _open_thread(
        self, watch: LeagueWatch, message: Message | PartialMessage, event: Event
    ) -> int | None:
        try:
            thread = await message.create_thread(
                name=thread_name(event), auto_archive_duration=1440
            )
        except NotFound:
            raise  # the message is gone; the caller decides what that means
        except Forbidden:
            logger.warning(
                f"Paused the league watch in channel {watch.channel_id}: no longer allowed to open threads."
            )
            await self.store.pause(watch)
            raise _Stopped
        except HTTPException:
            logger.exception(
                f"Couldn't open a thread for game {event.id} in channel {watch.channel_id}."
            )
            return None
        return thread.id

    async def _post_game(
        self,
        watch: LeagueWatch,
        channel: TextChannel,
        league: str,
        event: Event,
        updates: list[GameUpdate],
        now: datetime,
    ) -> None:
        directory = self.directory()
        embed = game_message(
            event, directory.league(league) if directory is not None else None
        )
        emoji = self.bot.get_custom_emoji(CREDIT_EMOJI)
        embed = credit(embed, emoji.url if emoji is not None else None)
        content = None
        mentions = AllowedMentions.none()
        # A role deleted since the watch was set up is skipped, rather than mentioned as "@deleted-role".
        role = channel.guild.get_role(watch.role_id) if watch.role_id else None
        if role is not None:
            content = role.mention
            mentions = AllowedMentions(everyone=False, users=False, roles=[role])
        try:
            message = await channel.send(
                content, embed=embed, allowed_mentions=mentions
            )
        except NotFound:
            logger.info(
                f"Removed the league watch in channel {watch.channel_id}: the channel is gone."
            )
            await self.store.delete(watch)
            raise _Stopped
        except Forbidden:
            logger.warning(
                f"Paused the league watch in channel {watch.channel_id}: no longer allowed to post."
            )
            await self.store.pause(watch)
            raise _Stopped
        except HTTPException:
            logger.exception(
                f"Couldn't post game {event.id} in channel {watch.channel_id}."
            )
            return

        # A game posted while under way starts its thread from where the game stands, rather than with all that came
        # before.
        game = PostedGame(
            league,
            message.id,
            None,
            now,
            event.date,
            False,
            frozenset(u.key for u in updates),
        )
        try:
            thread_id = await self._open_thread(watch, message, event)
        except NotFound:
            thread_id, game = None, replace(
                game, closed=True
            )  # the message was deleted at once
        except _Stopped:
            await self.store.record_game(watch, event.id, game)
            raise
        if thread_id is not None:
            game = replace(game, thread_id=thread_id)
            if (joined := joined_update(parse_key(league)[0], event)) is not None:
                try:
                    await self._thread(thread_id).send(
                        joined.line,
                        embed=joined.embed(),
                        allowed_mentions=AllowedMentions.none(),
                    )
                    game = replace(game, delivered=game.delivered | {joined.key})
                except HTTPException:
                    logger.warning(
                        f"Couldn't say where game {event.id} stands in its thread."
                    )
        await self.store.record_game(watch, event.id, game)

    async def _send_updates(
        self,
        watch: LeagueWatch,
        channel: TextChannel,
        event: Event,
        game: PostedGame,
        new: list[GameUpdate],
    ) -> None:
        thread_id = game.thread_id
        if thread_id is None:
            try:
                thread_id = await self._open_thread(
                    watch, channel.get_partial_message(game.message_id), event
                )
            except NotFound:
                logger.info(
                    f"Stopped game {event.id}'s updates in channel {watch.channel_id}: its message is gone."
                )
                await self.store.close_game(watch, event.id)
                return
            if thread_id is None:
                return
            await self.store.set_thread(watch, event.id, thread_id)

        thread = self._thread(thread_id)
        sent: list[str] = []
        try:
            for update in new:
                await thread.send(
                    update.line,
                    embed=update.embed(),
                    allowed_mentions=AllowedMentions.none(),
                )
                sent.append(update.key)
        except (NotFound, Forbidden):
            # The thread was deleted or locked: this game's updates stop, and the channel's other games go on.
            logger.info(
                f"Stopped game {event.id}'s updates in channel {watch.channel_id}: its thread is gone."
            )
            await self.store.close_game(watch, event.id)
        except HTTPException:
            logger.exception(
                f"Couldn't send game {event.id}'s updates in channel {watch.channel_id}."
            )
        finally:
            if sent:
                await self.store.mark_delivered(watch, event.id, sent)

    async def _prune(
        self, watch: LeagueWatch, boards: Mapping[str, Scoreboard | None], now: datetime
    ) -> None:
        stale = []
        for event_id, game in watch.games.items():
            board = boards.get(game.league)
            event = board.event(event_id) if board is not None else None
            age = now - game.posted
            if game.league not in watch.leagues or age > KEEP_AT_MOST:
                stale.append(event_id)
            elif board is not None and event is None and age > FORGET_AFTER:
                stale.append(event_id)
            elif event is not None and not _live(event) and not date_known(event):
                # Posted before it had a date, which ESPN gives it once it's set: it's posted again then.
                stale.append(event_id)
        await self.store.forget(watch, stale)


__all__ = [
    "DELIVERED_PER_GAME",
    "FIELD",
    "FORGET_AFTER",
    "KEEP_AT_MOST",
    "LATE",
    "PREGAME",
    "LeagueWatch",
    "LeagueWatchStore",
    "LeagueWatcher",
    "PostedGame",
    "should_post",
]

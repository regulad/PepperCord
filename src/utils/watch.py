"""Watches: a channel's standing request to be sent a feed's updates, such as each new rotation, as they happen.

A cog describes what its feed can be watched for with a :class:`WatchSource`, and runs a :class:`Watcher`, which checks
every minute for events that are due and posts each one to every channel watching its topic.

Watches live in the guild's document, or in the user's for direct messages, under ``<namespace>_watches.<channel id>``:

    {"topics": [...], "role": <role id or null>, "paused": false, "delivered": {"<topic>": [<event keys>]}}

Each watch keeps the keys of the latest events it was sent, per topic, so neither a retry nor a restart posts an event
twice, and a bot that was down posts what it missed while the event is still recent.
"""

import logging
from asyncio import Semaphore, TaskGroup
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum, auto
from io import BytesIO
from typing import Any, Final, Protocol, cast

from discord import (
    AllowedMentions,
    DMChannel,
    Embed,
    File,
    Forbidden,
    HTTPException,
    Member,
    NotFound,
    Role,
    TextChannel,
)
from discord.abc import Messageable
from discord.ext import tasks

from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext
from utils.commands import UserFacingError
from utils.database import PCDocument, PCInternalDocument

logger = logging.getLogger(__name__)

GRACE: Final = timedelta(hours=2)
"""How late an event dated in advance, such as a rotation's start, can still be posted. A bot down longer skips it."""

DELIVERED_PER_TOPIC: Final = 50
"""How many of the latest events a watch remembers being sent, for each topic."""

SEND_CONCURRENCY: Final = 5
"""How many channels an event is sent to at once. discord.py keeps each send within Discord's rate limits."""


@dataclass(frozen=True)
class Rendered:
    """An event's message, rendered once and sent to every watch."""

    content: str
    embed: Embed
    files: tuple[tuple[str, bytes], ...] = ()

    def discord_files(self) -> list[File]:
        # Sending a File uses it up, so each send gets its own.
        return [File(BytesIO(data), filename=name) for name, data in self.files]


@dataclass(frozen=True)
class WatchEvent:
    """Something that happened that a watch can be sent, such as a new rotation."""

    key: str
    """Names the event. Deriving the same event again gives the same key, which is how it's never posted twice."""
    topic: str
    at: datetime
    """When it happened, or, for an event the feed doesn't date, when the bot first noticed it."""
    expires: datetime
    """When it stops being worth posting."""
    render: Callable[[], Awaitable[Rendered]] = field(compare=False)

    def is_due(self, now: datetime) -> bool:
        return self.at <= now < self.expires

    @classmethod
    def dated(
        cls,
        key: str,
        topic: str,
        at: datetime,
        render: Callable[[], Awaitable[Rendered]],
        *,
        ends: datetime | None = None,
    ) -> "WatchEvent":
        """An event the feed dates in advance, which can be posted up to GRACE late, and never after ``ends``."""
        expires = at + GRACE if ends is None else min(at + GRACE, ends)
        return cls(key, topic, at, expires, render)


class FirstSeen:
    """When the bot first noticed each event the feed doesn't date, such as a Splatfest being announced.

    It's kept in memory, so after a restart those events are new again. A watch's delivered keys keep that from posting
    any of them twice, and so a bot that was down posts what it missed while the event is still worth posting.
    """

    def __init__(self) -> None:
        self._times: dict[str, datetime] = {}

    def __call__(self, key: str, now: datetime) -> datetime:
        return self._times.setdefault(key, now)

    def forget_all_but(self, keys: Iterable[str]) -> None:
        keep = set(keys)
        self._times = {key: at for key, at in self._times.items() if key in keep}


class WatchSource(Protocol):
    """What a feed can be watched for. A cog implements it, and a :class:`Watcher` posts its events."""

    @property
    def namespace(self) -> str:
        """Names the field watches are stored in, ``<namespace>_watches``, and the feed in messages."""
        ...

    @property
    def name(self) -> str:
        """The feed's name in messages, such as "Splatoon 3"."""
        ...

    @property
    def topics(self) -> Mapping[str, str]:
        """Each topic a channel can watch, and what watching it posts."""
        ...

    def events(self, now: datetime) -> Iterable[WatchEvent]:
        """Every event the feed has produced that can still be posted, due or not. Called every minute."""
        ...


@dataclass(frozen=True)
class Watch:
    """A channel's watch on a feed."""

    document: PCDocument
    channel_id: int
    topics: frozenset[str]
    role_id: int | None
    paused: bool
    delivered: Mapping[str, frozenset[str]]

    def wants(self, event: WatchEvent) -> bool:
        return (
            not self.paused
            and event.topic in self.topics
            and event.key not in self.delivered.get(event.topic, frozenset())
        )


class WatchStore:
    """Reads and writes one feed's watches in the user and guild documents."""

    def __init__(self, bot: CustomBot, namespace: str) -> None:
        self.bot = bot
        self.field = f"{namespace}_watches"

    def _path(self, channel_id: int, *parts: str) -> str:
        # Channel IDs and topics are digits and plain words, so they're safe in a field path.
        return ".".join((self.field, str(channel_id), *parts))

    async def in_document(self, document: PCDocument) -> list[Watch]:
        entries = cast(
            dict[str, dict[str, Any]], await document.safe_get(self.field, {})
        )
        return [
            Watch(
                document=document,
                channel_id=int(channel_id),
                topics=frozenset(entry.get("topics", ())),
                role_id=entry.get("role"),
                paused=bool(entry.get("paused", False)),
                delivered={
                    topic: frozenset(keys)
                    for topic, keys in entry.get("delivered", {}).items()
                },
            )
            for channel_id, entry in entries.items()
        ]

    async def everywhere(self) -> list[Watch]:
        watches: list[Watch] = []
        for name in ("user", "guild"):
            collection = self.bot.ddb.get_collection(name)
            for raw in await collection.find({self.field: {"$exists": True}}).to_list(
                length=None
            ):
                watches += await self.in_document(await self._document(name, raw))
        return watches

    async def _document(self, collection: str, raw: PCInternalDocument) -> PCDocument:
        # The bot's cached documents reload after each write, so writing through them keeps what commands read current.
        if collection == "guild" and (guild := self.bot.get_guild(raw["_id"])):
            return await self.bot.get_guild_document(guild)
        if collection == "user" and (user := self.bot.get_user(raw["_id"])):
            return await self.bot.get_user_document(user)
        # A guild the bot left, or a user it can't see. Wrapped by the query that found it, every write would go to the
        # first document with a watch.
        return raw.wrap(self.bot.ddb.get_collection(collection), {"_id": raw["_id"]})

    async def add(
        self,
        document: PCDocument,
        channel_id: int,
        topic: str,
        role_id: int | None,
        seen: Iterable[str],
    ) -> None:
        """Add a topic to a channel's watch, resume it, and record ``seen`` as sent so the watch starts fresh."""
        update: dict[str, Any] = {
            "$addToSet": {self._path(channel_id, "topics"): topic},
            "$set": {self._path(channel_id, "paused"): False},
            "$push": {
                self._path(channel_id, "delivered", topic): {
                    "$each": list(seen),
                    "$slice": -DELIVERED_PER_TOPIC,
                }
            },
        }
        if role_id is not None:
            update["$set"][self._path(channel_id, "role")] = role_id
        await document.update_db(update)

    async def remove(
        self, document: PCDocument, channel_id: int, topic: str | None
    ) -> bool:
        """Remove a topic from a channel's watch, or every topic if None. Returns whether there was anything to remove."""
        watch = next(
            (w for w in await self.in_document(document) if w.channel_id == channel_id),
            None,
        )
        if watch is None or (topic is not None and topic not in watch.topics):
            return False
        if topic is None or watch.topics == {topic}:
            await document.update_db({"$unset": {self._path(channel_id): True}})
        else:
            await document.update_db(
                {
                    "$pull": {self._path(channel_id, "topics"): topic},
                    "$unset": {self._path(channel_id, "delivered", topic): True},
                }
            )
        return True

    async def mark_delivered(self, watch: Watch, event: WatchEvent) -> None:
        await watch.document.update_db(
            {
                "$push": {
                    self._path(watch.channel_id, "delivered", event.topic): {
                        "$each": [event.key],
                        "$slice": -DELIVERED_PER_TOPIC,
                    }
                }
            }
        )

    async def pause(self, watch: Watch) -> None:
        await watch.document.update_db(
            {"$set": {self._path(watch.channel_id, "paused"): True}}
        )

    async def delete(self, watch: Watch) -> None:
        await watch.document.update_db({"$unset": {self._path(watch.channel_id): True}})


class Outcome(Enum):
    DELIVERED = auto()
    GONE = auto()
    """The channel was deleted, or is one the bot can't post in: the watch is removed."""
    BLOCKED = auto()
    """The bot isn't allowed to post there any more: the watch is paused until someone adds a topic to it again."""
    FAILED = auto()
    """Something else went wrong: the event is tried again next minute, while it's still due."""


class Watcher:
    """Posts a source's events to the channels that watch them, checking every minute."""

    def __init__(
        self, bot: CustomBot, source: WatchSource, store: WatchStore | None = None
    ) -> None:
        self.bot = bot
        self.source = source
        self.store = store if store is not None else WatchStore(bot, source.namespace)
        # Events every watch that wanted them has been sent, which need no database reads until the bot restarts.
        # A watch added later starts with every due event marked as sent.
        self._settled: set[str] = set()
        # Events that couldn't be rendered, which would fail the same way again.
        self._broken: set[str] = set()
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
            logger.exception(f"Couldn't post {self.source.name} updates to watches.")

    def due(self, now: datetime) -> list[WatchEvent]:
        events = list(self.source.events(now))
        current = {event.key for event in events}
        self._settled &= current
        self._broken &= current
        skip = self._settled | self._broken
        return sorted(
            (event for event in events if event.is_due(now) and event.key not in skip),
            key=lambda e: e.at,
        )

    async def dispatch(self, now: datetime) -> None:
        due = self.due(now)
        if not due:
            return

        watches = await self.store.everywhere()
        unreachable: set[int] = set()
        for event in due:
            recipients = [
                w for w in watches if w.channel_id not in unreachable and w.wants(event)
            ]
            if not recipients:
                self._settled.add(event.key)
                continue

            try:
                rendered = await event.render()
            except Exception:
                logger.exception(
                    f"Couldn't render the {self.source.name} update {event.key}."
                )
                self._broken.add(event.key)
                continue

            semaphore = Semaphore(SEND_CONCURRENCY)

            async def deliver(watch: Watch) -> Outcome:
                async with semaphore:
                    return await self._deliver(watch, event, rendered)

            async with TaskGroup() as group:
                tasks_by_watch = [
                    (watch, group.create_task(deliver(watch))) for watch in recipients
                ]
            outcomes = [(watch, task.result()) for watch, task in tasks_by_watch]

            unreachable |= {
                w.channel_id
                for w, outcome in outcomes
                if outcome in (Outcome.GONE, Outcome.BLOCKED)
            }
            if all(outcome is not Outcome.FAILED for _, outcome in outcomes):
                self._settled.add(event.key)
            delivered = sum(outcome is Outcome.DELIVERED for _, outcome in outcomes)
            logger.info(
                f"Posted the {self.source.name} update {event.key} to {delivered} of {len(outcomes)} watches."
            )

    async def _deliver(
        self, watch: Watch, event: WatchEvent, rendered: Rendered
    ) -> Outcome:
        try:
            outcome = await self._send(watch, rendered)
        except Exception:
            logger.exception(
                f"Couldn't post {event.key} in channel {watch.channel_id}."
            )
            return Outcome.FAILED

        try:
            match outcome:
                case Outcome.DELIVERED:
                    await self.store.mark_delivered(watch, event)
                case Outcome.GONE:
                    await self.store.delete(watch)
                case Outcome.BLOCKED:
                    await self.store.pause(watch)
        except Exception:
            logger.exception(
                f"Couldn't record posting {event.key} in channel {watch.channel_id}."
            )
        return outcome

    async def _send(self, watch: Watch, rendered: Rendered) -> Outcome:
        # Deleted channels and lost permissions are expected, and are logged as such rather than reported as errors.
        try:
            channel = self.bot.get_channel(
                watch.channel_id
            ) or await self.bot.fetch_channel(watch.channel_id)
            if not isinstance(channel, Messageable):
                logger.info(
                    f"Removed the {self.source.name} watch in channel {watch.channel_id}: it can't be posted in."
                )
                return Outcome.GONE
            content = rendered.content
            mentions = AllowedMentions.none()
            # A role deleted since the watch was set up is skipped, rather than mentioned as "@deleted-role".
            role = (
                channel.guild.get_role(watch.role_id)
                if isinstance(channel, TextChannel) and watch.role_id
                else None
            )
            if role is not None:
                content = f"{role.mention} {content}"
                mentions = AllowedMentions(everyone=False, users=False, roles=[role])
            await channel.send(
                content,
                embed=rendered.embed,
                files=rendered.discord_files(),
                allowed_mentions=mentions,
            )
        except NotFound:
            logger.info(
                f"Removed the {self.source.name} watch in channel {watch.channel_id}: the channel is gone."
            )
            return Outcome.GONE
        except Forbidden:
            logger.warning(
                f"Paused the {self.source.name} watch in channel {watch.channel_id}: no longer allowed to post."
            )
            return Outcome.BLOCKED
        except HTTPException:
            logger.exception(
                f"Couldn't post a {self.source.name} update in channel {watch.channel_id}."
            )
            return Outcome.FAILED
        return Outcome.DELIVERED


# The commands. Each cog defines its own, since their names and choices are its own, and calls these.


async def _target(
    ctx: CustomContext, channel: TextChannel, dms: bool
) -> tuple[PCDocument, TextChannel | DMChannel]:
    if ctx.guild is None or dms:
        return (
            ctx["author_document"],
            ctx.author.dm_channel or await ctx.author.create_dm(),
        )
    if not isinstance(channel, TextChannel) or channel.guild != ctx.guild:
        raise UserFacingError(
            "Pick a text channel in this server, or use `dms` to watch in your direct messages."
        )
    if not channel.permissions_for(cast(Member, ctx.author)).manage_channels:
        raise UserFacingError(
            f"You need the Manage Channels permission in {channel.mention} to change what it watches."
        )
    return ctx["guild_document"], channel


def _topic(watcher: Watcher, topic: str) -> str:
    if topic not in watcher.source.topics:
        raise UserFacingError(
            f"There's no topic named `{topic}`. Pick one of: {', '.join(watcher.source.topics)}."
        )
    return topic


async def add_watch(
    ctx: CustomContext,
    watcher: Watcher,
    topic: str,
    channel: TextChannel,
    dms: bool,
    role: Role | None,
) -> None:
    """Start posting a topic's updates in a channel, or in the author's direct messages."""
    topic = _topic(watcher, topic)
    document, target = await _target(ctx, channel, dms)
    description = watcher.source.topics[topic]

    if isinstance(target, TextChannel):
        mine = target.permissions_for(target.guild.me)
        missing = [
            name
            for name, allowed in (
                ("Send Messages", mine.send_messages),
                ("Embed Links", mine.embed_links),
                ("Attach Files", mine.attach_files),
            )
            if not allowed
        ]
        if missing:
            raise UserFacingError(
                f"I need {', '.join(missing)} in {target.mention} to post there."
            )
        if role is not None and not (role.mentionable or mine.mention_everyone):
            raise UserFacingError(
                f"I can't mention {role.mention} in {target.mention}: make the role mentionable, or let me mention "
                "everyone there."
            )
    else:
        if role is not None:
            raise UserFacingError("A role can only be mentioned in a server's channel.")
        try:
            await target.send(
                f"You'll get {watcher.source.name} updates here. Topic: {description}."
            )
        except Forbidden:
            raise UserFacingError(
                "I can't send you direct messages. Allow them from this server's members, then retry."
            )

    now = datetime.now(UTC)
    # Everything due now counts as sent, so a new watch doesn't start with a backlog.
    seen = [
        event.key
        for event in watcher.source.events(now)
        if event.topic == topic and event.is_due(now)
    ]
    await watcher.store.add(
        document, target.id, topic, role.id if role is not None else None, seen
    )

    where = "your direct messages" if isinstance(target, DMChannel) else target.mention
    await ctx.send(
        f"Posting {watcher.source.name} updates in {where}. Topic: {description}.",
        ephemeral=True,
    )


async def remove_watch(
    ctx: CustomContext, watcher: Watcher, topic: str, channel: TextChannel, dms: bool
) -> None:
    """Stop posting a topic's updates in a channel, or every topic's if ``topic`` is "all"."""
    chosen = None if topic == "all" else _topic(watcher, topic)
    document, target = await _target(ctx, channel, dms)
    where = "your direct messages" if isinstance(target, DMChannel) else target.mention
    if not await watcher.store.remove(document, target.id, chosen):
        raise UserFacingError(f"Nothing to stop: {where} isn't watching that.")
    what = "" if chosen is None else f" Topic: {watcher.source.topics[chosen]}."
    await ctx.send(
        f"Stopped posting {watcher.source.name} updates in {where}.{what}",
        ephemeral=True,
    )


async def list_watches(ctx: CustomContext, watcher: Watcher) -> None:
    """List what this server's channels watch, or what the author's direct messages watch."""
    if ctx.guild is None:
        watches = await watcher.store.in_document(ctx["author_document"])
    else:
        watches = await watcher.store.in_document(ctx["guild_document"])

    lines: list[str] = []
    for watch in sorted(watches, key=lambda watch: watch.channel_id):
        where = "Your direct messages"
        role = None
        if ctx.guild is not None:
            channel = ctx.guild.get_channel(watch.channel_id)
            where = channel.mention if channel is not None else "A deleted channel"
            role = (
                ctx.guild.get_role(watch.role_id) if watch.role_id is not None else None
            )
        line = f"{where}: {', '.join(sorted(watch.topics))}"
        if role is not None:
            line += f", mentioning {role.mention}"
        if watch.paused:
            line += ". **Paused**: I wasn't allowed to post there. Add a topic again to resume."
        lines.append(line)

    embed = Embed(
        title=f"{watcher.source.name} watches",
        description="\n".join(lines) or "Nothing is watched here.",
    )
    embed.add_field(
        name="Topics",
        value="\n".join(
            f"`{topic}`: {description}"
            for topic, description in watcher.source.topics.items()
        ),
        inline=False,
    )
    await ctx.send(embed=embed, ephemeral=True, allowed_mentions=AllowedMentions.none())


__all__ = [
    "DELIVERED_PER_TOPIC",
    "GRACE",
    "FirstSeen",
    "Rendered",
    "Watch",
    "WatchEvent",
    "WatchSource",
    "WatchStore",
    "Watcher",
    "add_watch",
    "list_watches",
    "remove_watch",
]

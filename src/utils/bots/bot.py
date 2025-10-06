import logging
import sys
import traceback
from asyncio import Semaphore
from collections import deque
from os import getcwd
from os.path import splitext, join
from typing import Union, Type, MutableMapping, Deque, Optional, TYPE_CHECKING, Any

import discord
from aiofiles import open as aopen
from discord import (
    Member,
    Guild,
    PartialEmoji,
    Emoji,
    Message,
    GroupChannel,
    DMChannel,
    TextChannel,
)
from discord.ext import commands
from discord.ext.commands.bot import CFT
from discord.user import BaseUser, User
from discord.utils import find
from motor.motor_asyncio import AsyncIOMotorDatabase

from utils.database import Document
from .context import CustomContext

CONFIGURATION_PROVIDERS = Union[dict, MutableMapping]

logger: logging.Logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from discord.state import ConnectionState


class CustomBotBase(commands.bot.BotBase):
    @staticmethod
    async def store_original_kwargs(ctx: CustomContext, *args, **kwargs):
        # On custom contexts with interactions, the original kwargs can be discarded when a command is re-prepared
        if ctx.interaction is not None:
            ctx["original_kwargs"] = ctx.kwargs

    def __init__(
        self,
        command_prefix,
        help_command=commands.HelpCommand(),
        description=None,
        *,
        database,
        config: CONFIGURATION_PROVIDERS,
        **options,
    ):
        self._database = database
        self._config: CONFIGURATION_PROVIDERS = config

        self._context_cache: deque[CustomContext] = deque(maxlen=100)
        self._context_semaphores: deque[tuple[int, Semaphore]] = deque(maxlen=10)
        # theoretical max of 10 contexts processed at once
        self._context_fetch_semaphore: Semaphore = Semaphore(1)
        # this is a little hacky, but it beats the alternative which is wasting time and firing events more than once

        self._user_doc_cache: deque[tuple[BaseUser | Member, Document]] = deque(
            maxlen=30
        )
        self._guild_doc_cache: deque[tuple[discord.Guild, Document]] = deque(maxlen=30)

        super().__init__(
            command_prefix,
            help_command=help_command,
            description=description,
            **options,
        )

        self.before_invoke(self.store_original_kwargs)

    @property
    def home_server(self) -> Guild | None:
        maybe_home_server: str = self._config.get("PEPPERCORD_HOME_SERVER")
        if maybe_home_server is not None:
            maybe_home_guild: Guild | None = super().get_guild(int(maybe_home_server))  # type: ignore
            if maybe_home_guild is not None:
                return maybe_home_guild
            else:
                logger.critical(
                    f"Home server is set to {maybe_home_server}, but could not find!"
                )
                return None
        else:
            return None

    def get_custom_emoji(self, emoji_filename: str) -> PartialEmoji | Emoji | None:
        """Gets a custom emoji from the bot's home server."""

        home_server: Guild | None = self.home_server
        emoji_filename_split: tuple[str, str] = splitext(emoji_filename)
        for emoji in home_server.emojis:
            if emoji.name == emoji_filename_split[0]:
                return emoji
        else:
            return None

    async def fetch_or_upload_custom_emoji(
        self, emoji_filename: str
    ) -> PartialEmoji | Emoji | None:
        """Fetches a custom emoji from the bot's home server."""

        maybe_exists: PartialEmoji | Emoji | None = self.get_custom_emoji(
            emoji_filename
        )

        if maybe_exists is not None:
            return maybe_exists
        else:
            home_server: Guild | None = self.home_server
            emoji_filename_split: tuple[str, str] = splitext(emoji_filename)
            if home_server is not None:
                if home_server.me.guild_permissions.manage_emojis:
                    async with aopen(
                        join(getcwd(), "resources", "emojis", emoji_filename), "rb"
                    ) as f:
                        emoji_bytes: bytes = await f.read()

                    # upload
                    return await home_server.create_custom_emoji(
                        name=emoji_filename_split[0],
                        image=emoji_bytes,
                        reason="Emoji upload for PepperCord.",
                    )
                else:
                    return None
            else:
                return None

    @property
    def owner(self) -> Optional[User]:
        return self.get_user(self.owner_id)  # type: ignore

    @property
    def owners(self) -> list[User] | None:
        return (
            [self.get_user(owner_id) for owner_id in self.owner_ids]
            if self.owner_ids is not None
            else None
        )  # type: ignore

    @property
    def effective_owners(self) -> list[User]:
        if self.owners is not None and self.owner is not None:
            return [self.owner] + self.owners
        elif self.owner is not None:
            return [self.owner]
        elif self.owners is not None:
            return self.owners
        else:
            return []

    @property
    def database(self) -> AsyncIOMotorDatabase:
        return self._database

    @property
    def config(self) -> CONFIGURATION_PROVIDERS:
        return self._config

    async def get_command_document(self, command: commands.Command):
        """Gets a command's document from the database."""

        return await Document.get_document(
            self._database["commands"],
            {
                "name": command.name,
                "cog": (
                    command.cog_name
                    if (hasattr(command, "cog_name") and command.cog_name is not None)
                    else None
                ),
            },
        )

    async def get_guild_document(self, model: discord.Guild) -> Document:
        """Gets a guild's document from the database."""

        for other, document in self._guild_doc_cache:
            if other == model:
                return document
        else:
            document: Document = await Document.get_document(
                self._database["guild"], {"_id": model.id}
            )
            self._guild_doc_cache.appendleft((model, document))
            return document

    async def get_user_document(self, model: Member | BaseUser) -> Document:
        """Gets a user's document from the database."""

        for other, document in self._user_doc_cache:
            if other == model:
                return document
        else:
            document: Document = await Document.get_document(
                self._database["user"], {"_id": model.id}
            )
            self._user_doc_cache.appendleft((model, document))
            return document

    async def get_context(
        self, message: discord.Message, *, cls: Type[commands.Context] = CustomContext
    ):
        if cls is CustomContext:
            async with self._context_fetch_semaphore:
                # FIXME: There has to be a cleaner way to ensure that only one context is ever made per message and that on_context_creation" is only ever fired once per message. This is a nightmare!
                maybe_semaphore_tuple: tuple[int, Semaphore] | None = find(
                    lambda sema_tuple: sema_tuple[0] == message.id,
                    reversed(self._context_semaphores),
                )
                processing_semaphore: Semaphore | None = (
                    maybe_semaphore_tuple[-1]
                    if maybe_semaphore_tuple is not None
                    else None
                )

                if processing_semaphore is None:
                    processing_semaphore = Semaphore(1)
                    self._context_semaphores.append((message.id, processing_semaphore))
            async with processing_semaphore:
                existing: CustomContext | None = find(
                    lambda ctx: ctx.message.id == message.id,
                    reversed(self._context_cache),
                )

                if existing is not None:
                    return existing  # the existing context will already have had its hooks run, send it!
                else:
                    result: CustomContext = await super().get_context(
                        message, cls=CustomContext
                    )
                    await self.wait_for_dispatch("context_creation", result)
                    self.dispatch("message_context", result)
                    # new! kind of useless because there is no way to check if it is a new message, but could be useful for analytics? maybe?
                    self._context_cache.append(result)

                return result
        else:
            return await super().get_context(
                message, cls=cls
            )  # all of our fancy magic only works on customcontext

    async def on_context_creation(
        self, ctx: commands.Context
    ) -> None:  # Placeholder method
        pass

    async def wait_for_dispatch(self, event_name, *args, **kwargs):
        await super().wait_for_dispatch(event_name, *args, **kwargs)  # type: ignore
        ev = "on_" + event_name
        for event in self.extra_events.get(ev, []):
            await super()._schedule_event(event, ev, *args, **kwargs)  # type: ignore


class ClientMixin:
    @property
    def has_presences(self) -> bool:
        """
        Whether the bot is currently tracking presences.
        """
        return self._connection.intents.presences

    @property
    def has_members(self) -> bool:
        """
        Whether the bot is currently tracking members.
        """
        return self._connection.intents.members

    @property
    def has_message_content(self) -> bool:
        """
        Whether the bot is currently tracking message content.
        """
        return self._connection.intents.message_content

    @property
    def perceivable_users(self) -> int:
        """
        The number of users the bot can perceive.
        """
        return (
            len(self.users)
            if self.has_members
            else sum((guild.member_count or 0) for guild in self.guilds)
        )

    def __init__(self, *args, **kwargs):
        self._aux_max_messages: int | None = kwargs.get("max_messages", 1000)
        if self._aux_max_messages is not None and self._aux_max_messages <= 0:
            self._aux_max_messages = 1000
        if self._aux_max_messages is not None:
            self._aux_messages: Optional[Deque[Message]] = deque(
                maxlen=self._aux_max_messages
            )
        else:
            self._aux_messages: Optional[Deque[Message]] = None
        super().__init__(*args, **kwargs)

    async def wait_for_dispatch(self, event: str, *args, **kwargs):
        logging.debug("Dispatching event %s", event)
        method = "on_" + event

        listeners = self._listeners.get(event)  # type: ignore
        if listeners:
            removed = []
            for i, (future, condition) in enumerate(listeners):
                if future.cancelled():
                    removed.append(i)
                    continue

                try:
                    result = condition(*args)
                except Exception as exc:
                    future.set_exception(exc)
                    removed.append(i)
                else:
                    if result:
                        if len(args) == 0:
                            future.set_result(None)
                        elif len(args) == 1:
                            future.set_result(args[0])
                        else:
                            future.set_result(args)
                        removed.append(i)

            if len(removed) == len(listeners):
                self._listeners.pop(event)  # type: ignore
            else:
                for idx in reversed(removed):
                    del listeners[idx]

        try:
            coro = getattr(self, method)
        except AttributeError:
            pass
        else:
            await self._schedule_event(coro, method, *args, **kwargs)  # type: ignore

    _connection: "ConnectionState"

    def _get_aux_message(self, msg_id: Optional[int]) -> Optional[Message]:
        return (
            find(lambda m: m.id == msg_id, reversed(self._aux_messages))
            if self._aux_messages
            else None
        )

    async def smart_fetch_message(
        self, channel: TextChannel | DMChannel | GroupChannel, message_id: int
    ) -> Message:
        """Fetches a message from a channel, or from the cache if possible."""

        existing: Message | None = self._connection._get_message(
            message_id
        ) or self._get_aux_message(message_id)

        if existing is not None:
            return existing
        else:
            fetched: Message = await channel.fetch_message(message_id)
            if self._aux_messages is not None:
                self._aux_messages.append(fetched)
            return fetched

    async def on_error(self, event_method: str, /, *args: Any, **kwargs: Any) -> None:
        log = f"A critical exception occurred in {event_method}!"

        exc_info = sys.exc_info()

        if not any(exc_info) and len(args) > 1 and isinstance(args[1], Exception):
            exc_info = (type(args[1]), args[1], args[1].__traceback__)

        if exc_info[0] is not None:
            log += (
                f"\nException: {exc_info[0].__name__}: {exc_info[1]}"
                f"\nTraceback:\n"
                "".join(traceback.format_tb(exc_info[2]))
            )

        logger.exception(log, exc_info=exc_info if exc_info[0] is not None else None)


class CustomAutoShardedBot(CustomBotBase, ClientMixin, discord.AutoShardedClient):
    pass


class CustomBot(CustomBotBase, ClientMixin, discord.Client):
    pass


BOT_TYPES = Union[CustomBot, CustomAutoShardedBot]

__all__ = ["CustomBot", "CustomAutoShardedBot", "BOT_TYPES", "CONFIGURATION_PROVIDERS"]

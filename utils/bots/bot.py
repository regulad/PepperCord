import logging
from collections import deque
from os import getcwd
from os.path import splitext, join
from typing import Union, Type, MutableMapping, Deque, Optional, Sequence

import discord
from aiofiles import open as aopen
from discord import Member, Guild, PartialEmoji, Emoji, Message, GroupChannel, DMChannel, TextChannel
from discord.ext import commands
from discord.user import BaseUser
from discord.utils import SequenceProxy
from motor.motor_asyncio import AsyncIOMotorDatabase

from utils.database import Document
from .context import CustomContext

CONFIGURATION_PROVIDERS = Union[dict, MutableMapping]

logger: logging.Logger = logging.getLogger(__name__)


class CustomBotBase(commands.bot.BotBase):
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

        self._context_cache: deque[tuple[discord.Message, commands.Context]] = deque(
            maxlen=10
        )
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

    @property
    def home_server(self) -> Guild | None:
        maybe_home_server: str = self._config.get("PEPPERCORD_HOME_SERVER")
        if maybe_home_server is not None:
            maybe_home_guild: Guild | None = super().get_guild(int(maybe_home_server))  # type: ignore
            if maybe_home_guild is not None:
                return maybe_home_guild
            else:
                logger.critical(f"Home server is set to {maybe_home_server}, but could not find!")
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

    async def fetch_or_upload_custom_emoji(self, emoji_filename: str) -> PartialEmoji | Emoji | None:
        """Fetches a custom emoji from the bot's home server."""

        maybe_exists: PartialEmoji | Emoji | None = self.get_custom_emoji(emoji_filename)

        if maybe_exists is not None:
            return maybe_exists
        else:
            home_server: Guild | None = self.home_server
            emoji_filename_split: tuple[str, str] = splitext(emoji_filename)
            if home_server is not None:
                if home_server.me.guild_permissions.manage_emojis:
                    async with aopen(join(getcwd(), "resources", "emojis", emoji_filename), "rb") as f:
                        emoji_bytes: bytes = await f.read()

                    # upload
                    return await home_server.create_custom_emoji(
                        name=emoji_filename_split[0],
                        image=emoji_bytes,
                        reason="Emoji upload for PepperCord."
                    )
                else:
                    return None
            else:
                return None

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
                "cog": command.cog_name
                if (hasattr(command, "cog_name") and command.cog_name is not None)
                else None,
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
        for other, context in self._context_cache:
            if isinstance(context, cls) and other == message:
                return context
        else:
            result: cls = await super().get_context(message, cls=cls)
            await self.wait_for_dispatch("context_creation", result)
            self._context_cache.appendleft((message, result))
            return result

    async def on_context_creation(
            self, ctx: commands.Context
    ) -> None:  # Placeholder method
        pass

    async def wait_for_dispatch(self, event_name, *args, **kwargs):
        await super().wait_for_dispatch(event_name, *args, **kwargs)  # type: ignore
        ev = "on_" + event_name
        for event in self.extra_events.get(ev, []):
            await super()._schedule_event(event, ev, *args, **kwargs)  # type: ignore


class CustomClientBase:
    def __init__(self, *args, **kwargs):
        self._aux_max_messages: int | None = kwargs.get('max_messages', 1000)
        if self._aux_max_messages is not None and self._aux_max_messages <= 0:
            self._aux_max_messages = 1000
        if self._aux_max_messages is not None:
            self._aux_messages: Optional[Deque[Message]] = deque(maxlen=self._aux_max_messages)
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

    cached_messages: Sequence[Message]

    async def smart_fetch_message(self, channel: TextChannel | DMChannel | GroupChannel,
                                  message_id: int) -> Message:
        """Fetches a message from a channel, or from the cache if possible."""

        maybe_cache: list[Message] = [m for m in self.cached_messages if m.id == message_id]
        maybe_cached: Message | None = maybe_cache[0] if len(maybe_cache) > 0 else None
        del maybe_cache  # cleaup duty

        if maybe_cached is not None:
            return maybe_cached
        elif self._aux_messages is not None:
            maybe_aux_cache: list[Message] = [m for m in SequenceProxy(self._aux_messages) if m.id == message_id]
            maybe_aux_cached: Message | None = maybe_aux_cache[0] if len(maybe_aux_cache) > 0 else None
            del maybe_aux_cache  # cleaup duty

            if maybe_aux_cached is not None:
                return maybe_aux_cached
            else:
                message: Message = await channel.fetch_message(message_id)
                self._aux_messages.append(message)
                return message
        else:
            return await channel.fetch_message(message_id)


class CustomAutoShardedBot(CustomBotBase, CustomClientBase, discord.AutoShardedClient):
    pass


class CustomBot(CustomBotBase, CustomClientBase, discord.Client):
    pass


BOT_TYPES = Union[CustomBot, CustomAutoShardedBot]

__all__ = ["CustomBot", "CustomAutoShardedBot", "BOT_TYPES", "CONFIGURATION_PROVIDERS"]

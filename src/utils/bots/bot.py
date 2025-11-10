import logging
import sys
import traceback
from asyncio import Semaphore
from collections import deque
from os import getcwd
from os.path import splitext, join
from typing import (
    Dict,
    Literal,
    Type,
    MutableMapping,
    Optional,
    Any,
    TypeVar,
    cast,
    overload,
)

import discord
from aiofiles import open as aopen
from discord import (
    Interaction,
    Member,
    Guild,
    PartialEmoji,
    Emoji,
    Message,
)
from discord.ext.commands import Bot, Command, Context
from pymongo.asynchronous.database import AsyncDatabase
from discord.user import BaseUser, User
from discord.utils import find

from utils.database import PCDocument, PCInternalDocument
from .context import CustomContext

logger: logging.Logger = logging.getLogger(__name__)

ContextT = TypeVar("ContextT", bound="Context[Any]")


# In the past, I used to maintain a version of the custom bot that used the AutoShardedMixin backend.
# However, I decided to stop maintaining it in order to make typing easier.
# Plus, I decided to start using emojis more, and emojis do not work consistently on AutoShardedBots: https://github.com/Rapptz/discord.py/discussions/8333
class CustomBot(Bot):

    @staticmethod
    async def store_original_kwargs(
        ctx: CustomContext, *args: Any, **kwargs: Any
    ) -> None:
        # On custom contexts with interactions, the original kwargs can be discarded when a command is re-prepared
        if ctx.interaction is not None:
            ctx["original_kwargs"] = ctx.kwargs

    def __init__(
        self,
        *,
        database: AsyncDatabase[PCInternalDocument],
        config: MutableMapping[str, str],
        **options: Any,
    ):
        self._database = database
        self._config = config

        self._custom_state: Dict[str, Any] = {}

        self._context_cache: deque[CustomContext] = deque(maxlen=100)
        self._context_semaphores: deque[tuple[int, Semaphore]] = deque(maxlen=100)
        self._context_fetch_semaphore: Semaphore = Semaphore(1)

        self._user_doc_cache: deque[tuple[BaseUser | Member, PCDocument]] = deque(
            maxlen=30
        )
        self._guild_doc_cache: deque[tuple[discord.Guild, PCDocument]] = deque(
            maxlen=30
        )

        super().__init__(
            config.get("PEPPERCORD_PREFIX", "?"),
            **options,
        )

        self.before_invoke(self.store_original_kwargs)

    # custom state
    @overload
    def __getitem__(self, item: Literal["prefix_cache"]) -> dict[int, str]: ...

    @overload
    def __getitem__(self, item: str) -> Any: ...

    def __getitem__(self, item: str) -> Any:
        return self._custom_state[item]

    def __contains__(self, key: str) -> bool:
        return key in self._custom_state

    @overload
    def __setitem__(
        self, key: Literal["prefix_cache"], value: dict[int, str]
    ) -> None: ...

    @overload
    def __setitem__(self, key: str, value: Any) -> None: ...

    def __setitem__(self, key: str, value: Any) -> None:
        self._custom_state[key] = value

    def __delitem__(self, key: str) -> None:
        del self._custom_state[key]

    # end custom state

    @property
    def home_server(self) -> Guild | None:
        maybe_home_server = self._config.get("PEPPERCORD_HOME_SERVER")
        if maybe_home_server is not None:
            maybe_home_guild = super().get_guild(int(maybe_home_server))
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

        home_server = self.home_server

        if home_server is None:
            return None

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

    async def fetch_owner(self) -> Optional[User]:
        if self.owner_id is None:
            return None
        return await self.fetch_user(self.owner_id)

    async def fetch_owners(self) -> list[User] | None:
        return (
            [await self.fetch_user(owner_id) for owner_id in self.owner_ids]
            if self.owner_ids is not None
            else None
        )

    async def fetch_effective_owners(self) -> list[User]:
        fetched_owner = await self.fetch_owner()
        fetched_owners = await self.fetch_owners()
        if fetched_owners is not None and fetched_owner is not None:
            return list(
                set([fetched_owner] + fetched_owners)
            )  # hacky way to guarantee uniqueness
        elif fetched_owner is not None:
            return [fetched_owner]
        elif fetched_owners is not None:
            return fetched_owners.copy()
        else:
            return []

    @property
    def database(self) -> AsyncDatabase[PCInternalDocument]:
        return self._database

    @property
    def config(self) -> MutableMapping[str, str]:
        return self._config

    async def get_command_document(self, command: Command[Any, Any, Any]) -> PCDocument:
        """Gets a command's document from the database."""

        return await PCDocument.get_document(
            self._database["commands"],
            {
                "name": command.name,
                "cog": getattr(
                    command, "cog_name", None
                ),  # cog_name isn't on HybridAppCommand, even though it inherits from Command
            },
        )

    async def get_guild_document(self, model: discord.Guild) -> PCDocument:
        """Gets a guild's document from the database."""

        for other, document in self._guild_doc_cache:
            if other == model:
                return document
        else:
            document = await PCDocument.get_document(
                self._database["guild"], {"_id": model.id}
            )
            self._guild_doc_cache.appendleft((model, document))
            return document

    async def get_user_document(self, model: Member | BaseUser) -> PCDocument:
        """Gets a user's document from the database."""

        for other, document in self._user_doc_cache:
            if other == model:
                return document
        else:
            document = await PCDocument.get_document(
                self._database["user"], {"_id": model.id}
            )
            self._user_doc_cache.appendleft((model, document))
            return document

    async def get_context(
        self, origin: Message | Interaction, *, cls: Type[ContextT] = CustomContext  # type: ignore[assignment]
    ) -> ContextT:
        if cls is CustomContext:
            async with self._context_fetch_semaphore:
                # d.py calls get_context multiple times simultaneously for each context
                # To avoid running the DB hooks more than once, this code ensures that only one context exists per message/interaction

                maybe_semaphore_tuple: tuple[int, Semaphore] | None = find(
                    lambda sema_tuple: sema_tuple[0] == origin.id,
                    reversed(self._context_semaphores),
                )

                processing_semaphore: Semaphore | None = (
                    maybe_semaphore_tuple[-1]
                    if maybe_semaphore_tuple is not None
                    else None
                )

                if processing_semaphore is None:
                    processing_semaphore = Semaphore(1)
                    self._context_semaphores.append((origin.id, processing_semaphore))
            async with processing_semaphore:
                existing: CustomContext | None = find(
                    lambda ctx: ctx.message.id == origin.id,
                    reversed(self._context_cache),
                )

                if existing is not None:
                    return cast(
                        ContextT, existing
                    )  # the existing context will already have had its hooks run, send it!
                else:
                    result = await super().get_context(origin, cls=CustomContext)
                    await self.wait_for_dispatch("context_creation", result)
                    self.dispatch("message_context", result)
                    # new! kind of useless because there is no way to check if it is a new message, but could be useful for analytics? maybe?
                    self._context_cache.append(result)

                return cast(
                    ContextT, result
                )  # mypy bug? this is already the correct type without a cast
        else:
            return await super().get_context(
                origin, cls=cls
            )  # all of our fancy magic only works on customcontext

    # Gripe: hooks into internals too much. Should be retired.
    async def wait_for_dispatch(
        self, event_name: str, *args: Any, **kwargs: Any
    ) -> None:
        """
        Dispatch a d.py client event, and wait for the listeners to finish.
        Also includes the bot listeners "extra_events"
        """

        await self._super___wait_for_dispatch(event_name, *args, **kwargs)
        ev = "on_" + event_name
        for event in self.extra_events.get(ev, []):
            await super()._schedule_event(event, ev, *args, **kwargs)

    # The methods below this comment were originally a part of the ClientMixin that was applied to both the AutoSharded and regular bots.

    @property
    def perceivable_users(self) -> int:
        """
        The number of users the bot can perceive.
        """
        return (
            len(self.users)
            if self.intents.members
            else sum((guild.member_count or 0) for guild in self.guilds)
        )

    async def _super___wait_for_dispatch(
        self, event: str, *args: Any, **kwargs: Any
    ) -> None:
        """
        Dispatch a d.py client event, and wait for the listeners to finish
        """

        logging.debug("Dispatching event %s", event)
        method = "on_" + event

        listeners = self._listeners.get(event)
        if listeners is not None:
            removed = []
            for i, (future, condition) in enumerate(listeners):
                # I have NO idea what the "cancelled" stuff is. It's merely copied from the d.py internals.

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
                self._listeners.pop(event)
            else:
                for idx in reversed(removed):
                    del listeners[idx]

        try:
            coro = getattr(self, method)
        except AttributeError:
            pass
        else:
            await self._schedule_event(coro, method, *args, **kwargs)

    async def on_error(self, event_method: str, /, *args: Any, **kwargs: Any) -> None:
        log = f"A critical exception occurred in {event_method}!"

        exc_info = sys.exc_info()

        if not any(exc_info) and len(args) > 1 and isinstance(args[1], Exception):
            exc_info = (type(args[1]), args[1], args[1].__traceback__)  # type: ignore[assignment] # it's close enough, barring traceback being maybe none

        if exc_info[0] is not None:
            log += f"\nException: {exc_info[0].__name__}: {exc_info[1]}"

        if exc_info[2] is not None:
            log += f"\nTraceback:\n" "".join(traceback.format_tb(exc_info[2]))

        logger.exception(log, exc_info=exc_info if exc_info[0] is not None else None)


__all__ = ("CustomBot",)

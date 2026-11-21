import logging
from asyncio import Semaphore, sleep, timeout
from collections import deque
from os import getcwd, listdir
from os.path import isdir, join, splitext
from typing import (
    Dict,
    Literal,
    Type,
    MutableMapping,
    Any,
    TypeVar,
    cast,
    overload,
)

import discord
import sentry_sdk
from aiofiles import open as aopen
from aiohttp import ClientError
from discord import (
    DiscordServerError,
    Interaction,
    Member,
    Emoji,
    Message,
)
from discord.ext.commands import Bot, Context
from pymongo.asynchronous.database import AsyncDatabase
from discord.user import BaseUser
from discord.utils import find

from utils.database import PCDocument, PCInternalDocument
from utils.reporting import identify_bot
from .context import CustomContext

logger: logging.Logger = logging.getLogger(__name__)

ContextT = TypeVar("ContextT", bound="Context[Any]")

# discord.py retries the gateway through network failures, but an error from a request in setup_hook ends bot.start, and
# a stalled request first waits out aiohttp's five-minute default. These bound the emoji fetch instead.
EMOJI_FETCH_TIMEOUT: float = 30
EMOJI_FETCH_ATTEMPTS: int = 4


# In the past, I used to maintain a version of the custom bot that used the AutoShardedMixin backend.
# However, I decided to stop maintaining it in order to make typing easier.
# Plus, I decided to start using emojis more, and emojis do not work consistently on AutoShardedBots: https://github.com/Rapptz/discord.py/discussions/8333
class CustomBot(Bot):

    @staticmethod
    async def before_invoke_handler(
        ctx: CustomContext, *args: Any, **kwargs: Any
    ) -> None:
        # Started first so the before_invocation listeners land in the transaction too.
        ctx.start_sentry_transaction()
        await ctx.bot.wait_for_dispatch("before_invocation_blocking", ctx)
        ctx.bot.dispatch("before_invocation_nonblocking", ctx)
        # On custom contexts with interactions, the original kwargs can be discarded when a command is re-prepared
        if ctx.interaction is not None:
            ctx["original_kwargs"] = ctx.kwargs

    @staticmethod
    async def after_invoke_handler(
        ctx: CustomContext, *args: Any, **kwargs: Any
    ) -> None:
        try:
            await ctx.bot.wait_for_dispatch("after_invocation_blocking", ctx)
            ctx.bot.dispatch("after_invocation_nonblocking", ctx)
        finally:
            ctx.finish_sentry_transaction()

    def __init__(
        self,
        *,
        ddb: AsyncDatabase[PCInternalDocument],
        config: MutableMapping[str, str],
        **options: Any,
    ):
        self.ddb = ddb

        self._config = config

        self._custom_state: Dict[str, Any] = {}

        # Filled by sync_application_emojis during setup_hook.
        self._application_emojis: dict[str, Emoji] = {}

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

        self.before_invoke(self.before_invoke_handler)
        self.after_invoke(self.after_invoke_handler)

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

    async def setup_hook(self) -> None:
        # Runs after login, so the bot's user and application IDs are known, and before the gateway connects.
        assert self.user is not None
        identify_bot(self.user.id)
        await self.sync_application_emojis()

    # Emojis

    async def sync_application_emojis(self) -> None:
        """
        Upload each image in resources/emojis that the application doesn't have yet, then cache them all by name.

        Application emojis belong to the bot itself, so they work in every guild and DM without a server to host them.
        """
        emojis = {
            emoji.name: emoji
            for emoji in await self._fetch_application_emojis_with_retries()
        }

        emoji_directory = join(getcwd(), "resources", "emojis")
        if not isdir(emoji_directory):
            logger.warning(
                "resources/emojis is missing, so there are no custom emojis to upload."
            )
        else:
            for filename in sorted(listdir(emoji_directory)):
                name = splitext(filename)[0]
                if name in emojis:
                    continue

                async with aopen(join(emoji_directory, filename), "rb") as f:
                    image = await f.read()
                try:
                    emojis[name] = await self.create_application_emoji(
                        name=name, image=image
                    )
                except (discord.HTTPException, ClientError, TimeoutError):
                    # Emojis are decoration, so a failed upload shouldn't stop the bot from starting.
                    logger.exception(f"Failed to upload application emoji {name}.")
                else:
                    logger.info(f"Uploaded application emoji {name}.")

        self._application_emojis = emojis
        logger.info(f"{len(emojis)} application emojis are available.")

    async def _fetch_application_emojis_with_retries(self) -> list[Emoji]:
        """
        Fetch the application's emojis, trying again when the network or Discord fails.

        Each attempt gets EMOJI_FETCH_TIMEOUT seconds. Once EMOJI_FETCH_ATTEMPTS have failed, the last error is raised,
        which ends bot.start and the process, so the container restarts the bot.
        """
        attempt = 1
        while True:
            try:
                async with timeout(EMOJI_FETCH_TIMEOUT):
                    return await self.fetch_application_emojis()
            except (ClientError, TimeoutError, DiscordServerError) as error:
                if attempt >= EMOJI_FETCH_ATTEMPTS or self.is_closed():
                    raise
                delay = 2**attempt
                logger.warning(
                    f"Couldn't fetch the application emojis ({error!r}), so trying again in {delay} seconds."
                )
                await sleep(delay)
                attempt += 1

    def get_custom_emoji(self, emoji_filename: str) -> Emoji | None:
        """Gets one of the bot's application emojis by its file name in resources/emojis, with or without the extension."""
        return self._application_emojis.get(splitext(emoji_filename)[0])

    @property
    def config(self) -> MutableMapping[str, str]:
        return self._config

    async def get_guild_document(self, model: discord.Guild) -> PCDocument:
        """Gets a guild's document from the database."""

        for other, document in self._guild_doc_cache:
            if other == model:
                return document
        else:
            document = await PCDocument.get_document(
                self.ddb["guild"], {"_id": model.id}
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
                self.ddb["user"], {"_id": model.id}
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

    def dispatch(self, event_name: str, /, *args: Any, **kwargs: Any) -> None:
        if (
            event_name == "command_error"
            and args
            and isinstance(args[0], CustomContext)
        ):
            # Command.dispatch_error calls this synchronously from the command's own task, on both the prefix and slash
            # paths. That makes it the one place to finish a failed slash command's transaction, which discord.py
            # never passes to after_invoke. It runs before the error listeners are scheduled.
            args[0].finish_sentry_transaction()
        super().dispatch(event_name, *args, **kwargs)

    async def on_error(self, event_method: str, /, *args: Any, **kwargs: Any) -> None:
        # discord.py calls this from inside the except block around the listener that failed.
        sentry_sdk.capture_exception(tags={"event": event_method})
        # Sentry's dedupe integration drops the copy of this event the logging integration would send.
        logger.exception("Unhandled exception in %s", event_method)


__all__ = ("CustomBot",)

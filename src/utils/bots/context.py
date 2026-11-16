from abc import ABC
from contextlib import ExitStack
from typing import Dict, Any, Literal, cast, TYPE_CHECKING, Coroutine, overload

import sentry_sdk
from sentry_sdk.consts import SPANSTATUS
from sentry_sdk.tracing import Span
from discord import (
    Message,
    HTTPException,
    NotFound,
    User,
    VoiceProtocol,
    WebhookMessage,
)
from discord.ext.commands import Context

from utils.database import PCDocument

from ..audio import *

if TYPE_CHECKING:
    from utils.bots.bot import CustomBot


class SendHandler(ABC):
    async def send(self, *args: Any, **kwargs: Any) -> Message:
        raise NotImplementedError


class _DefaultSendHandler(SendHandler):
    def __init__(self, ctx: "CustomContext"):
        self.ctx: "CustomContext" = ctx

    async def send(self, *args: Any, **kwargs: Any) -> Message:
        message: Message
        if self.ctx.interaction is None:
            if kwargs.get("ephemeral") is not None:
                del kwargs["ephemeral"]
            if kwargs.get("reference") is None:
                # Before we reply to the message, we need to check if the message still exists.
                # If the user quickly deletes the message or we jank it with purge, we need to
                # avoid hitting a reference.
                # Also, this is stupid and slow. The whole bot is. Oh well.
                if (
                    self.ctx.guild is not None
                    and not self.ctx.channel.permissions_for(
                        self.ctx.guild.me
                    ).read_message_history
                ):
                    # If we don't have read_message_history, we need to bail so we don't accidentally cause an error.
                    pass
                    # I would return here, but this method has a stupid structure and this isn't a submethod
                else:
                    og_message = self.ctx.message
                    try:
                        await self.ctx.channel.fetch_message(og_message.id)
                    except NotFound:
                        pass
                    else:
                        kwargs["reference"] = self.ctx.message
            message = await self.ctx.send_bare(*args, **kwargs)
        else:
            try:
                message = await self.ctx.send_bare(*args, **kwargs)
            except HTTPException:
                try:
                    # NOTICE: If I ever used wait=false, then this
                    # mypy can't solve for the type because of the passed through args/kwargs
                    message = cast(
                        WebhookMessage,
                        await self.ctx.interaction.followup.send(*args, **kwargs),
                    )
                except HTTPException:
                    if kwargs.get("ephemeral") is not None:
                        del kwargs["ephemeral"]
                    message = await self.ctx.channel.send(*args, **kwargs)  # Worst case
        self.ctx["response"] = message  # this is both neat and kinda broken
        return message


class CustomContext(Context["CustomBot"]):
    def __init__(self, **kwargs: Any):  # TODO: fix passthrough kwargs
        self._custom_state: Dict[str, Any] = {}
        self.send_handler: SendHandler = _DefaultSendHandler(self)
        # A NoOpSpan rather than a Transaction when tracing is off, so typed as their common base.
        self.sentry_transaction: Span | None = None
        self._sentry_scopes = ExitStack()
        super().__init__(**kwargs)

    # Sentry

    @property
    def sentry_tags(self) -> dict[str, str]:
        """Tags that describe this command invocation in Sentry."""
        tags = {"invocation": "slash" if self.interaction is not None else "prefix"}
        if self.command is not None:
            tags["command"] = self.command.qualified_name
        if self.cog is not None:
            tags["cog"] = self.cog.qualified_name
        if self.guild is not None:
            tags["guild_id"] = str(self.guild.id)
        return tags

    def start_sentry_transaction(self) -> None:
        """
        Open a Sentry transaction for this command, in its own scope so concurrent commands don't share spans or tags.

        It has to be finished from the same task it was started in. The bot's before_invoke and after_invoke hooks
        both run in the command's task, for prefix and slash invocations alike.
        """
        if self.command is None or self.sentry_transaction is not None:
            return

        scope = self._sentry_scopes.enter_context(sentry_sdk.isolation_scope())
        scope.set_user({"id": str(self.author.id)})
        for key, value in self.sentry_tags.items():
            scope.set_tag(key, value)

        self.sentry_transaction = self._sentry_scopes.enter_context(
            sentry_sdk.start_transaction(
                op="discord.command", name=self.command.qualified_name
            )
        )

    def finish_sentry_transaction(self) -> None:
        """Close the transaction opened by start_sentry_transaction, marking it failed if the command failed."""
        if self.sentry_transaction is None:
            return

        self.sentry_transaction.set_status(
            SPANSTATUS.INTERNAL_ERROR if self.command_failed else SPANSTATUS.OK
        )
        self._sentry_scopes.close()

    def report_error(self, error: BaseException) -> str | None:
        """Send an error raised by this command to Sentry. Returns the event ID, or None if reporting is off."""
        contexts: dict[str, dict[str, Any]] = {}
        if self.sentry_transaction is not None:
            # A prefix command's error handlers run after its transaction has closed, so link the trace explicitly.
            contexts["trace"] = self.sentry_transaction.get_trace_context()

        return sentry_sdk.capture_exception(
            error,
            user={"id": str(self.author.id)},
            tags=self.sentry_tags,
            contexts=contexts,
        )

    # Special cases for keys this bot uses often
    # Other keys are forbidden
    @overload
    def __getitem__(self, item: Literal["guild_document"]) -> PCDocument: ...

    @overload
    def __getitem__(self, item: Literal["author_document"]) -> PCDocument: ...

    @overload
    def __getitem__(self, item: Literal["response"]) -> Message: ...

    @overload
    def __getitem__(self, item: Literal["original_kwargs"]) -> dict[str, Any]: ...

    @overload
    def __getitem__(self, item: str) -> Any: ...

    # End special types

    def __getitem__(self, item: str) -> Any:
        return self._custom_state[item]

    # Special cases for keys this bot uses often
    # Other keys are forbidden
    @overload
    def __setitem__(
        self, key: Literal["guild_document"], value: PCDocument
    ) -> None: ...

    @overload
    def __setitem__(
        self, key: Literal["author_document"], value: PCDocument
    ) -> None: ...

    @overload
    def __setitem__(self, key: Literal["response"], value: Message) -> None: ...

    @overload
    def __setitem__(
        self, key: Literal["original_kwargs"], value: dict[str, Any]
    ) -> None: ...

    @overload
    def __setitem__(self, key: str, value: Any) -> None: ...

    # End special types

    def __setitem__(self, key: str, value: Any) -> None:
        self._custom_state[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self._custom_state

    def __delitem__(self, key: str) -> None:
        del self._custom_state[key]

    async def get_or_create_voice_client(self, **kwargs: Any) -> VoiceProtocol:
        """
        Shortcut to creating a custom voice client for the author's channel.
        If a client is already present, return that.
        """

        if isinstance(self.author, User):
            raise RuntimeError("Author isn't attached to a server!")
        elif self.author.voice is None:
            raise RuntimeError("Author doesn't have a tracked voice state!")
        elif self.author.voice.channel is None:
            raise RuntimeError("Author's isn't in a Voice channel!")

        return self.voice_client or await CustomVoiceClient.create(
            self.author.voice.channel, **kwargs
        )

    def send(
        self, *args: Any, **kwargs: Any
    ) -> Coroutine[Any, Any, Message]:  # TODO: Fix passthrough kwargs
        return self.send_handler.send(*args, **kwargs)

    def send_bare(
        self, *args: Any, **kwargs: Any
    ) -> Coroutine[Any, Any, Message]:  # TODO: Fix passthrough kwargs
        return super().send(*args, **kwargs)


__all__: list[str] = [
    "CustomContext",
    "SendHandler",
]

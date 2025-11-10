from abc import ABC
from typing import Dict, Any, Literal, Self, cast, TYPE_CHECKING, Coroutine, overload

from discord import (
    Interaction,
    Message,
    HTTPException,
    User,
    VoiceProtocol,
    WebhookMessage,
)
from discord.ext.commands import Context

from utils.database import PCDocument

from .audio import *

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


class CustomContext(Context[CustomBot]):
    def __init__(self, **kwargs: Any):  # TODO: fix passthrough kwargs
        self._custom_state: Dict[str, Any] = {}
        self.send_handler: SendHandler = _DefaultSendHandler(self)
        super().__init__(**kwargs)

    # Special cases for keys this bot uses often
    # Other keys are forbidden
    @overload
    def __getitem__(self, item: Literal["guild_document"]) -> PCDocument: ...

    @overload
    def __getitem__(self, item: Literal["author_document"]) -> PCDocument: ...

    @overload
    def __getitem__(self, item: Literal["command_document"]) -> PCDocument: ...

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
    def __setitem__(
        self, key: Literal["command_document"], value: PCDocument
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

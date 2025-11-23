from io import BytesIO
from typing import Iterable, Optional, List, Callable, Union, Coroutine, Any

from discord import (
    AllowedMentions,
    File,
    HTTPException,
    Member,
    Message,
    TextChannel,
    Webhook,
    WebhookMessage,
)
from discord.abc import User as ABCUser
from discord.utils import MISSING as D_MISSING, maybe_coroutine

from utils.bots.bot import CustomBot
from utils.bots.context import SendHandler
from utils.database import PCDocument
from utils.misc import split_str_chunks


async def get_or_create_namespaced_webhook(
    namespace: str,
    bot: CustomBot,
    channel: TextChannel,
    **kwargs: Any,
) -> Webhook:
    guild_doc: PCDocument = await bot.get_guild_document(channel.guild)
    existing_webhook: Optional[int] = (
        await guild_doc.safe_get(f"{namespace}_webhooks", {})
    ).get(str(channel.id))
    maybe_webhook: Optional[Webhook]
    try:
        maybe_webhook = (
            await bot.fetch_webhook(existing_webhook)
            if existing_webhook is not None
            else None
        )
    except HTTPException:
        await guild_doc.update_db({"$unset": {f"{namespace}_webhooks.{channel.id}": 1}})
        maybe_webhook = None
    if maybe_webhook is None:
        if kwargs.get("name") is None:
            kwargs["name"] = namespace.upper()
        webhook = await channel.create_webhook(**kwargs)
        await guild_doc.update_db(
            {"$set": {f"{namespace}_webhooks.{channel.id}": webhook.id}}
        )
        return webhook
    else:
        return maybe_webhook


async def impersonate(
    webhook: Webhook,
    victim: ABCUser,
    *args: Any,
    **kwargs: Any,
) -> WebhookMessage:
    if kwargs.get("avatar_url") is None:
        kwargs["avatar_url"] = victim.display_avatar.url
    if kwargs.get("username") is None:
        kwargs["username"] = victim.display_name
    if kwargs.get("wait") is None:
        kwargs["wait"] = True  # guarantees returned object
    elif kwargs["wait"] is False:
        raise RuntimeError(
            "Can't impersonate a message without waiting for the message!"
        )
    return await webhook.send(*args, **kwargs)  # type: ignore[no-any-return] # guaranteed by runtime checks


async def resend_as_webhook(
    webhook: Webhook,
    message: Message,
    *,
    content: Optional[str] = None,
    clean: bool = True,
) -> WebhookMessage:
    content = content or (message.clean_content if clean else message.content)
    if not isinstance(message.author, Member) or message.guild is None:
        raise RuntimeError("Can't resend as a webhook outside of a guild!")

    return await impersonate(
        webhook,
        message.author,
        (content if len(message.clean_content) > 0 else D_MISSING),
        # inherit the allowed mentions of the original author
        allowed_mentions=(
            AllowedMentions(
                everyone=message.author.guild_permissions.mention_everyone,
                users=True,
                roles=(
                    message.author.guild_permissions.manage_roles
                    or [role for role in message.guild.roles if role.mentionable]
                ),
            )
        ),
        embeds=message.embeds if len(message.embeds) > 0 else D_MISSING,
        files=(
            [
                File(BytesIO(await attachment.read()), filename=attachment.filename)
                for attachment in message.attachments
            ]
            if len(message.attachments) > 0
            else D_MISSING
        ),
    )


async def resend_message_with_filter(
    message: Message,
    filter_callable: Callable[[str], Union[str, Coroutine[Any, Any, str]]],
    webhook: Webhook,
    *,
    delete_message: bool = True,
) -> WebhookMessage | Iterable[WebhookMessage]:
    filtered_message = await maybe_coroutine(filter_callable, message.clean_content)

    webhook_message: WebhookMessage | Iterable[WebhookMessage]
    if len(filtered_message) > 2000:
        webhook_message = [
            await resend_as_webhook(webhook, message, content=message_fragment)
            for message_fragment in split_str_chunks(filtered_message, chunk_size=2000)
        ]
    else:
        webhook_message = await resend_as_webhook(
            webhook, message, content=filtered_message
        )

    if delete_message:
        await message.delete()  # We don't see this now.

    return webhook_message


class WebhookSendHandler(SendHandler):
    def __init__(self, webhook: Webhook) -> None:
        self.webhook: Webhook = webhook

    async def send(self, *args: Any, **kwargs: Any) -> Message:
        if kwargs.get("ephemeral") is not None:
            del kwargs["ephemeral"]
        if kwargs.get("return_message") is not None:
            del kwargs["return_message"]
        if kwargs.get("reference") is not None:
            del kwargs["reference"]
        if kwargs.get("wait") is None:
            kwargs["wait"] = True  # guarantees returned object
        elif kwargs["wait"] is False:
            raise RuntimeError(
                "Can't impersonate a message without waiting for the message!"
            )
        return await self.webhook.send(*args, **kwargs)  # type: ignore[no-any-return] # guaranteed by runtime checks


class ImpersonateSendHandler(WebhookSendHandler):
    def __init__(self, webhook: Webhook, victim: ABCUser) -> None:
        super().__init__(webhook)
        self.victim = victim

    async def send(self, *args: Any, **kwargs: Any) -> Message:
        if kwargs.get("ephemeral") is not None:
            del kwargs["ephemeral"]
        if kwargs.get("return_message") is not None:
            del kwargs["return_message"]
        if kwargs.get("reference") is not None:
            del kwargs["reference"]
        return await impersonate(self.webhook, self.victim, *args, **kwargs)


__all__: List[str] = [
    "get_or_create_namespaced_webhook",
    "resend_as_webhook",
    "impersonate",
    "resend_message_with_filter",
    "WebhookSendHandler",
    "ImpersonateSendHandler",
]

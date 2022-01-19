from io import BytesIO
from typing import Optional, List, Callable, Union, Coroutine, Any

import discord

from utils import bots
from utils.database import Document
from utils.misc import split_string_chunks


async def get_or_create_namespaced_webhook(
        namespace: str, bot: bots.BOT_TYPES,
        channel: discord.TextChannel,
        **kwargs: Any,
) -> discord.Webhook:
    guild_doc: Document = await bot.get_guild_document(channel.guild)
    existing_webhook: Optional[int] = guild_doc.get(f"{namespace}_webhooks", {}).get(str(channel.id))
    try:
        maybe_webhook: Optional[discord.Webhook] = await bot.fetch_webhook(existing_webhook) \
            if existing_webhook is not None \
            else None
    except discord.HTTPException:
        await guild_doc.update_db({"$unset": {f"{namespace}_webhooks.{channel.id}": 1}})
        maybe_webhook: Optional[discord.Webhook] = None
    except Exception:
        raise
    if maybe_webhook is None:
        if kwargs.get("name") is None:
            kwargs["name"] = namespace.upper()
        webhook: discord.Webhook = await channel.create_webhook(**kwargs)
        await guild_doc.update_db({"$set": {f"{namespace}_webhooks.{channel.id}": webhook.id}})
        return webhook
    else:
        return maybe_webhook


async def impersonate(
        webhook: discord.Webhook,
        victim: discord.abc.User,
        *args: Any,
        **kwargs: Any,
) -> Optional[discord.WebhookMessage]:
    if kwargs.get("avatar_url") is None:
        kwargs["avatar_url"] = (victim.guild_avatar.url
                                if victim.guild_avatar is not None
                                else victim.avatar.url) \
            if hasattr(victim, "guild_avatar") \
            else victim.avatar.url
    if kwargs.get("username") is None:
        kwargs["username"] = victim.display_name
    return await webhook.send(*args, **kwargs)


async def resend_as_webhook(
        webhook: discord.Webhook,
        message: discord.Message,
        *,
        content: Optional[str] = None,
        clean: bool = True,
) -> Optional[discord.WebhookMessage]:
    content: str = content or (message.clean_content if clean else message.content)
    return await impersonate(
        webhook,
        message.author,
        (
            content
            if len(message.clean_content) > 0
            else discord.utils.MISSING
        ),
        allowed_mentions=(
            discord.AllowedMentions(
                everyone=False,
                users=True,
                roles=[role for role in message.guild.roles if role.mentionable]
            )
        ),
        embeds=message.embeds if len(message.embeds) > 0 else discord.utils.MISSING,
        files=(
            [
                discord.File(BytesIO(await attachment.read()), filename=attachment.filename)
                for attachment
                in message.attachments
            ]
            if len(message.attachments) > 0
            else discord.utils.MISSING
        ),
    )


async def filter_message(
        message: discord.Message,
        filter_callable: Callable[[str], Union[str, Coroutine[Any, Any, str]]],
        webhook: discord.Webhook,
        *,
        delete_message: bool = True,
) -> Optional[discord.WebhookMessage]:
    message: discord.Message = message if isinstance(message, discord.Message) else message.message
    filtered_message: str = await discord.utils.maybe_coroutine(filter_callable, message.clean_content)

    if len(filtered_message) > 2000:
        webhook_message: Optional[discord.WebhookMessage] = None
        for message_fragment in split_string_chunks(filtered_message, chunk_size=2000):
            await resend_as_webhook(webhook, message, content=message_fragment)
    else:
        webhook_message: Optional[discord.WebhookMessage] = await resend_as_webhook(
            webhook,
            message,
            content=filtered_message
        )

    if delete_message:
        await message.delete()  # We don't see this now.

    return webhook_message


class WebhookSendHandler(bots.SendHandler):
    def __init__(self, webhook: discord.Webhook) -> None:
        self.webhook: discord.Webhook = webhook

    async def send(self, *args, **kwargs) -> discord.Message:
        if kwargs.get("ephemeral") is not None:
            del kwargs["ephemeral"]
        if kwargs.get("return_message") is not None:
            del kwargs["return_message"]
        if kwargs.get("reference") is not None:
            del kwargs["reference"]
        return await self.webhook.send(*args, **kwargs)


class ImpersonateSendHandler(WebhookSendHandler):
    def __init__(self, webhook: discord.Webhook, victim: discord.abc.User) -> None:
        super().__init__(webhook)
        self.victim: discord.abc.User = victim

    async def send(self, *args, **kwargs) -> discord.Message:
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
    "filter_message",
    "WebhookSendHandler",
    "ImpersonateSendHandler"
]

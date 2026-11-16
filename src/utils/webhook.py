from typing import Optional, List, Any

from discord import HTTPException, TextChannel, Webhook, WebhookMessage
from discord.abc import User as ABCUser

from utils.bots.bot import CustomBot
from utils.database import PCDocument


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


__all__: List[str] = [
    "get_or_create_namespaced_webhook",
    "impersonate",
]

from io import BytesIO
from typing import Optional, List, Callable, Union, Coroutine, Any

import discord

from utils import bots
from utils.database import Document


async def get_or_create_namespaced_webhook(namespace: str, bot: Union[bots.BOT_TYPES, bots.CustomContext],
                                           channel: discord.TextChannel) -> discord.Webhook:
    bot: bots.BOT_TYPES = bot if isinstance(bot, (bots.CustomBot, bots.CustomAutoShardedBot)) else bot.bot
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
        webhook: discord.Webhook = await channel.create_webhook(name=namespace.upper())
        await guild_doc.update_db({"$set": {f"{namespace}_webhooks.{channel.id}": webhook.id}})
        return webhook
    else:
        return maybe_webhook


async def filter_message(
        message: Union[discord.Message, bots.CustomContext],
        filter_callable: Callable[[str], Union[str, Coroutine[Any, Any, str]]],
        webhook: Optional[discord.Webhook] = None,
        *,
        delete_message: bool = True,
        namespace: str = "filter",
        bot: Optional[bots.BOT_TYPES] = None,
) -> Optional[discord.WebhookMessage]:
    webhook: discord.Webhook = webhook \
                               or await get_or_create_namespaced_webhook(
                                   namespace,
                                   message if isinstance(message, bots.CustomContext) else bot,
                                   message.channel
                               )
    message: discord.Message = message if isinstance(message, discord.Message) else message.message
    webhook_message: Optional[discord.WebhookMessage] = await webhook.send(
        content=await discord.utils.maybe_coroutine(filter_callable, message.clean_content)
        if len(message.clean_content) > 0
        else discord.utils.MISSING,
        username=message.author.display_name,
        avatar_url=message.author.guild_avatar.url
        if message.author.guild_avatar is not None
        else message.author.avatar.url,
        allowed_mentions=discord.AllowedMentions(
            everyone=False,
            users=True,
            roles=[role for role in message.guild.roles if role.mentionable]
        ),
        embeds=message.embeds if len(message.embeds) > 0 else discord.utils.MISSING,
        files=[
            discord.File(BytesIO(await attachment.read()), filename=attachment.filename)
            for attachment
            in message.attachments
        ]
        if len(message.attachments) > 0
        else discord.utils.MISSING,
    )

    if delete_message:
        await message.delete()  # We don't see this now.

    return webhook_message


__all__: List[str] = [
    "get_or_create_namespaced_webhook",
    "filter_message"
]

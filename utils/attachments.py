from typing import Optional, Tuple, Union, TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from utils.bots import BOT_TYPES


class NoMedia(Exception):
    """Raised when no media is found."""

    pass


class BadMedia(Exception):
    """Raised when"""

    pass


class WrongMedia(BadMedia):
    pass


class MediaTooLarge(BadMedia):
    pass


class MediaTooLong(BadMedia):
    pass


async def find_url(
        message: discord.Message, bot: "BOT_TYPES"
) -> Tuple[str, Union[discord.Attachment, discord.Embed]]:
    """
    Finds the URL of media attached to a message.

    If a message is replying to another message, recurse on that message.

    Else, if a message has attachments, return the first attachment's URL and it's object instance.

    Else, if a message has embeds from an extraneous source, return the first embed's URL and it's object instance.
    """

    if not isinstance(message, discord.Message):  # Must be a _FakeSlashMessage
        raise NoMedia
    if message.attachments:
        attachment: discord.Attachment = message.attachments[0]

        return attachment.url, attachment
    elif message.embeds and message.embeds[0].type != "rich":
        embed: discord.Embed = message.embeds[0]

        if embed.type == "gifv":
            embed_url = embed.video.url
        else:
            embed_url = embed.url

        return embed_url, embed
    elif message.reference:
        referenced_message: Optional[discord.Message] = message.reference.cached_message
        if referenced_message is None:
            referenced_message = await bot.smart_fetch_message(message.channel, message.reference.message_id)

        return await find_url(referenced_message, bot)
    else:
        raise NoMedia


async def find_url_recurse(
        message: discord.Message, bot: "BOT_TYPES"
) -> Tuple[str, Union[discord.Attachment, discord.Embed]]:
    """Attempts to find the media URL of a message,
    and if no message is found, iterate over messages in the channel history."""

    try:
        return await find_url(message, bot)
    except NoMedia:
        async for message in message.channel.history(
                before=message.created_at, limit=50
        ):
            try:
                return await find_url(message, bot)
            except NoMedia:
                continue
        raise


__all__ = [
    "find_url",
    "find_url_recurse",
    "NoMedia",
    "BadMedia",
    "WrongMedia",
    "MediaTooLarge",
    "MediaTooLong",
]

from typing import Optional, Tuple, Union

import discord


class NoMedia(Exception):
    """Raised when no media is found."""

    pass


class BadMedia(Exception):
    """Raised when """

    pass


class WrongMedia(BadMedia):
    pass


class MediaTooLarge(BadMedia):
    pass


class MediaTooLong(BadMedia):
    pass


async def find_url(message: discord.Message) -> Tuple[str, Union[discord.Attachment, discord.Embed]]:
    """
    Finds the URL of media attached to a message.

    If a message is replying to another message, recurse on that message.

    Else, if a message has attachments, return the first attachment's URL and it's object instance.

    Else, if a message has embeds from an extraneous source, return the first embed's URL and it's object instance.
    """

    if message.reference:
        referenced_message: Optional[discord.Message] = message.reference.cached_message
        if referenced_message is None:
            referenced_message = await message.channel.fetch_message(message.reference.message_id)

        return await find_url(referenced_message)
    elif message.attachments:
        attachment: discord.Attachment = message.attachments[0]

        return attachment.url, attachment
    elif message.embeds and message.embeds[0].type != "rich":
        embed: discord.Embed = message.embeds[0]

        if embed.type == "gifv":
            embed_url = embed.video.url
        else:
            embed_url = embed.url

        return embed_url, embed
    raise NoMedia


async def find_url_recurse(message: discord.Message) -> Tuple[str, Union[discord.Attachment, discord.Embed]]:
    """Attempts to find the media URL of a message,
    and if no message is found, iterate over messages in the channel history."""

    try:
        return await find_url(message)
    except NoMedia:
        async for message in message.channel.history(before=message.created_at, limit=50):
            try:
                return await find_url(message)
            except NoMedia:
                continue
        raise


__all__ = ["find_url", "find_url_recurse", "NoMedia", "BadMedia", "WrongMedia", "MediaTooLarge", "MediaTooLong"]

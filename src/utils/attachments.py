from typing import Optional, Tuple, Union, TYPE_CHECKING, cast

import discord

from utils.bots.bot import CustomBot


class NoMedia(Exception):
    """Raised when no media is found."""

    pass


class BadMedia(Exception):
    pass


class WrongMedia(BadMedia):
    pass


class MediaTooLarge(BadMedia):
    pass


class MediaTooLong(BadMedia):
    pass


async def find_url(
    message: discord.Message, bot: CustomBot
) -> Tuple[str, Union[discord.Attachment, discord.Embed]]:
    """
    Finds the URL of the first media attached to a message.

    If a message is replying to another message, recurse on that message.

    Else, if a message has attachments, return the first attachment's URL and it's object instance.

    Else, if a message has embeds from an extraneous source, return the first embed's URL and it's object instance.
    """

    if not isinstance(message, discord.Message):  # Must be a _FakeSlashMessage
        raise NoMedia

    if message.attachments:
        attachment = message.attachments[0]
        return attachment.url, attachment
    elif message.embeds:
        for embed in message.embeds:
            match embed.type:
                case "image":
                    # Won't be None with this type
                    return cast(str, embed.url), embed
                case "gifv":
                    # Won't be None with this type
                    return cast(str, embed.video.url), embed
                case _:
                    continue

    if message.reference:
        referenced_message: Optional[discord.Message] = message.reference.cached_message
        if referenced_message is None:
            # reference.message_id is only None when the reference is a system message, and to my knowledge users can't reply to those directly with normal messages
            referenced_message = await message.channel.fetch_message(
                cast(int, message.reference.message_id)
            )

        return await find_url(referenced_message, bot)

    raise NoMedia


async def find_url_recurse(
    message: discord.Message, bot: CustomBot
) -> Tuple[str, Union[discord.Attachment, discord.Embed]]:
    """Attempts to find the media URL of a message,
    and if no message is found, iterate over messages in the channel history."""

    try:
        return await find_url(message, bot)
    except NoMedia:
        async for message in message.channel.history(
            before=message.created_at, limit=50  # TODO: extract magic number
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

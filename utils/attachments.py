from typing import Optional, Tuple, Union

import discord


class BadMedia(Exception):
    pass


class NoMedia(BadMedia):
    pass


class WrongMedia(BadMedia):
    pass


async def find_url(message: discord.Message) -> Tuple[str, Union[discord.Attachment, discord.Embed]]:
    if message.reference:
        referenced_message: Optional[discord.Message] = message.reference.cached_message
        if referenced_message is None:
            referenced_message: discord.Message = await message.channel.fetch_message(message.reference.message_id)

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
    try:
        return await find_url(message)
    except NoMedia:
        async for message in message.channel.history(before=message.created_at, limit=50):
            try:
                return await find_url(message)
            except NoMedia:
                continue
        raise


__all__ = ["find_url", "find_url_recurse", "NoMedia", "BadMedia", "WrongMedia"]

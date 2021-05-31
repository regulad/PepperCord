"""Checks for voice."""

import utils.errors as errors
from .permissions import is_man


async def is_in_voice(ctx):
    """Returns true if a user is in a voice channel, raises utils.errors.NotInVoiceChannel if not."""

    if ctx.author.voice is None:
        raise errors.NotInVoiceChannel()
    else:
        return True


async def is_alone(ctx):
    """Returns true if the user is alone in a voice channel, raises utils.errors.NotAlone if they arent."""

    await is_in_voice(ctx)
    channel = ctx.author.voice.channel
    if len(channel.members) > 2:
        raise errors.NotAlone()
    else:
        return True
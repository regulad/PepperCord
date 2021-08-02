from discord.ext import commands

from utils.bots import CustomContext


class NotInVoiceChannel(commands.CheckFailure):
    """Raised when a user should be in a voice channel and they are not."""

    pass


class NotAlone(commands.CheckFailure):
    """Raised when a user should be alone in a voice channel and they are not."""

    pass


async def is_in_voice(ctx: CustomContext) -> bool:
    """Returns true if a user is in a voice channel, raises NotInVoiceChannel if not."""

    return ctx.author.voice is not None


@commands.check
async def check_is_in_voice(ctx: CustomContext) -> bool:
    """Returns true if a user is in a voice channel, raises NotInVoiceChannel if not."""

    if not await is_in_voice(ctx):
        raise NotInVoiceChannel
    else:
        return True


async def is_alone(ctx: CustomContext) -> bool:
    """Returns true if the user is alone in a voice channel, raises NotAlone if they arent.

    Will raise AttributeError if the user does not have a VoiceState."""

    return len(ctx.author.voice.channel.members) <= 1


@commands.check
async def check_is_alone(ctx: CustomContext) -> bool:
    """Returns true if the user is alone in a voice channel, raises NotAlone if they arent."""

    if not await is_in_voice(ctx):
        raise NotInVoiceChannel
    elif not await is_alone(ctx):
        raise NotAlone
    else:
        return True


__all__ = ["NotInVoiceChannel", "NotAlone", "is_alone", "is_in_voice", "check_is_alone", "check_is_in_voice"]

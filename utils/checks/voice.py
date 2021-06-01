from discord.ext import commands


class NotInVoiceChannel(commands.CheckFailure):
    pass


class NotAlone(commands.CheckFailure):
    pass


async def is_in_voice(ctx):
    """Returns true if a user is in a voice channel, raises NotInVoiceChannel if not."""

    if ctx.author.voice is None:
        raise NotInVoiceChannel
    else:
        return True


async def is_alone(ctx):
    """Returns true if the user is alone in a voice channel, raises NotAlone if they arent."""

    await is_in_voice(ctx)
    channel = ctx.author.voice.channel
    if len(channel.members) > 2:
        raise NotAlone
    else:
        return True

from discord import TextChannel, Thread
from discord.ext.commands import CheckFailure, check

from utils.bots import CustomContext, CustomVoiceClient


class CantCreateAudioClient(CheckFailure):
    """The invoker of this command does not have a valid voice channel that can be joined."""

    pass


async def can_have_voice_client(ctx: CustomContext) -> bool:
    try:
        assert ctx.guild is not None
        custom_voice_client: CustomVoiceClient = await ctx.get_or_create_voice_client()
        if custom_voice_client.bound is None and isinstance(
            ctx.channel, (TextChannel, Thread)
        ):
            custom_voice_client.bind(ctx.channel)
    except AttributeError:
        return False
    except AssertionError:
        return False
    except Exception:
        raise
    else:
        return True


async def check_voice_client_predicate(ctx: CustomContext) -> bool:
    if await can_have_voice_client(ctx):
        return True
    else:
        raise CantCreateAudioClient


@check
async def check_voice_client(ctx: CustomContext) -> bool:
    return await check_voice_client_predicate(ctx)


__all__: list[str] = [
    "CantCreateAudioClient",
    "can_have_voice_client",
    "check_voice_client",
    "check_voice_client_predicate",
]

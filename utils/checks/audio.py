from discord.ext.commands import CheckFailure, check

from utils.bots import CustomContext


class CantCreateAudioClient(CheckFailure):
    """The invoker of this command does not have a valid voice channel that can be joined."""

    pass


async def can_have_voice_client(ctx: CustomContext) -> bool:
    try:
        await ctx.get_or_create_voice_client()
    except AttributeError:
        return False
    except Exception:
        raise
    else:
        return True


@check
async def check_voice_client(ctx: CustomContext) -> bool:
    if await can_have_voice_client(ctx):
        return True
    else:
        raise CantCreateAudioClient


__all__: list[str] = [
    "CantCreateAudioClient",
    "can_have_voice_client",
    "check_voice_client"
]

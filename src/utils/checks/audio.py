from discord import TextChannel, Thread
from discord.ext.commands import CheckFailure, check

from utils.audio import CustomVoiceClient
from utils.bots.context import CustomContext


class CantCreateAudioClient(CheckFailure):
    """The invoker of this command does not have a valid voice channel that can be joined."""

    pass


async def can_have_voice_client(ctx: CustomContext) -> bool:
    """
    Predicate to check if a context is capable of holding a voice client.
    Has the side effect of creating & attaching a voice client.
    """

    try:
        assert ctx.guild is not None
        custom_voice_client = await ctx.get_or_create_voice_client()

        if not isinstance(custom_voice_client, CustomVoiceClient):
            raise RuntimeError(
                "Created a custom voice client, but it wasn't of type CustomVoiceClient!"
            )

        if custom_voice_client.bound is None and isinstance(
            ctx.channel, (TextChannel, Thread)
        ):
            custom_voice_client.bind(ctx.channel)
    except AttributeError:
        return False
    except AssertionError:
        return False
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

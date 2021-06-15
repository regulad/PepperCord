from typing import Union
import os
from json import load

from discord.ext import commands
from asyncgTTS import ServiceAccount, AsyncGTTSSession
from aiohttp import ClientSession

from utils import checks
from utils.embed_menus import AudioSourceMenu
from utils.sources import TTSSource
from utils import bots


class TextToSpeech(commands.Cog):
    """Sends Text-To-Speech in the voice chat."""

    def __init__(self, bot: Union[bots.CustomBot, bots.CustomAutoShardedBot]):
        self.bot = bot

    async def cog_check(self, ctx: bots.CustomContext):
        return await checks.is_in_voice(ctx) and await checks.is_a_voter(ctx)

    async def cog_before_invoke(self, ctx: bots.CustomContext):
        if ctx.voice_client is None:
            await ctx.author.voice.channel.connect()

    @commands.command(
        name="tts",
        aliases=["texttospeech"],
        brief="Queue some text-to-speech audio.",
        description="Turns text into speech and adds it to the audio queue.",
        usage="<Text>"
    )
    @commands.cooldown(10, 2, commands.BucketType.user)
    async def text_to_speech(self, ctx: bots.CustomContext, *, text: str) -> None:
        async with ctx.typing():
            source = await TTSSource.from_text(text, ctx.bot.async_gtts_session, ctx.author)

            if not len(list(ctx.audio_player.queue.deque)) > 0:
                ctx.audio_player.queue.put_nowait(source)
            else:
                ctx.audio_player.queue.deque.appendleft(source)  # Meh.

            await AudioSourceMenu(source).start(ctx)


def setup(bot: Union[bots.CustomBot, bots.CustomAutoShardedBot]):
    if os.path.exists("config/SERVICE_ACCOUNT.json"):
        with open("config/SERVICE_ACCOUNT.json") as service_account_fp:
            bot.service_account = ServiceAccount.from_service_account_dict(load(service_account_fp))

        bot.gtts_client_session = ClientSession()
        bot.async_gtts_session = AsyncGTTSSession.from_service_account(
            bot.service_account, client_session=bot.gtts_client_session
        )

        bot.add_cog(TextToSpeech(bot))


def teardown(bot: Union[bots.CustomBot, bots.CustomAutoShardedBot]):
    if bot.async_gtts_session is not None:
        bot.remove_cog("TextToSpeech")

        bot.loop.create_task(bot.gtts_client_session.close())
        # Not perfect, but it shouldn't be that big of an issue.
        # It isn't normally mission critical to close the connection.
        # I should really consider reworking the way connections are closed for the AsyncGTTSSession.

from discord.ext import commands

from utils import checks
from utils.embed_menus import AudioSourceMenu
from utils.sources import TTSSource


class TextToSpeech(commands.Cog):
    """Sends Text-To-Speech in the voice chat."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await checks.is_in_voice(ctx)

    async def cog_before_invoke(self, ctx):
        if ctx.voice_client is None:
            await ctx.author.voice.channel.connect()

    @commands.command(
        name="tts",
        aliases=["texttospeech"],
        brief="Queue some text-to-speech audio.",
        description="Adds text-to-speech audio from https://gist.github.com/regulad/9b5725f941beff3adc42f52961abd7a6 "
                    "to the currently running audio queue.",
        usage="<Text>"
    )
    @commands.cooldown(10, 2, commands.BucketType.user)
    async def text_to_speech(self, ctx, *, text: str):
        async with ctx.typing():
            source = await TTSSource.from_text(text, ctx.audio_player.tts_client_session, ctx.author)

            if not len(list(ctx.audio_player.queue.deque)) > 0:
                ctx.audio_player.queue.put_nowait(source)
            else:
                ctx.audio_player.queue.deque.appendleft(source)  # Meh.

            await AudioSourceMenu(source).start(ctx)


def setup(bot):
    bot.add_cog(TextToSpeech(bot))

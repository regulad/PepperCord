import random

from discord.ext import commands, menus

from utils import checks, embed_menus
from utils.bots import CustomContext, BOT_TYPES
from utils.checks import NotInVoiceChannel, is_in_voice


class AudioQueue(commands.Cog):
    """Commands that manage the Audio Player's queue."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot

    @commands.Cog.listener()
    async def on_context_creation(self, ctx: CustomContext) -> None:
        ctx["audio_player"] = lambda: ctx.bot.get_audio_player(ctx.voice_client)

    async def cog_check(self, ctx: CustomContext) -> bool:
        if not await is_in_voice(ctx):
            raise NotInVoiceChannel
        else:
            return True

    async def cog_before_invoke(self, ctx: CustomContext) -> None:
        if ctx.voice_client is None:
            await ctx.author.voice.channel.connect()

    @commands.group()
    async def player(self, ctx: CustomContext) -> None:
        """A suite of commands for controlling the audio player."""
        pass

    @player.command()
    @commands.check_any(checks.check_is_man, checks.check_is_alone)
    async def stop(self, ctx: CustomContext) -> None:
        """Stops playing audio and leaves the voice channel."""
        await ctx["audio_player"]().voice_client.disconnect()
        await ctx.send("Disconnected.", ephemeral=True)

    @player.command()
    async def pause(self, ctx: CustomContext) -> None:
        """Pauses or plays the audio player."""
        if ctx["audio_player"]().paused:
            ctx["audio_player"]().voice_client.resume()
            await ctx.send("Playing.", ephemeral=True)
        else:
            ctx["audio_player"]().voice_client.pause()
            await ctx.send("Paused.", ephemeral=True)

    @player.command()
    @commands.check_any(checks.check_is_man, checks.check_is_alone)
    async def skip(self, ctx: CustomContext) -> None:
        """Skips foward to the next song on the track queue."""
        ctx["audio_player"]().voice_client.stop()
        await ctx.send("Stopped.", ephemeral=True)

    @player.group()
    async def queue(self, ctx: CustomContext) -> None:
        """Commands for controlling the queue of tracks that are about to be played."""
        pass

    @queue.command()
    async def list(self, ctx: CustomContext) -> None:
        """List all songs on the queue."""
        source = embed_menus.QueueMenuSource(
            list(ctx["audio_player"]().queue.deque),
            f"Current tracks on queue:{' (Loop on)' if ctx['audio_player']().loop else ''}",
        )
        await menus.ViewMenuPages(source=source).start(ctx, ephemeral=True)

    @queue.command()
    @commands.check_any(checks.check_is_man, checks.check_is_alone)
    async def shuffle(self, ctx: CustomContext) -> None:
        """Shuffle all songs on the queue."""
        if len(list(ctx["audio_player"]().queue.deque)) > 0:
            random.shuffle(ctx["audio_player"]().queue.deque)
        await ctx.send("Shuffled.")

    @queue.command()
    @commands.check_any(checks.check_is_man, checks.check_is_alone)
    async def loop(self, ctx: CustomContext) -> None:
        """Toggles the loop function. While the loop is on, the current song will keep repeating."""
        ctx["audio_player"]().loop = not ctx["audio_player"]().loop
        await ctx.send(f"Loop is {'on' if ctx['audio_player']().loop else 'off'}.")

    @queue.command()
    @commands.check_any(checks.check_is_man, checks.check_is_alone)
    async def clear(self, ctx: CustomContext) -> None:
        """Clears all songs on the queue."""
        ctx["audio_player"]().queue.clear()
        ctx.voice_client.stop()
        await ctx.send("Queue cleared.", ephemeral=True)

    @queue.command()
    @commands.check_any(checks.check_is_man, checks.check_is_alone)
    async def pop(
        self,
        ctx: CustomContext,
        *,
        index: int = commands.Option(
            description="The position of the track in the queue."
        ),
    ) -> None:
        """Removes a song from the queue at a position of your choice."""
        del ctx["audio_player"]().queue.deque[index - 1]
        await ctx.send("Track removed.", ephemeral=True)

    @commands.command()
    async def nowplaying(self, ctx: CustomContext) -> None:
        playing_track = ctx["audio_player"]().voice_client.source
        if playing_track is None:
            await ctx.send("No track is playing.")
        else:
            await embed_menus.AudioSourceMenu(playing_track).start(ctx)


def setup(bot: BOT_TYPES):
    bot.add_cog(AudioQueue(bot))

import random

from discord.ext import commands, menus

from utils import checks, embed_menus


class AudioQueue(commands.Cog):
    """Commands that manage the Audio Player's queue."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await checks.is_in_voice(ctx)

    async def cog_before_invoke(self, ctx):
        if ctx.voice_client is None:
            await ctx.author.voice.channel.connect()

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="audioplayer",
        aliases=["ap", "mp"],
        brief="Commands for the audio player.",
        description="Commands for controlling the audio player.",
    )
    async def player(self, ctx):
        pass

    @player.command(
        name="stop",
        aliases=["s"],
        brief="Stops playing.",
        description="Stops playing audio.",
    )
    @commands.check_any(commands.check(checks.is_man), commands.check(checks.is_alone))
    async def pstop(self, ctx):
        await ctx.audio_player.voice_client.disconnect()

    @player.command(
        name="pause",
        aliases=["play", "p"],
        brief="Toggles the audio player on and off.",
        description="Toggles the audio player between playing and paused.",
    )
    async def ppause(self, ctx):
        if ctx.audio_player.paused:
            ctx.audio_player.voice_client.resume()
        else:
            ctx.audio_player.voice_client.pause()

    @player.command(
        name="skip",
        aliases=["sk"],
        brief="Skips to the next song on the queue.",
        description="Skips the audio player to the next song on the queue.",
    )
    @commands.check_any(commands.check(checks.is_man), commands.check(checks.is_alone))
    async def pskip(self, ctx):
        ctx.audio_player.voice_client.stop()

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="queue",
        aliases=["q"],
        brief="Commands for the queue.",
        description="Commands for the active queue currently being played.",
    )
    async def queuecommand(self, ctx):
        source = embed_menus.QueueMenuSource(list(ctx.audio_player.queue.deque), "Current tracks on queue:")
        pages = menus.MenuPages(source=source)
        await pages.start(ctx)

    @queuecommand.command(
        name="shuffle",
        brief="Shuffles the current queue.",
        description="Shuffles the current queue. Note that this changes the queue.",
    )
    @commands.check_any(commands.check(checks.is_man), commands.check(checks.is_alone))
    async def qshuffle(self, ctx):
        if len(list(ctx.audio_player.queue.deque)) > 0:
            random.shuffle(ctx.audio_player.queue.deque)

    @queuecommand.command(
        name="clear",
        aliases=["delete"],
        brief="Deletes all items on the queue.",
        description="Deletes all items on the queue, leaving behind a blank slate.",
    )
    @commands.check_any(commands.check(checks.is_man), commands.check(checks.is_alone))
    async def qclear(self, ctx):
        ctx.audio_player.queue.clear()
        ctx.voice_client.stop()

    @queuecommand.command(
        name="pop",
        aliases=["remove"],
        brief="Pops a track off of the queue.",
        description="Pops a track of the queue. Index starts at 1.",
    )
    @commands.check_any(commands.check(checks.is_man), commands.check(checks.is_alone))
    async def qpop(self, ctx, *, index: int):
        del ctx.audio_player.queue.deque[index - 1]

    @commands.command(
        name="nowplaying",
        aliases=["np"],
        brief="Shows the currently playing track.",
        description="Shows the currently playing track.",
    )
    async def nowplaying(self, ctx):
        playing_track = ctx.audio_player.voice_client.source
        if playing_track is None:
            await ctx.send("No track is playing.")
        else:
            await embed_menus.AudioSourceMenu(playing_track).start(ctx)


def setup(bot):
    bot.add_cog(AudioQueue(bot))

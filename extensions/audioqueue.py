import random

from discord.ext import commands, menus

from utils.bots import CustomContext, BOT_TYPES
from utils import checks, embed_menus
from utils.checks import NotInVoiceChannel, is_in_voice


class AudioQueue(commands.Cog):
    """Commands that manage the Audio Player's queue."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot

    async def cog_check(self, ctx: CustomContext) -> bool:
        if not await is_in_voice(ctx):
            raise NotInVoiceChannel
        else:
            return True

    async def cog_before_invoke(self, ctx: CustomContext) -> None:
        if ctx.voice_client is None:
            await ctx.author.voice.channel.connect()

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="audioplayer",
        aliases=["ap", "mp"],
        description="Commands for controlling the audio player.",
    )
    async def player(self, ctx: CustomContext) -> None:
        pass

    @player.command(
        name="stop",
        aliases=["s"],
        description="Stops playing audio.",
    )
    @commands.check_any(checks.check_is_man, checks.check_is_alone)
    async def pstop(self, ctx: CustomContext) -> None:
        await ctx.audio_player.voice_client.disconnect()

    @player.command(
        name="pause",
        aliases=["play", "p"],
        description="Toggles the audio player between playing and paused.",
    )
    async def ppause(self, ctx: CustomContext) -> None:
        if ctx.audio_player.paused:
            ctx.audio_player.voice_client.resume()
        else:
            ctx.audio_player.voice_client.pause()

    @player.command(
        name="skip",
        aliases=["sk"],
        description="Skips the audio player to the next song on the queue.",
    )
    @commands.check_any(checks.check_is_man, checks.check_is_alone)
    async def pskip(self, ctx: CustomContext) -> None:
        ctx.audio_player.voice_client.stop()

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="queue",
        aliases=["q"],
        description="Commands for the active queue currently being played.",
    )
    async def queuecommand(self, ctx: CustomContext) -> None:
        source = embed_menus.QueueMenuSource(
            list(ctx.audio_player.queue.deque), "Current tracks on queue:"
        )
        await menus.MenuPages(source=source).start(ctx)

    @queuecommand.command(
        name="shuffle",
        description="Shuffles the current queue.\n"
        "Note that this changes the queue, and cannot be undone.",
    )
    @commands.check_any(checks.check_is_man, checks.check_is_alone)
    async def qshuffle(self, ctx: CustomContext) -> None:
        if len(list(ctx.audio_player.queue.deque)) > 0:
            random.shuffle(ctx.audio_player.queue.deque)

    @queuecommand.command(
        name="clear",
        aliases=["delete"],
        description="Deletes all items on the queue, leaving behind a blank slate.",
    )
    @commands.check_any(checks.check_is_man, checks.check_is_alone)
    async def qclear(self, ctx: CustomContext) -> None:
        ctx.audio_player.queue.clear()
        ctx.voice_client.stop()

    @queuecommand.command(
        name="pop",
        aliases=["remove"],
        description="Pops a track of the queue. Index starts at 1.",
    )
    @commands.check_any(checks.check_is_man, checks.check_is_alone)
    async def qpop(self, ctx: CustomContext, *, index: int) -> None:
        del ctx.audio_player.queue.deque[index - 1]

    @commands.command(
        name="nowplaying",
        aliases=["np"],
        description="Shows the currently playing track.",
    )
    async def nowplaying(self, ctx: CustomContext) -> None:
        playing_track = ctx.audio_player.voice_client.source
        if playing_track is None:
            await ctx.send("No track is playing.")
        else:
            await embed_menus.AudioSourceMenu(playing_track).start(ctx)


def setup(bot: BOT_TYPES):
    bot.add_cog(AudioQueue(bot))

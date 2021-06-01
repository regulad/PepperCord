import random

from discord.ext import commands, menus

from utils import checks, embed_menus, music, validators


class AudioQueue(commands.Cog):
    """Commands that manage the Audio Player's queue."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):  # Meh.
        await checks.is_in_voice(ctx)
        try:
            await checks.is_alone(ctx)
        except commands.CheckFailure:
            try:
                await checks.is_man(ctx)
            except commands.CheckFailure:
                raise checks.NotAlone
        return True

    async def cog_before_invoke(self, ctx):
        if ctx.voice_client is None:
            await ctx.author.voice.channel.connect()

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
    async def qshuffle(self, ctx):
        if len(list(ctx.audio_player.queue.deque)) > 0:
            random.shuffle(ctx.audio_player.queue.deque)

    @queuecommand.command(
        name="clear",
        aliases=["delete"],
        brief="Deletes all items on the queue.",
        description="Deletes all items on the queue, leaving behind a blank slate.",
    )
    async def qclear(self, ctx):
        ctx.audio_player.queue.clear()
        ctx.voice_client.stop()

    @queuecommand.command(
        name="pop",
        aliases=["remove"],
        brief="Pops a track off of the queue.",
        description="Pops a track of the queue. Index starts at 1.",
    )
    async def qpop(self, ctx, *, index: int):
        del ctx.audio_player.queue.deque[index - 1]

    @queuecommand.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="play",
        aliases=["p", "a", "add"],
        brief="Adds a song to the queue.",
        description="Adds a supported song to the current queue.",
    )
    async def play(self, ctx, *, query: str):
        async with ctx.typing():
            if validators.str_is_url(query):
                url = query
            else:
                url = f"ytsearch:{query}"
            source = await music.YTDLSource.from_url(ctx.audio_player.file_downloader, url, ctx.author)
            for track in source:
                await ctx.audio_player.queue.put(track)
            menu_source = embed_menus.QueueMenuSource(source, "Added:")
            pages = menus.MenuPages(source=menu_source)
            await pages.start(ctx)

    @play.command(
        name="top",
        aliases=["t"],
        brief="Adds a song to the top of the queue.",
        description="Adds a supported song to the top of the current queue.",
    )
    async def pt(self, ctx, *, query):
        if not len(list(ctx.audio_player.queue)) > 0:
            await ctx.invoke(self.play, query=query)
        else:
            async with ctx.typing():
                if validators.str_is_url(query):
                    url = query
                else:
                    url = f"ytsearch:{query}"
                source = await music.YTDLSource.from_url(ctx.audio_player.file_downloader, url, ctx.author)
                for track in source:
                    ctx.audio_player.queue.deque.appendleft(track)
                menu_source = embed_menus.QueueMenuSource(source, "Added to top:")
                pages = menus.MenuPages(source=menu_source)
                await pages.start(ctx)


def setup(bot):
    bot.add_cog(AudioQueue(bot))

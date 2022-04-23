from discord.app_commands import describe
from discord.ext.commands import hybrid_command, Cog
from discord.ext.menus import ViewMenuPages
from youtube_dl import YoutubeDL

from extensions.audio.control import QueueMenuSource, AudioSourceMenu
from utils.bots import BOT_TYPES, CustomContext
from utils.checks import check_voice_client_predicate
from utils.sources import YTDLSource, YTDL_FORMAT_OPTIONS
from utils.validators import str_is_url


class Music(Cog):
    """Controls for the audio features of the bot."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot
        self._file_downloader: YoutubeDL = YoutubeDL(YTDL_FORMAT_OPTIONS)

    async def cog_check(self, ctx: CustomContext) -> bool:
        return await check_voice_client_predicate(ctx)

    @hybrid_command(aliases=["p"])
    @describe(query="The video to search on YouTube, or a url.")
    async def play(
            self,
            ctx: CustomContext,
            *,
            query: str,
    ) -> None:
        """Plays a video from YouTube, or from another place with a URL."""
        await ctx.defer()
        query: str = query if str_is_url(query) else f"ytsearch:{query}"

        ytdl_sources: list[YTDLSource] = await YTDLSource.from_url(
            self._file_downloader, query, ctx.author, loop=ctx.voice_client.loop
        )
        for source in ytdl_sources:
            await ctx.voice_client.queue.put(source)

        if len(ytdl_sources) == 1:
            await AudioSourceMenu(ytdl_sources[0], ctx.voice_client).start(ctx)
        else:
            await ViewMenuPages(
                QueueMenuSource(ytdl_sources, ctx.voice_client, "Tracks added:")
            ).start(ctx)

    @hybrid_command(aliases=["pt"])
    @describe(query="The video to search on YouTube, or a url.")
    async def playtop(
            self,
            ctx: CustomContext,
            *,
            query: str,
    ) -> None:
        """Plays a song at the top of the queue."""
        await ctx.defer()
        query: str = query if str_is_url(query) else f"ytsearch:{query}"

        ytdl_sources: list[YTDLSource] = await YTDLSource.from_url(
            self._file_downloader, query, ctx.author, loop=ctx.voice_client.loop
        )
        for source in ytdl_sources:
            if len(ctx.voice_client.queue.deque) > 1:
                ctx.voice_client.queue.deque.appendleft(source)
            else:
                await ctx.voice_client.queue.put(source)

        if len(ytdl_sources) == 1:
            await AudioSourceMenu(ytdl_sources[0], ctx.voice_client).start(ctx)
        else:
            await ViewMenuPages(
                QueueMenuSource(ytdl_sources, ctx.voice_client, "Tracks added:")
            ).start(ctx)


async def setup(bot: BOT_TYPES) -> None:
    await bot.add_cog(Music(bot))

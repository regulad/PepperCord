from typing import Sequence, cast
from discord.app_commands import describe
from discord.app_commands import guild_only as ac_guild_only
from discord.ext.commands import hybrid_command, Cog, guild_only

from discord.ext.menus import MenuPages
from utils.bots.audio import CustomVoiceClient
from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext

from yt_dlp import YoutubeDL

from extensions.audio.control import QueueMenuSource, AudioSourceMenu
from utils.checks.audio import check_voice_client_predicate
from utils.sources.common import YTDL_AUDIO_FORMAT_INITIAL_OPTIONS
from utils.sources.ytdl import YTDLInfo, YTDLSource
from utils.validators import str_is_url


MS_TRACK_LENGTH_LIMIT = 5_400_000  # 1 hr 30 mins  # TODO: make more robust


async def too_long_to_download_checker(ytdlinfo: YTDLInfo) -> bool:
    duration = cast(int, getattr(ytdlinfo, "duration", 0)) * 1000
    return duration < MS_TRACK_LENGTH_LIMIT


class Music(Cog):
    """Controls for the audio features of the bot."""

    def __init__(self, bot: CustomBot) -> None:
        self.bot = bot
        self._file_downloader = YoutubeDL(dict(YTDL_AUDIO_FORMAT_INITIAL_OPTIONS))
        self._info_checker = too_long_to_download_checker

    async def cog_check(self, ctx: CustomContext) -> bool:  # type: ignore[override]
        if not isinstance(ctx, CustomContext):
            raise RuntimeError("Cannot process a context that is not a CustomContext.")
        return await check_voice_client_predicate(ctx)

    @hybrid_command(aliases=["p"])  # type: ignore[arg-type]  # bad d.py export
    @guild_only()
    @ac_guild_only()
    @describe(query="The video to search on YouTube, or a url.")
    async def play(
        self,
        ctx: CustomContext,
        *,
        query: str,
    ) -> None:
        """Plays a video from YouTube, or from another place with a URL."""
        assert ctx.voice_client is not None  # guaranteed at runtime
        if not isinstance(ctx.voice_client, CustomVoiceClient):
            raise RuntimeError("This command cannot be run right now.")

        async with ctx.typing():
            query = query if str_is_url(query) else f"ytsearch:{query}"

            ytdl_sources: Sequence[YTDLSource] = await YTDLSource.from_url(
                query,
                ctx.author,
                file_downloader=self._file_downloader,
                loop=ctx.voice_client.loop,
                preload_checker=self._info_checker,
            )
            for source in ytdl_sources:
                await ctx.voice_client.queue.put(source)

            if len(ytdl_sources) == 1:
                # We have to do this because the legacy AudioSourceMenu doesn't respond to the Interaction
                await ctx.send("Added a track.", ephemeral=True)
                await AudioSourceMenu(ytdl_sources[0], ctx.voice_client).start(ctx)
            else:
                # We have to do this because the legacy AudioSourceMenu doesn't respond to the Interaction
                await ctx.send("Added tracks.", ephemeral=True)
                menu: "MenuPages[CustomBot, CustomContext, QueueMenuSource]" = (
                    MenuPages(
                        QueueMenuSource(ytdl_sources, ctx.voice_client, "Tracks added:")
                    )
                )
                await menu.start(ctx)

    @hybrid_command(aliases=["pt"])  # type: ignore[arg-type]  # bad d.py export
    @guild_only()
    @ac_guild_only()
    @describe(query="The video to search on YouTube, or a url.")
    async def playtop(
        self,
        ctx: CustomContext,
        *,
        query: str,
    ) -> None:
        """Plays a song at the top of the queue."""
        assert ctx.voice_client is not None  # guaranteed at runtime
        if not isinstance(ctx.voice_client, CustomVoiceClient):
            raise RuntimeError("This command cannot be run right now.")

        async with ctx.typing():
            query = query if str_is_url(query) else f"ytsearch:{query}"

            ytdl_sources: Sequence[YTDLSource] = await YTDLSource.from_url(
                query,
                ctx.author,
                file_downloader=self._file_downloader,
                loop=ctx.voice_client.loop,
                preload_checker=self._info_checker,
            )
            for source in ytdl_sources:
                if len(ctx.voice_client.queue.deque) > 1:
                    ctx.voice_client.queue.deque.appendleft(source)
                else:
                    await ctx.voice_client.queue.put(source)

            if len(ytdl_sources) == 1:
                # We have to do this because the legacy AudioSourceMenu doesn't respond to the Interaction
                await ctx.send("Added a track.", ephemeral=True)
                await AudioSourceMenu(ytdl_sources[0], ctx.voice_client).start(ctx)
            else:
                # We have to do this because the legacy AudioSourceMenu doesn't respond to the Interaction
                await ctx.send("Added tracks.", ephemeral=True)
                menu: "MenuPages[CustomBot, CustomContext, QueueMenuSource]" = (
                    MenuPages(
                        QueueMenuSource(ytdl_sources, ctx.voice_client, "Tracks added:")
                    )
                )
                await menu.start(ctx)


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(Music(bot))

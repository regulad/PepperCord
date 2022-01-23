from discord import Embed, Message
from discord.ext.commands import command, Cog, Option
from discord.ext.menus import ViewMenuPages, ListPageSource, ViewMenu
from youtube_dl import YoutubeDL

from utils.bots import BOT_TYPES, CustomContext, EnhancedSource, CustomVoiceClient
from utils.checks import can_have_voice_client, CantCreateAudioClient
from utils.converters import duration_to_str
from utils.sources import YTDLSource, YTDL_FORMAT_OPTIONS
from utils.validators import str_is_url

PROGRESS: str = "🟩"
VOID: str = "⬜"
COUNT: int = 11


class QueueMenuSource(ListPageSource):
    def __init__(self, entries: list[EnhancedSource], client: CustomVoiceClient, msg: str):
        self.msg: str = msg
        self.client: CustomVoiceClient = client
        super().__init__(entries, per_page=10)

    async def format_page(self, menu, page_entries):
        offset = menu.current_page * self.per_page
        base_embed = Embed(
            title=self.msg, description=f"{len(self.entries)} total tracks"
        )

        if self.client.source is not None and self.client.source.duration is not None:
            time_until: float = (self.client.source.duration - self.client.ms_read) / 1000
        else:
            time_until: float = 0
        # Before the current page
        for track in self.entries[:offset]:
            duration = track.duration or 0
            time_until += duration / 1000

        # The current page
        for iteration, value in enumerate(page_entries, start=offset):
            base_embed.add_field(
                name=f"{iteration + 1}: {duration_to_str(int(time_until))} left",
                value=f"[{value.name}]({value.description})\n{duration_to_str(value.duration / 1000)} long"
                      f"\nAdded by: {value.invoker.display_name}",
                inline=False,
            )
            time_until += (value.duration or 0 / 1000)
        return base_embed


class AudioSourceMenu(ViewMenu):
    """An embed menu that makes displaying a source fancy."""

    def __init__(self, source: EnhancedSource, client: CustomVoiceClient, **kwargs) -> None:
        self.source: EnhancedSource = source
        self.client: CustomVoiceClient = client

        super().__init__(**kwargs)

    async def send_initial_message(self, ctx, channel) -> Message:
        if self.source is None:
            await ctx.send("There is no source.")
        else:
            embed: Embed = Embed(title=self.source.name, description=self.source.description)
            if isinstance(self.source, YTDLSource):
                info = self.source.info

                thumbnail = info.get("thumbnail")
                if thumbnail is not None:
                    embed.set_thumbnail(url=thumbnail)

                uploader = info.get("uploader")
                uploader_url = info.get("uploader_url")
                if uploader is not None and uploader_url is not None:
                    embed.set_author(name=uploader, url=uploader_url)
            if self.source.duration is not None:
                embed.add_field(
                    name="Duration:",
                    value=duration_to_str(int(self.source.duration / 1000)),
                )
                if self.client.source == self.source:
                    squares: list[str] = []
                    for i in range(1, COUNT + 1):
                        squares.append(PROGRESS if (self.client.progress > (1 / COUNT) * i) else VOID)
                    embed.add_field(
                        name="Left:",
                        value=f"{duration_to_str(int((self.source.duration - self.client.ms_read) / 1000))}\n"
                              f"{''.join(squares)}"
                    )
            embed.add_field(name="Added by:", value=self.source.invoker.display_name)
            return await channel.send(embed=embed, **self._get_kwargs())


class Audio(Cog):
    """Controls for the audio features of the bot."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot
        self._file_downloader: YoutubeDL = YoutubeDL(YTDL_FORMAT_OPTIONS)

    async def cog_check(self, ctx: CustomContext) -> bool:
        if await can_have_voice_client(ctx):
            return True
        else:
            raise CantCreateAudioClient

    @command(aliases=["p"])
    async def play(
            self,
            ctx: CustomContext,
            *,
            query: str = Option(description="The video to search on YouTube, or a url.")
    ) -> None:
        """Plays a video from YouTube, or from another place with a URL."""
        await ctx.defer()
        query: str = query if str_is_url(query) else f"ytsearch:{query}"

        ytdl_sources: list[YTDLSource] = await YTDLSource.from_url(
            self._file_downloader,
            query,
            ctx.author,
            loop=ctx.voice_client.loop
        )
        for source in ytdl_sources:
            await ctx.voice_client.queue.put(source)

        if len(ytdl_sources) == 1:
            await AudioSourceMenu(ytdl_sources[0], ctx.voice_client).start(ctx)
        else:
            await ViewMenuPages(QueueMenuSource(ytdl_sources, ctx.voice_client, "Tracks added:")).start(ctx)

    @command(aliases=["q"])
    async def queue(self, ctx: CustomContext) -> None:
        """Displays information the upcoming tracks."""
        maybe_source: EnhancedSource = ctx.voice_client.source
        if maybe_source is None:
            await ctx.send("No track is playing.", ephemeral=True)
        else:
            await ViewMenuPages(
                QueueMenuSource(list(ctx.voice_client.queue.deque), ctx.voice_client, "Tracks on queue:")
            ).start(ctx, ephemeral=False)

    @command(aliases=["np"])
    async def nowplaying(self, ctx: CustomContext) -> None:
        """Displays information for the currently playing track, including how much time is left."""
        maybe_source: EnhancedSource = ctx.voice_client.source
        if maybe_source is None:
            await ctx.send("No track is playing.", ephemeral=True)
        else:
            await AudioSourceMenu(maybe_source, ctx.voice_client).start(ctx)

    @command(aliases=["pt"])
    async def playtop(
            self,
            ctx: CustomContext,
            *,
            query: str = Option(description="The video to search on YouTube, or a url.")
    ) -> None:
        """Plays a song at the top of the queue."""
        await ctx.defer()
        query: str = query if str_is_url(query) else f"ytsearch:{query}"

        ytdl_sources: list[YTDLSource] = await YTDLSource.from_url(
            self._file_downloader,
            query,
            ctx.author,
            loop=ctx.voice_client.loop
        )
        for source in ytdl_sources:
            if len(ctx.voice_client.queue.deque) > 1:
                ctx.voice_client.queue.deque.appendleft(source)
            else:
                await ctx.voice_client.queue.put(source)

        if len(ytdl_sources) == 1:
            await AudioSourceMenu(ytdl_sources[0], ctx.voice_client).start(ctx)
        else:
            await ViewMenuPages(QueueMenuSource(ytdl_sources, ctx.voice_client, "Tracks added:")).start(ctx)

    @command()
    async def pause(self, ctx: CustomContext) -> None:
        """Pauses the audio player."""
        ctx.voice_client.pause()
        await ctx.send("Paused the audio player.", ephemeral=True)

    @command()
    async def resume(self, ctx: CustomContext) -> None:
        """Resumes the audio player."""
        ctx.voice_client.resume()
        await ctx.send("Resumed the audio player.", ephemeral=True)

    @command()
    async def skip(self, ctx: CustomContext) -> None:
        """Stops the currently playing track."""
        ctx.voice_client.stop()
        await ctx.send("Stopped the currently playing track.", ephemeral=True)

    @command()
    async def disconnect(self, ctx: CustomContext) -> None:
        """Disconnects the audio player."""
        await ctx.voice_client.disconnect(force=True)
        await ctx.send("Disconnected from the voice channel.", ephemeral=True)


def setup(bot: BOT_TYPES) -> None:
    bot.add_cog(Audio(bot))

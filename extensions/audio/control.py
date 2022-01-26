from discord import Embed, Message
from discord.ext.commands import command, Cog
from discord.ext.menus import ViewMenuPages, ListPageSource, ViewMenu

from utils.bots import BOT_TYPES, CustomContext, EnhancedSource, CustomVoiceClient
from utils.checks import check_voice_client_predicate
from utils.converters import duration_to_str
from utils.sources import YTDLSource

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
            time_until: float = self.client.source.duration - self.client.ms_read
        else:
            time_until: float = 0
        # Before the current page
        for track in self.entries[:offset]:
            if track.duration is not None:
                time_until += track.duration

        # The current page
        for iteration, value in enumerate(page_entries, start=offset):
            base_embed.add_field(
                name=f"{iteration + 1}: {duration_to_str(int(time_until / 1000))} left",
                value=f"[{value.name}]({value.description})\n{duration_to_str(int(value.duration or 0 / 1000))} long"
                      f"\nAdded by: {value.invoker.display_name}",
                inline=False,
            )
            if value.duration is not None:
                time_until += value.duration
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

    async def cog_check(self, ctx: CustomContext) -> bool:
        return await check_voice_client_predicate(ctx)

    @command(aliases=["q"])
    async def queue(self, ctx: CustomContext) -> None:
        """Displays information the upcoming tracks."""
        maybe_source: EnhancedSource = ctx.voice_client.source
        if maybe_source is None:
            await ctx.send("No track is playing.", ephemeral=True)
        else:
            await ViewMenuPages(
                QueueMenuSource(
                    list(ctx.voice_client.queue.deque),
                    ctx.voice_client,
                    "Tracks on queue (Loop is on):" if ctx.voice_client.should_loop else "Tracks on queue:"
                )
            ).start(ctx, ephemeral=False)

    @command(aliases=["np"])
    async def nowplaying(self, ctx: CustomContext) -> None:
        """Displays information for the currently playing track, including how much time is left."""
        maybe_source: EnhancedSource = ctx.voice_client.source
        if maybe_source is None:
            await ctx.send("No track is playing.", ephemeral=True)
        else:
            await AudioSourceMenu(maybe_source, ctx.voice_client).start(ctx)

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

    @command(aliases=["s"])
    async def skip(self, ctx: CustomContext) -> None:
        """Stops the currently playing track."""
        ctx.voice_client.stop()
        await ctx.send("Stopped the currently playing track.", ephemeral=True)

    @command(aliases=["dc", "fuckoff"])
    async def disconnect(self, ctx: CustomContext) -> None:
        """Disconnects the audio player."""
        await ctx.voice_client.disconnect(force=True)
        await ctx.send("Disconnected from the voice channel.", ephemeral=True)

    @command(aliases=["l"])
    async def loop(self, ctx: CustomContext) -> None:
        """Toggles loop."""
        ctx.voice_client.should_loop = not ctx.voice_client.should_loop
        await ctx.send(f"Toggled loop {'on' if ctx.voice_client.should_loop else 'off'}.", ephemeral=True)


def setup(bot: BOT_TYPES) -> None:
    bot.add_cog(Audio(bot))

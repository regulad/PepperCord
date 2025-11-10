from typing import Any, Sequence
from discord import Embed, Message, VoiceClient
import discord
from discord.app_commands import guild_only as ac_guild_only
from discord.ext.commands import hybrid_command, Cog, guild_only

from discord.ext.menus import ListPageSource, Menu, MenuPages
from utils.bots.audio import CustomVoiceClient, EnhancedSource
from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext
from utils.checks.audio import check_voice_client_predicate
from utils.converters import duration_to_str
from utils.sources.ytdl import YTDLSource

PROGRESS: str = "🟩"
VOID: str = "⬜"
COUNT: int = 11


class QueueMenuSource(
    ListPageSource[
        EnhancedSource, MenuPages[CustomBot, CustomContext, "QueueMenuSource"]
    ]
):
    def __init__(
        self, entries: Sequence[EnhancedSource], client: CustomVoiceClient, msg: str
    ):
        self.msg: str = msg
        self.client: CustomVoiceClient = client
        super().__init__(entries, per_page=10)

    async def format_page(
        self,
        menu: MenuPages[CustomBot, CustomContext, "QueueMenuSource"],
        page_entries: list[EnhancedSource] | EnhancedSource,
    ) -> Embed:
        assert isinstance(page_entries, list)  # guaranteed at runtime by per_page > 1

        offset = menu.current_page * self.per_page
        base_embed = Embed(
            title=self.msg, description=f"{len(self.entries)} total tracks"
        )
        base_embed.set_footer(
            text=f"Page {menu.current_page + 1}/{self.get_max_pages()}"
        )

        time_until: float
        if self.client.source is not None and self.client.source.duration is not None:
            time_until = self.client.source.duration - (self.client.ms_read or 0)
        else:
            time_until = 0
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


class AudioSourceMenu(Menu[CustomBot, CustomContext]):
    """An embed menu that makes displaying a source fancy."""

    def __init__(
        self,
        source: EnhancedSource,
        client: CustomVoiceClient,
        **kwargs: Any,  # TODO: improve kwarg passthrough
    ) -> None:
        self.source: EnhancedSource = source
        self.client: CustomVoiceClient = client

        super().__init__(**kwargs)

    async def send_initial_message(
        self, ctx: CustomContext, channel: discord.abc.Messageable
    ) -> Message:
        embed: Embed = Embed(
            title=self.source.name, description=self.source.description
        )
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
                    squares.append(
                        PROGRESS
                        if ((self.client.progress or 0) > (1 / COUNT) * i)
                        else VOID
                    )
                embed.add_field(
                    name="Left:",
                    value=f"{duration_to_str(int((self.source.duration - (self.client.ms_read or 0)) / 1000))}\n"
                    f"{''.join(squares)}",
                )
        embed.add_field(name="Added by:", value=self.source.invoker.display_name)
        return await channel.send(embed=embed)


class Audio(Cog):
    """Controls for the audio features of the bot."""

    def __init__(self, bot: CustomBot) -> None:
        self.bot: CustomBot = bot

    async def cog_check(self, ctx: CustomContext) -> bool:  # type: ignore[override]  # bad d.py export type, it works
        return await check_voice_client_predicate(ctx)

    @hybrid_command(aliases=["q"])  # type: ignore[arg-type]  # bad d.py export
    @guild_only()
    @ac_guild_only()
    async def queue(self, ctx: CustomContext) -> None:
        """Displays information the upcoming tracks."""
        assert ctx.voice_client is not None  # guaranteed at runtime
        if not isinstance(ctx.voice_client, CustomVoiceClient):
            raise RuntimeError("This command cannot be run right now.")

        maybe_source = ctx.voice_client.source
        if maybe_source is None:
            await ctx.send("No track is playing.", ephemeral=True)
        else:
            menu: MenuPages[CustomBot, CustomContext, "QueueMenuSource"] = MenuPages(
                QueueMenuSource(
                    list(ctx.voice_client.queue.deque),
                    ctx.voice_client,
                    (
                        "Tracks on queue (Loop is on):"
                        if ctx.voice_client.should_loop
                        else "Tracks on queue:"
                    ),
                )
            )
            await menu.start(ctx)

    @hybrid_command(aliases=["np"])  # type: ignore[arg-type]  # bad d.py export
    @guild_only()
    @ac_guild_only()
    async def nowplaying(self, ctx: CustomContext) -> None:
        """Displays information for the currently playing track, including how much time is left."""
        assert ctx.voice_client is not None  # guaranteed at runtime
        if not isinstance(ctx.voice_client, CustomVoiceClient):
            raise RuntimeError("This command cannot be run right now.")

        maybe_source = ctx.voice_client.source
        if maybe_source is None:
            await ctx.send("No track is playing.", ephemeral=True)
        else:
            await AudioSourceMenu(maybe_source, ctx.voice_client).start(ctx)

    @hybrid_command()  # type: ignore[arg-type]  # bad d.py export
    @guild_only()
    @ac_guild_only()
    async def pause(self, ctx: CustomContext) -> None:
        """Pauses the audio player."""
        assert ctx.voice_client is not None  # guaranteed at runtime
        if not isinstance(ctx.voice_client, CustomVoiceClient):
            raise RuntimeError("This command cannot be run right now.")
        ctx.voice_client.pause()
        await ctx.send("Paused the audio player.", ephemeral=True)

    @hybrid_command()  # type: ignore[arg-type]  # bad d.py export
    @guild_only()
    @ac_guild_only()
    async def resume(self, ctx: CustomContext) -> None:
        """Resumes the audio player."""
        assert ctx.voice_client is not None  # guaranteed at runtime
        if not isinstance(ctx.voice_client, VoiceClient):
            raise RuntimeError("This command cannot be run right now.")
        ctx.voice_client.resume()
        await ctx.send("Resumed the audio player.", ephemeral=True)

    @hybrid_command(aliases=["s"])  # type: ignore[arg-type]  # bad d.py export
    @guild_only()
    @ac_guild_only()
    async def skip(self, ctx: CustomContext) -> None:
        """Stops the currently playing track."""
        assert ctx.voice_client is not None  # guaranteed at runtime
        if not isinstance(ctx.voice_client, VoiceClient):
            raise RuntimeError("This command cannot be run right now.")
        ctx.voice_client.stop()
        await ctx.send("Stopped the currently playing track.", ephemeral=True)

    @hybrid_command(aliases=["dc", "fuckoff"])  # type: ignore[arg-type]  # bad d.py export
    @guild_only()
    @ac_guild_only()
    async def disconnect(self, ctx: CustomContext) -> None:
        """Disconnects the audio player."""
        assert ctx.voice_client is not None  # guaranteed at runtime
        await ctx.voice_client.disconnect(force=True)
        await ctx.send("Disconnected from the voice channel.", ephemeral=True)

    @hybrid_command(aliases=["l"])  # type: ignore[arg-type]  # bad d.py export
    @guild_only()
    @ac_guild_only()
    async def loop(self, ctx: CustomContext) -> None:
        """Toggles loop."""
        assert ctx.voice_client is not None  # guaranteed at runtime
        if not isinstance(ctx.voice_client, CustomVoiceClient):
            raise RuntimeError("This command cannot be run right now.")
        ctx.voice_client.should_loop = not ctx.voice_client.should_loop
        await ctx.send(
            f"Toggled loop {'on' if ctx.voice_client.should_loop else 'off'}.",
            ephemeral=True,
        )


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(Audio(bot))

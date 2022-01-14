from typing import Union

import discord
from discord.ext import commands, menus
from youtube_dl import YoutubeDL

from utils import checks, embed_menus, audio, validators, sources
from utils.bots import BOT_TYPES, CustomContext


class TrackPlaylist(list):
    @classmethod
    def from_queue(cls, queue: audio.AudioQueue):
        new_playlist = cls()
        for track in queue.deque:
            if isinstance(track, sources.YTDLSource):
                new_playlist.append(track)
        return new_playlist

    @classmethod
    async def from_sanitized(
            cls,
            sanitized: list,
            user: Union[discord.Member, discord.User],
            *,
            file_downloader: YoutubeDL,
    ):
        new_playlist = cls()
        for url in sanitized:
            new_playlist.extend(
                await sources.YTDLSource.from_url(file_downloader, url, user)
            )
        return new_playlist

    @property
    def sanitized(self) -> list:
        new_list = []
        for track in self:
            new_list.append(track.url)
        return new_list


class Music(commands.Cog):
    """Listen to your favorite tracks in a voice channel."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot

    async def cog_before_invoke(self, ctx: CustomContext) -> None:
        if ctx.voice_client is None:
            await ctx.author.voice.channel.connect()

    @commands.group()
    async def playlist(self, ctx: CustomContext) -> None:
        """
        The playlist system allows you to store a queue into your data and then recall it later.
        """
        pass

    @playlist.command()
    async def store(self, ctx: CustomContext) -> None:
        """
        Saves the current queue into your personal playlist.
        """
        playlist = TrackPlaylist.from_queue(ctx["audio_player"]().queue)
        await ctx["author_document"].update_db(
            {"$set": {"audio.playlist": playlist.sanitized}}
        )
        await ctx.send("Saved.", ephemeral=True)

    @playlist.command()
    async def recall(self, ctx: CustomContext) -> None:
        """
        Recalls your playlist into the queue.
        You must have already stored a playlist.
        """
        await ctx.defer(ephemeral=True)

        if ctx["author_document"].get("audio", {}).get("playlist") is None:
            await ctx.send("You don't have a playlist saved.", ephemeral=True)
            return
        else:
            user_track_playlist = await TrackPlaylist.from_sanitized(
                ctx["author_document"]["audio"]["playlist"],
                ctx.author,
                file_downloader=ctx["audio_player"]().file_downloader,
            )
            for track in user_track_playlist:
                ctx["audio_player"]().queue.put_nowait(track)
            await ctx.send("Playlist has been restored.", ephemeral=True)

    @commands.command()
    @commands.cooldown(3, 20, commands.BucketType.user)
    async def play(
            self,
            ctx: CustomContext,
            *,
            query: str = commands.Option(
                description="The song or URL to be searched. Will search using YouTube."
            ),
    ) -> None:
        """
        Adds a song to the queue.
        This track will be downloaded using YouTubeDL and must be from one of the services that it supports
        """
        await ctx.defer()

        if validators.str_is_url(query):
            url = query
        else:
            url = f"ytsearch:{query}"
        source = await sources.YTDLSource.from_url(
            ctx["audio_player"]().file_downloader, url, ctx.author
        )
        for track in source:
            ctx["audio_player"]().queue.put_nowait(track)
        menu_source = embed_menus.QueueMenuSource(source, "Added:")
        pages = menus.ViewMenuPages(source=menu_source)
        await pages.start(ctx)

    @commands.command()
    @commands.check_any(
        commands.has_permissions(moderate_members=True), checks.check_is_alone
    )
    async def playtop(
            self,
            ctx: CustomContext,
            *,
            query: str = commands.Option(
                description="The song or URL to be searched. Will search using YouTube."
            ),
    ) -> None:
        """
        Plays a song from the top of the queue.
        Every exception from play also applies here.
        """
        if not len(list(ctx["audio_player"]().queue.deque)) > 0:
            await ctx.invoke(self.play, query=query)
        else:
            await ctx.defer()

            if validators.str_is_url(query):
                url = query
            else:
                url = f"ytsearch:{query}"
            source = await sources.YTDLSource.from_url(
                ctx["audio_player"]().file_downloader, url, ctx.author
            )
            for track in source:
                ctx["audio_player"]().queue.deque.appendleft(track)
            menu_source = embed_menus.QueueMenuSource(source, "Added to top:")
            pages = menus.ViewMenuPages(source=menu_source)
            await pages.start(ctx)


def setup(bot: BOT_TYPES) -> None:
    bot.add_cog(Music(bot))

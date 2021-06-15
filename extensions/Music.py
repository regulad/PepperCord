from typing import Union

import discord
from discord.ext import commands, menus
from youtube_dl import YoutubeDL

from utils import checks, embed_menus, audio, validators, sources


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
        cls, sanitized: list, user: Union[discord.Member, discord.User], *, file_downloader: YoutubeDL
    ):
        new_playlist = cls()
        for url in sanitized:
            new_playlist.extend(await sources.YTDLSource.from_url(file_downloader, url, user))
        return new_playlist

    @property
    def sanitized(self) -> list:
        new_list = []
        for track in self:
            new_list.append(track.url)
        return new_list


class Music(commands.Cog):
    """Listen to your favorite tracks in a voice channel."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await checks.is_man(ctx)

    async def cog_before_invoke(self, ctx):
        if ctx.voice_client is None:
            await ctx.author.voice.channel.connect()

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="playlist",
        aliases=["pl"],
        brief="Commands for playlists.",
        description="Commands for playlists. Each user can have their own playlist, which persists between guilds.",
    )
    async def playlist(self, ctx):
        pass

    @playlist.command(
        name="save",
        aliases=["set", "store"],
        brief="Sets a playlist.",
        description="Sets user's playlist to the current queue.",
    )
    async def plset(self, ctx):
        playlist = TrackPlaylist.from_queue(ctx.audio_player.queue)
        await ctx.author_document.update_db({"$set": {"audio.playlist": playlist.sanitized}})

    @playlist.command(
        name="load",
        aliases=["get", "put"],
        brief="Loads a playlist.",
        description="Loads a playlist into the current queue. Does not overwrite existing queue, "
                    "it just appends to it.",
    )
    async def plget(self, ctx):
        async with ctx.typing():
            if ctx.author_document.get("audio", {}).get("playlist") is None:
                await ctx.send("You don't have a playlist saved.")
                return
            else:
                user_track_playlist = await TrackPlaylist.from_sanitized(
                    ctx.author_document["audio"]["playlist"],
                    ctx.author,
                    file_downloader=ctx.audio_player.file_downloader
                )
                for track in user_track_playlist:
                    ctx.audio_player.queue.put_nowait(track)


    @commands.group(
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
            source = await sources.YTDLSource.from_url(ctx.audio_player.file_downloader, url, ctx.author)
            for track in source:
                ctx.audio_player.queue.put_nowait(track)
            menu_source = embed_menus.QueueMenuSource(source, "Added:")
            pages = menus.MenuPages(source=menu_source)
            await pages.start(ctx)

    @play.command(
        name="top",
        aliases=["t"],
        brief="Adds a song to the top of the queue.",
        description="Adds a supported song to the top of the current queue.",
    )
    @commands.check_any(commands.check(checks.is_man), commands.check(checks.is_alone))
    async def pt(self, ctx, *, query):
        if not len(list(ctx.audio_player.queue.deque)) > 0:
            await ctx.invoke(self.play, query=query)
        else:
            async with ctx.typing():
                if validators.str_is_url(query):
                    url = query
                else:
                    url = f"ytsearch:{query}"
                source = await sources.YTDLSource.from_url(ctx.audio_player.file_downloader, url, ctx.author)
                for track in source:
                    ctx.audio_player.queue.deque.appendleft(track)
                menu_source = embed_menus.QueueMenuSource(source, "Added to top:")
                pages = menus.MenuPages(source=menu_source)
                await pages.start(ctx)


def setup(bot):
    bot.add_cog(Music(bot))

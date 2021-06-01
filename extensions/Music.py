import asyncio
import random
from typing import Union

import discord
from discord.ext import commands, menus
from youtube_dl import YoutubeDL

from utils import checks, validators, converters, music, bots

# Not sure what the deal with these is, but the d.py docs suggested it so ¯\_(ツ)_/¯
ytdl_format_options = {
    "format": "bestaudio/best",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",  # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {"options": "-vn"}


class YTDLSource(discord.PCMVolumeTransformer):
    """Represents a source from YoutubeDL that has the ability to have it's volume changed."""

    def __init__(self, source: discord.FFmpegPCMAudio, volume=0.5, *, info, invoker):
        super().__init__(source, volume)

        self.info = info
        self.invoker = invoker

    @property
    def url(self):
        return self.info["webpage_url"]

    @classmethod
    async def from_url(cls, file_downloader: YoutubeDL, url: str, invoker: Union[discord.Member, discord.User]):
        """Returns a list of YTDLSources from a playlist or song."""

        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, lambda: file_downloader.extract_info(url, download=False))

        tracks = []

        if info.setdefault("entries", None):
            # Url refers to a playlist, so a list of instances must be returned.

            for entry in info["entries"]:
                track = cls(discord.FFmpegPCMAudio(entry["url"], **ffmpeg_options), info=entry, invoker=invoker)
                tracks.append(track)

        else:
            # Url refers to a single track, so a list containing only a single instance must be returned.

            track = cls(discord.FFmpegPCMAudio(info["url"], **ffmpeg_options), info=info, invoker=invoker)
            tracks.append(track)

        return tracks


class TrackPlaylist(list):
    @classmethod
    def from_queue(cls, queue: music.TrackQueue):
        new_playlist = cls()
        for track in queue.deque:
            new_playlist.append(track)
        return new_playlist

    @classmethod
    async def from_sanitized(
        cls, sanitized: list, user: Union[discord.Member, discord.User], *, file_downloader: YoutubeDL
    ):
        new_playlist = cls()
        for url in sanitized:
            new_playlist.extend(await YTDLSource.from_url(file_downloader, url, user))
        return new_playlist

    @property
    def sanitized(self) -> list:
        new_list = []
        for track in self:
            new_list.append(track.url)
        return new_list


class QueuePlaylistSource(menus.ListPageSource):
    def __init__(self, entries: list, msg: str):
        self.msg = msg
        super().__init__(entries, per_page=10)

    async def format_page(self, menu, page_entries):
        offset = menu.current_page * self.per_page
        base_embed = discord.Embed(title=self.msg, description=f"{len(self.entries)} total tracks")
        time_until = 0
        for track in self.entries[:offset]:
            duration = track.info["duration"]
            time_until += duration
        for iteration, value in enumerate(page_entries, start=offset):
            title = value.info["title"]
            duration = value.info["duration"]
            url = value.info["webpage_url"]
            invoker = value.invoker
            time_until += duration
            base_embed.add_field(
                name=f"{iteration + 1}: {converters.duration_to_str(time_until)} left",
                value=f"[{title}]({url}): {converters.duration_to_str(duration)} long, added by {invoker.display_name}",
                inline=False,
            )
        return base_embed


class Music(commands.Cog):
    """Listen to your favorite tracks in a voice channel."""

    def __init__(self, bot):
        self.bot = bot
        self.file_downloader = YoutubeDL(ytdl_format_options)

    async def cog_check(self, ctx):  # Meh.
        await checks.is_in_voice(ctx)
        try:
            await checks.is_alone(ctx)
        except commands.CheckFailure:
            try:
                await checks.is_man(ctx)
            except commands.CheckFailure:
                raise music.NotAlone
        return True

    async def cog_before_invoke(self, ctx):
        if ctx.voice_client is None:
            await ctx.author.voice.channel.connect()

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="musicplayer",
        aliases=["p", "mp"],
        brief="Commands for the music player.",
        description="Commands for controlling the music player.",
    )
    async def player(self, ctx):
        pass

    @player.command(
        name="stop",
        aliases=["s"],
        brief="Stops playing.",
        description="Stops playing audio.",
    )
    async def pstop(self, ctx):
        await ctx.music_player.voice_client.disconnect()

    @player.command(
        name="pause",
        aliases=["play", "p"],
        brief="Toggles the music player on and off.",
        description="Toggles the music player between playing and paused.",
    )
    async def ppause(self, ctx):
        if ctx.music_player.paused:
            ctx.music_player.voice_client.resume()
        else:
            ctx.music_player.voice_client.pause()

    @player.command(
        name="skip",
        aliases=["sk"],
        brief="Skips to the next song on the queue.",
        description="Skips the music player to the next song on the queue.",
    )
    async def pskip(self, ctx):
        ctx.music_player.voice_client.stop()

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
        playlist = TrackPlaylist.from_queue(ctx.music_player.queue)
        ctx.author_document.setdefault("music", {})["playlist"] = playlist.sanitized
        await ctx.author_document.replace_db()

    @playlist.command(
        name="load",
        aliases=["get", "put"],
        brief="Loads a playlist.",
        description="Loads a playlist into the current queue. Does not overwrite existing queue, "
        "it just appends to it.",
    )
    async def plget(self, ctx):
        async with ctx.typing():
            try:
                user_playlist = ctx.author_document.setdefault("music", {})["playlist"]
            except KeyError:
                await ctx.send("You don't have a playlist saved.")
                return
            user_track_playlist = await TrackPlaylist.from_sanitized(
                user_playlist, ctx.author, file_downloader=self.file_downloader
            )
            for track in user_track_playlist:
                await ctx.music_player.queue.put(track)

    @commands.command(
        name="nowplaying",
        aliases=["np"],
        brief="Shows the currently playing track.",
        description="Shows the currently playing track.",
    )
    async def nowplaying(self, ctx):
        playing_track = ctx.music_player.now_playing

        if playing_track is None:
            await ctx.send("Nothing is playing.")
        elif not isinstance(playing_track, YTDLSource):
            await ctx.send("The currently playing track isn't a song.")
        else:
            info = playing_track.info
            embed = (
                discord.Embed(title=info["title"], description=info["webpage_url"])
                .add_field(name="Duration:", value=converters.duration_to_str(info["duration"]))
                .add_field(name="Added by:", value=playing_track.invoker.display_name)
            )
            try:
                embed.set_thumbnail(url=info["thumbnail"])
            except KeyError:
                pass
            try:
                embed.set_author(name=info["uploader"], url=info["uploader_url"])
            except KeyError:
                pass
            await ctx.send(embed=embed)

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="queue",
        aliases=["q"],
        brief="Commands for the queue.",
        description="Commands for the active queue currently being played.",
    )
    async def queuecommand(self, ctx):
        source = QueuePlaylistSource(list(ctx.music_player.queue.deque), "Current tracks on queue:")
        pages = menus.MenuPages(source=source)
        await pages.start(ctx)

    @queuecommand.command(
        name="shuffle",
        brief="Shuffles the current queue.",
        description="Shuffles the current queue. Note that this changes the queue.",
    )
    async def qshuffle(self, ctx):
        if len(list(ctx.music_player.queue.deque)) > 0:
            random.shuffle(ctx.music_player.queue.deque)

    @queuecommand.command(
        name="clear",
        aliases=["delete"],
        brief="Deletes all items on the queue.",
        description="Deletes all items on the queue, leaving behind a blank slate.",
    )
    async def qclear(self, ctx):
        ctx.music_player.queue.clear()
        ctx.voice_client.stop()

    @queuecommand.command(
        name="pop",
        aliases=["remove"],
        brief="Pops a track off of the queue.",
        description="Pops a track of the queue. Index starts at 1.",
    )
    async def qpop(self, ctx, *, index: int):
        del ctx.music_player.queue.deque[index - 1]

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
            source = await YTDLSource.from_url(self.file_downloader, url, ctx.author)
            menu_source = QueuePlaylistSource(source, "Added:")
            pages = menus.MenuPages(source=menu_source)
            await pages.start(ctx)
            for track in source:
                await ctx.music_player.queue.put(track)

    @play.command(
        name="top",
        aliases=["t"],
        brief="Adds a song to the top of the queue.",
        description="Adds a supported song to the top of the current queue.",
    )
    async def pt(self, ctx, *, query):
        if not len(list(ctx.music_player.queue)) > 0:
            await ctx.invoke(self.play, query=query)
        else:
            async with ctx.typing():
                if validators.str_is_url(query):
                    url = query
                else:
                    url = f"ytsearch:{query}"
                source = await YTDLSource.from_url(self.file_downloader, url, ctx.author)
                menu_source = QueuePlaylistSource(source, "Added to top:")
                pages = menus.MenuPages(source=menu_source)
                await pages.start(ctx)
                for track in source:
                    ctx.music_player.queue.deque.appendleft(track)


def setup(bot):
    bot.add_cog(Music(bot))

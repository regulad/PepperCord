import asyncio
import collections
import typing

import discord
from youtube_dl import YoutubeDL
from discord.ext import commands, menus

from utils import checks, validators, errors, converters

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

    def __init__(self, source: discord.FFmpegPCMAudio, volume=0.5, *, info):
        super().__init__(source, volume)

        self.info = info

    @property
    def url(self):
        return self.info["webpage_url"]

    @classmethod
    async def from_url(cls, file_downloader: YoutubeDL, url: str):
        """Returns a YTDLSource or list of YTDLSource instances (If url refers to a playlist) from a url."""

        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, lambda: file_downloader.extract_info(url, download=False))

        tracks = []

        if info.setdefault("entries", None):
            # Url refers to a playlist, so a list of instances must be returned.

            for entry in info["entries"]:
                track = cls(discord.FFmpegPCMAudio(entry["url"], **ffmpeg_options), info=entry)
                tracks.append(track)

        else:
            # Url refers to a single track, so a single instance must be returned.

            track = cls(discord.FFmpegPCMAudio(info["url"], **ffmpeg_options), info=info)

            tracks.append(track)

        return tracks


class TrackPlaylist(list):
    @classmethod
    async def from_sanitized(cls, sanitized: list, *, file_downloader: YoutubeDL):
        loop = asyncio.get_event_loop()
        new_playlist = cls()
        for url in sanitized:
            new_playlist.extend(await YTDLSource.from_url(file_downloader, url, loop=loop))
        return new_playlist

    @property
    def sanitized(self):
        new_list = []
        for track in self:
            new_list.append(track.url)
        return new_list


class TrackQueue(asyncio.Queue):
    """Represents a queue."""

    def __init__(self, *args, guild: discord.Guild, **kwargs):
        self.guild = guild
        self.loop = False
        self.shuffle = False
        self.now_playing = None
        self.music_playing = False
        super().__init__(*args, **kwargs)

    def __iter__(self):
        return self._queue.__iter__()

    def __next__(self):
        return self._queue.__next__()

    def __len__(self):
        return self.qsize()

    @property
    def deque(self) -> collections.deque:
        return self._queue

    @property
    def playlist(self) -> TrackPlaylist:
        new_playlist = TrackPlaylist()
        for track in self:
            new_playlist.append(track)
        return track

    def clear(self):
        return self.deque.clear()


class MusicIsDone:
    def __init__(self, queue: TrackQueue):
        self.queue = queue

    def on_done(self, error: typing.Optional[Exception]):
        if error is not None:
            raise error
        else:
            self.queue.task_done()
            self.queue.now_playing = None


async def music_player(queue: TrackQueue):
    guild = queue.guild
    voice_client = guild.voice_client
    music_is_done = MusicIsDone(queue)
    while True:
        if voice_client is None:
            queue.clear()
            break
        track = await queue.get()
        voice_client.play(track, after=music_is_done.on_done)
        queue.now_playing = track
        while voice_client.is_playing():
            await asyncio.sleep(1)


class SourceCache(dict):
    """Stores the queues of guilds."""

    def guild(self, guild: discord.Guild):
        return self.setdefault(guild.id, TrackQueue(guild=guild))


class QueuePlaylistSource(menus.ListPageSource):
    def __init__(self, data: list, msg: str):
        self.msg = msg
        super().__init__(data, per_page=10)

    async def format_page(self, menu, page_entries):
        offset = menu.current_page * self.per_page
        base_embed = discord.Embed(title=self.msg, description=f"{len(page_entries)} total tracks")
        time_until = 0
        for iteration, value in enumerate(page_entries, start=offset):
            title = value.info["title"]
            duration = value.info["duration"]
            url = value.info["webpage_url"]
            time_until += duration
            base_embed.add_field(
                name=f"{iteration + 1}: {converters.duration_to_str(time_until)} left",
                value=f"[{title}]({url}): {converters.duration_to_str(duration)} long",
                inline=False,
            )
        return base_embed


class Music(commands.Cog):
    """Listen to your favorite tracks in a voice channel."""

    def __init__(self, bot):
        self.bot = bot
        self.file_downloader = YoutubeDL(ytdl_format_options)
        self.source_cache = SourceCache()

    async def cog_check(self, ctx):
        return await checks.is_alone_or_manager(ctx)

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="playlist",
        aliases=["pl"],
        brief="Commands for playlists.",
        description="Commands for playlists. Each user can have their own playlist, which persists between guilds.",
    )
    async def playlist(self, ctx):
        raise errors.SubcommandNotFound()

    @playlist.command(
        name="save",
        aliases=["set"],
        brief="Sets a playlist.",
        description="Sets user's playlist to the current queue.",
    )
    async def plset(self, ctx):
        queue = self.source_cache.guild(ctx.guild)
        ctx.user_doc.setdefault("music", {})["playlist"] = queue.playlist.sanitized
        await ctx.user_doc.replace_db()

    @playlist.command(
        name="load",
        aliases=["get"],
        brief="Loads a playlist.",
        description="Loads a playlist into the current queue. Does not overwrite existing queue, "
                    "it just appends to it.",
    )
    async def plget(self, ctx):
        user_playlist = ctx.user_doc.setdefault("music", {}).setdefault("playlist", [])
        user_track_playlist = await TrackPlaylist.from_sanitized(user_playlist, file_downloader=self.file_downloader)
        self.source_cache.guild(ctx.guild).deque.extend(user_track_playlist)

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="queue",
        aliases=["q"],
        brief="Commands for the queue.",
        description="Commands for the active queue currently being played.",
    )
    async def queuecommand(self, ctx):
        queue = self.source_cache.guild(ctx.guild)
        source = QueuePlaylistSource(list(queue.deque), "Current songs on queue:")
        pages = menus.MenuPages(source=source)
        await pages.start(ctx)

    @queuecommand.command(
        name="clear",
        aliases=["delete"],
        brief="Deletes all items on the queue.",
        description="Deletes all items on the queue, leaving behind a blank slate.",
    )
    async def qclear(self, ctx):
        queue = self.source_cache.guild(ctx.guild)
        queue.clear()
        ctx.voice_client.stop()

    @queuecommand.command(
        name="pop",
        aliases=["remove"],
        brief="Pops a track off of the queue.",
        description="Pops a track of the queue. Index starts at 1.",
    )
    async def qpop(self, ctx, *, index: int):
        index = (index - 1) or 0
        queue = self.source_cache.guild(ctx.guild)
        queue.deque.pop(index)

    @queuecommand.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="play",
        aliases=["p", "a", "add"],
        brief="Adds a song to the queue.",
        description="Adds a supported song to the current queue.",
    )
    async def play(self, ctx, *, query: str):
        if validators.str_is_url(query):
            url = query
        else:
            url = f"ytsearch:{query}"
        source = await YTDLSource.from_url(self.file_downloader, url)
        menu_source = QueuePlaylistSource(source, "Added:")
        pages = menus.MenuPages(source=menu_source)
        await pages.start(ctx)
        self.source_cache.guild(ctx.guild).deque.extend(source)

    @play.command(
        name="top",
        aliases=["t"],
        brief="Adds a song to the top of the queue.",
        description="Adds a supported song to the top of the current queue.",
    )
    async def pt(self, ctx, *, query):
        if validators.str_is_url(query):
            url = query
        else:
            url = f"ytsearch:{query}"
        source = await YTDLSource.from_url(self.file_downloader, url)
        menu_source = QueuePlaylistSource(source, "Added to top:")
        pages = menus.MenuPages(source=menu_source)
        await pages.start(ctx)
        self.source_cache.guild(ctx.guild).deque.extendleft(0, source)

    @play.before_invoke
    async def join_voice(self, ctx):
        voice_channel = ctx.author.voice.channel
        await voice_channel.connect()

    @play.after_invoke
    async def play_tracks(self, ctx):
        guild_queue = self.source_cache.guild(ctx.guild)
        voice_client = ctx.voice_client
        if not voice_client.is_playing():
            await music_player(guild_queue)


def setup(bot):
    bot.add_cog(Music(bot))

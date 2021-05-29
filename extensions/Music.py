import asyncio

import discord
from youtube_dl import YoutubeDL
from discord.ext import commands, menus

from utils import checks, validators, errors, converters

# Not sure what the deal with these is, but the d.py docs suggested it so ¯\_(ツ)_/¯
ytdl_format_options = {
    "format": "bestaudio/best",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",  # bind to ipv4 since ipv6 addresses cause issues sometimes (what year are we living in?)
}

ffmpeg_options = {"options": "-vn"}


class YTDLSource(discord.PCMVolumeTransformer):
    """Represents a source from YoutubeDL that has the ability to have it's volume changed."""

    def __init__(self, source: discord.FFmpegPCMAudio, volume=0.5, *, info=None):
        super().__init__(source, volume)

        self.info = info

    @property
    def url(self):
        return self.info["webpage_url"]

    @classmethod
    async def from_url(cls, file_downloader: YoutubeDL, url: str, *, loop=None):
        """Returns a YTDLSource or list of YTDLSource instances (If url refers to a playlist) from a url."""

        loop = loop or asyncio.get_event_loop()
        info = await loop.run_in_executor(None, lambda: file_downloader.extract_info(url, download=False))

        tracks = TrackPlaylist()

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
    def __init__(self, *args, **kwargs):
        self.loop = False
        self.shuffle = False
        super().__init__(*args, **kwargs)

    @classmethod
    async def from_sanitized(cls, sanitized: list, *, file_downloader: YoutubeDL, loop=None):
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


class SourceCache(dict):
    def guild(self, guild: discord.Guild):
        return self.setdefault(guild.id, TrackPlaylist())


class QueuePlaylistSource(menus.ListPageSource):
    def __init__(self, data: TrackPlaylist, guild):
        self.guild = guild
        super().__init__(data, per_page=10)

    async def format_page(self, menu, page_entries):
        offset = menu.current_page * self.per_page
        base_embed = discord.Embed(title=f"{self.guild.name}'s Current Playlist").set_thumbnail(url=self.guild.icon_url)
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
        description="Sets the selected playlist to the current playlist.",
    )
    async def plset(self, ctx):
        playlist = self.source_cache.guild(ctx.guild)
        ctx.user_doc.setdefault("music", {})["playlist"] = playlist.sanitized
        await ctx.user_doc.replace_db()

    @playlist.command(
        name="load",
        aliases=["get"],
        brief="Loads a playlist.",
        description="Loads a playlist into the current playlist. Does not overwrite existing playlist, "
        "it just appends it.",
    )
    async def plget(self, ctx):
        user_playlist = ctx.user_doc.setdefault("music", {}).setdefault("playlist", [])
        user_track_playlist = await TrackPlaylist.from_sanitized(
            user_playlist, file_downloader=self.file_downloader, loop=ctx.bot.loop
        )
        self.source_cache.guild(ctx.guild).extend(user_track_playlist)

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="queue",
        aliases=["q"],
        brief="Commands for the queue.",
        description="Commands for the active queue currently being played.",
    )
    async def queue(self, ctx):
        playlist = self.source_cache.guild(ctx.guild)
        source = QueuePlaylistSource(playlist, ctx.guild)
        pages = menus.MenuPages(source=source)
        await pages.start(ctx)

    @queue.commands(
        name="clear",
        aliases=["delete"],
        brief="Deletes all items on the queue.",
        description="Deletes all items on the queue, leaving behind a blank slate.",
    )
    async def qclear(self, ctx):
        playlist = self.source_cache.guild(ctx.guild)
        playlist.clear()
        ctx.voice_client.stop()

    @queue.command(
        name="pop",
        aliases=["remove"],
        brief="Pops a track off of the queue.",
        description="Pops a track of the queue. Index starts at 1.",
    )
    async def qpop(self, ctx, *, index: int):
        index = (index - 1) or 0
        playlist = self.source_cache.guild(ctx.guild)
        playlist.pop(index)

    @queue.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="play",
        aliases=["p", "a", "add"],
        brief="Adds a song to the playlist.",
        description="Adds a supported song to the current playlist.",
    )
    async def play(self, ctx, *, query: str):
        if validators.str_is_url(query):
            url = query
        else:
            url = "https://youtube.com"  # TODO: Find it!
        source = await YTDLSource.from_url(self.file_downloader, url, loop=ctx.bot.loop)
        self.source_cache.guild(ctx.guild).extend(source)

    @play.command(
        name="top",
        aliases=["t"],
        brief="Adds a song to the top of the playlist.",
        description="Adds a supported song to the top of the current playlist.",
    )
    async def pt(self, ctx, query):
        if validators.str_is_url(query):
            url = query
        else:
            url = "https://youtube.com"  # TODO: Find it!
        source = await YTDLSource.from_url(self.file_downloader, url, loop=ctx.bot.loop)
        self.source_cache.guild(ctx.guild).insert(0, source)


def setup(bot):
    bot.add_cog(Music(bot))

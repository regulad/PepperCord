from typing import Union

import discord
from discord.ext import commands
from youtube_dl import YoutubeDL

from utils import checks, embed_menus, converters, audio, music


class TrackPlaylist(list):
    @classmethod
    def from_queue(cls, queue: audio.TrackQueue):
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
            new_playlist.extend(await music.YTDLSource.from_url(file_downloader, url, user))
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

    async def cog_check(self, ctx):  # Meh.
        await checks.is_in_voice(ctx)
        try:
            await checks.is_alone(ctx)
        except commands.CheckFailure:
            try:
                await checks.is_man(ctx)
            except commands.CheckFailure:
                raise checks.NotAlone
        return True

    async def cog_before_invoke(self, ctx):
        if ctx.voice_client is None:
            await ctx.author.voice.channel.connect()

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="audioplayer",
        aliases=["p", "mp"],
        brief="Commands for the audio player.",
        description="Commands for controlling the audio player.",
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
        await ctx.audio_player.voice_client.disconnect()

    @player.command(
        name="pause",
        aliases=["play", "p"],
        brief="Toggles the audio player on and off.",
        description="Toggles the audio player between playing and paused.",
    )
    async def ppause(self, ctx):
        if ctx.audio_player.paused:
            ctx.audio_player.voice_client.resume()
        else:
            ctx.audio_player.voice_client.pause()

    @player.command(
        name="skip",
        aliases=["sk"],
        brief="Skips to the next song on the queue.",
        description="Skips the audio player to the next song on the queue.",
    )
    async def pskip(self, ctx):
        ctx.audio_player.voice_client.stop()

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
        ctx.author_document.setdefault("audio", {})["playlist"] = playlist.sanitized
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
                user_playlist = ctx.author_document.setdefault("audio", {})["playlist"]
            except KeyError:
                await ctx.send("You don't have a playlist saved.")
                return
            user_track_playlist = await TrackPlaylist.from_sanitized(
                user_playlist, ctx.author, file_downloader=ctx.audio_player.file_downloader
            )
            for track in user_track_playlist:
                await ctx.audio_player.queue.put(track)

    @commands.command(
        name="nowplaying",
        aliases=["np"],
        brief="Shows the currently playing track.",
        description="Shows the currently playing track.",
    )
    async def nowplaying(self, ctx):
        playing_track = ctx.audio_player.now_playing

        if playing_track is None:
            await ctx.send("Nothing is playing.")
        elif not isinstance(playing_track, music.YTDLSource):
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


def setup(bot):
    bot.add_cog(Music(bot))

import asyncio
import collections
from typing import Optional

import discord
from youtube_dl import YoutubeDL

from .config import ytdl_format_options


class AudioQueue(asyncio.Queue):
    @property
    def deque(
            self,
    ) -> collections.deque:  # Nasty, but its a weird property of how the Queue works. This may break!
        return self._queue


def _play_callback(error: Optional[Exception], *, future: asyncio.Future):
    if error is not None:
        future.set_exception(error)
    else:
        future.set_result(True)


def _voice_client_play(voice_client: discord.VoiceClient, source) -> asyncio.Future:
    future = voice_client.loop.create_future()
    voice_client.play(
        source, after=lambda exception: _play_callback(exception, future=future)
    )
    return future


class AudioPlayer:
    """Represents a music player that can play from a queue of sources."""

    def __init__(self, voice_client: discord.VoiceClient):
        self.voice_client = voice_client

        self.queue = AudioQueue()

        self.loop: bool = False

        self._file_downloader = None
        self._tts_client_session = None
        # Set to none so they will only be created when required.

        self.task = self.voice_client.loop.create_task(self.play())

    def __del__(self):
        if not self.done:
            self.task.cancel()

    @property
    def file_downloader(self):
        if self._file_downloader is None:
            self._file_downloader = YoutubeDL(ytdl_format_options)

        return self._file_downloader

    @property
    def done(self):
        return self.task.done()

    @property
    def playing(self):
        return self.voice_client.is_playing()

    @property
    def paused(self):
        return self.voice_client.is_paused()

    @property
    def now_playing(self):
        return self.voice_client.source

    async def play(self):
        while self.voice_client is not None:
            if len(self.voice_client.channel.members) <= 1:
                await self.voice_client.disconnect()

            track = await self.queue.get()

            if hasattr(track, "refresh"):
                track = await track.refresh()  # For YouTube time restrictions

            await _voice_client_play(self.voice_client, track)

            while self.loop:  # Python can suck my
                await _voice_client_play(self.voice_client, track)


__all__ = ["AudioPlayer", "AudioQueue"]

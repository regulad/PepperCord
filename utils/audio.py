import asyncio
import collections
from typing import Optional

import discord
from youtube_dl import YoutubeDL

from utils.music import ytdl_format_options


class TrackQueue(asyncio.Queue):
    @property
    def deque(self) -> collections.deque:  # Nasty, but its a weird property of how the Queue works. This may break!
        return self._queue


def play_callback(error: Optional[Exception], *, future: asyncio.Future):
    if error is not None:
        future.set_exception(error)
    else:
        future.set_result(True)


def voice_client_play(voice_client: discord.VoiceClient, source) -> asyncio.Future:
    future = voice_client.loop.create_future()
    voice_client.play(source, after=lambda exception: play_callback(exception, future=future))
    return future


class AudioPlayer:
    """Represents a music player that can play from a queue of sources."""

    def __init__(self, voice_client: discord.VoiceClient):
        self.voice_client = voice_client

        self.queue = TrackQueue()
        self.file_downloader = YoutubeDL(ytdl_format_options)

        self.task = self.voice_client.loop.create_task(self.play())

    def __del__(self):
        if not self.task.done():
            self.task.cancel()

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
        while True:
            if self.voice_client is None:
                self.queue.clear()
                break

            track = await self.queue.get()

            await voice_client_play(self.voice_client, track)

import asyncio
import collections
import copy
import datetime
from typing import Optional

import discord
from youtube_dl import YoutubeDL

from .config import YTDL_FORMAT_OPTIONS


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


async def prepare_track(track):  # I would typehint this, but circular imports.
    if (
            hasattr(track, "refresh")
            and hasattr(track, "created")
            and track.created + datetime.timedelta(seconds=10) <= datetime.datetime.now()
    ):  # Relatively arbitrary.
        return await track.refresh()  # For YouTube time restrictions
    else:
        return track


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
            self._file_downloader = YoutubeDL(YTDL_FORMAT_OPTIONS)

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

            if not self.loop:
                await _voice_client_play(self.voice_client, await prepare_track(track))
            else:
                while self.loop:
                    await _voice_client_play(
                        self.voice_client, await prepare_track(copy.copy(track))
                    )
                    # I have no idea why this object needs to be shallow copied before it works.
                    # Raises AttributeError on something called a _MissingSentinel?


__all__ = ["AudioPlayer", "AudioQueue"]

import asyncio
import typing

import discord

from .queue import TrackQueue


class MusicIsDone:
    def __init__(self, queue: TrackQueue):
        self.queue = queue

    def on_done(self, error: typing.Optional[Exception]):
        if error is not None:
            raise error
        else:
            self.queue.task_done()
            self.queue.now_playing = None


class MusicPlayer:
    """Represents a music player that can play from a queue of sources."""

    def __init__(self, voice_client: discord.VoiceClient):
        self.queue = TrackQueue()
        self.voice_client = voice_client

        self.now_playing = None

    async def play(self):
        music_is_done = MusicIsDone(self.queue)
        while True:
            if self.voice_client is None:
                self.queue.clear()
                break
            track = await self.queue.get()
            self.voice_client.play(track, after=music_is_done.on_done)
            self.now_playing = track
            while self.voice_client.is_playing():
                await asyncio.sleep(1)

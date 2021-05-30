import asyncio
from typing import Optional

import discord

from .queue import TrackQueue


class MusicIsRunning:
    """Class used for handling if a task is done or not."""  # Kinda sucks.

    def __init__(self, queue: TrackQueue):
        self.queue = queue

        self.running = False

    def on_start(self):
        self.running = True

    def on_done(self, error: Optional[Exception]):
        self.running = False
        self.queue.task_done()

        if error is not None:
            raise error


class MusicPlayer:
    """Represents a music player that can play from a queue of sources."""

    def __init__(self, voice_client: discord.VoiceClient):
        self.voice_client = voice_client

        self.queue = TrackQueue()

        self.task = self.voice_client.loop.create_task(self.play())

    def __del__(self):
        if not self.task.done():
            self.task.cancel()

    @property
    def running(self):
        return not self.task.done()

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

            music_is_running = MusicIsRunning(self.queue)

            track = await self.queue.get()

            self.voice_client.play(track, after=music_is_running.on_done)

            music_is_running.on_start()

            while music_is_running.running:  # Jankiest part
                if self.voice_client is None:
                    self.queue.clear()
                    break

                if len(self.voice_client.channel.members) == 1:
                    await self.voice_client.disconnect()
                    break

                await asyncio.sleep(5)

from abc import ABC
from asyncio import Queue, Future, Task, wait_for
from collections import deque
from typing import Optional, cast

from discord import VoiceClient, Client, AudioSource
from discord import abc


class EnhancedSource(AudioSource, ABC):
    @property
    def invoker(self) -> abc.User:
        raise NotImplementedError

    @property
    def length(self) -> Optional[int]:
        """Get the length of the source. If this is not feasible, you can return None."""
        return None

    async def refresh(self, voice_client: "CustomVoiceClient") -> "EnhancedSource":
        """
        This allows you to fetch the source again,
        in case it is something like a YouTube video where the ability to read it decays after a set amount of time.
        """
        return self


class AudioQueue(Queue[EnhancedSource]):
    def _init(self, maxsize: int) -> None:
        self._queue: deque[EnhancedSource] = deque(maxlen=maxsize) if maxsize > 0 else deque()

    @property
    def deque(self) -> deque:
        return self._queue


def _maybe_exception(future: Future[None], exception: Optional[Exception]) -> None:
    if exception is not None:
        future.set_exception(exception)
    else:
        future.set_result(None)


class CustomVoiceClient(VoiceClient):
    @staticmethod
    async def create(connectable: abc.Connectable, **kwargs) -> "CustomVoiceClient":
        return await connectable.connect(**kwargs, cls=CustomVoiceClient)

    def __init__(self, client: Client, channel: abc.Connectable):
        super().__init__(client, channel)
        self._should_loop: bool = False
        self._audio_queue: AudioQueue = AudioQueue()

    @property
    def queue(self) -> AudioQueue:
        return self._audio_queue

    def play_future(self, source: AudioSource) -> Future[None]:
        future: Future[None] = self.loop.create_future()
        self.play(source, after=lambda exception: _maybe_exception(future, exception))
        return future

    def create_task(self, *args, **kwargs) -> Task[None]:
        return self.loop.create_task(self.join_queue(*args, **kwargs))

    async def join_queue(self, timeout: Optional[int] = 60, leave_when_done: bool = True) -> None:
        """
        Plays tracks from the queue while tracks remain on the queue.
        This should be run in an async task.
        If the timeout is reached, a TimeoutError will be thrown.
        """
        try:
            while True:
                track: EnhancedSource = await wait_for(self._audio_queue.get(), timeout)

                while True:
                    track: EnhancedSource = await track.refresh(self)
                    await self.play_future(track)
                    if not self._should_loop:
                        break
                if not self.is_connected():
                    break
        finally:
            if leave_when_done and self.is_connected():
                await self.disconnect(force=False)

    @property
    def source(self) -> Optional[EnhancedSource]:
        return cast(EnhancedSource, super().source)

    @property
    def ms_read(self) -> Optional[int]:
        """Returns the amount of milliseconds that have been read from the audio source."""
        if self._player is None:
            return None
        else:
            return self._player.loops * 20

    @property
    def distance(self) -> Optional[float]:
        """Returns an int 0-1 representing the distance through the track."""
        if self.source is None:
            return None
        elif self.source.length is None:
            return None
        else:
            return self.ms_read / self.source.length


__all__: list[str] = [
    "CustomVoiceClient",
    "EnhancedSource",
    "AudioQueue"
]

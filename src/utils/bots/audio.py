from abc import ABC
from asyncio import Queue, Future, wait_for
from collections import deque
from logging import getLogger
from typing import Any, Optional, Self, cast

from discord import VoiceClient, Client, AudioSource, TextChannel, Thread
from discord import abc

logger = getLogger(__name__)


class EnhancedSource(AudioSource, ABC):
    @property
    def invoker(self) -> abc.User:
        raise NotImplementedError

    @property
    def duration(self) -> Optional[int]:
        """Get the length of the source. If this is not feasible, you can return None."""
        return None

    @property
    def name(self) -> str:
        return "Unknown Track"

    @property
    def description(self) -> str:
        return f'"{self.name}"'

    async def refresh(self, voice_client: "CustomVoiceClient") -> Self:
        """
        This allows you to fetch the source again,
        in case it is something like a YouTube video where the ability to read it decays after a set amount of time.
        """
        return self


class AudioQueue(Queue[EnhancedSource]):
    def _init(self, maxsize: int) -> None:
        self._queue: deque[EnhancedSource] = (
            deque(maxlen=maxsize) if maxsize > 0 else deque()
        )

    def _get(self) -> EnhancedSource:
        return self._queue.popleft()

    def _put(self, item: EnhancedSource) -> None:
        self._queue.append(item)

    @property
    def deque(self) -> deque[EnhancedSource]:
        return self._queue


def _maybe_exception(future: Future[None], exception: Optional[Exception]) -> None:
    if exception is not None:
        future.set_exception(exception)
    else:
        future.set_result(None)


class CustomVoiceClient(VoiceClient):
    @staticmethod
    async def create(
        connectable: abc.Connectable, **kwargs: Any
    ) -> "CustomVoiceClient":
        return await connectable.connect(**kwargs, cls=CustomVoiceClient)

    def __init__(self, client: Client, channel: abc.Connectable):
        super().__init__(client, channel)
        self.should_loop: bool = False
        self._task = self.loop.create_task(self._run())
        self._audio_queue: AudioQueue = AudioQueue()
        self._bound_to: Optional[TextChannel | Thread] = None

        self.wait_for: Optional[int] = None

    @property
    def queue(self) -> AudioQueue:
        return self._audio_queue

    @property
    def bound(self) -> Optional[TextChannel | Thread]:
        return self._bound_to

    def bind(self, to: TextChannel | Thread) -> None:
        assert self._bound_to is None
        assert isinstance(to, (TextChannel, Thread))
        self._bound_to = to

    def play_future(self, source: AudioSource) -> Future[None]:
        future: Future[None] = self.loop.create_future()
        self.play(source, after=lambda exception: _maybe_exception(future, exception))
        return future

    async def _run(self) -> None:
        """
        Plays tracks from the queue while tracks remain on the queue.
        This should be run in an async task.
        If the timeout is reached, a TimeoutError will be thrown.
        """
        try:
            while True:
                track: EnhancedSource = await wait_for(
                    self._audio_queue.get(), self.wait_for
                )

                while True:
                    track = await track.refresh(self)
                    try:
                        await self.play_future(track)
                    except Exception:
                        logger.warning(f"Failed to play track {track} on CVC {self}")
                        pass  # We don't care. Go on to the next one!
                    if not self.should_loop:
                        break
        except TimeoutError:
            if self.bound is not None:
                await self.bound.send("Ran out of tracks to play. Leaving...")
            self.wait_for = 120  # Reset this
        finally:
            if self.is_connected():
                await self.disconnect(force=False)

    async def disconnect(self, *, force: bool = False) -> None:
        await super().disconnect(force=force)
        if not self._task.done():
            self._task.cancel()

    @property
    def source(self) -> Optional[EnhancedSource]:
        return cast(EnhancedSource, super().source)

    @source.setter
    def source(self, _: AudioSource) -> None:
        raise NotImplementedError(
            "CustomVoiceClient feeds from a queue, and cannot be directly controlled!"
        )

    @property
    def ms_read(self) -> Optional[int]:
        """Returns the amount of milliseconds that have been read from the audio source."""
        if self._player is None:
            return None
        else:
            return self._player.loops * 20

    @property
    def progress(self) -> Optional[float]:
        """Returns a float 0-1 representing the distance through the track."""
        if self.source is None:
            return None
        elif self.source.duration is None:
            return None
        else:
            return self.ms_read or 0 / self.source.duration


__all__: list[str] = ["CustomVoiceClient", "EnhancedSource", "AudioQueue"]

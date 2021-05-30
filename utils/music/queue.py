import asyncio
import collections


class TrackQueue(asyncio.Queue):
    """Represents a queue."""

    @property
    def deque(self) -> collections.deque:
        return self._queue

    def clear(self):
        return self.deque.clear()

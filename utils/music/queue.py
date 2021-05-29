import asyncio
import collections


class TrackQueue(asyncio.Queue):
    """Represents a queue."""

    def __iter__(self):
        return self._queue.__iter__()

    def __next__(self):
        return self._queue.__next__()

    def __len__(self):
        return self.qsize()

    @property
    def deque(self) -> collections.deque:
        return self._queue

    def clear(self):
        return self.deque.clear()

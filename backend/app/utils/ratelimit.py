import time
from collections import deque


class SlidingWindowLimiter:
    """In-process sliding-window limiter. Swap for Redis when running several API workers."""

    def __init__(self, max_keys: int = 50_000):
        self.hits: dict[str, deque[float]] = {}
        self.max_keys = max_keys

    def hit(self, key: str, limit: int, window: float = 60.0) -> float | None:
        """Record a hit; return None if allowed, else seconds until the next slot frees up."""
        now = time.monotonic()
        bucket = self.hits.get(key)
        if bucket is None:
            if len(self.hits) >= self.max_keys:
                self._prune(now, window)
            bucket = self.hits[key] = deque()
        while bucket and now - bucket[0] >= window:
            bucket.popleft()
        if len(bucket) >= limit:
            return max(0.0, window - (now - bucket[0]))
        bucket.append(now)
        return None

    def _prune(self, now: float, window: float) -> None:
        for key in [k for k, b in self.hits.items() if not b or now - b[-1] >= window]:
            del self.hits[key]

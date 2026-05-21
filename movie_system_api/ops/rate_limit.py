"""简易内存限流（按 IP + 路由），适用于登录等敏感接口。"""
from __future__ import annotations

import threading
import time
from collections import defaultdict


class RateLimiter:
    def __init__(self):
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._hits[key]
            self._hits[key] = [t for t in bucket if t > cutoff]
            if len(self._hits[key]) >= limit:
                return False
            self._hits[key].append(now)
            return True

    def retry_after(self, key: str, window_seconds: int) -> int:
        with self._lock:
            bucket = self._hits.get(key) or []
            if not bucket:
                return 0
            wait = int(window_seconds - (time.time() - bucket[0])) + 1
            return max(1, wait)


limiter = RateLimiter()

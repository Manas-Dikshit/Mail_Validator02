from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any, Optional


class TTLCache:
    """Simple thread-safe TTL + LRU-bounded cache.

    Not distributed; intended for single-process CLI/API usage. For
    multi-process deployments swap this for Redis behind the same
    get/set interface.
    """

    def __init__(self, max_size: int = 50_000, default_ttl: int = 3600) -> None:
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._store: "OrderedDict[str, tuple[float, Any]]" = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at < time.time():
                del self._store[key]
                return None
            self._store.move_to_end(key)
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        ttl = ttl if ttl is not None else self._default_ttl
        with self._lock:
            self._store[key] = (time.time() + ttl, value)
            self._store.move_to_end(key)
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)

    def stats(self) -> dict:
        with self._lock:
            return {"size": len(self._store), "max_size": self._max_size}

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

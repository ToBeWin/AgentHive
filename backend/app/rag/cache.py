"""Lightweight TTL + LRU cache for RAG retrieval hot paths.

Embedding computation and vector search are the dominant latency sources in
RAG pipelines. Caching short, repeated queries (e.g. customer service
greetings, common policy questions) cuts p50 latency significantly without
affecting correctness for fresh documents.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Generic, TypeVar

logger = logging.getLogger(__name__)

K = TypeVar("K")
V = TypeVar("V")


class TTLCache(Generic[K, V]):
    """Thread-safe TTL + size-bounded LRU cache.

    - Entries expire after `ttl_seconds` (lazy eviction on access).
    - Hard cap at `maxsize` entries; LRU eviction when full.
    - `clear()` allows callers to invalidate after document ingestion.
    """

    def __init__(self, *, maxsize: int = 512, ttl_seconds: float = 300.0) -> None:
        self._maxsize = maxsize
        self._ttl = ttl_seconds
        self._data: OrderedDict[K, tuple[float, V]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: K) -> V | None:
        now = time.monotonic()
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self._misses += 1
                return None
            expires_at, value = entry
            if expires_at < now:
                self._data.pop(key, None)
                self._misses += 1
                return None
            self._data.move_to_end(key)
            self._hits += 1
            return value

    def set(self, key: K, value: V) -> None:
        now = time.monotonic()
        expires_at = now + self._ttl
        with self._lock:
            self._data[key] = (expires_at, value)
            self._data.move_to_end(key)
            while len(self._data) > self._maxsize:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "size": len(self._data),
                "hits": self._hits,
                "misses": self._misses,
                "maxsize": self._maxsize,
                "ttl_seconds": int(self._ttl),
            }


def cached_call(
    cache: TTLCache[Any, V],
    key_fn: Callable[..., Any],
) -> Callable[[Callable[..., V]], Callable[..., V]]:
    """Decorator factory: cache a function's return value in a TTLCache.

    `key_fn` receives the same args as the wrapped function and must return a
    hashable cache key. Exceptions from the wrapped function bypass the cache.
    """

    def decorator(func: Callable[..., V]) -> Callable[..., V]:
        def wrapper(*args: Any, **kwargs: Any) -> V:
            key = key_fn(*args, **kwargs)
            cached = cache.get(key)
            if cached is not None:
                return cached
            value = func(*args, **kwargs)
            cache.set(key, value)
            return value

        setattr(wrapper, "__wrapped__", func)
        setattr(wrapper, "__cache__", cache)
        return wrapper

    return decorator


# Shared caches (process-wide). Keep small to bound memory.
EMBEDDING_CACHE: TTLCache[Any, Any] = TTLCache(maxsize=1024, ttl_seconds=600.0)
RETRIEVAL_CACHE: TTLCache[Any, Any] = TTLCache(maxsize=256, ttl_seconds=180.0)


def clear_rag_caches() -> None:
    """Invalidate all RAG caches. Call after document ingestion or KB edits."""
    EMBEDDING_CACHE.clear()
    RETRIEVAL_CACHE.clear()
    logger.info("rag caches cleared")

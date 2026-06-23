import time
from collections import defaultdict, deque
from hashlib import sha256
from threading import Lock
from typing import Any, Protocol


class RateLimiter(Protocol):
    def hit(self, key: str, *, limit: int, window_seconds: int) -> bool: ...


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def hit(self, key: str, *, limit: int, window_seconds: int) -> bool:
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True


class RedisRateLimiter:
    _HIT_SCRIPT = """
    local current = redis.call("INCR", KEYS[1])
    if current == 1 then
      redis.call("EXPIRE", KEYS[1], ARGV[1])
    end
    if current > tonumber(ARGV[2]) then
      return 0
    end
    return 1
    """

    def __init__(
        self,
        redis_url: str,
        *,
        client: Any | None = None,
        key_prefix: str = "passport-auth:rate-limit",
    ) -> None:
        if client is None:
            from redis import Redis

            client = Redis.from_url(redis_url)
        self._client = client
        self._key_prefix = key_prefix

    def hit(self, key: str, *, limit: int, window_seconds: int) -> bool:
        redis_key = f"{self._key_prefix}:{sha256(key.encode('utf-8')).hexdigest()}"
        return bool(
            self._client.eval(
                self._HIT_SCRIPT,
                1,
                redis_key,
                int(window_seconds),
                int(limit),
            )
        )


def create_rate_limiter(redis_url: str | None = None) -> RateLimiter:
    if redis_url:
        return RedisRateLimiter(redis_url)
    return InMemoryRateLimiter()


def rate_limit_client(headers: dict[str, str], client_host: str | None) -> str:
    forwarded_for = headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or "unknown"
    return client_host or "unknown"

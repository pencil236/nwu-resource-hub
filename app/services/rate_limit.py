import threading
import time
from collections import defaultdict
from typing import cast

from fastapi import HTTPException, status
from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

_memory_hits: dict[str, list[float]] = defaultdict(list)
_lock = threading.Lock()


def enforce_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    settings = get_settings()
    try:
        redis = Redis.from_url(settings.redis_url, socket_connect_timeout=0.2)
        bucket = f"rate:{key}:{int(time.time() // window_seconds)}"
        count = cast(int, redis.incr(bucket))
        if count == 1:
            redis.expire(bucket, window_seconds + 1)
    except RedisError:
        now = time.monotonic()
        with _lock:
            recent = [stamp for stamp in _memory_hits[key] if now - stamp < window_seconds]
            recent.append(now)
            _memory_hits[key] = recent
            count = len(recent)
    if count > limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "请求过于频繁，请稍后再试")

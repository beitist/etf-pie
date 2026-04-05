import json
import os
from typing import Any

import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

_redis: redis.Redis | None = None
_memory_cache: dict[str, str] = {}

# TTLs in seconds
TTL_PROFILE = 86400  # 24h
TTL_CHART = 14400  # 4h
TTL_SEARCH = 3600  # 1h


async def get_redis() -> redis.Redis | None:
    global _redis
    if _redis is None:
        try:
            _redis = redis.from_url(REDIS_URL, decode_responses=True)
            await _redis.ping()
        except Exception:
            _redis = None
    return _redis


async def cache_get(key: str) -> Any | None:
    r = await get_redis()
    if r:
        try:
            val = await r.get(key)
            if val:
                return json.loads(val)
        except Exception:
            pass
    # Fallback: in-memory
    if key in _memory_cache:
        return json.loads(_memory_cache[key])
    return None


async def cache_set(key: str, value: Any, ttl: int = TTL_PROFILE) -> None:
    data = json.dumps(value, ensure_ascii=False)
    r = await get_redis()
    if r:
        try:
            await r.set(key, data, ex=ttl)
            return
        except Exception:
            pass
    # Fallback: in-memory (no TTL)
    _memory_cache[key] = data

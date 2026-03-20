"""
Redis cache helpers.
"""
import functools
import hashlib
import json
import logging
from typing import Any, Callable, Optional

from flask import current_app

logger = logging.getLogger(__name__)
_redis_client = None


def get_redis():
    global _redis_client
    if _redis_client is None:
        import redis
        url = current_app.config.get("REDIS_URL", "redis://localhost:6379/0")
        db = current_app.config.get("REDIS_DB", 0)
        pool = redis.ConnectionPool.from_url(
            url,
            db=db,
            max_connections=current_app.config.get("REDIS_MAX_CONNECTIONS", 20),
            socket_timeout=current_app.config.get("REDIS_SOCKET_TIMEOUT", 5),
            socket_connect_timeout=2,
            decode_responses=True,
        )
        _redis_client = redis.Redis(connection_pool=pool)
    return _redis_client


def cache_get(key: str) -> Optional[Any]:
    try:
        raw = get_redis().get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as exc:
        logger.warning("Cache GET error for %s: %s", key, exc)
        return None


def cache_set(key: str, value: Any, ttl: int = 300) -> bool:
    try:
        get_redis().setex(key, ttl, json.dumps(value))
        return True
    except Exception as exc:
        logger.warning("Cache SET error for %s: %s", key, exc)
        return False


def cache_delete(key: str) -> bool:
    try:
        get_redis().delete(key)
        return True
    except Exception as exc:
        logger.warning("Cache DELETE error for %s: %s", key, exc)
        return False


def cache_delete_pattern(pattern: str) -> int:
    try:
        r = get_redis()
        keys = r.keys(pattern)
        if keys:
            return r.delete(*keys)
        return 0
    except Exception as exc:
        logger.warning("Cache pattern delete error for %s: %s", pattern, exc)
        return 0


def cache_increment(key: str, amount: int = 1, ttl: int = 3600) -> Optional[int]:
    """Atomically increment a counter key. Applies TTL when the key is first created."""
    try:
        r = get_redis()
        new_val = r.incrby(key, amount)
        if new_val == amount:  # key was just created by this increment
            r.expire(key, ttl)
        return new_val
    except Exception as exc:
        logger.warning("Cache INCREMENT error for %s: %s", key, exc)
        return None


def cache_get_or_set(key: str, fn: Callable, ttl: int = 300) -> Any:
    """Return cached value or call fn(), store the result, and return it."""
    hit = cache_get(key)
    if hit is not None:
        return hit
    value = fn()
    cache_set(key, value, ttl=ttl)
    return value


def cache_ttl(key: str) -> Optional[int]:
    """Return remaining TTL in seconds, or None if the key does not exist."""
    try:
        ttl = get_redis().ttl(key)
        return ttl if ttl >= 0 else None
    except Exception as exc:
        logger.warning("Cache TTL error for %s: %s", key, exc)
        return None


def cache_flush_all() -> bool:
    """Flush all keys in the current Redis DB. Use carefully in production."""
    try:
        get_redis().flushdb()
        logger.warning("Cache flushed (flushdb called)")
        return True
    except Exception as exc:
        logger.warning("Cache flush error: %s", exc)
        return False


def make_cache_key(*parts) -> str:
    raw = ":".join(str(p) for p in parts)
    return "wf:" + hashlib.md5(raw.encode()).hexdigest()  # noqa: S324  # nosec B324


def cached(ttl: int = 300, key_fn: Optional[Callable] = None):
    """Decorator — cache the return value of a function in Redis."""
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            if key_fn is not None:
                cache_key = key_fn(*args, **kwargs)
            else:
                cache_key = make_cache_key(f.__module__, f.__name__, *args, *kwargs.values())

            hit = cache_get(cache_key)
            if hit is not None:
                return hit

            result = f(*args, **kwargs)
            cache_set(cache_key, result, ttl=ttl)
            return result
        return wrapper
    return decorator

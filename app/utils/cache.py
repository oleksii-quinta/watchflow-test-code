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
        _redis_client = redis.from_url(url, decode_responses=True)
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

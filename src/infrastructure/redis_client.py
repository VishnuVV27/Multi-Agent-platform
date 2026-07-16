import redis
from redis import Redis
from typing import Any, Optional

from src.config import settings

redis_client: Optional[Redis] = None


async def init_redis():
    """Initialize Redis connection."""
    global redis_client
    try:
        redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        # Test connection
        redis_client.ping()
        print("✅ Redis connected")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        raise


def get_redis() -> Redis:
    """Get Redis client instance."""
    if redis_client is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return redis_client


async def cache_get(key: str) -> Optional[Any]:
    """Get value from cache."""
    client = get_redis()
    return client.get(key)


async def cache_set(key: str, value: Any, ttl: int = 3600) -> bool:
    """Set value in cache with optional TTL."""
    client = get_redis()
    return client.setex(key, ttl, value)


async def cache_delete(key: str) -> bool:
    """Delete value from cache."""
    client = get_redis()
    return bool(client.delete(key))


async def cache_exists(key: str) -> bool:
    """Check if key exists in cache."""
    client = get_redis()
    return bool(client.exists(key))

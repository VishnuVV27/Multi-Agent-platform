"""
Rate Limiter: Token bucket algorithm for request rate limiting.

Controls requests per minute/hour.
"""

import logging
import time
from typing import Dict, Tuple, Optional

from src.infrastructure.redis_client import get_redis_client
from src.rate_limiting.policy_engine import get_policy_engine

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter using Redis.

    Allows configurable requests per minute/hour.
    """

    def __init__(self):
        """Initialize rate limiter."""
        self.redis = get_redis_client()
        self.policy_engine = get_policy_engine()

    def check_rate_limit(
        self,
        identifier: str,
        limit_type: str = "requests_per_minute",
    ) -> Tuple[bool, Dict[str, any]]:
        """
        Check if request is within rate limit.

        Args:
            identifier: User/agent/workflow ID
            limit_type: Type of limit (requests_per_minute, requests_per_hour)

        Returns:
            (is_allowed, info_dict)
            info_dict: {allowed, remaining, reset_in_seconds, limit}
        """
        try:
            # Get limit from policy
            policy = self.policy_engine.get_user_policy()
            limit = policy.get(limit_type, 20)

            # Calculate time window (in seconds)
            if "minute" in limit_type:
                window_seconds = 60
            elif "hour" in limit_type:
                window_seconds = 3600
            else:
                window_seconds = 60

            # Redis key for this identifier
            key = f"rate_limit:{identifier}:{limit_type}"

            # Get current count
            current_count = int(self.redis.get(key) or 0)

            info = {
                "allowed": current_count < limit,
                "remaining": max(0, limit - current_count - 1),
                "reset_in_seconds": self.redis.ttl(key) if current_count > 0 else window_seconds,
                "limit": limit,
                "current": current_count,
            }

            if current_count < limit:
                # Increment counter
                pipe = self.redis.pipeline()
                pipe.incr(key)
                pipe.expire(key, window_seconds)
                pipe.execute()

                logger.debug(f"Rate limit OK: {identifier} ({current_count + 1}/{limit})")
                return True, info
            else:
                logger.warning(f"Rate limit exceeded: {identifier} ({current_count}/{limit})")
                return False, info

        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open on error (allow request)
            return True, {"allowed": True, "error": str(e)}

    def get_remaining_quota(self, identifier: str) -> Dict[str, int]:
        """
        Get remaining quota for an identifier.

        Args:
            identifier: User/agent/workflow ID

        Returns:
            Dict with remaining quotas
        """
        try:
            policy = self.policy_engine.get_user_policy()

            remaining = {}

            # Check requests per minute
            rpm_key = f"rate_limit:{identifier}:requests_per_minute"
            rpm_limit = policy.get("requests_per_minute", 20)
            rpm_used = int(self.redis.get(rpm_key) or 0)
            remaining["requests_per_minute"] = max(0, rpm_limit - rpm_used)

            # Check requests per hour
            rph_key = f"rate_limit:{identifier}:requests_per_hour"
            rph_limit = policy.get("requests_per_hour", 500)
            rph_used = int(self.redis.get(rph_key) or 0)
            remaining["requests_per_hour"] = max(0, rph_limit - rph_used)

            return remaining

        except Exception as e:
            logger.error(f"Failed to get remaining quota: {e}")
            return {}

    def reset_limit(self, identifier: str) -> bool:
        """
        Reset rate limit for an identifier (admin only).

        Args:
            identifier: User/agent/workflow ID

        Returns:
            True if reset successful
        """
        try:
            self.redis.delete(f"rate_limit:{identifier}:requests_per_minute")
            self.redis.delete(f"rate_limit:{identifier}:requests_per_hour")
            logger.info(f"Rate limit reset: {identifier}")
            return True
        except Exception as e:
            logger.error(f"Failed to reset rate limit: {e}")
            return False


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter

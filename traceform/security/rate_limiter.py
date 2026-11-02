import logging
import time
from collections import defaultdict
from typing import Dict, List, Tuple
from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    """
    §6F — Sliding Window Rate Limiter.
    Tracks requests per operator, API key hash, or client IP within a sliding time window.
    """

    def __init__(self, max_requests: int = 120, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> Tuple[bool, int, float]:
        """
        Check if request is allowed for a given tracking key.
        Returns: (is_allowed, remaining_requests, reset_after_seconds)
        """
        now = time.time()
        window_start = now - self.window_seconds

        # Clean old timestamps
        timestamps = [t for t in self._history[key] if t > window_start]
        self._history[key] = timestamps

        if len(timestamps) < self.max_requests:
            self._history[key].append(now)
            remaining = self.max_requests - len(self._history[key])
            return True, remaining, float(self.window_seconds)

        oldest = timestamps[0] if timestamps else now
        reset_after = max(0.0, oldest + self.window_seconds - now)
        return False, 0, round(reset_after, 2)


# Global rate limiter instance
_global_limiter = SlidingWindowRateLimiter(max_requests=200, window_seconds=60)


async def check_rate_limit(request: Request, key_identifier: str = "global") -> None:
    """FastAPI dependency to enforce sliding window rate limiting."""
    client_ip = request.client.host if request.client else "unknown"
    tracking_key = f"{key_identifier}:{client_ip}"

    allowed, remaining, reset_after = _global_limiter.is_allowed(tracking_key)
    if not allowed:
        logger.warning("Rate limit exceeded for %s. Reset in %ss", tracking_key, reset_after)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Maximum {_global_limiter.max_requests} requests per {_global_limiter.window_seconds}s. Try again in {reset_after}s.",
            headers={"Retry-After": str(int(reset_after))},
        )

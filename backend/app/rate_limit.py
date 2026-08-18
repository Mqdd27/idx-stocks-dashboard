"""Simple in-memory sliding-window rate limiter for AI endpoints."""
import time
from typing import Optional

from .config import get_settings

settings = get_settings()

_hits: dict[str, list[float]] = {}


def rate_limit(key: str, limit: Optional[int] = None, window: float = 60.0) -> bool:
    """Return True if request is allowed, False if over limit."""
    limit = limit or settings.ai_rate_limit_per_minute
    now = time.monotonic()
    bucket = _hits.setdefault(key, [])
    bucket[:] = [t for t in bucket if now - t < window]
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True
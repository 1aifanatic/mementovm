from __future__ import annotations

import hmac
import json
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException

from .config import Settings


class SlidingWindowRateLimiter:
    """Small per-process guard for the single-instance public demo profile."""

    def __init__(self, limit: int, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, *, now: float | None = None) -> bool:
        if self.limit <= 0:
            return True
        current = time.monotonic() if now is None else now
        cutoff = current - self.window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(current)
            return True


def authorize_event_ingestion(
    settings: Settings, *, supplied_key: str | None, source: str
) -> None:
    configured_key = settings.event_ingest_api_key
    if configured_key:
        if not supplied_key or not hmac.compare_digest(supplied_key, configured_key):
            raise HTTPException(401, "Invalid event ingestion API key")
        return
    if settings.app_env == "production":
        raise HTTPException(503, "Event ingestion is disabled until an API key is configured")
    if source != "simulator":
        raise HTTPException(401, "Development event ingestion is limited to the simulator")


def validate_event_size(payload: dict, maximum_bytes: int) -> None:
    encoded = json.dumps(payload, default=str, separators=(",", ":")).encode("utf-8")
    if len(encoded) > maximum_bytes:
        raise HTTPException(413, "Event payload exceeds the configured size limit")

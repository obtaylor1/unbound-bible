import hashlib
import time
from collections import defaultdict, deque
from threading import Lock
from fastapi import HTTPException, Request


class InMemoryRateLimiter:
    def __init__(self):
        self.events = defaultdict(deque); self.lock = Lock()

    def check(self, bucket: str, key: str, limit: int, window_seconds: int) -> None:
        now = time.monotonic(); identifier = (bucket, key)
        with self.lock:
            events = self.events[identifier]
            while events and events[0] <= now - window_seconds: events.popleft()
            if len(events) >= limit:
                retry = max(1, int(window_seconds - (now - events[0])))
                raise HTTPException(status_code=429, detail={'code': 'rate_limited', 'message': 'Too many requests. Please try again shortly.', 'retry_after': retry}, headers={'Retry-After': str(retry)})
            events.append(now)


def request_key(request: Request) -> str:
    authorization = request.headers.get('authorization', '')
    if authorization: return 'token:' + hashlib.sha256(authorization.encode()).hexdigest()[:24]
    return 'ip:' + (request.client.host if request.client else 'unknown')


def enforce_rate_limit(bucket: str, setting_name: str, window_seconds: int):
    def dependency(request: Request) -> None:
        limit = getattr(request.app.state.settings, setting_name)
        request.app.state.rate_limiter.check(bucket, request_key(request), limit, window_seconds)
    return dependency

from fastapi import Request, HTTPException
from collections import defaultdict
from datetime import datetime, timedelta
import asyncio


class RateLimiter:
    def __init__(self):
        self.requests = defaultdict(list)
        self.lock = asyncio.Lock()

    async def check_rate_limit(
            self,
            key: str,
            max_requests: int = 60,
            window_seconds: int = 60
    ):
        async with self.lock:
            now = datetime.utcnow()
            window_start = now - timedelta(seconds=window_seconds)

            # Remove old requests
            self.requests[key] = [
                req_time for req_time in self.requests[key]
                if req_time > window_start
            ]

            if len(self.requests[key]) >= max_requests:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Max {max_requests} requests per {window_seconds} seconds."
                )

            self.requests[key].append(now)


rate_limiter = RateLimiter()


async def rate_limit_dependency(request: Request):
    # Use IP address as key
    client_ip = request.client.host
    await rate_limiter.check_rate_limit(client_ip)
"""
CyberShield AI — Login Rate Limiter
Extensible in-memory sliding window rate limiter for login endpoints.
Protects against brute-force credential stuffing attacks.
"""

import time
from typing import Dict, List, Tuple
from fastapi import HTTPException, status, Request


class LoginRateLimiter:
    def __init__(self, max_attempts: int = 5, window_seconds: int = 900):  # 5 attempts per 15 minutes
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: Dict[str, List[float]] = {}

    def _clean_expired(self, key: str, now: float) -> None:
        cutoff = now - self.window_seconds
        if key in self._attempts:
            self._attempts[key] = [t for t in self._attempts[key] if t > cutoff]
            if not self._attempts[key]:
                del self._attempts[key]

    def _get_keys(self, request: Request, email: str) -> List[str]:
        client_ip = "127.0.0.1"
        if request.client and request.client.host:
            client_ip = request.client.host
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()

        norm_email = email.lower().strip() if email else "anonymous"
        return [f"ip:{client_ip}", f"email:{norm_email}"]

    def check_rate_limit(self, request: Request, email: str) -> None:
        """Raises HTTPException(429) if the client or email has exceeded max failed attempts."""
        now = time.time()
        keys = self._get_keys(request, email)

        for key in keys:
            self._clean_expired(key, now)
            attempts = self._attempts.get(key, [])
            if len(attempts) >= self.max_attempts:
                earliest = attempts[0]
                retry_after = int(self.window_seconds - (now - earliest))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many failed login attempts. Please try again in {max(1, retry_after)} seconds.",
                    headers={"Retry-After": str(max(1, retry_after))}
                )

    def record_failure(self, request: Request, email: str) -> None:
        """Records a failed login attempt for the client IP and email."""
        now = time.time()
        keys = self._get_keys(request, email)
        for key in keys:
            self._clean_expired(key, now)
            if key not in self._attempts:
                self._attempts[key] = []
            self._attempts[key].append(now)

    def record_success(self, request: Request, email: str) -> None:
        """Resets failed login tracking upon successful authentication."""
        keys = self._get_keys(request, email)
        for key in keys:
            self._attempts.pop(key, None)

    def reset(self, key: str = None) -> None:
        """Resets tracking for testing purposes."""
        if key:
            self._attempts.pop(key, None)
        else:
            self._attempts.clear()


login_rate_limiter = LoginRateLimiter(max_attempts=5, window_seconds=900)
auth_rate_limiter = login_rate_limiter

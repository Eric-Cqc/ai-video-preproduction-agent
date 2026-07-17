import hashlib
import hmac
import time
from dataclasses import dataclass, field
from threading import Lock

COOKIE_NAME = "pilot_access"
COOKIE_VERSION = "v1"


def password_matches(candidate: str, configured: str) -> bool:
    return hmac.compare_digest(candidate.encode(), configured.encode())


def issue_session(secret: str, *, ttl_seconds: int, now: int | None = None) -> str:
    expires_at = (now if now is not None else int(time.time())) + ttl_seconds
    payload = f"{COOKIE_VERSION}.{expires_at}"
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def session_is_valid(value: str | None, secret: str, *, now: int | None = None) -> bool:
    if value is None:
        return False
    parts = value.split(".")
    if len(parts) != 3:
        return False
    version, expires_at, signature = parts
    if version != COOKIE_VERSION:
        return False
    try:
        expiry = int(expires_at)
    except ValueError:
        return False
    if expiry < (now if now is not None else int(time.time())):
        return False
    payload = f"{version}.{expires_at}"
    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


@dataclass(slots=True)
class FailedAccessLimiter:
    max_attempts: int = 5
    window_seconds: int = 300
    _attempts: dict[str, list[float]] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def allowed(self, client_key: str, *, now: float | None = None) -> bool:
        current = now if now is not None else time.monotonic()
        with self._lock:
            attempts = [
                value
                for value in self._attempts.get(client_key, [])
                if value > current - self.window_seconds
            ]
            self._attempts[client_key] = attempts
            return len(attempts) < self.max_attempts

    def record_failure(self, client_key: str, *, now: float | None = None) -> None:
        current = now if now is not None else time.monotonic()
        with self._lock:
            attempts = [
                value
                for value in self._attempts.get(client_key, [])
                if value > current - self.window_seconds
            ]
            attempts.append(current)
            self._attempts[client_key] = attempts

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.config import get_settings
from app.core.security import decode_token


def user_or_ip(request: Request) -> str:
    """Per-user key for authenticated routes, falling back to client IP."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        claims = decode_token(auth[7:], "access")
        if claims:
            return f"user:{claims.user_id}"
    return get_remote_address(request)


limiter = Limiter(key_func=get_remote_address, enabled=get_settings().rate_limit_enabled)

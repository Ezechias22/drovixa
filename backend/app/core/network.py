from __future__ import annotations

from fastapi import Request

from app.core.config import get_settings


def forwarded_for(request: Request) -> str | None:
    if not get_settings().TRUST_PROXY_HEADERS:
        return None
    value = request.headers.get("X-Forwarded-For", "").split(",", maxsplit=1)[0].strip()
    return value[:64] or None


def client_ip(request: Request) -> str | None:
    forwarded = forwarded_for(request)
    direct = request.client.host[:64] if request.client else None
    return forwarded or direct

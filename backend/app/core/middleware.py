from __future__ import annotations

import logging
import re
import time
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings
from app.core.localization import reset_content_language, set_content_language
from app.core.observability import metrics

logger = logging.getLogger("drovixa.request")

STRICT_API_CSP = "default-src 'none'; frame-ancestors 'none'"
API_DOCS_CSP = "; ".join(
    (
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        ("style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com"),
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data: https://fastapi.tiangolo.com",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    )
)
API_DOC_PATHS = frozenset({"/docs", "/docs/oauth2-redirect", "/redoc"})
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        supplied_request_id = request.headers.get("X-Request-ID", "")
        request_id = (
            supplied_request_id if SAFE_REQUEST_ID.fullmatch(supplied_request_id) else str(uuid4())
        )
        request.state.request_id = request_id
        language_token = set_content_language(
            request.headers.get("X-Drovixa-Language")
            or request.headers.get("Accept-Language")
        )
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            reset_content_language(language_token)
            duration_seconds = time.perf_counter() - started
            duration_ms = round(duration_seconds * 1000, 2)
            if get_settings().METRICS_ENABLED and not request.url.path.endswith("/metrics"):
                metrics.record(request.method, request.url.path, status_code, duration_seconds)
            logger.info(
                "request_completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = (
            "cross-origin"
            if any(
                media_path in request.url.path
                for media_path in ("/media/content/", "/original-media/")
            )
            else "same-site"
        )
        response.headers["Content-Security-Policy"] = (
            API_DOCS_CSP if request.url.path in API_DOC_PATHS else STRICT_API_CSP
        )
        settings = get_settings()
        if settings.FORCE_HTTPS:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={settings.HSTS_MAX_AGE_SECONDS}; includeSubDomains; preload"
            )
        return response


class RequestSizeLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    @staticmethod
    def _response() -> JSONResponse:
        return JSONResponse(
            status_code=413,
            content={
                "success": False,
                "error": {
                    "code": "PAYLOAD_TOO_LARGE",
                    "message": "The request payload is too large.",
                },
                "meta": {},
            },
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        maximum = get_settings().MAX_REQUEST_BODY_BYTES
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                too_large = int(content_length) > maximum
            except ValueError:
                too_large = True
            if too_large:
                await self._response()(scope, receive, send)
                return

        body = bytearray()
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            body.extend(message.get("body", b""))
            if len(body) > maximum:
                await self._response()(scope, receive, send)
                return
            more_body = message.get("more_body", False)

        delivered = False

        async def replay_body() -> Message:
            nonlocal delivered
            if delivered:
                return {"type": "http.request", "body": b"", "more_body": False}
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay_body, send)

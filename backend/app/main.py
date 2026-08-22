from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import dispose_database
from app.core.exceptions import install_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import (
    RequestContextMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.observability import configure_observability
from app.core.redis import close_redis
from app.core.version import APP_VERSION, build_info
from app.schemas.common import success

settings = get_settings()
configure_logging(settings.LOG_LEVEL)
configure_observability(settings)
logger = logging.getLogger(__name__)


async def _poll_scheduled_notifications() -> None:
    from app.core.database import SessionFactory
    from app.services.notifications import dispatch_due_notification_campaigns

    while True:
        try:
            async with SessionFactory() as db:
                dispatched = await dispatch_due_notification_campaigns(db)
            if dispatched:
                logger.info("Dispatched %s scheduled notification campaign(s)", dispatched)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scheduled notification polling failed")
        await asyncio.sleep(settings.SCHEDULED_NOTIFICATION_POLL_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    polling_task: asyncio.Task[None] | None = None
    if settings.SCHEDULED_NOTIFICATION_POLLING_ENABLED:
        polling_task = asyncio.create_task(_poll_scheduled_notifications())
    try:
        yield
    finally:
        if polling_task is not None:
            polling_task.cancel()
            with suppress(asyncio.CancelledError):
                await polling_task
        await close_redis()
        await dispose_database()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Drovixa API",
        version=APP_VERSION,
        description="Streaming platform API",
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    # A trusted edge proxy terminates TLS and enforces redirects for production.
    # Keep internal service-to-service HTTP functional on the private network.
    if settings.FORCE_HTTPS and not settings.TRUST_PROXY_HEADERS:
        app.add_middleware(HTTPSRedirectMiddleware)
    if settings.TRUSTED_HOSTS:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.TRUSTED_HOSTS)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
    )
    install_exception_handlers(app)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get(settings.API_V1_PREFIX, include_in_schema=False)
    async def api_root() -> dict[str, Any]:
        return success({"app": settings.APP_NAME, "status": "ok", **build_info()})

    return app


app = create_app()

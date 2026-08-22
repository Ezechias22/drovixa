from __future__ import annotations

import hmac

from fastapi import APIRouter, Request
from starlette.responses import PlainTextResponse

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.observability import metrics

router = APIRouter(tags=["Operations"])


def _metrics_token(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return request.headers.get("X-Metrics-Token", "").strip()


@router.get("/metrics", include_in_schema=False, response_class=PlainTextResponse)
async def prometheus_metrics(request: Request) -> PlainTextResponse:
    settings = get_settings()
    if not settings.METRICS_ENABLED:
        raise AppError("NOT_FOUND", "Metrics are disabled.", status_code=404)
    if settings.METRICS_TOKEN:
        supplied = _metrics_token(request)
        if not supplied or not hmac.compare_digest(supplied, settings.METRICS_TOKEN):
            raise AppError("UNAUTHORIZED", "A metrics token is required.", status_code=401)
    return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4")

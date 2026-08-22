from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.api.deps import DbSession
from app.core.exceptions import AppError
from app.integrations.payments import get_payment_provider
from app.schemas.common import success
from app.services.monetization import process_payment_webhook

router = APIRouter(prefix="/webhooks/payments", tags=["Payment webhooks"])


@router.post("/{provider_name}")
async def payment_webhook(provider_name: str, request: Request, db: DbSession) -> dict[str, Any]:
    provider = get_payment_provider()
    if provider_name != provider.name or provider_name == "disabled":
        raise AppError("NOT_FOUND", "Payment provider not found.", status_code=404)
    body = await request.body()
    signature = request.headers.get("Stripe-Signature")
    event = provider.handle_webhook(body=body, signature=signature)
    row, duplicate = await process_payment_webhook(db, provider=provider, event=event)
    return success(
        {
            "event_id": row.provider_event_id,
            "status": row.status,
            "duplicate": duplicate,
        }
    )

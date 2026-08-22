from __future__ import annotations

import hashlib
import hmac
import json
import time
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import Settings
from app.core.exceptions import AppError
from app.integrations.payments.base import (
    CheckoutRequest,
    CheckoutResult,
    PaymentProvider,
    ProviderEvent,
    RefundResult,
)


class StripePaymentProvider(PaymentProvider):
    name = "stripe"

    def __init__(
        self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.settings = settings
        self.transport = transport

    def _secret_key(self) -> str:
        if not self.settings.STRIPE_SECRET_KEY:
            raise AppError(
                "PAYMENT_PROVIDER_UNAVAILABLE",
                "Stripe is not configured.",
                status_code=503,
            )
        return self.settings.STRIPE_SECRET_KEY

    async def _request(
        self,
        method: str,
        path: str,
        *,
        data: dict[str, Any] | None = None,
        content: bytes | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        if content is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        try:
            async with httpx.AsyncClient(
                auth=httpx.BasicAuth(self._secret_key(), ""),
                timeout=self.settings.PAYMENT_API_TIMEOUT_SECONDS,
                transport=self.transport,
            ) as client:
                response = await client.request(
                    method,
                    f"{self.settings.STRIPE_API_BASE_URL.rstrip('/')}{path}",
                    data=data,
                    content=content,
                    headers=headers,
                )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("invalid provider response")
            return payload
        except (httpx.HTTPError, ValueError) as exc:
            raise AppError(
                "PAYMENT_PROVIDER_ERROR",
                "The payment provider could not complete the request.",
                status_code=502,
            ) from exc

    @staticmethod
    def _minor_units(amount: Decimal) -> int:
        return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutResult:
        items: list[tuple[str, str]] = [
            ("mode", "subscription" if request.subscription else "payment"),
            ("customer_email", request.customer_email),
            ("success_url", request.success_url),
            ("cancel_url", request.cancel_url),
            ("client_reference_id", request.payment_id),
            ("metadata[payment_id]", request.payment_id),
            ("metadata[product_type]", request.product_type),
            ("line_items[0][quantity]", str(request.quantity)),
        ]
        for key, value in request.metadata.items():
            items.append((f"metadata[{key}]", value))
            if request.subscription:
                items.append((f"subscription_data[metadata][{key}]", value))
        if request.subscription:
            items.append(("subscription_data[metadata][payment_id]", request.payment_id))
        if request.provider_price_id:
            items.append(("line_items[0][price]", request.provider_price_id))
        else:
            items.extend(
                [
                    ("line_items[0][price_data][currency]", request.currency.lower()),
                    (
                        "line_items[0][price_data][unit_amount]",
                        str(self._minor_units(request.amount)),
                    ),
                    ("line_items[0][price_data][product_data][name]", request.product_name),
                ]
            )
            if request.subscription:
                plan_interval = request.metadata.get("interval", "monthly")
                stripe_interval = "year" if plan_interval == "annual" else "month"
                interval_count = "3" if plan_interval == "quarterly" else "1"
                items.extend(
                    [
                        ("line_items[0][price_data][recurring][interval]", stripe_interval),
                        (
                            "line_items[0][price_data][recurring][interval_count]",
                            interval_count,
                        ),
                    ]
                )
        body = await self._request(
            "POST",
            "/checkout/sessions",
            content=urlencode(items).encode(),
            idempotency_key=request.idempotency_key,
        )
        session_id, url = body.get("id"), body.get("url")
        if not isinstance(session_id, str) or not isinstance(url, str):
            raise AppError(
                "PAYMENT_PROVIDER_ERROR",
                "Stripe did not return a checkout URL.",
                status_code=502,
            )
        return CheckoutResult(session_id, url, str(body.get("status", "open")), body)

    async def verify_payment(self, provider_transaction_id: str) -> str:
        return await self.get_payment_status(provider_transaction_id)

    async def get_payment_status(self, provider_transaction_id: str) -> str:
        body = await self._request("GET", f"/checkout/sessions/{provider_transaction_id}")
        payment_status = str(body.get("payment_status", "unpaid"))
        return "paid" if payment_status == "paid" else "pending"

    async def refund_payment(
        self, provider_transaction_id: str, *, amount: Decimal | None = None
    ) -> RefundResult:
        data: dict[str, str] = {"payment_intent": provider_transaction_id}
        if amount is not None:
            data["amount"] = str(self._minor_units(amount))
        body = await self._request("POST", "/refunds", data=data)
        refund_id = body.get("id")
        if not isinstance(refund_id, str):
            raise AppError("PAYMENT_PROVIDER_ERROR", "Stripe refund failed.", status_code=502)
        return RefundResult(refund_id, str(body.get("status", "pending")), body)

    def handle_webhook(self, *, body: bytes, signature: str | None) -> ProviderEvent:
        secret = self.settings.STRIPE_WEBHOOK_SECRET
        if not secret or not signature:
            raise AppError(
                "WEBHOOK_SIGNATURE_INVALID", "Invalid webhook signature.", status_code=401
            )
        parts: dict[str, list[str]] = {}
        for item in signature.split(","):
            key, _, value = item.partition("=")
            parts.setdefault(key, []).append(value)
        try:
            timestamp = int(parts["t"][0])
        except (KeyError, ValueError, IndexError) as exc:
            raise AppError(
                "WEBHOOK_SIGNATURE_INVALID", "Invalid webhook signature.", status_code=401
            ) from exc
        if abs(int(time.time()) - timestamp) > self.settings.PAYMENT_WEBHOOK_TOLERANCE_SECONDS:
            raise AppError(
                "WEBHOOK_SIGNATURE_EXPIRED", "Webhook signature expired.", status_code=401
            )
        expected = hmac.new(
            secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256
        ).hexdigest()
        if not any(hmac.compare_digest(expected, candidate) for candidate in parts.get("v1", [])):
            raise AppError(
                "WEBHOOK_SIGNATURE_INVALID", "Invalid webhook signature.", status_code=401
            )
        try:
            event = json.loads(body)
        except json.JSONDecodeError as exc:
            raise AppError("WEBHOOK_INVALID", "Invalid webhook payload.", status_code=400) from exc
        event_id, event_type = event.get("id"), event.get("type")
        obj = event.get("data", {}).get("object", {})
        if (
            not isinstance(event_id, str)
            or not isinstance(event_type, str)
            or not isinstance(obj, dict)
        ):
            raise AppError("WEBHOOK_INVALID", "Invalid webhook payload.", status_code=400)
        raw_metadata = obj.get("metadata")
        metadata: dict[str, Any] = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
        raw_parent = obj.get("parent")
        parent: dict[str, Any] = raw_parent if isinstance(raw_parent, dict) else {}
        raw_subscription_details = parent.get("subscription_details")
        subscription_details: dict[str, Any] = (
            raw_subscription_details if isinstance(raw_subscription_details, dict) else {}
        )
        if not metadata and isinstance(subscription_details.get("metadata"), dict):
            metadata = dict(subscription_details["metadata"])
        raw_subscription_id = obj.get("subscription")
        if not raw_subscription_id and event_type.startswith("customer.subscription."):
            raw_subscription_id = obj.get("id")
        if not raw_subscription_id:
            raw_subscription_id = subscription_details.get("subscription")
        period_end = obj.get("current_period_end")
        raw_lines = obj.get("lines")
        lines: dict[str, Any] = raw_lines if isinstance(raw_lines, dict) else {}
        raw_line_data = lines.get("data")
        line_data: list[Any] = raw_line_data if isinstance(raw_line_data, list) else []
        if not period_end and line_data and isinstance(line_data[0], dict):
            period = line_data[0].get("period")
            if isinstance(period, dict):
                period_end = period.get("end")
        return ProviderEvent(
            event_id=event_id,
            event_type=event_type,
            provider_transaction_id=str(obj["id"]) if obj.get("id") else None,
            payment_id=str(metadata["payment_id"]) if metadata.get("payment_id") else None,
            status=str(obj.get("payment_status") or obj.get("status") or ""),
            subscription_id=str(raw_subscription_id) if raw_subscription_id else None,
            period_end=int(period_end) if period_end else None,
            raw=event,
        )

    async def cancel_subscription(self, provider_subscription_id: str) -> None:
        await self._request(
            "POST",
            f"/subscriptions/{provider_subscription_id}",
            data={"cancel_at_period_end": "true"},
        )

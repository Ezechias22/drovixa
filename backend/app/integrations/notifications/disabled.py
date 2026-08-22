from __future__ import annotations

from app.integrations.notifications.base import PushMessage, PushResult


class DisabledPushProvider:
    name = "disabled"
    enabled = False

    async def send(self, *, tokens: list[str], message: PushMessage) -> list[PushResult]:
        del message
        return [
            PushResult(
                success=False,
                error_code="PROVIDER_NOT_CONFIGURED",
                error_message="Firebase Cloud Messaging is not configured.",
            )
            for _ in tokens
        ]

from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

import firebase_admin
from firebase_admin import credentials, messaging

from app.integrations.notifications.base import PushMessage, PushResult


class FirebasePushProvider:
    name = "firebase"
    enabled = True

    def __init__(self, *, service_account_b64: str, project_id: str, dry_run: bool) -> None:
        self.dry_run = dry_run
        app_name = f"drovixa-{project_id}"
        try:
            self.app = firebase_admin.get_app(app_name)
        except ValueError:
            raw = base64.b64decode(service_account_b64, validate=True)
            service_account: dict[str, Any] = json.loads(raw.decode("utf-8"))
            credential = credentials.Certificate(service_account)
            self.app = firebase_admin.initialize_app(
                credential, {"projectId": project_id}, name=app_name
            )

    async def send(self, *, tokens: list[str], message: PushMessage) -> list[PushResult]:
        if len(tokens) > 500:
            raise ValueError("Firebase multicast batches cannot exceed 500 tokens")
        notification = messaging.Notification(
            title=message.title,
            body=message.body,
            image=message.image_url,
        )
        multicast = messaging.MulticastMessage(
            tokens=tokens,
            notification=notification,
            data=message.data,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    channel_id="drovixa_updates",
                    click_action="OPEN_DROVIXA",
                    image=message.image_url,
                ),
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(aps=messaging.Aps(sound="default")),
                fcm_options=messaging.APNSFCMOptions(image=message.image_url),
            ),
        )
        response = await asyncio.to_thread(
            messaging.send_each_for_multicast,
            multicast,
            dry_run=self.dry_run,
            app=self.app,
        )
        results: list[PushResult] = []
        for item in response.responses:
            if item.success:
                results.append(PushResult(success=True, message_id=item.message_id))
                continue
            error = item.exception
            error_code = getattr(error, "code", None) or (
                type(error).__name__ if error else "UNKNOWN_FIREBASE_ERROR"
            )
            results.append(
                PushResult(
                    success=False,
                    error_code=str(error_code),
                    error_message=str(error)[:1_000] if error else "Firebase rejected the message.",
                )
            )
        return results

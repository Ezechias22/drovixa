from __future__ import annotations

from app.core.config import Settings, get_settings
from app.integrations.notifications.base import PushProvider
from app.integrations.notifications.disabled import DisabledPushProvider


def get_push_provider(settings: Settings | None = None) -> PushProvider:
    current = settings or get_settings()
    if current.PUSH_PROVIDER != "firebase":
        return DisabledPushProvider()
    if not current.FIREBASE_PROJECT_ID or not current.FIREBASE_SERVICE_ACCOUNT_JSON_B64:
        return DisabledPushProvider()
    # Keep Firebase optional for local/test installations that deliberately use
    # PUSH_PROVIDER=disabled. Production images install firebase-admin and only
    # import it when the provider is actually selected.
    from app.integrations.notifications.firebase import FirebasePushProvider

    return FirebasePushProvider(
        service_account_b64=current.FIREBASE_SERVICE_ACCOUNT_JSON_B64,
        project_id=current.FIREBASE_PROJECT_ID,
        dry_run=current.FIREBASE_DRY_RUN,
    )

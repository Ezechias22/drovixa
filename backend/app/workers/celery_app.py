import asyncio

from celery import Celery

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery(
    "drovixa",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    beat_schedule={
        "dispatch-scheduled-notification-campaigns": {
            "task": "notifications.dispatch_scheduled",
            "schedule": 60.0,
        }
    },
)


@celery_app.task(name="system.ping")  # type: ignore[untyped-decorator]
def ping() -> str:
    return "pong"


async def _dispatch_scheduled() -> int:
    from app.core.database import SessionFactory, dispose_database
    from app.services.notifications import dispatch_due_notification_campaigns

    try:
        async with SessionFactory() as db:
            return await dispatch_due_notification_campaigns(db)
    finally:
        await dispose_database()


@celery_app.task(name="notifications.dispatch_scheduled")  # type: ignore[untyped-decorator]
def dispatch_scheduled_notifications() -> int:
    return asyncio.run(_dispatch_scheduled())


async def _deliver_campaign_push(campaign_id: str) -> dict[str, int]:
    from uuid import UUID

    from app.core.database import SessionFactory, dispose_database
    from app.services.notifications import deliver_campaign_push

    try:
        async with SessionFactory() as db:
            return await deliver_campaign_push(db, campaign_id=UUID(campaign_id))
    finally:
        await dispose_database()


@celery_app.task(name="notifications.deliver_campaign_push")  # type: ignore[untyped-decorator]
def deliver_campaign_push_task(campaign_id: str) -> dict[str, int]:
    return asyncio.run(_deliver_campaign_push(campaign_id))

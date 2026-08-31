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
        },
        "run-viewer-engagement-automations": {
            "task": "engagement.run",
            "schedule": 3600.0,
        },
    },
)


@celery_app.task(name="system.ping")  # type: ignore[untyped-decorator]
def ping() -> str:
    return "pong"


async def _dispatch_scheduled() -> int:
    from app.core.database import SessionFactory, dispose_database
    from app.services.administration import (
        dispatch_notification_campaign,
        scheduled_campaign_ids,
    )

    dispatched = 0
    try:
        async with SessionFactory() as db:
            campaign_ids = await scheduled_campaign_ids(db)
        for campaign_id in campaign_ids:
            async with SessionFactory() as db:
                campaign = await dispatch_notification_campaign(db, campaign_id=campaign_id)
                if campaign.status == "queued":
                    from app.services.notifications import deliver_campaign_push

                    await deliver_campaign_push(db, campaign_id=campaign_id)
                dispatched += 1
    finally:
        await dispose_database()
    return dispatched


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


async def _run_engagement() -> dict[str, int]:
    from app.core.database import SessionFactory, dispose_database
    from app.services.engagement import run_engagement_automations

    try:
        async with SessionFactory() as db:
            return await run_engagement_automations(db)
    finally:
        await dispose_database()


@celery_app.task(name="engagement.run")  # type: ignore[untyped-decorator]
def run_engagement_automations_task() -> dict[str, int]:
    return asyncio.run(_run_engagement())

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import distinct, exists, func, not_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError
from app.models.administration import (
    HomepageSection,
    HomepageSectionItem,
    NotificationCampaign,
)
from app.models.auth import Device
from app.models.base import utcnow
from app.models.community import Comment, Report
from app.models.content import Content, VideoAsset
from app.models.enums import (
    CommentStatus,
    ContentStatus,
    PaymentStatus,
    RefundStatus,
    ReportStatus,
    SubscriptionStatus,
    UserStatus,
    VideoStatus,
)
from app.models.experience import Notification, NotificationPreference
from app.models.monetization import Payment, Refund, Subscription
from app.models.streaming import PlaybackSession, WatchProgress
from app.models.user import User
from app.services.content import content_data
from app.services.notifications import create_campaign_deliveries


def homepage_section_data(row: HomepageSection, *, include_items: bool = True) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": row.id,
        "key": row.key,
        "title": row.title,
        "algorithm": row.algorithm,
        "presentation": row.presentation,
        "active": row.active,
        "sort_order": row.sort_order,
        "max_items": row.max_items,
        "genre_id": row.genre_id,
        "target_countries": row.target_countries,
        "target_languages": row.target_languages,
        "target_subscription": row.target_subscription,
        "starts_at": row.starts_at,
        "ends_at": row.ends_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
    if include_items:
        data["items"] = [
            {
                "id": item.id,
                "content_id": item.content_id,
                "sort_order": item.sort_order,
                "content": content_data(item.content, detailed=False),
            }
            for item in row.items
        ]
    return data


def campaign_data(row: NotificationCampaign) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "type": row.type,
        "title": row.title,
        "body": row.body,
        "image_url": row.image_url,
        "action_url": row.action_url,
        "audience": row.audience,
        "channels": row.channels,
        "status": row.status,
        "scheduled_at": row.scheduled_at,
        "sent_at": row.sent_at,
        "created_by_id": row.created_by_id,
        "recipient_count": row.recipient_count,
        "failure_count": row.failure_count,
        "metadata": row.campaign_metadata,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


async def dashboard_metrics(db: AsyncSession) -> dict[str, Any]:
    now = utcnow()
    thirty_days_ago = now - timedelta(days=30)
    thirty_days_ahead = now + timedelta(days=30)
    active_subscription_statuses = [SubscriptionStatus.TRIALING, SubscriptionStatus.ACTIVE]

    async def count(model: type[Any], *conditions: Any) -> int:
        return int(await db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0)

    gross_revenue = Decimal(
        await db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.status.in_(
                    [PaymentStatus.PAID, PaymentStatus.REFUNDED, PaymentStatus.PARTIALLY_REFUNDED]
                )
            )
        )
        or 0
    )
    refunds = Decimal(
        await db.scalar(
            select(func.coalesce(func.sum(Refund.amount), 0)).where(
                Refund.status == RefundStatus.SUCCEEDED
            )
        )
        or 0
    )
    cards = {
        "users_total": await count(User, User.deleted_at.is_(None)),
        "users_new_30d": await count(
            User, User.deleted_at.is_(None), User.created_at >= thirty_days_ago
        ),
        "active_subscriptions": await count(
            Subscription,
            Subscription.status.in_(active_subscription_statuses),
            Subscription.current_period_end > now,
        ),
        "published_content": await count(
            Content, Content.deleted_at.is_(None), Content.status == ContentStatus.PUBLISHED
        ),
        "gross_revenue": gross_revenue,
        "net_revenue": gross_revenue - refunds,
        "open_reports": await count(
            Report, Report.status.in_([ReportStatus.OPEN, ReportStatus.UNDER_REVIEW])
        ),
        "comments_under_review": await count(Comment, Comment.status == CommentStatus.UNDER_REVIEW),
    }
    warnings = {
        "licenses_expiring": await count(
            Content,
            Content.deleted_at.is_(None),
            Content.license_end.is_not(None),
            Content.license_end >= now,
            Content.license_end <= thirty_days_ahead,
        ),
        "scheduled_releases": await count(
            Content,
            Content.deleted_at.is_(None),
            Content.status == ContentStatus.SCHEDULED,
        ),
        "video_failures": await count(
            VideoAsset, VideoAsset.deleted_at.is_(None), VideoAsset.status == VideoStatus.FAILED
        ),
        "payment_errors": await count(Payment, Payment.status == PaymentStatus.FAILED),
        "reports_pending": cards["open_reports"],
    }

    user_rows = (
        await db.execute(
            select(User.created_at).where(
                User.deleted_at.is_(None), User.created_at >= now - timedelta(days=13)
            )
        )
    ).all()
    user_counts: dict[str, int] = defaultdict(int)
    for (created_at,) in user_rows:
        user_counts[created_at.date().isoformat()] += 1
    user_growth = []
    for days_ago in range(13, -1, -1):
        day = (now - timedelta(days=days_ago)).date().isoformat()
        user_growth.append({"date": day, "users": user_counts[day]})

    recent_payments = list(
        (await db.scalars(select(Payment).order_by(Payment.created_at.desc()).limit(6))).all()
    )
    return {
        "cards": cards,
        "warnings": warnings,
        "user_growth": user_growth,
        "recent_payments": [
            {
                "id": row.id,
                "amount": row.amount,
                "currency": row.currency,
                "status": row.status,
                "provider": row.provider,
                "created_at": row.created_at,
            }
            for row in recent_payments
        ],
    }


async def analytics_overview(db: AsyncSession, *, days: int) -> dict[str, Any]:
    now = utcnow()
    start = now - timedelta(days=days - 1)
    users = int(
        await db.scalar(
            select(func.count(distinct(PlaybackSession.user_id))).where(
                PlaybackSession.created_at >= start, PlaybackSession.user_id.is_not(None)
            )
        )
        or 0
    )
    sessions = int(
        await db.scalar(
            select(func.count(PlaybackSession.id)).where(PlaybackSession.created_at >= start)
        )
        or 0
    )
    watch_seconds = int(
        await db.scalar(
            select(func.coalesce(func.sum(WatchProgress.position_seconds), 0)).where(
                WatchProgress.last_watched_at >= start
            )
        )
        or 0
    )
    completed = int(
        await db.scalar(
            select(func.count(WatchProgress.id)).where(
                WatchProgress.last_watched_at >= start, WatchProgress.completed.is_(True)
            )
        )
        or 0
    )
    started = int(
        await db.scalar(
            select(func.count(WatchProgress.id)).where(WatchProgress.last_watched_at >= start)
        )
        or 0
    )
    payments = list(
        (
            await db.scalars(
                select(Payment).where(
                    Payment.created_at >= start,
                    Payment.status.in_(
                        [
                            PaymentStatus.PAID,
                            PaymentStatus.REFUNDED,
                            PaymentStatus.PARTIALLY_REFUNDED,
                        ]
                    ),
                )
            )
        ).all()
    )
    revenue_by_day: dict[str, Decimal] = defaultdict(Decimal)
    for payment in payments:
        revenue_by_day[payment.created_at.date().isoformat()] += payment.amount
    timeline = []
    for offset in range(days):
        day = (start + timedelta(days=offset)).date().isoformat()
        timeline.append({"date": day, "revenue": revenue_by_day[day]})
    return {
        "period_days": days,
        "unique_viewers": users,
        "playback_sessions": sessions,
        "watch_hours": round(watch_seconds / 3600, 2),
        "completion_rate": round((completed / started * 100) if started else 0, 2),
        "gross_revenue": sum((row.amount for row in payments), Decimal(0)),
        "timeline": timeline,
    }


async def content_analytics(db: AsyncSession, *, limit: int) -> list[dict[str, Any]]:
    progress = (
        select(
            WatchProgress.content_id.label("content_id"),
            func.count(distinct(WatchProgress.user_id)).label("unique_viewers"),
            func.avg(WatchProgress.percentage).label("average_completion"),
            func.avg(WatchProgress.position_seconds).label("average_watch_seconds"),
        )
        .group_by(WatchProgress.content_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(
                Content,
                func.coalesce(progress.c.unique_viewers, 0),
                func.coalesce(progress.c.average_completion, 0),
                func.coalesce(progress.c.average_watch_seconds, 0),
            )
            .outerjoin(progress, progress.c.content_id == Content.id)
            .where(Content.deleted_at.is_(None))
            .order_by(Content.view_count.desc(), Content.like_count.desc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "id": content.id,
            "title": content.title,
            "type": content.type,
            "views": content.view_count,
            "likes": content.like_count,
            "rating": content.rating,
            "unique_viewers": int(unique_viewers),
            "average_completion": round(float(average_completion), 2),
            "average_watch_seconds": round(float(average_watch_seconds), 2),
        }
        for content, unique_viewers, average_completion, average_watch_seconds in rows
    ]


async def _eligible_user_ids(
    db: AsyncSession, *, audience: dict[str, Any], campaign_type: str
) -> list[UUID]:
    segment = str(audience.get("segment", "all"))
    now = utcnow()
    statement = select(User.id).where(User.deleted_at.is_(None), User.status == UserStatus.ACTIVE)
    active_subscription = exists(
        select(Subscription.id).where(
            Subscription.user_id == User.id,
            Subscription.status.in_([SubscriptionStatus.TRIALING, SubscriptionStatus.ACTIVE]),
            Subscription.current_period_end > now,
        )
    )
    if segment == "premium":
        statement = statement.where(active_subscription)
    elif segment == "non_premium":
        statement = statement.where(not_(active_subscription))
    elif segment == "specific":
        statement = statement.where(User.id.in_(audience.get("user_ids", [])))
    elif segment == "country":
        statement = statement.where(User.country_code.in_(audience.get("country_codes", [])))
    elif segment == "language":
        statement = statement.where(User.language_code.in_(audience.get("language_codes", [])))
    elif segment == "inactive":
        cutoff = now - timedelta(days=int(audience.get("inactive_days", 30)))
        recently_seen = exists(
            select(Device.id).where(Device.user_id == User.id, Device.last_seen_at >= cutoff)
        )
        statement = statement.where(not_(recently_seen))

    preference_field = {
        "new_episode": NotificationPreference.new_episodes,
        "new_series": NotificationPreference.new_episodes,
        "new_movie": NotificationPreference.new_episodes,
        "promotion": NotificationPreference.promotions,
        "recommendation": NotificationPreference.recommendations,
        "wallet": NotificationPreference.wallet,
        "purchase": NotificationPreference.wallet,
        "subscription": NotificationPreference.wallet,
        "comment_reply": NotificationPreference.comments,
        "comment_like": NotificationPreference.comments,
    }.get(campaign_type)
    if preference_field is not None:
        opted_out = exists(
            select(NotificationPreference.user_id).where(
                NotificationPreference.user_id == User.id, preference_field.is_(False)
            )
        )
        statement = statement.where(not_(opted_out))
    return list(await db.scalars(statement.order_by(User.id)))


async def dispatch_notification_campaign(
    db: AsyncSession, *, campaign_id: UUID
) -> NotificationCampaign:
    campaign = await db.scalar(
        select(NotificationCampaign).where(NotificationCampaign.id == campaign_id).with_for_update()
    )
    if campaign is None:
        raise AppError("NOT_FOUND", "Notification campaign not found.", status_code=404)
    if campaign.status in {"queued", "processing", "sent", "partial", "failed"}:
        return campaign
    if campaign.status == "cancelled":
        raise AppError("CAMPAIGN_CANCELLED", "This campaign is cancelled.", status_code=409)
    campaign.status = "processing"
    await db.flush()
    user_ids = await _eligible_user_ids(db, audience=campaign.audience, campaign_type=campaign.type)
    if "in_app" in campaign.channels:
        db.add_all(
            [
                Notification(
                    user_id=user_id,
                    type=campaign.type,
                    title=campaign.title,
                    body=campaign.body,
                    image_url=campaign.image_url,
                    action_url=campaign.action_url,
                    payload={**campaign.campaign_metadata, "campaign_id": str(campaign.id)},
                )
                for user_id in user_ids
            ]
        )
    push_delivery_count = await create_campaign_deliveries(
        db, campaign=campaign, user_ids=user_ids
    )
    campaign.recipient_count = len(user_ids)
    campaign.failure_count = 0
    campaign.status = "queued" if push_delivery_count else "sent"
    campaign.sent_at = None if push_delivery_count else utcnow()
    metadata = campaign.campaign_metadata if isinstance(campaign.campaign_metadata, dict) else {}
    campaign.campaign_metadata = {
        **metadata,
        "delivery": {
            "in_app": "sent" if "in_app" in campaign.channels else "not_requested",
            "push": (
                {"status": "queued", "registered_tokens": push_delivery_count}
                if push_delivery_count
                else (
                    {"status": "no_registered_tokens", "registered_tokens": 0}
                    if "push" in campaign.channels
                    else "not_requested"
                )
            ),
            "email": "provider_not_configured" if "email" in campaign.channels else "not_requested",
        },
    }
    await db.commit()
    return campaign


async def scheduled_campaign_ids(db: AsyncSession) -> list[UUID]:
    return list(
        await db.scalars(
            select(NotificationCampaign.id).where(
                NotificationCampaign.status == "scheduled",
                NotificationCampaign.scheduled_at.is_not(None),
                NotificationCampaign.scheduled_at <= utcnow(),
            )
        )
    )


async def homepage_section(
    db: AsyncSession, section_id: UUID, *, for_update: bool = False
) -> HomepageSection:
    statement = (
        select(HomepageSection)
        .where(HomepageSection.id == section_id)
        .options(selectinload(HomepageSection.items).selectinload(HomepageSectionItem.content))
    )
    if for_update:
        statement = statement.with_for_update()
    row = await db.scalar(statement)
    if row is None:
        raise AppError("NOT_FOUND", "Homepage section not found.", status_code=404)
    return row


async def ensure_homepage_content(db: AsyncSession, content_id: UUID) -> Content:
    row = await db.scalar(
        select(Content).where(Content.id == content_id, Content.deleted_at.is_(None))
    )
    if row is None:
        raise AppError("NOT_FOUND", "Content not found.", status_code=404)
    return row

from __future__ import annotations

import base64
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs
from uuid import UUID

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.administration import NotificationCampaign
from app.models.base import utcnow
from app.models.configuration import FeatureFlag, RemoteConfig
from app.models.content import Content, Episode, Series
from app.models.enums import ContentType, UserStatus, WalletTransactionType
from app.models.experience import Notification, NotificationPreference
from app.models.growth import GrowthAutomation, RewardedAdSession
from app.models.streaming import WatchProgress
from app.models.user import User
from app.services.monetization import (
    _apply_wallet_change,
    get_or_create_wallet,
    has_active_subscription,
)
from app.services.notifications import send_user_push

DEFAULT_REWARDED_CONFIG = {"coins_per_ad": 10, "daily_limit": 5}
DEFAULT_PREMIUM_CONFIG = {
    "max_per_session": 2,
    "max_per_day": 3,
    "first_delay_seconds": 90,
    "repeat_delay_seconds": 480,
    "notification_cooldown_hours": 72,
    "continue_after_hours": 24,
    "continue_cooldown_hours": 48,
}

_public_keys: dict[str, ec.EllipticCurvePublicKey] = {}
_public_keys_loaded_at = 0.0


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _bounded_int(value: object, *, default: int, minimum: int, maximum: int) -> int:
    if not isinstance(value, (str, bytes, bytearray, int, float)):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


async def _flag_enabled(db: AsyncSession, key: str) -> bool:
    row = await db.scalar(select(FeatureFlag).where(FeatureFlag.key == key))
    return bool(row and row.enabled and row.rollout_percentage > 0)


async def _remote_dict(
    db: AsyncSession, key: str, defaults: dict[str, int]
) -> dict[str, int]:
    row = await db.scalar(select(RemoteConfig).where(RemoteConfig.key == key))
    value = row.value if row and isinstance(row.value, dict) else {}
    return {**defaults, **value}


async def _premium_user(db: AsyncSession, user_id: UUID) -> bool:
    user = await db.scalar(
        select(User).where(User.id == user_id).options(selectinload(User.roles))
    )
    return bool(
        user
        and (
            "premium_user" in user.role_names
            or await has_active_subscription(db, user_id=user_id)
        )
    )


def _ad_unit_id(platform: str) -> str | None:
    settings = get_settings()
    if platform == "android":
        return settings.ADMOB_ANDROID_REWARDED_AD_UNIT_ID
    if platform == "ios":
        return settings.ADMOB_IOS_REWARDED_AD_UNIT_ID
    return None


async def engagement_config(
    db: AsyncSession, *, user_id: UUID, platform: str
) -> dict[str, Any]:
    now = utcnow()
    day_start = datetime.combine(now.date(), datetime.min.time(), tzinfo=UTC)
    rewarded = await _remote_dict(db, "admob_rewarded", DEFAULT_REWARDED_CONFIG)
    offers = await _remote_dict(db, "premium_engagement", DEFAULT_PREMIUM_CONFIG)
    coins_per_ad = _bounded_int(
        rewarded.get("coins_per_ad"), default=10, minimum=1, maximum=100
    )
    daily_limit = _bounded_int(
        rewarded.get("daily_limit"), default=5, minimum=1, maximum=25
    )
    watched_today = int(
        await db.scalar(
            select(func.count(RewardedAdSession.id)).where(
                RewardedAdSession.user_id == user_id,
                RewardedAdSession.status == "credited",
                RewardedAdSession.credited_at >= day_start,
            )
        )
        or 0
    )
    premium = await _premium_user(db, user_id)
    ad_unit_id = _ad_unit_id(platform)
    rewarded_enabled = (
        not premium
        and bool(ad_unit_id)
        and await _flag_enabled(db, "rewarded_ads_enabled")
    )
    return {
        "premium": premium,
        "rewarded_ad": {
            "enabled": rewarded_enabled,
            "coins_per_ad": coins_per_ad,
            "daily_limit": daily_limit,
            "watched_today": watched_today,
            "remaining_today": max(0, daily_limit - watched_today),
            "configured": bool(ad_unit_id),
        },
        "premium_offer": {
            "enabled": not premium and await _flag_enabled(db, "premium_offers_enabled"),
            "max_per_session": _bounded_int(
                offers.get("max_per_session"), default=2, minimum=0, maximum=3
            ),
            "max_per_day": _bounded_int(
                offers.get("max_per_day"), default=3, minimum=0, maximum=5
            ),
            "first_delay_seconds": _bounded_int(
                offers.get("first_delay_seconds"), default=90, minimum=30, maximum=3600
            ),
            "repeat_delay_seconds": _bounded_int(
                offers.get("repeat_delay_seconds"), default=480, minimum=180, maximum=7200
            ),
        },
    }


def rewarded_session_data(row: RewardedAdSession) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "custom_data": row.session_token,
        "ad_unit_id": row.ad_unit_id,
        "reward_coins": row.reward_coins,
        "expires_at": row.expires_at,
        "status": row.status,
    }


async def create_rewarded_ad_session(
    db: AsyncSession, *, user_id: UUID, platform: str
) -> dict[str, Any]:
    config = await engagement_config(db, user_id=user_id, platform=platform)
    rewarded = config["rewarded_ad"]
    if config["premium"]:
        raise AppError("PREMIUM_HAS_NO_ADS", "Premium members do not receive ads.", status_code=409)
    if not rewarded["enabled"]:
        raise AppError("REWARDED_ADS_DISABLED", "Rewarded ads are not available.", status_code=503)
    if rewarded["remaining_today"] <= 0:
        raise AppError(
            "REWARDED_AD_DAILY_LIMIT",
            "You reached today's rewarded-ad limit.",
            status_code=409,
        )

    now = utcnow()
    existing = await db.scalar(
        select(RewardedAdSession)
        .where(
            RewardedAdSession.user_id == user_id,
            RewardedAdSession.platform == platform,
            RewardedAdSession.status == "pending",
            RewardedAdSession.expires_at > now,
        )
        .order_by(RewardedAdSession.created_at.desc())
    )
    if existing:
        return rewarded_session_data(existing)

    ad_unit_id = _ad_unit_id(platform)
    if not ad_unit_id:
        raise AppError("REWARDED_ADS_DISABLED", "Rewarded ads are not configured.", status_code=503)
    row = RewardedAdSession(
        user_id=user_id,
        session_token=secrets.token_urlsafe(48),
        platform=platform,
        ad_unit_id=ad_unit_id,
        reward_coins=int(rewarded["coins_per_ad"]),
        status="pending",
        expires_at=now + timedelta(minutes=30),
        verification_metadata={},
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return rewarded_session_data(row)


async def _admob_public_keys() -> dict[str, ec.EllipticCurvePublicKey]:
    global _public_keys_loaded_at
    settings = get_settings()
    if (
        _public_keys
        and time.monotonic() - _public_keys_loaded_at < settings.ADMOB_SSV_KEY_CACHE_SECONDS
    ):
        return _public_keys
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(settings.ADMOB_SSV_PUBLIC_KEYS_URL)
        response.raise_for_status()
    payload = response.json()
    loaded: dict[str, ec.EllipticCurvePublicKey] = {}
    for item in payload.get("keys", []):
        key_id = str(item.get("keyId", ""))
        pem = item.get("pem")
        if not key_id or not isinstance(pem, str):
            continue
        key = serialization.load_pem_public_key(pem.encode("utf-8"))
        if isinstance(key, ec.EllipticCurvePublicKey):
            loaded[key_id] = key
    if not loaded:
        raise AppError(
            "ADMOB_KEYS_UNAVAILABLE",
            "AdMob verification keys are unavailable.",
            status_code=503,
        )
    _public_keys.clear()
    _public_keys.update(loaded)
    _public_keys_loaded_at = time.monotonic()
    return _public_keys


async def verify_admob_signature(raw_query: str) -> dict[str, str]:
    marker = "&signature="
    if marker not in raw_query:
        raise AppError("ADMOB_SIGNATURE_INVALID", "AdMob signature is missing.", status_code=403)
    signed_query = raw_query.split(marker, 1)[0]
    parsed = parse_qs(raw_query, keep_blank_values=True)
    params = {key: values[-1] for key, values in parsed.items() if values}
    signature_value = params.get("signature")
    key_id = params.get("key_id")
    if not signature_value or not key_id:
        raise AppError("ADMOB_SIGNATURE_INVALID", "AdMob signature is incomplete.", status_code=403)
    signature_value += "=" * (-len(signature_value) % 4)
    try:
        signature = base64.urlsafe_b64decode(signature_value.encode("ascii"))
        public_key = (await _admob_public_keys())[key_id]
        public_key.verify(signature, signed_query.encode("ascii"), ec.ECDSA(hashes.SHA256()))
    except (ValueError, KeyError, InvalidSignature) as exc:
        raise AppError(
            "ADMOB_SIGNATURE_INVALID",
            "AdMob signature is invalid.",
            status_code=403,
        ) from exc
    return params


async def complete_rewarded_ad_from_ssv(
    db: AsyncSession, *, raw_query: str
) -> dict[str, Any]:
    params = await verify_admob_signature(raw_query)
    token = params.get("custom_data", "")
    transaction_id = params.get("transaction_id", "")
    callback_user_id = params.get("user_id", "")
    ad_unit = params.get("ad_unit", "")
    if not token or not transaction_id or not callback_user_id or not ad_unit:
        raise AppError("ADMOB_CALLBACK_INVALID", "AdMob callback is incomplete.", status_code=422)

    duplicate = await db.scalar(
        select(RewardedAdSession).where(
            RewardedAdSession.admob_transaction_id == transaction_id
        )
    )
    if duplicate:
        return {"recorded": True, "credited": duplicate.status == "credited", "duplicate": True}

    row = await db.scalar(
        select(RewardedAdSession)
        .where(RewardedAdSession.session_token == token)
        .with_for_update()
    )
    if row is None:
        raise AppError(
            "ADMOB_SESSION_INVALID",
            "Rewarded-ad session was not found.",
            status_code=403,
        )
    if str(row.user_id) != callback_user_id or row.ad_unit_id != ad_unit:
        raise AppError(
            "ADMOB_SESSION_INVALID",
            "Rewarded-ad session does not match.",
            status_code=403,
        )
    if _aware(row.expires_at) <= utcnow():
        row.status = "expired"
        await db.commit()
        raise AppError("ADMOB_SESSION_EXPIRED", "Rewarded-ad session expired.", status_code=410)
    if row.status == "credited":
        return {"recorded": True, "credited": True, "duplicate": True}

    config = await _remote_dict(db, "admob_rewarded", DEFAULT_REWARDED_CONFIG)
    daily_limit = _bounded_int(config.get("daily_limit"), default=5, minimum=1, maximum=25)
    now = utcnow()
    day_start = datetime.combine(now.date(), datetime.min.time(), tzinfo=UTC)
    await db.scalar(select(User.id).where(User.id == row.user_id).with_for_update())
    credited_today = int(
        await db.scalar(
            select(func.count(RewardedAdSession.id)).where(
                RewardedAdSession.user_id == row.user_id,
                RewardedAdSession.status == "credited",
                RewardedAdSession.credited_at >= day_start,
            )
        )
        or 0
    )
    row.admob_transaction_id = transaction_id
    row.verification_metadata = {
        "ad_network": params.get("ad_network"),
        "ad_unit": ad_unit,
        "reward_amount": params.get("reward_amount"),
        "reward_item": params.get("reward_item"),
        "timestamp": params.get("timestamp"),
    }
    if credited_today >= daily_limit:
        row.status = "daily_limit"
        await db.commit()
        return {"recorded": True, "credited": False, "daily_limit": True}

    wallet = await get_or_create_wallet(db, user_id=row.user_id, lock=True)
    ledger = _apply_wallet_change(
        wallet,
        regular_delta=0,
        bonus_delta=row.reward_coins,
        transaction_type=WalletTransactionType.PROMOTION,
        source="admob_rewarded",
        idempotency_key=f"admob:{transaction_id}",
        reference=transaction_id,
        metadata={"rewarded_ad_session_id": str(row.id), "ad_unit": ad_unit},
    )
    db.add(ledger)
    row.status = "credited"
    row.credited_at = now
    db.add(
        Notification(
            user_id=row.user_id,
            type="wallet",
            title=f"+{row.reward_coins} Drovixa coins",
            body="Your AdMob reward was verified and added to your wallet.",
            action_url="/coins",
            payload={"ledger_id": str(ledger.id), "source": "admob_rewarded"},
        )
    )
    await db.commit()
    return {"recorded": True, "credited": True, "reward_coins": row.reward_coins}


async def queue_publication_notification(
    db: AsyncSession, *, content_id: UUID | None = None, episode_id: UUID | None = None
) -> NotificationCampaign | None:
    if not await _flag_enabled(db, "content_notifications_enabled"):
        return None
    content: Content
    image_url: str | None
    if episode_id:
        episode = await db.scalar(
            select(Episode)
            .where(Episode.id == episode_id)
            .options(joinedload(Episode.series).joinedload(Series.content))
        )
        if episode is None:
            return None
        content = episode.series.content
        campaign_key = f"auto:new_episode:{episode.id}"
        campaign_type = "new_episode"
        title = f"New episode: {episode.title}"
        body = f"A new episode of {content.title} is ready to watch."
        action_url = f"/watch/{episode.id}?target=episode"
        image_url = episode.thumbnail_url or content.poster_url
    elif content_id:
        found_content = await db.get(Content, content_id)
        if found_content is None:
            return None
        content = found_content
        kind = "series" if content.type == ContentType.SERIES else "movie"
        campaign_key = f"auto:new_{kind}:{content.id}"
        campaign_type = f"new_{kind}"
        title = f"New on Drovixa: {content.title}"
        body = "Open Drovixa and start watching now."
        action_url = f"/{kind}/{content.slug}"
        image_url = content.poster_url
    else:
        return None

    existing = await db.scalar(
        select(NotificationCampaign).where(NotificationCampaign.name == campaign_key)
    )
    if existing:
        return existing
    campaign = NotificationCampaign(
        name=campaign_key,
        type=campaign_type,
        title=title,
        body=body,
        image_url=image_url,
        action_url=action_url,
        audience={"segment": "all"},
        channels=["in_app", "push"],
        status="scheduled",
        scheduled_at=utcnow(),
        campaign_metadata={
            "automatic": True,
            "content_id": str(content.id),
            **({"episode_id": str(episode_id)} if episode_id else {}),
        },
    )
    db.add(campaign)
    await db.flush()
    return campaign


def _automation_due(row: GrowthAutomation, now: datetime) -> bool:
    return bool(
        row.active
        and (
            row.last_triggered_at is None
            or _aware(row.last_triggered_at) <= now - timedelta(hours=row.cooldown_hours)
        )
    )


async def _queue_premium_offer_campaign(
    db: AsyncSession, automation: GrowthAutomation, now: datetime
) -> int:
    if not await _flag_enabled(db, "premium_offers_enabled"):
        return 0
    campaign = NotificationCampaign(
        name=f"auto:premium_offer:{now:%Y%m%d%H}",
        type="promotion",
        title="Unlock more with Drovixa Premium",
        body="Watch without ads and enjoy every Premium benefit.",
        action_url="/premium",
        audience={"segment": "non_premium"},
        channels=["in_app", "push"],
        status="scheduled",
        scheduled_at=now,
        campaign_metadata={"automatic": True, "source": "premium_offer"},
    )
    db.add(campaign)
    automation.last_triggered_at = now
    return 1


async def _continue_watching_reminders(
    db: AsyncSession, automation: GrowthAutomation, now: datetime
) -> int:
    if not await _flag_enabled(db, "continue_watching_reminders_enabled"):
        return 0
    config = await _remote_dict(db, "premium_engagement", DEFAULT_PREMIUM_CONFIG)
    after_hours = _bounded_int(
        config.get("continue_after_hours"), default=24, minimum=6, maximum=168
    )
    cooldown_hours = _bounded_int(
        config.get("continue_cooldown_hours"), default=48, minimum=12, maximum=336
    )
    oldest = now - timedelta(days=14)
    newest = now - timedelta(hours=after_hours)
    recent_cutoff = now - timedelta(hours=cooldown_hours)
    opted_out = set(
        await db.scalars(
            select(NotificationPreference.user_id).where(
                NotificationPreference.recommendations.is_(False)
            )
        )
    )
    recently_reminded = set(
        await db.scalars(
            select(Notification.user_id).where(
                Notification.type == "continue_watching",
                Notification.created_at >= recent_cutoff,
            )
        )
    )
    rows = list(
        (
            await db.scalars(
                select(WatchProgress)
                .join(User, User.id == WatchProgress.user_id)
                .where(
                    User.status == UserStatus.ACTIVE,
                    User.deleted_at.is_(None),
                    WatchProgress.completed.is_(False),
                    WatchProgress.removed_at.is_(None),
                    WatchProgress.position_seconds > 0,
                    WatchProgress.last_watched_at >= oldest,
                    WatchProgress.last_watched_at <= newest,
                )
                .options(
                    selectinload(WatchProgress.content),
                    selectinload(WatchProgress.episode),
                )
                .order_by(WatchProgress.user_id, WatchProgress.last_watched_at.desc())
                .limit(1000)
            )
        ).all()
    )
    latest: dict[UUID, WatchProgress] = {}
    for row in rows:
        latest.setdefault(row.user_id, row)
    movie_content_ids = [
        row.content_id for row in latest.values() if row.episode_id is None
    ]
    movie_ids = {content_id: content_id for content_id in movie_content_ids}
    pushes: list[dict[str, Any]] = []
    for user_id, progress in latest.items():
        if user_id in opted_out or user_id in recently_reminded:
            continue
        if progress.episode_id:
            action_url = f"/watch/{progress.episode_id}?target=episode"
        else:
            movie_id = movie_ids.get(progress.content_id)
            if movie_id is None:
                continue
            action_url = f"/watch/{movie_id}?target=movie"
        title = f"Continue watching {progress.content.title}"
        body = "Your place is saved. Tap to continue where you stopped."
        db.add(
            Notification(
                user_id=user_id,
                type="continue_watching",
                title=title,
                body=body,
                image_url=progress.content.poster_url,
                action_url=action_url,
                payload={"progress_id": str(progress.id)},
            )
        )
        pushes.append(
            {
                "user_id": user_id,
                "title": title,
                "body": body,
                "action_url": action_url,
                "image_url": progress.content.poster_url,
            }
        )
    automation.last_triggered_at = now
    await db.commit()
    for push in pushes:
        await send_user_push(
            db,
            user_id=push["user_id"],
            title=push["title"],
            body=push["body"],
            action_url=push["action_url"],
            notification_type="continue_watching",
            image_url=push["image_url"],
        )
    return len(pushes)


async def run_engagement_automations(db: AsyncSession) -> dict[str, int]:
    if not get_settings().ENGAGEMENT_AUTOMATION_ENABLED:
        return {"premium_campaigns": 0, "continue_reminders": 0}
    now = utcnow()
    rows = list(
        await db.scalars(
            select(GrowthAutomation)
            .where(
                GrowthAutomation.key.in_(
                    ["premium-offer-notification", "continue-watching-reminder"]
                )
            )
            .with_for_update()
        )
    )
    by_key = {row.key: row for row in rows}
    premium_campaigns = 0
    premium = by_key.get("premium-offer-notification")
    if premium and _automation_due(premium, now):
        premium_campaigns = await _queue_premium_offer_campaign(db, premium, now)
    reminders = 0
    continuation = by_key.get("continue-watching-reminder")
    if continuation and _automation_due(continuation, now):
        reminders = await _continue_watching_reminders(db, continuation, now)
    else:
        await db.commit()
    return {"premium_campaigns": premium_campaigns, "continue_reminders": reminders}

from __future__ import annotations

import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
import jwt
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext
from app.core.exceptions import AppError
from app.core.security import hash_password, normalize_email
from app.models.base import utcnow
from app.models.content import Content, Episode
from app.models.enums import ContentStatus, WalletTransactionType
from app.models.experience import Notification
from app.models.growth import (
    AdDelivery,
    AdEvent,
    AdPlacement,
    DailyRewardClaim,
    GrowthAutomation,
    GrowthEvent,
    Referral,
    ReferralCode,
    SocialIdentity,
    WatchParty,
    WatchPartyMember,
    WatchPartyMessage,
)
from app.models.user import User
from app.repositories.users import get_role_by_name, get_user_by_email, get_user_by_id
from app.schemas.auth import DeviceInput
from app.services.auth import IssuedTokens, _create_session_and_tokens
from app.services.monetization import _apply_wallet_change, get_or_create_wallet
from app.services.personalization import owned_profile

DAILY_REWARDS = (5, 5, 10, 10, 15, 20, 50)
INVITER_REWARD = 50
INVITEE_REWARD = 25


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _configured_ids(name: str) -> set[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return set()
    if raw.startswith("["):
        try:
            return {str(item).strip() for item in json.loads(raw) if str(item).strip()}
        except (ValueError, TypeError):
            return set()
    return {item.strip() for item in raw.split(",") if item.strip()}


def growth_config() -> dict[str, Any]:
    return {
        "google_login": bool(_configured_ids("GOOGLE_OAUTH_CLIENT_IDS")),
        "apple_login": bool(_configured_ids("APPLE_OAUTH_CLIENT_IDS")),
        "daily_rewards": list(DAILY_REWARDS),
        "referral": {"inviter_coins": INVITER_REWARD, "invitee_coins": INVITEE_REWARD},
        "watch_party_max_members": 25,
    }


async def verify_social_token(provider: str, token: str) -> dict[str, str]:
    if provider == "google":
        audiences = _configured_ids("GOOGLE_OAUTH_CLIENT_IDS")
        if not audiences:
            raise AppError(
                "SOCIAL_LOGIN_NOT_CONFIGURED",
                "Google login is not configured.",
                status_code=503,
            )
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://oauth2.googleapis.com/tokeninfo", params={"id_token": token}
                )
            response.raise_for_status()
            claims = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AppError(
                "INVALID_SOCIAL_TOKEN", "Google token is invalid.", status_code=401
            ) from exc
        if claims.get("aud") not in audiences or claims.get("email_verified") not in {
            "true",
            True,
        }:
            raise AppError("INVALID_SOCIAL_TOKEN", "Google token is invalid.", status_code=401)
        subject, email = claims.get("sub"), claims.get("email")
        name = claims.get("name")
    elif provider == "apple":
        audiences = _configured_ids("APPLE_OAUTH_CLIENT_IDS")
        if not audiences:
            raise AppError(
                "SOCIAL_LOGIN_NOT_CONFIGURED",
                "Apple login is not configured.",
                status_code=503,
            )
        try:
            header = jwt.get_unverified_header(token)
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get("https://appleid.apple.com/auth/keys")
            response.raise_for_status()
            keys = response.json().get("keys", [])
            jwk = next(item for item in keys if item.get("kid") == header.get("kid"))
            key = jwt.PyJWK.from_dict(jwk).key  # type: ignore[attr-defined]
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=list(audiences),
                issuer="https://appleid.apple.com",
            )
        except (httpx.HTTPError, ValueError, KeyError, StopIteration, jwt.PyJWTError) as exc:
            raise AppError(
                "INVALID_SOCIAL_TOKEN", "Apple token is invalid.", status_code=401
            ) from exc
        subject, email, name = claims.get("sub"), claims.get("email"), None
    else:
        raise AppError(
            "SOCIAL_PROVIDER_UNSUPPORTED",
            "Social provider is unsupported.",
            status_code=422,
        )
    if not isinstance(subject, str):
        raise AppError("INVALID_SOCIAL_TOKEN", "Social token is invalid.", status_code=401)
    return {
        "subject": subject,
        "email": normalize_email(email) if isinstance(email, str) else "",
        "name": str(name or "").strip(),
    }


async def social_login(
    db: AsyncSession,
    *,
    provider: str,
    claims: dict[str, str],
    display_name: str | None,
    device: DeviceInput,
    ip: str | None,
    user_agent: str | None,
) -> IssuedTokens:
    identity = await db.scalar(
        select(SocialIdentity).where(
            SocialIdentity.provider == provider,
            SocialIdentity.subject == claims["subject"],
        )
    )
    user = await get_user_by_id(db, identity.user_id) if identity else None
    if user is None:
        if not claims["email"]:
            raise AppError(
                "SOCIAL_EMAIL_REQUIRED",
                "The provider did not return an email for this first sign in.",
                status_code=422,
            )
        user = await get_user_by_email(db, claims["email"])
        if user is None:
            role = await get_role_by_name(db, "user")
            if role is None:
                raise AppError("SERVICE_MISCONFIGURED", "User role is missing.", status_code=500)
            user = User(
                email=claims["email"],
                name=(display_name or claims["name"] or claims["email"].split("@", 1)[0])[:120],
                password_hash=hash_password(secrets.token_urlsafe(48)),
                email_verified=True,
            )
            user.roles.append(role)
            db.add(user)
            await db.flush()
            await get_or_create_wallet(db, user_id=user.id)
        else:
            user.email_verified = True
        db.add(
            SocialIdentity(
                user_id=user.id,
                provider=provider,
                subject=claims["subject"],
                email=claims["email"],
            )
        )
        await db.flush()
    issued = await _create_session_and_tokens(db, user, device, ip=ip, user_agent=user_agent)
    await record_growth_event(db, user_id=user.id, event_name="social_login", metadata={})
    await db.commit()
    return issued


def ad_data(row: AdPlacement, delivery: AdDelivery) -> dict[str, Any]:
    return {
        "id": row.id,
        "delivery_id": delivery.id,
        "session_key": delivery.session_key,
        "format": row.format,
        "placement": row.placement,
        "headline": row.headline,
        "body": row.body,
        "media_url": row.media_url,
        "click_url": row.click_url,
        "sponsor": row.sponsor,
        "reward_coins": row.reward_coins,
        "expires_at": delivery.expires_at,
    }


async def next_ad(
    db: AsyncSession,
    *,
    placement: str,
    context: AuthContext | None,
    device_key: str,
    country: str | None,
    language: str | None,
) -> dict[str, Any] | None:
    now = utcnow()
    rows = list(
        (
            await db.scalars(
                select(AdPlacement)
                .where(
                    AdPlacement.active.is_(True),
                    AdPlacement.placement == placement,
                    (AdPlacement.starts_at.is_(None) | (AdPlacement.starts_at <= now)),
                    (AdPlacement.ends_at.is_(None) | (AdPlacement.ends_at > now)),
                )
                .order_by(AdPlacement.priority.desc(), AdPlacement.created_at)
            )
        ).all()
    )
    row = next(
        (
            item
            for item in rows
            if (not item.countries or (country and country.upper() in item.countries))
            and (not item.languages or (language and language.casefold() in item.languages))
        ),
        None,
    )
    if row is None:
        return None
    start = datetime.combine(now.date(), datetime.min.time(), tzinfo=UTC)
    cap_conditions = [AdDelivery.ad_id == row.id, AdDelivery.created_at >= start]
    if context:
        cap_conditions.append(AdDelivery.user_id == context.user.id)
    else:
        cap_conditions.append(AdDelivery.device_key == device_key)
    delivered = int(await db.scalar(select(func.count(AdDelivery.id)).where(*cap_conditions)) or 0)
    if delivered >= row.daily_cap:
        return None
    delivery = AdDelivery(
        ad_id=row.id,
        user_id=context.user.id if context else None,
        device_key=device_key[:180],
        session_key=secrets.token_urlsafe(40),
        expires_at=now + timedelta(minutes=30),
    )
    db.add(delivery)
    await db.commit()
    await db.refresh(delivery)
    return ad_data(row, delivery)


async def track_ad_event(
    db: AsyncSession,
    *,
    context: AuthContext | None,
    delivery_id: UUID,
    session_key: str,
    event_type: str,
) -> dict[str, Any]:
    delivery = await db.scalar(
        select(AdDelivery)
        .where(AdDelivery.id == delivery_id, AdDelivery.session_key == session_key)
        .with_for_update()
    )
    if delivery is None or _aware(delivery.expires_at) <= utcnow():
        raise AppError("AD_SESSION_INVALID", "Ad session is invalid or expired.", status_code=403)
    if delivery.user_id and (context is None or delivery.user_id != context.user.id):
        raise AppError(
            "AD_SESSION_INVALID",
            "Ad session does not belong to this user.",
            status_code=403,
        )
    existing = await db.scalar(
        select(AdEvent).where(AdEvent.delivery_id == delivery.id, AdEvent.event_type == event_type)
    )
    ad = await db.get(AdPlacement, delivery.ad_id)
    if ad is None:
        raise AppError("NOT_FOUND", "Ad no longer exists.", status_code=404)
    rewarded = False
    if existing is None:
        db.add(
            AdEvent(
                ad_id=ad.id,
                delivery_id=delivery.id,
                user_id=context.user.id if context else None,
                event_type=event_type,
            )
        )
        if event_type == "completed":
            delivery.completed_at = utcnow()
            if ad.reward_coins and context and delivery.rewarded_at is None:
                wallet = await get_or_create_wallet(db, user_id=context.user.id, lock=True)
                ledger = _apply_wallet_change(
                    wallet,
                    regular_delta=0,
                    bonus_delta=ad.reward_coins,
                    transaction_type=WalletTransactionType.PROMOTION,
                    source="rewarded_ad",
                    idempotency_key=f"ad:{delivery.id}",
                    reference=str(ad.id),
                    metadata={"delivery_id": str(delivery.id)},
                )
                db.add(ledger)
                delivery.rewarded_at = utcnow()
                rewarded = True
    await db.commit()
    return {"recorded": True, "rewarded": rewarded, "reward_coins": ad.reward_coins}


def reward_data(row: DailyRewardClaim | None, *, next_streak: int) -> dict[str, Any]:
    return {
        "claimed_today": row is not None,
        "claim": (
            {"date": row.claim_date, "streak_day": row.streak_day, "coins": row.coins}
            if row
            else None
        ),
        "next_streak_day": next_streak,
        "next_coins": DAILY_REWARDS[next_streak - 1],
        "calendar": list(DAILY_REWARDS),
    }


async def daily_reward_status(db: AsyncSession, *, user_id: UUID) -> dict[str, Any]:
    today = utcnow().date()
    latest = await db.scalar(
        select(DailyRewardClaim)
        .where(DailyRewardClaim.user_id == user_id)
        .order_by(DailyRewardClaim.claim_date.desc())
    )
    if latest and latest.claim_date == today:
        next_streak = min(latest.streak_day + 1, 7)
        return reward_data(latest, next_streak=next_streak)
    next_streak = (
        min(latest.streak_day + 1, 7)
        if latest and latest.claim_date == today - timedelta(days=1)
        else 1
    )
    return reward_data(None, next_streak=next_streak)


async def claim_daily_reward(db: AsyncSession, *, user_id: UUID) -> dict[str, Any]:
    today = utcnow().date()
    existing = await db.scalar(
        select(DailyRewardClaim).where(
            DailyRewardClaim.user_id == user_id, DailyRewardClaim.claim_date == today
        )
    )
    if existing:
        return await daily_reward_status(db, user_id=user_id)
    latest = await db.scalar(
        select(DailyRewardClaim)
        .where(DailyRewardClaim.user_id == user_id)
        .order_by(DailyRewardClaim.claim_date.desc())
    )
    streak = (
        min(latest.streak_day + 1, 7)
        if latest and latest.claim_date == today - timedelta(days=1)
        else 1
    )
    coins = DAILY_REWARDS[streak - 1]
    wallet = await get_or_create_wallet(db, user_id=user_id, lock=True)
    ledger = _apply_wallet_change(
        wallet,
        regular_delta=0,
        bonus_delta=coins,
        transaction_type=WalletTransactionType.DAILY_REWARD,
        source="daily_reward",
        idempotency_key=f"daily:{today.isoformat()}",
        reference=today.isoformat(),
        metadata={"streak_day": streak},
    )
    db.add(ledger)
    await db.flush()
    claim = DailyRewardClaim(
        user_id=user_id,
        claim_date=today,
        streak_day=streak,
        coins=coins,
        ledger_id=ledger.id,
    )
    db.add(claim)
    await record_growth_event(
        db, user_id=user_id, event_name="daily_reward_claimed", metadata={"streak": streak}
    )
    await db.commit()
    return await daily_reward_status(db, user_id=user_id)


async def _referral_code(db: AsyncSession, user_id: UUID) -> ReferralCode:
    row = await db.scalar(select(ReferralCode).where(ReferralCode.user_id == user_id))
    if row:
        return row
    for _ in range(5):
        code = f"DRV{secrets.token_hex(4).upper()}"
        if not await db.scalar(select(ReferralCode.id).where(ReferralCode.code == code)):
            row = ReferralCode(user_id=user_id, code=code)
            db.add(row)
            await db.flush()
            return row
    raise AppError("REFERRAL_CODE_FAILED", "Could not create a referral code.", status_code=500)


async def referral_summary(db: AsyncSession, *, user_id: UUID) -> dict[str, Any]:
    code = await _referral_code(db, user_id)
    invited = int(
        await db.scalar(select(func.count(Referral.id)).where(Referral.inviter_id == user_id)) or 0
    )
    earned = int(
        await db.scalar(
            select(func.coalesce(func.sum(Referral.inviter_reward), 0)).where(
                Referral.inviter_id == user_id, Referral.status == "qualified"
            )
        )
        or 0
    )
    applied = await db.scalar(select(Referral).where(Referral.invitee_id == user_id))
    await db.commit()
    return {
        "code": code.code,
        "share_url": f"https://drovixa-web-free.onrender.com/register?ref={code.code}",
        "invited": invited,
        "earned_coins": earned,
        "applied": applied is not None,
        "inviter_reward": INVITER_REWARD,
        "invitee_reward": INVITEE_REWARD,
    }


async def apply_referral(db: AsyncSession, *, user_id: UUID, raw_code: str) -> dict[str, Any]:
    if await db.scalar(select(Referral.id).where(Referral.invitee_id == user_id)):
        raise AppError(
            "REFERRAL_ALREADY_APPLIED", "A referral was already applied.", status_code=409
        )
    code = await db.scalar(
        select(ReferralCode).where(
            ReferralCode.code == raw_code.strip().upper(), ReferralCode.active.is_(True)
        )
    )
    if code is None:
        raise AppError("REFERRAL_CODE_INVALID", "Referral code is invalid.", status_code=404)
    if code.user_id == user_id:
        raise AppError(
            "REFERRAL_SELF_INVITE", "You cannot use your own referral code.", status_code=409
        )
    inviter_wallet = await get_or_create_wallet(db, user_id=code.user_id, lock=True)
    invitee_wallet = await get_or_create_wallet(db, user_id=user_id, lock=True)
    referral = Referral(
        inviter_id=code.user_id,
        invitee_id=user_id,
        code_id=code.id,
        inviter_reward=INVITER_REWARD,
        invitee_reward=INVITEE_REWARD,
        qualified_at=utcnow(),
    )
    db.add(referral)
    inviter_ledger = _apply_wallet_change(
        inviter_wallet,
        regular_delta=0,
        bonus_delta=INVITER_REWARD,
        transaction_type=WalletTransactionType.REFERRAL,
        source="referral_inviter",
        idempotency_key=f"referral:inviter:{user_id}",
        reference=str(user_id),
        metadata={"invitee_id": str(user_id)},
    )
    invitee_ledger = _apply_wallet_change(
        invitee_wallet,
        regular_delta=0,
        bonus_delta=INVITEE_REWARD,
        transaction_type=WalletTransactionType.REFERRAL,
        source="referral_invitee",
        idempotency_key=f"referral:invitee:{code.user_id}",
        reference=str(code.user_id),
        metadata={"inviter_id": str(code.user_id)},
    )
    db.add_all([inviter_ledger, invitee_ledger])
    await record_growth_event(db, user_id=user_id, event_name="referral_qualified", metadata={})
    await db.commit()
    return await referral_summary(db, user_id=user_id)


async def record_growth_event(
    db: AsyncSession, *, user_id: UUID | None, event_name: str, metadata: dict[str, Any]
) -> None:
    db.add(GrowthEvent(user_id=user_id, event_name=event_name, event_metadata=metadata))
    if user_id is None:
        return
    automations = list(
        (
            await db.scalars(
                select(GrowthAutomation).where(
                    GrowthAutomation.active.is_(True),
                    GrowthAutomation.trigger_event == event_name,
                )
            )
        ).all()
    )
    now = utcnow()
    for automation in automations:
        if automation.last_triggered_at and _aware(automation.last_triggered_at) > now - timedelta(
            hours=automation.cooldown_hours
        ):
            continue
        config = automation.action_config
        db.add(
            Notification(
                user_id=user_id,
                type="promotion",
                title=str(config.get("title", automation.name))[:160],
                body=str(config.get("body", "A new Drovixa reward is waiting for you."))[:2000],
                image_url=None,
                action_url=str(config.get("action_url", "/rewards"))[:1000],
                expires_at=now + timedelta(days=7),
            )
        )
        automation.last_triggered_at = now


def party_data(
    party: WatchParty,
    *,
    user_id: UUID,
    members: list[tuple[WatchPartyMember, str]],
    messages: list[tuple[WatchPartyMessage, str]],
) -> dict[str, Any]:
    return {
        "id": party.id,
        "invite_code": party.invite_code,
        "share_url": f"https://drovixa-web-free.onrender.com/watch-party/{party.invite_code}",
        "title": party.title,
        "content_id": party.content_id,
        "episode_id": party.episode_id,
        "host_id": party.host_id,
        "is_host": party.host_id == user_id,
        "status": party.status,
        "position_seconds": party.position_seconds,
        "paused": party.paused,
        "max_members": party.max_members,
        "last_heartbeat_at": party.last_heartbeat_at,
        "members": [
            {"user_id": member.user_id, "name": name, "role": member.role, "status": member.status}
            for member, name in members
        ],
        "messages": [
            {
                "id": message.id,
                "user_id": message.user_id,
                "name": name,
                "message": message.message,
                "created_at": message.created_at,
            }
            for message, name in messages
        ],
    }


async def create_watch_party(
    db: AsyncSession,
    *,
    context: AuthContext,
    content_id: UUID,
    episode_id: UUID | None,
    profile_id: UUID | None,
    title: str,
    max_members: int,
) -> WatchParty:
    content = await db.get(Content, content_id)
    if content is None or content.status != ContentStatus.PUBLISHED:
        raise AppError("NOT_FOUND", "Published title not found.", status_code=404)
    if episode_id:
        episode = await db.get(Episode, episode_id)
        if episode is None or episode.series_id != content_id:
            raise AppError("NOT_FOUND", "Episode not found for this title.", status_code=404)
    profile = await owned_profile(db, context=context, profile_id=profile_id)
    for _ in range(5):
        invite_code = secrets.token_hex(4).upper()
        if not await db.scalar(select(WatchParty.id).where(WatchParty.invite_code == invite_code)):
            break
    party = WatchParty(
        host_id=context.user.id,
        content_id=content_id,
        episode_id=episode_id,
        invite_code=invite_code,
        title=title.strip(),
        max_members=max_members,
        last_heartbeat_at=utcnow(),
    )
    db.add(party)
    await db.flush()
    db.add(
        WatchPartyMember(
            party_id=party.id,
            user_id=context.user.id,
            profile_id=profile.id,
            role="host",
            last_seen_at=utcnow(),
        )
    )
    await record_growth_event(
        db, user_id=context.user.id, event_name="watch_party_created", metadata={}
    )
    await db.commit()
    await db.refresh(party)
    return party


async def join_watch_party(
    db: AsyncSession, *, context: AuthContext, code: str, profile_id: UUID | None
) -> WatchParty:
    party = await db.scalar(
        select(WatchParty).where(WatchParty.invite_code == code.upper()).with_for_update()
    )
    if party is None or party.status == "ended":
        raise AppError("WATCH_PARTY_NOT_FOUND", "Watch Party is unavailable.", status_code=404)
    profile = await owned_profile(db, context=context, profile_id=profile_id)
    member = await db.scalar(
        select(WatchPartyMember).where(
            WatchPartyMember.party_id == party.id,
            WatchPartyMember.user_id == context.user.id,
        )
    )
    if member is None:
        count = int(
            await db.scalar(
                select(func.count(WatchPartyMember.id)).where(
                    WatchPartyMember.party_id == party.id,
                    WatchPartyMember.status == "active",
                )
            )
            or 0
        )
        if count >= party.max_members:
            raise AppError("WATCH_PARTY_FULL", "Watch Party is full.", status_code=409)
        db.add(
            WatchPartyMember(
                party_id=party.id,
                user_id=context.user.id,
                profile_id=profile.id,
                role="guest",
                last_seen_at=utcnow(),
            )
        )
    else:
        member.status = "active"
        member.profile_id = profile.id
        member.last_seen_at = utcnow()
    await db.commit()
    return party


async def watch_party_state(db: AsyncSession, *, context: AuthContext, code: str) -> dict[str, Any]:
    party = await db.scalar(select(WatchParty).where(WatchParty.invite_code == code.upper()))
    if party is None:
        raise AppError("WATCH_PARTY_NOT_FOUND", "Watch Party is unavailable.", status_code=404)
    member = await db.scalar(
        select(WatchPartyMember).where(
            WatchPartyMember.party_id == party.id,
            WatchPartyMember.user_id == context.user.id,
            WatchPartyMember.status == "active",
        )
    )
    if member is None:
        raise AppError(
            "WATCH_PARTY_MEMBERSHIP_REQUIRED",
            "Join this Watch Party first.",
            status_code=403,
        )
    member.last_seen_at = utcnow()
    member_rows = (
        await db.execute(
            select(WatchPartyMember, User.name)
            .join(User, User.id == WatchPartyMember.user_id)
            .where(
                WatchPartyMember.party_id == party.id,
                WatchPartyMember.status == "active",
            )
            .order_by(WatchPartyMember.created_at)
        )
    ).all()
    members = [(row[0], row[1]) for row in member_rows]
    message_rows = (
        await db.execute(
            select(WatchPartyMessage, User.name)
            .join(User, User.id == WatchPartyMessage.user_id)
            .where(WatchPartyMessage.party_id == party.id)
            .order_by(WatchPartyMessage.created_at.desc())
            .limit(50)
        )
    ).all()
    messages = [(row[0], row[1]) for row in message_rows]
    await db.commit()
    return party_data(
        party, user_id=context.user.id, members=members, messages=list(reversed(messages))
    )


async def update_watch_party(
    db: AsyncSession,
    *,
    context: AuthContext,
    code: str,
    position_seconds: int,
    paused: bool,
    status: str,
) -> dict[str, Any]:
    party = await db.scalar(
        select(WatchParty).where(WatchParty.invite_code == code.upper()).with_for_update()
    )
    if party is None:
        raise AppError("WATCH_PARTY_NOT_FOUND", "Watch Party is unavailable.", status_code=404)
    if party.host_id != context.user.id:
        raise AppError(
            "WATCH_PARTY_HOST_REQUIRED",
            "Only the host controls playback.",
            status_code=403,
        )
    party.position_seconds = position_seconds
    party.paused = paused
    party.status = status
    party.last_heartbeat_at = utcnow()
    if status == "ended":
        party.ended_at = utcnow()
    await db.commit()
    return await watch_party_state(db, context=context, code=code)


async def send_watch_party_message(
    db: AsyncSession, *, context: AuthContext, code: str, message: str
) -> dict[str, Any]:
    party = await db.scalar(select(WatchParty).where(WatchParty.invite_code == code.upper()))
    if party is None or party.status == "ended":
        raise AppError("WATCH_PARTY_NOT_FOUND", "Watch Party is unavailable.", status_code=404)
    member = await db.scalar(
        select(WatchPartyMember.id).where(
            WatchPartyMember.party_id == party.id,
            WatchPartyMember.user_id == context.user.id,
            WatchPartyMember.status == "active",
        )
    )
    if member is None:
        raise AppError(
            "WATCH_PARTY_MEMBERSHIP_REQUIRED",
            "Join this Watch Party first.",
            status_code=403,
        )
    row = WatchPartyMessage(party_id=party.id, user_id=context.user.id, message=message.strip())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"id": row.id, "message": row.message, "created_at": row.created_at}


async def safe_apply_referral(db: AsyncSession, *, user_id: UUID, raw_code: str) -> dict[str, Any]:
    try:
        return await apply_referral(db, user_id=user_id, raw_code=raw_code)
    except IntegrityError as exc:
        await db.rollback()
        raise AppError(
            "REFERRAL_ALREADY_APPLIED", "A referral was already applied.", status_code=409
        ) from exc

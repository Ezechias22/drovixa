from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import PlainTextResponse

from app.api.deps import CurrentContext, DbSession, OptionalContext, require_feature_enabled
from app.core.network import forwarded_for
from app.core.rate_limit import rate_limit
from app.schemas.common import success
from app.schemas.growth import (
    AdEventInput,
    GrowthEventInput,
    ReferralApplyInput,
    RewardedAdSessionInput,
    SocialLoginInput,
    WatchPartyCreateInput,
    WatchPartyJoinInput,
    WatchPartyMessageInput,
    WatchPartyStateInput,
)
from app.schemas.user import UserOut
from app.services.engagement import (
    complete_rewarded_ad_from_ssv,
    create_rewarded_ad_session,
    engagement_config,
)
from app.services.growth import (
    claim_daily_reward,
    create_watch_party,
    daily_reward_status,
    growth_config,
    join_watch_party,
    next_ad,
    record_growth_event,
    referral_summary,
    safe_apply_referral,
    send_watch_party_message,
    social_login,
    track_ad_event,
    update_watch_party,
    verify_social_token,
    watch_party_state,
)

router = APIRouter(tags=["Growth"])


@router.get("/growth/config")
async def public_growth_config() -> dict[str, Any]:
    return success(growth_config())


@router.get("/engagement/config")
async def viewer_engagement_config(
    context: CurrentContext,
    db: DbSession,
    platform: str = Query(default="android", pattern="^(android|ios)$"),
) -> dict[str, Any]:
    return success(
        await engagement_config(db, user_id=context.user.id, platform=platform)
    )


@router.post(
    "/rewards/ads/session",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("rewarded-ad-session", requests=20, window_seconds=3600))],
)
async def rewarded_ad_session(
    payload: RewardedAdSessionInput, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    return success(
        await create_rewarded_ad_session(
            db,
            user_id=context.user.id,
            platform=payload.platform,
        )
    )


@router.get("/webhooks/admob/reward", response_class=PlainTextResponse)
async def admob_reward_callback(request: Request, db: DbSession) -> PlainTextResponse:
    raw_query = request.scope.get("query_string", b"").decode("ascii")
    await complete_rewarded_ad_from_ssv(db, raw_query=raw_query)
    return PlainTextResponse("ok")


@router.get(
    "/ads/next",
    dependencies=[require_feature_enabled("ads_enabled", error_code="ADS_DISABLED")],
)
async def ad_next(
    db: DbSession,
    context: OptionalContext,
    placement: str = Query(default="home_feed", min_length=2, max_length=80),
    device_key: str = Header(default="anonymous", alias="X-Drovixa-Device-ID"),
    country: str | None = Header(default=None, alias="X-Drovixa-Country"),
    language: str | None = Header(default=None, alias="X-Drovixa-Language"),
) -> dict[str, Any]:
    row = await next_ad(
        db,
        placement=placement,
        context=context,
        device_key=device_key,
        country=country,
        language=language,
    )
    return success(row)


@router.post(
    "/ads/events",
    dependencies=[require_feature_enabled("ads_enabled", error_code="ADS_DISABLED")],
)
async def ad_event(
    payload: AdEventInput, db: DbSession, context: OptionalContext
) -> dict[str, Any]:
    return success(
        await track_ad_event(
            db,
            context=context,
            delivery_id=payload.delivery_id,
            session_key=payload.session_key,
            event_type=payload.event_type,
        )
    )


@router.get(
    "/rewards/daily",
    dependencies=[
        require_feature_enabled("daily_rewards_enabled", error_code="DAILY_REWARDS_DISABLED")
    ],
)
async def reward_status(context: CurrentContext, db: DbSession) -> dict[str, Any]:
    return success(await daily_reward_status(db, user_id=context.user.id))


@router.post(
    "/rewards/daily/claim",
    dependencies=[
        require_feature_enabled("daily_rewards_enabled", error_code="DAILY_REWARDS_DISABLED"),
        Depends(rate_limit("daily-reward", requests=10, window_seconds=3600)),
    ],
)
async def reward_claim(context: CurrentContext, db: DbSession) -> dict[str, Any]:
    return success(await claim_daily_reward(db, user_id=context.user.id))


@router.get(
    "/referrals/me",
    dependencies=[require_feature_enabled("referrals_enabled", error_code="REFERRALS_DISABLED")],
)
async def referrals_me(context: CurrentContext, db: DbSession) -> dict[str, Any]:
    return success(await referral_summary(db, user_id=context.user.id))


@router.post(
    "/referrals/apply",
    dependencies=[
        require_feature_enabled("referrals_enabled", error_code="REFERRALS_DISABLED"),
        Depends(rate_limit("referral-apply", requests=10, window_seconds=3600)),
    ],
)
async def referrals_apply(
    payload: ReferralApplyInput, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    return success(await safe_apply_referral(db, user_id=context.user.id, raw_code=payload.code))


@router.post(
    "/auth/social",
    dependencies=[
        require_feature_enabled("social_login_enabled", error_code="SOCIAL_LOGIN_DISABLED"),
        Depends(rate_limit("social-login", requests=20, window_seconds=900)),
    ],
)
async def auth_social(payload: SocialLoginInput, request: Request, db: DbSession) -> dict[str, Any]:
    claims = await verify_social_token(payload.provider, payload.id_token)
    issued = await social_login(
        db,
        provider=payload.provider,
        claims=claims,
        display_name=payload.display_name,
        device=payload.device,
        ip=forwarded_for(request) or (request.client.host if request.client else None),
        user_agent=request.headers.get("User-Agent"),
    )
    return success(
        {
            "access_token": issued.access_token,
            "refresh_token": issued.refresh_token,
            "token_type": "bearer",
            "expires_in": issued.expires_in,
            "user": UserOut.from_user(issued.user),
        }
    )


@router.post(
    "/watch-parties",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        require_feature_enabled("watch_party_enabled", error_code="WATCH_PARTY_DISABLED")
    ],
)
async def party_create(
    payload: WatchPartyCreateInput, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    party = await create_watch_party(
        db,
        context=context,
        content_id=payload.content_id,
        episode_id=payload.episode_id,
        profile_id=payload.profile_id,
        title=payload.title,
        max_members=payload.max_members,
    )
    return success(await watch_party_state(db, context=context, code=party.invite_code))


@router.post(
    "/watch-parties/{code}/join",
    dependencies=[
        require_feature_enabled("watch_party_enabled", error_code="WATCH_PARTY_DISABLED")
    ],
)
async def party_join(
    code: str, payload: WatchPartyJoinInput, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    await join_watch_party(db, context=context, code=code, profile_id=payload.profile_id)
    return success(await watch_party_state(db, context=context, code=code))


@router.get(
    "/watch-parties/{code}",
    dependencies=[
        require_feature_enabled("watch_party_enabled", error_code="WATCH_PARTY_DISABLED")
    ],
)
async def party_get(code: str, context: CurrentContext, db: DbSession) -> dict[str, Any]:
    return success(await watch_party_state(db, context=context, code=code))


@router.patch(
    "/watch-parties/{code}/state",
    dependencies=[
        require_feature_enabled("watch_party_enabled", error_code="WATCH_PARTY_DISABLED")
    ],
)
async def party_update(
    code: str, payload: WatchPartyStateInput, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    return success(
        await update_watch_party(
            db,
            context=context,
            code=code,
            position_seconds=payload.position_seconds,
            paused=payload.paused,
            status=payload.status,
        )
    )


@router.post(
    "/watch-parties/{code}/messages",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        require_feature_enabled("watch_party_enabled", error_code="WATCH_PARTY_DISABLED")
    ],
)
async def party_message(
    code: str, payload: WatchPartyMessageInput, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    return success(
        await send_watch_party_message(db, context=context, code=code, message=payload.message)
    )


@router.post("/growth/events", status_code=status.HTTP_202_ACCEPTED)
async def growth_event(
    payload: GrowthEventInput, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    await record_growth_event(
        db,
        user_id=context.user.id,
        event_name=payload.event_name,
        metadata=dict(payload.metadata),
    )
    await db.commit()
    return success({"accepted": True})

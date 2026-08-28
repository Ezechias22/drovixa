from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import DbSession, require_permission
from app.models.personalization import CastSession, ContentRating, DownloadLicense, ViewerProfile
from app.models.user import User
from app.schemas.common import success

router = APIRouter(prefix="/admin/experience", tags=["Admin personalization"])
AnalyticsViewer = Annotated[User, require_permission("analytics.view")]


@router.get("/summary")
async def phase10_summary(_: AnalyticsViewer, db: DbSession) -> dict[str, Any]:
    profiles = int(await db.scalar(select(func.count(ViewerProfile.id))) or 0)
    kids = int(
        await db.scalar(
            select(func.count(ViewerProfile.id)).where(
                ViewerProfile.is_kids.is_(True), ViewerProfile.active.is_(True)
            )
        )
        or 0
    )
    ratings = int(await db.scalar(select(func.count(ContentRating.id))) or 0)
    average_score = float(await db.scalar(select(func.avg(ContentRating.score))) or 0)
    download_rows = (
        await db.execute(
            select(DownloadLicense.status, func.count(DownloadLicense.id)).group_by(
                DownloadLicense.status
            )
        )
    ).all()
    downloads: dict[str, int] = {status: int(count) for status, count in download_rows}
    cast_rows = (
        await db.execute(
            select(CastSession.status, func.count(CastSession.id)).group_by(CastSession.status)
        )
    ).all()
    cast_sessions: dict[str, int] = {status: int(count) for status, count in cast_rows}
    return success(
        {
            "profiles": profiles,
            "kids_profiles": kids,
            "ratings": ratings,
            "average_score": round(average_score, 2),
            "downloads": downloads,
            "cast_sessions": cast_sessions,
        }
    )

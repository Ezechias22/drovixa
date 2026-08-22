from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentContext, DbSession, OptionalContext, require_feature_enabled
from app.core.rate_limit import rate_limit
from app.models.community import Like
from app.models.enums import CommentTargetType, LikeTargetType, ReportTargetType
from app.schemas.common import success
from app.schemas.community import (
    CommentCreate,
    CommentReportInput,
    CommentUpdate,
    LikeInput,
    ReportCreate,
)
from app.services.community import (
    add_comment_like,
    add_like,
    create_comment,
    create_report,
    delete_own_comment,
    list_comments,
    list_replies,
    remove_comment_like,
    remove_like,
    report_data,
    report_reason_data,
    update_own_comment,
    validate_like_target,
)

router = APIRouter(tags=["Community"])
Page = Annotated[int, Query(ge=1)]
Limit = Annotated[int, Query(ge=1, le=100)]
COMMENTS_ENABLED = require_feature_enabled("comments_enabled", error_code="COMMENTS_DISABLED")


def _meta(page: int, limit: int, total: int) -> dict[str, int]:
    return {"page": page, "limit": limit, "total": total, "pages": (total + limit - 1) // limit}


@router.get("/likes")
async def like_status(
    target_type: LikeTargetType,
    target_id: UUID,
    context: OptionalContext,
    db: DbSession,
) -> dict[str, Any]:
    await validate_like_target(db, target_type, target_id)
    count = int(
        await db.scalar(
            select(func.count(Like.id)).where(
                Like.target_type == target_type, Like.target_id == target_id
            )
        )
        or 0
    )
    liked = bool(
        context
        and await db.scalar(
            select(Like.id).where(
                Like.user_id == context.user.id,
                Like.target_type == target_type,
                Like.target_id == target_id,
            )
        )
    )
    return success(
        {"target_type": target_type, "target_id": target_id, "liked": liked, "count": count}
    )


@router.post("/likes", status_code=status.HTTP_201_CREATED)
async def create_like(payload: LikeInput, context: CurrentContext, db: DbSession) -> dict[str, Any]:
    row, count, created = await add_like(db, user_id=context.user.id, payload=payload)
    return success(
        {
            "id": row.id,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "liked": True,
            "count": count,
            "created": created,
        }
    )


@router.delete("/likes")
async def delete_like(payload: LikeInput, context: CurrentContext, db: DbSession) -> dict[str, Any]:
    count = await remove_like(db, user_id=context.user.id, payload=payload)
    return success(
        {
            "target_type": payload.target_type,
            "target_id": payload.target_id,
            "liked": False,
            "count": count,
        }
    )


@router.get("/comments", dependencies=[COMMENTS_ENABLED])
async def comments(
    target_type: CommentTargetType,
    target_id: UUID,
    context: OptionalContext,
    db: DbSession,
    page: Page = 1,
    limit: Limit = 20,
    sort: str = Query(default="newest", pattern="^(newest|oldest|popular)$"),
) -> dict[str, Any]:
    rows, total = await list_comments(
        db,
        context=context,
        target_type=target_type,
        target_id=target_id,
        page=page,
        limit=limit,
        sort=sort,
    )
    return success(rows, meta=_meta(page, limit, total))


@router.get("/comments/{comment_id}/replies", dependencies=[COMMENTS_ENABLED])
async def comment_replies(
    comment_id: UUID,
    context: OptionalContext,
    db: DbSession,
    page: Page = 1,
    limit: Limit = 20,
) -> dict[str, Any]:
    rows, total = await list_replies(
        db, context=context, comment_id=comment_id, page=page, limit=limit
    )
    return success(rows, meta=_meta(page, limit, total))


@router.post(
    "/comments",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        COMMENTS_ENABLED,
        Depends(rate_limit("comments", requests=20, window_seconds=60)),
    ],
)
async def post_comment(
    payload: CommentCreate, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    return success(await create_comment(db, context=context, payload=payload))


@router.patch("/comments/{comment_id}", dependencies=[COMMENTS_ENABLED])
async def patch_comment(
    comment_id: UUID,
    payload: CommentUpdate,
    context: CurrentContext,
    db: DbSession,
) -> dict[str, Any]:
    return success(
        await update_own_comment(db, context=context, comment_id=comment_id, payload=payload)
    )


@router.delete("/comments/{comment_id}", dependencies=[COMMENTS_ENABLED])
async def delete_comment(
    comment_id: UUID, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    await delete_own_comment(db, context=context, comment_id=comment_id)
    return success({"id": comment_id, "deleted": True})


@router.post("/comments/{comment_id}/like", dependencies=[COMMENTS_ENABLED])
async def like_comment(comment_id: UUID, context: CurrentContext, db: DbSession) -> dict[str, Any]:
    return success(await add_comment_like(db, context=context, comment_id=comment_id))


@router.delete("/comments/{comment_id}/like", dependencies=[COMMENTS_ENABLED])
async def unlike_comment(
    comment_id: UUID, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    return success(await remove_comment_like(db, context=context, comment_id=comment_id))


@router.get("/report-reasons")
async def report_reasons(
    db: DbSession, target_type: ReportTargetType | None = None
) -> dict[str, Any]:
    return success(await report_reason_data(db, target_type))


@router.post(
    "/reports",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("reports", requests=10, window_seconds=3600))],
)
async def post_report(
    payload: ReportCreate, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    row, created = await create_report(db, context=context, payload=payload)
    return success(dict(report_data(row), created=created))


@router.post(
    "/comments/{comment_id}/report",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        COMMENTS_ENABLED,
        Depends(rate_limit("comment_reports", requests=10, window_seconds=3600)),
    ],
)
async def report_comment(
    comment_id: UUID,
    payload: CommentReportInput,
    context: CurrentContext,
    db: DbSession,
) -> dict[str, Any]:
    row, created = await create_report(
        db,
        context=context,
        payload=ReportCreate(
            target_type=ReportTargetType.COMMENT,
            target_id=comment_id,
            reason_code=payload.reason_code,
            details=payload.details,
        ),
    )
    return success(dict(report_data(row), created=created))

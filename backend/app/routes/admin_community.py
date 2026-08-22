from __future__ import annotations

from datetime import UTC
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Request, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, selectinload

from app.api.deps import DbSession, require_permission
from app.core.exceptions import AppError
from app.models.base import utcnow
from app.models.community import Comment, Report, UserMute
from app.models.enums import (
    CommentStatus,
    CommentTargetType,
    ReportStatus,
    ReportTargetType,
    UserStatus,
)
from app.models.user import User
from app.schemas.common import success
from app.schemas.community import (
    CommentModerationInput,
    ReportUpdate,
    UserBanInput,
    UserMuteInput,
)
from app.services.audit import add_audit_log
from app.services.auth import revoke_all_user_sessions
from app.services.community import (
    active_mute,
    comment_data,
    moderate_comment,
    report_data,
    update_report,
)

router = APIRouter(prefix="/admin", tags=["Admin community"])
CommentModerator = Annotated[User, require_permission("comments.moderate")]
ReportManager = Annotated[User, require_permission("reports.manage")]
Page = Annotated[int, Query(ge=1)]
Limit = Annotated[int, Query(ge=1, le=100)]


def _meta(page: int, limit: int, total: int) -> dict[str, int]:
    return {"page": page, "limit": limit, "total": total, "pages": (total + limit - 1) // limit}


def _moderation_data(row: Comment, current_user_id: UUID) -> dict[str, Any]:
    return dict(
        comment_data(row, current_user_id=current_user_id),
        user_id=row.user_id,
        moderated_by_id=row.moderated_by_id,
        moderated_at=row.moderated_at,
        moderation_reason=row.moderation_reason,
        deleted_at=row.deleted_at,
    )


@router.get("/comments")
async def admin_comments(
    admin: CommentModerator,
    db: DbSession,
    page: Page = 1,
    limit: Limit = 20,
    status_filter: CommentStatus | None = Query(default=None, alias="status"),
    target_type: CommentTargetType | None = None,
    target_id: UUID | None = None,
    q: str | None = Query(default=None, max_length=160),
) -> dict[str, Any]:
    conditions = []
    if status_filter is not None:
        conditions.append(Comment.status == status_filter)
    if target_type is not None:
        conditions.append(Comment.target_type == target_type)
    if target_id is not None:
        conditions.append(Comment.target_id == target_id)
    if q:
        conditions.append(Comment.body.ilike(f"%{q.strip()}%"))
    total = int(await db.scalar(select(func.count(Comment.id)).where(*conditions)) or 0)
    rows = list(
        (
            await db.scalars(
                select(Comment)
                .where(*conditions)
                .options(joinedload(Comment.author).selectinload(User.roles))
                .order_by(Comment.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        )
        .unique()
        .all()
    )
    return success(
        [_moderation_data(row, admin.id) for row in rows], meta=_meta(page, limit, total)
    )


@router.patch("/comments/{comment_id}")
async def moderate_comment_route(
    comment_id: UUID,
    payload: CommentModerationInput,
    request: Request,
    admin: CommentModerator,
    db: DbSession,
) -> dict[str, Any]:
    existing = await db.scalar(
        select(Comment)
        .where(Comment.id == comment_id)
        .options(joinedload(Comment.author).selectinload(User.roles))
    )
    if existing is None:
        raise AppError("NOT_FOUND", "Comment not found.", status_code=404)
    old = _moderation_data(existing, admin.id)
    row = await moderate_comment(
        db,
        comment_id=comment_id,
        moderator_id=admin.id,
        action=payload.action,
        reason=payload.reason,
    )
    new = _moderation_data(row, admin.id)
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action=f"comment.{payload.action.value}",
        entity_type="comment",
        entity_id=str(row.id),
        old_value=jsonable_encoder(old),
        new_value=jsonable_encoder(new),
    )
    await db.commit()
    return success(new)


@router.get("/reports")
async def admin_reports(
    _: ReportManager,
    db: DbSession,
    page: Page = 1,
    limit: Limit = 20,
    status_filter: ReportStatus | None = Query(default=None, alias="status"),
    target_type: ReportTargetType | None = None,
) -> dict[str, Any]:
    conditions = []
    if status_filter is not None:
        conditions.append(Report.status == status_filter)
    if target_type is not None:
        conditions.append(Report.target_type == target_type)
    total = int(await db.scalar(select(func.count(Report.id)).where(*conditions)) or 0)
    rows = list(
        (
            await db.scalars(
                select(Report)
                .where(*conditions)
                .options(joinedload(Report.reporter))
                .order_by(Report.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        )
        .unique()
        .all()
    )
    return success([report_data(row) for row in rows], meta=_meta(page, limit, total))


@router.patch("/reports/{report_id}")
async def patch_report(
    report_id: UUID,
    payload: ReportUpdate,
    request: Request,
    admin: ReportManager,
    db: DbSession,
) -> dict[str, Any]:
    existing = await db.scalar(
        select(Report).where(Report.id == report_id).options(joinedload(Report.reporter))
    )
    if existing is None:
        raise AppError("NOT_FOUND", "Report not found.", status_code=404)
    old = report_data(existing)
    row = await update_report(db, report_id=report_id, moderator_id=admin.id, payload=payload)
    new = report_data(row)
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="report.update",
        entity_type="report",
        entity_id=str(row.id),
        old_value=jsonable_encoder(old),
        new_value=jsonable_encoder(new),
    )
    await db.commit()
    return success(new)


async def _community_user(db: DbSession, user_id: UUID) -> User:
    row = await db.scalar(select(User).where(User.id == user_id).options(selectinload(User.roles)))
    if row is None or row.deleted_at is not None:
        raise AppError("NOT_FOUND", "User not found.", status_code=404)
    if row.role_names & {"admin", "super_admin"}:
        raise AppError(
            "PROTECTED_ACCOUNT",
            "This account cannot be moderated here.",
            status_code=403,
        )
    return row


@router.post("/users/{user_id}/mute", status_code=status.HTTP_201_CREATED)
async def mute_user(
    user_id: UUID,
    payload: UserMuteInput,
    request: Request,
    admin: CommentModerator,
    db: DbSession,
) -> dict[str, Any]:
    await _community_user(db, user_id)
    expires_at = payload.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at is not None and expires_at <= utcnow():
        raise AppError("VALIDATION_ERROR", "expires_at must be in the future.", status_code=422)
    existing = await active_mute(db, user_id)
    if existing is not None:
        return success({"id": existing.id, "user_id": user_id, "already_muted": True})
    row = UserMute(
        user_id=user_id,
        moderator_id=admin.id,
        reason=payload.reason,
        starts_at=utcnow(),
        expires_at=expires_at,
    )
    db.add(row)
    await db.flush()
    snapshot = {
        "id": row.id,
        "user_id": row.user_id,
        "reason": row.reason,
        "starts_at": row.starts_at,
        "expires_at": row.expires_at,
    }
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="user.mute",
        entity_type="user",
        entity_id=str(user_id),
        old_value=None,
        new_value=jsonable_encoder(snapshot),
    )
    await db.commit()
    return success(snapshot)


@router.delete("/users/{user_id}/mute")
async def unmute_user(
    user_id: UUID,
    request: Request,
    admin: CommentModerator,
    db: DbSession,
) -> dict[str, Any]:
    row = await active_mute(db, user_id)
    if row is None:
        return success({"user_id": user_id, "muted": False})
    row.revoked_at = utcnow()
    row.revoked_by_id = admin.id
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="user.unmute",
        entity_type="user",
        entity_id=str(user_id),
        old_value=jsonable_encoder({"mute_id": row.id, "expires_at": row.expires_at}),
        new_value=jsonable_encoder({"revoked_at": row.revoked_at}),
    )
    await db.commit()
    return success({"user_id": user_id, "muted": False})


@router.post("/users/{user_id}/ban")
async def ban_user(
    user_id: UUID,
    payload: UserBanInput,
    request: Request,
    admin: CommentModerator,
    db: DbSession,
) -> dict[str, Any]:
    row = await _community_user(db, user_id)
    old_status = row.status
    row.status = UserStatus.BANNED
    await revoke_all_user_sessions(db, row.id, reason="community_ban")
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="user.ban",
        entity_type="user",
        entity_id=str(row.id),
        old_value={"status": old_status.value},
        new_value={"status": row.status.value, "reason": payload.reason},
    )
    await db.commit()
    return success({"id": row.id, "status": row.status})


@router.post("/users/{user_id}/restore")
async def restore_user(
    user_id: UUID,
    request: Request,
    admin: CommentModerator,
    db: DbSession,
) -> dict[str, Any]:
    row = await _community_user(db, user_id)
    old_status = row.status
    row.status = UserStatus.ACTIVE
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="user.restore",
        entity_type="user",
        entity_id=str(row.id),
        old_value={"status": old_status.value},
        new_value={"status": row.status.value},
    )
    await db.commit()
    return success({"id": row.id, "status": row.status})

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from sqlalchemy import case, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import AuthContext
from app.core.exceptions import AppError
from app.models.base import utcnow
from app.models.community import Comment, CommentLike, Like, Report, ReportReason, UserMute
from app.models.content import Content, Episode, Subtitle, VideoAsset
from app.models.enums import (
    CommentStatus,
    CommentTargetType,
    ContentStatus,
    ContentVisibility,
    LikeTargetType,
    Orientation,
    ReportStatus,
    ReportTargetType,
)
from app.models.experience import Notification, NotificationPreference
from app.models.user import User
from app.schemas.community import (
    CommentCreate,
    CommentModerationAction,
    CommentUpdate,
    LikeInput,
    ReportCreate,
    ReportUpdate,
)


def _author_options() -> Any:
    return joinedload(Comment.author).selectinload(User.roles)


async def _public_content(db: AsyncSession, target_id: UUID) -> Content:
    now = utcnow()
    row = await db.scalar(
        select(Content).where(
            Content.id == target_id,
            Content.deleted_at.is_(None),
            Content.status == ContentStatus.PUBLISHED,
            Content.visibility == ContentVisibility.PUBLIC,
            or_(Content.published_at.is_(None), Content.published_at <= now),
            or_(Content.license_start.is_(None), Content.license_start <= now),
            or_(Content.license_end.is_(None), Content.license_end >= now),
        )
    )
    if row is None:
        raise AppError("NOT_FOUND", "Content not found.", status_code=404)
    return row


async def _public_episode(
    db: AsyncSession, target_id: UUID, *, require_vertical: bool = False
) -> Episode:
    now = utcnow()
    conditions = [
        Episode.id == target_id,
        Episode.deleted_at.is_(None),
        Episode.status == ContentStatus.PUBLISHED,
        or_(Episode.published_at.is_(None), Episode.published_at <= now),
    ]
    if require_vertical:
        conditions.append(Episode.orientation.in_([Orientation.VERTICAL, Orientation.MIXED]))
    row = await db.scalar(select(Episode).where(*conditions))
    if row is None:
        raise AppError("NOT_FOUND", "Episode not found.", status_code=404)
    return row


async def validate_comment_target(
    db: AsyncSession, target_type: CommentTargetType, target_id: UUID
) -> None:
    if target_type == CommentTargetType.CONTENT:
        await _public_content(db, target_id)
    else:
        await _public_episode(
            db, target_id, require_vertical=target_type == CommentTargetType.SHORT
        )


async def validate_like_target(
    db: AsyncSession, target_type: LikeTargetType, target_id: UUID
) -> None:
    if target_type == LikeTargetType.CONTENT:
        await _public_content(db, target_id)
    else:
        await _public_episode(db, target_id, require_vertical=target_type == LikeTargetType.SHORT)


async def ensure_not_muted(db: AsyncSession, user_id: UUID) -> None:
    now = utcnow()
    mute = await db.scalar(
        select(UserMute.id).where(
            UserMute.user_id == user_id,
            UserMute.revoked_at.is_(None),
            or_(UserMute.expires_at.is_(None), UserMute.expires_at > now),
        )
    )
    if mute is not None:
        raise AppError(
            "COMMUNITY_MUTED",
            "Your account is temporarily unable to post comments.",
            status_code=403,
        )


async def get_comment(db: AsyncSession, comment_id: UUID, *, public_only: bool = False) -> Comment:
    conditions = [Comment.id == comment_id]
    if public_only:
        conditions.extend([Comment.status == CommentStatus.VISIBLE, Comment.deleted_at.is_(None)])
    row = await db.scalar(select(Comment).where(*conditions).options(_author_options()))
    if row is None:
        raise AppError("NOT_FOUND", "Comment not found.", status_code=404)
    return row


async def _liked_comment_ids(
    db: AsyncSession, user_id: UUID | None, comment_ids: list[UUID]
) -> set[UUID]:
    if user_id is None or not comment_ids:
        return set()
    return set(
        (
            await db.scalars(
                select(CommentLike.comment_id).where(
                    CommentLike.user_id == user_id, CommentLike.comment_id.in_(comment_ids)
                )
            )
        ).all()
    )


def comment_data(
    row: Comment, *, current_user_id: UUID | None, liked: bool = False
) -> dict[str, Any]:
    role_names = row.author.role_names
    badge = None
    if "super_admin" in role_names or "admin" in role_names:
        badge = "admin"
    elif "content_manager" in role_names:
        badge = "creator"
    elif "moderator" in role_names:
        badge = "moderator"
    return {
        "id": row.id,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "parent_id": row.parent_id,
        "body": row.body,
        "is_spoiler": row.is_spoiler,
        "status": row.status,
        "is_pinned": row.is_pinned,
        "like_count": row.like_count,
        "reply_count": row.reply_count,
        "liked_by_me": liked,
        "edited": row.edited_at is not None,
        "edited_at": row.edited_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "author": {
            "id": row.author.id,
            "name": row.author.name,
            "badge": badge,
        },
        "can_edit": current_user_id == row.user_id and row.status == CommentStatus.VISIBLE,
        "can_delete": current_user_id == row.user_id and row.status != CommentStatus.DELETED,
    }


async def list_comments(
    db: AsyncSession,
    *,
    context: AuthContext | None,
    target_type: CommentTargetType,
    target_id: UUID,
    page: int,
    limit: int,
    sort: str,
) -> tuple[list[dict[str, Any]], int]:
    await validate_comment_target(db, target_type, target_id)
    conditions = [
        Comment.target_type == target_type,
        Comment.target_id == target_id,
        Comment.parent_id.is_(None),
        Comment.status == CommentStatus.VISIBLE,
        Comment.deleted_at.is_(None),
    ]
    total = int(await db.scalar(select(func.count(Comment.id)).where(*conditions)) or 0)
    order: Any
    if sort == "oldest":
        order = Comment.created_at.asc()
    elif sort == "popular":
        order = Comment.like_count.desc()
    else:
        order = Comment.created_at.desc()
    rows = list(
        (
            await db.scalars(
                select(Comment)
                .where(*conditions)
                .options(_author_options())
                .order_by(Comment.is_pinned.desc(), order, Comment.id)
                .offset((page - 1) * limit)
                .limit(limit)
            )
        )
        .unique()
        .all()
    )
    user_id = context.user.id if context else None
    liked_ids = await _liked_comment_ids(db, user_id, [row.id for row in rows])
    return [
        comment_data(row, current_user_id=user_id, liked=row.id in liked_ids) for row in rows
    ], total


async def list_replies(
    db: AsyncSession,
    *,
    context: AuthContext | None,
    comment_id: UUID,
    page: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    parent = await get_comment(db, comment_id, public_only=True)
    conditions = [
        Comment.parent_id == parent.id,
        Comment.status == CommentStatus.VISIBLE,
        Comment.deleted_at.is_(None),
    ]
    total = int(await db.scalar(select(func.count(Comment.id)).where(*conditions)) or 0)
    rows = list(
        (
            await db.scalars(
                select(Comment)
                .where(*conditions)
                .options(_author_options())
                .order_by(Comment.created_at.asc(), Comment.id)
                .offset((page - 1) * limit)
                .limit(limit)
            )
        )
        .unique()
        .all()
    )
    user_id = context.user.id if context else None
    liked_ids = await _liked_comment_ids(db, user_id, [row.id for row in rows])
    return [
        comment_data(row, current_user_id=user_id, liked=row.id in liked_ids) for row in rows
    ], total


async def _notify_comment_activity(
    db: AsyncSession,
    *,
    recipient_id: UUID,
    actor_id: UUID,
    title: str,
    body: str,
    comment_id: UUID,
) -> None:
    if recipient_id == actor_id:
        return
    preferences = await db.get(NotificationPreference, recipient_id)
    if preferences is not None and not preferences.comments:
        return
    db.add(
        Notification(
            user_id=recipient_id,
            type="comment_reply" if title == "New reply" else "comment_like",
            title=title,
            body=body,
            action_url=f"drovixa://comment/{comment_id}",
            payload={"comment_id": str(comment_id)},
        )
    )


async def create_comment(
    db: AsyncSession, *, context: AuthContext, payload: CommentCreate
) -> dict[str, Any]:
    await ensure_not_muted(db, context.user.id)
    await validate_comment_target(db, payload.target_type, payload.target_id)
    parent = None
    if payload.parent_id is not None:
        parent = await get_comment(db, payload.parent_id, public_only=True)
        if parent.parent_id is not None:
            raise AppError(
                "VALIDATION_ERROR", "Replies can only be one level deep.", status_code=422
            )
        if parent.target_type != payload.target_type or parent.target_id != payload.target_id:
            raise AppError("VALIDATION_ERROR", "Reply target does not match.", status_code=422)
    row = Comment(
        user_id=context.user.id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        parent_id=payload.parent_id,
        body=payload.body,
        is_spoiler=payload.is_spoiler,
    )
    row.author = context.user
    db.add(row)
    await db.flush()
    if parent is not None:
        await db.execute(
            update(Comment)
            .where(Comment.id == parent.id)
            .values(reply_count=Comment.reply_count + 1)
        )
        await _notify_comment_activity(
            db,
            recipient_id=parent.user_id,
            actor_id=context.user.id,
            title="New reply",
            body=f"{context.user.name} replied to your comment.",
            comment_id=parent.id,
        )
    await db.commit()
    return comment_data(row, current_user_id=context.user.id)


async def update_own_comment(
    db: AsyncSession,
    *,
    context: AuthContext,
    comment_id: UUID,
    payload: CommentUpdate,
) -> dict[str, Any]:
    await ensure_not_muted(db, context.user.id)
    row = await get_comment(db, comment_id)
    if row.user_id != context.user.id:
        raise AppError("FORBIDDEN", "You can only edit your own comments.", status_code=403)
    if row.status != CommentStatus.VISIBLE or row.deleted_at is not None:
        raise AppError("COMMENT_NOT_EDITABLE", "This comment cannot be edited.", status_code=409)
    changes = payload.model_dump(exclude_none=True)
    for key, value in changes.items():
        setattr(row, key, value)
    row.edited_at = utcnow()
    await db.commit()
    return comment_data(row, current_user_id=context.user.id)


async def delete_own_comment(db: AsyncSession, *, context: AuthContext, comment_id: UUID) -> None:
    row = await get_comment(db, comment_id)
    if row.user_id != context.user.id:
        raise AppError("FORBIDDEN", "You can only delete your own comments.", status_code=403)
    if row.status == CommentStatus.DELETED:
        return
    row.status = CommentStatus.DELETED
    row.deleted_at = utcnow()
    row.body = "[deleted]"
    if row.parent_id is not None:
        await db.execute(
            update(Comment)
            .where(Comment.id == row.parent_id)
            .values(reply_count=case((Comment.reply_count > 0, Comment.reply_count - 1), else_=0))
        )
    await db.commit()


async def add_like(
    db: AsyncSession, *, user_id: UUID, payload: LikeInput
) -> tuple[Like, int, bool]:
    await validate_like_target(db, payload.target_type, payload.target_id)
    existing = await db.scalar(
        select(Like).where(
            Like.user_id == user_id,
            Like.target_type == payload.target_type,
            Like.target_id == payload.target_id,
        )
    )
    created = False
    if existing is not None:
        row = existing
    else:
        row = Like(user_id=user_id, target_type=payload.target_type, target_id=payload.target_id)
        try:
            async with db.begin_nested():
                db.add(row)
                await db.flush()
            created = True
        except IntegrityError:
            concurrent = await db.scalar(
                select(Like).where(
                    Like.user_id == user_id,
                    Like.target_type == payload.target_type,
                    Like.target_id == payload.target_id,
                )
            )
            if concurrent is None:
                raise
            row = concurrent
        if created and payload.target_type == LikeTargetType.CONTENT:
            await db.execute(
                update(Content)
                .where(Content.id == payload.target_id)
                .values(like_count=Content.like_count + 1)
            )
    count = int(
        await db.scalar(
            select(func.count(Like.id)).where(
                Like.target_type == payload.target_type, Like.target_id == payload.target_id
            )
        )
        or 0
    )
    await db.commit()
    return row, count, created


async def remove_like(db: AsyncSession, *, user_id: UUID, payload: LikeInput) -> int:
    row = await db.scalar(
        select(Like).where(
            Like.user_id == user_id,
            Like.target_type == payload.target_type,
            Like.target_id == payload.target_id,
        )
    )
    if row is not None:
        await db.delete(row)
        if payload.target_type == LikeTargetType.CONTENT:
            await db.execute(
                update(Content)
                .where(Content.id == payload.target_id)
                .values(like_count=case((Content.like_count > 0, Content.like_count - 1), else_=0))
            )
        await db.flush()
    count = int(
        await db.scalar(
            select(func.count(Like.id)).where(
                Like.target_type == payload.target_type, Like.target_id == payload.target_id
            )
        )
        or 0
    )
    await db.commit()
    return count


async def add_comment_like(
    db: AsyncSession, *, context: AuthContext, comment_id: UUID
) -> dict[str, Any]:
    row = await get_comment(db, comment_id, public_only=True)
    existing = await db.get(CommentLike, (context.user.id, row.id))
    if existing is None:
        db.add(CommentLike(user_id=context.user.id, comment_id=row.id))
        row.like_count += 1
        await _notify_comment_activity(
            db,
            recipient_id=row.user_id,
            actor_id=context.user.id,
            title="Comment liked",
            body=f"{context.user.name} liked your comment.",
            comment_id=row.id,
        )
    await db.commit()
    return {"comment_id": row.id, "liked": True, "like_count": row.like_count}


async def remove_comment_like(
    db: AsyncSession, *, context: AuthContext, comment_id: UUID
) -> dict[str, Any]:
    row = await get_comment(db, comment_id, public_only=True)
    existing = await db.get(CommentLike, (context.user.id, row.id))
    if existing is not None:
        await db.delete(existing)
        row.like_count = max(0, row.like_count - 1)
    await db.commit()
    return {"comment_id": row.id, "liked": False, "like_count": row.like_count}


async def report_reason_data(
    db: AsyncSession, target_type: ReportTargetType | None
) -> list[dict[str, Any]]:
    statement = select(ReportReason).where(ReportReason.active.is_(True))
    rows = (await db.scalars(statement.order_by(ReportReason.sort_order, ReportReason.code))).all()
    return [
        {
            "code": row.code,
            "label": row.label,
            "description": row.description,
            "target_types": row.target_types,
        }
        for row in rows
        if target_type is None or target_type.value in row.target_types
    ]


async def _report_snapshot(
    db: AsyncSession, target_type: ReportTargetType, target_id: UUID | None
) -> dict[str, Any]:
    if target_type == ReportTargetType.TECHNICAL:
        return {"type": "technical"}
    if target_id is None:
        raise AppError("VALIDATION_ERROR", "target_id is required.", status_code=422)
    if target_type == ReportTargetType.COMMENT:
        comment = await get_comment(db, target_id, public_only=True)
        return {
            "id": str(comment.id),
            "author_id": str(comment.user_id),
            "body": comment.body[:500],
        }
    if target_type == ReportTargetType.USER:
        user = await db.get(User, target_id)
        if user is None or user.deleted_at is not None:
            raise AppError("NOT_FOUND", "User not found.", status_code=404)
        return {"id": str(user.id), "name": user.name}
    if target_type == ReportTargetType.CONTENT:
        content = await _public_content(db, target_id)
        return {"id": str(content.id), "title": content.title, "type": content.type.value}
    if target_type == ReportTargetType.EPISODE:
        episode = await _public_episode(db, target_id)
        return {"id": str(episode.id), "title": episode.title}
    if target_type == ReportTargetType.VIDEO:
        video = await db.scalar(
            select(VideoAsset).where(VideoAsset.id == target_id, VideoAsset.deleted_at.is_(None))
        )
        if video is None:
            raise AppError("NOT_FOUND", "Video not found.", status_code=404)
        return {"id": str(video.id), "provider": video.provider, "status": video.status.value}
    subtitle = await db.scalar(
        select(Subtitle).where(Subtitle.id == target_id, Subtitle.deleted_at.is_(None))
    )
    if subtitle is None:
        raise AppError("NOT_FOUND", "Subtitle not found.", status_code=404)
    return {"id": str(subtitle.id), "label": subtitle.label, "format": subtitle.format.value}


def report_data(row: Report) -> dict[str, Any]:
    return {
        "id": row.id,
        "reporter": {"id": row.reporter.id, "name": row.reporter.name},
        "target_type": row.target_type,
        "target_id": row.target_id,
        "reason_code": row.reason_code,
        "details": row.details,
        "status": row.status,
        "assigned_to_id": row.assigned_to_id,
        "resolved_by_id": row.resolved_by_id,
        "resolved_at": row.resolved_at,
        "resolution_note": row.resolution_note,
        "target_snapshot": row.target_snapshot,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


async def create_report(
    db: AsyncSession, *, context: AuthContext, payload: ReportCreate
) -> tuple[Report, bool]:
    reason = await db.scalar(
        select(ReportReason).where(
            ReportReason.code == payload.reason_code, ReportReason.active.is_(True)
        )
    )
    if reason is None or payload.target_type.value not in reason.target_types:
        raise AppError(
            "INVALID_REPORT_REASON", "This report reason is unavailable.", status_code=422
        )
    snapshot = await _report_snapshot(db, payload.target_type, payload.target_id)
    existing = await db.scalar(
        select(Report)
        .where(
            Report.reporter_id == context.user.id,
            Report.target_type == payload.target_type,
            Report.target_id == payload.target_id,
            Report.reason_code == payload.reason_code,
            Report.status.in_([ReportStatus.OPEN, ReportStatus.UNDER_REVIEW]),
        )
        .options(joinedload(Report.reporter))
    )
    if existing is not None:
        return existing, False
    row = Report(
        reporter_id=context.user.id,
        reporter=context.user,
        target_type=payload.target_type,
        target_id=payload.target_id,
        reason_code=payload.reason_code,
        details=payload.details,
        target_snapshot=snapshot,
    )
    db.add(row)
    await db.flush()
    if payload.target_type == ReportTargetType.COMMENT and payload.target_id is not None:
        report_count = int(
            await db.scalar(
                select(func.count(Report.id)).where(
                    Report.target_type == ReportTargetType.COMMENT,
                    Report.target_id == payload.target_id,
                    Report.status.in_([ReportStatus.OPEN, ReportStatus.UNDER_REVIEW]),
                )
            )
            or 0
        )
        if report_count >= 3:
            await db.execute(
                update(Comment)
                .where(Comment.id == payload.target_id, Comment.status == CommentStatus.VISIBLE)
                .values(status=CommentStatus.UNDER_REVIEW)
            )
    await db.commit()
    return row, True


async def moderate_comment(
    db: AsyncSession,
    *,
    comment_id: UUID,
    moderator_id: UUID,
    action: CommentModerationAction,
    reason: str | None,
) -> Comment:
    row = await get_comment(db, comment_id)
    now = utcnow()
    if action == CommentModerationAction.HIDE:
        row.status = CommentStatus.HIDDEN
    elif action == CommentModerationAction.DELETE:
        row.status = CommentStatus.DELETED
        row.deleted_at = now
        row.body = "[deleted by moderator]"
    elif action == CommentModerationAction.RESTORE:
        row.status = CommentStatus.VISIBLE
        row.deleted_at = None
    elif action == CommentModerationAction.SPAM:
        row.status = CommentStatus.SPAM
    elif action == CommentModerationAction.PIN:
        if row.parent_id is not None or row.status != CommentStatus.VISIBLE:
            raise AppError(
                "COMMENT_NOT_PINNABLE",
                "Only visible top-level comments can be pinned.",
                status_code=409,
            )
        row.is_pinned = True
    elif action == CommentModerationAction.UNPIN:
        row.is_pinned = False
    row.moderated_by_id = moderator_id
    row.moderated_at = now
    row.moderation_reason = reason
    await db.flush()
    return row


async def update_report(
    db: AsyncSession,
    *,
    report_id: UUID,
    moderator_id: UUID,
    payload: ReportUpdate,
) -> Report:
    row = await db.scalar(
        select(Report).where(Report.id == report_id).options(joinedload(Report.reporter))
    )
    if row is None:
        raise AppError("NOT_FOUND", "Report not found.", status_code=404)
    changes = payload.model_dump(exclude_none=True)
    for key, value in changes.items():
        setattr(row, key, value)
    if payload.status in {ReportStatus.RESOLVED, ReportStatus.DISMISSED}:
        row.resolved_by_id = moderator_id
        row.resolved_at = utcnow()
    elif payload.status in {ReportStatus.OPEN, ReportStatus.UNDER_REVIEW}:
        row.resolved_by_id = None
        row.resolved_at = None
    await db.flush()
    return row


async def active_mute(db: AsyncSession, user_id: UUID) -> UserMute | None:
    now = utcnow()
    return cast(
        UserMute | None,
        await db.scalar(
            select(UserMute)
            .where(
                UserMute.user_id == user_id,
                UserMute.revoked_at.is_(None),
                or_(UserMute.expires_at.is_(None), UserMute.expires_at > now),
            )
            .order_by(UserMute.created_at.desc())
        ),
    )

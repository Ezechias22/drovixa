from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    CommentStatus,
    CommentTargetType,
    LikeTargetType,
    ReportStatus,
    ReportTargetType,
)
from app.models.user import User


def enum_values(enum: type[Any]) -> list[str]:
    return [item.value for item in enum]


class Like(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "likes"
    __table_args__ = (
        UniqueConstraint("user_id", "target_type", "target_id", name="uq_likes_user_target"),
        Index("ix_likes_target", "target_type", "target_id"),
        Index("ix_likes_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    target_type: Mapped[LikeTargetType] = mapped_column(
        Enum(LikeTargetType, name="like_target_type", values_callable=enum_values)
    )
    target_id: Mapped[UUID]


class Comment(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "comments"
    __table_args__ = (
        Index(
            "ix_comments_target_status_created",
            "target_type",
            "target_id",
            "status",
            "created_at",
        ),
        Index("ix_comments_parent_created", "parent_id", "created_at"),
        Index("ix_comments_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    target_type: Mapped[CommentTargetType] = mapped_column(
        Enum(CommentTargetType, name="comment_target_type", values_callable=enum_values)
    )
    target_id: Mapped[UUID]
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), index=True
    )
    body: Mapped[str] = mapped_column(Text)
    is_spoiler: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    status: Mapped[CommentStatus] = mapped_column(
        Enum(CommentStatus, name="comment_status", values_callable=enum_values),
        default=CommentStatus.VISIBLE,
        server_default=CommentStatus.VISIBLE.value,
        index=True,
    )
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    like_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reply_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    moderated_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    moderation_reason: Mapped[str | None] = mapped_column(String(500))

    author: Mapped[User] = relationship(foreign_keys=[user_id], lazy="joined")
    moderator: Mapped[User | None] = relationship(foreign_keys=[moderated_by_id], lazy="joined")
    parent: Mapped[Comment | None] = relationship(
        remote_side="Comment.id",
        back_populates="replies",
        foreign_keys=[parent_id],
        lazy="noload",
    )
    replies: Mapped[list[Comment]] = relationship(
        back_populates="parent", cascade="all, delete-orphan", lazy="noload"
    )


class CommentLike(TimestampMixin, Base):
    __tablename__ = "comment_likes"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    comment_id: Mapped[UUID] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), primary_key=True
    )


class ReportReason(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "report_reasons"

    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(String(500))
    target_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Report(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_status_created", "status", "created_at"),
        Index("ix_reports_target", "target_type", "target_id"),
        Index("ix_reports_reporter_created", "reporter_id", "created_at"),
    )

    reporter_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    target_type: Mapped[ReportTargetType] = mapped_column(
        Enum(ReportTargetType, name="report_target_type", values_callable=enum_values)
    )
    target_id: Mapped[UUID | None]
    reason_code: Mapped[str] = mapped_column(String(80), index=True)
    details: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, name="report_status", values_callable=enum_values),
        default=ReportStatus.OPEN,
        server_default=ReportStatus.OPEN.value,
        index=True,
    )
    assigned_to_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    resolved_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(Text)
    target_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    reporter: Mapped[User] = relationship(foreign_keys=[reporter_id], lazy="joined")
    assigned_to: Mapped[User | None] = relationship(foreign_keys=[assigned_to_id], lazy="joined")
    resolved_by: Mapped[User | None] = relationship(foreign_keys=[resolved_by_id], lazy="joined")


class UserMute(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_mutes"
    __table_args__ = (Index("ix_user_mutes_user_active", "user_id", "revoked_at", "expires_at"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    moderator_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reason: Mapped[str] = mapped_column(String(500))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

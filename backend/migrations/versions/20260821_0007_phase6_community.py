"""phase 6 community

Revision ID: 20260821_0007
Revises: 20260816_0006
Create Date: 2026-08-21 02:00:00
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0007"
down_revision: str | None = "20260816_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_NAMESPACE = uuid.UUID("568b998e-a294-42f8-85b6-227e66e707b7")


def stable_id(kind: str, name: str) -> uuid.UUID:
    return uuid.uuid5(UUID_NAMESPACE, f"{kind}:{name}")


def timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


like_target_type = sa.Enum("content", "episode", "short", name="like_target_type")
comment_target_type = sa.Enum("content", "episode", "short", name="comment_target_type")
comment_status = sa.Enum(
    "visible", "hidden", "deleted", "under_review", "spam", name="comment_status"
)
report_target_type = sa.Enum(
    "comment",
    "user",
    "content",
    "episode",
    "video",
    "subtitle",
    "technical",
    name="report_target_type",
)
report_status = sa.Enum(
    "open", "under_review", "resolved", "dismissed", name="report_status"
)


def upgrade() -> None:
    op.create_table(
        "likes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("target_type", like_target_type, nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_likes"),
        sa.UniqueConstraint("user_id", "target_type", "target_id", name="uq_likes_user_target"),
    )
    op.create_index("ix_likes_target", "likes", ["target_type", "target_id"])
    op.create_index("ix_likes_user_created", "likes", ["user_id", "created_at"])

    op.create_table(
        "comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("target_type", comment_target_type, nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_spoiler", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("status", comment_status, server_default="visible", nullable=False),
        sa.Column("is_pinned", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("like_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reply_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("moderated_by_id", sa.Uuid(), nullable=True),
        sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("moderation_reason", sa.String(500), nullable=True),
        *timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("like_count >= 0", name="ck_comments_like_count_non_negative"),
        sa.CheckConstraint("reply_count >= 0", name="ck_comments_reply_count_non_negative"),
        sa.ForeignKeyConstraint(["moderated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_id"], ["comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_comments"),
    )
    op.create_index("ix_comments_status", "comments", ["status"])
    op.create_index("ix_comments_parent_id", "comments", ["parent_id"])
    op.create_index("ix_comments_moderated_by_id", "comments", ["moderated_by_id"])
    op.create_index(
        "ix_comments_target_status_created",
        "comments",
        ["target_type", "target_id", "status", "created_at"],
    )
    op.create_index("ix_comments_parent_created", "comments", ["parent_id", "created_at"])
    op.create_index("ix_comments_user_created", "comments", ["user_id", "created_at"])

    op.create_table(
        "comment_likes",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("comment_id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "comment_id", name="pk_comment_likes"),
    )

    op.create_table(
        "report_reasons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("target_types", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_report_reasons"),
    )
    op.create_index("ix_report_reasons_code", "report_reasons", ["code"], unique=True)

    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reporter_id", sa.Uuid(), nullable=False),
        sa.Column("target_type", report_target_type, nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("reason_code", sa.String(80), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("status", report_status, server_default="open", nullable=False),
        sa.Column("assigned_to_id", sa.Uuid(), nullable=True),
        sa.Column("resolved_by_id", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("target_snapshot", sa.JSON(), server_default="{}", nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["assigned_to_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_reports"),
    )
    op.create_index("ix_reports_status", "reports", ["status"])
    op.create_index("ix_reports_reason_code", "reports", ["reason_code"])
    op.create_index("ix_reports_assigned_to_id", "reports", ["assigned_to_id"])
    op.create_index("ix_reports_resolved_by_id", "reports", ["resolved_by_id"])
    op.create_index("ix_reports_status_created", "reports", ["status", "created_at"])
    op.create_index("ix_reports_target", "reports", ["target_type", "target_id"])
    op.create_index("ix_reports_reporter_created", "reports", ["reporter_id", "created_at"])

    op.create_table(
        "user_mutes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("moderator_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_id", sa.Uuid(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["moderator_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["revoked_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_user_mutes"),
    )
    op.create_index(
        "ix_user_mutes_user_active", "user_mutes", ["user_id", "revoked_at", "expires_at"]
    )

    reasons_table = sa.table(
        "report_reasons",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("label", sa.String()),
        sa.column("description", sa.String()),
        sa.column("target_types", sa.JSON()),
        sa.column("active", sa.Boolean()),
        sa.column("sort_order", sa.Integer()),
    )
    reasons = [
        ("inappropriate", "Inappropriate content", "Content that should not be on Drovixa", 0),
        ("harassment", "Harassment or bullying", "Threats, intimidation or targeted abuse", 1),
        ("hate_speech", "Hate speech", "Attacks based on a protected characteristic", 2),
        ("spam", "Spam or misleading", "Spam, scams or repetitive promotion", 3),
        ("spoiler", "Unmarked spoiler", "A spoiler that was not properly marked", 4),
        ("violence", "Graphic violence", "Graphic or disturbing violent material", 5),
        ("sexual_content", "Sexual content", "Sexual or exploitative material", 6),
        ("copyright", "Copyright concern", "Possible unauthorized copyrighted material", 7),
        ("technical_issue", "Technical problem", "Playback, subtitle or application problem", 8),
        ("other", "Other", "Another issue that needs review", 9),
    ]
    all_targets = ["comment", "user", "content", "episode", "video", "subtitle", "technical"]
    op.bulk_insert(
        reasons_table,
        [
            {
                "id": stable_id("report_reason", code),
                "code": code,
                "label": label,
                "description": description,
                "target_types": op.inline_literal(json.dumps(all_targets)),
                "active": True,
                "sort_order": sort_order,
            }
            for code, label, description, sort_order in reasons
        ],
        multiinsert=False,
    )
    op.execute(
        sa.text(
            "UPDATE feature_flags SET enabled = true, updated_at = now() "
            "WHERE key = 'comments_enabled'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE feature_flags SET enabled = false, updated_at = now() "
            "WHERE key = 'comments_enabled'"
        )
    )
    op.drop_index("ix_user_mutes_user_active", table_name="user_mutes")
    op.drop_table("user_mutes")
    op.drop_index("ix_reports_reporter_created", table_name="reports")
    op.drop_index("ix_reports_target", table_name="reports")
    op.drop_index("ix_reports_status_created", table_name="reports")
    op.drop_index("ix_reports_resolved_by_id", table_name="reports")
    op.drop_index("ix_reports_assigned_to_id", table_name="reports")
    op.drop_index("ix_reports_reason_code", table_name="reports")
    op.drop_index("ix_reports_status", table_name="reports")
    op.drop_table("reports")
    op.drop_index("ix_report_reasons_code", table_name="report_reasons")
    op.drop_table("report_reasons")
    op.drop_table("comment_likes")
    op.drop_index("ix_comments_user_created", table_name="comments")
    op.drop_index("ix_comments_parent_created", table_name="comments")
    op.drop_index("ix_comments_target_status_created", table_name="comments")
    op.drop_index("ix_comments_moderated_by_id", table_name="comments")
    op.drop_index("ix_comments_parent_id", table_name="comments")
    op.drop_index("ix_comments_status", table_name="comments")
    op.drop_table("comments")
    op.drop_index("ix_likes_user_created", table_name="likes")
    op.drop_index("ix_likes_target", table_name="likes")
    op.drop_table("likes")
    report_status.drop(op.get_bind(), checkfirst=True)
    report_target_type.drop(op.get_bind(), checkfirst=True)
    comment_status.drop(op.get_bind(), checkfirst=True)
    comment_target_type.drop(op.get_bind(), checkfirst=True)
    like_target_type.drop(op.get_bind(), checkfirst=True)

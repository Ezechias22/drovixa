"""phase 8 production performance indexes

Revision ID: 20260822_0009
Revises: 20260822_0008
Create Date: 2026-08-22 23:40:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260822_0009"
down_revision: str | None = "20260822_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_content_feed",
        "content",
        ["status", "visibility", "type", "published_at"],
        unique=False,
    )
    op.create_index(
        "ix_video_assets_status_updated",
        "video_assets",
        ["status", "updated_at"],
        unique=False,
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"], unique=False)
    op.create_index(
        "ix_audit_logs_action_created",
        "audit_logs",
        ["action", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_payments_status_created",
        "payments",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_user_sessions_user_last_seen",
        "user_sessions",
        ["user_id", "last_seen_at"],
        unique=False,
    )
    op.create_index(
        "ix_watch_progress_user_watched",
        "watch_progress",
        ["user_id", "last_watched_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_watch_progress_user_watched", table_name="watch_progress")
    op.drop_index("ix_user_sessions_user_last_seen", table_name="user_sessions")
    op.drop_index("ix_payments_status_created", table_name="payments")
    op.drop_index("ix_audit_logs_action_created", table_name="audit_logs")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_video_assets_status_updated", table_name="video_assets")
    op.drop_index("ix_content_feed", table_name="content")

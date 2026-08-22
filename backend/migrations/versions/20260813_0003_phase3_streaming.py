"""phase 3 secure streaming

Revision ID: 20260813_0003
Revises: 20260813_0002
Create Date: 2026-08-13 18:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0003"
down_revision: str | None = "20260813_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.add_column(
        "video_assets", sa.Column("provider_error_code", sa.String(120), nullable=True)
    )
    op.add_column(
        "video_assets", sa.Column("provider_error_message", sa.Text(), nullable=True)
    )
    op.add_column(
        "video_assets", sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True)
    )

    upload_protocol = sa.Enum("basic", "tus", name="upload_protocol")
    op.create_table(
        "video_upload_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("video_asset_id", sa.Uuid(), nullable=False),
        sa.Column("initiated_by_id", sa.Uuid(), nullable=True),
        sa.Column("protocol", upload_protocol, nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("max_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("upload_completed_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["initiated_by_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["video_asset_id"], ["video_assets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_video_upload_sessions"),
    )
    op.create_index(
        "ix_video_upload_sessions_video_asset_id",
        "video_upload_sessions",
        ["video_asset_id"],
        unique=True,
    )
    op.create_index(
        "ix_video_upload_sessions_initiated_by_id",
        "video_upload_sessions",
        ["initiated_by_id"],
    )

    webhook_status = sa.Enum(
        "received",
        "processed",
        "ignored",
        "failed",
        name="webhook_processing_status",
    )
    op.create_table(
        "video_webhook_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("provider_asset_id", sa.String(255), nullable=True),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("signature_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "status", webhook_status, server_default="received", nullable=False
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_video_webhook_events"),
        sa.UniqueConstraint(
            "provider", "idempotency_key", name="uq_video_webhook_event"
        ),
    )
    op.create_index(
        "ix_video_webhook_events_provider",
        "video_webhook_events",
        ["provider"],
    )
    op.create_index(
        "ix_video_webhook_events_provider_asset_id",
        "video_webhook_events",
        ["provider_asset_id"],
    )
    op.create_index(
        "ix_video_webhook_events_status", "video_webhook_events", ["status"]
    )

    entitlement_type = sa.Enum(
        "series", "movie", name="entitlement_content_type"
    )
    op.create_table(
        "user_entitlements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("content_type", entitlement_type, nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_permanent", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        *timestamps(),
        sa.CheckConstraint(
            "expires_at IS NULL OR starts_at IS NULL OR expires_at >= starts_at",
            name=op.f("ck_user_entitlements_date_range"),
        ),
        sa.ForeignKeyConstraint(
            ["content_id"], ["content.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["episode_id"], ["episodes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_user_entitlements"),
    )
    op.create_index(
        "ix_user_entitlements_user_id", "user_entitlements", ["user_id"]
    )
    op.create_index(
        "ix_user_entitlements_content_id", "user_entitlements", ["content_id"]
    )
    op.create_index(
        "ix_user_entitlements_episode_id", "user_entitlements", ["episode_id"]
    )
    op.create_index(
        "ix_user_entitlements_transaction_id",
        "user_entitlements",
        ["transaction_id"],
    )
    op.create_index(
        "ix_user_entitlements_expires_at", "user_entitlements", ["expires_at"]
    )
    op.create_index(
        "ix_user_entitlements_lookup",
        "user_entitlements",
        ["user_id", "content_id", "episode_id"],
    )

    op.create_table(
        "playback_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("auth_session_id", sa.Uuid(), nullable=True),
        sa.Column("device_id", sa.Uuid(), nullable=True),
        sa.Column("client_device_id", sa.String(160), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=True),
        sa.Column("video_asset_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("view_counted_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["auth_session_id"], ["user_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["content_id"], ["content.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["device_id"], ["devices.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["episode_id"], ["episodes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["video_asset_id"], ["video_assets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_playback_sessions"),
    )
    for column in (
        "user_id",
        "auth_session_id",
        "device_id",
        "content_id",
        "episode_id",
        "video_asset_id",
        "expires_at",
    ):
        op.create_index(
            f"ix_playback_sessions_{column}", "playback_sessions", [column]
        )
    op.create_index(
        "ix_playback_sessions_user_active",
        "playback_sessions",
        ["user_id", "expires_at", "revoked_at"],
    )
    op.create_index(
        "ix_playback_sessions_asset_active",
        "playback_sessions",
        ["video_asset_id", "expires_at"],
    )

    watch_type = sa.Enum("series", "movie", name="watch_content_type")
    op.create_table(
        "watch_progress",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("content_type", watch_type, nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=True),
        sa.Column("device_id", sa.Uuid(), nullable=True),
        sa.Column("position_seconds", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column(
            "completed", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("last_watched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.CheckConstraint(
            "position_seconds >= 0", name=op.f("ck_watch_progress_position_non_negative")
        ),
        sa.CheckConstraint(
            "duration_seconds > 0", name=op.f("ck_watch_progress_duration_positive")
        ),
        sa.CheckConstraint(
            "percentage >= 0 AND percentage <= 100",
            name=op.f("ck_watch_progress_percentage_range"),
        ),
        sa.ForeignKeyConstraint(
            ["content_id"], ["content.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["device_id"], ["devices.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["episode_id"], ["episodes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_watch_progress"),
    )
    for column in (
        "user_id",
        "content_id",
        "episode_id",
        "device_id",
        "last_watched_at",
    ):
        op.create_index(f"ix_watch_progress_{column}", "watch_progress", [column])
    op.create_index(
        "uq_watch_progress_episode",
        "watch_progress",
        ["user_id", "episode_id"],
        unique=True,
        postgresql_where=sa.text("episode_id IS NOT NULL"),
        sqlite_where=sa.text("episode_id IS NOT NULL"),
    )
    op.create_index(
        "uq_watch_progress_movie",
        "watch_progress",
        ["user_id", "content_id"],
        unique=True,
        postgresql_where=sa.text("episode_id IS NULL"),
        sqlite_where=sa.text("episode_id IS NULL"),
    )
    op.create_index(
        "ix_watch_progress_continue",
        "watch_progress",
        ["user_id", "completed", "removed_at"],
    )

    history_type = sa.Enum("series", "movie", name="history_content_type")
    op.create_table(
        "watch_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("content_type", history_type, nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=True),
        sa.Column("playback_session_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=True),
        sa.Column("position_seconds", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column(
            "completed", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_watched_at", sa.DateTime(timezone=True), nullable=False),
        *timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["content_id"], ["content.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["device_id"], ["devices.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["episode_id"], ["episodes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["playback_session_id"], ["playback_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_watch_history"),
        sa.UniqueConstraint(
            "playback_session_id", name="uq_watch_history_playback_session"
        ),
    )
    for column in (
        "user_id",
        "content_id",
        "episode_id",
        "playback_session_id",
        "device_id",
        "last_watched_at",
    ):
        op.create_index(f"ix_watch_history_{column}", "watch_history", [column])
    op.create_index(
        "ix_watch_history_user_watched",
        "watch_history",
        ["user_id", "last_watched_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_watch_history_user_watched", table_name="watch_history")
    for column in reversed(
        (
            "user_id",
            "content_id",
            "episode_id",
            "playback_session_id",
            "device_id",
            "last_watched_at",
        )
    ):
        op.drop_index(f"ix_watch_history_{column}", table_name="watch_history")
    op.drop_table("watch_history")

    op.drop_index("ix_watch_progress_continue", table_name="watch_progress")
    op.drop_index("uq_watch_progress_movie", table_name="watch_progress")
    op.drop_index("uq_watch_progress_episode", table_name="watch_progress")
    for column in reversed(
        ("user_id", "content_id", "episode_id", "device_id", "last_watched_at")
    ):
        op.drop_index(f"ix_watch_progress_{column}", table_name="watch_progress")
    op.drop_table("watch_progress")

    op.drop_index("ix_playback_sessions_asset_active", table_name="playback_sessions")
    op.drop_index("ix_playback_sessions_user_active", table_name="playback_sessions")
    for column in reversed(
        (
            "user_id",
            "auth_session_id",
            "device_id",
            "content_id",
            "episode_id",
            "video_asset_id",
            "expires_at",
        )
    ):
        op.drop_index(f"ix_playback_sessions_{column}", table_name="playback_sessions")
    op.drop_table("playback_sessions")

    op.drop_index("ix_user_entitlements_lookup", table_name="user_entitlements")
    for column in reversed(
        ("user_id", "content_id", "episode_id", "transaction_id", "expires_at")
    ):
        op.drop_index(f"ix_user_entitlements_{column}", table_name="user_entitlements")
    op.drop_table("user_entitlements")

    op.drop_index("ix_video_webhook_events_status", table_name="video_webhook_events")
    op.drop_index(
        "ix_video_webhook_events_provider_asset_id", table_name="video_webhook_events"
    )
    op.drop_index("ix_video_webhook_events_provider", table_name="video_webhook_events")
    op.drop_table("video_webhook_events")

    op.drop_index(
        "ix_video_upload_sessions_initiated_by_id", table_name="video_upload_sessions"
    )
    op.drop_index(
        "ix_video_upload_sessions_video_asset_id", table_name="video_upload_sessions"
    )
    op.drop_table("video_upload_sessions")

    op.drop_column("video_assets", "ready_at")
    op.drop_column("video_assets", "provider_error_message")
    op.drop_column("video_assets", "provider_error_code")

    bind = op.get_bind()
    for enum_name in (
        "history_content_type",
        "watch_content_type",
        "entitlement_content_type",
        "webhook_processing_status",
        "upload_protocol",
    ):
        sa.Enum(name=enum_name).drop(bind, checkfirst=True)

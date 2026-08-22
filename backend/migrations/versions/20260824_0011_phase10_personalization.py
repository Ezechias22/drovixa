"""phase 10 profiles, kids mode, ratings, downloads and casting

Revision ID: 20260824_0011
Revises: 20260823_0010
Create Date: 2026-08-24 00:11:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260824_0011"
down_revision: str | None = "20260823_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "content",
        sa.Column("rating_count", sa.BigInteger(), server_default="0", nullable=False),
    )

    op.create_table(
        "viewer_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("avatar_key", sa.String(length=60), server_default="nova", nullable=False),
        sa.Column("is_kids", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("age_limit", sa.Integer(), server_default="18", nullable=False),
        sa.Column("language_code", sa.String(length=16), server_default="en", nullable=False),
        sa.Column("autoplay_next", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("autoplay_previews", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("pin_hash", sa.String(length=512), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "age_limit >= 0 AND age_limit <= 18",
            name="ck_viewer_profiles_age_limit_range",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_viewer_profiles_user_id", "viewer_profiles", ["user_id"])
    op.create_index("ix_viewer_profiles_user_active", "viewer_profiles", ["user_id", "active"])

    op.create_table(
        "content_ratings",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("score >= 1 AND score <= 5", name="ck_content_ratings_score_range"),
        sa.ForeignKeyConstraint(["content_id"], ["content.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["viewer_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "content_id", name="uq_content_ratings_profile_content"),
    )
    op.create_index("ix_content_ratings_user_id", "content_ratings", ["user_id"])
    op.create_index("ix_content_ratings_profile_id", "content_ratings", ["profile_id"])
    op.create_index("ix_content_ratings_content_id", "content_ratings", ["content_id"])
    op.create_index("ix_content_ratings_content", "content_ratings", ["content_id", "score"])

    op.create_table(
        "download_licenses",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=True),
        sa.Column("video_asset_id", sa.Uuid(), nullable=False),
        sa.Column("quality", sa.String(length=30), server_default="720p", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="authorized", nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bytes_downloaded", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("bytes_downloaded >= 0", name="ck_download_licenses_bytes_non_negative"),
        sa.ForeignKeyConstraint(["content_id"], ["content.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["episode_id"], ["episodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["viewer_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_asset_id"], ["video_assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_download_licenses_token_hash"),
    )
    for column in (
        "user_id",
        "profile_id",
        "device_id",
        "content_id",
        "episode_id",
        "video_asset_id",
        "token_hash",
        "expires_at",
        "status",
    ):
        op.create_index(f"ix_download_licenses_{column}", "download_licenses", [column])
    op.create_index("ix_download_licenses_user_status", "download_licenses", ["user_id", "status"])
    op.create_index(
        "ix_download_licenses_expiry", "download_licenses", ["expires_at", "revoked_at"]
    )

    op.create_table(
        "cast_sessions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("playback_session_id", sa.Uuid(), nullable=True),
        sa.Column("target_device_id", sa.String(length=200), nullable=False),
        sa.Column("target_device_name", sa.String(length=160), nullable=False),
        sa.Column("target_type", sa.String(length=30), server_default="chromecast", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="connected", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["playback_session_id"], ["playback_sessions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["viewer_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("user_id", "profile_id", "device_id", "playback_session_id", "status"):
        op.create_index(f"ix_cast_sessions_{column}", "cast_sessions", [column])
    op.create_index("ix_cast_sessions_user_status", "cast_sessions", ["user_id", "status"])

    op.execute(
        sa.text(
            "UPDATE feature_flags SET enabled = true, rollout_percentage = 100 "
            "WHERE key IN ('multi_profile_enabled','kids_mode_enabled','ratings_enabled',"
            "'downloads_enabled','chromecast_enabled','airplay_enabled')"
        )
    )


def downgrade() -> None:
    op.drop_table("cast_sessions")
    op.drop_table("download_licenses")
    op.drop_table("content_ratings")
    op.drop_table("viewer_profiles")
    op.drop_column("content", "rating_count")

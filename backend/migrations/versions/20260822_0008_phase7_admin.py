"""phase 7 administration

Revision ID: 20260822_0008
Revises: 20260821_0007
Create Date: 2026-08-22 00:00:00
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260822_0008"
down_revision: str | None = "20260821_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_NAMESPACE = uuid.UUID("568b998e-a294-42f8-85b6-227e66e707b7")


def stable_id(kind: str, name: str) -> uuid.UUID:
    return uuid.uuid5(UUID_NAMESPACE, f"{kind}:{name}")


def timestamp_columns() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.add_column("users", sa.Column("country_code", sa.String(length=2), nullable=True))
    op.add_column("users", sa.Column("language_code", sa.String(length=16), nullable=True))
    op.create_index("ix_users_country_code", "users", ["country_code"], unique=False)
    op.create_index("ix_users_language_code", "users", ["language_code"], unique=False)

    op.create_table(
        "homepage_sections",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("algorithm", sa.String(length=50), nullable=False),
        sa.Column("presentation", sa.String(length=30), server_default="poster", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_items", sa.Integer(), server_default="20", nullable=False),
        sa.Column("genre_id", sa.Uuid(), nullable=True),
        sa.Column(
            "target_countries", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False
        ),
        sa.Column(
            "target_languages", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False
        ),
        sa.Column("target_subscription", sa.String(length=30), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at >= starts_at",
            name="ck_homepage_sections_schedule_range",
        ),
        sa.CheckConstraint(
            "max_items >= 1 AND max_items <= 50",
            name="ck_homepage_sections_max_items_range",
        ),
        sa.ForeignKeyConstraint(
            ["genre_id"], ["genres.id"], name="fk_homepage_sections_genre_id", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_homepage_sections"),
    )
    op.create_index(
        "ix_homepage_sections_active_order",
        "homepage_sections",
        ["active", "sort_order"],
        unique=False,
    )
    op.create_index(
        "ix_homepage_sections_algorithm", "homepage_sections", ["algorithm"], unique=False
    )
    op.create_index("ix_homepage_sections_ends_at", "homepage_sections", ["ends_at"], unique=False)
    op.create_index(
        "ix_homepage_sections_genre_id", "homepage_sections", ["genre_id"], unique=False
    )
    op.create_index("ix_homepage_sections_key", "homepage_sections", ["key"], unique=True)
    op.create_index(
        "ix_homepage_sections_starts_at", "homepage_sections", ["starts_at"], unique=False
    )

    op.create_table(
        "homepage_section_items",
        sa.Column("section_id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["content.id"],
            name="fk_homepage_section_items_content_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["section_id"],
            ["homepage_sections.id"],
            name="fk_homepage_section_items_section_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_homepage_section_items"),
        sa.UniqueConstraint("section_id", "content_id", name="uq_homepage_section_content"),
    )
    op.create_index(
        "ix_homepage_section_items_content_id",
        "homepage_section_items",
        ["content_id"],
        unique=False,
    )
    op.create_index(
        "ix_homepage_section_items_order",
        "homepage_section_items",
        ["section_id", "sort_order"],
        unique=False,
    )
    op.create_index(
        "ix_homepage_section_items_section_id",
        "homepage_section_items",
        ["section_id"],
        unique=False,
    )

    op.create_table(
        "notification_campaigns",
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("image_url", sa.String(length=2048), nullable=True),
        sa.Column("action_url", sa.String(length=2048), nullable=True),
        sa.Column("audience", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("channels", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("recipient_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failure_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("metadata", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "failure_count >= 0", name="ck_notification_campaigns_failure_count_non_negative"
        ),
        sa.CheckConstraint(
            "recipient_count >= 0",
            name="ck_notification_campaigns_recipient_count_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_notification_campaigns_created_by_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notification_campaigns"),
    )
    op.create_index(
        "ix_notification_campaigns_created_by_id",
        "notification_campaigns",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_campaigns_scheduled_at",
        "notification_campaigns",
        ["scheduled_at"],
        unique=False,
    )
    op.create_index(
        "ix_notification_campaigns_sent_at",
        "notification_campaigns",
        ["sent_at"],
        unique=False,
    )
    op.create_index(
        "ix_notification_campaigns_status_schedule",
        "notification_campaigns",
        ["status", "scheduled_at"],
        unique=False,
    )
    op.create_index(
        "ix_notification_campaigns_type", "notification_campaigns", ["type"], unique=False
    )

    sections = sa.table(
        "homepage_sections",
        sa.column("id", sa.Uuid()),
        sa.column("key", sa.String()),
        sa.column("title", sa.String()),
        sa.column("algorithm", sa.String()),
        sa.column("presentation", sa.String()),
        sa.column("active", sa.Boolean()),
        sa.column("sort_order", sa.Integer()),
        sa.column("max_items", sa.Integer()),
        sa.column("target_countries", sa.JSON()),
        sa.column("target_languages", sa.JSON()),
    )
    defaults = [
        ("continue_watching", "Continue Watching", "continue_watching", "progress", 0),
        ("trending", "Trending Now", "trending", "poster", 10),
        ("top_10", "Top 10 Today", "top_10", "ranked", 20),
        ("new_releases", "New Releases", "latest", "poster", 30),
        ("premium_originals", "Premium Originals", "manual", "wide", 40),
    ]
    op.bulk_insert(
        sections,
        [
            {
                "id": stable_id("homepage_section", key),
                "key": key,
                "title": title,
                "algorithm": algorithm,
                "presentation": presentation,
                "active": True,
                "sort_order": sort_order,
                "max_items": 20,
                "target_countries": op.inline_literal(json.dumps([])),
                "target_languages": op.inline_literal(json.dumps([])),
            }
            for key, title, algorithm, presentation, sort_order in defaults
        ],
        multiinsert=False,
    )


def downgrade() -> None:
    op.drop_index("ix_notification_campaigns_type", table_name="notification_campaigns")
    op.drop_index("ix_notification_campaigns_status_schedule", table_name="notification_campaigns")
    op.drop_index("ix_notification_campaigns_sent_at", table_name="notification_campaigns")
    op.drop_index("ix_notification_campaigns_scheduled_at", table_name="notification_campaigns")
    op.drop_index("ix_notification_campaigns_created_by_id", table_name="notification_campaigns")
    op.drop_table("notification_campaigns")
    op.drop_index("ix_homepage_section_items_section_id", table_name="homepage_section_items")
    op.drop_index("ix_homepage_section_items_order", table_name="homepage_section_items")
    op.drop_index("ix_homepage_section_items_content_id", table_name="homepage_section_items")
    op.drop_table("homepage_section_items")
    op.drop_index("ix_homepage_sections_starts_at", table_name="homepage_sections")
    op.drop_index("ix_homepage_sections_key", table_name="homepage_sections")
    op.drop_index("ix_homepage_sections_genre_id", table_name="homepage_sections")
    op.drop_index("ix_homepage_sections_ends_at", table_name="homepage_sections")
    op.drop_index("ix_homepage_sections_algorithm", table_name="homepage_sections")
    op.drop_index("ix_homepage_sections_active_order", table_name="homepage_sections")
    op.drop_table("homepage_sections")
    op.drop_index("ix_users_language_code", table_name="users")
    op.drop_index("ix_users_country_code", table_name="users")
    op.drop_column("users", "language_code")
    op.drop_column("users", "country_code")

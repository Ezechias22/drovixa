"""phase 1 foundation

Revision ID: 20260812_0001
Revises:
Create Date: 2026-08-12 00:00:00
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_NAMESPACE = uuid.UUID("568b998e-a294-42f8-85b6-227e66e707b7")


def stable_id(kind: str, name: str) -> uuid.UUID:
    return uuid.uuid5(UUID_NAMESPACE, f"{kind}:{name}")


def timestamp_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), server_default=sa.true(), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
    )
    op.create_index("ix_roles_name", "roles", ["name"], unique=True)

    op.create_table(
        "permissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_permissions"),
    )
    op.create_index("ix_permissions_code", "permissions", ["code"], unique=True)

    user_status = sa.Enum(
        "active",
        "suspended",
        "banned",
        "deleted",
        name="userstatus",
        native_enum=False,
        length=20,
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("status", user_status, server_default="active", nullable=False),
        sa.Column("email_verified", sa.Boolean(), server_default=sa.false(), nullable=False),
        *timestamp_columns(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_status_deleted_at", "users", ["status", "deleted_at"])

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("permission_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )

    op.create_table(
        "devices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.String(160), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("platform", sa.String(30), nullable=False),
        sa.Column("last_ip", sa.String(64), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_devices"),
        sa.UniqueConstraint("user_id", "device_id", name="uq_devices_user_device"),
    )
    op.create_index("ix_devices_user_id", "devices", ["user_id"])

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(80), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_user_sessions"),
    )
    op.create_index("ix_user_sessions_device_id", "user_sessions", ["device_id"])
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_active", "user_sessions", ["user_id", "revoked_at"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_token_id", sa.Uuid(), nullable=True),
        sa.Column("reuse_detected_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["session_id"], ["user_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_refresh_tokens"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_session_id", "refresh_tokens", ["session_id"])
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])
    op.create_index(
        "ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True
    )
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])
    op.create_index(
        "ix_refresh_tokens_session_active", "refresh_tokens", ["session_id", "revoked_at"]
    )

    op.create_table(
        "feature_flags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("rollout_percentage", sa.Integer(), server_default="100", nullable=False),
        sa.Column("rules", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "rollout_percentage >= 0 AND rollout_percentage <= 100",
            name="valid_rollout_percentage",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_feature_flags"),
    )
    op.create_index("ix_feature_flags_key", "feature_flags", ["key"], unique=True)

    op.create_table(
        "remote_config",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_public", sa.Boolean(), server_default=sa.true(), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_remote_config"),
    )
    op.create_index("ix_remote_config_key", "remote_config", ["key"], unique=True)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("admin_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.String(120), nullable=False),
        sa.Column("old_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
    )
    op.create_index("ix_audit_logs_admin_id", "audit_logs", ["admin_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])

    seed_foundation_data()


def seed_foundation_data() -> None:
    permission_descriptions = {
        "content.view": "View content administration",
        "content.create": "Create content",
        "content.edit": "Edit content",
        "content.delete": "Archive or delete content",
        "content.publish": "Publish content",
        "users.view": "View users",
        "users.suspend": "Suspend or restore users",
        "wallet.view": "View wallet information",
        "wallet.adjust": "Make audited wallet adjustments",
        "payments.view": "View payment records",
        "payments.refund": "Issue payment refunds",
        "subscriptions.manage": "Manage subscriptions",
        "comments.moderate": "Moderate comments",
        "reports.manage": "Manage reports",
        "notifications.manage": "Manage notification campaigns",
        "settings.view": "View private platform settings",
        "settings.manage": "Change platform settings",
        "admins.manage": "Manage administrators",
        "roles.manage": "Manage roles and permissions",
        "audit.view": "View audit logs",
        "analytics.view": "View administrative analytics",
        "support.manage": "Manage support tickets",
    }
    role_permissions = {
        "guest": set(),
        "user": set(),
        "premium_user": set(),
        "moderator": {"comments.moderate", "reports.manage", "content.view"},
        "content_manager": {
            "content.view", "content.create", "content.edit", "content.delete",
            "content.publish", "analytics.view",
        },
        "support_agent": {"users.view", "support.manage", "reports.manage"},
        "finance_admin": {
            "users.view", "wallet.view", "wallet.adjust", "payments.view",
            "payments.refund", "subscriptions.manage", "analytics.view",
        },
        "admin": set(permission_descriptions) - {"admins.manage", "roles.manage"},
        "super_admin": set(permission_descriptions),
    }
    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("description", sa.Text()),
    )
    roles_table = sa.table(
        "roles",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("is_system", sa.Boolean()),
    )
    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Uuid()),
        sa.column("permission_id", sa.Uuid()),
    )
    op.bulk_insert(
        permissions_table,
        [
            {"id": stable_id("permission", code), "code": code, "description": description}
            for code, description in permission_descriptions.items()
        ],
    )
    op.bulk_insert(
        roles_table,
        [
            {
                "id": stable_id("role", role),
                "name": role,
                "description": f"System {role.replace('_', ' ')} role",
                "is_system": True,
            }
            for role in role_permissions
        ],
    )
    op.bulk_insert(
        role_permissions_table,
        [
            {
                "role_id": stable_id("role", role),
                "permission_id": stable_id("permission", permission),
            }
            for role, permissions in role_permissions.items()
            for permission in sorted(permissions)
        ],
    )

    flags_table = sa.table(
        "feature_flags",
        sa.column("id", sa.Uuid()),
        sa.column("key", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("enabled", sa.Boolean()),
        sa.column("rollout_percentage", sa.Integer()),
        sa.column("rules", sa.JSON()),
    )
    flags = [
        "comments_enabled", "downloads_enabled", "coins_enabled",
        "subscriptions_enabled", "ads_enabled", "guest_mode_enabled",
        "registration_enabled", "social_login_enabled", "share_enabled",
        "referrals_enabled", "daily_rewards_enabled", "ratings_enabled",
        "multi_profile_enabled", "kids_mode_enabled", "watch_party_enabled",
        "chromecast_enabled", "airplay_enabled", "maintenance_mode",
    ]
    enabled_by_default = {"guest_mode_enabled", "registration_enabled", "share_enabled"}
    op.bulk_insert(
        flags_table,
        [
            {
                "id": stable_id("feature", key),
                "key": key,
                "description": f"Controls the {key.removesuffix('_enabled').replace('_', ' ')} module",
                "enabled": key in enabled_by_default,
                "rollout_percentage": 100,
                "rules": op.inline_literal(json.dumps({})),
            }
            for key in flags
        ],
        multiinsert=False,
    )

    config_table = sa.table(
        "remote_config",
        sa.column("id", sa.Uuid()),
        sa.column("key", sa.String()),
        sa.column("value", sa.JSON()),
        sa.column("description", sa.Text()),
        sa.column("is_public", sa.Boolean()),
    )
    config_values = {
        "minimum_app_version": "1.0.0",
        "latest_app_version": "1.0.0",
        "force_update": False,
        "maintenance_message": "System temporarily unavailable. Please try again later.",
        "accent_color": "#FF3D71",
        "support_email": "support@drovixa.com",
        "terms_url": "https://drovixa.com/terms",
        "privacy_url": "https://drovixa.com/privacy",
        "default_language": "en",
        "default_coin_price": 0,
        "watch_completion_percentage": 90,
        "progress_sync_interval": 15,
        "ads_frequency": 3,
    }
    op.bulk_insert(
        config_table,
        [
            {
                "id": stable_id("config", key),
                "key": key,
                "value": op.inline_literal(json.dumps(value)),
                "description": f"Runtime setting: {key.replace('_', ' ')}",
                "is_public": True,
            }
            for key, value in config_values.items()
        ],
        multiinsert=False,
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("remote_config")
    op.drop_table("feature_flags")
    op.drop_table("refresh_tokens")
    op.drop_table("user_sessions")
    op.drop_table("devices")
    op.drop_table("role_permissions")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("permissions")
    op.drop_table("roles")

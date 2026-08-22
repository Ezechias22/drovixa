"""phase 3.1 Mux provider

Revision ID: 20260813_0004
Revises: 20260813_0003
Create Date: 2026-08-13 22:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0004"
down_revision: str | None = "20260813_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE upload_protocol ADD VALUE IF NOT EXISTS 'resumable'")


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return
    resumable_count = connection.scalar(
        sa.text(
            "SELECT count(*) FROM video_upload_sessions "
            "WHERE protocol::text = 'resumable'"
        )
    )
    if resumable_count:
        raise RuntimeError(
            "Cannot downgrade while Mux resumable upload sessions exist. "
            "Preserve the current migration or archive those sessions first."
        )
    op.execute("ALTER TYPE upload_protocol RENAME TO upload_protocol_with_resumable")
    op.execute("CREATE TYPE upload_protocol AS ENUM ('basic', 'tus')")
    op.execute(
        "ALTER TABLE video_upload_sessions ALTER COLUMN protocol TYPE upload_protocol "
        "USING protocol::text::upload_protocol"
    )
    op.execute("DROP TYPE upload_protocol_with_resumable")

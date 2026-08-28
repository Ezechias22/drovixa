"""phase 12.4 durable content cover media

Revision ID: 20260827_0013
Revises: 20260825_0012
Create Date: 2026-08-27 21:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_0013"
down_revision: str | None = "20260825_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_media",
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("variant", sa.String(length=30), nullable=False),
        sa.Column("mime_type", sa.String(length=80), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("image_data", sa.LargeBinary(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "byte_size > 0 AND byte_size <= 1800000",
            name="ck_content_media_byte_size_range",
        ),
        sa.ForeignKeyConstraint(["content_id"], ["content.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_content_media_content_id", "content_media", ["content_id"])
    op.create_index("ix_content_media_created_by_id", "content_media", ["created_by_id"])
    op.create_index("ix_content_media_variant", "content_media", ["variant"])
    op.create_index(
        "ix_content_media_content_variant", "content_media", ["content_id", "variant"]
    )


def downgrade() -> None:
    op.drop_index("ix_content_media_content_variant", table_name="content_media")
    op.drop_index("ix_content_media_variant", table_name="content_media")
    op.drop_index("ix_content_media_created_by_id", table_name="content_media")
    op.drop_index("ix_content_media_content_id", table_name="content_media")
    op.drop_table("content_media")

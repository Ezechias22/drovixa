"""phase 12.8 viewer profile photos

Revision ID: 20260829_0014
Revises: 20260827_0013
Create Date: 2026-08-29 01:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260829_0014"
down_revision: str | None = "20260827_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_url", sa.String(length=2048), nullable=True))
    op.create_table(
        "user_avatars",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("mime_type", sa.String(length=80), nullable=False),
        sa.Column("image_data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_avatars")
    op.drop_column("users", "avatar_url")

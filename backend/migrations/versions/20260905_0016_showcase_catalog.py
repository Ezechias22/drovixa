"""multilingual removable showcase catalog

Revision ID: 20260905_0016
Revises: 20260830_0015
Create Date: 2026-09-05 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260905_0016"
down_revision: str | None = "20260830_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "content",
        sa.Column("translations", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
    )
    op.add_column("content", sa.Column("demo_batch", sa.String(length=80), nullable=True))
    op.create_index(op.f("ix_content_demo_batch"), "content", ["demo_batch"], unique=False)
    op.add_column(
        "episodes",
        sa.Column("translations", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("episodes", "translations")
    op.drop_index(op.f("ix_content_demo_batch"), table_name="content")
    op.drop_column("content", "demo_batch")
    op.drop_column("content", "translations")

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, CheckConstraint, String, Text
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class FeatureFlag(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "feature_flags"
    __table_args__ = (
        CheckConstraint(
            "rollout_percentage >= 0 AND rollout_percentage <= 100",
            name="valid_rollout_percentage",
        ),
    )

    key: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    rollout_percentage: Mapped[int] = mapped_column(default=100, nullable=False)
    rules: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )


class RemoteConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "remote_config"

    key: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(default=True, nullable=False)

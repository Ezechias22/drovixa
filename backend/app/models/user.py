from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import UserStatus
from app.models.rbac import user_roles

if TYPE_CHECKING:
    from app.models.auth import Device, UserSession
    from app.models.rbac import Role


class User(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_status_deleted_at", "status", "deleted_at"),)

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        Enum(
            UserStatus,
            native_enum=False,
            length=20,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=UserStatus.ACTIVE,
        nullable=False,
    )
    email_verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(2), index=True)
    language_code: Mapped[str | None] = mapped_column(String(16), index=True)

    roles: Mapped[list[Role]] = relationship(
        secondary=user_roles, back_populates="users", lazy="selectin"
    )
    devices: Mapped[list[Device]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    sessions: Mapped[list[UserSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def permission_codes(self) -> set[str]:
        return {permission.code for role in self.roles for permission in role.permissions}

    @property
    def role_names(self) -> set[str]:
        return {role.name for role in self.roles}

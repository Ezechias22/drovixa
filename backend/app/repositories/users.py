from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from app.models.rbac import Role
from app.models.user import User


def user_load_options() -> tuple[ORMOption, ...]:
    return (selectinload(User.roles).selectinload(Role.permissions),)


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email).options(*user_load_options()))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id).options(*user_load_options()))
    return result.scalar_one_or_none()


async def get_role_by_name(db: AsyncSession, name: str) -> Role | None:
    result = await db.execute(
        select(Role).where(Role.name == name).options(selectinload(Role.permissions))
    )
    return result.scalar_one_or_none()

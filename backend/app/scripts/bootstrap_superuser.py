from __future__ import annotations

import asyncio

from sqlalchemy import insert, select, update

from app.core.config import get_settings
from app.core.database import SessionFactory, dispose_database
from app.core.security import hash_password, normalize_email, utcnow
from app.models.auth import RefreshToken, UserSession
from app.models.enums import UserStatus
from app.models.monetization import Wallet
from app.models.notifications import PushToken
from app.models.rbac import user_roles
from app.models.user import User
from app.repositories.users import get_role_by_name, get_user_by_email


async def bootstrap() -> None:
    settings = get_settings()
    if not settings.FIRST_SUPERUSER_EMAIL or not settings.FIRST_SUPERUSER_PASSWORD:
        raise RuntimeError("FIRST_SUPERUSER_EMAIL and FIRST_SUPERUSER_PASSWORD are required")
    if len(settings.FIRST_SUPERUSER_PASSWORD) < 12:
        raise RuntimeError("FIRST_SUPERUSER_PASSWORD must contain at least 12 characters")
    async with SessionFactory() as db:
        role = await get_role_by_name(db, "super_admin")
        if role is None:
            raise RuntimeError("Run `alembic upgrade head` before bootstrapping")
        email = normalize_email(settings.FIRST_SUPERUSER_EMAIL)
        user = await get_user_by_email(db, email)
        created = user is None
        if user is None:
            user = User(
                email=email,
                name=settings.FIRST_SUPERUSER_NAME.strip(),
                password_hash=hash_password(settings.FIRST_SUPERUSER_PASSWORD),
                status=UserStatus.ACTIVE,
                email_verified=True,
            )
            db.add(user)
            await db.flush()
            db.add(Wallet(user_id=user.id))
        role_link = await db.scalar(
            select(user_roles.c.user_id).where(
                user_roles.c.user_id == user.id,
                user_roles.c.role_id == role.id,
            )
        )
        if role_link is None:
            await db.execute(insert(user_roles).values(user_id=user.id, role_id=role.id))
        user.password_hash = hash_password(settings.FIRST_SUPERUSER_PASSWORD)
        user.status = UserStatus.ACTIVE
        user.deleted_at = None
        user.email_verified = True
        if not created:
            now = utcnow()
            await db.execute(
                update(UserSession)
                .where(
                    UserSession.user_id == user.id,
                    UserSession.revoked_at.is_(None),
                )
                .values(
                    revoked_at=now,
                    revoke_reason="superuser_bootstrap_reset",
                )
            )
            await db.execute(
                update(RefreshToken)
                .where(
                    RefreshToken.user_id == user.id,
                    RefreshToken.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
            await db.execute(
                update(PushToken)
                .where(PushToken.user_id == user.id, PushToken.active.is_(True))
                .values(active=False, disabled_at=now)
            )
        await db.commit()
        action = "created" if created else "reset"
        print(f"Super administrator {action}: {email}")


async def main() -> None:
    try:
        await bootstrap()
    finally:
        await dispose_database()


if __name__ == "__main__":
    asyncio.run(main())

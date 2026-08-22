from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import SessionFactory
from app.core.security import verify_password
from app.models.monetization import Wallet
from app.models.user import User
from app.scripts import bootstrap_superuser


async def test_bootstrap_creates_and_resets_superuser_without_async_lazy_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        FIRST_SUPERUSER_EMAIL="owner@drovixa.example",
        FIRST_SUPERUSER_PASSWORD="first-secure-password",
        FIRST_SUPERUSER_NAME="Drovixa Owner",
    )
    monkeypatch.setattr(bootstrap_superuser, "get_settings", lambda: settings)

    await bootstrap_superuser.bootstrap()
    settings.FIRST_SUPERUSER_PASSWORD = "second-secure-password"
    await bootstrap_superuser.bootstrap()

    async with SessionFactory() as db:
        user = await db.scalar(
            select(User)
            .where(User.email == "owner@drovixa.example")
            .options(selectinload(User.roles))
        )
        assert user is not None
        assert user.status.value == "active"
        assert {role.name for role in user.roles} == {"super_admin"}
        assert verify_password("second-secure-password", user.password_hash)
        assert await db.get(Wallet, user.id) is not None


async def test_bootstrap_once_keeps_existing_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        FIRST_SUPERUSER_EMAIL="free-owner@drovixa.example",
        FIRST_SUPERUSER_PASSWORD="first-secure-password",
        FIRST_SUPERUSER_NAME="Drovixa Owner",
    )
    monkeypatch.setattr(bootstrap_superuser, "get_settings", lambda: settings)

    await bootstrap_superuser.bootstrap(reset_existing_password=False)
    settings.FIRST_SUPERUSER_PASSWORD = "a-different-render-secret"
    await bootstrap_superuser.bootstrap(reset_existing_password=False)

    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == settings.FIRST_SUPERUSER_EMAIL))
        assert user is not None
        assert verify_password("first-secure-password", user.password_hash)
        assert not verify_password("a-different-render-secret", user.password_hash)

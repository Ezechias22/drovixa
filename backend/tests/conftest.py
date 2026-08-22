from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

os.environ.update(
    {
        "APP_ENV": "testing",
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "JWT_SECRET": "test-jwt-secret-that-is-long-enough-123456",
        "REFRESH_SECRET": "test-refresh-secret-that-is-different-654321",
        "RATE_LIMIT_ENABLED": "false",
        "HEALTHCHECK_REDIS_REQUIRED": "false",
        "TRUSTED_HOSTS": '["localhost","test"]',
    }
)

from app.core.database import SessionFactory, engine
from app.core.permissions import PERMISSIONS, ROLE_PERMISSIONS
from app.main import app
from app.models.base import Base
from app.models.community import ReportReason
from app.models.configuration import FeatureFlag, RemoteConfig
from app.models.rbac import Permission, Role
from app.models.user import User


@pytest.fixture(autouse=True)
async def reset_database() -> AsyncIterator[None]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    async with SessionFactory() as db:
        permission_models = {
            code: Permission(code=code, description=description)
            for code, description in PERMISSIONS.items()
        }
        db.add_all(permission_models.values())
        for name, permission_codes in ROLE_PERMISSIONS.items():
            db.add(
                Role(
                    name=name,
                    description=f"System {name} role",
                    permissions=[permission_models[code] for code in sorted(permission_codes)],
                )
            )
        db.add_all(
            [
                FeatureFlag(
                    key="guest_mode_enabled",
                    description="Guest mode",
                    enabled=True,
                    rollout_percentage=100,
                    rules={},
                ),
                FeatureFlag(
                    key="comments_enabled",
                    description="Comments",
                    enabled=False,
                    rollout_percentage=100,
                    rules={},
                ),
                FeatureFlag(
                    key="registration_enabled",
                    description="Registration",
                    enabled=True,
                    rollout_percentage=100,
                    rules={},
                ),
                RemoteConfig(
                    key="accent_color",
                    value="#FF3D71",
                    description="Brand accent",
                    is_public=True,
                ),
                RemoteConfig(
                    key="internal_key",
                    value="private",
                    description="Private test value",
                    is_public=False,
                ),
            ]
        )
        target_types = [
            "comment",
            "user",
            "content",
            "episode",
            "video",
            "subtitle",
            "technical",
        ]
        db.add_all(
            [
                ReportReason(
                    code="inappropriate",
                    label="Inappropriate content",
                    target_types=target_types,
                    active=True,
                    sort_order=0,
                ),
                ReportReason(
                    code="spam",
                    label="Spam or misleading",
                    target_types=target_types,
                    active=True,
                    sort_order=1,
                ),
                ReportReason(
                    code="technical_issue",
                    label="Technical problem",
                    target_types=target_types,
                    active=True,
                    sort_order=2,
                ),
            ]
        )
        await db.commit()
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as http_client:
        yield http_client


@pytest.fixture
def register_payload() -> dict[str, object]:
    return {
        "email": "viewer@example.com",
        "name": "Drovixa Viewer",
        "password": "securepass123",
        "device": {
            "device_id": "device-12345678",
            "name": "Test Phone",
            "platform": "android",
        },
    }


@pytest.fixture
async def registered(client: AsyncClient, register_payload: dict[str, object]) -> dict[str, object]:
    response = await client.post("/api/v1/auth/register", json=register_payload)
    assert response.status_code == 201
    return response.json()["data"]


@pytest.fixture
async def admin_headers(db: AsyncSession, registered: dict[str, object]) -> dict[str, str]:
    user = await db.scalar(
        select(User).where(User.email == "viewer@example.com").options(selectinload(User.roles))
    )
    role = await db.scalar(select(Role).where(Role.name == "super_admin"))
    assert user is not None and role is not None
    user.roles.append(role)
    await db.commit()
    return {"Authorization": f"Bearer {registered['access_token']}"}

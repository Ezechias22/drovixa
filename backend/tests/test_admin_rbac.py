from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit import AuditLog
from app.models.rbac import Role
from app.models.user import User


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_regular_user_cannot_access_admin_settings(
    client: AsyncClient, registered: dict[str, object]
) -> None:
    response = await client.get(
        "/api/v1/admin/feature-flags",
        headers=auth_header(str(registered["access_token"])),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_super_admin_updates_flag_and_writes_audit(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
) -> None:
    user = await db.scalar(
        select(User).where(User.email == "viewer@example.com").options(selectinload(User.roles))
    )
    super_role = await db.scalar(select(Role).where(Role.name == "super_admin"))
    assert user is not None and super_role is not None
    user.roles.append(super_role)
    await db.commit()

    response = await client.patch(
        "/api/v1/admin/feature-flags/comments_enabled",
        headers=auth_header(str(registered["access_token"])),
        json={"enabled": True, "rollout_percentage": 25, "rules": {"countries": ["BR"]}},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["enabled"] is True
    assert data["rollout_percentage"] == 25

    public = await client.get("/api/v1/feature-flags")
    assert public.json()["data"]["comments_enabled"]["rules"] == {"countries": ["BR"]}
    audit_count = await db.scalar(select(func.count()).select_from(AuditLog))
    assert audit_count == 1


async def test_admin_cannot_create_arbitrary_config_keys(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
) -> None:
    user = await db.scalar(
        select(User).where(User.email == "viewer@example.com").options(selectinload(User.roles))
    )
    role = await db.scalar(select(Role).where(Role.name == "super_admin"))
    assert user is not None and role is not None
    user.roles.append(role)
    await db.commit()

    response = await client.patch(
        "/api/v1/admin/remote-config/not-registered",
        headers=auth_header(str(registered["access_token"])),
        json={"value": "unsafe"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_super_admin_reads_and_updates_remote_config(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
) -> None:
    user = await db.scalar(
        select(User).where(User.email == "viewer@example.com").options(selectinload(User.roles))
    )
    role = await db.scalar(select(Role).where(Role.name == "super_admin"))
    assert user is not None and role is not None
    user.roles.append(role)
    await db.commit()
    headers = auth_header(str(registered["access_token"]))

    flags = await client.get("/api/v1/admin/feature-flags", headers=headers)
    config = await client.get("/api/v1/admin/remote-config", headers=headers)
    updated = await client.patch(
        "/api/v1/admin/remote-config/accent_color",
        headers=headers,
        json={"value": "#7C3AED", "is_public": True},
    )
    assert flags.status_code == 200
    assert config.status_code == 200
    assert any(item["key"] == "internal_key" for item in config.json()["data"])
    assert updated.status_code == 200
    assert updated.json()["data"]["value"] == "#7C3AED"

    public = await client.get("/api/v1/remote-config")
    assert public.json()["data"]["accent_color"] == "#7C3AED"
    audit_count = await db.scalar(select(func.count()).select_from(AuditLog))
    assert audit_count == 1

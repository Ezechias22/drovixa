from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_refresh_token, utcnow
from app.models.auth import Device, RefreshToken, UserSession
from app.models.configuration import FeatureFlag
from app.models.enums import UserStatus
from app.models.rbac import Role
from app.models.user import User


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_register_me_update_and_password_is_hashed(
    client: AsyncClient,
    db: AsyncSession,
    register_payload: dict[str, object],
) -> None:
    response = await client.post("/api/v1/auth/register", json=register_payload)
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 1200
    assert data["user"]["roles"] == ["user"]

    user = await db.scalar(select(User).where(User.email == "viewer@example.com"))
    assert user is not None
    assert user.password_hash != register_payload["password"]

    me = await client.get("/api/v1/users/me", headers=auth_header(data["access_token"]))
    assert me.status_code == 200
    assert me.json()["data"]["email"] == "viewer@example.com"

    updated = await client.patch(
        "/api/v1/users/me",
        headers=auth_header(data["access_token"]),
        json={"name": "New Viewer Name", "country_code": "ht", "language_code": "HT"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "New Viewer Name"
    assert updated.json()["data"]["country_code"] == "HT"
    assert updated.json()["data"]["language_code"] == "ht"


async def test_duplicate_registration_and_invalid_login_are_safe(
    client: AsyncClient, register_payload: dict[str, object]
) -> None:
    first = await client.post("/api/v1/auth/register", json=register_payload)
    assert first.status_code == 201
    duplicate = await client.post("/api/v1/auth/register", json=register_payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"

    bad_login = await client.post(
        "/api/v1/auth/login",
        json={**register_payload, "password": "wrong-password"},
    )
    assert bad_login.status_code == 401
    assert bad_login.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_refresh_rotation_hashing_and_reuse_revokes_family(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
) -> None:
    first_refresh = str(registered["refresh_token"])
    stored = await db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(first_refresh))
    )
    assert stored is not None
    assert stored.token_hash != first_refresh

    rotated = await client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert rotated.status_code == 200
    second_refresh = rotated.json()["data"]["refresh_token"]
    assert second_refresh != first_refresh

    reused = await client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "REFRESH_TOKEN_REUSED"

    family_revoked = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": second_refresh}
    )
    assert family_revoked.status_code == 401
    assert family_revoked.json()["error"]["code"] in {"SESSION_REVOKED", "REFRESH_TOKEN_REUSED"}


async def test_logout_revokes_access_session(
    client: AsyncClient, registered: dict[str, object]
) -> None:
    headers = auth_header(str(registered["access_token"]))
    response = await client.post("/api/v1/auth/logout", headers=headers)
    assert response.status_code == 200
    after = await client.get("/api/v1/users/me", headers=headers)
    assert after.status_code == 401
    assert after.json()["error"]["code"] == "SESSION_REVOKED"


async def test_device_inventory_and_logout(
    client: AsyncClient, registered: dict[str, object]
) -> None:
    headers = auth_header(str(registered["access_token"]))
    devices = await client.get("/api/v1/users/me/devices", headers=headers)
    assert devices.status_code == 200
    device = devices.json()["data"][0]
    assert device["current"] is True

    removed = await client.delete(f"/api/v1/users/me/devices/{device['id']}", headers=headers)
    assert removed.status_code == 200
    after = await client.get("/api/v1/users/me", headers=headers)
    assert after.status_code == 401


async def test_login_second_device_and_logout_all(
    client: AsyncClient,
    registered: dict[str, object],
    register_payload: dict[str, object],
) -> None:
    second_device = {
        "device_id": "web-device-87654321",
        "name": "Chrome",
        "platform": "web",
    }
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": register_payload["email"],
            "password": register_payload["password"],
            "device": second_device,
        },
    )
    assert login.status_code == 200
    second = login.json()["data"]
    devices = await client.get(
        "/api/v1/users/me/devices", headers=auth_header(second["access_token"])
    )
    assert len(devices.json()["data"]) == 2

    logout = await client.post(
        "/api/v1/auth/logout-all", headers=auth_header(second["access_token"])
    )
    assert logout.status_code == 200
    first_session = await client.get(
        "/api/v1/users/me", headers=auth_header(str(registered["access_token"]))
    )
    assert first_session.status_code == 401


async def test_invalid_tokens_validation_and_missing_device(
    client: AsyncClient, registered: dict[str, object]
) -> None:
    missing = await client.get("/api/v1/users/me")
    malformed = await client.get(
        "/api/v1/users/me", headers={"Authorization": "Bearer malformed.jwt.token"}
    )
    unknown_refresh = await client.post("/api/v1/auth/refresh", json={"refresh_token": "x" * 80})
    invalid_password = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "invalid@example.com",
            "name": "Invalid User",
            "password": "letters-only",
            "device": {
                "device_id": "device-invalid-123",
                "name": "Phone",
                "platform": "android",
            },
        },
    )
    headers = auth_header(str(registered["access_token"]))
    missing_device = await client.delete(
        "/api/v1/users/me/devices/00000000-0000-0000-0000-000000000001",
        headers=headers,
    )
    assert missing.status_code == 401
    assert malformed.status_code == 401
    assert unknown_refresh.status_code == 401
    assert invalid_password.status_code == 422
    assert missing_device.status_code == 404


async def test_suspended_account_is_blocked_immediately(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
    register_payload: dict[str, object],
) -> None:
    user = await db.scalar(select(User).where(User.email == "viewer@example.com"))
    assert user is not None
    user.status = UserStatus.SUSPENDED
    await db.commit()

    current = await client.get(
        "/api/v1/users/me", headers=auth_header(str(registered["access_token"]))
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": register_payload["email"],
            "password": register_payload["password"],
            "device": register_payload["device"],
        },
    )
    assert current.status_code == 403
    assert current.json()["error"]["code"] == "ACCOUNT_SUSPENDED"
    assert login.status_code == 403


async def test_registration_feature_flag_is_enforced_server_side(
    client: AsyncClient,
    db: AsyncSession,
    register_payload: dict[str, object],
) -> None:
    flag = await db.scalar(select(FeatureFlag).where(FeatureFlag.key == "registration_enabled"))
    assert flag is not None
    flag.enabled = False
    await db.commit()

    response = await client.post("/api/v1/auth/register", json=register_payload)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "REGISTRATION_DISABLED"


async def test_existing_device_is_updated_and_untrusted_forwarded_ip_is_ignored(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
    register_payload: dict[str, object],
) -> None:
    del registered
    login_payload = {
        **register_payload,
        "device": {
            **register_payload["device"],
            "name": "Renamed Android Phone",
            "platform": "android",
        },
    }
    response = await client.post(
        "/api/v1/auth/login",
        headers={"X-Forwarded-For": "203.0.113.10, 10.0.0.1"},
        json=login_payload,
    )
    assert response.status_code == 200
    device = await db.scalar(select(Device).where(Device.device_id == "device-12345678"))
    assert device is not None
    assert device.name == "Renamed Android Phone"
    assert device.last_ip == "127.0.0.1"


async def test_banned_and_deleted_accounts_cannot_login(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
    register_payload: dict[str, object],
) -> None:
    del registered
    user = await db.scalar(select(User).where(User.email == "viewer@example.com"))
    assert user is not None
    user.status = UserStatus.BANNED
    await db.commit()
    banned = await client.post("/api/v1/auth/login", json=register_payload)
    assert banned.status_code == 403
    assert banned.json()["error"]["code"] == "ACCOUNT_BANNED"

    user.status = UserStatus.DELETED
    await db.commit()
    deleted = await client.post("/api/v1/auth/login", json=register_payload)
    assert deleted.status_code == 403
    assert deleted.json()["error"]["code"] == "ACCOUNT_DELETED"


async def test_expired_refresh_token_is_revoked(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
) -> None:
    raw_refresh = str(registered["refresh_token"])
    token = await db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_refresh))
    )
    assert token is not None
    token.expires_at = utcnow() - timedelta(seconds=1)
    await db.commit()
    expired = await client.post("/api/v1/auth/refresh", json={"refresh_token": raw_refresh})
    assert expired.status_code == 401
    assert expired.json()["error"]["code"] == "REFRESH_TOKEN_EXPIRED"
    await db.refresh(token)
    assert token.revoked_at is not None


async def test_refresh_rejects_unavailable_account_and_revokes_session(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
) -> None:
    raw_refresh = str(registered["refresh_token"])
    user = await db.scalar(select(User).where(User.email == "viewer@example.com"))
    assert user is not None
    user.status = UserStatus.BANNED
    await db.commit()
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": raw_refresh})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_UNAVAILABLE"
    session = await db.scalar(select(UserSession).where(UserSession.user_id == user.id))
    token = await db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_refresh))
    )
    if session is not None:
        await db.refresh(session)
    if token is not None:
        await db.refresh(token)
    assert session is not None and session.revoked_at is not None
    assert token is not None and token.revoked_at is not None


async def test_registration_fails_if_default_role_is_missing(
    client: AsyncClient,
    db: AsyncSession,
    register_payload: dict[str, object],
) -> None:
    role = await db.scalar(select(Role).where(Role.name == "user"))
    assert role is not None
    await db.delete(role)
    await db.commit()
    response = await client.post("/api/v1/auth/register", json=register_payload)
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "SERVICE_MISCONFIGURED"

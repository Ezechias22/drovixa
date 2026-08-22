from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.network import client_ip
from app.models.audit import AuditLog
from app.models.user import User


def add_audit_log(
    db: AsyncSession,
    *,
    admin: User,
    request: Request,
    action: str,
    entity_type: str,
    entity_id: str,
    old_value: dict[str, Any] | None,
    new_value: dict[str, Any] | None,
) -> None:
    ip = client_ip(request)
    db.add(
        AuditLog(
            admin_id=admin.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
            ip=ip[:64] if ip else None,
            user_agent=request.headers.get("User-Agent", "")[:1000] or None,
        )
    )

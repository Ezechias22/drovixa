from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Request, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, require_permission
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.administration import (
    HomepageSection,
    HomepageSectionItem,
    NotificationCampaign,
)
from app.models.audit import AuditLog
from app.models.base import utcnow
from app.models.enums import UserStatus
from app.models.rbac import Role
from app.models.user import User
from app.schemas.administration import (
    AdminUserRolesUpdate,
    AdminUserStatusUpdate,
    HomepageItemCreate,
    HomepageReorderInput,
    HomepageSectionCreate,
    HomepageSectionUpdate,
    NotificationCampaignCreate,
    NotificationCampaignSendInput,
    NotificationCampaignUpdate,
)
from app.schemas.common import success
from app.services.administration import (
    analytics_overview,
    campaign_data,
    content_analytics,
    dashboard_metrics,
    dispatch_notification_campaign,
    ensure_homepage_content,
    homepage_section,
    homepage_section_data,
)
from app.services.audit import add_audit_log
from app.services.auth import revoke_all_user_sessions
from app.services.notifications import (
    campaign_delivery_summary,
    deliver_campaign_push,
    disable_user_push_tokens,
    push_provider_status,
)

router = APIRouter(prefix="/admin", tags=["Admin operations"])
AnalyticsViewer = Annotated[User, require_permission("analytics.view")]
UsersViewer = Annotated[User, require_permission("users.view")]
UsersManager = Annotated[User, require_permission("users.suspend")]
AdminsManager = Annotated[User, require_permission("admins.manage")]
HomepageViewer = Annotated[User, require_permission("content.view")]
HomepageManager = Annotated[User, require_permission("content.edit")]
NotificationManager = Annotated[User, require_permission("notifications.manage")]
AuditViewer = Annotated[User, require_permission("audit.view")]
Page = Annotated[int, Query(ge=1)]
Limit = Annotated[int, Query(ge=1, le=100)]


def _meta(page: int, limit: int, total: int) -> dict[str, int]:
    return {"page": page, "limit": limit, "total": total, "pages": (total + limit - 1) // limit}


def _user_data(row: User) -> dict[str, Any]:
    return {
        "id": row.id,
        "email": row.email,
        "name": row.name,
        "status": row.status,
        "email_verified": row.email_verified,
        "country_code": row.country_code,
        "language_code": row.language_code,
        "roles": sorted(row.role_names),
        "devices": len(row.devices),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


@router.get("/dashboard")
async def dashboard(_: AnalyticsViewer, db: DbSession) -> dict[str, Any]:
    return success(await dashboard_metrics(db))


@router.get("/analytics/overview")
async def admin_analytics_overview(
    _: AnalyticsViewer, db: DbSession, days: int = Query(default=30, ge=7, le=365)
) -> dict[str, Any]:
    return success(await analytics_overview(db, days=days))


@router.get("/analytics/content")
async def admin_content_analytics(
    _: AnalyticsViewer, db: DbSession, limit: int = Query(default=20, ge=1, le=100)
) -> dict[str, Any]:
    return success(await content_analytics(db, limit=limit))


@router.get("/users")
async def admin_users(
    _: UsersViewer,
    db: DbSession,
    page: Page = 1,
    limit: Limit = 20,
    q: str | None = Query(default=None, max_length=160),
    status_filter: UserStatus | None = Query(default=None, alias="status"),
    role: str | None = Query(default=None, max_length=50),
) -> dict[str, Any]:
    conditions: list[ColumnElement[bool]] = [User.deleted_at.is_(None)]
    if q:
        pattern = f"%{q.strip()}%"
        conditions.append(User.email.ilike(pattern) | User.name.ilike(pattern))
    if status_filter:
        conditions.append(User.status == status_filter)
    if role:
        conditions.append(User.roles.any(Role.name == role))
    total = int(await db.scalar(select(func.count(User.id)).where(*conditions)) or 0)
    rows = list(
        (
            await db.scalars(
                select(User)
                .where(*conditions)
                .options(selectinload(User.roles), selectinload(User.devices))
                .order_by(User.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        )
        .unique()
        .all()
    )
    return success([_user_data(row) for row in rows], meta=_meta(page, limit, total))


@router.get("/users/{user_id}")
async def admin_user(user_id: UUID, _: UsersViewer, db: DbSession) -> dict[str, Any]:
    row = await db.scalar(
        select(User)
        .where(User.id == user_id, User.deleted_at.is_(None))
        .options(selectinload(User.roles), selectinload(User.devices))
    )
    if row is None:
        raise AppError("NOT_FOUND", "User not found.", status_code=404)
    return success(_user_data(row))


async def _managed_user(db: DbSession, user_id: UUID) -> User:
    row = await db.scalar(
        select(User)
        .where(User.id == user_id, User.deleted_at.is_(None))
        .options(selectinload(User.roles), selectinload(User.devices))
        .with_for_update()
    )
    if row is None:
        raise AppError("NOT_FOUND", "User not found.", status_code=404)
    return row


@router.patch("/users/{user_id}/status")
async def update_user_status(
    user_id: UUID,
    payload: AdminUserStatusUpdate,
    request: Request,
    admin: UsersManager,
    db: DbSession,
) -> dict[str, Any]:
    row = await _managed_user(db, user_id)
    if row.id == admin.id:
        raise AppError("PROTECTED_ACCOUNT", "You cannot change your own status.", status_code=403)
    if "super_admin" in row.role_names:
        raise AppError("PROTECTED_ACCOUNT", "A super administrator is protected.", status_code=403)
    old = _user_data(row)
    row.status = payload.status
    if payload.status == UserStatus.DELETED:
        row.deleted_at = utcnow()
    else:
        row.deleted_at = None
    if payload.status != UserStatus.ACTIVE:
        await disable_user_push_tokens(db, user_id=row.id, commit=False)
        await revoke_all_user_sessions(db, row.id, reason=f"admin_{payload.status.value}")
    new = _user_data(row)
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="user.status.update",
        entity_type="user",
        entity_id=str(row.id),
        old_value=jsonable_encoder(old),
        new_value=jsonable_encoder({**new, "reason": payload.reason}),
    )
    await db.commit()
    return success(new)


@router.patch("/users/{user_id}/roles")
async def update_user_roles(
    user_id: UUID,
    payload: AdminUserRolesUpdate,
    request: Request,
    admin: AdminsManager,
    db: DbSession,
) -> dict[str, Any]:
    row = await _managed_user(db, user_id)
    if row.id == admin.id and "super_admin" not in payload.roles:
        raise AppError(
            "PROTECTED_ACCOUNT", "You cannot remove your own super_admin role.", status_code=403
        )
    roles = list(await db.scalars(select(Role).where(Role.name.in_(payload.roles))))
    if len(roles) != len(payload.roles):
        found = {role.name for role in roles}
        raise AppError(
            "INVALID_ROLE",
            "One or more roles do not exist.",
            status_code=422,
            details={"unknown": sorted(set(payload.roles) - found)},
        )
    old = _user_data(row)
    row.roles = roles
    await db.flush()
    new = _user_data(row)
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="user.roles.update",
        entity_type="user",
        entity_id=str(row.id),
        old_value=jsonable_encoder(old),
        new_value=jsonable_encoder(new),
    )
    await db.commit()
    return success(new)


@router.get("/roles")
async def admin_roles(_: UsersViewer, db: DbSession) -> dict[str, Any]:
    rows = list(
        (await db.scalars(select(Role).options(selectinload(Role.permissions)).order_by(Role.name)))
        .unique()
        .all()
    )
    return success(
        [
            {
                "id": row.id,
                "name": row.name,
                "description": row.description,
                "permissions": sorted(permission.code for permission in row.permissions),
            }
            for row in rows
        ]
    )


@router.get("/homepage/sections")
async def homepage_sections(_: HomepageViewer, db: DbSession) -> dict[str, Any]:
    rows = list(
        (
            await db.scalars(
                select(HomepageSection)
                .options(
                    selectinload(HomepageSection.items).selectinload(HomepageSectionItem.content)
                )
                .order_by(HomepageSection.sort_order, HomepageSection.created_at)
            )
        )
        .unique()
        .all()
    )
    return success([homepage_section_data(row) for row in rows])


@router.post("/homepage/sections", status_code=status.HTTP_201_CREATED)
async def create_homepage_section(
    payload: HomepageSectionCreate,
    request: Request,
    admin: HomepageManager,
    db: DbSession,
) -> dict[str, Any]:
    if await db.scalar(select(HomepageSection.id).where(HomepageSection.key == payload.key)):
        raise AppError("CONFLICT", "This homepage section key already exists.", status_code=409)
    row = HomepageSection(**payload.model_dump(), items=[])
    db.add(row)
    await db.flush()
    snapshot = homepage_section_data(row)
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="homepage_section.create",
        entity_type="homepage_section",
        entity_id=str(row.id),
        old_value=None,
        new_value=jsonable_encoder(snapshot),
    )
    await db.commit()
    return success(snapshot)


@router.patch("/homepage/sections/{section_id}")
async def update_homepage_section(
    section_id: UUID,
    payload: HomepageSectionUpdate,
    request: Request,
    admin: HomepageManager,
    db: DbSession,
) -> dict[str, Any]:
    row = await homepage_section(db, section_id, for_update=True)
    old = homepage_section_data(row)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    if row.algorithm == "genre" and row.genre_id is None:
        raise AppError("VALIDATION_ERROR", "genre_id is required.", status_code=422)
    if row.ends_at and row.starts_at and row.ends_at < row.starts_at:
        raise AppError("VALIDATION_ERROR", "ends_at must follow starts_at.", status_code=422)
    await db.flush()
    new = homepage_section_data(row)
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="homepage_section.update",
        entity_type="homepage_section",
        entity_id=str(row.id),
        old_value=jsonable_encoder(old),
        new_value=jsonable_encoder(new),
    )
    await db.commit()
    return success(new)


@router.delete("/homepage/sections/{section_id}")
async def archive_homepage_section(
    section_id: UUID, request: Request, admin: HomepageManager, db: DbSession
) -> dict[str, Any]:
    row = await homepage_section(db, section_id, for_update=True)
    old = homepage_section_data(row)
    row.active = False
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="homepage_section.archive",
        entity_type="homepage_section",
        entity_id=str(row.id),
        old_value=jsonable_encoder(old),
        new_value={"active": False},
    )
    await db.commit()
    return success({"id": row.id, "archived": True})


@router.post("/homepage/sections/reorder")
async def reorder_homepage_sections(
    payload: HomepageReorderInput,
    request: Request,
    admin: HomepageManager,
    db: DbSession,
) -> dict[str, Any]:
    rows = list(
        await db.scalars(select(HomepageSection).where(HomepageSection.id.in_(payload.section_ids)))
    )
    if len(rows) != len(set(payload.section_ids)):
        raise AppError(
            "NOT_FOUND", "One or more homepage sections were not found.", status_code=404
        )
    by_id = {row.id: row for row in rows}
    old = {str(row.id): row.sort_order for row in rows}
    for order, section_id in enumerate(payload.section_ids):
        by_id[section_id].sort_order = order
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="homepage_section.reorder",
        entity_type="homepage",
        entity_id="global",
        old_value=old,
        new_value={str(section_id): order for order, section_id in enumerate(payload.section_ids)},
    )
    await db.commit()
    return success({"reordered": len(rows)})


@router.post("/homepage/sections/{section_id}/items", status_code=status.HTTP_201_CREATED)
async def add_homepage_item(
    section_id: UUID,
    payload: HomepageItemCreate,
    request: Request,
    admin: HomepageManager,
    db: DbSession,
) -> dict[str, Any]:
    row = await homepage_section(db, section_id, for_update=True)
    await ensure_homepage_content(db, payload.content_id)
    if await db.scalar(
        select(HomepageSectionItem.id).where(
            HomepageSectionItem.section_id == section_id,
            HomepageSectionItem.content_id == payload.content_id,
        )
    ):
        raise AppError("CONFLICT", "Content is already in this section.", status_code=409)
    item = HomepageSectionItem(section_id=section_id, **payload.model_dump())
    db.add(item)
    await db.flush()
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="homepage_section.item.add",
        entity_type="homepage_section",
        entity_id=str(row.id),
        old_value=None,
        new_value=jsonable_encoder(
            {"item_id": item.id, "content_id": item.content_id, "sort_order": item.sort_order}
        ),
    )
    await db.commit()
    return success({"id": item.id, "content_id": item.content_id, "sort_order": item.sort_order})


@router.delete("/homepage/sections/{section_id}/items/{item_id}")
async def delete_homepage_item(
    section_id: UUID,
    item_id: UUID,
    request: Request,
    admin: HomepageManager,
    db: DbSession,
) -> dict[str, Any]:
    item = await db.scalar(
        select(HomepageSectionItem).where(
            HomepageSectionItem.id == item_id, HomepageSectionItem.section_id == section_id
        )
    )
    if item is None:
        raise AppError("NOT_FOUND", "Homepage item not found.", status_code=404)
    snapshot = {"item_id": item.id, "content_id": item.content_id}
    await db.delete(item)
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="homepage_section.item.remove",
        entity_type="homepage_section",
        entity_id=str(section_id),
        old_value=jsonable_encoder(snapshot),
        new_value=None,
    )
    await db.commit()
    return success({"id": item_id, "deleted": True})


@router.get("/notification-campaigns")
async def notification_campaigns(
    _: NotificationManager,
    db: DbSession,
    page: Page = 1,
    limit: Limit = 20,
    status_filter: str | None = Query(default=None, alias="status", max_length=30),
) -> dict[str, Any]:
    conditions: list[ColumnElement[bool]] = []
    if status_filter:
        conditions.append(NotificationCampaign.status == status_filter)
    total = int(
        await db.scalar(select(func.count(NotificationCampaign.id)).where(*conditions)) or 0
    )
    rows = list(
        await db.scalars(
            select(NotificationCampaign)
            .where(*conditions)
            .order_by(NotificationCampaign.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    )
    return success([campaign_data(row) for row in rows], meta=_meta(page, limit, total))


@router.get("/notifications/provider-status")
async def notification_provider_status(_: NotificationManager) -> dict[str, Any]:
    return success(push_provider_status())


@router.get("/notification-campaigns/{campaign_id}/deliveries")
async def notification_campaign_deliveries(
    campaign_id: UUID, _: NotificationManager, db: DbSession
) -> dict[str, Any]:
    return success(await campaign_delivery_summary(db, campaign_id=campaign_id))


@router.post("/notification-campaigns", status_code=status.HTTP_201_CREATED)
async def create_notification_campaign(
    payload: NotificationCampaignCreate,
    request: Request,
    admin: NotificationManager,
    db: DbSession,
) -> dict[str, Any]:
    data = payload.model_dump(exclude={"metadata", "audience"})
    row = NotificationCampaign(
        **data,
        audience=payload.audience.model_dump(mode="json"),
        campaign_metadata=payload.metadata,
        created_by_id=admin.id,
        status="scheduled" if payload.scheduled_at and payload.scheduled_at > utcnow() else "draft",
    )
    db.add(row)
    await db.flush()
    snapshot = campaign_data(row)
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="notification_campaign.create",
        entity_type="notification_campaign",
        entity_id=str(row.id),
        old_value=None,
        new_value=jsonable_encoder(snapshot),
    )
    await db.commit()
    return success(snapshot)


@router.patch("/notification-campaigns/{campaign_id}")
async def update_notification_campaign(
    campaign_id: UUID,
    payload: NotificationCampaignUpdate,
    request: Request,
    admin: NotificationManager,
    db: DbSession,
) -> dict[str, Any]:
    row = await db.scalar(
        select(NotificationCampaign).where(NotificationCampaign.id == campaign_id).with_for_update()
    )
    if row is None:
        raise AppError("NOT_FOUND", "Notification campaign not found.", status_code=404)
    if row.status not in {"draft", "scheduled"}:
        raise AppError("CAMPAIGN_LOCKED", "A processed campaign cannot be edited.", status_code=409)
    old = campaign_data(row)
    changes = payload.model_dump(exclude_unset=True)
    if "audience" in changes and payload.audience is not None:
        changes["audience"] = payload.audience.model_dump(mode="json")
    if "metadata" in changes:
        changes["campaign_metadata"] = changes.pop("metadata")
    for key, value in changes.items():
        setattr(row, key, value)
    row.status = "scheduled" if row.scheduled_at and row.scheduled_at > utcnow() else "draft"
    new = campaign_data(row)
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="notification_campaign.update",
        entity_type="notification_campaign",
        entity_id=str(row.id),
        old_value=jsonable_encoder(old),
        new_value=jsonable_encoder(new),
    )
    await db.commit()
    return success(new)


@router.post("/notification-campaigns/{campaign_id}/send")
async def send_notification_campaign(
    campaign_id: UUID,
    payload: NotificationCampaignSendInput,
    request: Request,
    admin: NotificationManager,
    db: DbSession,
) -> dict[str, Any]:
    row = await db.get(NotificationCampaign, campaign_id)
    if row is None:
        raise AppError("NOT_FOUND", "Notification campaign not found.", status_code=404)
    if not payload.send_now:
        if row.scheduled_at is None or row.scheduled_at <= utcnow():
            raise AppError(
                "VALIDATION_ERROR", "A future scheduled_at value is required.", status_code=422
            )
        row.status = "scheduled"
        await db.commit()
        return success(campaign_data(row))
    old = campaign_data(row)
    sent = await dispatch_notification_campaign(db, campaign_id=campaign_id)
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="notification_campaign.send",
        entity_type="notification_campaign",
        entity_id=str(sent.id),
        old_value=jsonable_encoder(old),
        new_value=jsonable_encoder(campaign_data(sent)),
    )
    await db.commit()
    if sent.status == "queued":
        if get_settings().NOTIFICATION_DELIVERY_MODE == "inline":
            await deliver_campaign_push(db, campaign_id=sent.id)
        else:
            from app.workers.celery_app import deliver_campaign_push_task

            deliver_campaign_push_task.delay(str(sent.id))
    return success(campaign_data(sent))


@router.post("/notification-campaigns/{campaign_id}/cancel")
async def cancel_notification_campaign(
    campaign_id: UUID, request: Request, admin: NotificationManager, db: DbSession
) -> dict[str, Any]:
    row = await db.scalar(
        select(NotificationCampaign).where(NotificationCampaign.id == campaign_id).with_for_update()
    )
    if row is None:
        raise AppError("NOT_FOUND", "Notification campaign not found.", status_code=404)
    if row.status == "sent":
        raise AppError("CAMPAIGN_LOCKED", "A sent campaign cannot be cancelled.", status_code=409)
    old = campaign_data(row)
    row.status = "cancelled"
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="notification_campaign.cancel",
        entity_type="notification_campaign",
        entity_id=str(row.id),
        old_value=jsonable_encoder(old),
        new_value={"status": "cancelled"},
    )
    await db.commit()
    return success(campaign_data(row))


@router.get("/audit-logs")
async def audit_logs(
    _: AuditViewer,
    db: DbSession,
    page: Page = 1,
    limit: Limit = 20,
    action: str | None = Query(default=None, max_length=120),
    entity_type: str | None = Query(default=None, max_length=80),
    admin_id: UUID | None = None,
) -> dict[str, Any]:
    conditions: list[ColumnElement[bool]] = []
    if action:
        conditions.append(AuditLog.action.ilike(f"%{action.strip()}%"))
    if entity_type:
        conditions.append(AuditLog.entity_type == entity_type)
    if admin_id:
        conditions.append(AuditLog.admin_id == admin_id)
    total = int(await db.scalar(select(func.count(AuditLog.id)).where(*conditions)) or 0)
    rows = list(
        await db.scalars(
            select(AuditLog)
            .where(*conditions)
            .order_by(AuditLog.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    )
    return success(
        [
            {
                "id": row.id,
                "admin_id": row.admin_id,
                "action": row.action,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "old_value": row.old_value,
                "new_value": row.new_value,
                "ip": row.ip,
                "user_agent": row.user_agent,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        meta=_meta(page, limit, total),
    )

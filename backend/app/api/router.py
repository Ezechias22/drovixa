from fastapi import APIRouter

from app.routes import (
    admin_catalog,
    admin_community,
    admin_configuration,
    admin_content,
    admin_monetization,
    admin_operations,
    admin_streaming,
    auth,
    catalog,
    community,
    configuration,
    content,
    experience,
    health,
    monetization,
    notifications,
    operations,
    payment_webhooks,
    streaming,
    users,
    video_webhooks,
)

api_router = APIRouter()
api_router.include_router(operations.router)
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(configuration.router)
api_router.include_router(community.router)
api_router.include_router(catalog.router)
api_router.include_router(content.router)
api_router.include_router(experience.router)
api_router.include_router(streaming.router)
api_router.include_router(monetization.router)
api_router.include_router(notifications.router)
api_router.include_router(video_webhooks.router)
api_router.include_router(payment_webhooks.router)
api_router.include_router(admin_configuration.router)
api_router.include_router(admin_community.router)
api_router.include_router(admin_catalog.router)
api_router.include_router(admin_content.router)
api_router.include_router(admin_streaming.router)
api_router.include_router(admin_monetization.router)
api_router.include_router(admin_operations.router)

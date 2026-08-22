from typing import Any

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas.common import success
from app.services.configuration import public_feature_flags, public_remote_config

router = APIRouter(tags=["Runtime configuration"])


@router.get("/feature-flags")
async def feature_flags(db: DbSession) -> dict[str, Any]:
    return success(await public_feature_flags(db))


@router.get("/remote-config")
async def remote_config(db: DbSession) -> dict[str, Any]:
    return success(await public_remote_config(db))

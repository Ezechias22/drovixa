from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Response

from app.api.deps import DbSession
from app.core.exceptions import AppError
from app.models.content import ContentMedia

router = APIRouter(tags=["Media"])


@router.get("/media/content/{media_id}")
async def content_media(media_id: UUID, db: DbSession) -> Response:
    row = await db.get(ContentMedia, media_id)
    if row is None:
        raise AppError("NOT_FOUND", "Cover image not found.", status_code=404)
    return Response(
        content=row.image_data,
        media_type=row.mime_type,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": f'"{row.id}"',
        },
    )

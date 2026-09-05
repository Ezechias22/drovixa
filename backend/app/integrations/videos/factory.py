from functools import lru_cache

from app.core.config import get_settings
from app.integrations.videos.base import VideoProvider
from app.integrations.videos.cloudflare import CloudflareStreamProvider
from app.integrations.videos.mux import MuxVideoProvider
from app.integrations.videos.original import OriginalVideoProvider


@lru_cache
def get_video_provider() -> VideoProvider:
    settings = get_settings()
    if settings.VIDEO_PROVIDER == "mux":
        return MuxVideoProvider(settings)
    if settings.VIDEO_PROVIDER == "cloudflare_stream":
        return CloudflareStreamProvider(settings)
    raise RuntimeError(f"Unsupported video provider: {settings.VIDEO_PROVIDER}")


@lru_cache
def get_original_video_provider() -> OriginalVideoProvider:
    return OriginalVideoProvider(get_settings())

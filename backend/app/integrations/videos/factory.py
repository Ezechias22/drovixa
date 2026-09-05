from functools import lru_cache

from app.core.config import get_settings
from app.integrations.videos.base import VideoProvider
from app.integrations.videos.cloudflare import CloudflareStreamProvider
from app.integrations.videos.demo import DemoVideoProvider
from app.integrations.videos.mux import MuxVideoProvider


@lru_cache
def get_video_provider() -> VideoProvider:
    settings = get_settings()
    if settings.VIDEO_PROVIDER == "mux":
        return MuxVideoProvider(settings)
    if settings.VIDEO_PROVIDER == "cloudflare_stream":
        return CloudflareStreamProvider(settings)
    raise RuntimeError(f"Unsupported video provider: {settings.VIDEO_PROVIDER}")


@lru_cache
def get_demo_video_provider() -> DemoVideoProvider:
    return DemoVideoProvider(get_settings())

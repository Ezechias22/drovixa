from __future__ import annotations

import logging
import re
from collections import defaultdict
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.config import Settings

logger = logging.getLogger("drovixa.observability")

_UUID_SEGMENT = re.compile(
    r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}"
)
_NUMERIC_SEGMENT = re.compile(r"/\d+(?=/|$)")
_DURATION_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)


def normalized_path(path: str) -> str:
    value = _UUID_SEGMENT.sub("/:id", path)
    return _NUMERIC_SEGMENT.sub("/:id", value)[:180]


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._requests: dict[tuple[str, str, int], int] = defaultdict(int)
        self._duration_count: dict[tuple[str, str], int] = defaultdict(int)
        self._duration_sum: dict[tuple[str, str], float] = defaultdict(float)
        self._duration_buckets: dict[tuple[str, str, float], int] = defaultdict(int)

    def record(self, method: str, path: str, status_code: int, duration_seconds: float) -> None:
        route = normalized_path(path)
        key = (method, route)
        with self._lock:
            self._requests[(method, route, status_code)] += 1
            self._duration_count[key] += 1
            self._duration_sum[key] += duration_seconds
            for bucket in _DURATION_BUCKETS:
                if duration_seconds <= bucket:
                    self._duration_buckets[(method, route, bucket)] += 1

    def render(self) -> str:
        lines = [
            "# HELP drovixa_http_requests_total Total HTTP requests.",
            "# TYPE drovixa_http_requests_total counter",
        ]
        with self._lock:
            for (method, path, status), count in sorted(self._requests.items()):
                labels = _labels(method=method, path=path, status=str(status))
                lines.append(f"drovixa_http_requests_total{{{labels}}} {count}")
            lines.extend(
                [
                    "# HELP drovixa_http_request_duration_seconds HTTP request duration.",
                    "# TYPE drovixa_http_request_duration_seconds histogram",
                ]
            )
            for (method, path), count in sorted(self._duration_count.items()):
                cumulative = 0
                for bucket in _DURATION_BUCKETS:
                    cumulative = self._duration_buckets[(method, path, bucket)]
                    labels = _labels(method=method, path=path, le=str(bucket))
                    lines.append(
                        f"drovixa_http_request_duration_seconds_bucket{{{labels}}} {cumulative}"
                    )
                labels = _labels(method=method, path=path, le="+Inf")
                lines.append(f"drovixa_http_request_duration_seconds_bucket{{{labels}}} {count}")
                base_labels = _labels(method=method, path=path)
                lines.append(
                    "drovixa_http_request_duration_seconds_sum"
                    f"{{{base_labels}}} {self._duration_sum[(method, path)]:.6f}"
                )
                lines.append(
                    f"drovixa_http_request_duration_seconds_count{{{base_labels}}} {count}"
                )
        return "\n".join(lines) + "\n"


def _labels(**values: str) -> str:
    return ",".join(f'{key}="{_escape(value)}"' for key, value in values.items())


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


metrics = MetricsRegistry()


def configure_observability(settings: Settings) -> None:
    if not settings.SENTRY_DSN:
        logger.info("sentry_disabled")
        return
    try:
        import sentry_sdk
    except ImportError:
        logger.warning("sentry_sdk_not_installed")
        return
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.APP_ENV,
        release=settings.RELEASE,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        profiles_sample_rate=settings.SENTRY_PROFILES_SAMPLE_RATE,
        send_default_pii=False,
    )
    logger.info("sentry_enabled")

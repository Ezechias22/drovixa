from __future__ import annotations

import os

APP_VERSION = "0.12.0"
BUILD_SHA = os.getenv("BUILD_SHA", "local")
RELEASE = os.getenv("RELEASE", f"drovixa@{APP_VERSION}")


def build_info() -> dict[str, str]:
    return {
        "version": APP_VERSION,
        "release": RELEASE,
        "build_sha": BUILD_SHA,
    }

from __future__ import annotations

from typing import Any


def success(data: Any, *, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"success": True, "data": data, "meta": meta or {}}

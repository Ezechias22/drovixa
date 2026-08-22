from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FeatureFlagUpdate(BaseModel):
    enabled: bool | None = None
    rollout_percentage: int | None = Field(default=None, ge=0, le=100)
    rules: dict[str, Any] | None = None


class RemoteConfigUpdate(BaseModel):
    value: Any
    is_public: bool | None = None

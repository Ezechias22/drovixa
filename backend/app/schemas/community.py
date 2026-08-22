from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import (
    CommentTargetType,
    LikeTargetType,
    ReportStatus,
    ReportTargetType,
)


def normalize_text(value: str) -> str:
    return " ".join(value.split())


class LikeInput(BaseModel):
    target_type: LikeTargetType
    target_id: UUID


class CommentCreate(BaseModel):
    target_type: CommentTargetType
    target_id: UUID
    body: str = Field(min_length=1, max_length=2000)
    parent_id: UUID | None = None
    is_spoiler: bool = False

    @field_validator("body")
    @classmethod
    def validate_body(cls, value: str) -> str:
        normalized = normalize_text(value)
        if not normalized:
            raise ValueError("Comment cannot be empty.")
        return normalized


class CommentUpdate(BaseModel):
    body: str | None = Field(default=None, min_length=1, max_length=2000)
    is_spoiler: bool | None = None

    @field_validator("body")
    @classmethod
    def validate_body(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_text(value)
        if not normalized:
            raise ValueError("Comment cannot be empty.")
        return normalized

    @model_validator(mode="after")
    def require_change(self) -> CommentUpdate:
        if self.body is None and self.is_spoiler is None:
            raise ValueError("At least one field is required.")
        return self


class ReportCreate(BaseModel):
    target_type: ReportTargetType
    target_id: UUID | None = None
    reason_code: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9_]+$")
    details: str | None = Field(default=None, max_length=2000)

    @field_validator("details")
    @classmethod
    def normalize_details(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_text(value)
        return normalized or None

    @model_validator(mode="after")
    def validate_target(self) -> ReportCreate:
        if self.target_type == ReportTargetType.TECHNICAL and self.target_id is None:
            return self
        if self.target_id is None:
            raise ValueError("target_id is required for this report type.")
        return self


class CommentReportInput(BaseModel):
    reason_code: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9_]+$")
    details: str | None = Field(default=None, max_length=2000)


class CommentModerationAction(StrEnum):
    HIDE = "hide"
    DELETE = "delete"
    RESTORE = "restore"
    SPAM = "spam"
    PIN = "pin"
    UNPIN = "unpin"


class CommentModerationInput(BaseModel):
    action: CommentModerationAction
    reason: str | None = Field(default=None, max_length=500)


class ReportUpdate(BaseModel):
    status: ReportStatus | None = None
    assigned_to_id: UUID | None = None
    resolution_note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_change(self) -> ReportUpdate:
        if self.status is None and self.assigned_to_id is None and self.resolution_note is None:
            raise ValueError("At least one field is required.")
        return self


class UserMuteInput(BaseModel):
    reason: str = Field(min_length=2, max_length=500)
    expires_at: datetime | None = None

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return normalize_text(value)


class UserBanInput(BaseModel):
    reason: str = Field(min_length=2, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return normalize_text(value)

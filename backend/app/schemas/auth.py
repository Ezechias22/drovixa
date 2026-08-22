from __future__ import annotations

import re

from pydantic import BaseModel, EmailStr, Field, field_validator


class DeviceInput(BaseModel):
    device_id: str = Field(min_length=8, max_length=160)
    name: str = Field(min_length=1, max_length=120)
    platform: str = Field(pattern=r"^(android|ios|web|pwa|tablet|unknown)$")


class RegisterInput(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    device: DeviceInput

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
            raise ValueError("Password must include at least one letter and one number")
        return value


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    device: DeviceInput


class RefreshInput(BaseModel):
    refresh_token: str = Field(min_length=40, max_length=512)

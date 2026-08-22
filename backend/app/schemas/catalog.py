from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CountryCreate(BaseModel):
    code: str = Field(min_length=2, max_length=2)
    name: str = Field(min_length=1, max_length=120)
    currency: str = Field(min_length=3, max_length=3)
    active: bool = True
    sort_order: int = 0

    @field_validator("code", "currency")
    @classmethod
    def uppercase_code(cls, value: str) -> str:
        return value.strip().upper()


class CountryUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=2, max_length=2)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    active: bool | None = None
    sort_order: int | None = None

    @field_validator("code", "currency")
    @classmethod
    def uppercase_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else value


class LanguageCreate(BaseModel):
    code: str = Field(min_length=2, max_length=15, pattern=r"^[A-Za-z]{2,3}(-[A-Za-z]{2})?$")
    name: str = Field(min_length=1, max_length=120)
    native_name: str = Field(min_length=1, max_length=120)
    active: bool = True
    sort_order: int = 0


class LanguageUpdate(BaseModel):
    code: str | None = Field(
        default=None, min_length=2, max_length=15, pattern=r"^[A-Za-z]{2,3}(-[A-Za-z]{2})?$"
    )
    name: str | None = Field(default=None, min_length=1, max_length=120)
    native_name: str | None = Field(default=None, min_length=1, max_length=120)
    active: bool | None = None
    sort_order: int | None = None


class GenreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str | None = Field(default=None, min_length=1, max_length=120)
    icon: str | None = Field(default=None, max_length=120)
    image_url: str | None = Field(default=None, max_length=2048)
    active: bool = True
    sort_order: int = 0


class GenreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    slug: str | None = Field(default=None, min_length=1, max_length=120)
    icon: str | None = Field(default=None, max_length=120)
    image_url: str | None = Field(default=None, max_length=2048)
    active: bool | None = None
    sort_order: int | None = None


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str | None = Field(default=None, min_length=1, max_length=120)
    active: bool = True


class TagUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    slug: str | None = Field(default=None, min_length=1, max_length=120)
    active: bool | None = None


class PersonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    slug: str | None = Field(default=None, min_length=1, max_length=200)
    photo_url: str | None = Field(default=None, max_length=2048)
    bio: str | None = None
    country_id: UUID | None = None
    social_links: dict[str, Any] = Field(default_factory=dict)
    active: bool = True


class ActorCreate(PersonCreate):
    birth_date: date | None = None


class PersonUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    slug: str | None = Field(default=None, min_length=1, max_length=200)
    photo_url: str | None = Field(default=None, max_length=2048)
    bio: str | None = None
    country_id: UUID | None = None
    social_links: dict[str, Any] | None = None
    active: bool | None = None


class ActorUpdate(PersonUpdate):
    birth_date: date | None = None


class CatalogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    active: bool

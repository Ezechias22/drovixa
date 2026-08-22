from pydantic import BaseModel, Field, field_validator


class SearchHistoryInput(BaseModel):
    query: str = Field(min_length=1, max_length=160)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Search query cannot be empty.")
        return normalized


class NotificationPreferenceUpdate(BaseModel):
    new_episodes: bool | None = None
    promotions: bool | None = None
    recommendations: bool | None = None
    wallet: bool | None = None
    comments: bool | None = None

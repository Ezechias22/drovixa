from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class PushMessage:
    title: str
    body: str
    image_url: str | None
    action_url: str | None
    data: dict[str, str]


@dataclass(frozen=True, slots=True)
class PushResult:
    success: bool
    message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class PushProvider(Protocol):
    name: str
    enabled: bool

    async def send(self, *, tokens: list[str], message: PushMessage) -> list[PushResult]: ...

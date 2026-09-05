from __future__ import annotations

from contextvars import ContextVar, Token

SUPPORTED_CONTENT_LANGUAGES = frozenset({"en", "fr", "pt-BR", "es", "ht"})
_content_language: ContextVar[str] = ContextVar("content_language", default="en")


def normalize_content_language(value: str | None) -> str:
    if not value:
        return "en"
    candidate = value.split(",", maxsplit=1)[0].split(";", maxsplit=1)[0].strip()
    lowered = candidate.lower()
    if lowered.startswith("pt"):
        return "pt-BR"
    for language in ("ht", "fr", "es", "en"):
        if lowered == language or lowered.startswith(f"{language}-"):
            return language
    return "en"


def set_content_language(value: str | None) -> Token[str]:
    return _content_language.set(normalize_content_language(value))


def reset_content_language(token: Token[str]) -> None:
    _content_language.reset(token)


def content_language() -> str:
    return _content_language.get()


def localized_fields(
    translations: dict[str, dict[str, str]] | None,
    fallback: dict[str, str | None],
) -> dict[str, str | None]:
    catalog = translations or {}
    selected = catalog.get(content_language()) or catalog.get("en") or {}
    return {key: selected.get(key) or value for key, value in fallback.items()}

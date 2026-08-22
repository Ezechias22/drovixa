from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt

from app.core.config import Settings
from app.core.exceptions import AppError
from app.integrations.videos.base import (
    PlaybackGrant,
    ProviderUpload,
    VideoMetadata,
    VideoProvider,
)
from app.models.enums import UploadProtocol, VideoStatus


class MuxVideoProvider(VideoProvider):
    """Mux Video adapter with direct uploads and server-signed playback."""

    name = "mux"
    webhook_signature_header = "Mux-Signature"
    _pending_prefix = "mux-upload:"

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport

    def _api_credentials(self) -> tuple[str, str]:
        token_id = self.settings.MUX_TOKEN_ID
        token_secret = self.settings.MUX_TOKEN_SECRET
        if not token_id or not token_secret:
            raise AppError(
                "VIDEO_PROVIDER_NOT_CONFIGURED",
                "The Mux API credentials are not configured.",
                status_code=503,
            )
        return token_id, token_secret

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> httpx.Response:
        token_id, token_secret = self._api_credentials()
        try:
            async with httpx.AsyncClient(
                auth=httpx.BasicAuth(token_id, token_secret),
                timeout=self.settings.VIDEO_API_TIMEOUT_SECONDS,
                transport=self.transport,
            ) as client:
                response = await client.request(
                    method,
                    f"{self.settings.MUX_API_BASE_URL.rstrip('/')}{path}",
                    json=json_body,
                    headers={"Accept": "application/json"},
                )
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            raise AppError(
                "VIDEO_PROVIDER_ERROR",
                "Mux could not complete the video request.",
                status_code=502,
            ) from exc

    @staticmethod
    def _data(response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            raise AppError(
                "VIDEO_PROVIDER_ERROR",
                "Mux returned an invalid response.",
                status_code=502,
            ) from exc
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            raise AppError(
                "VIDEO_PROVIDER_ERROR",
                "Mux did not return the requested resource.",
                status_code=502,
            )
        return data

    def _asset_settings(
        self,
        *,
        title: str,
        creator_id: str | None = None,
        external_id: str | None = None,
        signed: bool = True,
    ) -> dict[str, Any]:
        settings: dict[str, Any] = {
            "playback_policies": ["signed" if signed else "public"],
            "video_quality": self.settings.MUX_VIDEO_QUALITY,
            "max_resolution_tier": self.settings.MUX_MAX_RESOLUTION_TIER,
            "meta": {"title": title},
        }
        if creator_id:
            settings["meta"]["creator_id"] = creator_id
        if external_id:
            settings["meta"]["external_id"] = external_id
            settings["passthrough"] = external_id
        return settings

    def select_upload_protocol(self, *, requested: str, file_size_bytes: int) -> UploadProtocol:
        del file_size_bytes
        if requested not in {"auto", UploadProtocol.RESUMABLE.value}:
            raise AppError(
                "VIDEO_UPLOAD_PROTOCOL_UNSUPPORTED",
                "Mux direct uploads require the resumable upload protocol.",
                status_code=422,
            )
        return UploadProtocol.RESUMABLE

    async def upload_video(
        self, *, source_url: str, name: str, require_signed_urls: bool = True
    ) -> VideoMetadata:
        response = await self._request(
            "POST",
            "/assets",
            json_body={
                "inputs": [{"url": source_url}],
                **self._asset_settings(title=name, signed=require_signed_urls),
            },
        )
        data = self._data(response)
        return self._asset_metadata(data, raw=data)

    async def get_upload_url(
        self,
        *,
        file_name: str,
        content_type: str,
        file_size_bytes: int,
        max_duration_seconds: int,
        protocol: UploadProtocol,
        creator_id: str,
        external_id: str,
    ) -> ProviderUpload:
        del file_size_bytes, max_duration_seconds
        if protocol != UploadProtocol.RESUMABLE:
            raise AppError(
                "VIDEO_UPLOAD_PROTOCOL_UNSUPPORTED",
                "Mux direct uploads require the resumable upload protocol.",
                status_code=422,
            )
        timeout = self.settings.MUX_UPLOAD_TIMEOUT_SECONDS
        response = await self._request(
            "POST",
            "/uploads",
            json_body={
                "cors_origin": self.settings.MUX_UPLOAD_CORS_ORIGIN,
                "timeout": timeout,
                "new_asset_settings": self._asset_settings(
                    title=file_name,
                    creator_id=creator_id,
                    external_id=external_id,
                ),
            },
        )
        data = self._data(response)
        upload_id = data.get("id")
        upload_url = data.get("url")
        if not isinstance(upload_id, str) or not isinstance(upload_url, str):
            raise AppError(
                "VIDEO_PROVIDER_ERROR",
                "Mux did not return a direct upload URL.",
                status_code=502,
            )
        return ProviderUpload(
            provider_asset_id=f"{self._pending_prefix}{upload_id}",
            upload_url=upload_url,
            protocol=UploadProtocol.RESUMABLE,
            expires_at=datetime.now(UTC) + timedelta(seconds=timeout),
            headers={"Content-Type": content_type},
        )

    async def get_video_status(self, provider_asset_id: str) -> VideoMetadata:
        return await self.get_video_metadata(provider_asset_id)

    async def delete_video(self, provider_asset_id: str) -> None:
        if provider_asset_id.startswith(self._pending_prefix):
            upload_id = provider_asset_id.removeprefix(self._pending_prefix)
            await self._request("PUT", f"/uploads/{upload_id}/cancel")
            return
        await self._request("DELETE", f"/assets/{provider_asset_id}")

    def get_playback_url(self, playback_token: str) -> str:
        return f"https://stream.mux.com/{playback_token}.m3u8"

    def _private_key(self) -> tuple[str, bytes]:
        key_id = self.settings.MUX_SIGNING_KEY_ID
        encoded_key = self.settings.MUX_SIGNING_PRIVATE_KEY_B64
        if not key_id or not encoded_key:
            raise AppError(
                "VIDEO_SIGNING_NOT_CONFIGURED",
                "Mux signed playback is not configured.",
                status_code=503,
            )
        try:
            private_key = base64.b64decode("".join(encoded_key.split()), validate=True)
        except (ValueError, TypeError) as exc:
            raise AppError(
                "VIDEO_SIGNING_NOT_CONFIGURED",
                "The Mux signing key is invalid.",
                status_code=503,
            ) from exc
        return key_id, private_key

    def _sign_token(self, playback_id: str, *, audience: str, expires_at: datetime) -> str:
        key_id, private_key = self._private_key()
        claims = {
            "sub": playback_id,
            "aud": audience,
            "exp": int(expires_at.timestamp()),
            "kid": key_id,
        }
        try:
            encoded = jwt.encode(
                claims,
                private_key,
                algorithm="RS256",
                headers={"kid": key_id},
            )
        except (jwt.PyJWTError, ValueError, TypeError) as exc:
            raise AppError(
                "VIDEO_SIGNING_NOT_CONFIGURED",
                "The Mux signing key could not be loaded.",
                status_code=503,
            ) from exc
        return encoded.decode() if isinstance(encoded, bytes) else encoded

    async def create_signed_url(
        self,
        *,
        provider_asset_id: str,
        playback_id: str | None,
        expires_at: datetime,
        country_code: str | None,
    ) -> PlaybackGrant:
        del country_code
        effective_playback_id = playback_id
        if not effective_playback_id:
            metadata = await self.get_video_metadata(provider_asset_id)
            effective_playback_id = metadata.playback_id
        if not effective_playback_id:
            raise AppError(
                "VIDEO_NOT_READY",
                "Mux has not created a playback ID for this asset.",
                status_code=409,
            )
        token = self._sign_token(effective_playback_id, audience="v", expires_at=expires_at)
        return PlaybackGrant(
            hls_url=f"https://stream.mux.com/{effective_playback_id}.m3u8?token={token}",
            dash_url=None,
            expires_at=expires_at,
        )

    def generate_thumbnail(self, provider_asset_id: str, *, time_seconds: int = 0) -> str:
        expires_at = datetime.now(UTC) + timedelta(
            seconds=self.settings.VIDEO_PLAYBACK_TOKEN_TTL_SECONDS
        )
        claims_time = max(time_seconds, 0)
        key_id, private_key = self._private_key()
        claims = {
            "sub": provider_asset_id,
            "aud": "t",
            "exp": int(expires_at.timestamp()),
            "kid": key_id,
            "params": {"time": claims_time},
        }
        try:
            token = jwt.encode(
                claims,
                private_key,
                algorithm="RS256",
                headers={"kid": key_id},
            )
        except (jwt.PyJWTError, ValueError, TypeError) as exc:
            raise AppError(
                "VIDEO_SIGNING_NOT_CONFIGURED",
                "The Mux signing key could not be loaded.",
                status_code=503,
            ) from exc
        token_value = token.decode() if isinstance(token, bytes) else token
        return f"https://image.mux.com/{provider_asset_id}/thumbnail.jpg?token={token_value}"

    async def get_video_metadata(self, provider_asset_id: str) -> VideoMetadata:
        if provider_asset_id.startswith(self._pending_prefix):
            upload_id = provider_asset_id.removeprefix(self._pending_prefix)
            response = await self._request("GET", f"/uploads/{upload_id}")
            upload = self._data(response)
            asset_id = upload.get("asset_id")
            if isinstance(asset_id, str) and asset_id:
                asset_response = await self._request("GET", f"/assets/{asset_id}")
                asset = self._data(asset_response)
                return self._asset_metadata(asset, raw=asset)
            return self._upload_metadata(upload, raw=upload)
        response = await self._request("GET", f"/assets/{provider_asset_id}")
        data = self._data(response)
        return self._asset_metadata(data, raw=data)

    def verify_webhook(self, *, body: bytes, signature: str | None) -> datetime:
        secret = self.settings.MUX_WEBHOOK_SECRET
        if not secret:
            raise AppError(
                "VIDEO_WEBHOOK_NOT_CONFIGURED",
                "The Mux webhook is not configured.",
                status_code=503,
            )
        if not signature:
            raise AppError(
                "INVALID_WEBHOOK_SIGNATURE",
                "Webhook signature is missing.",
                status_code=401,
            )
        parts: dict[str, list[str]] = {}
        for item in signature.split(","):
            if "=" not in item:
                continue
            key, value = item.split("=", maxsplit=1)
            parts.setdefault(key.strip(), []).append(value.strip())
        try:
            timestamp = int(parts.get("t", [""])[0])
        except ValueError:
            timestamp = 0
        now = int(datetime.now(UTC).timestamp())
        if not timestamp or abs(now - timestamp) > self.settings.VIDEO_WEBHOOK_TOLERANCE_SECONDS:
            raise AppError(
                "INVALID_WEBHOOK_SIGNATURE",
                "Webhook signature is stale.",
                status_code=401,
            )
        expected = hmac.new(
            secret.encode(),
            str(timestamp).encode() + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        if not any(hmac.compare_digest(expected, candidate) for candidate in parts.get("v1", [])):
            raise AppError(
                "INVALID_WEBHOOK_SIGNATURE",
                "Webhook signature is invalid.",
                status_code=401,
            )
        return datetime.fromtimestamp(timestamp, tz=UTC)

    def parse_webhook(self, payload: dict[str, Any]) -> VideoMetadata:
        event_type = payload.get("type")
        data = payload.get("data")
        if not isinstance(event_type, str) or not isinstance(data, dict):
            raise AppError(
                "INVALID_WEBHOOK_PAYLOAD",
                "The Mux webhook payload is invalid.",
                status_code=400,
            )
        raw = json.loads(json.dumps(payload))
        if event_type in {
            "video.asset.created",
            "video.asset.ready",
            "video.asset.errored",
            "video.asset.updated",
            "video.asset.deleted",
        }:
            return self._asset_metadata(data, raw=raw, event_type=event_type)
        if event_type in {
            "video.upload.created",
            "video.upload.asset_created",
            "video.upload.errored",
            "video.upload.cancelled",
        }:
            return self._upload_metadata(data, raw=raw)
        object_data = payload.get("object")
        object_id = object_data.get("id") if isinstance(object_data, dict) else None
        fallback_id = object_id if isinstance(object_id, str) else str(data.get("id", "unknown"))
        return VideoMetadata(
            provider_asset_id=fallback_id,
            status=VideoStatus.PROCESSING,
            actionable=False,
            raw=raw,
        )

    @staticmethod
    def _correlation(data: dict[str, Any]) -> str | None:
        passthrough = data.get("passthrough")
        if isinstance(passthrough, str) and passthrough:
            return passthrough
        meta = data.get("meta")
        external = meta.get("external_id") if isinstance(meta, dict) else None
        if isinstance(external, str) and external:
            return external
        new_settings = data.get("new_asset_settings")
        if isinstance(new_settings, dict):
            nested = new_settings.get("passthrough")
            if isinstance(nested, str) and nested:
                return nested
            nested_meta = new_settings.get("meta")
            nested_external = (
                nested_meta.get("external_id") if isinstance(nested_meta, dict) else None
            )
            if isinstance(nested_external, str) and nested_external:
                return nested_external
        return None

    def _upload_metadata(self, data: dict[str, Any], *, raw: dict[str, Any]) -> VideoMetadata:
        upload_id = data.get("id")
        if not isinstance(upload_id, str) or not upload_id:
            raise AppError(
                "INVALID_WEBHOOK_PAYLOAD",
                "The Mux upload identifier is missing.",
                status_code=400,
            )
        raw_status = str(data.get("status", "waiting")).casefold()
        asset_id = data.get("asset_id")
        provider_id = (
            asset_id
            if isinstance(asset_id, str) and asset_id
            else f"{self._pending_prefix}{upload_id}"
        )
        failed = raw_status in {"errored", "cancelled", "timed_out"}
        error = data.get("error")
        error_data = error if isinstance(error, dict) else {}
        return VideoMetadata(
            provider_asset_id=provider_id,
            status=(
                VideoStatus.FAILED
                if failed
                else VideoStatus.PROCESSING
                if raw_status == "asset_created"
                else VideoStatus.UPLOADING
            ),
            error_code=str(error_data.get("type")) if error_data.get("type") else None,
            error_message=(str(error_data.get("message")) if error_data.get("message") else None),
            correlation_id=self._correlation(data),
            raw=raw,
        )

    def _asset_metadata(
        self,
        data: dict[str, Any],
        *,
        raw: dict[str, Any],
        event_type: str | None = None,
    ) -> VideoMetadata:
        asset_id = data.get("id")
        if not isinstance(asset_id, str) or not asset_id:
            raise AppError(
                "INVALID_WEBHOOK_PAYLOAD",
                "The Mux asset identifier is missing.",
                status_code=400,
            )
        raw_status = str(data.get("status", "preparing")).casefold()
        if event_type == "video.asset.deleted":
            status = VideoStatus.DELETED
        elif raw_status == "ready":
            status = VideoStatus.READY
        elif raw_status == "errored":
            status = VideoStatus.FAILED
        else:
            status = VideoStatus.PROCESSING

        playback_ids = data.get("playback_ids")
        playbacks = playback_ids if isinstance(playback_ids, list) else []
        signed_playback = next(
            (
                item.get("id")
                for item in playbacks
                if isinstance(item, dict)
                and item.get("policy") == "signed"
                and isinstance(item.get("id"), str)
            ),
            None,
        )
        fallback_playback = next(
            (
                item.get("id")
                for item in playbacks
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            ),
            None,
        )
        tracks = data.get("tracks")
        video_track = (
            next(
                (item for item in tracks if isinstance(item, dict) and item.get("type") == "video"),
                {},
            )
            if isinstance(tracks, list)
            else {}
        )
        errors = data.get("errors")
        error_data = errors if isinstance(errors, dict) else {}
        messages = error_data.get("messages")
        error_message = (
            "; ".join(str(item) for item in messages) if isinstance(messages, list) else None
        )
        duration = data.get("duration")
        width = video_track.get("max_width")
        height = video_track.get("max_height")
        return VideoMetadata(
            provider_asset_id=asset_id,
            status=status,
            duration_seconds=round(float(duration)) if isinstance(duration, int | float) else None,
            width=width if isinstance(width, int) else None,
            height=height if isinstance(height, int) else None,
            playback_id=signed_playback or fallback_playback,
            error_code=str(error_data.get("type")) if error_data.get("type") else None,
            error_message=error_message,
            correlation_id=self._correlation(data),
            raw=raw,
        )

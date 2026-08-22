from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime
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


class CloudflareStreamProvider(VideoProvider):
    name = "cloudflare_stream"

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport

    def _api_credentials(self) -> tuple[str, str]:
        if not self.settings.CLOUDFLARE_ACCOUNT_ID or not self.settings.CLOUDFLARE_STREAM_API_TOKEN:
            raise AppError(
                "VIDEO_PROVIDER_NOT_CONFIGURED",
                "The video provider credentials are not configured.",
                status_code=503,
            )
        return self.settings.CLOUDFLARE_ACCOUNT_ID, self.settings.CLOUDFLARE_STREAM_API_TOKEN

    def _customer_code(self) -> str:
        if not self.settings.CLOUDFLARE_STREAM_CUSTOMER_CODE:
            raise AppError(
                "VIDEO_PROVIDER_NOT_CONFIGURED",
                "The video playback domain is not configured.",
                status_code=503,
            )
        return self.settings.CLOUDFLARE_STREAM_CUSTOMER_CODE

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        account_id, token = self._api_credentials()
        request_headers = {"Authorization": f"Bearer {token}"}
        if headers:
            request_headers.update(headers)
        url = f"{self.settings.CLOUDFLARE_API_BASE_URL}/accounts/{account_id}{path}"
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.VIDEO_API_TIMEOUT_SECONDS,
                transport=self.transport,
            ) as client:
                response = await client.request(
                    method,
                    url,
                    json=json_body,
                    headers=request_headers,
                )
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            raise AppError(
                "VIDEO_PROVIDER_ERROR",
                "The video provider could not complete the request.",
                status_code=502,
            ) from exc

    @staticmethod
    def _result(response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            raise AppError(
                "VIDEO_PROVIDER_ERROR",
                "The video provider returned an invalid response.",
                status_code=502,
            ) from exc
        result = body.get("result") if isinstance(body, dict) else None
        if not isinstance(result, dict):
            raise AppError(
                "VIDEO_PROVIDER_ERROR",
                "The video provider did not return the requested resource.",
                status_code=502,
            )
        return result

    async def upload_video(
        self, *, source_url: str, name: str, require_signed_urls: bool = True
    ) -> VideoMetadata:
        response = await self._request(
            "POST",
            "/stream/copy",
            json_body={
                "url": source_url,
                "meta": {"name": name},
                "requireSignedURLs": require_signed_urls,
                "allowedOrigins": self.settings.VIDEO_ALLOWED_ORIGINS,
            },
        )
        return self._metadata(self._result(response))

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
        del content_type, external_id
        if protocol == UploadProtocol.BASIC:
            response = await self._request(
                "POST",
                "/stream/direct_upload",
                json_body={
                    "maxDurationSeconds": max_duration_seconds,
                    "creator": creator_id,
                    "meta": {"name": file_name},
                    "requireSignedURLs": True,
                    "allowedOrigins": self.settings.VIDEO_ALLOWED_ORIGINS,
                },
            )
            result = self._result(response)
            upload_url = result.get("uploadURL")
            provider_asset_id = result.get("uid")
            if not isinstance(upload_url, str) or not isinstance(provider_asset_id, str):
                raise AppError(
                    "VIDEO_PROVIDER_ERROR",
                    "The video provider did not return an upload URL.",
                    status_code=502,
                )
            return ProviderUpload(provider_asset_id, upload_url, protocol)

        encoded_name = base64.b64encode(file_name.encode()).decode()
        encoded_signed = base64.b64encode(b"true").decode()
        encoded_duration = base64.b64encode(str(max_duration_seconds).encode()).decode()
        metadata = (
            f"name {encoded_name},requiresignedurls {encoded_signed},"
            f"maxdurationseconds {encoded_duration}"
        )
        response = await self._request(
            "POST",
            "/stream?direct_user=true",
            headers={
                "Tus-Resumable": "1.0.0",
                "Upload-Length": str(file_size_bytes),
                "Upload-Metadata": metadata,
                "Upload-Creator": creator_id,
            },
        )
        upload_url = response.headers.get("Location")
        provider_asset_id = response.headers.get("stream-media-id")
        if not provider_asset_id and upload_url:
            provider_asset_id = upload_url.rstrip("/").rsplit("/", maxsplit=1)[-1]
        if not upload_url or not provider_asset_id:
            raise AppError(
                "VIDEO_PROVIDER_ERROR",
                "The video provider did not return a resumable upload URL.",
                status_code=502,
            )
        return ProviderUpload(
            provider_asset_id,
            upload_url,
            protocol,
            headers={"Tus-Resumable": "1.0.0"},
        )

    async def get_video_status(self, provider_asset_id: str) -> VideoMetadata:
        return await self.get_video_metadata(provider_asset_id)

    async def delete_video(self, provider_asset_id: str) -> None:
        await self._request("DELETE", f"/stream/{provider_asset_id}")

    def get_playback_url(self, playback_token: str) -> str:
        return (
            f"https://customer-{self._customer_code()}.cloudflarestream.com/"
            f"{playback_token}/manifest/video.m3u8"
        )

    async def create_signed_url(
        self,
        *,
        provider_asset_id: str,
        playback_id: str | None,
        expires_at: datetime,
        country_code: str | None,
    ) -> PlaybackGrant:
        del playback_id
        key_id = self.settings.CLOUDFLARE_STREAM_SIGNING_KEY_ID
        encoded_pem = self.settings.CLOUDFLARE_STREAM_SIGNING_KEY_PEM_B64
        if not key_id or not encoded_pem:
            raise AppError(
                "VIDEO_SIGNING_NOT_CONFIGURED",
                "Signed playback is not configured.",
                status_code=503,
            )
        try:
            private_key = base64.b64decode(encoded_pem, validate=True)
        except ValueError as exc:
            raise AppError(
                "VIDEO_SIGNING_NOT_CONFIGURED",
                "The video signing key is invalid.",
                status_code=503,
            ) from exc
        claims: dict[str, Any] = {
            "sub": provider_asset_id,
            "kid": key_id,
            "exp": int(expires_at.timestamp()),
        }
        if country_code:
            claims["accessRules"] = [
                {
                    "type": "ip.geoip.country",
                    "action": "allow",
                    "country": [country_code],
                },
                {"type": "any", "action": "block"},
            ]
        try:
            encoded_token = jwt.encode(
                claims, private_key, algorithm="RS256", headers={"kid": key_id}
            )
        except (jwt.PyJWTError, ValueError, TypeError) as exc:
            raise AppError(
                "VIDEO_SIGNING_NOT_CONFIGURED",
                "The video signing key could not be loaded.",
                status_code=503,
            ) from exc
        token = encoded_token.decode() if isinstance(encoded_token, bytes) else encoded_token
        base = f"https://customer-{self._customer_code()}.cloudflarestream.com/{token}"
        return PlaybackGrant(
            hls_url=f"{base}/manifest/video.m3u8",
            dash_url=f"{base}/manifest/video.mpd",
            expires_at=expires_at,
        )

    def generate_thumbnail(self, provider_asset_id: str, *, time_seconds: int = 0) -> str:
        return (
            f"https://customer-{self._customer_code()}.cloudflarestream.com/"
            f"{provider_asset_id}/thumbnails/thumbnail.jpg?time={max(time_seconds, 0)}s"
        )

    async def get_video_metadata(self, provider_asset_id: str) -> VideoMetadata:
        response = await self._request("GET", f"/stream/{provider_asset_id}")
        return self._metadata(self._result(response))

    def verify_webhook(self, *, body: bytes, signature: str | None) -> datetime:
        secret = self.settings.CLOUDFLARE_STREAM_WEBHOOK_SECRET
        if not secret:
            raise AppError(
                "VIDEO_WEBHOOK_NOT_CONFIGURED",
                "The video webhook is not configured.",
                status_code=503,
            )
        if not signature:
            raise AppError(
                "INVALID_WEBHOOK_SIGNATURE", "Webhook signature is missing.", status_code=401
            )
        parts = dict(item.split("=", maxsplit=1) for item in signature.split(",") if "=" in item)
        timestamp_value, supplied = parts.get("time"), parts.get("sig1")
        try:
            timestamp = int(timestamp_value or "")
        except ValueError:
            timestamp = 0
        now = int(datetime.now(UTC).timestamp())
        if not timestamp or abs(now - timestamp) > self.settings.VIDEO_WEBHOOK_TOLERANCE_SECONDS:
            raise AppError(
                "INVALID_WEBHOOK_SIGNATURE", "Webhook signature is stale.", status_code=401
            )
        source = str(timestamp).encode() + b"." + body
        expected = hmac.new(secret.encode(), source, hashlib.sha256).hexdigest()
        if not supplied or not hmac.compare_digest(expected, supplied):
            raise AppError(
                "INVALID_WEBHOOK_SIGNATURE", "Webhook signature is invalid.", status_code=401
            )
        return datetime.fromtimestamp(timestamp, tz=UTC)

    def parse_webhook(self, payload: dict[str, Any]) -> VideoMetadata:
        return self._metadata(payload)

    @staticmethod
    def _metadata(payload: dict[str, Any]) -> VideoMetadata:
        provider_asset_id = payload.get("uid")
        if not isinstance(provider_asset_id, str) or not provider_asset_id:
            raise AppError(
                "INVALID_WEBHOOK_PAYLOAD", "The video identifier is missing.", status_code=400
            )
        raw_status = payload.get("status")
        status_data: dict[str, Any] = raw_status if isinstance(raw_status, dict) else {}
        state = str(status_data.get("state", "")).casefold()
        ready = payload.get("readyToStream") is True and state == "ready"
        if ready:
            status = VideoStatus.READY
        elif state == "error":
            status = VideoStatus.FAILED
        elif state in {"queued", "inprogress", "downloading", "uploading"}:
            status = VideoStatus.PROCESSING
        else:
            status = VideoStatus.PROCESSING

        duration = payload.get("duration")
        raw_input = payload.get("input")
        input_data: dict[str, Any] = raw_input if isinstance(raw_input, dict) else {}
        error_code = status_data.get("errReasonCode") or status_data.get("errorReasonCode")
        error_message = status_data.get("errReasonText") or status_data.get("errorReasonText")
        return VideoMetadata(
            provider_asset_id=provider_asset_id,
            status=status,
            duration_seconds=round(float(duration)) if isinstance(duration, int | float) else None,
            width=input_data.get("width") if isinstance(input_data.get("width"), int) else None,
            height=input_data.get("height") if isinstance(input_data.get("height"), int) else None,
            thumbnail_url=payload.get("thumbnail")
            if isinstance(payload.get("thumbnail"), str)
            else None,
            playback_id=provider_asset_id,
            error_code=error_code if isinstance(error_code, str) else None,
            error_message=error_message if isinstance(error_message, str) else None,
            raw=json.loads(json.dumps(payload)),
        )

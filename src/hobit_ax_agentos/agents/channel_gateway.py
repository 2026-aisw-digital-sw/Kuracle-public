from __future__ import annotations

from typing import Any
from uuid import uuid4

from hobit_ax_agentos.config import AppSettings
from hobit_ax_agentos.models import IncomingMessage


class ChannelGateway:
    """Normalize channel-specific payloads into IncomingMessage."""

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings()

    def normalize(self, channel: str, payload: dict[str, Any]) -> IncomingMessage:
        if channel == "api":
            return self._from_api(payload)
        if channel in {"web", "portal"}:
            return self._from_web(channel, payload)
        if channel in {"kakaotalk", "kakao"}:
            return self._from_kakao(payload)
        return self._from_generic(channel, payload)

    def _from_api(self, payload: dict[str, Any]) -> IncomingMessage:
        metadata = dict(payload.get("metadata") or {})
        if payload.get("idempotency_key"):
            metadata["idempotency_key"] = str(payload["idempotency_key"])
        return IncomingMessage(
            channel=str(payload.get("channel") or "api"),
            user_id=str(payload.get("user_id") or self.settings.default_user_id),
            text=str(payload.get("text") or payload.get("query") or ""),
            session_id=str(payload.get("session_id") or self.settings.default_session_id),
            attachments=list(payload.get("attachments") or []),
            metadata=metadata,
        )

    def _from_web(self, channel: str, payload: dict[str, Any]) -> IncomingMessage:
        return IncomingMessage(
            channel=channel,
            user_id=str(payload.get("user_id") or payload.get("member_id") or "anonymous"),
            text=str(payload.get("message") or payload.get("text") or ""),
            session_id=str(payload.get("session_id") or f"{channel}-{uuid4().hex[:12]}"),
            attachments=list(payload.get("attachments") or []),
            metadata=self._metadata_with_raw(payload),
        )

    def _from_kakao(self, payload: dict[str, Any]) -> IncomingMessage:
        user_request = payload.get("userRequest", {})
        user = user_request.get("user", {})
        return IncomingMessage(
            channel="kakaotalk",
            user_id=str(user.get("id") or "kakao-user"),
            text=str(user_request.get("utterance") or payload.get("text") or ""),
            session_id=str(payload.get("session_id") or user.get("id") or "kakao-session"),
            metadata=self._metadata_with_raw(payload),
        )

    def _from_generic(self, channel: str, payload: dict[str, Any]) -> IncomingMessage:
        return IncomingMessage(
            channel=channel,
            user_id=str(payload.get("user_id") or self.settings.default_user_id),
            text=str(payload.get("text") or payload.get("message") or ""),
            session_id=str(payload.get("session_id") or self.settings.default_session_id),
            attachments=list(payload.get("attachments") or []),
            metadata=self._metadata_with_raw(payload),
        )

    def _metadata_with_raw(self, payload: dict[str, Any]) -> dict:
        metadata = {"raw": payload}
        if payload.get("idempotency_key"):
            metadata["idempotency_key"] = str(payload["idempotency_key"])
        return metadata

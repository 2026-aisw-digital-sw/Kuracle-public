from __future__ import annotations

from typing import Any


class ChannelGatewayTemplate:
    agent_id = "agent_hobit_channel_gateway"

    def normalize(self, channel: str, payload: dict[str, Any]) -> dict[str, Any]:
        text = str(payload.get("message") or payload.get("text") or "").strip()
        return {
            "channel": channel,
            "user_id": str(payload.get("user_id") or payload.get("member_id") or "web-user"),
            "session_id": str(payload.get("session_id") or "web-session"),
            "text": text,
            "metadata": {"raw": payload},
        }

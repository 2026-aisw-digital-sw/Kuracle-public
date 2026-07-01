from __future__ import annotations

from agents.agent_hobit_channel_gateway.template import ChannelGatewayTemplate


def test_channel_gateway_template_normalizes_minimum_message() -> None:
    result = ChannelGatewayTemplate().normalize("web", {"message": "복수전공 알려줘"})
    assert result["channel"] == "web"
    assert result["text"] == "복수전공 알려줘"
    assert result["user_id"]
    assert result["session_id"]

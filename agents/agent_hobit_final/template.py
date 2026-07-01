from __future__ import annotations

from typing import Any


class FinalResponseAgentTemplate:
    agent_id = "agent_hobit_final"

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        knowledge = payload.get("knowledge") or {}
        action = payload.get("action") or {}
        escalation = payload.get("escalation") or {}
        response = knowledge.get("answer") or "답변을 만들지 못했습니다."
        if escalation.get("requires_human_review"):
            response = f"{response.rstrip()}\n\n담당자가 확인 후 안내해 드리겠습니다."
        return {
            "response": response,
            "delivery": {
                "channel": payload.get("channel", "api"),
                "action_plan": action.get("action_plan"),
                "escalation": escalation,
            },
        }

from __future__ import annotations

from typing import Any


class FinalResponseAgent:
    agent_id = "agent_hobit_final"

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        knowledge = payload.get("knowledge") or {}
        action = payload.get("action") or {}
        escalation = payload.get("escalation") or {}
        response = knowledge.get("answer") or "No answer was generated."
        if escalation.get("requires_human_review"):
            response = (response or "").rstrip()
            if response:
                response = f"{response}\n\n담당자가 확인 후 안내해 드리겠습니다."
            else:
                response = "담당자가 확인 후 안내해 드리겠습니다."
        return {
            "response": response,
            "delivery": {
                "channel": payload.get("channel", "api"),
                "action_plan": action.get("action_plan"),
                "escalation": escalation,
            },
        }


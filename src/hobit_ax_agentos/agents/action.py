from __future__ import annotations

from typing import Any


class ActionAgent:
    agent_id = "agent_hobit_action"

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        knowledge = payload.get("knowledge") or payload
        cited_rule_ids = knowledge.get("cited_rule_ids") or []
        return {
            "action_plan": {
                "title": "Regulation-based action draft",
                "checklist": [
                    "Check required user profile fields",
                    "Verify cited regulation clauses",
                    "Confirm submission path and deadline",
                ],
                "cited_rule_ids": cited_rule_ids,
                "draft": knowledge.get("answer") or "",
            },
            "requires_human_approval": bool(knowledge.get("risk_class") == "HIGH"),
        }


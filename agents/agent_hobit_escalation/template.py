from __future__ import annotations

from typing import Any
from uuid import uuid4


class EscalationAgentTemplate:
    agent_id = "agent_hobit_escalation"

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        knowledge = payload.get("knowledge") or payload
        reason = "human_review_required" if knowledge.get("requires_human_review") else "low_confidence"
        return {
            "requires_human_review": True,
            "reason": reason,
            "escalation_id": f"esc_{uuid4().hex}",
            "review_package": {
                "answer": knowledge.get("answer"),
                "confidence": knowledge.get("confidence"),
                "cited_rule_ids": knowledge.get("cited_rule_ids") or [],
                "unresolved_points": knowledge.get("unresolved_points") or [],
            },
        }

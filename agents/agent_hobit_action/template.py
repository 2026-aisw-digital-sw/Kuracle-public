from __future__ import annotations

from typing import Any


class ActionAgentTemplate:
    agent_id = "agent_hobit_action"

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        knowledge = payload.get("knowledge") or payload
        return {
            "action_plan": {
                "title": "행정 처리 준비안",
                "checklist": [
                    "사용자 프로필 누락 항목 확인",
                    "인용 규정 조항 확인",
                    "신청 경로와 마감일 확인",
                ],
                "cited_rule_ids": knowledge.get("cited_rule_ids") or [],
                "draft": knowledge.get("answer") or "",
            },
            "requires_human_approval": knowledge.get("risk_class") == "HIGH",
        }

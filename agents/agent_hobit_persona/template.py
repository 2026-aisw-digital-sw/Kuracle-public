from __future__ import annotations

from typing import Any


class PersonaWorkerTemplate:
    agent_id = "agent_hobit_persona"

    def build(self, message: dict[str, Any], history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        history = history or []
        issue_types = [
            str(item["issue_type"])
            for item in history
            if item.get("issue_type")
        ][:5]
        return {
            "session_id": message["session_id"],
            "user_id": message["user_id"],
            "top_issue_types": issue_types,
            "predicted_questions": [],
            "profile": dict((message.get("metadata") or {}).get("profile") or {}),
        }

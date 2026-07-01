from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4


class TriggerAgentTemplate:
    agent_id = "agent_hobit_trigger"

    def deadline_check(
        self,
        user_id: str,
        session_id: str,
        issue_type: str,
        deadline: date,
        today: date,
    ) -> dict[str, Any] | None:
        days_left = (deadline - today).days
        if days_left < 0 or days_left > 7:
            return None
        return {
            "trigger_id": f"trigger_{uuid4().hex}",
            "event_type": "deadline_check",
            "user_id": user_id,
            "session_id": session_id,
            "message": {
                "channel": "trigger",
                "user_id": user_id,
                "session_id": session_id,
                "text": f"{issue_type} 마감이 {days_left}일 남았습니다.",
                "metadata": {
                    "trigger": "deadline_check",
                    "issue_type": issue_type,
                    "deadline": deadline.isoformat(),
                    "days_left": days_left,
                },
            },
        }

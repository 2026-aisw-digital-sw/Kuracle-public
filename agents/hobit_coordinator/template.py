from __future__ import annotations

from typing import Any


class CoordinatorTemplate:
    agent_id = "hobit_coordinator"

    def classify(self, message: dict[str, Any]) -> dict[str, str]:
        text = str(message.get("text") or "").lower()
        if any(token in text for token in ["신청", "제출", "apply", "submit"]):
            intent_family = "actionable_regulation"
        elif any(token in text for token in ["마감", "기간", "deadline"]):
            intent_family = "deadline_question"
        else:
            intent_family = "regulation_question"
        return {"intent_family": intent_family}

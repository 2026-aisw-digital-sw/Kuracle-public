from __future__ import annotations

from collections import Counter
from typing import Any

from hobit_ax_agentos.models import IncomingMessage, PersonaSnapshot


class PersonaWorker:
    """Deterministic first-pass persona context builder."""

    def build(
        self,
        message: IncomingMessage,
        history: list[dict[str, Any]] | None = None,
    ) -> PersonaSnapshot:
        history = history or []
        issue_types = self._issue_types(message, history)
        return PersonaSnapshot(
            session_id=message.session_id,
            user_id=message.user_id,
            top_issue_types=issue_types,
            predicted_questions=self._predicted_questions(issue_types),
            profile=dict(message.metadata.get("profile") or {}),
        )

    def _issue_types(
        self,
        message: IncomingMessage,
        history: list[dict[str, Any]],
    ) -> list[str]:
        counter: Counter[str] = Counter()
        for item in history:
            issue = item.get("issue_type") or item.get("request_type")
            if issue:
                counter[str(issue)] += 1
        lowered = message.text.lower()
        keyword_map = {
            "academic.plural_major": ["\ubcf5\uc218\uc804\uacf5", "double major"],
            "academic.leave_of_absence": ["\ud734\ud559", "leave"],
            "academic.course_registration": ["\uc218\uac15\uc2e0\uccad", "course"],
            "scholarship.general": ["\uc7a5\ud559", "scholarship"],
        }
        for issue_type, keywords in keyword_map.items():
            if any(keyword.lower() in lowered for keyword in keywords):
                counter[issue_type] += 3
        return [issue for issue, _ in counter.most_common(5)]

    def _predicted_questions(self, issue_types: list[str]) -> list[str]:
        templates = {
            "academic.plural_major": "\ubcf5\uc218\uc804\uacf5 \uc2e0\uccad \uc790\uaca9\uc740 \ubb50\uc57c?",
            "academic.leave_of_absence": "\ud734\ud559 \uc2e0\uccad\uc5d0 \ud544\uc694\ud55c \uc11c\ub958\ub294?",
            "academic.course_registration": "\uc218\uac15\uc2e0\uccad \uc815\uc815 \uae30\uac04\uc740 \uc5b8\uc81c\uc57c?",
            "scholarship.general": "\uc7a5\ud559\uae08 \uc720\uc9c0 \uc870\uac74\uc740 \ubb50\uc57c?",
        }
        return [templates[issue] for issue in issue_types if issue in templates][:5]

from __future__ import annotations

from datetime import date

from agents.agent_hobit_trigger.template import TriggerAgentTemplate


def test_trigger_template_emits_due_deadline_event() -> None:
    event = TriggerAgentTemplate().deadline_check(
        "u1", "s1", "복수전공", date(2026, 7, 5), date(2026, 7, 1)
    )
    assert event is not None
    assert event["message"]["channel"] == "trigger"
    assert event["message"]["metadata"]["days_left"] == 4

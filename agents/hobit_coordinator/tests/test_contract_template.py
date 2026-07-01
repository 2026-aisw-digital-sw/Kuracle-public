from __future__ import annotations

from agents.hobit_coordinator.template import CoordinatorTemplate


def test_coordinator_template_classifies_actionable_text() -> None:
    result = CoordinatorTemplate().classify({"text": "복수전공 신청 방법"})
    assert result["intent_family"] == "actionable_regulation"

from __future__ import annotations

from agents.agent_hobit_escalation.template import EscalationAgentTemplate


def test_escalation_template_returns_review_package() -> None:
    result = EscalationAgentTemplate().run({"answer": "A", "confidence": 0.4})
    assert result["requires_human_review"] is True
    assert result["escalation_id"].startswith("esc_")
    assert result["review_package"]["answer"] == "A"

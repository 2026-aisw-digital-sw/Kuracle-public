from __future__ import annotations

from agents.agent_hobit_action.template import ActionAgentTemplate


def test_action_template_requires_approval_for_high_risk() -> None:
    result = ActionAgentTemplate().run({"risk_class": "HIGH", "cited_rule_ids": ["r1"]})
    assert result["requires_human_approval"] is True
    assert result["action_plan"]["cited_rule_ids"] == ["r1"]

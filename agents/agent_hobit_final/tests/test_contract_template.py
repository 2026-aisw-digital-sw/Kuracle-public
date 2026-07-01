from __future__ import annotations

from agents.agent_hobit_final.template import FinalResponseAgentTemplate


def test_final_template_mentions_human_review() -> None:
    result = FinalResponseAgentTemplate().run(
        {
            "knowledge": {"answer": "기본 답변"},
            "escalation": {"requires_human_review": True},
        }
    )
    assert "담당자" in result["response"]
    assert result["delivery"]["escalation"]["requires_human_review"] is True

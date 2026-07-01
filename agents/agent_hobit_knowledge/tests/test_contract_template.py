from __future__ import annotations

from agents.agent_hobit_knowledge.template import KnowledgeAgentTemplate


def test_knowledge_template_returns_branch_flags() -> None:
    result = KnowledgeAgentTemplate().run({"message": {"text": "복수전공"}})
    assert "requires_action" in result
    assert "requires_human_review" in result
    assert isinstance(result["cited_rule_ids"], list)

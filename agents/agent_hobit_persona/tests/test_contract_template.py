from __future__ import annotations

from agents.agent_hobit_persona.template import PersonaWorkerTemplate


def test_persona_template_preserves_identity() -> None:
    result = PersonaWorkerTemplate().build(
        {"session_id": "s1", "user_id": "u1", "metadata": {}},
        [{"issue_type": "academic.plural_major"}],
    )
    assert result["session_id"] == "s1"
    assert result["top_issue_types"] == ["academic.plural_major"]

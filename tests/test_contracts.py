from __future__ import annotations

import pytest

from hobit_ax_agentos.agentos.contracts import (
    AgentContractError,
    validate_output_contract,
)
from hobit_ax_agentos.schemas import KNOWLEDGE_OUTPUT_SCHEMA


def test_validate_output_contract_accepts_matching_result() -> None:
    validate_output_contract(
        agent_id="agent_hobit_knowledge",
        node_id="knowledge_query",
        result={
            "answer": "Use the portal.",
            "confidence": 0.92,
            "requires_action": False,
            "requires_human_review": False,
            "risk_class": "LOW",
            "cited_rule_ids": ["rule_1"],
        },
        schema=KNOWLEDGE_OUTPUT_SCHEMA,
    )


def test_validate_output_contract_rejects_missing_required_field() -> None:
    with pytest.raises(AgentContractError) as exc:
        validate_output_contract(
            agent_id="agent_hobit_knowledge",
            node_id="knowledge_query",
            result={
                "answer": "Use the portal.",
                "confidence": 0.92,
                "requires_action": False,
                "risk_class": "LOW",
            },
            schema=KNOWLEDGE_OUTPUT_SCHEMA,
        )

    assert "requires_human_review is required" in str(exc.value)


def test_validate_output_contract_rejects_wrong_type() -> None:
    with pytest.raises(AgentContractError) as exc:
        validate_output_contract(
            agent_id="agent_hobit_knowledge",
            node_id="knowledge_query",
            result={
                "answer": "Use the portal.",
                "confidence": "high",
                "requires_action": False,
                "requires_human_review": False,
                "risk_class": "LOW",
            },
            schema=KNOWLEDGE_OUTPUT_SCHEMA,
        )

    assert "$.confidence expected number" in str(exc.value)

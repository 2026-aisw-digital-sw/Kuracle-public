from __future__ import annotations

import pytest

from hobit_ax_agentos.agentos.plan_validation import (
    PlanExecutionError,
    summarize_plan_execution,
    validate_lease_against_plan,
)
from hobit_ax_agentos.models import CoordinationPlan


def _plan() -> CoordinationPlan:
    return CoordinationPlan(
        plan_id="plan_1",
        session_id="session_1",
        user_id="user_1",
        channel="api",
        intent_family="regulation_question",
        selected_agents=["agent_hobit_knowledge", "agent_hobit_final"],
        skipped_agents=["agent_hobit_action"],
        graph_nodes=[
            {
                "node_id": "knowledge_query",
                "assigned_agent_id": "agent_hobit_knowledge",
            },
            {
                "node_id": "final_response",
                "assigned_agent_id": "agent_hobit_final",
            },
        ],
    )


def test_validate_lease_against_plan_accepts_planned_node() -> None:
    validate_lease_against_plan(
        plan=_plan(),
        node_id="knowledge_query",
        agent_id="agent_hobit_knowledge",
    )


def test_validate_lease_against_plan_rejects_unplanned_node() -> None:
    with pytest.raises(PlanExecutionError) as exc:
        validate_lease_against_plan(
            plan=_plan(),
            node_id="rogue_node",
            agent_id="agent_hobit_knowledge",
        )

    assert "rogue_node is not in coordination plan" in str(exc.value)


def test_summarize_plan_execution_reports_sequence() -> None:
    summary = summarize_plan_execution(
        plan=_plan(),
        worker_results=[
            {"node_id": "knowledge_query", "agent_id": "agent_hobit_knowledge"},
            {"node_id": "final_response", "agent_id": "agent_hobit_final"},
        ],
    )

    assert summary["valid"] is True
    assert summary["executed_nodes"] == ["knowledge_query", "final_response"]
    assert summary["violations"] == []


def test_summarize_plan_execution_detects_skipped_agent() -> None:
    plan = _plan()
    plan.graph_nodes.append(
        {
            "node_id": "action_prepare",
            "assigned_agent_id": "agent_hobit_action",
        }
    )

    summary = summarize_plan_execution(
        plan=plan,
        worker_results=[
            {"node_id": "action_prepare", "agent_id": "agent_hobit_action"},
        ],
    )

    assert summary["valid"] is False
    assert "skipped_agent_executed:agent_hobit_action" in summary["violations"]

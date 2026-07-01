from __future__ import annotations

from hobit_ax_agentos.agents.persona import PersonaWorker
from hobit_ax_agentos.models import (
    AgentRunRecord,
    CoordinationPlan,
    EscalationCase,
    IncomingMessage,
)
from hobit_ax_agentos.services.run_trace import RunTraceService
from hobit_ax_agentos.storage import (
    ConversationStore,
    CoordinationPlanStore,
    EscalationStore,
    OutboxStore,
    PersonaStore,
    RunStore,
)


def test_run_trace_joins_related_records(tmp_path) -> None:
    message = IncomingMessage("api", "user_1", "double major", "session_1")
    ConversationStore(tmp_path).append_message(message)
    PersonaStore(tmp_path).append(PersonaWorker().build(message))
    CoordinationPlanStore(tmp_path).save(
        CoordinationPlan(
            plan_id="plan_1",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            intent_family="regulation_question",
            selected_agents=["agent_hobit_knowledge", "agent_hobit_final"],
        )
    )
    RunStore(tmp_path).save(
        AgentRunRecord(
            run_id="run_1",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            state="COMPLETED",
            trace_id="trace_1",
            coordination_plan_id="plan_1",
            final={"response": "answer"},
            run_summary={
                "state": "COMPLETED",
                "lifecycle_events": [
                    {
                        "event": "run.started",
                        "run_id": "run_1",
                        "at": "2026-01-01T00:00:00+00:00",
                    },
                    {
                        "event": "node.completed",
                        "run_id": "run_1",
                        "node_id": "knowledge_query",
                        "agent_id": "agent_hobit_knowledge",
                        "at": "2026-01-01T00:00:01+00:00",
                    },
                ],
            },
            worker_results=[{"node_id": "knowledge_query"}],
        )
    )
    OutboxStore(tmp_path).append_response(
        session_id="session_1",
        user_id="user_1",
        channel="api",
        text="answer",
        run_id="run_1",
        trace_id="trace_1",
    )
    EscalationStore(tmp_path).save(
        EscalationCase(
            escalation_id="esc_1",
            session_id="session_1",
            user_id="user_1",
            reason="review",
            run_id="run_1",
            trace_id="trace_1",
        )
    )

    trace = RunTraceService(tmp_path).trace("run_1")

    assert trace is not None
    assert trace["run"]["run_id"] == "run_1"
    assert trace["coordination_plan"]["plan_id"] == "plan_1"
    assert trace["latest_persona"]["top_issue_types"] == ["academic.plural_major"]
    assert [event["event"] for event in trace["lifecycle_events"]] == [
        "run.started",
        "node.completed",
    ]
    assert trace["worker_results"] == [{"node_id": "knowledge_query"}]
    assert trace["related"]["conversation_turns"][0]["text"] == "double major"
    assert trace["related"]["outbox"][0]["text"] == "answer"
    assert trace["related"]["escalations"][0]["escalation_id"] == "esc_1"


def test_run_trace_returns_none_for_missing_run(tmp_path) -> None:
    assert RunTraceService(tmp_path).trace("missing") is None

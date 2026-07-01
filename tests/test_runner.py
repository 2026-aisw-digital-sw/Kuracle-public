from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hobit_ax_agentos.agentos.contracts import AgentContractError
from hobit_ax_agentos.agentos.plan_validation import PlanExecutionError
from hobit_ax_agentos.agentos.runner import ServiceRunner
from hobit_ax_agentos.agents.knowledge import KnowledgeAgent
from hobit_ax_agentos.config import AppSettings
from hobit_ax_agentos.models import IncomingMessage
from hobit_ax_agentos.storage import (
    ConversationStore,
    CoordinationPlanStore,
    EscalationStore,
    IdempotencyStore,
    OutboxStore,
    PersonaStore,
    RunStore,
)


class AnsweredAdapter:
    def run_supervisor(self, query: str, profile: dict | None = None, session_id: str | None = None) -> dict:
        return {
            "raw_query": query,
            "workflow_status": "ANSWERED",
            "parsed_intent": {
                "intent_mode": "deadline",
                "request_type": "academic.plural_major",
            },
            "issue_graph": [{"issue_type": "academic.plural_major"}],
            "grounded_answer": {
                "summary": "Double major applications are handled through the portal.",
                "cited_rule_ids": ["rule_1"],
                "unresolved_points": [],
            },
            "evidence_packets": [{"confidence": 0.92}],
        }


class EscalatedAdapter:
    def run_supervisor(self, query: str, profile: dict | None = None, session_id: str | None = None) -> dict:
        return {
            "raw_query": query,
            "workflow_status": "ESCALATED",
            "parsed_intent": {
                "intent_mode": "deadline",
                "request_type": "academic.plural_major",
            },
            "issue_graph": [{"issue_type": "academic.plural_major"}],
            "grounded_answer": {
                "summary": "This needs manual confirmation.",
                "cited_rule_ids": [],
                "unresolved_points": ["deadline source missing"],
            },
            "evidence_packets": [{"confidence": 0.3}],
        }


class BrokenAdapter:
    def run_supervisor(self, query: str, profile: dict | None = None, session_id: str | None = None) -> dict:
        raise RuntimeError("adapter exploded")


class BrokenFinalAgent:
    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"delivery": {"channel": payload.get("channel", "api")}}


@dataclass(slots=True)
class FakeKernelLease:
    lease_id: str
    run_id: str
    trace_id: str
    node: dict[str, Any]
    assigned_agent_id: str


class FakeKernelClient:
    def __init__(self) -> None:
        self.capabilities: list[Any] = []
        self.graph: dict[str, Any] | None = None
        self.results: dict[str, dict[str, Any]] = {}
        self.leased: set[str] = set()
        self.skipped: set[str] = set()
        self.state = "RUNNING"

    def register_capability(self, capability) -> None:
        self.capabilities.append(capability)

    def submit_graph(self, graph) -> dict[str, str]:
        self.graph = graph.to_dict()
        return {"run_id": "run_1"}

    def get_run(self, run_id: str) -> dict[str, Any]:
        return {"run_id": run_id, "trace_id": "trace_1", "state": self.state}

    def lease_next_task(self, agent_id: str):
        assert self.graph is not None
        self._skip_false_condition_nodes()
        for node in self.graph["nodes"]:
            node_id = node["node_id"]
            if node_id in self.results or node_id in self.leased or node_id in self.skipped:
                continue
            if node["assigned_agent_id"] != agent_id:
                continue
            if not self._dependencies_satisfied(node_id):
                continue
            self.leased.add(node_id)
            return FakeKernelLease(
                lease_id=f"lease_{node_id}",
                run_id="run_1",
                trace_id="trace_1",
                node=node,
                assigned_agent_id=agent_id,
            )
        return None

    def request_action(self, action) -> dict[str, Any]:
        node_id = action.node_id
        self.results[node_id] = action.args["result"]
        self.leased.discard(node_id)
        self._skip_false_condition_nodes()
        if self._all_terminal():
            self.state = "COMPLETED"
        return {
            "accepted": True,
            "node_id": node_id,
            "policy_user_id": action.policy_context.user_id,
            "policy_session_id": action.policy_context.session_id,
        }

    def _incoming_edges(self, node_id: str) -> list[dict[str, Any]]:
        assert self.graph is not None
        return [edge for edge in self.graph["edges"] if edge["to_node_id"] == node_id]

    def _dependencies_satisfied(self, node_id: str) -> bool:
        for edge in self._incoming_edges(node_id):
            source = edge["from_node_id"]
            if source not in self.results and source not in self.skipped:
                return False
            if source in self.results and not self._condition_matches(edge):
                return False
        return True

    def _skip_false_condition_nodes(self) -> None:
        assert self.graph is not None
        for edge in self.graph["edges"]:
            if not edge.get("condition_expr"):
                continue
            source = edge["from_node_id"]
            target = edge["to_node_id"]
            if source in self.results and not self._condition_matches(edge):
                self.skipped.add(target)

    def _condition_matches(self, edge: dict[str, Any]) -> bool:
        expr = edge.get("condition_expr")
        if expr is None:
            return True
        if "==" not in expr:
            return False
        key, expected_raw = [part.strip() for part in expr.split("==", 1)]
        expected = expected_raw.lower() == "true"
        return bool(self.results[edge["from_node_id"]].get(key)) is expected

    def _all_terminal(self) -> bool:
        assert self.graph is not None
        return all(
            node["node_id"] in self.results or node["node_id"] in self.skipped
            for node in self.graph["nodes"]
        )


class StalledKernelClient(FakeKernelClient):
    def lease_next_task(self, agent_id: str):
        return None


class RogueKernelClient(FakeKernelClient):
    def __init__(self) -> None:
        super().__init__()
        self.rogue_leased = False

    def lease_next_task(self, agent_id: str):
        if agent_id != "agent_hobit_knowledge" or self.rogue_leased:
            return None
        self.rogue_leased = True
        return FakeKernelLease(
            lease_id="lease_rogue",
            run_id="run_1",
            trace_id="trace_1",
            node={
                "node_id": "rogue_node",
                "assigned_agent_id": "agent_hobit_knowledge",
            },
            assigned_agent_id="agent_hobit_knowledge",
        )


def test_service_runner_executes_non_action_graph_end_to_end(tmp_path) -> None:
    fake_client = FakeKernelClient()
    settings = AppSettings(data_dir=tmp_path, enable_action_agent=False)
    runner = ServiceRunner(
        settings=settings,
        kernel_client_factory=lambda: fake_client,
        knowledge_agent=KnowledgeAgent(adapter=AnsweredAdapter()),
    )

    result = runner.run_message(
        IncomingMessage(
            channel="api",
            user_id="user_1",
            session_id="session_1",
            text="When is double major deadline?",
        ),
        timeout_seconds=2.0,
    )

    turns = ConversationStore(tmp_path).list_by_session("session_1")
    plans = CoordinationPlanStore(tmp_path).list_by_session("session_1")
    personas = PersonaStore(tmp_path).list_by_session("session_1")
    runs = RunStore(tmp_path).list_by_session("session_1")
    deliveries = OutboxStore(tmp_path).list_by_session("session_1")

    assert result.run_summary["state"] == "COMPLETED"
    assert result.final is not None
    assert result.final["response"] == "Double major applications are handled through the portal."
    assert [capability.capability_id for capability in fake_client.capabilities] == [
        "cap.agent_hobit_knowledge",
        "cap.agent_hobit_escalation",
        "cap.agent_hobit_final",
    ]
    assert fake_client.capabilities[0].output_schema["required"]
    assert "escalation_prepare" not in fake_client.results
    assert EscalationStore(tmp_path).list_all() == []
    assert [turn.role for turn in turns] == ["USER", "ASSISTANT"]
    assert plans[0].skipped_agents == ["agent_hobit_action"]
    assert personas[0].top_issue_types == ["academic.plural_major"]
    assert deliveries[0].status == "PENDING"
    assert deliveries[0].channel == "api"
    assert deliveries[0].text == result.final["response"]
    assert runs[0].state == "COMPLETED"
    assert runs[0].final == result.final
    assert [item["node_id"] for item in runs[0].worker_results] == [
        "knowledge_query",
        "final_response",
    ]
    assert result.worker_results[0]["action_result"]["policy_user_id"] == "user_1"
    assert result.worker_results[0]["action_result"]["policy_session_id"] == "session_1"
    assert result.run_summary["plan_execution"]["valid"] is True
    assert result.run_summary["plan_execution"]["executed_nodes"] == [
        "knowledge_query",
        "final_response",
    ]
    assert [event["event"] for event in result.run_summary["lifecycle_events"]] == [
        "run.started",
        "node.leased",
        "node.started",
        "node.completed",
        "node.leased",
        "node.started",
        "node.completed",
        "run.finished",
    ]
    assert result.run_summary["lifecycle_events"][1]["node_id"] == "knowledge_query"


def test_service_runner_records_actual_classification_on_plan(tmp_path) -> None:
    fake_client = FakeKernelClient()
    settings = AppSettings(data_dir=tmp_path, enable_action_agent=False)
    runner = ServiceRunner(
        settings=settings,
        kernel_client_factory=lambda: fake_client,
        knowledge_agent=KnowledgeAgent(adapter=AnsweredAdapter()),
    )

    result = runner.run_message(
        IncomingMessage(
            channel="api",
            user_id="user_1",
            session_id="session_1",
            text="When is double major deadline?",
        ),
        timeout_seconds=2.0,
    )

    plans = CoordinationPlanStore(tmp_path).list_by_session("session_1")

    assert result.run_summary["state"] == "COMPLETED"
    assert "preliminary_classification" in plans[0].routing_reasons
    assert plans[0].routing_reasons["actual_classification"] == {
        "intent_mode": "deadline",
        "request_type": "academic.plural_major",
        "issue_types": ["academic.plural_major"],
    }


def test_service_runner_clears_results_between_runs(tmp_path) -> None:
    settings = AppSettings(data_dir=tmp_path, enable_action_agent=False)
    runner = ServiceRunner(
        settings=settings,
        kernel_client_factory=FakeKernelClient,
        knowledge_agent=KnowledgeAgent(adapter=AnsweredAdapter()),
    )

    first = runner.run_message(
        IncomingMessage("api", "user_1", "first question", "session_1"),
        timeout_seconds=2.0,
    )
    second = runner.run_message(
        IncomingMessage("api", "user_1", "second question", "session_1"),
        timeout_seconds=2.0,
    )

    assert first.run_id == "run_1"
    assert second.final is not None
    assert len(ConversationStore(tmp_path).list_by_session("session_1")) == 4


def test_service_runner_reuses_idempotent_run(tmp_path) -> None:
    fake_client = FakeKernelClient()
    settings = AppSettings(data_dir=tmp_path, enable_action_agent=False)
    runner = ServiceRunner(
        settings=settings,
        kernel_client_factory=lambda: fake_client,
        knowledge_agent=KnowledgeAgent(adapter=AnsweredAdapter()),
    )

    first = runner.run_message(
        IncomingMessage(
            "api",
            "user_1",
            "When is double major deadline?",
            "session_1",
            metadata={"idempotency_key": "request_1"},
        ),
        timeout_seconds=2.0,
    )
    second = runner.run_message(
        IncomingMessage(
            "api",
            "user_1",
            "When is double major deadline?",
            "session_1",
            metadata={"idempotency_key": "request_1"},
        ),
        timeout_seconds=2.0,
    )

    assert second.run_id == first.run_id
    assert second.final == first.final
    assert second.run_summary["idempotency_reused"] is True
    assert len(RunStore(tmp_path).list_by_session("session_1")) == 1
    assert len(ConversationStore(tmp_path).list_by_session("session_1")) == 2
    assert len(OutboxStore(tmp_path).list_by_session("session_1")) == 1
    assert IdempotencyStore(tmp_path).get("request_1")["run_id"] == first.run_id


def test_service_runner_executes_escalation_branch_when_review_required(tmp_path) -> None:
    fake_client = FakeKernelClient()
    settings = AppSettings(data_dir=tmp_path, enable_action_agent=False)
    runner = ServiceRunner(
        settings=settings,
        kernel_client_factory=lambda: fake_client,
        knowledge_agent=KnowledgeAgent(adapter=EscalatedAdapter()),
    )

    result = runner.run_message(
        IncomingMessage(
            channel="api",
            user_id="user_1",
            session_id="session_1",
            text="Please verify the double major deadline.",
        ),
        timeout_seconds=2.0,
    )

    cases = EscalationStore(tmp_path).list_all()
    runs = RunStore(tmp_path).list_by_session("session_1")

    assert result.run_summary["state"] == "COMPLETED"
    assert "escalation_prepare" in fake_client.results
    assert len(cases) == 1
    assert cases[0].reason == "high_risk"
    assert cases[0].session_id == "session_1"
    assert [item["node_id"] for item in runs[0].worker_results] == [
        "knowledge_query",
        "escalation_prepare",
        "final_response",
    ]
    assert result.final is not None
    assert "담당자가 확인 후 안내해 드리겠습니다." in result.final["response"]
    assert result.final["delivery"]["escalation"]["reason"] == "high_risk"


def test_service_runner_records_failed_run_on_worker_error(tmp_path) -> None:
    settings = AppSettings(data_dir=tmp_path, enable_action_agent=False)
    runner = ServiceRunner(
        settings=settings,
        kernel_client_factory=FakeKernelClient,
        knowledge_agent=KnowledgeAgent(adapter=BrokenAdapter()),
    )

    try:
        runner.run_message(
            IncomingMessage("api", "user_1", "broken question", "session_1"),
            timeout_seconds=2.0,
        )
    except RuntimeError as exc:
        assert str(exc) == "adapter exploded"
    else:
        raise AssertionError("expected worker error")

    runs = RunStore(tmp_path).list_by_session("session_1")

    assert runs[0].state == "FAILED"
    assert runs[0].run_summary["error_type"] == "RuntimeError"
    assert runs[0].run_summary["failed_node_id"] == "knowledge_query"
    assert runs[0].final is None


def test_service_runner_records_failed_run_on_contract_violation(tmp_path) -> None:
    settings = AppSettings(data_dir=tmp_path, enable_action_agent=False)
    runner = ServiceRunner(
        settings=settings,
        kernel_client_factory=FakeKernelClient,
        knowledge_agent=KnowledgeAgent(adapter=AnsweredAdapter()),
        final_agent=BrokenFinalAgent(),
    )

    try:
        runner.run_message(
            IncomingMessage("api", "user_1", "contract question", "session_1"),
            timeout_seconds=2.0,
        )
    except AgentContractError as exc:
        assert "agent_hobit_final/final_response output contract violation" in str(exc)
    else:
        raise AssertionError("expected contract violation")

    runs = RunStore(tmp_path).list_by_session("session_1")

    assert runs[0].state == "FAILED"
    assert runs[0].run_summary["error_type"] == "AgentContractError"
    assert runs[0].run_summary["failed_node_id"] == "final_response"
    assert runs[0].run_summary["failed_agent_id"] == "agent_hobit_final"
    assert runs[0].run_summary["lifecycle_events"][-1]["event"] == "node.failed"
    assert runs[0].run_summary["lifecycle_events"][-1]["node_id"] == "final_response"
    assert runs[0].final is None
    assert OutboxStore(tmp_path).list_by_session("session_1") == []


def test_service_runner_rejects_unplanned_kernel_lease(tmp_path) -> None:
    settings = AppSettings(data_dir=tmp_path, enable_action_agent=False)
    runner = ServiceRunner(
        settings=settings,
        kernel_client_factory=RogueKernelClient,
        knowledge_agent=KnowledgeAgent(adapter=AnsweredAdapter()),
    )

    try:
        runner.run_message(
            IncomingMessage("api", "user_1", "rogue lease", "session_1"),
            timeout_seconds=2.0,
        )
    except PlanExecutionError as exc:
        assert "rogue_node is not in coordination plan" in str(exc)
    else:
        raise AssertionError("expected plan execution error")

    runs = RunStore(tmp_path).list_by_session("session_1")

    assert runs[0].state == "FAILED"
    assert runs[0].run_summary["error_type"] == "PlanExecutionError"
    assert runs[0].run_summary["failed_node_id"] == "rogue_node"
    assert runs[0].run_summary["failed_agent_id"] == "agent_hobit_knowledge"
    assert [event["event"] for event in runs[0].run_summary["lifecycle_events"]] == [
        "run.started",
        "node.leased",
        "node.failed",
    ]


def test_service_runner_records_timed_out_run(tmp_path) -> None:
    settings = AppSettings(data_dir=tmp_path, enable_action_agent=False)
    runner = ServiceRunner(
        settings=settings,
        kernel_client_factory=StalledKernelClient,
        knowledge_agent=KnowledgeAgent(adapter=AnsweredAdapter()),
    )

    try:
        runner.run_message(
            IncomingMessage("api", "user_1", "slow question", "session_1"),
            timeout_seconds=0.01,
        )
    except TimeoutError:
        pass
    else:
        raise AssertionError("expected timeout")

    runs = RunStore(tmp_path).list_by_session("session_1")

    assert runs[0].state == "TIMED_OUT"
    assert runs[0].run_summary["error_type"] == "TimeoutError"
    assert runs[0].run_summary["lifecycle_events"][-1]["event"] == "run.timed_out"
    assert runs[0].final is None

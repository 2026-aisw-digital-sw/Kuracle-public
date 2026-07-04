from __future__ import annotations

from datetime import date

from hobit_ax_agentos.agents.channel_gateway import ChannelGateway
from hobit_ax_agentos.agents.coordinator import CoordinatorAgent
from hobit_ax_agentos.agents.escalation import EscalationAgent
from hobit_ax_agentos.agents.final_response import FinalResponseAgent
from hobit_ax_agentos.agents.knowledge import KnowledgeAgent
from hobit_ax_agentos.agents.persona import PersonaWorker
from hobit_ax_agentos.agents.trigger import TriggerAgent
from hobit_ax_agentos.config import AppSettings
from hobit_ax_agentos.models import IncomingMessage
from hobit_ax_agentos.storage import (
    ConversationStore,
    CoordinationPlanStore,
    DeadlineWatchStore,
    EscalationStore,
    PersonaStore,
)


class FakeAdapter:
    def run_supervisor(self, query: str, profile: dict | None = None, session_id: str | None = None) -> dict:
        return {
            "raw_query": query,
            "workflow_status": "ANSWERED",
            "parsed_intent": {
                "intent_mode": "deadline",
                "request_type": "academic.plural_major",
            },
            "issue_graph": [
                {
                    "issue_id": "I1",
                    "issue_type": "academic.plural_major",
                    "role": "deadline",
                }
            ],
            "coverage_report": {"coverage_score": 0.9},
            "grounded_answer": {
                "summary": "Double major applications are handled through the portal.",
                "cited_rule_ids": ["rule_1"],
                "unresolved_points": [],
                "regulation_gaps": [],
                "profile_gaps": [],
            },
            "evidence_packets": [{"confidence": 0.9}],
        }

    def run_action_agent(self, knowledge_result: dict, profile: dict | None = None) -> dict:
        state = knowledge_result.get("state") or {}
        issue_graph = state.get("issue_graph") or []
        issue_type = issue_graph[0].get("issue_type") if issue_graph else "academic.plural_major"
        return {
            "action_plan": {
                "issue_type": issue_type,
                "form_name": "신청서",
                "action_type": "checklist",
                "steps": [],
                "pre_filled_form": [],
                "required_docs": ["신청서"],
                "portal_url": None,
                "deadline": None,
                "cautions": [],
            },
            "requires_human_approval": False,
        }


def test_channel_gateway_normalizes_api_payload() -> None:
    message = ChannelGateway().normalize(
        "api",
        {
            "query": "When is double major application?",
            "user_id": "user_1",
            "session_id": "session_1",
        },
    )

    assert message.channel == "api"
    assert message.user_id == "user_1"
    assert message.text == "When is double major application?"


def test_knowledge_agent_returns_structured_state() -> None:
    result = KnowledgeAgent(adapter=FakeAdapter()).run(
        {"message": {"text": "When is double major application?"}}
    )

    assert result["answer"]
    assert result["confidence"] == 0.9
    assert result["requires_human_review"] is False
    assert result["issue_types"] == ["academic.plural_major"]
    assert result["coverage_report"]["coverage_score"] == 0.9


def test_persona_worker_predicts_from_message() -> None:
    snapshot = PersonaWorker().build(
        IncomingMessage(
            channel="api",
            user_id="user_1",
            session_id="session_1",
            text="\ubcf5\uc218\uc804\uacf5 \uc2e0\uccad \uc900\ube44\ud574\uc57c \ud574",
        )
    )

    assert snapshot.top_issue_types == ["academic.plural_major"]
    assert snapshot.predicted_questions
    assert snapshot.created_at


def test_persona_store_persists_latest_snapshot(tmp_path) -> None:
    store = PersonaStore(tmp_path)
    first = PersonaWorker().build(
        IncomingMessage(
            channel="api",
            user_id="user_1",
            session_id="session_1",
            text="double major",
        )
    )
    second = PersonaWorker().build(
        IncomingMessage(
            channel="api",
            user_id="user_1",
            session_id="session_1",
            text="scholarship",
        )
    )

    store.append(first)
    store.append(second)
    latest = store.latest("session_1")

    assert latest is not None
    assert latest.top_issue_types == ["scholarship.general"]
    assert len(store.list_by_session("session_1")) == 2


def test_trigger_agent_emits_deadline_event_inside_window() -> None:
    event = TriggerAgent().deadline_check(
        user_id="user_1",
        session_id="session_1",
        issue_type="academic.plural_major",
        deadline=date(2026, 7, 5),
        today=date(2026, 7, 1),
    )

    assert event is not None
    assert event.metadata["days_left"] == 4


def test_trigger_agent_registers_and_emits_due_deadline_watch(tmp_path) -> None:
    store = DeadlineWatchStore(tmp_path)
    agent = TriggerAgent(watch_store=store)
    watch = agent.register_deadline_watch(
        user_id="user_1",
        session_id="session_1",
        issue_type="academic.plural_major",
        deadline=date(2026, 7, 5),
        reminder_window_days=7,
    )

    events = agent.due_deadline_events(today=date(2026, 7, 1))
    duplicate_events = agent.due_deadline_events(today=date(2026, 7, 1))
    stored = store.get(watch.watch_id)

    assert len(events) == 1
    assert events[0].metadata["watch_id"] == watch.watch_id
    assert duplicate_events == []
    assert stored is not None
    assert stored.last_triggered_on == "2026-07-01"


class FakeReconcileAdapter:
    def __init__(self, affected_issue_types: list[str]) -> None:
        self.affected_issue_types = affected_issue_types

    def reconcile_regulations(self) -> dict:
        return {
            "has_changes": bool(self.affected_issue_types),
            "needs_reingest": ["REG_LEAVE_OF_ABSENCE"],
            "affected_issue_types": self.affected_issue_types,
        }


def test_trigger_agent_emits_regulation_changed_events_for_watched_issue_types(
    tmp_path,
) -> None:
    store = DeadlineWatchStore(tmp_path)
    agent = TriggerAgent(
        watch_store=store,
        adapter=FakeReconcileAdapter(["academic.plural_major"]),
    )
    watched = agent.register_deadline_watch(
        user_id="user_1",
        session_id="session_1",
        issue_type="academic.plural_major",
        deadline=date(2026, 12, 1),
    )
    unaffected = agent.register_deadline_watch(
        user_id="user_2",
        session_id="session_2",
        issue_type="scholarship.general",
        deadline=date(2026, 12, 1),
    )

    events = agent.regulation_change_events()

    assert len(events) == 1
    assert events[0].user_id == "user_1"
    assert events[0].event_type == "regulation_changed"
    assert events[0].metadata["issue_type"] == "academic.plural_major"
    assert unaffected.issue_type == "scholarship.general"


def test_trigger_agent_emits_no_regulation_changed_events_when_nothing_changed(
    tmp_path,
) -> None:
    store = DeadlineWatchStore(tmp_path)
    agent = TriggerAgent(watch_store=store, adapter=FakeReconcileAdapter([]))
    agent.register_deadline_watch(
        user_id="user_1",
        session_id="session_1",
        issue_type="academic.plural_major",
        deadline=date(2026, 12, 1),
    )

    assert agent.regulation_change_events() == []


def test_trigger_agent_completes_deadline_watch_on_deadline_day(tmp_path) -> None:
    store = DeadlineWatchStore(tmp_path)
    agent = TriggerAgent(watch_store=store)
    watch = agent.register_deadline_watch(
        user_id="user_1",
        session_id="session_1",
        issue_type="academic.plural_major",
        deadline=date(2026, 7, 5),
    )

    events = agent.due_deadline_events(today=date(2026, 7, 5))
    stored = store.get(watch.watch_id)

    assert len(events) == 1
    assert stored is not None
    assert stored.status == "COMPLETED"


def test_escalation_agent_persists_case(tmp_path) -> None:
    store = EscalationStore(tmp_path)
    result = EscalationAgent(store=store).run(
        {
            "knowledge": {
                "answer": "needs review",
                "confidence": 0.4,
                "requires_human_review": True,
                "issue_types": ["academic.plural_major"],
            },
            "context": {"user_id": "user_1", "session_id": "session_1"},
        }
    )

    case = store.get(result["escalation_id"])
    assert case is not None
    assert case.reason == "human_review_required"
    assert case.review_package["issue_types"] == ["academic.plural_major"]

    acknowledged = store.acknowledge(result["escalation_id"])
    assert acknowledged.status == "ACKNOWLEDGED"
    assigned = store.assign(result["escalation_id"], "reviewer_1")
    assert assigned.status == "ACKNOWLEDGED"
    assert assigned.assignee == "reviewer_1"
    noted = store.add_note(
        result["escalation_id"],
        author="reviewer_1",
        text="Checking source policy.",
    )
    assert noted.notes[0]["author"] == "reviewer_1"
    assert noted.notes[0]["visibility"] == "internal"
    resolved = store.resolve(result["escalation_id"])
    assert resolved.status == "RESOLVED"


def test_conversation_store_persists_session_turns(tmp_path) -> None:
    store = ConversationStore(tmp_path)
    message = IncomingMessage(
        channel="api",
        user_id="user_1",
        session_id="session_1",
        text="hello",
    )
    store.append_message(message)
    store.append_assistant("session_1", "user_1", "answer")

    turns = store.list_by_session("session_1")
    assert [turn.role for turn in turns] == ["USER", "ASSISTANT"]


def test_coordinator_persists_plan_without_action_agent(tmp_path) -> None:
    settings = AppSettings(data_dir=tmp_path, enable_action_agent=False, openai_api_key=None)
    persona = PersonaWorker().build(
        IncomingMessage(
            channel="api",
            user_id="user_1",
            session_id="session_1",
            text="When is double major deadline?",
        )
    )
    message = IncomingMessage(
        channel="api",
        user_id="user_1",
        session_id="session_1",
        text="When is double major deadline?",
    )

    plan = CoordinatorAgent(settings).create_plan(message, persona=persona)
    stored = CoordinationPlanStore(tmp_path).get(plan.plan_id)

    assert stored is not None
    assert stored.intent_family == "deadline_question"
    assert "agent_hobit_action" in stored.skipped_agents
    assert "agent_hobit_knowledge" in stored.selected_agents
    assert [node["node_id"] for node in stored.graph_nodes] == [
        "knowledge_query",
        "escalation_prepare",
        "final_response",
    ]


def test_final_response_ignores_non_review_escalation_payload() -> None:
    result = FinalResponseAgent().run(
        {
            "channel": "api",
            "knowledge": {"answer": "Use the portal."},
            "escalation": {"requires_human_review": False, "reason": "skipped"},
        }
    )

    assert result["response"] == "Use the portal."
    assert result["delivery"]["escalation"]["requires_human_review"] is False


def test_action_agent_produces_action_plan_via_adapter() -> None:
    from hobit_ax_agentos.agents.action import ActionAgent

    agent = ActionAgent(adapter=FakeAdapter())
    result = agent.run({
        "knowledge": {
            "risk_class": "LOW",
            "state": {
                "issue_graph": [{"issue_type": "academic.plural_major"}],
                "parsed_intent": {"intent_mode": "checklist"},
                "evidence_packets": [],
            },
        }
    })

    assert result["action_plan"]["issue_type"] == "academic.plural_major"
    assert result["action_plan"]["form_name"] == "신청서"
    assert result["requires_human_approval"] is False


def test_action_agent_propagates_high_risk_approval() -> None:
    from hobit_ax_agentos.agents.action import ActionAgent

    agent = ActionAgent(adapter=FakeAdapter())
    result = agent.run({
        "knowledge": {
            "risk_class": "HIGH",
            "state": {},
        }
    })

    assert result["requires_human_approval"] is True

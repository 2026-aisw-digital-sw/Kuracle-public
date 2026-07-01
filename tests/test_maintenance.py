from __future__ import annotations

import json

from hobit_ax_agentos.models import (
    AgentRunRecord,
    AsyncJobRecord,
    CoordinationPlan,
    DeadlineWatch,
    EscalationCase,
    IncomingMessage,
)
from hobit_ax_agentos.services.maintenance import MaintenanceService
from hobit_ax_agentos.services.metrics import MetricsService
from hobit_ax_agentos.services.session_directory import SessionDirectoryService
from hobit_ax_agentos.services.session_state import SessionStateService
from hobit_ax_agentos.storage import (
    AsyncJobStore,
    ConversationStore,
    CoordinationPlanStore,
    DeadlineWatchStore,
    EscalationStore,
    OutboxStore,
    RunStore,
)


def test_maintenance_exports_session_records(tmp_path) -> None:
    AsyncJobStore(tmp_path).save(
        AsyncJobRecord(
            job_id="job_1",
            kind="query",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            status="COMPLETED",
            run_id="run_1",
        )
    )
    ConversationStore(tmp_path).append_message(
        IncomingMessage("api", "user_1", "hello", "session_1")
    )
    CoordinationPlanStore(tmp_path).save(
        CoordinationPlan(
            plan_id="plan_1",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            intent_family="regulation_question",
            selected_agents=["agent_hobit_knowledge"],
        )
    )
    RunStore(tmp_path).save(
        AgentRunRecord(
            run_id="run_1",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            state="COMPLETED",
        )
    )
    EscalationStore(tmp_path).save(
        EscalationCase(
            escalation_id="esc_1",
            session_id="session_1",
            user_id="user_1",
            reason="review",
        )
    )
    OutboxStore(tmp_path).append_response("session_1", "user_1", "api", "answer")

    export = MaintenanceService(tmp_path).export_session("session_1")

    assert export["summary"]["counts"]["turns"] == 1
    assert export["summary"]["counts"]["async_jobs"] == 1
    assert export["summary"]["recent"]["async_jobs"][0]["job_id"] == "job_1"
    assert export["records"]["async_jobs"][0]["job_id"] == "job_1"
    assert export["records"]["conversation_turns"][0]["text"] == "hello"
    assert export["records"]["coordination_plans"][0]["plan_id"] == "plan_1"
    assert export["records"]["agent_runs"][0]["run_id"] == "run_1"
    assert export["records"]["escalations"][0]["escalation_id"] == "esc_1"
    assert export["records"]["outbox"][0]["text"] == "answer"


def test_maintenance_writes_session_export_file(tmp_path) -> None:
    ConversationStore(tmp_path).append_message(
        IncomingMessage("api", "user_1", "hello", "session_1")
    )
    output = tmp_path / "exports" / "session_1.json"

    result = MaintenanceService(tmp_path).write_session_export("session_1", output)
    data = json.loads(output.read_text(encoding="utf-8"))

    assert result["path"] == str(output)
    assert result["counts"]["conversation_turns"] == 1
    assert data["session_id"] == "session_1"


def test_maintenance_storage_stats_counts_jsonl(tmp_path) -> None:
    AsyncJobStore(tmp_path).save(
        AsyncJobRecord(
            job_id="job_1",
            kind="query",
            session_id="session_1",
            user_id="user_1",
            channel="api",
        )
    )
    ConversationStore(tmp_path).append_message(
        IncomingMessage("api", "user_1", "hello", "session_1")
    )

    stats = MaintenanceService(tmp_path).storage_stats()

    assert stats["counts"]["conversation_turns"] == 1
    assert stats["counts"]["async_jobs"] == 1
    by_name = {item["name"]: item for item in stats["files"]}
    assert by_name["conversation_turns.jsonl"]["lines"] == 1
    assert by_name["async_jobs.jsonl"]["lines"] == 1


def test_session_timeline_combines_records_in_time_order(tmp_path) -> None:
    AsyncJobStore(tmp_path).save(
        AsyncJobRecord(
            job_id="job_1",
            kind="query",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            status="COMPLETED",
        )
    )
    ConversationStore(tmp_path).append_message(
        IncomingMessage("api", "user_1", "hello", "session_1")
    )
    CoordinationPlanStore(tmp_path).save(
        CoordinationPlan(
            plan_id="plan_1",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            intent_family="regulation_question",
            selected_agents=["agent_hobit_knowledge"],
        )
    )
    RunStore(tmp_path).save(
        AgentRunRecord(
            run_id="run_1",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            state="COMPLETED",
        )
    )
    OutboxStore(tmp_path).append_response("session_1", "user_1", "api", "answer")

    timeline = SessionStateService(tmp_path).timeline("session_1", limit=5)

    assert timeline["count"] == 5
    event_types = [event["event_type"] for event in timeline["events"]]
    assert "async_job.completed" in event_types
    assert "coordination.plan" in event_types
    assert "run.completed" in event_types
    assert "outbox.pending" in event_types
    assert any(event["record"].get("text") == "answer" for event in timeline["events"])


def test_session_directory_lists_sessions_with_open_items(tmp_path) -> None:
    AsyncJobStore(tmp_path).save(
        AsyncJobRecord(
            job_id="job_1",
            kind="query",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            status="RUNNING",
        )
    )
    AsyncJobStore(tmp_path).save(
        AsyncJobRecord(
            job_id="job_2",
            kind="query",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            status="FAILED",
        )
    )
    ConversationStore(tmp_path).append_message(
        IncomingMessage("api", "user_1", "hello", "session_1")
    )
    RunStore(tmp_path).save(
        AgentRunRecord(
            run_id="run_1",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            state="RUNNING",
        )
    )
    EscalationStore(tmp_path).save(
        EscalationCase(
            escalation_id="esc_1",
            session_id="session_1",
            user_id="user_1",
            reason="review",
        )
    )
    OutboxStore(tmp_path).append_response("session_2", "user_2", "api", "answer")

    directory = SessionDirectoryService(tmp_path).list_sessions()

    assert directory["count"] == 2
    by_session = {item["session_id"]: item for item in directory["sessions"]}
    assert by_session["session_1"]["users"] == ["user_1"]
    assert by_session["session_1"]["counts"]["turns"] == 1
    assert by_session["session_1"]["counts"]["async_jobs"] == 2
    assert by_session["session_1"]["counts"]["runs"] == 1
    assert by_session["session_1"]["open_items"]["active_async_jobs"] == 1
    assert by_session["session_1"]["open_items"]["failed_async_jobs"] == 1
    assert by_session["session_1"]["open_items"]["active_runs"] == 1
    assert by_session["session_1"]["open_items"]["open_escalations"] == 1
    assert by_session["session_2"]["open_items"]["pending_deliveries"] == 1


def test_metrics_summary_counts_operational_backlog(tmp_path) -> None:
    AsyncJobStore(tmp_path).save(
        AsyncJobRecord(
            job_id="job_1",
            kind="query",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            status="RUNNING",
        )
    )
    RunStore(tmp_path).save(
        AgentRunRecord(
            run_id="run_1",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            state="RUNNING",
        )
    )
    RunStore(tmp_path).save(
        AgentRunRecord(
            run_id="run_2",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            state="FAILED",
        )
    )
    OutboxStore(tmp_path).append_response("session_1", "user_1", "api", "pending")
    failed_delivery = OutboxStore(tmp_path).append_response("session_1", "user_1", "api", "failed")
    OutboxStore(tmp_path).mark_failed(failed_delivery.delivery_id, "transport error")
    EscalationStore(tmp_path).save(
        EscalationCase(
            escalation_id="esc_1",
            session_id="session_1",
            user_id="user_1",
            reason="review",
            status="ACKNOWLEDGED",
        )
    )
    DeadlineWatchStore(tmp_path).save(
        DeadlineWatch(
            watch_id="watch_1",
            session_id="session_1",
            user_id="user_1",
            issue_type="academic.plural_major",
            deadline="2026-07-05",
        )
    )

    metrics = MetricsService(tmp_path).summary()

    assert metrics["totals"]["agent_runs"] == 2
    assert metrics["totals"]["async_jobs"] == 1
    assert metrics["by_status"]["async_jobs"] == {"RUNNING": 1}
    assert metrics["backlog"]["active_async_jobs"] == 1
    assert metrics["by_status"]["agent_runs"] == {"FAILED": 1, "RUNNING": 1}
    assert metrics["by_status"]["outbox"] == {"FAILED": 1, "PENDING": 1}
    assert metrics["backlog"]["running_runs"] == 1
    assert metrics["backlog"]["failed_runs"] == 1
    assert metrics["backlog"]["pending_deliveries"] == 1
    assert metrics["backlog"]["failed_deliveries"] == 1
    assert metrics["backlog"]["open_escalations"] == 1
    assert metrics["backlog"]["active_deadline_watches"] == 1

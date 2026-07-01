from __future__ import annotations

from datetime import date, datetime, timedelta

from hobit_ax_agentos.models import (
    AgentRunRecord,
    AsyncJobRecord,
    DeadlineWatch,
    EscalationCase,
)
from hobit_ax_agentos.services.alerts import AlertsService
from hobit_ax_agentos.storage import (
    AsyncJobStore,
    DeadlineWatchStore,
    EscalationStore,
    OutboxStore,
    RunStore,
)


def test_alerts_service_reports_operational_backlog(tmp_path) -> None:
    job = AsyncJobStore(tmp_path).save(
        AsyncJobRecord(
            job_id="job_1",
            kind="query",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            status="RUNNING",
        )
    )
    failed_job = AsyncJobStore(tmp_path).save(
        AsyncJobRecord(
            job_id="job_2",
            kind="query",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            status="FAILED",
            error="adapter exploded",
        )
    )
    run = RunStore(tmp_path).save(
        AgentRunRecord(
            run_id="run_1",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            state="RUNNING",
        )
    )
    OutboxStore(tmp_path).append_response("session_1", "user_1", "api", "pending")
    EscalationStore(tmp_path).save(
        EscalationCase(
            escalation_id="esc_1",
            session_id="session_1",
            user_id="user_1",
            reason="review",
        )
    )
    DeadlineWatchStore(tmp_path).save(
        DeadlineWatch(
            watch_id="watch_1",
            session_id="session_1",
            user_id="user_1",
            issue_type="academic.plural_major",
            deadline="2026-07-02",
        )
    )
    now = datetime.fromisoformat(run.updated_at) + timedelta(minutes=31)
    assert datetime.fromisoformat(job.updated_at) <= now
    assert datetime.fromisoformat(failed_job.updated_at) <= now

    alerts = AlertsService(tmp_path).alerts(
        now=now,
        today=date(2026, 7, 1),
        running_minutes=10,
        job_minutes=10,
        delivery_minutes=10,
        escalation_minutes=30,
        deadline_days=3,
    )

    by_type = {item["alert_type"]: item for item in alerts["items"]}
    assert alerts["count"] == 6
    assert by_type["job.stale"]["record_id"] == "job_1"
    assert by_type["job.failed"]["record_id"] == "job_2"
    assert "adapter exploded" in by_type["job.failed"]["message"]
    assert by_type["run.stale"]["record_id"] == "run_1"
    assert by_type["run.stale"]["age_minutes"] == 31
    assert by_type["outbox.pending"]["severity"] == "MEDIUM"
    assert by_type["escalation.open"]["severity"] == "HIGH"
    assert by_type["deadline.due"]["record"]["days_left"] == 1


def test_alerts_service_ignores_fresh_items(tmp_path) -> None:
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
    run = RunStore(tmp_path).save(
        AgentRunRecord(
            run_id="run_1",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            state="RUNNING",
        )
    )
    now = datetime.fromisoformat(run.updated_at) + timedelta(minutes=2)

    alerts = AlertsService(tmp_path).alerts(now=now, running_minutes=10, job_minutes=10)

    assert alerts == {"count": 0, "items": []}

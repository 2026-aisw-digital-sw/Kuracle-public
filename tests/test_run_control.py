from __future__ import annotations

import pytest

from hobit_ax_agentos.models import AgentRunRecord, EscalationCase
from hobit_ax_agentos.services.run_control import RunControlService
from hobit_ax_agentos.storage import EscalationStore, OutboxStore, RunStore


def test_run_control_cancels_run_and_closes_related_records(tmp_path) -> None:
    RunStore(tmp_path).save(
        AgentRunRecord(
            run_id="run_1",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            state="RUNNING",
            trace_id="trace_1",
            run_summary={"state": "RUNNING"},
        )
    )
    delivery = OutboxStore(tmp_path).append_response(
        session_id="session_1",
        user_id="user_1",
        channel="api",
        text="pending answer",
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

    result = RunControlService(tmp_path).cancel("run_1", reason="duplicate request")

    assert result is not None
    assert result["run"]["state"] == "CANCELLED"
    assert result["run"]["run_summary"]["previous_state"] == "RUNNING"
    assert result["run"]["run_summary"]["cancel_reason"] == "duplicate request"
    assert result["failed_deliveries"][0]["delivery_id"] == delivery.delivery_id
    assert result["failed_deliveries"][0]["status"] == "FAILED"
    assert result["failed_deliveries"][0]["error"] == "run_cancelled:run_1"
    assert result["resolved_escalations"][0]["status"] == "RESOLVED"
    assert result["resolved_escalations"][0]["review_package"]["cancelled_by_run_id"] == "run_1"


def test_run_control_rejects_terminal_run(tmp_path) -> None:
    RunStore(tmp_path).save(
        AgentRunRecord(
            run_id="run_done",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            state="COMPLETED",
        )
    )

    with pytest.raises(ValueError, match="not cancellable"):
        RunControlService(tmp_path).cancel("run_done")


def test_run_control_returns_none_for_missing_run(tmp_path) -> None:
    assert RunControlService(tmp_path).cancel("missing") is None

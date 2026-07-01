from __future__ import annotations

import json

from hobit_ax_agentos.models import (
    AgentRunRecord,
    AsyncJobRecord,
    CoordinationPlan,
    OutboundDelivery,
)
from hobit_ax_agentos.services.storage_audit import StorageAuditService
from hobit_ax_agentos.storage import (
    CoordinationPlanStore,
    IdempotencyStore,
    OutboxStore,
    RunStore,
)


def test_storage_audit_reports_ok_for_valid_records(tmp_path) -> None:
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
            coordination_plan_id="plan_1",
        )
    )
    OutboxStore(tmp_path).append(
        OutboundDelivery(
            delivery_id="delivery_1",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            text="answer",
            run_id="run_1",
        )
    )
    (tmp_path / "async_jobs.jsonl").write_text(
        json.dumps(
            AsyncJobRecord(
                job_id="job_1",
                kind="query",
                session_id="session_1",
                user_id="user_1",
                channel="api",
                status="COMPLETED",
                run_id="run_1",
            ).to_dict(),
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    IdempotencyStore(tmp_path).save(
        key="request_1",
        run_id="run_1",
        session_id="session_1",
        user_id="user_1",
        channel="api",
    )

    audit = StorageAuditService(tmp_path).audit()

    assert audit["status"] == "ok"
    assert audit["issues"] == []
    assert audit["counts"]["agent_runs"] == 1
    assert audit["counts"]["async_jobs"] == 1
    assert audit["counts"]["outbox"] == 1
    assert audit["counts"]["idempotency_keys"] == 1


def test_storage_audit_reports_invalid_json_and_missing_references(tmp_path) -> None:
    (tmp_path / "conversation_turns.jsonl").write_text("{bad json\n", encoding="utf-8")
    (tmp_path / "agent_runs.jsonl").write_text(
        json.dumps(
            {
                "run_id": "run_1",
                "session_id": "session_1",
                "user_id": "user_1",
                "channel": "api",
                "state": "COMPLETED",
                "coordination_plan_id": "missing_plan",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    OutboxStore(tmp_path).append(
        OutboundDelivery(
            delivery_id="delivery_1",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            text="answer",
            run_id="missing_run",
        )
    )
    (tmp_path / "async_jobs.jsonl").write_text(
        json.dumps(
            AsyncJobRecord(
                job_id="job_1",
                kind="query",
                session_id="session_1",
                user_id="user_1",
                channel="api",
                run_id="missing_run",
            ).to_dict(),
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    IdempotencyStore(tmp_path).save(
        key="request_1",
        run_id="missing_run",
        session_id="session_1",
        user_id="user_1",
        channel="api",
    )

    audit = StorageAuditService(tmp_path).audit()

    assert audit["status"] == "degraded"
    issue_types = {issue["issue_type"] for issue in audit["issues"]}
    assert "invalid_json" in issue_types
    assert "missing_coordination_plan" in issue_types
    assert "missing_run" in issue_types

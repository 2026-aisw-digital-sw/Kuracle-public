from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from hobit_ax_agentos.agents.persona import PersonaWorker
from hobit_ax_agentos.api import main
from hobit_ax_agentos.config import AppSettings
from hobit_ax_agentos.models import (
    AgentRunRecord,
    CoordinationPlan,
    DeadlineWatch,
    EscalationCase,
    IncomingMessage,
    ServiceResult,
)
from hobit_ax_agentos.storage import (
    AsyncJobStore,
    CoordinationPlanStore,
    DeadlineWatchStore,
    EscalationStore,
    OutboxStore,
    PersonaStore,
    RunStore,
)


def test_gateway_classifies_normalized_message(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    client = TestClient(main.app)

    response = client.post(
        "/gateway/api",
        json={
            "query": "When is double major deadline?",
            "user_id": "user_1",
            "session_id": "session_1",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["message"]["text"] == "When is double major deadline?"
    assert data["classification"]["intent_family"] == "deadline_question"


def test_web_ui_assets_are_served_without_api_token(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "settings",
        AppSettings(data_dir=tmp_path, api_token="secret-token"),
    )
    client = TestClient(main.app)

    html = client.get("/app")
    portal = client.get("/portal")
    css = client.get("/ui/app.css")
    js = client.get("/ui/app.js")
    portal_css = client.get("/ui/portal.css")
    portal_js = client.get("/ui/portal.js")

    assert html.status_code == 200
    assert "Hobit AX AgentOS" in html.text
    assert portal.status_code == 200
    assert "Hobit AX Portal" in portal.text
    assert css.status_code == 200
    assert "text/css" in css.headers["content-type"]
    assert js.status_code == 200
    assert "application/javascript" in js.headers["content-type"]
    assert portal_css.status_code == 200
    assert portal_js.status_code == 200
    assert client.get("/config").status_code == 401


def test_gateway_dry_run_returns_graph(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    client = TestClient(main.app)

    response = client.post(
        "/gateway/web/dry-run",
        json={
            "message": "When is double major deadline?",
            "member_id": "member_1",
            "session_id": "session_1",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["message"]["channel"] == "web"
    assert data["message"]["user_id"] == "member_1"
    assert data["graph"]["nodes"][0]["node_id"] == "knowledge_query"
    assert not any(node["node_id"] == "action_prepare" for node in data["graph"]["nodes"])


def test_gateway_query_runs_normalized_message(tmp_path, monkeypatch) -> None:
    seen: dict = {}

    class FakeRunner:
        def __init__(self, settings) -> None:
            self.settings = settings

        def run_message(self, message, timeout_seconds: float = 120.0) -> ServiceResult:
            seen["message"] = message
            seen["timeout_seconds"] = timeout_seconds
            return ServiceResult(
                run_id="run_1",
                trace_id="trace_1",
                final={"response": "ok"},
                run_summary={"state": "COMPLETED"},
                worker_results=[],
            )

    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    monkeypatch.setattr(main, "ServiceRunner", FakeRunner)
    client = TestClient(main.app)

    response = client.post(
        "/gateway/kakao/query",
        json={
            "userRequest": {
                "utterance": "double major",
                "user": {"id": "kakao_user_1"},
            },
            "idempotency_key": "kakao_request_1",
            "timeout_seconds": 3.5,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["result"]["run_id"] == "run_1"
    assert seen["message"].channel == "kakaotalk"
    assert seen["message"].user_id == "kakao_user_1"
    assert seen["message"].metadata["idempotency_key"] == "kakao_request_1"
    assert seen["timeout_seconds"] == 3.5


def test_query_submit_records_async_job_result(tmp_path, monkeypatch) -> None:
    seen: dict = {}

    class FakeRunner:
        def __init__(self, settings) -> None:
            self.settings = settings

        def run_message(self, message, timeout_seconds: float = 120.0) -> ServiceResult:
            seen["message"] = message
            seen["timeout_seconds"] = timeout_seconds
            return ServiceResult(
                run_id="run_async_1",
                trace_id="trace_async_1",
                final={"response": "async ok"},
                run_summary={"state": "COMPLETED"},
                worker_results=[],
            )

    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    monkeypatch.setattr(main, "ServiceRunner", FakeRunner)
    client = TestClient(main.app)

    response = client.post(
        "/query/submit?timeout_seconds=4.5",
        json={
            "channel": "api",
            "user_id": "user_1",
            "session_id": "session_1",
            "text": "double major",
        },
    )

    assert response.status_code == 200
    job_id = response.json()["job"]["job_id"]
    job = client.get(f"/jobs/{job_id}").json()
    completed_jobs = client.get("/jobs?status=completed").json()

    assert response.json()["job"]["status"] == "QUEUED"
    assert job["status"] == "COMPLETED"
    assert job["run_id"] == "run_async_1"
    assert job["result"]["final"]["response"] == "async ok"
    assert completed_jobs[0]["job_id"] == job_id
    assert seen["message"].text == "double major"
    assert seen["timeout_seconds"] == 4.5
    assert AsyncJobStore(tmp_path).get(job_id).status == "COMPLETED"


def test_gateway_submit_records_normalized_async_job(tmp_path, monkeypatch) -> None:
    seen: dict = {}

    class FakeRunner:
        def __init__(self, settings) -> None:
            self.settings = settings

        def run_message(self, message, timeout_seconds: float = 120.0) -> ServiceResult:
            seen["message"] = message
            return ServiceResult(
                run_id="run_gateway_async",
                trace_id="trace_gateway_async",
                final={"response": "ok"},
                run_summary={"state": "COMPLETED"},
                worker_results=[],
            )

    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    monkeypatch.setattr(main, "ServiceRunner", FakeRunner)
    client = TestClient(main.app)

    response = client.post(
        "/gateway/web/submit",
        json={
            "message": "When is double major deadline?",
            "member_id": "member_1",
            "session_id": "session_1",
            "timeout_seconds": 1.5,
        },
    )

    assert response.status_code == 200
    data = response.json()
    job = client.get(data["status_url"]).json()

    assert data["message"]["channel"] == "web"
    assert data["classification"]["intent_family"] == "deadline_question"
    assert job["status"] == "COMPLETED"
    assert job["message"]["user_id"] == "member_1"
    assert job["run_id"] == "run_gateway_async"
    assert seen["message"].channel == "web"


def test_query_submit_records_failed_async_job(tmp_path, monkeypatch) -> None:
    class FakeRunner:
        def __init__(self, settings) -> None:
            self.settings = settings

        def run_message(self, message, timeout_seconds: float = 120.0) -> ServiceResult:
            raise RuntimeError("async exploded")

    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    monkeypatch.setattr(main, "ServiceRunner", FakeRunner)
    client = TestClient(main.app)

    response = client.post(
        "/query/submit",
        json={
            "channel": "api",
            "user_id": "user_1",
            "session_id": "session_1",
            "text": "broken",
        },
    )

    job = client.get(response.json()["status_url"]).json()

    assert job["status"] == "FAILED"
    assert job["error_type"] == "RuntimeError"
    assert job["error"] == "async exploded"


def test_run_queued_async_job_endpoint(tmp_path, monkeypatch) -> None:
    class FakeRunner:
        def __init__(self, settings) -> None:
            self.settings = settings

        def run_message(self, message, timeout_seconds: float = 120.0) -> ServiceResult:
            return ServiceResult(
                run_id="run_manual_1",
                trace_id="trace_manual_1",
                final={"response": message.text},
                run_summary={"state": "COMPLETED"},
                worker_results=[],
            )

    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    monkeypatch.setattr(main, "ServiceRunner", FakeRunner)
    job = AsyncJobStore(tmp_path).create(
        kind="query",
        message=IncomingMessage("api", "user_1", "manual job", "session_1"),
    )
    client = TestClient(main.app)

    response = client.post(f"/jobs/{job.job_id}/run")

    assert response.status_code == 200
    data = response.json()
    assert data["skipped"] is False
    assert data["job"]["status"] == "COMPLETED"
    assert data["job"]["run_id"] == "run_manual_1"


def test_run_queued_async_jobs_endpoint(tmp_path, monkeypatch) -> None:
    class FakeRunner:
        def __init__(self, settings) -> None:
            self.settings = settings

        def run_message(self, message, timeout_seconds: float = 120.0) -> ServiceResult:
            return ServiceResult(
                run_id=f"run_{message.text}",
                trace_id=f"trace_{message.text}",
                final={"response": message.text},
                run_summary={"state": "COMPLETED"},
                worker_results=[],
            )

    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    monkeypatch.setattr(main, "ServiceRunner", FakeRunner)
    AsyncJobStore(tmp_path).create(
        kind="query",
        message=IncomingMessage("api", "user_1", "first", "session_1"),
    )
    AsyncJobStore(tmp_path).create(
        kind="query",
        message=IncomingMessage("api", "user_1", "second", "session_1"),
    )
    client = TestClient(main.app)

    response = client.post("/jobs/run-queued", json={"limit": 10})

    assert response.status_code == 200
    assert [item["job"]["status"] for item in response.json()] == ["COMPLETED", "COMPLETED"]
    assert [job.status for job in AsyncJobStore(tmp_path).list_all()] == [
        "COMPLETED",
        "COMPLETED",
    ]


def test_requeue_stale_async_jobs_endpoint(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    job = AsyncJobStore(tmp_path).create(
        kind="query",
        message=IncomingMessage("api", "user_1", "stale", "session_1"),
    )
    job.status = "RUNNING"
    job.updated_at = (datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat()
    AsyncJobStore(tmp_path).save(job, touch=False)
    client = TestClient(main.app)

    response = client.post(
        "/jobs/requeue-stale",
        json={"older_than_minutes": 30, "limit": 10},
    )

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert AsyncJobStore(tmp_path).get(job.job_id).status == "QUEUED"


def test_failed_async_job_can_be_retried(tmp_path, monkeypatch) -> None:
    seen: dict = {}

    class FakeRunner:
        def __init__(self, settings) -> None:
            self.settings = settings

        def run_message(self, message, timeout_seconds: float = 120.0) -> ServiceResult:
            seen["message"] = message
            seen["timeout_seconds"] = timeout_seconds
            return ServiceResult(
                run_id="run_retry_1",
                trace_id="trace_retry_1",
                final={"response": "retry ok"},
                run_summary={"state": "COMPLETED"},
                worker_results=[],
            )

    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    monkeypatch.setattr(main, "ServiceRunner", FakeRunner)
    source = AsyncJobStore(tmp_path).create(
        kind="query",
        message=IncomingMessage("api", "user_1", "retry me", "session_1"),
        metadata={"timeout_seconds": 7.0},
    )
    AsyncJobStore(tmp_path).mark_failed(source.job_id, RuntimeError("first failed"))
    client = TestClient(main.app)

    response = client.post(f"/jobs/{source.job_id}/retry")

    assert response.status_code == 200
    retry_job = client.get(response.json()["status_url"]).json()
    assert retry_job["status"] == "COMPLETED"
    assert retry_job["run_id"] == "run_retry_1"
    assert retry_job["metadata"]["retry_of_job_id"] == source.job_id
    assert retry_job["metadata"]["retry_count"] == 1
    assert seen["message"].text == "retry me"
    assert seen["timeout_seconds"] == 7.0


def test_async_job_cancel_endpoint(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    job = AsyncJobStore(tmp_path).create(
        kind="query",
        message=IncomingMessage("api", "user_1", "cancel me", "session_1"),
    )
    client = TestClient(main.app)

    response = client.post(f"/jobs/{job.job_id}/cancel", json={"reason": "duplicate"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CANCELLED"
    assert data["error_type"] == "Cancelled"
    assert data["metadata"]["cancel_reason"] == "duplicate"


def test_async_job_retry_and_cancel_conflicts(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    store = AsyncJobStore(tmp_path)
    completed = store.create(
        kind="query",
        message=IncomingMessage("api", "user_1", "done", "session_1"),
    )
    completed.status = "COMPLETED"
    store.save(completed)
    running = store.create(
        kind="query",
        message=IncomingMessage("api", "user_1", "running", "session_1"),
    )
    running.status = "RUNNING"
    store.save(running)
    client = TestClient(main.app)

    retry_response = client.post(f"/jobs/{completed.job_id}/retry")
    cancel_response = client.post(f"/jobs/{running.job_id}/cancel")

    assert retry_response.status_code == 409
    assert "not retryable" in retry_response.json()["detail"]
    assert cancel_response.status_code == 409
    assert "not cancellable" in cancel_response.json()["detail"]


def test_doctor_endpoint_returns_report(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "settings",
        AppSettings(
            agentos_repo_path=tmp_path / "missing-agentos",
            hobit_ax_repo_path=tmp_path / "missing-hobit",
            data_dir=tmp_path / "data",
        ),
    )
    client = TestClient(main.app)

    response = client.get("/doctor")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


def test_integration_probe_endpoint(tmp_path, monkeypatch) -> None:
    class FakeProbeService:
        def __init__(self, settings) -> None:
            self.settings = settings

        def report(self, rag_query: str = "복수전공 신청 기간 알려줘") -> dict:
            return {
                "status": "ok",
                "probes": [{"name": "fake", "ok": True, "query": rag_query}],
            }

    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    monkeypatch.setattr(main, "IntegrationProbeService", FakeProbeService)
    client = TestClient(main.app)

    response = client.get("/integration/probe?rag_query=test-query")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["probes"][0]["query"] == "test-query"


def test_e2e_smoke_endpoint(tmp_path, monkeypatch) -> None:
    class FakeSmokeService:
        def __init__(self, settings, runner_factory=None) -> None:
            self.settings = settings
            self.runner_factory = runner_factory

        def run(self, **kwargs) -> dict:
            return {
                "status": "ok",
                "message": kwargs,
                "steps": [{"name": "fake", "ok": True}],
            }

    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    monkeypatch.setattr(main, "E2ESmokeService", FakeSmokeService)
    client = TestClient(main.app)

    response = client.post(
        "/smoke/e2e",
        json={"query": "hello", "channel": "web", "render_channel": "kakao"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["message"]["query"] == "hello"
    assert response.json()["message"]["channel"] == "web"
    assert response.json()["message"]["render_channel"] == "kakao"


def test_api_token_protects_non_public_endpoints(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path, api_token="token_1"))
    client = TestClient(main.app)

    health = client.get("/health")
    ready = client.get("/ready")
    unauthorized = client.get("/doctor")
    authorized = client.get("/doctor", headers={"Authorization": "Bearer token_1"})

    assert health.status_code == 200
    assert ready.status_code == 200
    assert unauthorized.status_code == 401
    assert unauthorized.json()["detail"] == "invalid or missing api token"
    assert authorized.status_code == 200


def test_api_token_accepts_x_api_token_header(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path, api_token="token_1"))
    client = TestClient(main.app)

    response = client.get("/config", headers={"x-api-token": "token_1"})

    assert response.status_code == 200
    assert response.json()["kernel"]["api_token_configured"] is True


def test_rate_limit_protects_non_public_endpoints(tmp_path, monkeypatch) -> None:
    main._rate_limit_buckets.clear()
    monkeypatch.setattr(
        main,
        "settings",
        AppSettings(data_dir=tmp_path, rate_limit_per_minute=1),
    )
    client = TestClient(main.app)

    first = client.get("/doctor")
    second = client.get("/doctor")
    health = client.get("/health")

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["detail"] == "rate limit exceeded"
    assert second.headers["Retry-After"] == "60"
    assert health.status_code == 200


def test_rate_limit_uses_token_bucket_when_authenticated(tmp_path, monkeypatch) -> None:
    main._rate_limit_buckets.clear()
    monkeypatch.setattr(
        main,
        "settings",
        AppSettings(data_dir=tmp_path, api_token="token_1", rate_limit_per_minute=1),
    )
    client = TestClient(main.app)

    first = client.get("/doctor", headers={"Authorization": "Bearer token_1"})
    second = client.get("/doctor", headers={"Authorization": "Bearer token_1"})
    other_token = client.get("/doctor", headers={"Authorization": "Bearer wrong"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert other_token.status_code == 401


def test_config_endpoint_returns_sanitized_snapshot(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "settings",
        AppSettings(data_dir=tmp_path, api_token="secret-token"),
    )
    client = TestClient(main.app)

    response = client.get("/config", headers={"Authorization": "Bearer secret-token"})

    assert response.status_code == 200
    data = response.json()
    assert data["kernel"]["api_token_configured"] is True
    assert "secret-token" not in str(data)
    assert data["runtime"]["action_agent_mode"] == "disabled_until_contract_studio_bridge"


def test_ready_endpoint_returns_readiness(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path / "data"))
    client = TestClient(main.app)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_agents_endpoint_returns_capability_manifest(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    client = TestClient(main.app)

    manifest = client.get("/agents").json()
    enabled = client.get("/agents?include_disabled=false").json()

    by_agent = {item["agent_id"]: item for item in manifest}
    assert by_agent["agent_hobit_action"]["enabled"] is False
    assert by_agent["agent_hobit_action"]["disabled_reason"] == (
        "deferred_until_contract_studio_bridge"
    )
    assert by_agent["agent_hobit_knowledge"]["output_schema"]["required"]
    assert [item["agent_id"] for item in enabled] == [
        "agent_hobit_knowledge",
        "agent_hobit_escalation",
        "agent_hobit_final",
    ]


def test_operational_state_endpoints(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
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
    EscalationStore(tmp_path).save(
        EscalationCase(
            escalation_id="esc_1",
            session_id="session_1",
            user_id="user_1",
            reason="human_review_required",
            run_id="run_1",
            trace_id="trace_1",
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
        )
    )
    delivery = OutboxStore(tmp_path).append_response(
        session_id="session_1",
        user_id="user_1",
        channel="api",
        text="answer",
        run_id="run_1",
        trace_id="trace_1",
    )
    DeadlineWatchStore(tmp_path).save(
        DeadlineWatch(
            watch_id="watch_1",
            user_id="user_1",
            session_id="session_1",
            issue_type="academic.plural_major",
            deadline="2026-07-05",
        )
    )
    PersonaStore(tmp_path).append(
        PersonaWorker().build(
            IncomingMessage(
                channel="api",
                user_id="user_1",
                session_id="session_1",
                text="double major",
            )
        )
    )
    client = TestClient(main.app)

    summary = client.get("/sessions/session_1/summary").json()
    sessions = client.get("/sessions").json()
    timeline = client.get("/sessions/session_1/timeline").json()
    export = client.get("/sessions/session_1/export").json()
    storage_stats = client.get("/maintenance/storage").json()
    storage_audit = client.get("/maintenance/audit").json()
    prune = client.post(
        "/maintenance/prune",
        json={"older_than_days": 365, "dry_run": True},
    ).json()
    metrics = client.get("/metrics/summary").json()
    alerts = client.get(
        "/alerts?running_minutes=0&delivery_minutes=0&escalation_minutes=0&deadline_days=10"
    ).json()
    plans = client.get("/sessions/session_1/plans").json()
    runs = client.get("/sessions/session_1/runs").json()
    run = client.get("/runs/run_1").json()
    trace = client.get("/runs/run_1/trace").json()
    outbox = client.get("/sessions/session_1/outbox").json()
    pending_outbox = client.get("/outbox?status=pending").json()
    rendered_delivery = client.get(f"/outbox/{delivery.delivery_id}/render?channel=kakao").json()
    sent = client.post(f"/outbox/{delivery.delivery_id}/sent").json()
    failed = client.post(
        f"/outbox/{delivery.delivery_id}/failed",
        json={"error": "transport error"},
    ).json()
    dispatch_skip = client.post(f"/outbox/{delivery.delivery_id}/dispatch").json()
    delivery_for_dispatch = OutboxStore(tmp_path).append_response(
        session_id="session_1",
        user_id="user_1",
        channel="api",
        text="dispatch me",
    )
    dispatch_one = client.post(f"/outbox/{delivery_for_dispatch.delivery_id}/dispatch").json()
    delivery_for_bulk = OutboxStore(tmp_path).append_response(
        session_id="session_1",
        user_id="user_1",
        channel="api",
        text="bulk dispatch me",
    )
    dispatch_bulk = client.post("/outbox/dispatch", json={"limit": 10}).json()
    escalations = client.get("/escalations").json()
    acknowledged = client.post("/escalations/esc_1/acknowledge").json()
    assigned = client.post("/escalations/esc_1/assign", json={"assignee": "reviewer_1"}).json()
    noted = client.post(
        "/escalations/esc_1/notes",
        json={
            "author": "reviewer_1",
            "text": "Checking policy.",
            "visibility": "internal",
        },
    ).json()
    resolved = client.post("/escalations/esc_1/resolve").json()
    resolved_list = client.get("/escalations?status=resolved").json()

    assert summary["counts"]["plans"] == 1
    assert sessions["count"] == 1
    assert sessions["sessions"][0]["session_id"] == "session_1"
    assert sessions["sessions"][0]["counts"]["runs"] == 1
    assert timeline["count"] == 6
    assert "coordination.plan" in [event["event_type"] for event in timeline["events"]]
    assert "run.completed" in [event["event_type"] for event in timeline["events"]]
    assert "outbox.pending" in [event["event_type"] for event in timeline["events"]]
    assert summary["counts"]["runs"] == 1
    assert export["records"]["agent_runs"][0]["run_id"] == "run_1"
    assert storage_stats["counts"]["agent_runs"] == 1
    assert storage_audit["status"] == "ok"
    assert storage_audit["counts"]["agent_runs"] == 1
    assert prune["dry_run"] is True
    assert "files" in prune
    assert metrics["totals"]["agent_runs"] == 1
    assert metrics["by_status"]["agent_runs"] == {"COMPLETED": 1}
    assert metrics["backlog"]["pending_deliveries"] == 1
    assert metrics["backlog"]["open_escalations"] == 1
    assert metrics["backlog"]["active_deadline_watches"] == 1
    assert alerts["count"] >= 3
    assert {"outbox.pending", "escalation.open", "deadline.due"}.issubset(
        {item["alert_type"] for item in alerts["items"]}
    )
    assert summary["latest_persona"]["top_issue_types"] == ["academic.plural_major"]
    assert summary["open_items"]["pending_deliveries"][0]["delivery_id"] == delivery.delivery_id
    assert summary["open_items"]["escalations"][0]["escalation_id"] == "esc_1"
    assert plans[0]["plan_id"] == "plan_1"
    assert runs[0]["run_id"] == "run_1"
    assert run["trace_id"] == "trace_1"
    assert trace["run"]["run_id"] == "run_1"
    assert trace["coordination_plan"]["plan_id"] == "plan_1"
    assert trace["related"]["outbox"][0]["delivery_id"] == delivery.delivery_id
    assert trace["related"]["escalations"][0]["escalation_id"] == "esc_1"
    assert outbox[0]["delivery_id"] == delivery.delivery_id
    assert pending_outbox[0]["status"] == "PENDING"
    assert rendered_delivery["channel"] == "kakao"
    assert rendered_delivery["payload"]["version"] == "2.0"
    assert rendered_delivery["payload"]["template"]["outputs"][0]["simpleText"]["text"] == "answer"
    assert sent["status"] == "SENT"
    assert failed["status"] == "FAILED"
    assert failed["error"] == "transport error"
    assert dispatch_skip["skipped"] is True
    assert dispatch_one["delivery"]["status"] == "SENT"
    assert any(
        item["delivery"]["delivery_id"] == delivery_for_bulk.delivery_id
        for item in dispatch_bulk
    )
    assert escalations[0]["escalation_id"] == "esc_1"
    assert acknowledged["status"] == "ACKNOWLEDGED"
    assert assigned["assignee"] == "reviewer_1"
    assert assigned["status"] == "ACKNOWLEDGED"
    assert noted["notes"][0]["text"] == "Checking policy."
    assert resolved["status"] == "RESOLVED"
    assert resolved_list[0]["status"] == "RESOLVED"


def test_missing_escalation_returns_404(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    client = TestClient(main.app)

    response = client.post("/escalations/missing/resolve")

    assert response.status_code == 404
    assert response.json()["detail"] == "escalation not found"


def test_missing_escalation_assign_returns_404(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    client = TestClient(main.app)

    response = client.post("/escalations/missing/assign", json={"assignee": "reviewer_1"})

    assert response.status_code == 404
    assert response.json()["detail"] == "escalation not found"


def test_missing_escalation_note_returns_404(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    client = TestClient(main.app)

    response = client.post("/escalations/missing/notes", json={"text": "note"})

    assert response.status_code == 404
    assert response.json()["detail"] == "escalation not found"


def test_global_runs_endpoint_filters_by_state(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    store = RunStore(tmp_path)
    store.save(
        AgentRunRecord(
            run_id="run_done",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            state="COMPLETED",
        )
    )
    store.save(
        AgentRunRecord(
            run_id="run_failed",
            session_id="session_2",
            user_id="user_2",
            channel="api",
            state="FAILED",
        )
    )
    client = TestClient(main.app)

    all_runs = client.get("/runs").json()
    failed_runs = client.get("/runs?state=failed").json()
    session_failed_runs = client.get("/sessions/session_2/runs?state=failed").json()

    assert [run["run_id"] for run in all_runs] == ["run_done", "run_failed"]
    assert [run["run_id"] for run in failed_runs] == ["run_failed"]
    assert [run["run_id"] for run in session_failed_runs] == ["run_failed"]


def test_missing_run_returns_404(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    client = TestClient(main.app)

    response = client.get("/runs/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "run not found"


def test_missing_job_returns_404(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    client = TestClient(main.app)

    response = client.get("/jobs/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "job not found"


def test_missing_run_trace_returns_404(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    client = TestClient(main.app)

    response = client.get("/runs/missing/trace")

    assert response.status_code == 404
    assert response.json()["detail"] == "run not found"


def test_missing_run_retry_returns_404(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    client = TestClient(main.app)

    response = client.post("/runs/missing/retry")

    assert response.status_code == 404
    assert response.json()["detail"] == "run not found"


def test_completed_run_retry_returns_409(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    RunStore(tmp_path).save(
        AgentRunRecord(
            run_id="run_done",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            state="COMPLETED",
        )
    )
    client = TestClient(main.app)

    response = client.post("/runs/run_done/retry")

    assert response.status_code == 409
    assert "not retryable" in response.json()["detail"]


def test_run_cancel_endpoint(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    RunStore(tmp_path).save(
        AgentRunRecord(
            run_id="run_running",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            state="RUNNING",
        )
    )
    client = TestClient(main.app)

    response = client.post("/runs/run_running/cancel", json={"reason": "operator stop"})

    assert response.status_code == 200
    assert response.json()["run"]["state"] == "CANCELLED"
    assert response.json()["run"]["run_summary"]["cancel_reason"] == "operator stop"


def test_missing_run_cancel_returns_404(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    client = TestClient(main.app)

    response = client.post("/runs/missing/cancel")

    assert response.status_code == 404
    assert response.json()["detail"] == "run not found"


def test_completed_run_cancel_returns_409(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    RunStore(tmp_path).save(
        AgentRunRecord(
            run_id="run_done",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            state="COMPLETED",
        )
    )
    client = TestClient(main.app)

    response = client.post("/runs/run_done/cancel")

    assert response.status_code == 409
    assert "not cancellable" in response.json()["detail"]


def test_missing_delivery_returns_404(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    client = TestClient(main.app)

    response = client.post("/outbox/missing/sent")

    assert response.status_code == 404
    assert response.json()["detail"] == "delivery not found"


def test_deadline_trigger_endpoint(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    client = TestClient(main.app)

    response = client.post(
        "/triggers/deadline-check",
        json={
            "user_id": "user_1",
            "session_id": "session_1",
            "issue_type": "academic.plural_major",
            "deadline": "2026-07-05",
            "today": "2026-07-01",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["days_left"] == 4
    assert data["message"]["session_id"] == "session_1"


def test_persona_endpoints_persist_and_return_snapshots(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    client = TestClient(main.app)

    created = client.post(
        "/persona/prefetch",
        json={
            "channel": "api",
            "user_id": "user_1",
            "session_id": "session_1",
            "text": "double major",
        },
    ).json()
    latest = client.get("/sessions/session_1/persona").json()
    snapshots = client.get("/sessions/session_1/personas").json()

    assert created["top_issue_types"] == ["academic.plural_major"]
    assert latest["top_issue_types"] == ["academic.plural_major"]
    assert snapshots[0]["session_id"] == "session_1"


def test_deadline_watch_endpoints(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", AppSettings(data_dir=tmp_path))
    client = TestClient(main.app)

    created = client.post(
        "/triggers/deadline-watches",
        json={
            "user_id": "user_1",
            "session_id": "session_1",
            "issue_type": "academic.plural_major",
            "deadline": "2026-07-05",
            "reminder_window_days": 7,
        },
    ).json()
    watches = client.get("/sessions/session_1/deadline-watches").json()
    due = client.post("/triggers/deadline-watches/due", json={"today": "2026-07-01"}).json()
    duplicate_due = client.post(
        "/triggers/deadline-watches/due",
        json={"today": "2026-07-01"},
    ).json()

    assert created["watch_id"].startswith("watch_")
    assert watches[0]["watch_id"] == created["watch_id"]
    assert due[0]["metadata"]["watch_id"] == created["watch_id"]
    assert duplicate_due == []

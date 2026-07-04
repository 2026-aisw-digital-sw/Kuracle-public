from __future__ import annotations

import time
from dataclasses import asdict
from datetime import date
from typing import Any

from hobit_ax_agentos.agentos.capabilities import agent_capabilities
from hobit_ax_agentos.agentos.runner import ServiceRunner
from hobit_ax_agentos.agents.channel_gateway import ChannelGateway
from hobit_ax_agentos.agents.coordinator import CoordinatorAgent
from hobit_ax_agentos.agents.trigger import TriggerAgent
from hobit_ax_agentos.config import AppSettings, bootstrap_local_dependencies
from hobit_ax_agentos.models import IncomingMessage, UserProfileRecord
from hobit_ax_agentos.services.delivery_dispatcher import DeliveryDispatcher
from hobit_ax_agentos.services.delivery_renderer import DeliveryRenderer
from hobit_ax_agentos.services.alerts import AlertsService
from hobit_ax_agentos.services.async_job_worker import AsyncJobWorker
from hobit_ax_agentos.services.config_snapshot import ConfigSnapshotService
from hobit_ax_agentos.services.doctor import DoctorService
from hobit_ax_agentos.services.e2e_smoke import E2ESmokeService
from hobit_ax_agentos.services.integration_probe import IntegrationProbeService
from hobit_ax_agentos.services.maintenance import MaintenanceService
from hobit_ax_agentos.services.metrics import MetricsService
from hobit_ax_agentos.services.run_control import RunControlService
from hobit_ax_agentos.services.run_retry import RunRetryService
from hobit_ax_agentos.services.run_trace import RunTraceService
from hobit_ax_agentos.services.retention import RetentionService
from hobit_ax_agentos.services.session_directory import SessionDirectoryService
from hobit_ax_agentos.services.session_state import SessionStateService
from hobit_ax_agentos.services.storage_audit import StorageAuditService
from hobit_ax_agentos.services.trigger_dispatcher import TriggerDispatcher
from hobit_ax_agentos.storage import (
    AsyncJobStore,
    ConversationStore,
    CoordinationPlanStore,
    DeadlineWatchStore,
    EscalationStore,
    OutboxStore,
    PersonaStore,
    ProfileStore,
    RunStore,
)

try:
    from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse, StreamingResponse
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Install hobit-ax-agentos[api] to run the API server") from exc


settings = AppSettings()
bootstrap_local_dependencies(settings)
app = FastAPI(title="Hobit AX AgentOS")


PUBLIC_PATHS = {"/health", "/ready"}
_rate_limit_buckets: dict[str, list[float]] = {}


@app.middleware("http")
async def require_api_token(request: Request, call_next):
    if _is_public_path(request.url.path) or not settings.api_token:
        return await call_next(request)
    if _request_token(request) != settings.api_token:
        return JSONResponse(
            status_code=401,
            content={"detail": "invalid or missing api token"},
        )
    return await call_next(request)


@app.middleware("http")
async def enforce_rate_limit(request: Request, call_next):
    if _is_public_path(request.url.path) or settings.rate_limit_per_minute <= 0:
        return await call_next(request)
    key = _rate_limit_key(request)
    now = time.monotonic()
    window_start = now - 60.0
    bucket = [
        timestamp
        for timestamp in _rate_limit_buckets.get(key, [])
        if timestamp >= window_start
    ]
    if len(bucket) >= settings.rate_limit_per_minute:
        _rate_limit_buckets[key] = bucket
        return JSONResponse(
            status_code=429,
            content={"detail": "rate limit exceeded"},
            headers={"Retry-After": "60"},
        )
    bucket.append(now)
    _rate_limit_buckets[key] = bucket
    return await call_next(request)


def _is_public_path(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith("/ui/")


def _rate_limit_key(request: Request) -> str:
    token = _request_token(request)
    if token:
        return f"token:{token}"
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return f"ip:{forwarded_for.split(',')[0].strip()}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


def _request_token(request: Request) -> str | None:
    header = request.headers.get("authorization")
    if header:
        scheme, _, token = header.partition(" ")
        if scheme.lower() == "bearer" and token:
            return token
    return request.headers.get("x-api-token")


def _job_worker() -> AsyncJobWorker:
    return AsyncJobWorker(
        settings=settings,
        runner_factory=lambda worker_settings: ServiceRunner(settings=worker_settings),
    )


def _run_async_job(
    job_id: str,
    message: IncomingMessage,
    timeout_seconds: float,
) -> None:
    del message
    try:
        _job_worker().run_one(
            job_id,
            timeout_seconds=timeout_seconds,
        )
    except KeyError:
        return


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "hobit-ax-agentos"}


@app.get("/ready")
def ready() -> dict:
    return DoctorService(settings).readiness()


@app.get("/doctor")
def doctor() -> dict:
    return DoctorService(settings).report()


@app.get("/integration/probe")
def integration_probe(rag_query: str = "복수전공 신청 기간 알려줘") -> dict:
    return IntegrationProbeService(settings).report(rag_query=rag_query)


@app.post("/smoke/e2e")
def e2e_smoke(payload: dict[str, Any] | None = None) -> dict:
    payload = payload or {}
    return E2ESmokeService(
        settings=settings,
        runner_factory=lambda smoke_settings: ServiceRunner(settings=smoke_settings),
    ).run(
        query=str(payload.get("query") or "double major application deadline"),
        channel=str(payload.get("channel") or "api"),
        user_id=str(payload["user_id"]) if payload.get("user_id") else None,
        session_id=str(payload["session_id"]) if payload.get("session_id") else None,
        timeout_seconds=float(payload.get("timeout_seconds", 120.0)),
        render_channel=str(payload["render_channel"]) if payload.get("render_channel") else None,
    )


@app.get("/config")
def config_snapshot() -> dict:
    return ConfigSnapshotService(settings).snapshot()


@app.post("/query")
def query(message: IncomingMessage) -> dict:
    result = ServiceRunner(settings=settings).run_message(message)
    return asdict(result)


@app.post("/query/submit")
def submit_query(
    message: IncomingMessage,
    background_tasks: BackgroundTasks,
    timeout_seconds: float = 120.0,
) -> dict:
    job = AsyncJobStore(settings.data_dir).create(
        kind="query",
        message=message,
        metadata={"timeout_seconds": timeout_seconds},
    )
    background_tasks.add_task(_run_async_job, job.job_id, message, timeout_seconds)
    return {
        "job": job.to_dict(),
        "status_url": f"/jobs/{job.job_id}",
    }


@app.post("/gateway/{channel}/dry-run")
def gateway_dry_run(channel: str, payload: dict[str, Any]) -> dict:
    message = ChannelGateway(settings).normalize(channel, payload)
    return {
        "message": message.to_dict(),
        "classification": CoordinatorAgent(settings).classify(message),
        "graph": ServiceRunner(settings=settings).dry_run_graph(message),
    }


@app.post("/gateway/{channel}/query")
def gateway_query(channel: str, payload: dict[str, Any]) -> dict:
    message = ChannelGateway(settings).normalize(channel, payload)
    timeout_seconds = float(payload.get("timeout_seconds", 120.0))
    result = ServiceRunner(settings=settings).run_message(
        message,
        timeout_seconds=timeout_seconds,
    )
    return {
        "message": message.to_dict(),
        "classification": CoordinatorAgent(settings).classify(message),
        "result": asdict(result),
    }


@app.post("/gateway/{channel}/submit")
def gateway_submit(
    channel: str,
    payload: dict[str, Any],
    background_tasks: BackgroundTasks,
) -> dict:
    message = ChannelGateway(settings).normalize(channel, payload)
    timeout_seconds = float(payload.get("timeout_seconds", 120.0))
    job = AsyncJobStore(settings.data_dir).create(
        kind=f"gateway:{channel}",
        message=message,
        metadata={"timeout_seconds": timeout_seconds},
    )
    background_tasks.add_task(_run_async_job, job.job_id, message, timeout_seconds)
    return {
        "message": message.to_dict(),
        "classification": CoordinatorAgent(settings).classify(message),
        "job": job.to_dict(),
        "status_url": f"/jobs/{job.job_id}",
    }


@app.post("/gateway/{channel}/stream")
async def gateway_stream(
    channel: str,
    payload: dict[str, Any],
    request: Request,
) -> StreamingResponse:
    """SSE streaming endpoint.

    Emits newline-delimited Server-Sent Events as the AgentOS graph executes:
      data: {"event": "run.started", ...}
      data: {"event": "node.started", "node_id": "knowledge_query", ...}
      data: {"event": "node.completed", "node_id": "knowledge_query", ...}
      ...
      data: {"event": "run.finished", "final": {...}, ...}

    The stream closes after the sentinel event or on client disconnect.
    """
    import asyncio
    import json
    import queue as _queue

    message = ChannelGateway(settings).normalize(channel, payload)
    timeout_seconds = float(payload.get("timeout_seconds", 120.0))
    q: _queue.Queue = _queue.Queue()

    async def _run_in_thread() -> None:
        loop = asyncio.get_event_loop()

        def _worker() -> None:
            try:
                ServiceRunner(settings=settings).run_message(
                    message,
                    timeout_seconds=timeout_seconds,
                    event_queue=q,
                )
            except Exception as exc:
                q.put({"event": "run.error", "error": type(exc).__name__, "detail": str(exc)})
                q.put(None)

        await loop.run_in_executor(None, _worker)

    async def _event_generator():
        task = asyncio.create_task(_run_in_thread())
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = q.get_nowait()
                    if item is None:  # sentinel — run finished or errored
                        break
                    yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                except _queue.Empty:
                    if task.done():
                        # drain any remaining events before closing
                        while not q.empty():
                            item = q.get_nowait()
                            if item is not None:
                                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                        break
                    await asyncio.sleep(0.05)
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.post("/gateway/{channel}")
def gateway(channel: str, payload: dict[str, Any]) -> dict:
    message = ChannelGateway(settings).normalize(channel, payload)
    return {
        "message": message.to_dict(),
        "classification": CoordinatorAgent(settings).classify(message),
    }


@app.put("/profiles/{user_id}")
def put_profile(user_id: str, record: UserProfileRecord) -> dict:
    record.user_id = user_id
    return ProfileStore(settings.data_dir).upsert(record).to_dict()


@app.get("/profiles/{user_id}")
def get_profile(user_id: str) -> dict | None:
    record = ProfileStore(settings.data_dir).get(user_id)
    return record.to_dict() if record else None


@app.post("/persona/prefetch")
def persona_prefetch(message: IncomingMessage) -> dict:
    from hobit_ax_agentos.services.persona_prefetch import PersonaPrefetchService

    snapshot = PersonaPrefetchService(settings).prefetch(message)
    PersonaStore(settings.data_dir).append(snapshot)
    return snapshot.to_dict()


@app.get("/sessions")
def sessions(limit: int = 50) -> dict:
    return SessionDirectoryService(settings.data_dir).list_sessions(limit=limit)


@app.get("/sessions/{session_id}/persona")
def session_persona(session_id: str) -> dict | None:
    snapshot = PersonaStore(settings.data_dir).latest(session_id)
    return snapshot.to_dict() if snapshot else None


@app.get("/sessions/{session_id}/personas")
def session_personas(session_id: str, limit: int = 50) -> list[dict]:
    return [
        snapshot.to_dict()
        for snapshot in PersonaStore(settings.data_dir).list_by_session(session_id, limit=limit)
    ]


@app.get("/sessions/{session_id}/history")
def session_history(session_id: str, limit: int = 50) -> list[dict]:
    return [
        turn.to_dict()
        for turn in ConversationStore(settings.data_dir).list_by_session(session_id, limit=limit)
    ]


@app.get("/sessions/{session_id}/summary")
def session_summary(session_id: str, limit: int = 10) -> dict:
    return SessionStateService(str(settings.data_dir)).summary(session_id, limit=limit)


@app.get("/sessions/{session_id}/timeline")
def session_timeline(session_id: str, limit: int = 50) -> dict:
    return SessionStateService(str(settings.data_dir)).timeline(session_id, limit=limit)


@app.get("/sessions/{session_id}/export")
def session_export(session_id: str, limit: int = 1000000) -> dict:
    return MaintenanceService(settings.data_dir).export_session(session_id, limit=limit)


@app.get("/maintenance/storage")
def maintenance_storage() -> dict:
    return MaintenanceService(settings.data_dir).storage_stats()


@app.get("/jobs")
def list_jobs(status: str | None = None, limit: int = 50) -> list[dict]:
    return [
        job.to_dict()
        for job in AsyncJobStore(settings.data_dir).list_by_status(
            status=status,
            limit=limit,
        )
    ]


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = AsyncJobStore(settings.data_dir).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job.to_dict()


@app.post("/jobs/run-queued")
def run_queued_jobs(payload: dict[str, Any] | None = None) -> list[dict]:
    payload = payload or {}
    return _job_worker().run_queued(limit=int(payload.get("limit", 10)))


@app.post("/jobs/requeue-stale")
def requeue_stale_jobs(payload: dict[str, Any] | None = None) -> dict:
    payload = payload or {}
    return _job_worker().requeue_stale_running(
        older_than_minutes=int(payload.get("older_than_minutes", 30)),
        limit=int(payload.get("limit", 50)),
    )


@app.post("/jobs/{job_id}/run")
def run_job(job_id: str, payload: dict[str, Any] | None = None) -> dict:
    payload = payload or {}
    try:
        return _job_worker().run_one(
            job_id,
            timeout_seconds=(
                float(payload["timeout_seconds"])
                if payload.get("timeout_seconds") is not None
                else None
            ),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc


@app.post("/jobs/{job_id}/retry")
def retry_job(job_id: str, background_tasks: BackgroundTasks) -> dict:
    store = AsyncJobStore(settings.data_dir)
    source = store.get(job_id)
    if source is None:
        raise HTTPException(status_code=404, detail="job not found")
    if source.status not in {"FAILED", "CANCELLED"}:
        raise HTTPException(
            status_code=409,
            detail=f"job {job_id} is not retryable from state {source.status}",
        )
    retry = store.create_retry(source)
    message = IncomingMessage(**retry.message)
    timeout_seconds = float(retry.metadata.get("timeout_seconds", 120.0))
    background_tasks.add_task(_run_async_job, retry.job_id, message, timeout_seconds)
    return {
        "source_job": source.to_dict(),
        "job": retry.to_dict(),
        "status_url": f"/jobs/{retry.job_id}",
    }


@app.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, payload: dict[str, Any] | None = None) -> dict:
    payload = payload or {}
    try:
        return AsyncJobStore(settings.data_dir).cancel(
            job_id,
            reason=str(payload.get("reason")) if payload.get("reason") else None,
        ).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/maintenance/audit")
def maintenance_audit() -> dict:
    return StorageAuditService(settings.data_dir).audit()


@app.post("/maintenance/prune")
def maintenance_prune(payload: dict[str, Any]) -> dict:
    return RetentionService(settings.data_dir).prune(
        older_than_days=int(payload["older_than_days"]),
        dry_run=bool(payload.get("dry_run", True)),
    )


@app.get("/metrics/summary")
def metrics_summary() -> dict:
    return MetricsService(settings.data_dir).summary()


@app.get("/alerts")
def alerts(
    running_minutes: int = 10,
    job_minutes: int = 10,
    delivery_minutes: int = 10,
    escalation_minutes: int = 30,
    deadline_days: int = 3,
) -> dict:
    return AlertsService(settings.data_dir).alerts(
        running_minutes=running_minutes,
        job_minutes=job_minutes,
        delivery_minutes=delivery_minutes,
        escalation_minutes=escalation_minutes,
        deadline_days=deadline_days,
    )


@app.get("/agents")
def agents(include_disabled: bool = True) -> list[dict]:
    capabilities = agent_capabilities(settings)
    if not include_disabled:
        capabilities = [capability for capability in capabilities if capability.enabled]
    return [capability.to_dict() for capability in capabilities]


@app.get("/outbox")
def list_outbox(status: str | None = None, limit: int = 50) -> list[dict]:
    return [
        delivery.to_dict()
        for delivery in OutboxStore(settings.data_dir).list_by_status(status=status, limit=limit)
    ]


@app.get("/sessions/{session_id}/outbox")
def session_outbox(session_id: str, limit: int = 50) -> list[dict]:
    return [
        delivery.to_dict()
        for delivery in OutboxStore(settings.data_dir).list_by_session(session_id, limit=limit)
    ]


@app.post("/outbox/{delivery_id}/sent")
def mark_delivery_sent(delivery_id: str) -> dict:
    try:
        return OutboxStore(settings.data_dir).mark_sent(delivery_id).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="delivery not found") from exc


@app.post("/outbox/{delivery_id}/failed")
def mark_delivery_failed(delivery_id: str, payload: dict[str, Any] | None = None) -> dict:
    payload = payload or {}
    try:
        return OutboxStore(settings.data_dir).mark_failed(
            delivery_id,
            error=str(payload.get("error")) if payload.get("error") else None,
        ).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="delivery not found") from exc


@app.post("/outbox/{delivery_id}/dispatch")
def dispatch_delivery(delivery_id: str) -> dict:
    try:
        return DeliveryDispatcher(settings).dispatch_one(delivery_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="delivery not found") from exc


@app.get("/outbox/{delivery_id}/render")
def render_delivery(delivery_id: str, channel: str | None = None) -> dict:
    try:
        return DeliveryRenderer(outbox_store=OutboxStore(settings.data_dir)).render_one(
            delivery_id,
            channel=channel,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="delivery not found") from exc


@app.post("/outbox/dispatch")
def dispatch_pending_deliveries(payload: dict[str, Any] | None = None) -> list[dict]:
    payload = payload or {}
    return DeliveryDispatcher(settings).dispatch_pending(limit=int(payload.get("limit", 50)))


@app.get("/escalations")
def list_escalations(status: str | None = None) -> list[dict]:
    cases = EscalationStore(settings.data_dir).list_all()
    if status:
        cases = [case for case in cases if case.status == status.upper()]
    return [case.to_dict() for case in cases]


@app.get("/escalations/{escalation_id}")
def get_escalation(escalation_id: str) -> dict | None:
    case = EscalationStore(settings.data_dir).get(escalation_id)
    if case is None:
        raise HTTPException(status_code=404, detail="escalation not found")
    return case.to_dict()


@app.post("/escalations/{escalation_id}/acknowledge")
def acknowledge_escalation(escalation_id: str) -> dict:
    try:
        return EscalationStore(settings.data_dir).acknowledge(escalation_id).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="escalation not found") from exc


@app.post("/escalations/{escalation_id}/assign")
def assign_escalation(escalation_id: str, payload: dict[str, Any]) -> dict:
    try:
        return EscalationStore(settings.data_dir).assign(
            escalation_id,
            assignee=str(payload["assignee"]),
        ).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="escalation not found") from exc


@app.post("/escalations/{escalation_id}/notes")
def add_escalation_note(escalation_id: str, payload: dict[str, Any]) -> dict:
    try:
        return EscalationStore(settings.data_dir).add_note(
            escalation_id,
            author=str(payload.get("author") or "operator"),
            text=str(payload["text"]),
            visibility=str(payload.get("visibility") or "internal"),
        ).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="escalation not found") from exc


@app.post("/escalations/{escalation_id}/resolve")
def resolve_escalation(escalation_id: str, payload: dict[str, Any] | None = None) -> dict:
    payload = payload or {}
    try:
        from hobit_ax_agentos.agents.escalation import EscalationAgent

        return EscalationAgent(settings).resolve(
            escalation_id,
            signal=str(payload.get("signal") or "neutral"),
            comment=payload.get("comment"),
        ).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="escalation not found") from exc


@app.get("/sessions/{session_id}/plans")
def session_plans(session_id: str, limit: int = 50) -> list[dict]:
    return [
        plan.to_dict()
        for plan in CoordinationPlanStore(settings.data_dir).list_by_session(
            session_id,
            limit=limit,
        )
    ]


@app.get("/sessions/{session_id}/runs")
def session_runs(
    session_id: str,
    limit: int = 50,
    state: str | None = None,
) -> list[dict]:
    return [
        run.to_dict()
        for run in RunStore(settings.data_dir).list_by_session(
            session_id,
            limit=limit,
            state=state,
        )
    ]


@app.get("/runs")
def list_runs(state: str | None = None, limit: int = 50) -> list[dict]:
    return [
        run.to_dict()
        for run in RunStore(settings.data_dir).list_by_state(
            state=state,
            limit=limit,
        )
    ]


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    run = RunStore(settings.data_dir).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run.to_dict()


@app.get("/runs/{run_id}/trace")
def run_trace(run_id: str, conversation_limit: int = 20) -> dict:
    trace = RunTraceService(settings.data_dir).trace(
        run_id,
        conversation_limit=conversation_limit,
    )
    if trace is None:
        raise HTTPException(status_code=404, detail="run not found")
    return trace


@app.post("/runs/{run_id}/retry")
def retry_run(run_id: str, payload: dict[str, Any] | None = None) -> dict:
    payload = payload or {}
    try:
        retry = RunRetryService(settings).retry(
            run_id,
            timeout_seconds=float(payload.get("timeout_seconds", 120.0)),
        )
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if retry is None:
        raise HTTPException(status_code=404, detail="run not found")
    return retry


@app.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str, payload: dict[str, Any] | None = None) -> dict:
    payload = payload or {}
    try:
        cancelled = RunControlService(settings.data_dir).cancel(
            run_id,
            reason=str(payload.get("reason")) if payload.get("reason") else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if cancelled is None:
        raise HTTPException(status_code=404, detail="run not found")
    return cancelled


@app.post("/triggers/deadline-check")
def deadline_check(payload: dict[str, Any]) -> dict | None:
    event = TriggerAgent().deadline_check(
        user_id=str(payload["user_id"]),
        session_id=str(payload["session_id"]),
        issue_type=str(payload["issue_type"]),
        deadline=date.fromisoformat(str(payload["deadline"])),
        today=date.fromisoformat(str(payload["today"])) if payload.get("today") else None,
    )
    return event.to_dict() if event else None


@app.post("/triggers/deadline-watches")
def create_deadline_watch(payload: dict[str, Any]) -> dict:
    watch = TriggerAgent(settings).register_deadline_watch(
        user_id=str(payload["user_id"]),
        session_id=str(payload["session_id"]),
        issue_type=str(payload["issue_type"]),
        deadline=date.fromisoformat(str(payload["deadline"])),
        reminder_window_days=int(payload.get("reminder_window_days", 7)),
        source=str(payload.get("source", "api")),
        metadata=dict(payload.get("metadata") or {}),
    )
    return watch.to_dict()


@app.get("/sessions/{session_id}/deadline-watches")
def session_deadline_watches(session_id: str, limit: int = 50) -> list[dict]:
    return [
        watch.to_dict()
        for watch in DeadlineWatchStore(settings.data_dir).list_by_session(
            session_id,
            limit=limit,
        )
    ]


@app.post("/triggers/deadline-watches/due")
def due_deadline_triggers(payload: dict[str, Any] | None = None) -> list[dict]:
    payload = payload or {}
    today = date.fromisoformat(str(payload["today"])) if payload.get("today") else None
    if payload.get("dispatch"):
        return TriggerDispatcher(settings).dispatch_due_deadline_events(
            today=today,
            timeout_seconds=float(payload.get("timeout_seconds", 120.0)),
        )
    return [event.to_dict() for event in TriggerAgent(settings).due_deadline_events(today=today)]


@app.post("/triggers/regulation-refresh")
def regulation_refresh_trigger(payload: dict[str, Any] | None = None) -> list[dict]:
    payload = payload or {}
    if payload.get("dispatch"):
        return TriggerDispatcher(settings).dispatch_regulation_change_events(
            timeout_seconds=float(payload.get("timeout_seconds", 120.0)),
        )
    return [event.to_dict() for event in TriggerAgent(settings).regulation_change_events()]

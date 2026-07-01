from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hobit_ax_agentos.config import AppSettings
from hobit_ax_agentos.models import IncomingMessage, ServiceResult
from hobit_ax_agentos.services.async_job_worker import AsyncJobWorker
from hobit_ax_agentos.storage import AsyncJobStore


class SuccessfulRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[IncomingMessage, float]] = []

    def run_message(self, message, timeout_seconds: float = 120.0) -> ServiceResult:
        self.calls.append((message, timeout_seconds))
        return ServiceResult(
            run_id=f"run_{len(self.calls)}",
            trace_id=f"trace_{len(self.calls)}",
            final={"response": message.text},
            run_summary={"state": "COMPLETED"},
            worker_results=[],
        )


class FailingRunner:
    def run_message(self, message, timeout_seconds: float = 120.0) -> ServiceResult:
        raise RuntimeError("worker exploded")


def test_async_job_worker_runs_one_queued_job(tmp_path) -> None:
    store = AsyncJobStore(tmp_path)
    runner = SuccessfulRunner()
    job = store.create(
        kind="query",
        message=IncomingMessage("api", "user_1", "hello", "session_1"),
        metadata={"timeout_seconds": 3.5},
    )
    worker = AsyncJobWorker(
        settings=AppSettings(data_dir=tmp_path),
        job_store=store,
        runner_factory=lambda settings: runner,
    )

    result = worker.run_one(job.job_id)

    saved = store.get(job.job_id)
    assert result["skipped"] is False
    assert saved.status == "COMPLETED"
    assert saved.run_id == "run_1"
    assert saved.result["final"]["response"] == "hello"
    assert runner.calls[0][0].text == "hello"
    assert runner.calls[0][1] == 3.5


def test_async_job_worker_marks_job_failed_on_runner_error(tmp_path) -> None:
    store = AsyncJobStore(tmp_path)
    job = store.create(
        kind="query",
        message=IncomingMessage("api", "user_1", "broken", "session_1"),
    )
    worker = AsyncJobWorker(
        settings=AppSettings(data_dir=tmp_path),
        job_store=store,
        runner_factory=lambda settings: FailingRunner(),
    )

    result = worker.run_one(job.job_id)

    saved = store.get(job.job_id)
    assert result["skipped"] is False
    assert result["error"] == "worker exploded"
    assert saved.status == "FAILED"
    assert saved.error_type == "RuntimeError"


def test_async_job_worker_skips_non_queued_job(tmp_path) -> None:
    store = AsyncJobStore(tmp_path)
    job = store.create(
        kind="query",
        message=IncomingMessage("api", "user_1", "done", "session_1"),
    )
    job.status = "COMPLETED"
    store.save(job)
    runner = SuccessfulRunner()
    worker = AsyncJobWorker(
        settings=AppSettings(data_dir=tmp_path),
        job_store=store,
        runner_factory=lambda settings: runner,
    )

    result = worker.run_one(job.job_id)

    assert result["skipped"] is True
    assert result["reason"] == "job_status_completed"
    assert runner.calls == []


def test_async_job_worker_runs_queued_batch(tmp_path) -> None:
    store = AsyncJobStore(tmp_path)
    store.create("query", IncomingMessage("api", "user_1", "first", "session_1"))
    store.create("query", IncomingMessage("api", "user_1", "second", "session_1"))
    runner = SuccessfulRunner()
    worker = AsyncJobWorker(
        settings=AppSettings(data_dir=tmp_path),
        job_store=store,
        runner_factory=lambda settings: runner,
    )

    results = worker.run_queued(limit=10)

    assert len(results) == 2
    assert [job.status for job in store.list_all()] == ["COMPLETED", "COMPLETED"]
    assert [call[0].text for call in runner.calls] == ["first", "second"]


def test_async_job_worker_loop_runs_until_idle(tmp_path) -> None:
    store = AsyncJobStore(tmp_path)
    store.create("query", IncomingMessage("api", "user_1", "first", "session_1"))
    runner = SuccessfulRunner()
    sleeps: list[float] = []
    worker = AsyncJobWorker(
        settings=AppSettings(data_dir=tmp_path),
        job_store=store,
        runner_factory=lambda settings: runner,
    )

    result = worker.run_loop(
        limit=10,
        interval_seconds=0.25,
        max_iterations=5,
        stop_when_idle=True,
        sleep_fn=sleeps.append,
    )

    assert result["iterations"] == 2
    assert result["processed"] == 1
    assert [batch["processed"] for batch in result["batches"]] == [1, 0]
    assert sleeps == [0.25]
    assert [job.status for job in store.list_all()] == ["COMPLETED"]


def test_async_job_worker_loop_respects_max_iterations(tmp_path) -> None:
    store = AsyncJobStore(tmp_path)
    runner = SuccessfulRunner()
    sleeps: list[float] = []
    worker = AsyncJobWorker(
        settings=AppSettings(data_dir=tmp_path),
        job_store=store,
        runner_factory=lambda settings: runner,
    )

    result = worker.run_loop(
        limit=10,
        interval_seconds=0.5,
        max_iterations=3,
        sleep_fn=sleeps.append,
    )

    assert result["iterations"] == 3
    assert result["processed"] == 0
    assert [batch["processed"] for batch in result["batches"]] == [0, 0, 0]
    assert sleeps == [0.5, 0.5]


def test_async_job_worker_requeues_stale_running_jobs(tmp_path) -> None:
    store = AsyncJobStore(tmp_path)
    stale = store.create("query", IncomingMessage("api", "user_1", "stale", "session_1"))
    stale.status = "RUNNING"
    stale.updated_at = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
    store.save(stale, touch=False)
    fresh = store.create("query", IncomingMessage("api", "user_1", "fresh", "session_1"))
    fresh.status = "RUNNING"
    fresh.updated_at = datetime.now(timezone.utc).isoformat()
    store.save(fresh, touch=False)
    worker = AsyncJobWorker(
        settings=AppSettings(data_dir=tmp_path),
        job_store=store,
        runner_factory=lambda settings: SuccessfulRunner(),
    )

    result = worker.requeue_stale_running(older_than_minutes=30)

    jobs = {job.job_id: job for job in store.list_all()}
    assert result["count"] == 1
    assert result["jobs"][0]["job_id"] == stale.job_id
    assert jobs[stale.job_id].status == "QUEUED"
    assert jobs[stale.job_id].metadata["requeue_count"] == 1
    assert jobs[fresh.job_id].status == "RUNNING"


def test_async_job_worker_loop_can_requeue_then_process(tmp_path) -> None:
    store = AsyncJobStore(tmp_path)
    job = store.create("query", IncomingMessage("api", "user_1", "stale", "session_1"))
    job.status = "RUNNING"
    job.updated_at = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
    store.save(job, touch=False)
    runner = SuccessfulRunner()
    worker = AsyncJobWorker(
        settings=AppSettings(data_dir=tmp_path),
        job_store=store,
        runner_factory=lambda settings: runner,
    )

    result = worker.run_loop(
        limit=10,
        max_iterations=1,
        requeue_stale_minutes=30,
    )

    saved = store.get(job.job_id)
    assert result["processed"] == 1
    assert result["batches"][0]["requeued"]["count"] == 1
    assert saved.status == "COMPLETED"
    assert runner.calls[0][0].text == "stale"

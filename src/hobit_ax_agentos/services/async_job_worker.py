from __future__ import annotations

import time
from typing import Callable

from hobit_ax_agentos.agentos.runner import ServiceRunner
from hobit_ax_agentos.config import AppSettings
from hobit_ax_agentos.models import IncomingMessage, ServiceResult
from hobit_ax_agentos.storage import AsyncJobStore


RunnerFactory = Callable[[AppSettings], ServiceRunner]


class AsyncJobWorker:
    def __init__(
        self,
        settings: AppSettings | None = None,
        job_store: AsyncJobStore | None = None,
        runner_factory: RunnerFactory | None = None,
    ) -> None:
        self.settings = settings or AppSettings()
        self.job_store = job_store or AsyncJobStore(self.settings.data_dir)
        self.runner_factory = runner_factory or (lambda settings: ServiceRunner(settings=settings))

    def run_one(self, job_id: str, timeout_seconds: float | None = None) -> dict:
        job = self.job_store.get(job_id)
        if job is None:
            raise KeyError(job_id)
        if job.status != "QUEUED":
            return {
                "job": job.to_dict(),
                "result": None,
                "skipped": True,
                "reason": f"job_status_{job.status.lower()}",
            }

        timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else float(job.metadata.get("timeout_seconds", 120.0))
        )
        message = IncomingMessage(**job.message)
        running = self.job_store.mark_running(job_id)
        try:
            result = self.runner_factory(self.settings).run_message(
                message,
                timeout_seconds=timeout,
            )
        except Exception as exc:
            failed = self.job_store.mark_failed(job_id, exc)
            return {
                "job": failed.to_dict(),
                "result": None,
                "skipped": False,
                "error": str(exc),
            }
        completed = self.job_store.mark_completed(job_id, result)
        return {
            "job": completed.to_dict(),
            "result": self._result_to_dict(result),
            "skipped": False,
            "previous_status": running.status,
        }

    def run_queued(self, limit: int = 10) -> list[dict]:
        queued = self.job_store.list_by_status("QUEUED", limit=limit)
        return [self.run_one(job.job_id) for job in queued]

    def requeue_stale_running(
        self,
        older_than_minutes: int = 30,
        limit: int = 50,
    ) -> dict:
        jobs = self.job_store.requeue_stale_running(
            older_than_minutes=older_than_minutes,
            limit=limit,
        )
        return {
            "count": len(jobs),
            "jobs": [job.to_dict() for job in jobs],
        }

    def run_loop(
        self,
        limit: int = 10,
        interval_seconds: float = 1.0,
        max_iterations: int | None = None,
        stop_when_idle: bool = False,
        requeue_stale_minutes: int | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> dict:
        sleep = sleep_fn or time.sleep
        iterations = 0
        batches: list[dict] = []
        while max_iterations is None or iterations < max_iterations:
            iterations += 1
            requeued = None
            if requeue_stale_minutes is not None:
                requeued = self.requeue_stale_running(
                    older_than_minutes=requeue_stale_minutes,
                    limit=limit,
                )
            results = self.run_queued(limit=limit)
            batch = {
                "iteration": iterations,
                "requeued": requeued,
                "processed": len(results),
                "results": results,
            }
            batches.append(batch)
            if stop_when_idle and not results:
                break
            if max_iterations is not None and iterations >= max_iterations:
                break
            sleep(interval_seconds)
        return {
            "iterations": iterations,
            "processed": sum(batch["processed"] for batch in batches),
            "batches": batches,
        }

    def _result_to_dict(self, result: ServiceResult) -> dict:
        return {
            "run_id": result.run_id,
            "trace_id": result.trace_id,
            "final": result.final,
            "run_summary": result.run_summary,
            "worker_results": result.worker_results,
        }

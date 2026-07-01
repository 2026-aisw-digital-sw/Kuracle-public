from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from hobit_ax_agentos.models import AsyncJobRecord, IncomingMessage, ServiceResult, utc_now
from hobit_ax_agentos.storage.locking import file_lock


class AsyncJobStore:
    def __init__(self, root: Path | str = "data") -> None:
        self.root = Path(root)
        self.path = self.root / "async_jobs.jsonl"
        self.root.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        kind: str,
        message: IncomingMessage,
        metadata: dict | None = None,
    ) -> AsyncJobRecord:
        job = AsyncJobRecord(
            job_id=f"job_{uuid4().hex}",
            kind=kind,
            session_id=message.session_id,
            user_id=message.user_id,
            channel=message.channel,
            message=message.to_dict(),
            metadata=dict(metadata or {}),
        )
        return self.save(job)

    def create_retry(self, source: AsyncJobRecord) -> AsyncJobRecord:
        message = IncomingMessage(**source.message)
        retry_count = int(source.metadata.get("retry_count", 0)) + 1
        metadata = {
            **source.metadata,
            "retry_of_job_id": source.job_id,
            "retry_count": retry_count,
        }
        return self.create(
            kind=source.kind,
            message=message,
            metadata=metadata,
        )

    def save(self, job: AsyncJobRecord, touch: bool = True) -> AsyncJobRecord:
        with file_lock(self.path):
            jobs = {item.job_id: item for item in self._read_all_unlocked()}
            if touch:
                job.updated_at = utc_now()
            jobs[job.job_id] = job
            self._write_all_unlocked(jobs.values())
        return job

    def mark_running(self, job_id: str) -> AsyncJobRecord:
        job = self._require(job_id)
        job.status = "RUNNING"
        job.error_type = None
        job.error = None
        return self.save(job)

    def mark_completed(self, job_id: str, result: ServiceResult) -> AsyncJobRecord:
        job = self._require(job_id)
        job.status = "COMPLETED"
        job.run_id = result.run_id
        job.trace_id = result.trace_id
        job.result = {
            "run_id": result.run_id,
            "trace_id": result.trace_id,
            "final": result.final,
            "run_summary": result.run_summary,
            "worker_results": result.worker_results,
        }
        job.error_type = None
        job.error = None
        return self.save(job)

    def mark_failed(self, job_id: str, error: Exception) -> AsyncJobRecord:
        job = self._require(job_id)
        job.status = "FAILED"
        job.error_type = error.__class__.__name__
        job.error = str(error)
        return self.save(job)

    def cancel(self, job_id: str, reason: str | None = None) -> AsyncJobRecord:
        job = self._require(job_id)
        if job.status != "QUEUED":
            raise ValueError(f"job {job_id} is not cancellable from state {job.status}")
        job.status = "CANCELLED"
        job.error_type = "Cancelled"
        job.error = reason or "cancelled by operator"
        job.metadata = {
            **job.metadata,
            "cancel_reason": reason or "cancelled by operator",
            "cancelled_at": utc_now(),
        }
        return self.save(job)

    def requeue_stale_running(
        self,
        older_than_minutes: int,
        now: datetime | None = None,
        limit: int = 50,
    ) -> list[AsyncJobRecord]:
        now = now or datetime.now(timezone.utc)
        requeued: list[AsyncJobRecord] = []
        with file_lock(self.path):
            jobs = {item.job_id: item for item in self._read_all_unlocked()}
            for job in jobs.values():
                if len(requeued) >= limit:
                    break
                if job.status != "RUNNING":
                    continue
                age_minutes = self._age_minutes(job.updated_at, now)
                if age_minutes < older_than_minutes:
                    continue
                count = int(job.metadata.get("requeue_count", 0)) + 1
                job.status = "QUEUED"
                job.error_type = None
                job.error = None
                job.metadata = {
                    **job.metadata,
                    "requeue_count": count,
                    "last_requeued_at": utc_now(),
                    "last_requeue_reason": (
                        f"stale_running_for_{age_minutes}_minutes"
                    ),
                }
                job.updated_at = utc_now()
                jobs[job.job_id] = job
                requeued.append(job)
            if requeued:
                self._write_all_unlocked(jobs.values())
        return requeued

    def get(self, job_id: str) -> AsyncJobRecord | None:
        return next((job for job in self.list_all() if job.job_id == job_id), None)

    def list_by_session(self, session_id: str, limit: int = 50) -> list[AsyncJobRecord]:
        jobs = [job for job in self.list_all() if job.session_id == session_id]
        return jobs[-limit:]

    def list_by_status(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[AsyncJobRecord]:
        jobs = self.list_all()
        if status:
            jobs = [job for job in jobs if job.status == status.upper()]
        return jobs[-limit:]

    def list_all(self) -> list[AsyncJobRecord]:
        with file_lock(self.path):
            return self._read_all_unlocked()

    def _read_all_unlocked(self) -> list[AsyncJobRecord]:
        if not self.path.exists():
            return []
        jobs: list[AsyncJobRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            jobs.append(AsyncJobRecord(**json.loads(line)))
        return jobs

    def _write_all_unlocked(self, jobs: Iterable[AsyncJobRecord]) -> None:
        lines = [json.dumps(job.to_dict(), ensure_ascii=False) for job in jobs]
        self.path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def _age_minutes(self, timestamp: str, now: datetime) -> int:
        parsed = datetime.fromisoformat(timestamp)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0, int((now - parsed).total_seconds() // 60))

    def _require(self, job_id: str) -> AsyncJobRecord:
        job = self.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return job

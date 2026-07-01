from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from hobit_ax_agentos.storage import (
    AsyncJobStore,
    DeadlineWatchStore,
    EscalationStore,
    OutboxStore,
    RunStore,
)


class AlertsService:
    def __init__(self, data_dir: str | Path) -> None:
        self.jobs = AsyncJobStore(data_dir)
        self.runs = RunStore(data_dir)
        self.deadline_watches = DeadlineWatchStore(data_dir)
        self.escalations = EscalationStore(data_dir)
        self.outbox = OutboxStore(data_dir)

    def alerts(
        self,
        now: datetime | None = None,
        today: date | None = None,
        running_minutes: int = 10,
        job_minutes: int = 10,
        delivery_minutes: int = 10,
        escalation_minutes: int = 30,
        deadline_days: int = 3,
    ) -> dict:
        now = now or datetime.now(timezone.utc)
        today = today or now.date()
        items = []
        for job in self.jobs.list_all():
            age_minutes = self._age_minutes(job.updated_at, now)
            if job.status in {"QUEUED", "RUNNING"} and age_minutes >= job_minutes:
                items.append(
                    self._alert(
                        severity="MEDIUM",
                        alert_type="job.stale",
                        record_id=job.job_id,
                        message=(
                            f"Async job {job.job_id} has been {job.status} "
                            f"for {age_minutes} minutes."
                        ),
                        age_minutes=age_minutes,
                        record=job.to_dict(),
                    )
                )
            if job.status == "FAILED":
                items.append(
                    self._alert(
                        severity="MEDIUM",
                        alert_type="job.failed",
                        record_id=job.job_id,
                        message=f"Async job {job.job_id} failed: {job.error or 'unknown error'}",
                        age_minutes=age_minutes,
                        record=job.to_dict(),
                    )
                )

        for run in self.runs.list_all():
            if run.state not in {"PENDING", "RUNNING", "BLOCKED"}:
                continue
            age_minutes = self._age_minutes(run.updated_at, now)
            if age_minutes >= running_minutes:
                items.append(
                    self._alert(
                        severity="HIGH" if run.state == "BLOCKED" else "MEDIUM",
                        alert_type="run.stale",
                        record_id=run.run_id,
                        message=f"Run {run.run_id} has been {run.state} for {age_minutes} minutes.",
                        age_minutes=age_minutes,
                        record=run.to_dict(),
                    )
                )

        for delivery in self.outbox.list_all():
            if delivery.status != "PENDING":
                continue
            age_minutes = self._age_minutes(delivery.updated_at, now)
            if age_minutes >= delivery_minutes:
                items.append(
                    self._alert(
                        severity="MEDIUM",
                        alert_type="outbox.pending",
                        record_id=delivery.delivery_id,
                        message=(
                            f"Delivery {delivery.delivery_id} has been pending "
                            f"for {age_minutes} minutes."
                        ),
                        age_minutes=age_minutes,
                        record=delivery.to_dict(),
                    )
                )

        for case in self.escalations.list_all():
            if case.status not in {"OPEN", "ACKNOWLEDGED"}:
                continue
            age_minutes = self._age_minutes(case.updated_at, now)
            if age_minutes >= escalation_minutes:
                items.append(
                    self._alert(
                        severity="HIGH" if case.status == "OPEN" else "MEDIUM",
                        alert_type="escalation.open",
                        record_id=case.escalation_id,
                        message=(
                            f"Escalation {case.escalation_id} has been {case.status} "
                            f"for {age_minutes} minutes."
                        ),
                        age_minutes=age_minutes,
                        record=case.to_dict(),
                    )
                )

        for watch in self.deadline_watches.list_all():
            if watch.status != "ACTIVE":
                continue
            days_left = (date.fromisoformat(watch.deadline) - today).days
            if 0 <= days_left <= deadline_days:
                items.append(
                    self._alert(
                        severity="HIGH" if days_left == 0 else "MEDIUM",
                        alert_type="deadline.due",
                        record_id=watch.watch_id,
                        message=(
                            f"Deadline watch {watch.watch_id} is due in "
                            f"{days_left} days."
                        ),
                        age_minutes=0,
                        record={
                            **watch.to_dict(),
                            "days_left": days_left,
                        },
                    )
                )

        severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        items.sort(
            key=lambda item: (
                severity_order.get(item["severity"], 99),
                item["alert_type"],
                item["record_id"],
            )
        )
        return {
            "count": len(items),
            "items": items,
        }

    def _age_minutes(self, timestamp: str, now: datetime) -> int:
        parsed = datetime.fromisoformat(timestamp)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0, int((now - parsed).total_seconds() // 60))

    def _alert(
        self,
        severity: str,
        alert_type: str,
        record_id: str,
        message: str,
        age_minutes: int,
        record: dict,
    ) -> dict:
        return {
            "severity": severity,
            "alert_type": alert_type,
            "record_id": record_id,
            "message": message,
            "age_minutes": age_minutes,
            "record": record,
        }

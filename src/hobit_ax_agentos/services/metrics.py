from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterable

from hobit_ax_agentos.storage import (
    AsyncJobStore,
    ConversationStore,
    CoordinationPlanStore,
    DeadlineWatchStore,
    EscalationStore,
    OutboxStore,
    PersonaStore,
    RunStore,
)


class MetricsService:
    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self.conversations = ConversationStore(self.data_dir)
        self.jobs = AsyncJobStore(self.data_dir)
        self.personas = PersonaStore(self.data_dir)
        self.plans = CoordinationPlanStore(self.data_dir)
        self.runs = RunStore(self.data_dir)
        self.deadline_watches = DeadlineWatchStore(self.data_dir)
        self.escalations = EscalationStore(self.data_dir)
        self.outbox = OutboxStore(self.data_dir)

    def summary(self) -> dict:
        runs = self.runs.list_all()
        jobs = self.jobs.list_all()
        deliveries = self.outbox.list_all()
        escalations = self.escalations.list_all()
        deadline_watches = self.deadline_watches.list_all()

        run_states = self._count(item.state for item in runs)
        job_statuses = self._count(item.status for item in jobs)
        delivery_statuses = self._count(item.status for item in deliveries)
        escalation_statuses = self._count(item.status for item in escalations)
        deadline_watch_statuses = self._count(item.status for item in deadline_watches)

        return {
            "data_dir": str(self.data_dir),
            "totals": {
                "conversation_turns": len(self.conversations.list_all()),
                "async_jobs": len(jobs),
                "persona_snapshots": len(self.personas.list_all()),
                "coordination_plans": len(self.plans.list_all()),
                "agent_runs": len(runs),
                "outbox": len(deliveries),
                "escalations": len(escalations),
                "deadline_watches": len(deadline_watches),
            },
            "by_status": {
                "agent_runs": run_states,
                "async_jobs": job_statuses,
                "outbox": delivery_statuses,
                "escalations": escalation_statuses,
                "deadline_watches": deadline_watch_statuses,
            },
            "backlog": {
                "running_runs": sum(run_states.get(state, 0) for state in ("PENDING", "RUNNING")),
                "active_async_jobs": sum(
                    job_statuses.get(status, 0) for status in ("QUEUED", "RUNNING")
                ),
                "failed_runs": sum(
                    run_states.get(state, 0)
                    for state in ("FAILED", "TIMED_OUT", "BLOCKED", "CANCELLED")
                ),
                "pending_deliveries": delivery_statuses.get("PENDING", 0),
                "failed_deliveries": delivery_statuses.get("FAILED", 0),
                "open_escalations": sum(
                    escalation_statuses.get(status, 0)
                    for status in ("OPEN", "ACKNOWLEDGED")
                ),
                "active_deadline_watches": deadline_watch_statuses.get("ACTIVE", 0),
            },
        }

    def _count(self, values: Iterable[str]) -> dict[str, int]:
        return dict(sorted(Counter(value.upper() for value in values).items()))

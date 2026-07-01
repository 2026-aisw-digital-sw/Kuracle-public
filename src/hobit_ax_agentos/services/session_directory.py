from __future__ import annotations

from pathlib import Path

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


class SessionDirectoryService:
    def __init__(self, data_dir: str | Path) -> None:
        self.jobs = AsyncJobStore(data_dir)
        self.conversations = ConversationStore(data_dir)
        self.personas = PersonaStore(data_dir)
        self.plans = CoordinationPlanStore(data_dir)
        self.runs = RunStore(data_dir)
        self.deadline_watches = DeadlineWatchStore(data_dir)
        self.escalations = EscalationStore(data_dir)
        self.outbox = OutboxStore(data_dir)

    def list_sessions(self, limit: int = 50) -> dict:
        sessions: dict[str, dict] = {}

        for job in self.jobs.list_all():
            item = self._session(sessions, job.session_id)
            item["counts"]["async_jobs"] += 1
            item["users"].add(job.user_id)
            if job.status in {"QUEUED", "RUNNING"}:
                item["open_items"]["active_async_jobs"] += 1
            if job.status == "FAILED":
                item["open_items"]["failed_async_jobs"] += 1
            self._touch(item, job.updated_at)

        for turn in self.conversations.list_all():
            item = self._session(sessions, turn.session_id)
            item["counts"]["turns"] += 1
            item["users"].add(turn.user_id)
            self._touch(item, turn.created_at)

        for snapshot in self.personas.list_all():
            item = self._session(sessions, snapshot.session_id)
            item["counts"]["persona_snapshots"] += 1
            item["users"].add(snapshot.user_id)
            self._touch(item, snapshot.created_at)

        for plan in self.plans.list_all():
            item = self._session(sessions, plan.session_id)
            item["counts"]["plans"] += 1
            item["users"].add(plan.user_id)
            self._touch(item, plan.created_at)

        for run in self.runs.list_all():
            item = self._session(sessions, run.session_id)
            item["counts"]["runs"] += 1
            item["users"].add(run.user_id)
            if run.state in {"PENDING", "RUNNING", "BLOCKED"}:
                item["open_items"]["active_runs"] += 1
            self._touch(item, run.updated_at)

        for watch in self.deadline_watches.list_all():
            item = self._session(sessions, watch.session_id)
            item["counts"]["deadline_watches"] += 1
            item["users"].add(watch.user_id)
            if watch.status == "ACTIVE":
                item["open_items"]["active_deadline_watches"] += 1
            self._touch(item, watch.updated_at)

        for case in self.escalations.list_all():
            item = self._session(sessions, case.session_id)
            item["counts"]["escalations"] += 1
            item["users"].add(case.user_id)
            if case.status in {"OPEN", "ACKNOWLEDGED"}:
                item["open_items"]["open_escalations"] += 1
            self._touch(item, case.updated_at)

        for delivery in self.outbox.list_all():
            item = self._session(sessions, delivery.session_id)
            item["counts"]["outbox"] += 1
            item["users"].add(delivery.user_id)
            if delivery.status == "PENDING":
                item["open_items"]["pending_deliveries"] += 1
            self._touch(item, delivery.updated_at)

        items = []
        for item in sessions.values():
            item["users"] = sorted(item["users"])
            items.append(item)
        items.sort(key=lambda item: item["latest_activity_at"] or "", reverse=True)
        return {
            "count": len(items),
            "sessions": items[:limit],
        }

    def _session(self, sessions: dict[str, dict], session_id: str) -> dict:
        if session_id not in sessions:
            sessions[session_id] = {
                "session_id": session_id,
                "users": set(),
                "latest_activity_at": None,
                "counts": {
                    "turns": 0,
                    "async_jobs": 0,
                    "persona_snapshots": 0,
                    "plans": 0,
                    "runs": 0,
                    "deadline_watches": 0,
                    "escalations": 0,
                    "outbox": 0,
                },
                "open_items": {
                    "active_runs": 0,
                    "active_async_jobs": 0,
                    "failed_async_jobs": 0,
                    "active_deadline_watches": 0,
                    "open_escalations": 0,
                    "pending_deliveries": 0,
                },
            }
        return sessions[session_id]

    def _touch(self, item: dict, timestamp: str) -> None:
        if item["latest_activity_at"] is None or timestamp > item["latest_activity_at"]:
            item["latest_activity_at"] = timestamp

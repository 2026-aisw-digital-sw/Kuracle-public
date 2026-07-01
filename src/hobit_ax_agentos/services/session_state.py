from __future__ import annotations

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


class SessionStateService:
    def __init__(self, data_dir: str) -> None:
        self.jobs = AsyncJobStore(data_dir)
        self.conversations = ConversationStore(data_dir)
        self.personas = PersonaStore(data_dir)
        self.plans = CoordinationPlanStore(data_dir)
        self.runs = RunStore(data_dir)
        self.deadline_watches = DeadlineWatchStore(data_dir)
        self.escalations = EscalationStore(data_dir)
        self.outbox = OutboxStore(data_dir)

    def summary(self, session_id: str, limit: int = 10) -> dict:
        turns = self.conversations.list_by_session(session_id, limit=limit)
        jobs = self.jobs.list_by_session(session_id, limit=limit)
        plans = self.plans.list_by_session(session_id, limit=limit)
        runs = self.runs.list_by_session(session_id, limit=limit)
        watches = self.deadline_watches.list_by_session(session_id, limit=limit)
        deliveries = self.outbox.list_by_session(session_id, limit=limit)
        escalations = [
            case
            for case in self.escalations.list_all()
            if case.session_id == session_id
        ][-limit:]
        latest_persona = self.personas.latest(session_id)
        return {
            "session_id": session_id,
            "latest_persona": latest_persona.to_dict() if latest_persona else None,
            "counts": {
                "turns": len(self.conversations.list_by_session(session_id, limit=1000000)),
                "async_jobs": len(self.jobs.list_by_session(session_id, limit=1000000)),
                "plans": len(self.plans.list_by_session(session_id, limit=1000000)),
                "runs": len(self.runs.list_by_session(session_id, limit=1000000)),
                "deadline_watches": len(
                    self.deadline_watches.list_by_session(session_id, limit=1000000)
                ),
                "escalations": len(
                    [
                        case
                        for case in self.escalations.list_all()
                        if case.session_id == session_id
                    ]
                ),
                "outbox": len(self.outbox.list_by_session(session_id, limit=1000000)),
            },
            "recent": {
                "turns": [turn.to_dict() for turn in turns],
                "async_jobs": [job.to_dict() for job in jobs],
                "plans": [plan.to_dict() for plan in plans],
                "runs": [run.to_dict() for run in runs],
                "deadline_watches": [watch.to_dict() for watch in watches],
                "escalations": [case.to_dict() for case in escalations],
                "outbox": [delivery.to_dict() for delivery in deliveries],
            },
            "open_items": {
                "escalations": [
                    case.to_dict()
                    for case in escalations
                    if case.status in {"OPEN", "ACKNOWLEDGED"}
                ],
                "active_async_jobs": [
                    job.to_dict()
                    for job in jobs
                    if job.status in {"QUEUED", "RUNNING"}
                ],
                "failed_async_jobs": [
                    job.to_dict()
                    for job in jobs
                    if job.status == "FAILED"
                ],
                "pending_deliveries": [
                    delivery.to_dict()
                    for delivery in deliveries
                    if delivery.status == "PENDING"
                ],
                "active_deadline_watches": [
                    watch.to_dict()
                    for watch in watches
                    if watch.status == "ACTIVE"
                ],
            },
        }

    def timeline(self, session_id: str, limit: int = 50) -> dict:
        events: list[dict] = []
        for job in self.jobs.list_by_session(session_id, limit=1000000):
            events.append(
                self._event(
                    event_type=f"async_job.{job.status.lower()}",
                    occurred_at=job.updated_at,
                    record_id=job.job_id,
                    record=job.to_dict(),
                )
            )
        for turn in self.conversations.list_by_session(session_id, limit=1000000):
            events.append(
                self._event(
                    event_type=f"conversation.{turn.role.lower()}",
                    occurred_at=turn.created_at,
                    record_id=turn.turn_id,
                    record=turn.to_dict(),
                )
            )
        for snapshot in self.personas.list_by_session(session_id, limit=1000000):
            events.append(
                self._event(
                    event_type="persona.snapshot",
                    occurred_at=snapshot.created_at,
                    record_id=f"persona:{snapshot.created_at}",
                    record=snapshot.to_dict(),
                )
            )
        for plan in self.plans.list_by_session(session_id, limit=1000000):
            events.append(
                self._event(
                    event_type="coordination.plan",
                    occurred_at=plan.created_at,
                    record_id=plan.plan_id,
                    record=plan.to_dict(),
                )
            )
        for run in self.runs.list_by_session(session_id, limit=1000000):
            events.append(
                self._event(
                    event_type=f"run.{run.state.lower()}",
                    occurred_at=run.updated_at,
                    record_id=run.run_id,
                    record=run.to_dict(),
                )
            )
        for watch in self.deadline_watches.list_by_session(session_id, limit=1000000):
            events.append(
                self._event(
                    event_type=f"deadline_watch.{watch.status.lower()}",
                    occurred_at=watch.updated_at,
                    record_id=watch.watch_id,
                    record=watch.to_dict(),
                )
            )
        for case in self.escalations.list_all():
            if case.session_id != session_id:
                continue
            events.append(
                self._event(
                    event_type=f"escalation.{case.status.lower()}",
                    occurred_at=case.updated_at,
                    record_id=case.escalation_id,
                    record=case.to_dict(),
                )
            )
        for delivery in self.outbox.list_by_session(session_id, limit=1000000):
            events.append(
                self._event(
                    event_type=f"outbox.{delivery.status.lower()}",
                    occurred_at=delivery.updated_at,
                    record_id=delivery.delivery_id,
                    record=delivery.to_dict(),
                )
            )
        events.sort(key=lambda item: (item["occurred_at"], item["event_type"], item["record_id"]))
        return {
            "session_id": session_id,
            "count": len(events),
            "events": events[-limit:],
        }

    def _event(
        self,
        event_type: str,
        occurred_at: str,
        record_id: str,
        record: dict,
    ) -> dict:
        return {
            "occurred_at": occurred_at,
            "event_type": event_type,
            "record_id": record_id,
            "record": record,
        }

from __future__ import annotations

from pathlib import Path

from hobit_ax_agentos.storage import (
    ConversationStore,
    CoordinationPlanStore,
    EscalationStore,
    OutboxStore,
    PersonaStore,
    RunStore,
)


class RunTraceService:
    def __init__(self, data_dir: str | Path) -> None:
        self.conversations = ConversationStore(data_dir)
        self.personas = PersonaStore(data_dir)
        self.plans = CoordinationPlanStore(data_dir)
        self.runs = RunStore(data_dir)
        self.escalations = EscalationStore(data_dir)
        self.outbox = OutboxStore(data_dir)

    def trace(self, run_id: str, conversation_limit: int = 20) -> dict | None:
        run = self.runs.get(run_id)
        if run is None:
            return None

        plan = (
            self.plans.get(run.coordination_plan_id)
            if run.coordination_plan_id
            else None
        )
        session_turns = self.conversations.list_by_session(
            run.session_id,
            limit=conversation_limit,
        )
        deliveries = [
            delivery
            for delivery in self.outbox.list_all()
            if delivery.run_id == run_id or delivery.trace_id == run.trace_id
        ]
        escalations = [
            case
            for case in self.escalations.list_all()
            if case.run_id == run_id
            or (run.trace_id is not None and case.trace_id == run.trace_id)
        ]
        latest_persona = self.personas.latest(run.session_id)

        return {
            "run": run.to_dict(),
            "coordination_plan": plan.to_dict() if plan else None,
            "latest_persona": latest_persona.to_dict() if latest_persona else None,
            "lifecycle_events": run.run_summary.get("lifecycle_events", []),
            "worker_results": run.worker_results,
            "final": run.final,
            "run_summary": run.run_summary,
            "related": {
                "conversation_turns": [turn.to_dict() for turn in session_turns],
                "outbox": [delivery.to_dict() for delivery in deliveries],
                "escalations": [case.to_dict() for case in escalations],
            },
        }

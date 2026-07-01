from __future__ import annotations

import json
from pathlib import Path

from hobit_ax_agentos.services.session_state import SessionStateService
from hobit_ax_agentos.storage import (
    AsyncJobStore,
    ConversationStore,
    CoordinationPlanStore,
    DeadlineWatchStore,
    EscalationStore,
    IdempotencyStore,
    OutboxStore,
    PersonaStore,
    RunStore,
)


class MaintenanceService:
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
        self.idempotency = IdempotencyStore(self.data_dir)

    def storage_stats(self) -> dict:
        files = []
        for path in sorted(self.data_dir.glob("*.jsonl")):
            files.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "bytes": path.stat().st_size,
                    "lines": self._line_count(path),
                }
            )
        return {
            "data_dir": str(self.data_dir),
            "files": files,
            "counts": {
                "conversation_turns": len(self.conversations.list_all()),
                "async_jobs": len(self.jobs.list_all()),
                "persona_snapshots": len(self.personas.list_all()),
                "coordination_plans": len(self.plans.list_all()),
                "agent_runs": len(self.runs.list_all()),
                "deadline_watches": len(self.deadline_watches.list_all()),
                "escalations": len(self.escalations.list_all()),
                "outbox": len(self.outbox.list_all()),
                "idempotency_keys": len(self.idempotency.list_all()),
            },
        }

    def export_session(self, session_id: str, limit: int = 1000000) -> dict:
        return {
            "session_id": session_id,
            "summary": SessionStateService(str(self.data_dir)).summary(session_id, limit=limit),
            "records": {
                "async_jobs": [
                    item.to_dict()
                    for item in self.jobs.list_all()
                    if item.session_id == session_id
                ][-limit:],
                "conversation_turns": [
                    item.to_dict()
                    for item in self.conversations.list_by_session(session_id, limit=limit)
                ],
                "persona_snapshots": [
                    item.to_dict()
                    for item in self.personas.list_by_session(session_id, limit=limit)
                ],
                "coordination_plans": [
                    item.to_dict()
                    for item in self.plans.list_by_session(session_id, limit=limit)
                ],
                "agent_runs": [
                    item.to_dict()
                    for item in self.runs.list_by_session(session_id, limit=limit)
                ],
                "deadline_watches": [
                    item.to_dict()
                    for item in self.deadline_watches.list_by_session(session_id, limit=limit)
                ],
                "escalations": [
                    item.to_dict()
                    for item in self.escalations.list_all()
                    if item.session_id == session_id
                ][-limit:],
                "outbox": [
                    item.to_dict()
                    for item in self.outbox.list_by_session(session_id, limit=limit)
                ],
            },
        }

    def write_session_export(
        self,
        session_id: str,
        output_path: str | Path,
        limit: int = 1000000,
    ) -> dict:
        export = self.export_session(session_id, limit=limit)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "path": str(path),
            "session_id": session_id,
            "counts": {
                name: len(items)
                for name, items in export["records"].items()
            },
        }

    def _line_count(self, path: Path) -> int:
        return len(path.read_text(encoding="utf-8").splitlines())

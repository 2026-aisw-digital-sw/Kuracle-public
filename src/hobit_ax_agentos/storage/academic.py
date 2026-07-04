from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from hobit_ax_agentos.models import AcademicEvent


class AcademicEventStore:
    def __init__(self, root: Path | str = "data") -> None:
        self.root = Path(root)
        self.path = self.root / "academic_events.jsonl"
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, event: AcademicEvent) -> AcademicEvent:
        events = {e.event_id: e for e in self.list_all()}
        events[event.event_id] = event
        self._write_all(events.values())
        return event

    def get(self, event_id: str) -> AcademicEvent | None:
        return next((e for e in self.list_all() if e.event_id == event_id), None)

    def list_by_user(self, user_id: str, limit: int = 50) -> list[AcademicEvent]:
        events = [e for e in self.list_all() if e.user_id == user_id]
        return events[-limit:]

    def list_by_session(self, session_id: str, limit: int = 50) -> list[AcademicEvent]:
        events = [e for e in self.list_all() if e.session_id == session_id]
        return events[-limit:]

    def list_active(self, user_id: str | None = None) -> list[AcademicEvent]:
        return [
            e for e in self.list_all()
            if e.status == "ACTIVE" and (user_id is None or e.user_id == user_id)
        ]

    def complete(self, event_id: str) -> AcademicEvent | None:
        return self._set_status(event_id, "COMPLETED")

    def dismiss(self, event_id: str) -> AcademicEvent | None:
        return self._set_status(event_id, "DISMISSED")

    def list_all(self) -> list[AcademicEvent]:
        if not self.path.exists():
            return []
        events: list[AcademicEvent] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            events.append(AcademicEvent(**json.loads(line)))
        return events

    def _set_status(self, event_id: str, status: str) -> AcademicEvent | None:
        from hobit_ax_agentos.models import utc_now
        events = {e.event_id: e for e in self.list_all()}
        event = events.get(event_id)
        if event is None:
            return None
        event.status = status  # type: ignore[assignment]
        event.updated_at = utc_now()
        self._write_all(events.values())
        return event

    def _write_all(self, events: Iterable[AcademicEvent]) -> None:
        lines = [json.dumps(e.to_dict(), ensure_ascii=False) for e in events]
        self.path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

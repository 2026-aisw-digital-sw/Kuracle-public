from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Iterable

from hobit_ax_agentos.models import DeadlineWatch, utc_now


class DeadlineWatchStore:
    def __init__(self, root: Path | str = "data") -> None:
        self.root = Path(root)
        self.path = self.root / "deadline_watches.jsonl"
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, watch: DeadlineWatch) -> DeadlineWatch:
        watches = {item.watch_id: item for item in self.list_all()}
        watch.updated_at = utc_now()
        watches[watch.watch_id] = watch
        self._write_all(watches.values())
        return watch

    def get(self, watch_id: str) -> DeadlineWatch | None:
        return next((watch for watch in self.list_all() if watch.watch_id == watch_id), None)

    def list_by_session(self, session_id: str, limit: int = 50) -> list[DeadlineWatch]:
        watches = [watch for watch in self.list_all() if watch.session_id == session_id]
        return watches[-limit:]

    def list_active_due(self, today: date) -> list[DeadlineWatch]:
        due: list[DeadlineWatch] = []
        for watch in self.list_all():
            if watch.status != "ACTIVE":
                continue
            deadline = date.fromisoformat(watch.deadline)
            days_left = (deadline - today).days
            if days_left < 0 or days_left > watch.reminder_window_days:
                continue
            if watch.last_triggered_on == today.isoformat():
                continue
            due.append(watch)
        return due

    def mark_triggered(self, watch_id: str, triggered_on: date) -> DeadlineWatch:
        watch = self._require(watch_id)
        watch.last_triggered_on = triggered_on.isoformat()
        if date.fromisoformat(watch.deadline) <= triggered_on:
            watch.status = "COMPLETED"
        return self.save(watch)

    def list_all(self) -> list[DeadlineWatch]:
        if not self.path.exists():
            return []
        watches: list[DeadlineWatch] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            watches.append(DeadlineWatch(**json.loads(line)))
        return watches

    def _write_all(self, watches: Iterable[DeadlineWatch]) -> None:
        lines = [json.dumps(watch.to_dict(), ensure_ascii=False) for watch in watches]
        self.path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def _require(self, watch_id: str) -> DeadlineWatch:
        watch = self.get(watch_id)
        if watch is None:
            raise KeyError(watch_id)
        return watch

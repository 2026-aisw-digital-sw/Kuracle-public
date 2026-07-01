from __future__ import annotations

import json
from pathlib import Path

from hobit_ax_agentos.models import PersonaSnapshot


class PersonaStore:
    def __init__(self, root: Path | str = "data") -> None:
        self.root = Path(root)
        self.path = self.root / "persona_snapshots.jsonl"
        self.root.mkdir(parents=True, exist_ok=True)

    def append(self, snapshot: PersonaSnapshot) -> PersonaSnapshot:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(snapshot.to_dict(), ensure_ascii=False) + "\n")
        return snapshot

    def latest(self, session_id: str) -> PersonaSnapshot | None:
        snapshots = self.list_by_session(session_id, limit=1)
        return snapshots[0] if snapshots else None

    def list_by_session(self, session_id: str, limit: int = 50) -> list[PersonaSnapshot]:
        snapshots = [
            snapshot
            for snapshot in self.list_all()
            if snapshot.session_id == session_id
        ]
        return snapshots[-limit:]

    def list_all(self) -> list[PersonaSnapshot]:
        if not self.path.exists():
            return []
        snapshots: list[PersonaSnapshot] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            snapshots.append(PersonaSnapshot(**json.loads(line)))
        return snapshots

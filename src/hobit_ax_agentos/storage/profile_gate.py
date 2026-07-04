from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from hobit_ax_agentos.models import ProfileGateRecord


class ProfileGateStore:
    def __init__(self, root: Path | str = "data") -> None:
        self.root = Path(root)
        self.path = self.root / "profile_gates.jsonl"
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, record: ProfileGateRecord) -> ProfileGateRecord:
        records = {r.gate_id: r for r in self.list_all()}
        records[record.gate_id] = record
        self._write_all(records.values())
        return record

    def get(self, gate_id: str) -> ProfileGateRecord | None:
        return next((r for r in self.list_all() if r.gate_id == gate_id), None)

    def active_for_session(self, session_id: str) -> ProfileGateRecord | None:
        """Return the most recent WAITING gate for this session, if any."""
        waiting = [
            r for r in self.list_all()
            if r.session_id == session_id and r.status == "WAITING"
        ]
        return waiting[-1] if waiting else None

    def resolve(self, gate_id: str) -> ProfileGateRecord | None:
        return self._set_status(gate_id, "RESOLVED")

    def expire(self, gate_id: str) -> ProfileGateRecord | None:
        return self._set_status(gate_id, "EXPIRED")

    def increment_retry(self, gate_id: str) -> ProfileGateRecord | None:
        from hobit_ax_agentos.models import utc_now
        records = {r.gate_id: r for r in self.list_all()}
        record = records.get(gate_id)
        if record is None:
            return None
        record.retry_count += 1
        record.updated_at = utc_now()
        if record.retry_count >= record.max_retries:
            record.status = "EXPIRED"
        self._write_all(records.values())
        return record

    def list_all(self) -> list[ProfileGateRecord]:
        if not self.path.exists():
            return []
        records: list[ProfileGateRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            records.append(ProfileGateRecord(**json.loads(line)))
        return records

    def _set_status(self, gate_id: str, status: str) -> ProfileGateRecord | None:
        from hobit_ax_agentos.models import utc_now
        records = {r.gate_id: r for r in self.list_all()}
        record = records.get(gate_id)
        if record is None:
            return None
        record.status = status  # type: ignore[assignment]
        record.updated_at = utc_now()
        self._write_all(records.values())
        return record

    def _write_all(self, records: Iterable[ProfileGateRecord]) -> None:
        lines = [json.dumps(r.to_dict(), ensure_ascii=False) for r in records]
        self.path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from hobit_ax_agentos.models import utc_now


class IdempotencyStore:
    def __init__(self, root: Path | str = "data") -> None:
        self.root = Path(root)
        self.path = self.root / "idempotency_keys.jsonl"
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, key: str, run_id: str, session_id: str, user_id: str, channel: str) -> dict:
        records = {item["key"]: item for item in self.list_all()}
        records[key] = {
            "key": key,
            "run_id": run_id,
            "session_id": session_id,
            "user_id": user_id,
            "channel": channel,
            "updated_at": utc_now(),
            "created_at": records.get(key, {}).get("created_at") or utc_now(),
        }
        self._write_all(records.values())
        return records[key]

    def get(self, key: str) -> dict | None:
        return next((record for record in self.list_all() if record["key"] == key), None)

    def list_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        records: list[dict] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            records.append(json.loads(line))
        return records

    def _write_all(self, records: Iterable[dict]) -> None:
        lines = [json.dumps(record, ensure_ascii=False) for record in records]
        self.path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

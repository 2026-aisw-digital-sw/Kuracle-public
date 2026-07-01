from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from hobit_ax_agentos.models import UserProfileRecord, utc_now


class ProfileStore:
    """user_id 기준 upsert JSONL 저장소. 다른 storage/* 모듈과 동일한 패턴을 따른다."""

    def __init__(self, root: Path | str = "data") -> None:
        self.root = Path(root)
        self.path = self.root / "user_profiles.jsonl"
        self.root.mkdir(parents=True, exist_ok=True)

    def upsert(self, record: UserProfileRecord) -> UserProfileRecord:
        records = {item.user_id: item for item in self.list_all()}
        record.updated_at = utc_now()
        records[record.user_id] = record
        self._write_all(records.values())
        return record

    def get(self, user_id: str) -> UserProfileRecord | None:
        return next(
            (record for record in self.list_all() if record.user_id == user_id),
            None,
        )

    def list_all(self) -> list[UserProfileRecord]:
        if not self.path.exists():
            return []
        records: list[UserProfileRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            records.append(UserProfileRecord(**json.loads(line)))
        return records

    def _write_all(self, records: Iterable[UserProfileRecord]) -> None:
        lines = [json.dumps(record.to_dict(), ensure_ascii=False) for record in records]
        self.path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

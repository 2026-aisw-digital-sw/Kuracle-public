from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


class RetentionService:
    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)

    def prune(
        self,
        older_than_days: int,
        dry_run: bool = True,
        now: datetime | None = None,
    ) -> dict:
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=older_than_days)
        files = []
        total_removed = 0
        for path in sorted(self.data_dir.glob("*.jsonl")):
            result = self._prune_file(path, cutoff=cutoff, dry_run=dry_run)
            files.append(result)
            total_removed += result["remove_count"]
        return {
            "dry_run": dry_run,
            "older_than_days": older_than_days,
            "cutoff": cutoff.isoformat(),
            "remove_count": total_removed,
            "files": files,
        }

    def _prune_file(self, path: Path, cutoff: datetime, dry_run: bool) -> dict:
        keep_lines = []
        remove_count = 0
        keep_count = 0
        invalid_count = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                timestamp = self._record_timestamp(payload)
            except Exception:
                keep_lines.append(line)
                keep_count += 1
                invalid_count += 1
                continue
            if timestamp and timestamp < cutoff:
                remove_count += 1
                continue
            keep_lines.append(line)
            keep_count += 1

        if not dry_run:
            path.write_text(
                "\n".join(keep_lines) + ("\n" if keep_lines else ""),
                encoding="utf-8",
            )

        return {
            "name": path.name,
            "path": str(path),
            "keep_count": keep_count,
            "remove_count": remove_count,
            "invalid_count": invalid_count,
        }

    def _record_timestamp(self, payload: dict) -> datetime | None:
        value = payload.get("updated_at") or payload.get("created_at")
        if not value:
            return None
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

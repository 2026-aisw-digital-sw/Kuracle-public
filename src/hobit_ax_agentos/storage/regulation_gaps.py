from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from hobit_ax_agentos.models import RegulationGap


class RegulationGapStore:
    def __init__(self, root: Path | str = "data") -> None:
        self.root = Path(root)
        self.path = self.root / "regulation_gaps.jsonl"
        self.root.mkdir(parents=True, exist_ok=True)

    def upsert(self, issue_type: str, query: str, **kwargs) -> RegulationGap:
        """Increment frequency if an open gap with the same issue_type exists; else create."""
        from hobit_ax_agentos.models import utc_now
        gaps = {g.gap_id: g for g in self.list_all()}
        existing = next(
            (g for g in gaps.values() if g.issue_type == issue_type and g.status == "OPEN"),
            None,
        )
        if existing:
            existing.frequency += 1
            existing.updated_at = utc_now()
            if kwargs.get("escalation_id"):
                existing.escalation_id = kwargs["escalation_id"]
            self._write_all(gaps.values())
            return existing
        import uuid
        gap = RegulationGap(
            gap_id=f"gap_{uuid.uuid4().hex}",
            issue_type=issue_type,
            query=query,
            **{k: v for k, v in kwargs.items() if k in {
                "user_id", "session_id", "escalation_id",
            }},
        )
        gaps[gap.gap_id] = gap
        self._write_all(gaps.values())
        return gap

    def resolve(self, gap_id: str, resolution: str | None = None) -> RegulationGap | None:
        from hobit_ax_agentos.models import utc_now
        gaps = {g.gap_id: g for g in self.list_all()}
        gap = gaps.get(gap_id)
        if gap is None:
            return None
        gap.status = "RESOLVED"
        gap.resolution = resolution
        gap.updated_at = utc_now()
        self._write_all(gaps.values())
        return gap

    def get(self, gap_id: str) -> RegulationGap | None:
        return next((g for g in self.list_all() if g.gap_id == gap_id), None)

    def list_open(self) -> list[RegulationGap]:
        return [g for g in self.list_all() if g.status == "OPEN"]

    def list_all(self) -> list[RegulationGap]:
        if not self.path.exists():
            return []
        gaps: list[RegulationGap] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            gaps.append(RegulationGap(**json.loads(line)))
        return gaps

    def _write_all(self, gaps: Iterable[RegulationGap]) -> None:
        lines = [json.dumps(g.to_dict(), ensure_ascii=False) for g in gaps]
        self.path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

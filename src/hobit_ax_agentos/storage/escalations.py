from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from hobit_ax_agentos.models import EscalationCase, utc_now


class EscalationStore:
    def __init__(self, root: Path | str = "data") -> None:
        self.root = Path(root)
        self.path = self.root / "escalations.jsonl"
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, case: EscalationCase) -> EscalationCase:
        cases = {item.escalation_id: item for item in self.list_all()}
        case.updated_at = utc_now()
        cases[case.escalation_id] = case
        self._write_all(cases.values())
        return case

    def get(self, escalation_id: str) -> EscalationCase | None:
        return next(
            (case for case in self.list_all() if case.escalation_id == escalation_id),
            None,
        )

    def acknowledge(self, escalation_id: str) -> EscalationCase:
        case = self._require(escalation_id)
        case.status = "ACKNOWLEDGED"
        return self.save(case)

    def assign(self, escalation_id: str, assignee: str) -> EscalationCase:
        case = self._require(escalation_id)
        case.assignee = assignee
        if case.status == "OPEN":
            case.status = "ACKNOWLEDGED"
        return self.save(case)

    def add_note(
        self,
        escalation_id: str,
        author: str,
        text: str,
        visibility: str = "internal",
    ) -> EscalationCase:
        case = self._require(escalation_id)
        case.notes.append(
            {
                "author": author,
                "text": text,
                "visibility": visibility,
                "created_at": utc_now(),
            }
        )
        return self.save(case)

    def resolve(
        self,
        escalation_id: str,
        signal: str = "neutral",
        comment: str | None = None,
    ) -> EscalationCase:
        case = self._require(escalation_id)
        case.status = "RESOLVED"
        case.resolution_signal = signal
        case.resolution_comment = comment
        return self.save(case)

    def list_all(self) -> list[EscalationCase]:
        if not self.path.exists():
            return []
        cases: list[EscalationCase] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            cases.append(EscalationCase(**json.loads(line)))
        return cases

    def _write_all(self, cases: Iterable[EscalationCase]) -> None:
        lines = [json.dumps(case.to_dict(), ensure_ascii=False) for case in cases]
        self.path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def _require(self, escalation_id: str) -> EscalationCase:
        case = self.get(escalation_id)
        if case is None:
            raise KeyError(escalation_id)
        return case

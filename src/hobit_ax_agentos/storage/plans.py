from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from hobit_ax_agentos.models import CoordinationPlan


class CoordinationPlanStore:
    def __init__(self, root: Path | str = "data") -> None:
        self.root = Path(root)
        self.path = self.root / "coordination_plans.jsonl"
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, plan: CoordinationPlan) -> CoordinationPlan:
        plans = {item.plan_id: item for item in self.list_all()}
        plans[plan.plan_id] = plan
        self._write_all(plans.values())
        return plan

    def get(self, plan_id: str) -> CoordinationPlan | None:
        return next((plan for plan in self.list_all() if plan.plan_id == plan_id), None)

    def list_by_session(self, session_id: str, limit: int = 50) -> list[CoordinationPlan]:
        plans = [plan for plan in self.list_all() if plan.session_id == session_id]
        return plans[-limit:]

    def list_all(self) -> list[CoordinationPlan]:
        if not self.path.exists():
            return []
        plans: list[CoordinationPlan] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            plans.append(CoordinationPlan(**json.loads(line)))
        return plans

    def _write_all(self, plans: Iterable[CoordinationPlan]) -> None:
        lines = [json.dumps(plan.to_dict(), ensure_ascii=False) for plan in plans]
        self.path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

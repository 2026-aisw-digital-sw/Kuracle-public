from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from hobit_ax_agentos.models import (
    AgentRunRecord,
    AsyncJobRecord,
    ConversationTurn,
    CoordinationPlan,
    DeadlineWatch,
    EscalationCase,
    OutboundDelivery,
    PersonaSnapshot,
)
from hobit_ax_agentos.storage import (
    CoordinationPlanStore,
    RunStore,
)


@dataclass(frozen=True, slots=True)
class AuditTarget:
    name: str
    filename: str
    loader: Callable[..., Any]


class StorageAuditService:
    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)

    def audit(self) -> dict:
        issues = []
        counts: dict[str, int] = {}
        for target in self._targets():
            file_issues, count = self._audit_file(target)
            issues.extend(file_issues)
            counts[target.name] = count
        issues.extend(self._audit_references())
        return {
            "status": "ok" if not issues else "degraded",
            "data_dir": str(self.data_dir),
            "counts": counts,
            "issues": issues,
        }

    def _audit_file(self, target: AuditTarget) -> tuple[list[dict], int]:
        path = self.data_dir / target.filename
        if not path.exists():
            return [], 0
        issues = []
        count = 0
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                issues.append(
                    self._issue(
                        "ERROR",
                        "invalid_json",
                        target.name,
                        line_no,
                        f"JSONDecodeError: {exc}",
                    )
                )
                continue
            try:
                target.loader(**payload)
            except Exception as exc:
                issues.append(
                    self._issue(
                        "ERROR",
                        "invalid_record",
                        target.name,
                        line_no,
                        f"{type(exc).__name__}: {exc}",
                    )
                )
                continue
            count += 1
        return issues, count

    def _audit_references(self) -> list[dict]:
        issues = []
        runs = RunStore(self.data_dir).list_all()
        plans = {plan.plan_id for plan in CoordinationPlanStore(self.data_dir).list_all()}
        run_ids = {run.run_id for run in runs}
        for run in runs:
            if run.coordination_plan_id and run.coordination_plan_id not in plans:
                issues.append(
                    self._issue(
                        "WARN",
                        "missing_coordination_plan",
                        "agent_runs",
                        None,
                        f"run {run.run_id} references missing plan {run.coordination_plan_id}",
                        record_id=run.run_id,
                    )
                )
        for target in (
            AuditTarget("async_jobs", "async_jobs.jsonl", AsyncJobRecord),
            AuditTarget("outbox", "outbox.jsonl", OutboundDelivery),
            AuditTarget("escalations", "escalations.jsonl", EscalationCase),
            AuditTarget("idempotency_keys", "idempotency_keys.jsonl", self._load_idempotency),
        ):
            for record in self._load_valid_records(target):
                run_id = record.get("run_id") if isinstance(record, dict) else getattr(record, "run_id", None)
                if run_id and run_id not in run_ids:
                    issues.append(
                        self._issue(
                            "WARN",
                            "missing_run",
                            target.name,
                            None,
                            f"{target.name} record references missing run {run_id}",
                            record_id=(
                                record.get("key")
                                if isinstance(record, dict)
                                else getattr(record, "delivery_id", None)
                                or getattr(record, "escalation_id", None)
                                or getattr(record, "job_id", None)
                            ),
                        )
                    )
        return issues

    def _load_valid_records(self, target: AuditTarget) -> list[Any]:
        path = self.data_dir / target.filename
        if not path.exists():
            return []
        records = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                records.append(target.loader(**json.loads(line)))
            except Exception:
                continue
        return records

    def _targets(self) -> list[AuditTarget]:
        return [
            AuditTarget("conversation_turns", "conversation_turns.jsonl", ConversationTurn),
            AuditTarget("async_jobs", "async_jobs.jsonl", AsyncJobRecord),
            AuditTarget("persona_snapshots", "persona_snapshots.jsonl", PersonaSnapshot),
            AuditTarget("coordination_plans", "coordination_plans.jsonl", CoordinationPlan),
            AuditTarget("agent_runs", "agent_runs.jsonl", AgentRunRecord),
            AuditTarget("deadline_watches", "deadline_watches.jsonl", DeadlineWatch),
            AuditTarget("escalations", "escalations.jsonl", EscalationCase),
            AuditTarget("outbox", "outbox.jsonl", OutboundDelivery),
            AuditTarget("idempotency_keys", "idempotency_keys.jsonl", self._load_idempotency),
        ]

    def _load_idempotency(self, **payload) -> dict:
        required = {"key", "run_id", "session_id", "user_id", "channel"}
        missing = sorted(required - set(payload))
        if missing:
            raise ValueError(f"missing required fields: {missing}")
        return payload

    def _issue(
        self,
        severity: str,
        issue_type: str,
        store: str,
        line_no: int | None,
        message: str,
        record_id: str | None = None,
    ) -> dict:
        return {
            "severity": severity,
            "issue_type": issue_type,
            "store": store,
            "line_no": line_no,
            "record_id": record_id,
            "message": message,
        }

from __future__ import annotations

from pathlib import Path

from hobit_ax_agentos.models import utc_now
from hobit_ax_agentos.storage import EscalationStore, OutboxStore, RunStore


CANCELLABLE_STATES = {"PENDING", "RUNNING", "BLOCKED"}


class RunControlService:
    def __init__(self, data_dir: str | Path) -> None:
        self.runs = RunStore(data_dir)
        self.outbox = OutboxStore(data_dir)
        self.escalations = EscalationStore(data_dir)

    def cancel(self, run_id: str, reason: str | None = None) -> dict | None:
        run = self.runs.get(run_id)
        if run is None:
            return None
        if run.state not in CANCELLABLE_STATES:
            raise ValueError(f"run state is not cancellable: {run.state}")

        cancelled_at = utc_now()
        run_summary = {
            **run.run_summary,
            "state": "CANCELLED",
            "cancelled_at": cancelled_at,
            "cancel_reason": reason or "operator_cancelled",
            "previous_state": run.state,
        }
        cancelled_run = self.runs.complete(
            run_id=run.run_id,
            state="CANCELLED",
            trace_id=run.trace_id,
            final=run.final,
            run_summary=run_summary,
        )
        failed_deliveries = []
        for delivery in self.outbox.list_all():
            if delivery.status != "PENDING":
                continue
            if delivery.run_id != run_id and (
                run.trace_id is None or delivery.trace_id != run.trace_id
            ):
                continue
            failed_deliveries.append(
                self.outbox.mark_failed(
                    delivery.delivery_id,
                    error=f"run_cancelled:{run_id}",
                ).to_dict()
            )

        resolved_escalations = []
        for case in self.escalations.list_all():
            if case.status == "RESOLVED":
                continue
            if case.run_id != run_id and (
                run.trace_id is None or case.trace_id != run.trace_id
            ):
                continue
            case.review_package = {
                **case.review_package,
                "cancelled_by_run_id": run_id,
                "cancelled_at": cancelled_at,
                "cancel_reason": reason or "operator_cancelled",
            }
            case.status = "RESOLVED"
            resolved_escalations.append(self.escalations.save(case).to_dict())

        return {
            "run": cancelled_run.to_dict(),
            "cancelled_at": cancelled_at,
            "failed_deliveries": failed_deliveries,
            "resolved_escalations": resolved_escalations,
        }

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from hobit_ax_agentos.agents.trigger import TriggerAgent
from hobit_ax_agentos.models import ServiceResult
from hobit_ax_agentos.services.trigger_dispatcher import TriggerDispatcher
from hobit_ax_agentos.storage import DeadlineWatchStore


@dataclass(slots=True)
class FakeRunner:
    seen: list[dict]

    def run_message(self, message, timeout_seconds: float = 120.0) -> ServiceResult:
        self.seen.append(
            {
                "text": message.text,
                "channel": message.channel,
                "timeout_seconds": timeout_seconds,
                "metadata": message.metadata,
            }
        )
        return ServiceResult(
            run_id="run_1",
            trace_id="trace_1",
            final={"response": "ok"},
            run_summary={"state": "COMPLETED"},
            worker_results=[],
        )


def test_trigger_dispatcher_runs_due_deadline_events(tmp_path) -> None:
    seen: list[dict] = []
    trigger_agent = TriggerAgent(watch_store=DeadlineWatchStore(tmp_path))
    trigger_agent.register_deadline_watch(
        user_id="user_1",
        session_id="session_1",
        issue_type="academic.plural_major",
        deadline=date(2026, 7, 5),
    )
    dispatcher = TriggerDispatcher(
        trigger_agent=trigger_agent,
        runner_factory=lambda: FakeRunner(seen),
    )

    dispatches = dispatcher.dispatch_due_deadline_events(
        today=date(2026, 7, 1),
        timeout_seconds=3.0,
    )
    duplicate_dispatches = dispatcher.dispatch_due_deadline_events(
        today=date(2026, 7, 1),
        timeout_seconds=3.0,
    )

    assert len(dispatches) == 1
    assert dispatches[0]["result"]["run_id"] == "run_1"
    assert seen[0]["channel"] == "trigger"
    assert seen[0]["timeout_seconds"] == 3.0
    assert seen[0]["metadata"]["watch_id"]
    assert duplicate_dispatches == []

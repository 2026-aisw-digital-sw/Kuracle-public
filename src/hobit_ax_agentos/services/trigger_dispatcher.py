from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Callable

from hobit_ax_agentos.agentos.runner import ServiceRunner
from hobit_ax_agentos.agents.trigger import TriggerAgent
from hobit_ax_agentos.config import AppSettings
from hobit_ax_agentos.models import ServiceResult, TriggerEvent


RunnerFactory = Callable[[], ServiceRunner]


class TriggerDispatcher:
    def __init__(
        self,
        settings: AppSettings | None = None,
        trigger_agent: TriggerAgent | None = None,
        runner_factory: RunnerFactory | None = None,
    ) -> None:
        self.settings = settings or AppSettings()
        self.trigger_agent = trigger_agent or TriggerAgent(self.settings)
        self.runner_factory = runner_factory or (lambda: ServiceRunner(settings=self.settings))

    def due_deadline_events(self, today: date | None = None) -> list[TriggerEvent]:
        return self.trigger_agent.due_deadline_events(today=today)

    def dispatch_due_deadline_events(
        self,
        today: date | None = None,
        timeout_seconds: float = 120.0,
    ) -> list[dict]:
        return self._dispatch(self.due_deadline_events(today=today), timeout_seconds)

    def regulation_change_events(self) -> list[TriggerEvent]:
        return self.trigger_agent.regulation_change_events()

    def dispatch_regulation_change_events(self, timeout_seconds: float = 120.0) -> list[dict]:
        return self._dispatch(self.regulation_change_events(), timeout_seconds)

    def _dispatch(self, events: list[TriggerEvent], timeout_seconds: float) -> list[dict]:
        dispatches: list[dict] = []
        for event in events:
            result = self.runner_factory().run_message(
                event.message,
                timeout_seconds=timeout_seconds,
            )
            dispatches.append(
                {
                    "trigger": event.to_dict(),
                    "result": self._result_to_dict(result),
                }
            )
        return dispatches

    def _result_to_dict(self, result: ServiceResult) -> dict:
        return asdict(result)

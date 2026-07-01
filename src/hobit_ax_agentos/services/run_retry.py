from __future__ import annotations

from pathlib import Path
from typing import Callable

from hobit_ax_agentos.agentos.runner import ServiceRunner
from hobit_ax_agentos.config import AppSettings
from hobit_ax_agentos.models import ConversationTurn, IncomingMessage, ServiceResult
from hobit_ax_agentos.storage import ConversationStore, RunStore


RETRYABLE_STATES = {"FAILED", "TIMED_OUT", "BLOCKED", "CANCELLED"}


class RunRetryService:
    def __init__(
        self,
        settings: AppSettings | None = None,
        runner_factory: Callable[[AppSettings], ServiceRunner] | None = None,
    ) -> None:
        self.settings = settings or AppSettings()
        self.runs = RunStore(self.settings.data_dir)
        self.conversations = ConversationStore(self.settings.data_dir)
        self.runner_factory = runner_factory or (lambda settings: ServiceRunner(settings=settings))

    def retry(self, run_id: str, timeout_seconds: float = 120.0) -> dict | None:
        run = self.runs.get(run_id)
        if run is None:
            return None
        if run.state not in RETRYABLE_STATES:
            raise ValueError(f"run state is not retryable: {run.state}")

        source_turn = self._source_user_turn(run.session_id, run.created_at)
        if source_turn is None:
            raise LookupError(f"source user turn not found for run: {run_id}")

        metadata = dict(source_turn.metadata)
        metadata.pop("persona", None)
        metadata["retry"] = {
            "retry_of_run_id": run.run_id,
            "retry_of_trace_id": run.trace_id,
            "source_turn_id": source_turn.turn_id,
            "source_run_state": run.state,
        }
        message = IncomingMessage(
            channel=source_turn.channel,
            user_id=source_turn.user_id,
            text=source_turn.text,
            session_id=source_turn.session_id,
            metadata=metadata,
        )
        result = self.runner_factory(self.settings).run_message(
            message,
            timeout_seconds=timeout_seconds,
        )
        return {
            "retry_of_run_id": run_id,
            "source_turn": source_turn.to_dict(),
            "result": self._result_to_dict(result),
        }

    def _source_user_turn(self, session_id: str, run_created_at: str) -> ConversationTurn | None:
        candidates = [
            turn
            for turn in self.conversations.list_by_session(session_id, limit=1000000)
            if turn.role == "USER" and turn.created_at <= run_created_at
        ]
        return candidates[-1] if candidates else None

    def _result_to_dict(self, result: ServiceResult) -> dict:
        return {
            "run_id": result.run_id,
            "trace_id": result.trace_id,
            "final": result.final,
            "run_summary": result.run_summary,
            "worker_results": result.worker_results,
        }

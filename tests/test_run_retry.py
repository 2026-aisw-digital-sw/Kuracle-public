from __future__ import annotations

import pytest

from hobit_ax_agentos.config import AppSettings
from hobit_ax_agentos.models import AgentRunRecord, IncomingMessage, ServiceResult
from hobit_ax_agentos.services.run_retry import RunRetryService
from hobit_ax_agentos.storage import ConversationStore, RunStore


class CapturingRunner:
    def __init__(self) -> None:
        self.messages = []
        self.timeouts = []

    def run_message(self, message: IncomingMessage, timeout_seconds: float = 120.0) -> ServiceResult:
        self.messages.append(message)
        self.timeouts.append(timeout_seconds)
        return ServiceResult(
            run_id="run_retry_1",
            trace_id="trace_retry_1",
            final={"response": "retried"},
            run_summary={"state": "COMPLETED"},
            worker_results=[],
        )


def test_run_retry_replays_source_user_turn(tmp_path) -> None:
    settings = AppSettings(data_dir=tmp_path)
    runner = CapturingRunner()
    turn = ConversationStore(tmp_path).append_message(
        IncomingMessage(
            "api",
            "user_1",
            "broken question",
            "session_1",
            metadata={"persona": {"stale": True}, "raw": {"source": "test"}},
        )
    )
    RunStore(tmp_path).save(
        AgentRunRecord(
            run_id="run_failed",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            state="FAILED",
            trace_id="trace_failed",
        )
    )

    result = RunRetryService(
        settings,
        runner_factory=lambda _: runner,
    ).retry("run_failed", timeout_seconds=3.5)

    assert result["retry_of_run_id"] == "run_failed"
    assert result["source_turn"]["turn_id"] == turn.turn_id
    assert result["result"]["run_id"] == "run_retry_1"
    assert runner.timeouts == [3.5]
    assert runner.messages[0].text == "broken question"
    assert "persona" not in runner.messages[0].metadata
    assert runner.messages[0].metadata["raw"] == {"source": "test"}
    assert runner.messages[0].metadata["retry"] == {
        "retry_of_run_id": "run_failed",
        "retry_of_trace_id": "trace_failed",
        "source_turn_id": turn.turn_id,
        "source_run_state": "FAILED",
    }


def test_run_retry_rejects_completed_run(tmp_path) -> None:
    settings = AppSettings(data_dir=tmp_path)
    ConversationStore(tmp_path).append_message(
        IncomingMessage("api", "user_1", "done question", "session_1")
    )
    RunStore(tmp_path).save(
        AgentRunRecord(
            run_id="run_done",
            session_id="session_1",
            user_id="user_1",
            channel="api",
            state="COMPLETED",
        )
    )

    with pytest.raises(ValueError, match="not retryable"):
        RunRetryService(settings, runner_factory=lambda _: CapturingRunner()).retry("run_done")


def test_run_retry_returns_none_for_missing_run(tmp_path) -> None:
    assert RunRetryService(AppSettings(data_dir=tmp_path)).retry("missing") is None

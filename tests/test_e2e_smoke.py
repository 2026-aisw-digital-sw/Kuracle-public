from __future__ import annotations

from hobit_ax_agentos.config import AppSettings
from hobit_ax_agentos.models import AgentRunRecord, ServiceResult
from hobit_ax_agentos.services.e2e_smoke import E2ESmokeService
from hobit_ax_agentos.storage import OutboxStore, RunStore


class RecordingRunner:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def run_message(self, message, timeout_seconds: float = 120.0) -> ServiceResult:
        RunStore(self.settings.data_dir).save(
            AgentRunRecord(
                run_id="run_smoke_1",
                trace_id="trace_smoke_1",
                session_id=message.session_id,
                user_id=message.user_id,
                channel=message.channel,
                state="COMPLETED",
                final={"response": "smoke ok"},
                run_summary={"state": "COMPLETED"},
            )
        )
        OutboxStore(self.settings.data_dir).append_response(
            session_id=message.session_id,
            user_id=message.user_id,
            channel=message.channel,
            text="smoke ok",
            run_id="run_smoke_1",
            trace_id="trace_smoke_1",
        )
        return ServiceResult(
            run_id="run_smoke_1",
            trace_id="trace_smoke_1",
            final={"response": "smoke ok"},
            run_summary={"state": "COMPLETED"},
            worker_results=[],
        )


class NoOutboxRunner:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def run_message(self, message, timeout_seconds: float = 120.0) -> ServiceResult:
        RunStore(self.settings.data_dir).save(
            AgentRunRecord(
                run_id="run_smoke_2",
                session_id=message.session_id,
                user_id=message.user_id,
                channel=message.channel,
                state="COMPLETED",
            )
        )
        return ServiceResult(
            run_id="run_smoke_2",
            trace_id=None,
            final={"response": "missing outbox"},
            run_summary={"state": "COMPLETED"},
            worker_results=[],
        )


def test_e2e_smoke_service_reports_ok(tmp_path) -> None:
    settings = AppSettings(data_dir=tmp_path)

    report = E2ESmokeService(
        settings=settings,
        runner_factory=lambda settings: RecordingRunner(settings),
    ).run(query="hello", render_channel="web")

    assert report["status"] == "ok"
    assert [step["name"] for step in report["steps"]] == [
        "graph_preview",
        "service_runner",
        "run_record",
        "outbox_delivery",
        "delivery_render",
    ]
    assert report["result"]["run_id"] == "run_smoke_1"
    assert report["rendered_delivery"]["channel"] == "web"
    assert report["rendered_delivery"]["payload"]["message"]["text"] == "smoke ok"


def test_e2e_smoke_service_reports_degraded_when_outbox_missing(tmp_path) -> None:
    settings = AppSettings(data_dir=tmp_path)

    report = E2ESmokeService(
        settings=settings,
        runner_factory=lambda settings: NoOutboxRunner(settings),
    ).run(query="hello")

    assert report["status"] == "degraded"
    assert report["steps"][-1]["name"] == "outbox_delivery"
    assert report["steps"][-1]["ok"] is False
    assert "outbox delivery not found" in report["steps"][-1]["message"]

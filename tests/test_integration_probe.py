from __future__ import annotations

import sys
from types import ModuleType

from hobit_ax_agentos.config import AppSettings
from hobit_ax_agentos.services import integration_probe
from hobit_ax_agentos.services.integration_probe import IntegrationProbeService


class HealthyClient:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def health(self) -> dict:
        return {"status": "ok"}


class BrokenClient:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def health(self) -> dict:
        raise ConnectionError("kernel offline")


class HealthyAdapter:
    def __init__(self, settings) -> None:
        self.settings = settings

    def _build_supervisor(self):
        return object()

    def run_supervisor(self, query: str, profile: dict | None = None, session_id: str | None = None) -> dict:
        return {
            "workflow_status": "ANSWERED",
            "grounded_answer": {"summary": f"answered: {query}"},
        }


class BrokenAdapter:
    def __init__(self, settings) -> None:
        self.settings = settings

    def _build_supervisor(self):
        raise RuntimeError("supervisor missing")

    def run_supervisor(self, query: str, profile: dict | None = None, session_id: str | None = None) -> dict:
        return {
            "workflow_status": "ESCALATED",
            "grounded_answer": {"summary": "needs review"},
            "adapter_error": {"type": "RuntimeError", "message": "query failed"},
        }


def _install_fake_modules(monkeypatch, client_cls=HealthyClient) -> None:
    sdk = ModuleType("agentos_sdk")
    sdk.AgentOSClient = client_cls
    rag = ModuleType("regulation_rag")
    workers = ModuleType("regulation_rag.workers")
    supervisor = ModuleType("regulation_rag.workers.supervisor")
    monkeypatch.setitem(sys.modules, "agentos_sdk", sdk)
    monkeypatch.setitem(sys.modules, "regulation_rag", rag)
    monkeypatch.setitem(sys.modules, "regulation_rag.workers", workers)
    monkeypatch.setitem(sys.modules, "regulation_rag.workers.supervisor", supervisor)


def test_integration_probe_reports_ok(monkeypatch, tmp_path) -> None:
    _install_fake_modules(monkeypatch)
    monkeypatch.setattr(integration_probe, "RegulationRagAdapter", HealthyAdapter)

    report = IntegrationProbeService(AppSettings(data_dir=tmp_path)).report(
        rag_query="double major"
    )

    assert report["status"] == "ok"
    by_name = {probe["name"]: probe for probe in report["probes"]}
    assert by_name["agentos_kernel_health"]["ok"] is True
    assert by_name["regulation_rag_import"]["ok"] is True
    assert by_name["regulation_rag_supervisor_build"]["ok"] is True
    assert by_name["regulation_rag_query"]["payload"]["summary"] == "answered: double major"


def test_integration_probe_reports_degraded(monkeypatch, tmp_path) -> None:
    _install_fake_modules(monkeypatch, client_cls=BrokenClient)
    monkeypatch.setattr(integration_probe, "RegulationRagAdapter", BrokenAdapter)

    report = IntegrationProbeService(AppSettings(data_dir=tmp_path)).report()

    assert report["status"] == "degraded"
    by_name = {probe["name"]: probe for probe in report["probes"]}
    assert by_name["agentos_kernel_health"]["ok"] is False
    assert "kernel offline" in by_name["agentos_kernel_health"]["message"]
    assert by_name["regulation_rag_supervisor_build"]["ok"] is False
    assert by_name["regulation_rag_query"]["ok"] is False

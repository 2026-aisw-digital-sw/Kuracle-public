from __future__ import annotations

from time import perf_counter
from typing import Any

from hobit_ax_agentos.adapters.regulation_rag import RegulationRagAdapter
from hobit_ax_agentos.config import AppSettings, bootstrap_local_dependencies


class IntegrationProbeService:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings()

    def report(self, rag_query: str = "복수전공 신청 기간 알려줘") -> dict:
        bootstrap_local_dependencies(self.settings)
        probes = [
            self.kernel_health(),
            self.regulation_rag_import(),
            self.regulation_rag_supervisor_build(),
            self.regulation_rag_query(rag_query),
        ]
        return {
            "status": "ok" if all(probe["ok"] for probe in probes) else "degraded",
            "kernel_base_url": self.settings.kernel_base_url,
            "regulation_rag_path": str(self.settings.regulation_rag_path),
            "probes": probes,
        }

    def kernel_health(self) -> dict:
        started = perf_counter()
        try:
            from agentos_sdk import AgentOSClient

            payload = AgentOSClient(
                base_url=self.settings.kernel_base_url,
                api_token=self.settings.api_token,
                timeout=2.0,
            ).health()
        except Exception as exc:
            return self._probe(
                name="agentos_kernel_health",
                ok=False,
                started=started,
                message=f"{type(exc).__name__}: {exc}",
            )
        return self._probe(
            name="agentos_kernel_health",
            ok=True,
            started=started,
            message="healthy",
            payload=payload,
        )

    def regulation_rag_import(self) -> dict:
        started = perf_counter()
        try:
            import regulation_rag  # noqa: F401
            import regulation_rag.workers.supervisor  # noqa: F401
        except Exception as exc:
            return self._probe(
                name="regulation_rag_import",
                ok=False,
                started=started,
                message=f"{type(exc).__name__}: {exc}",
            )
        return self._probe(
            name="regulation_rag_import",
            ok=True,
            started=started,
            message="importable",
        )

    def regulation_rag_supervisor_build(self) -> dict:
        started = perf_counter()
        try:
            RegulationRagAdapter(self.settings)._build_supervisor()
        except Exception as exc:
            return self._probe(
                name="regulation_rag_supervisor_build",
                ok=False,
                started=started,
                message=f"{type(exc).__name__}: {exc}",
            )
        return self._probe(
            name="regulation_rag_supervisor_build",
            ok=True,
            started=started,
            message="supervisor_buildable",
        )

    def regulation_rag_query(self, query: str) -> dict:
        started = perf_counter()
        try:
            result = RegulationRagAdapter(self.settings).run_supervisor(query)
        except Exception as exc:
            return self._probe(
                name="regulation_rag_query",
                ok=False,
                started=started,
                message=f"{type(exc).__name__}: {exc}",
            )
        adapter_error = result.get("adapter_error")
        return self._probe(
            name="regulation_rag_query",
            ok=adapter_error is None,
            started=started,
            message=(
                "query_completed"
                if adapter_error is None
                else f"{adapter_error.get('type')}: {adapter_error.get('message')}"
            ),
            payload={
                "workflow_status": result.get("workflow_status"),
                "has_adapter_error": adapter_error is not None,
                "summary": (result.get("grounded_answer") or {}).get("summary"),
            },
        )

    def _probe(
        self,
        name: str,
        ok: bool,
        started: float,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> dict:
        return {
            "name": name,
            "kind": "integration_probe",
            "ok": ok,
            "elapsed_ms": round((perf_counter() - started) * 1000, 2),
            "message": message,
            "payload": payload or {},
        }

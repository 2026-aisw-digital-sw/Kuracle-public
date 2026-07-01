from __future__ import annotations

from time import perf_counter
from typing import Callable

from hobit_ax_agentos.agentos.runner import ServiceRunner
from hobit_ax_agentos.config import AppSettings
from hobit_ax_agentos.models import IncomingMessage, ServiceResult
from hobit_ax_agentos.services.delivery_renderer import DeliveryRenderer
from hobit_ax_agentos.storage import OutboxStore, RunStore


RunnerFactory = Callable[[AppSettings], ServiceRunner]


class E2ESmokeService:
    def __init__(
        self,
        settings: AppSettings | None = None,
        runner_factory: RunnerFactory | None = None,
    ) -> None:
        self.settings = settings or AppSettings()
        self.runner_factory = runner_factory or (lambda settings: ServiceRunner(settings=settings))

    def run(
        self,
        query: str = "double major application deadline",
        channel: str = "api",
        user_id: str | None = None,
        session_id: str | None = None,
        timeout_seconds: float = 120.0,
        render_channel: str | None = None,
    ) -> dict:
        started = perf_counter()
        message = IncomingMessage(
            channel=channel,
            user_id=user_id or self.settings.default_user_id,
            text=query,
            session_id=session_id or self.settings.default_session_id,
            metadata={"smoke_test": True},
        )
        steps: list[dict] = []

        graph = self._step(
            steps,
            name="graph_preview",
            fn=lambda: ServiceRunner(settings=self.settings).dry_run_graph(message),
        )
        if graph is None:
            return self._report(started, steps, message)

        result = self._step(
            steps,
            name="service_runner",
            fn=lambda: self.runner_factory(self.settings).run_message(
                message,
                timeout_seconds=timeout_seconds,
            ),
        )
        if result is None:
            return self._report(started, steps, message)

        run_record = self._step(
            steps,
            name="run_record",
            fn=lambda: self._require_run(result),
        )
        if run_record is None:
            return self._report(started, steps, message, result=result)

        delivery = self._step(
            steps,
            name="outbox_delivery",
            fn=lambda: self._require_delivery(result),
        )
        rendered = None
        if delivery is not None:
            rendered = self._step(
                steps,
                name="delivery_render",
                fn=lambda: DeliveryRenderer(
                    outbox_store=OutboxStore(self.settings.data_dir)
                ).render(delivery, channel=render_channel),
            )

        return self._report(
            started,
            steps,
            message,
            result=result,
            run_record=run_record,
            rendered_delivery=rendered,
        )

    def _require_run(self, result: ServiceResult):
        run = RunStore(self.settings.data_dir).get(result.run_id)
        if run is None:
            raise LookupError(f"run record not found: {result.run_id}")
        return run

    def _require_delivery(self, result: ServiceResult):
        deliveries = [
            delivery
            for delivery in OutboxStore(self.settings.data_dir).list_all()
            if delivery.run_id == result.run_id
            or (result.trace_id is not None and delivery.trace_id == result.trace_id)
        ]
        if not deliveries:
            raise LookupError(f"outbox delivery not found for run: {result.run_id}")
        return deliveries[-1]

    def _step(self, steps: list[dict], name: str, fn):
        started = perf_counter()
        try:
            value = fn()
        except Exception as exc:
            steps.append(
                {
                    "name": name,
                    "ok": False,
                    "elapsed_ms": round((perf_counter() - started) * 1000, 2),
                    "message": f"{type(exc).__name__}: {exc}",
                }
            )
            return None
        steps.append(
            {
                "name": name,
                "ok": True,
                "elapsed_ms": round((perf_counter() - started) * 1000, 2),
                "message": "ok",
            }
        )
        return value

    def _report(
        self,
        started: float,
        steps: list[dict],
        message: IncomingMessage,
        result: ServiceResult | None = None,
        run_record=None,
        rendered_delivery: dict | None = None,
    ) -> dict:
        return {
            "status": "ok" if all(step["ok"] for step in steps) else "degraded",
            "elapsed_ms": round((perf_counter() - started) * 1000, 2),
            "message": message.to_dict(),
            "steps": steps,
            "result": self._result_to_dict(result) if result else None,
            "run_record": run_record.to_dict() if run_record else None,
            "rendered_delivery": rendered_delivery,
        }

    def _result_to_dict(self, result: ServiceResult) -> dict:
        return {
            "run_id": result.run_id,
            "trace_id": result.trace_id,
            "final": result.final,
            "run_summary": result.run_summary,
            "worker_results": result.worker_results,
        }

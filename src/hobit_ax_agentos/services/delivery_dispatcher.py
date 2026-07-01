from __future__ import annotations

from typing import Protocol

from hobit_ax_agentos.config import AppSettings
from hobit_ax_agentos.models import OutboundDelivery
from hobit_ax_agentos.storage import OutboxStore


class DeliveryTransport(Protocol):
    def send(self, delivery: OutboundDelivery) -> dict:
        ...


class LocalAckTransport:
    def send(self, delivery: OutboundDelivery) -> dict:
        return {
            "ok": True,
            "transport": "local_ack",
            "channel": delivery.channel,
            "delivery_id": delivery.delivery_id,
        }


class DeliveryDispatcher:
    def __init__(
        self,
        settings: AppSettings | None = None,
        outbox_store: OutboxStore | None = None,
        transport: DeliveryTransport | None = None,
    ) -> None:
        self.settings = settings or AppSettings()
        self.outbox_store = outbox_store or OutboxStore(self.settings.data_dir)
        self.transport = transport or LocalAckTransport()

    def dispatch_one(self, delivery_id: str) -> dict:
        delivery = self.outbox_store.get(delivery_id)
        if delivery is None:
            raise KeyError(delivery_id)
        if delivery.status != "PENDING":
            return {
                "delivery": delivery.to_dict(),
                "transport_result": None,
                "skipped": True,
                "reason": f"delivery_status_{delivery.status.lower()}",
            }
        try:
            transport_result = self.transport.send(delivery)
        except Exception as exc:
            failed = self.outbox_store.mark_failed(delivery_id, error=str(exc))
            return {
                "delivery": failed.to_dict(),
                "transport_result": None,
                "skipped": False,
                "error": str(exc),
            }
        if transport_result.get("ok"):
            updated = self.outbox_store.mark_sent(delivery_id)
        else:
            updated = self.outbox_store.mark_failed(
                delivery_id,
                error=str(transport_result.get("error") or "transport rejected delivery"),
            )
        return {
            "delivery": updated.to_dict(),
            "transport_result": transport_result,
            "skipped": False,
        }

    def dispatch_pending(self, limit: int = 50) -> list[dict]:
        deliveries = self.outbox_store.list_by_status("PENDING", limit=limit)
        return [self.dispatch_one(delivery.delivery_id) for delivery in deliveries]

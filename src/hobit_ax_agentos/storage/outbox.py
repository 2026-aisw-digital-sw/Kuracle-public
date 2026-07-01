from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from hobit_ax_agentos.models import OutboundDelivery, utc_now
from hobit_ax_agentos.storage.locking import file_lock


class OutboxStore:
    def __init__(self, root: Path | str = "data") -> None:
        self.root = Path(root)
        self.path = self.root / "outbox.jsonl"
        self.root.mkdir(parents=True, exist_ok=True)

    def append_response(
        self,
        session_id: str,
        user_id: str,
        channel: str,
        text: str,
        payload: dict | None = None,
        run_id: str | None = None,
        trace_id: str | None = None,
    ) -> OutboundDelivery:
        delivery = OutboundDelivery(
            delivery_id=f"delivery_{uuid4().hex}",
            session_id=session_id,
            user_id=user_id,
            channel=channel,
            text=text,
            payload=dict(payload or {}),
            run_id=run_id,
            trace_id=trace_id,
        )
        self.append(delivery)
        return delivery

    def append(self, delivery: OutboundDelivery) -> OutboundDelivery:
        with file_lock(self.path):
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(delivery.to_dict(), ensure_ascii=False) + "\n")
        return delivery

    def save(self, delivery: OutboundDelivery) -> OutboundDelivery:
        with file_lock(self.path):
            deliveries = {item.delivery_id: item for item in self._read_all_unlocked()}
            delivery.updated_at = utc_now()
            deliveries[delivery.delivery_id] = delivery
            self._write_all_unlocked(deliveries.values())
        return delivery

    def get(self, delivery_id: str) -> OutboundDelivery | None:
        return next(
            (delivery for delivery in self.list_all() if delivery.delivery_id == delivery_id),
            None,
        )

    def list_by_session(self, session_id: str, limit: int = 50) -> list[OutboundDelivery]:
        deliveries = [
            delivery
            for delivery in self.list_all()
            if delivery.session_id == session_id
        ]
        return deliveries[-limit:]

    def list_by_status(self, status: str | None = None, limit: int = 50) -> list[OutboundDelivery]:
        deliveries = self.list_all()
        if status:
            deliveries = [delivery for delivery in deliveries if delivery.status == status.upper()]
        return deliveries[-limit:]

    def mark_sent(self, delivery_id: str) -> OutboundDelivery:
        delivery = self._require(delivery_id)
        delivery.status = "SENT"
        delivery.sent_at = utc_now()
        delivery.error = None
        return self.save(delivery)

    def mark_failed(self, delivery_id: str, error: str | None = None) -> OutboundDelivery:
        delivery = self._require(delivery_id)
        delivery.status = "FAILED"
        delivery.error = error
        return self.save(delivery)

    def list_all(self) -> list[OutboundDelivery]:
        with file_lock(self.path):
            return self._read_all_unlocked()

    def _read_all_unlocked(self) -> list[OutboundDelivery]:
        if not self.path.exists():
            return []
        deliveries: list[OutboundDelivery] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            deliveries.append(OutboundDelivery(**json.loads(line)))
        return deliveries

    def _write_all_unlocked(self, deliveries: Iterable[OutboundDelivery]) -> None:
        lines = [json.dumps(delivery.to_dict(), ensure_ascii=False) for delivery in deliveries]
        self.path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def _require(self, delivery_id: str) -> OutboundDelivery:
        delivery = self.get(delivery_id)
        if delivery is None:
            raise KeyError(delivery_id)
        return delivery

from __future__ import annotations

from hobit_ax_agentos.models import OutboundDelivery
from hobit_ax_agentos.storage import OutboxStore


class DeliveryRenderer:
    def __init__(self, data_dir: str | None = None, outbox_store: OutboxStore | None = None) -> None:
        self.outbox_store = outbox_store or OutboxStore(data_dir or "data")

    def render_one(self, delivery_id: str, channel: str | None = None) -> dict:
        delivery = self.outbox_store.get(delivery_id)
        if delivery is None:
            raise KeyError(delivery_id)
        return self.render(delivery, channel=channel)

    def render(self, delivery: OutboundDelivery, channel: str | None = None) -> dict:
        target_channel = (channel or delivery.channel or "generic").lower()
        if target_channel in {"kakao", "kakaotalk"}:
            payload = self._kakao(delivery)
        elif target_channel in {"web", "portal"}:
            payload = self._web(delivery, target_channel)
        elif target_channel == "api":
            payload = self._api(delivery)
        else:
            payload = self._generic(delivery, target_channel)
        return {
            "delivery": delivery.to_dict(),
            "channel": target_channel,
            "payload": payload,
        }

    def _api(self, delivery: OutboundDelivery) -> dict:
        return {
            "delivery_id": delivery.delivery_id,
            "session_id": delivery.session_id,
            "user_id": delivery.user_id,
            "text": delivery.text,
            "status": delivery.status,
            "run_id": delivery.run_id,
            "trace_id": delivery.trace_id,
            "payload": delivery.payload,
        }

    def _web(self, delivery: OutboundDelivery, channel: str) -> dict:
        return {
            "type": "agent_response",
            "channel": channel,
            "delivery_id": delivery.delivery_id,
            "session_id": delivery.session_id,
            "user_id": delivery.user_id,
            "message": {
                "text": delivery.text,
                "metadata": {
                    "run_id": delivery.run_id,
                    "trace_id": delivery.trace_id,
                    "status": delivery.status,
                },
            },
        }

    def _kakao(self, delivery: OutboundDelivery) -> dict:
        return {
            "version": "2.0",
            "template": {
                "outputs": [
                    {
                        "simpleText": {
                            "text": delivery.text,
                        }
                    }
                ]
            },
            "context": {
                "values": [
                    {
                        "name": "delivery_id",
                        "lifeSpan": 1,
                        "params": {
                            "delivery_id": delivery.delivery_id,
                            "run_id": delivery.run_id,
                            "trace_id": delivery.trace_id,
                        },
                    }
                ]
            },
        }

    def _generic(self, delivery: OutboundDelivery, channel: str) -> dict:
        return {
            "channel": channel,
            "delivery_id": delivery.delivery_id,
            "text": delivery.text,
            "metadata": {
                "session_id": delivery.session_id,
                "user_id": delivery.user_id,
                "run_id": delivery.run_id,
                "trace_id": delivery.trace_id,
                "status": delivery.status,
            },
        }

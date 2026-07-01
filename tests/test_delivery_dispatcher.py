from __future__ import annotations

from hobit_ax_agentos.services.delivery_dispatcher import DeliveryDispatcher
from hobit_ax_agentos.services.delivery_renderer import DeliveryRenderer
from hobit_ax_agentos.storage import OutboxStore


class FailingTransport:
    def send(self, delivery) -> dict:
        raise RuntimeError("network down")


class RejectingTransport:
    def send(self, delivery) -> dict:
        return {"ok": False, "error": "rejected"}


def test_delivery_dispatcher_marks_pending_delivery_sent(tmp_path) -> None:
    store = OutboxStore(tmp_path)
    delivery = store.append_response(
        session_id="session_1",
        user_id="user_1",
        channel="api",
        text="hello",
    )

    result = DeliveryDispatcher(outbox_store=store).dispatch_one(delivery.delivery_id)

    assert result["delivery"]["status"] == "SENT"
    assert result["transport_result"]["transport"] == "local_ack"
    assert store.get(delivery.delivery_id).status == "SENT"


def test_delivery_dispatcher_marks_transport_exception_failed(tmp_path) -> None:
    store = OutboxStore(tmp_path)
    delivery = store.append_response("session_1", "user_1", "api", "hello")

    result = DeliveryDispatcher(
        outbox_store=store,
        transport=FailingTransport(),
    ).dispatch_one(delivery.delivery_id)

    assert result["delivery"]["status"] == "FAILED"
    assert result["error"] == "network down"
    assert store.get(delivery.delivery_id).error == "network down"


def test_delivery_dispatcher_marks_transport_rejection_failed(tmp_path) -> None:
    store = OutboxStore(tmp_path)
    delivery = store.append_response("session_1", "user_1", "api", "hello")

    result = DeliveryDispatcher(
        outbox_store=store,
        transport=RejectingTransport(),
    ).dispatch_one(delivery.delivery_id)

    assert result["delivery"]["status"] == "FAILED"
    assert result["transport_result"]["error"] == "rejected"


def test_delivery_dispatcher_skips_non_pending_delivery(tmp_path) -> None:
    store = OutboxStore(tmp_path)
    delivery = store.append_response("session_1", "user_1", "api", "hello")
    store.mark_sent(delivery.delivery_id)

    result = DeliveryDispatcher(outbox_store=store).dispatch_one(delivery.delivery_id)

    assert result["skipped"] is True
    assert result["reason"] == "delivery_status_sent"


def test_delivery_renderer_returns_kakao_payload(tmp_path) -> None:
    store = OutboxStore(tmp_path)
    delivery = store.append_response(
        session_id="session_1",
        user_id="user_1",
        channel="kakaotalk",
        text="hello kakao",
        run_id="run_1",
        trace_id="trace_1",
    )

    rendered = DeliveryRenderer(outbox_store=store).render_one(delivery.delivery_id)

    assert rendered["channel"] == "kakaotalk"
    assert rendered["delivery"]["delivery_id"] == delivery.delivery_id
    assert rendered["payload"]["version"] == "2.0"
    assert rendered["payload"]["template"]["outputs"][0]["simpleText"]["text"] == "hello kakao"
    assert rendered["payload"]["context"]["values"][0]["params"]["run_id"] == "run_1"


def test_delivery_renderer_can_override_channel(tmp_path) -> None:
    store = OutboxStore(tmp_path)
    delivery = store.append_response(
        session_id="session_1",
        user_id="user_1",
        channel="api",
        text="hello web",
    )

    rendered = DeliveryRenderer(outbox_store=store).render_one(
        delivery.delivery_id,
        channel="web",
    )

    assert rendered["channel"] == "web"
    assert rendered["payload"]["type"] == "agent_response"
    assert rendered["payload"]["message"]["text"] == "hello web"

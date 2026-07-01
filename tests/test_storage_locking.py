from __future__ import annotations

from multiprocessing import Process

from hobit_ax_agentos.models import IncomingMessage
from hobit_ax_agentos.storage import AsyncJobStore, OutboxStore


def _create_job(root: str, index: int) -> None:
    AsyncJobStore(root).create(
        kind="query",
        message=IncomingMessage(
            channel="api",
            user_id=f"user_{index}",
            text=f"question {index}",
            session_id="session_1",
        ),
    )


def _append_delivery(root: str, index: int) -> None:
    OutboxStore(root).append_response(
        session_id="session_1",
        user_id=f"user_{index}",
        channel="api",
        text=f"answer {index}",
    )


def test_async_job_store_preserves_concurrent_creates(tmp_path) -> None:
    processes = [
        Process(target=_create_job, args=(str(tmp_path), index))
        for index in range(8)
    ]

    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)

    assert all(process.exitcode == 0 for process in processes)
    jobs = AsyncJobStore(tmp_path).list_all()
    assert len(jobs) == 8
    assert sorted(job.message["text"] for job in jobs) == [
        f"question {index}" for index in range(8)
    ]


def test_outbox_store_preserves_concurrent_appends(tmp_path) -> None:
    processes = [
        Process(target=_append_delivery, args=(str(tmp_path), index))
        for index in range(8)
    ]

    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)

    assert all(process.exitcode == 0 for process in processes)
    deliveries = OutboxStore(tmp_path).list_all()
    assert len(deliveries) == 8
    assert sorted(delivery.text for delivery in deliveries) == [
        f"answer {index}" for index in range(8)
    ]

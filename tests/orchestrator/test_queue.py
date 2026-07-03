from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from dnd_llm.orchestrator.queue import EventQueue, QueuedEvent


def test_event_queue_dedupes_concurrent_duplicate_idempotency_keys() -> None:
    queue: EventQueue[int] = EventQueue()
    calls: list[str] = []

    def handler(event: QueuedEvent) -> int:
        calls.append(event.idempotency_key)
        time.sleep(0.01)
        return len(calls)

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(
            executor.map(
                lambda _: queue.submit(QueuedEvent("same-key", {"type": "test"}), handler),
                range(4),
            )
        )

    assert results == [1, 1, 1, 1]
    assert calls == ["same-key"]


def test_event_queue_processes_distinct_events_in_submission_order() -> None:
    queue: EventQueue[str] = EventQueue()
    handled: list[str] = []

    def handler(event: QueuedEvent) -> str:
        handled.append(event.idempotency_key)
        return f"handled:{event.idempotency_key}"

    first = queue.submit(QueuedEvent("event-1", {}), handler)
    second = queue.submit(QueuedEvent("event-2", {}), handler)

    assert first == "handled:event-1"
    assert second == "handled:event-2"
    assert handled == ["event-1", "event-2"]


def test_event_queue_does_not_cache_failed_events() -> None:
    queue: EventQueue[str] = EventQueue()
    calls = 0

    def failing_handler(_: QueuedEvent) -> str:
        nonlocal calls
        calls += 1
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        queue.submit(QueuedEvent("retryable", {}), failing_handler)
    with pytest.raises(RuntimeError, match="boom"):
        queue.submit(QueuedEvent("retryable", {}), failing_handler)

    assert calls == 2

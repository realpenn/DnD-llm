from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class QueuedEvent:
    idempotency_key: str
    payload: object


class IdempotencyStore:
    def __init__(self) -> None:
        self._seen: dict[str, object] = {}

    def seen(self, key: str) -> bool:
        return key in self._seen

    def get(self, key: str) -> object | None:
        return self._seen.get(key)

    def record(self, key: str, result: object) -> None:
        self._seen[key] = result


class EventQueue(Generic[T]):
    def __init__(self) -> None:
        self._queue: deque[QueuedEvent] = deque()
        self._lock = Lock()
        self.idempotency = IdempotencyStore()

    def submit(self, event: QueuedEvent, handler: Callable[[QueuedEvent], T]) -> T | object:
        with self._lock:
            if self.idempotency.seen(event.idempotency_key):
                return self.idempotency.get(event.idempotency_key)
            self._queue.append(event)
            current = self._queue.popleft()
            result = handler(current)
            self.idempotency.record(event.idempotency_key, result)
            return result

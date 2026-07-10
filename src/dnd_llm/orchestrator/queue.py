from __future__ import annotations

from collections import deque
from collections.abc import Callable, MutableMapping
from dataclasses import dataclass
from threading import Lock
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class QueuedEvent:
    idempotency_key: str
    payload: object


class IdempotencyStore:
    def __init__(
        self,
        persistent: MutableMapping[str, object] | None = None,
        *,
        serializer: Callable[[object], object] | None = None,
        deserializer: Callable[[object], object] | None = None,
    ) -> None:
        self._seen: dict[str, object] = {}
        self._persistent = persistent
        self._serializer = serializer or (lambda value: value)
        self._deserializer = deserializer or (lambda value: value)

    def seen(self, key: str) -> bool:
        return key in self._seen or (self._persistent is not None and key in self._persistent)

    def get(self, key: str) -> object | None:
        if key in self._seen:
            return self._seen[key]
        if self._persistent is None or key not in self._persistent:
            return None
        result = self._deserializer(self._persistent[key])
        self._seen[key] = result
        return result

    def record(self, key: str, result: object) -> None:
        self._seen[key] = result
        if self._persistent is not None:
            self._persistent[key] = self._serializer(result)


class EventQueue(Generic[T]):
    def __init__(
        self,
        *,
        persistent_store: MutableMapping[str, object] | None = None,
        serializer: Callable[[object], object] | None = None,
        deserializer: Callable[[object], object] | None = None,
    ) -> None:
        self._queue: deque[QueuedEvent] = deque()
        self._lock = Lock()
        self.idempotency = IdempotencyStore(
            persistent_store,
            serializer=serializer,
            deserializer=deserializer,
        )

    def submit(self, event: QueuedEvent, handler: Callable[[QueuedEvent], T]) -> T | object:
        with self._lock:
            if self.idempotency.seen(event.idempotency_key):
                return self.idempotency.get(event.idempotency_key)
            self._queue.append(event)
            current = self._queue.popleft()
            result = handler(current)
            self.idempotency.record(event.idempotency_key, result)
            return result

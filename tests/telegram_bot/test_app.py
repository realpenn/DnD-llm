from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace
from typing import cast

import pytest

from dnd_llm.config import Settings
from dnd_llm.telegram_bot.app import MAX_CONCURRENT_UPDATES, build_application, handle_update
from dnd_llm.telegram_bot.runtime import OutgoingMessage, TelegramRuntime


def test_build_application_requires_token() -> None:
    with pytest.raises(ValueError, match="BOT_TOKEN"):
        build_application(Settings(bot_token=None), cast(TelegramRuntime, object()))


def test_build_application_processes_multiple_chats_concurrently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeApplication:
        def __init__(self, max_concurrent_updates: int) -> None:
            self.update_processor = SimpleNamespace(max_concurrent_updates=max_concurrent_updates)

        def add_handler(self, handler) -> None:
            self.handler = handler

    class FakeBuilder:
        def token(self, token: str):
            assert token == "123456:test-token"
            return self

        def concurrent_updates(self, value: int):
            self.max_concurrent_updates = value
            return self

        def build(self):
            return FakeApplication(self.max_concurrent_updates)

    monkeypatch.setattr(
        "dnd_llm.telegram_bot.app.Application.builder",
        lambda: FakeBuilder(),
    )
    application = build_application(
        Settings(bot_token="123456:test-token"),
        cast(TelegramRuntime, object()),
    )

    assert application.update_processor.max_concurrent_updates == MAX_CONCURRENT_UPDATES
    assert MAX_CONCURRENT_UPDATES > 1


def test_handle_update_does_not_block_event_loop_on_sync_runtime() -> None:
    started = threading.Event()
    release = threading.Event()
    sent: list[tuple[str, str]] = []

    class BlockingRuntime:
        def handle_message(self, incoming, *, now):
            started.set()
            assert release.wait(timeout=1)
            return [OutgoingMessage(chat_id=incoming.chat_id, text=f"done:{now}")]

    update = SimpleNamespace(
        effective_message=SimpleNamespace(text="/status", message_id=7),
        effective_user=SimpleNamespace(id=11),
        effective_chat=SimpleNamespace(id=22, type="group"),
    )

    async def sender(chat_id: str, text: str) -> None:
        sent.append((chat_id, text))

    async def scenario() -> None:
        task = asyncio.create_task(handle_update(update, BlockingRuntime(), sender, now=123))
        for _ in range(100):
            if started.is_set():
                break
            await asyncio.sleep(0.001)
        assert started.is_set()
        await asyncio.sleep(0.01)
        assert not task.done()
        release.set()
        await task

    asyncio.run(scenario())
    assert sent == [("22", "done:123")]

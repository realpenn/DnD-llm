from __future__ import annotations

import sys
from types import SimpleNamespace

from dnd_llm.config import Settings
from dnd_llm.dm.client import OpenAICompatibleClient


def test_openai_compatible_client_unconfigured_preserves_messages_and_tools() -> None:
    client = OpenAICompatibleClient(Settings(openai_api_key=None), model="dm-model")
    messages = [{"role": "user", "content": "DD test"}]
    tools = [{"type": "function", "function": {"name": "roll_check"}}]

    response = client.chat(messages=messages, tools=tools)

    assert response == {"type": "unconfigured", "messages": messages, "tools": tools}


def test_openai_compatible_client_unconfigured_without_model() -> None:
    client = OpenAICompatibleClient(Settings(openai_api_key="test-key"), model=None)

    response = client.chat(messages=[{"role": "user", "content": "DD test"}])

    assert response["type"] == "unconfigured"
    assert response["tools"] == []


def test_openai_compatible_client_sets_explicit_timeout(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def model_dump(self) -> dict[str, object]:
            return {"type": "ok"}

    class FakeOpenAI:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=lambda **_: FakeResponse())
            )

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    client = OpenAICompatibleClient(
        Settings(openai_api_key="test-key"),
        model="dm-model",
        timeout_seconds=12.5,
    )

    assert client.chat(messages=[{"role": "user", "content": "DD test"}]) == {"type": "ok"}
    assert captured["timeout"] == 12.5

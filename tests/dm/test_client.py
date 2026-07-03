from __future__ import annotations

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

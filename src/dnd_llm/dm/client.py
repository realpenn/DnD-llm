from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from dnd_llm.config import Settings


@dataclass
class OpenAICompatibleClient:
    settings: Settings
    model: str | None

    def chat(
        self, messages: list[dict[str, str]], tools: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        if not self.settings.openai_api_key or not self.model:
            return {"type": "unconfigured", "messages": messages, "tools": tools or []}
        from openai import OpenAI

        client = OpenAI(
            api_key=self.settings.openai_api_key, base_url=self.settings.openai_base_url
        )
        client_any = cast(Any, client)
        payload: dict[str, Any] = {"model": self.model, "messages": messages}
        if tools is not None:
            payload["tools"] = tools
        response = client_any.chat.completions.create(**payload)
        return response.model_dump()

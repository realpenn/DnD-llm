from __future__ import annotations

from typing import Any


def model_usage_from_response(response: dict[str, Any]) -> dict[str, int]:
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return {}
    prompt_tokens = _int_usage(usage, "prompt_tokens", "input_tokens")
    completion_tokens = _int_usage(usage, "completion_tokens", "output_tokens")
    total_tokens = _int_usage(usage, "total_tokens")
    if total_tokens == 0:
        total_tokens = prompt_tokens + completion_tokens
    result = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }
    return {key: value for key, value in result.items() if value > 0}


def _int_usage(usage: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = usage.get(key)
        if value is not None:
            return max(0, int(value))
    return 0

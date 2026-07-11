from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any

from ..orchestrator.router import ContextSlice

PROMPT_VERSION = "dm-v1"
SUMMARY_PROMPT_VERSION = "summary-v1"
SUMMARY_MAX_CHARS = 2000
SUMMARY_NUMBER_RE = re.compile(r"\b\d+\b")


def build_dm_messages(context: ContextSlice, player_text: str) -> list[dict[str, str]]:
    payload: dict[str, Any] = asdict(context)
    return [
        {
            "role": "system",
            "content": (
                "你是 DnD-LLM 的 DM。所有机械数字只能来自工具结果；"
                "不要编造 HP、AC、骰值、金币、距离或 DC。"
            ),
        },
        {"role": "system", "content": f"context={payload}"},
        {"role": "user", "content": player_text},
    ]


def build_summary_messages(previous_summary: str, scene_notes: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "你是 DnD-LLM 的剧情摘要器。只压缩用户可见的公开剧情，"
                "不要新增、推断或保留精确 HP、AC、DC、骰值、金币、距离等机械数字；"
                "不要加入未出现在输入中的物品、武器、法术或奖励。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"既有摘要：\n{previous_summary.strip() or '（无）'}\n\n"
                f"新场景记录：\n{scene_notes.strip()}"
            ),
        },
    ]


def summarize(
    previous_summary: str,
    scene_notes: str,
    *,
    max_chars: int = SUMMARY_MAX_CHARS,
) -> str:
    """Deterministic fallback rolling summary for unconfigured summary models."""
    clean_previous = _sanitize_summary_text(previous_summary)
    clean_notes = _sanitize_summary_text(scene_notes)
    if clean_previous and clean_notes:
        merged = f"{clean_previous}\n{clean_notes}"
    else:
        merged = clean_previous or clean_notes
    return _trim_summary(merged, max_chars=max_chars)


def sanitize_summary(text: str, *, max_chars: int = SUMMARY_MAX_CHARS) -> str:
    return _trim_summary(_sanitize_summary_text(text), max_chars=max_chars)


def _sanitize_summary_text(text: str) -> str:
    collapsed = " ".join(text.split())
    return SUMMARY_NUMBER_RE.sub("<num>", collapsed)


def _trim_summary(text: str, *, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    marker = "..."
    keep = max_chars - len(marker)
    if keep <= 0:
        return marker[:max_chars]
    return f"{marker}{text[-keep:]}"

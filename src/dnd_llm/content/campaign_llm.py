from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .campaign_pack import CampaignPackDefinition, CampaignPackValidator


@dataclass
class CampaignLLMResult:
    accepted: bool
    pack: CampaignPackDefinition | None = None
    errors: list[str] | None = None
    raw_payload: dict[str, Any] | None = None


def generate_campaign_pack_candidate(
    prompt: str,
    *,
    client: Any,
    validator: CampaignPackValidator,
) -> CampaignLLMResult:
    messages = [
        {
            "role": "system",
            "content": (
                "你是 DnD-LLM 的战役包生成器。只返回一个完整 JSON object，"
                "格式必须是 CampaignPack。怪物、物品、动作、事件 automation 必须引用"
                "已实现的 SRD 5.2.1 或战役包内定义；不要创造未校验规则实体。"
            ),
        },
        {"role": "user", "content": prompt},
    ]
    response = client.chat(messages=messages)
    if response.get("type") == "unconfigured":
        return CampaignLLMResult(accepted=False, errors=["LLM client is unconfigured"])
    return _validated_pack_from_response(response, validator=validator)


def apply_llm_campaign_edit(
    pack: CampaignPackDefinition,
    text: str,
    *,
    client: Any,
    validator: CampaignPackValidator,
) -> CampaignLLMResult:
    messages = [
        {
            "role": "system",
            "content": (
                "你是 DnD-LLM 的战役包编辑器。根据 GM 指令重写并只返回完整 CampaignPack JSON。"
                "不得新增未通过 SRD 5.2.1 数据校验的怪物、物品、动作、奖励或 automation。"
            ),
        },
        {
            "role": "user",
            "content": (
                "当前 CampaignPack JSON：\n"
                f"{json.dumps(pack.to_dict(), ensure_ascii=False, sort_keys=True)}\n\n"
                f"GM 修改指令：\n{text.strip()}"
            ),
        },
    ]
    response = client.chat(messages=messages)
    if response.get("type") == "unconfigured":
        return CampaignLLMResult(accepted=False, errors=["LLM client is unconfigured"])
    return _validated_pack_from_response(response, validator=validator)


def _validated_pack_from_response(
    response: dict[str, Any],
    *,
    validator: CampaignPackValidator,
) -> CampaignLLMResult:
    payload = _campaign_pack_payload(response)
    if payload is None:
        return CampaignLLMResult(
            accepted=False,
            errors=["LLM response did not contain a CampaignPack JSON object"],
        )
    try:
        pack = CampaignPackDefinition.from_dict(payload)
    except (KeyError, TypeError, ValueError) as exc:
        return CampaignLLMResult(
            accepted=False,
            errors=[f"invalid CampaignPack JSON: {exc}"],
            raw_payload=payload,
        )
    report = validator.validate(pack)
    if not report.ok:
        return CampaignLLMResult(accepted=False, errors=report.errors, raw_payload=payload)
    return CampaignLLMResult(accepted=True, pack=pack, errors=[], raw_payload=payload)


def _campaign_pack_payload(response: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(response.get("campaign_pack"), dict):
        return dict(response["campaign_pack"])
    if "campaign_id" in response:
        return dict(response)
    content = _content_from_response(response)
    if not content:
        return None
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if isinstance(payload.get("campaign_pack"), dict):
        return dict(payload["campaign_pack"])
    return payload


def _content_from_response(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    return content.strip()
            text = first.get("text")
            if isinstance(text, str):
                return text.strip()
    content = response.get("content")
    return content.strip() if isinstance(content, str) else ""

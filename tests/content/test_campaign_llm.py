from __future__ import annotations

import json
from typing import Any

from dnd_llm.content.campaign_gen import starter_campaign_pack
from dnd_llm.content.campaign_llm import (
    apply_llm_campaign_edit,
    generate_campaign_pack_candidate,
)
from dnd_llm.content.campaign_pack import CampaignPackValidator
from dnd_llm.core.compendium.loader import CompendiumLoader


class FakeClient:
    def __init__(self, response: dict[str, Any]):
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self.calls.append({"messages": messages, "tools": tools or []})
        return self.response


def _validator() -> CampaignPackValidator:
    return CampaignPackValidator(compendium=CompendiumLoader("rules_data").load())


def _content_response(payload: dict[str, Any]) -> dict[str, Any]:
    return {"choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}]}


def test_llm_campaign_candidate_accepts_valid_structured_pack() -> None:
    pack = starter_campaign_pack()
    client = FakeClient(_content_response(pack.to_dict()))

    result = generate_campaign_pack_candidate(
        "生成一个 Tier 1 starter pack",
        client=client,
        validator=_validator(),
    )

    assert result.accepted is True
    assert result.pack is not None
    assert result.pack.campaign_id == "starter_generated"
    assert result.pack.outline["chapters"][0]["zone_ids"] == ["start", "ruins"]
    assert "只返回一个完整 JSON object" in client.calls[0]["messages"][0]["content"]


def test_llm_campaign_candidate_rejects_unknown_srd_references() -> None:
    payload = starter_campaign_pack().to_dict()
    payload["encounters"]["kobold_watch"]["monsters"][0]["monster_id"] = "srd.imaginary_dragon"
    client = FakeClient(_content_response(payload))

    result = generate_campaign_pack_candidate(
        "生成一个带有幻想怪物的 pack",
        client=client,
        validator=_validator(),
    )

    assert result.accepted is False
    assert result.errors is not None
    assert any("unknown monster_id srd.imaginary_dragon" in error for error in result.errors)


def test_llm_campaign_edit_rewrites_full_pack_and_validates() -> None:
    original = starter_campaign_pack()
    payload = original.to_dict()
    payload["title"] = "边境遗迹修订版"
    payload["zones"]["ruins"]["name"] = "崩塌遗迹入口"
    client = FakeClient(_content_response(payload))

    result = apply_llm_campaign_edit(
        original,
        "把标题改为边境遗迹修订版，ruins 改名为崩塌遗迹入口",
        client=client,
        validator=_validator(),
    )

    assert result.accepted is True
    assert result.pack is not None
    assert result.pack.title == "边境遗迹修订版"
    assert result.pack.zones["ruins"]["name"] == "崩塌遗迹入口"
    assert original.title == "边境遗迹"
    assert "当前 CampaignPack JSON" in client.calls[0]["messages"][1]["content"]


def test_llm_campaign_edit_rejects_invalid_or_unconfigured_response() -> None:
    original = starter_campaign_pack()
    invalid = apply_llm_campaign_edit(
        original,
        "随便改",
        client=FakeClient({"choices": [{"message": {"content": "not json"}}]}),
        validator=_validator(),
    )
    unconfigured = generate_campaign_pack_candidate(
        "生成",
        client=FakeClient({"type": "unconfigured"}),
        validator=_validator(),
    )

    assert invalid.accepted is False
    assert invalid.errors == ["LLM response did not contain a CampaignPack JSON object"]
    assert unconfigured.accepted is False
    assert unconfigured.errors == ["LLM client is unconfigured"]

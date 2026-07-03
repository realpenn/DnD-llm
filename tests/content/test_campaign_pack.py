from __future__ import annotations

from dnd_llm.content.campaign_editor import apply_natural_language_campaign_edit
from dnd_llm.content.campaign_gen import starter_campaign_pack
from dnd_llm.content.campaign_pack import CampaignPackLoader, CampaignPackValidator
from dnd_llm.content.character_gen import default_fighter
from dnd_llm.content.runtime import (
    apply_campaign_pack,
    build_encounter_combatants,
    register_campaign_pack_events,
)
from dnd_llm.core.compendium.loader import CompendiumLoader
from dnd_llm.core.persistence import AuditLog
from dnd_llm.core.tools import EngineTools


def test_starter_campaign_pack_validates_against_loaded_events() -> None:
    compendium = CompendiumLoader("rules_data").load()
    pack = CampaignPackLoader().load("rules_data/campaigns/starter/pack.json")

    report = CampaignPackValidator(compendium=compendium).validate(pack)

    assert report.ok, report.errors
    assert pack.outline["mainline"]
    assert pack.outline["chapters"][0]["zone_ids"] == ["start", "ruins"]
    assert pack.outline["npcs"][0]["role"] == "营地联络人"
    assert pack.outline["objectives"]
    assert pack.outline["endings"]
    assert pack.zones["start"]["edges"] == ["ruins"]
    assert pack.zones["vault"]["edges"] == ["ruins"]
    assert pack.zones["ruins"]["event_ids"] == ["starter.loose_stones"]
    assert "tactical_graph" in pack.zones["ruins"]
    assert pack.encounters["kobold_watch"]["budget"] == {
        "party_size": 4,
        "party_level": 1,
        "difficulty": "low",
    }
    assert "starter.loose_stones" in compendium.events
    event = compendium.events["starter.loose_stones"]
    assert event.trigger == {"type": "zone_entry", "zone_id": "ruins"}
    assert event.automation[1]["dc_ref"] == "starter.loose_stones.dex_save"
    assert event.automation[2]["damage_type"] == "bludgeoning"


def test_generated_starter_campaign_pack_validates_and_registers_embedded_events(
    make_state,
) -> None:
    compendium = CompendiumLoader("rules_data").load()
    pack = starter_campaign_pack()
    report = CampaignPackValidator(compendium=compendium).validate(pack)

    assert report.ok, report.errors
    assert pack.outline["chapters"][0]["title"] == "从营地到遗迹"
    assert pack.zones["ruins"]["tactical_graph"]["nodes"]
    assert pack.encounters["kobold_watch"]["budget"]["difficulty"] == "low"
    register_campaign_pack_events(compendium, pack)
    assert "starter.generated_loose_stones" in compendium.events

    state = make_state()
    assert state.encounter is not None
    tools = EngineTools(state, compendium, AuditLog())
    before = state.encounter.combatants["pc1"].hp_current
    result = tools.trigger_event(
        "starter.generated_loose_stones",
        actor_ids=["pc1"],
        targets=["pc1"],
        idempotency_key="generated-event",
    )

    assert result["success"] is True
    assert state.encounter.combatants["pc1"].hp_current <= before


def test_final_starter_campaign_pack_is_attributed_and_runtime_read_only(make_state) -> None:
    compendium = CompendiumLoader("rules_data").load()
    pack = CampaignPackLoader().load("rules_data/campaigns/starter/pack.json")
    before = pack.to_dict()
    state = make_state()
    audit = AuditLog()

    report = CampaignPackValidator(compendium=compendium).validate(pack)
    apply_campaign_pack(state, pack)
    tools = EngineTools(state, compendium, audit)
    tools.award(["pc1"], "starter.first_victory", idempotency_key="award-readonly-pack")
    tools.trigger_event(
        "starter.loose_stones",
        actor_ids=["pc1"],
        targets=["pc1"],
        idempotency_key="event-readonly-pack",
    )

    assert report.ok, report.errors
    assert any("SRD" in line and "CC-BY-4.0" in line for line in pack.attribution)
    assert pack.to_dict() == before


def test_campaign_pack_validator_rejects_missing_outline() -> None:
    compendium = CompendiumLoader("rules_data").load()
    pack = CampaignPackLoader().load("rules_data/campaigns/starter/pack.json")
    pack.outline = {}

    report = CampaignPackValidator(compendium=compendium).validate(pack)

    assert not report.ok
    assert any("campaign_pack.outline" in error for error in report.errors)


def test_campaign_pack_validator_rejects_bad_links() -> None:
    compendium = CompendiumLoader("rules_data").load()
    pack = CampaignPackLoader().load("rules_data/campaigns/starter/pack.json")
    pack.zones["start"]["edges"] = ["missing"]
    pack.zones["ruins"]["event_ids"] = ["missing.event"]
    pack.encounters["kobold_watch"]["monsters"][0]["monster_id"] = "missing.monster"
    pack.encounters["kobold_watch"]["monsters"][0]["actions"] = ["missing.action"]
    pack.rewards["starter.first_victory"]["items"] = ["missing.item"]

    report = CampaignPackValidator(compendium=compendium).validate(pack)

    assert not report.ok
    assert any("unknown zone" in error for error in report.errors)
    assert any("unknown event_id" in error for error in report.errors)
    assert any("unknown monster_id" in error for error in report.errors)
    assert any("unknown monster action" in error for error in report.errors)
    assert any("unknown reward item" in error for error in report.errors)


def test_campaign_pack_validator_accepts_srd_reward_items() -> None:
    compendium = CompendiumLoader("rules_data").load()
    pack = CampaignPackLoader().load("rules_data/campaigns/starter/pack.json")
    pack.rewards["starter.first_victory"]["items"] = [
        {"item_id": "srd.potion_of_healing", "quantity": 1}
    ]

    report = CampaignPackValidator(compendium=compendium).validate(pack)

    assert report.ok, report.errors


def test_apply_campaign_pack_stores_predefined_rewards_for_runtime(make_state) -> None:
    state = make_state()
    pack = CampaignPackLoader().load("rules_data/campaigns/starter/pack.json")

    apply_campaign_pack(state, pack)

    assert state.world.flags["campaign_rewards"]["starter.first_victory"] == {
        "gold": 12,
        "experience": 50,
        "items": [],
    }


def test_campaign_encounter_reward_awards_through_engine_tools(make_state) -> None:
    state = make_state()
    compendium = CompendiumLoader("rules_data").load()
    pack = CampaignPackLoader().load("rules_data/campaigns/starter/pack.json")
    apply_campaign_pack(state, pack)
    audit_log = AuditLog()
    reward_id = pack.encounters["kobold_watch"]["reward_id"]

    result = EngineTools(state, compendium, audit_log).award(
        ["pc1"],
        reward_id,
        idempotency_key="award-starter-encounter",
    )

    assert result["reward"]["kind"] == "campaign_reward"
    assert result["reward"]["reward_id"] == "starter.first_victory"
    assert state.characters["pc1"].gold == 12
    assert state.characters["pc1"].experience == 50
    assert state.characters["pc1"].inventory == {}
    assert audit_log.events[-1].tool_name == "award"
    assert audit_log.events[-1].tool_args["reward_id"] == "starter.first_victory"


def test_campaign_pack_validator_rejects_negative_reward_numbers() -> None:
    compendium = CompendiumLoader("rules_data").load()
    pack = CampaignPackLoader().load("rules_data/campaigns/starter/pack.json")
    pack.rewards["starter.first_victory"]["gold"] = -1
    pack.rewards["starter.first_victory"]["experience"] = -5

    report = CampaignPackValidator(compendium=compendium).validate(pack)

    assert not report.ok
    assert any("gold cannot be negative" in error for error in report.errors)
    assert any("experience cannot be negative" in error for error in report.errors)


def test_campaign_pack_validator_accepts_automated_xp_budget() -> None:
    compendium = CompendiumLoader("rules_data").load()
    pack = CampaignPackLoader().load("rules_data/campaigns/starter/pack.json")
    encounter = pack.encounters["kobold_watch"]
    encounter.pop("max_total_cr", None)
    encounter["budget"] = {"party_size": 4, "party_level": 1, "difficulty": "low"}
    encounter["monsters"][0]["count"] = 8

    report = CampaignPackValidator(compendium=compendium).validate(pack)

    assert report.ok, report.errors


def test_campaign_pack_validator_rejects_automated_xp_budget_overrun() -> None:
    compendium = CompendiumLoader("rules_data").load()
    pack = CampaignPackLoader().load("rules_data/campaigns/starter/pack.json")
    encounter = pack.encounters["kobold_watch"]
    encounter.pop("max_total_cr", None)
    encounter["budget"] = {"party_size": 4, "party_level": 1, "difficulty": "low"}
    encounter["monsters"][0]["count"] = 9

    report = CampaignPackValidator(compendium=compendium).validate(pack)

    assert not report.ok
    assert any("total XP 225 exceeds XP budget 200" in error for error in report.errors)


def test_campaign_pack_validator_rejects_invalid_automated_xp_budget() -> None:
    compendium = CompendiumLoader("rules_data").load()
    pack = CampaignPackLoader().load("rules_data/campaigns/starter/pack.json")
    encounter = pack.encounters["kobold_watch"]
    encounter.pop("max_total_cr", None)
    encounter["budget"] = {"party_size": 0, "party_level": 1, "difficulty": "low"}

    report = CampaignPackValidator(compendium=compendium).validate(pack)

    assert not report.ok
    assert any("invalid XP budget" in error for error in report.errors)


def test_campaign_pack_builds_monster_combatants_from_compendium_stat_blocks() -> None:
    compendium = CompendiumLoader("rules_data").load()
    pack = CampaignPackLoader().load("rules_data/campaigns/starter/pack.json")
    party = {"pc1": default_fighter("pc1", "Penn")}

    combatants = build_encounter_combatants(
        pack=pack,
        encounter_id="kobold_watch",
        party=party,
        compendium=compendium,
    )

    kobold = combatants["srd_kobold_1"]
    definition = compendium.monsters["srd.kobold"]
    assert kobold.hp_max == definition.hit_points
    assert kobold.armor_class == definition.armor_class
    assert kobold.speed_ft == definition.speed_ft
    assert kobold.abilities == definition.abilities
    assert kobold.actions == ["srd.kobold_dagger"]


def test_campaign_event_triggers_through_engine_tools(make_state) -> None:
    state = make_state()
    compendium = CompendiumLoader("rules_data").load()
    audit_log = AuditLog()
    tools = EngineTools(state, compendium, audit_log)
    assert state.encounter is not None
    before = state.encounter.combatants["pc1"].hp_current

    result = tools.trigger_event("starter.loose_stones", actor_ids=["pc1"], targets=["pc1"])

    assert result["success"] is True
    assert state.encounter.combatants["pc1"].hp_current <= before
    assert any(event.tool_name == "automation.execute" for event in audit_log.events)


def test_campaign_editor_applies_gm_natural_language_changes() -> None:
    compendium = CompendiumLoader("rules_data").load()
    pack = CampaignPackLoader().load("rules_data/campaigns/starter/pack.json")
    validator = CampaignPackValidator(compendium=compendium)

    result = apply_natural_language_campaign_edit(
        pack,
        "\n".join(
            [
                "标题：边境遗迹扩展版",
                "区域 ruins 名称 崩塌遗迹入口",
                "新增区域 vault 名称 宝库 连接 ruins",
                "区域 vault 事件 starter.loose_stones",
            ]
        ),
        validator=validator,
    )

    assert result.accepted is True
    assert result.pack is not None
    assert result.pack.title == "边境遗迹扩展版"
    assert result.pack.zones["ruins"]["name"] == "崩塌遗迹入口"
    assert "vault" in result.pack.zones["ruins"]["edges"]
    assert result.pack.zones["vault"]["event_ids"] == ["starter.loose_stones"]


def test_campaign_editor_rejects_invalid_event_reference() -> None:
    compendium = CompendiumLoader("rules_data").load()
    pack = CampaignPackLoader().load("rules_data/campaigns/starter/pack.json")
    validator = CampaignPackValidator(compendium=compendium)

    result = apply_natural_language_campaign_edit(
        pack,
        "区域 ruins 事件 missing.event",
        validator=validator,
    )

    assert result.accepted is False
    assert result.errors is not None
    assert any("unknown event_id" in error for error in result.errors)


def test_campaign_editor_rejects_unparseable_instruction() -> None:
    compendium = CompendiumLoader("rules_data").load()
    pack = CampaignPackLoader().load("rules_data/campaigns/starter/pack.json")
    validator = CampaignPackValidator(compendium=compendium)

    result = apply_natural_language_campaign_edit(
        pack,
        "把剧情变得更史诗一点",
        validator=validator,
    )

    assert result.accepted is False
    assert result.errors == ["无法解析修改指令：把剧情变得更史诗一点"]

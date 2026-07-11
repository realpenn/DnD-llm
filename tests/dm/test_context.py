from __future__ import annotations

import pytest

from dnd_llm.core.compendium.loader import CompendiumLoader
from dnd_llm.core.memory import remember_fragment
from dnd_llm.dm.context import build_dm_messages
from dnd_llm.orchestrator.router import build_context_slice


def test_dm_context_filters_exact_combat_numbers(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["pc1"].hp_current = 10
    state.encounter.combatants["pc1"].hp_max = 12
    state.encounter.combatants["goblin1"].hp_current = 3
    state.encounter.combatants["goblin1"].hp_max = 7
    compendium = CompendiumLoader("rules_data").load()

    context = build_context_slice(state, actor_id="pc1", actions=compendium.actions)
    messages = build_dm_messages(context, "DD 我观察敌人伤势")
    serialized = repr(messages)

    assert context.visible_state["encounter"]["combatants"]["pc1"]["hp"] == "Healthy"
    assert context.visible_state["encounter"]["combatants"]["goblin1"]["hp"] == "Bloodied"
    assert "hp_current" not in serialized
    assert "hp_max" not in serialized
    assert "armor_class" not in serialized
    assert "'hp': 10" not in serialized
    assert "'armor_class': 16" not in serialized


def test_dm_context_prompt_includes_rolling_summary(make_state) -> None:
    state = make_state()
    state.summary = "The party negotiated with Mara beside the old windmill."
    compendium = CompendiumLoader("rules_data").load()

    context = build_context_slice(state, actor_id="pc1", actions=compendium.actions)
    messages = build_dm_messages(context, "DD 我继续询问 Mara")
    serialized = repr(messages)

    assert context.summary == state.summary
    assert "The party negotiated with Mara" in serialized


def test_dm_context_combat_affordances_are_current_actor_only(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "pc2", "goblin1"]
    state.encounter.turn_index = 0
    state.encounter.action_budgets["pc1"] = {
        "action": 1,
        "bonus_action": 1,
        "reaction": 1,
        "movement": 30,
        "movement_used": 0,
        "free": 1,
    }
    compendium = CompendiumLoader("rules_data").load()

    current = build_context_slice(state, actor_id="pc1", actions=compendium.actions)
    out_of_turn = build_context_slice(state, actor_id="pc2", actions=compendium.actions)
    messages = build_dm_messages(current, "DD 我寻找可用动作")
    serialized = repr(messages)

    shortsword = next(
        item for item in current.affordances if item["action_id"] == "srd.shortsword_attack"
    )
    assert current.mode == "combat"
    assert shortsword["name"] == "短剑攻击"
    assert shortsword["economy"] == "action"
    assert shortsword["target_type"] == "hostile"
    assert shortsword["candidate_target_ids"] == ["goblin1"]
    assert "automation" not in serialized
    assert out_of_turn.affordances == []


def test_dm_context_includes_owned_item_actions_and_only_relevant_items(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "pc2", "goblin1"]
    state.encounter.turn_index = 0
    character = state.characters["pc1"]
    character.actions = ["srd.cure_wounds"]
    character.equipment = ["srd.quarterstaff"]
    character.inventory = {
        "srd.light_crossbow": 1,
        "srd.crossbow_bolt": 2,
        "srd.rope_50ft": 1,
    }
    character.resources["private-test-resource"] = 99
    state.encounter.action_budgets["pc1"] = {
        "action": 1,
        "bonus_action": 1,
        "reaction": 1,
        "movement": 30,
        "movement_used": 0,
        "free": 1,
    }
    compendium = CompendiumLoader("rules_data").load()

    context = build_context_slice(
        state,
        actor_id="pc1",
        actions=compendium.actions,
        items=compendium.items,
    )

    action_ids = {item["action_id"] for item in context.affordances}
    assert "srd.quarterstaff_attack" in action_ids
    assert "srd.light_crossbow_attack" in action_ids
    assert context.visible_state["actor"] == {
        "equipment": ["srd.quarterstaff"],
        "inventory": {"srd.light_crossbow": 1, "srd.crossbow_bolt": 2},
    }
    assert "private-test-resource" not in repr(context.visible_state)
    assert "srd.rope_50ft" not in repr(context.visible_state)


def test_dm_context_weapon_affordances_expose_legal_attack_params(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "goblin1"]
    state.encounter.turn_index = 0
    character = state.characters["pc1"]
    character.actions = []
    character.equipment = ["srd.quarterstaff", "srd.dagger"]
    character.feature_choices["weapon_mastery.srd.quarterstaff"] = "Topple"
    compendium = CompendiumLoader("rules_data").load()

    context = build_context_slice(
        state,
        actor_id="pc1",
        actions=compendium.actions,
        items=compendium.items,
    )

    quarterstaff = next(
        item for item in context.affordances if item["action_id"] == "srd.quarterstaff_attack"
    )
    dagger = next(item for item in context.affordances if item["action_id"] == "srd.dagger_attack")
    assert quarterstaff["weapon_mastery_property"] == "Topple"
    assert quarterstaff["optional_params"] == {
        "two_handed": {"type": "boolean"},
        "use_weapon_mastery": {"type": "boolean"},
    }
    assert dagger["weapon_mastery_property"] == "Nick"
    assert dagger["optional_params"] == {
        "weapon_ability": {
            "type": "string",
            "allowed_values": ["str", "dex"],
        }
    }


def test_dm_context_loading_weapon_remains_a_single_attack_affordance(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "goblin1"]
    state.encounter.turn_index = 0
    character = state.characters["pc1"]
    character.actions = []
    character.equipment = ["srd.light_crossbow"]
    character.inventory["srd.crossbow_bolt"] = 2
    state.encounter.combatants["pc1"].status_effects.append(
        {
            "condition": "loading_weapon_used_this_turn",
            "audit": {"weapon_action_id": "srd.light_crossbow_attack"},
        }
    )
    compendium = CompendiumLoader("rules_data").load()

    context = build_context_slice(
        state,
        actor_id="pc1",
        actions=compendium.actions,
        items=compendium.items,
    )

    light_crossbow = next(
        item for item in context.affordances if item["action_id"] == "srd.light_crossbow_attack"
    )
    assert light_crossbow["weapon_mastery_property"] == "Slow"
    assert light_crossbow["optional_params"] == {}


@pytest.mark.parametrize(
    ("item_id", "action_id", "mastery_property", "ammunition_id"),
    [
        ("srd.dagger", "srd.dagger_attack", "Nick", None),
        ("srd.shortbow", "srd.shortbow_attack", "Vex", "srd.arrow"),
        (
            "srd.light_crossbow",
            "srd.light_crossbow_attack",
            "Slow",
            "srd.crossbow_bolt",
        ),
        ("srd.mace", "srd.mace_attack", "Sap", None),
    ],
)
def test_dm_context_registered_weapon_masteries_expose_use_param(
    make_state,
    item_id: str,
    action_id: str,
    mastery_property: str,
    ammunition_id: str | None,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "goblin1"]
    state.encounter.turn_index = 0
    character = state.characters["pc1"]
    character.actions = []
    character.equipment = [item_id]
    character.feature_choices[f"weapon_mastery.{item_id}"] = mastery_property
    if ammunition_id is not None:
        character.inventory[ammunition_id] = 1
    compendium = CompendiumLoader("rules_data").load()

    context = build_context_slice(
        state,
        actor_id="pc1",
        actions=compendium.actions,
        items=compendium.items,
    )

    affordance = next(item for item in context.affordances if item["action_id"] == action_id)
    assert affordance["weapon_mastery_property"] == mastery_property
    assert affordance["optional_params"]["use_weapon_mastery"] == {"type": "boolean"}


def test_dm_context_exposes_registered_nick_light_extra_attack_after_first_light_attack(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "goblin1"]
    state.encounter.turn_index = 0
    state.encounter.action_budgets["pc1"] = {
        "action": 0,
        "bonus_action": 1,
        "reaction": 1,
        "movement": 30,
        "movement_used": 0,
        "free": 1,
    }
    character = state.characters["pc1"]
    character.actions = []
    character.equipment = ["srd.shortsword", "srd.dagger"]
    character.feature_choices["weapon_mastery.srd.dagger"] = "Nick"
    state.encounter.combatants["pc1"].status_effects.append(
        {
            "condition": "light_weapon_attack_this_turn",
            "audit": {"weapon_item_id": "srd.shortsword"},
        }
    )
    compendium = CompendiumLoader("rules_data").load()

    context = build_context_slice(
        state,
        actor_id="pc1",
        actions=compendium.actions,
        items=compendium.items,
    )

    dagger = next(item for item in context.affordances if item["action_id"] == "srd.dagger_attack")
    assert dagger["light_extra_attack_economy"] == "none"
    assert dagger["optional_params"]["use_light_extra_attack"] == {
        "type": "boolean",
        "required_value": True,
    }
    assert dagger["optional_params"]["use_weapon_mastery"] == {"type": "boolean"}
    assert not any(item["action_id"] == "srd.shortsword_attack" for item in context.affordances)


def test_dm_context_shows_step_of_the_wind_during_fleet_step_window(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "pc2", "goblin1"]
    state.encounter.turn_index = 0
    character = state.characters["pc1"]
    character.class_levels = {"monk": 11}
    character.subclasses = {"monk": "open_hand"}
    character.actions.extend(["srd.step_of_the_wind", "srd.fleet_step"])
    state.encounter.action_budgets["pc1"] = {
        "action": 1,
        "bonus_action": 0,
        "reaction": 1,
        "movement": 30,
        "movement_used": 0,
        "free": 1,
    }
    state.encounter.combatants["pc1"].status_effects.append(
        {
            "effect_id": "fleet-step-window",
            "source_ref": "SRD 5.2.1",
            "source_action_id": "srd.fleet_step",
            "target_id": "pc1",
            "applied_by": "pc1",
            "condition": "fleet_step_available",
            "duration": {"until": "end_of_current_turn"},
            "tick_on": "self_turn_end",
        }
    )
    compendium = CompendiumLoader("rules_data").load()

    context = build_context_slice(state, actor_id="pc1", actions=compendium.actions)

    assert any(item["action_id"] == "srd.step_of_the_wind" for item in context.affordances)


def test_dm_context_exploration_keeps_affordances_lazy(make_state) -> None:
    state = make_state()
    state.encounter = None
    compendium = CompendiumLoader("rules_data").load()

    context = build_context_slice(state, actor_id="pc1", actions=compendium.actions)

    assert context.mode == "exploration"
    assert context.affordances == []


def test_dm_context_affordance_targets_respect_range(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "goblin1"]
    state.encounter.turn_index = 0
    state.encounter.combatants["goblin1"].position_node_id = "back"
    compendium = CompendiumLoader("rules_data").load()

    context = build_context_slice(state, actor_id="pc1", actions=compendium.actions)

    shortsword = next(
        item for item in context.affordances if item["action_id"] == "srd.shortsword_attack"
    )
    assert shortsword["candidate_target_ids"] == []


def test_dm_context_respects_exact_hp_display_strategy_without_raw_fields(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.config.hp_display_strategy = "exact"
    state.encounter.combatants["pc1"].hp_current = 10
    state.encounter.combatants["pc1"].hp_max = 12
    compendium = CompendiumLoader("rules_data").load()

    context = build_context_slice(state, actor_id="pc1", actions=compendium.actions)
    messages = build_dm_messages(context, "DD 我查看状态")
    serialized = repr(messages)

    assert context.visible_state["encounter"]["combatants"]["pc1"]["hp"] == "10/12"
    assert "hp_current" not in serialized
    assert "hp_max" not in serialized


def test_dm_context_injects_retrieved_public_memory_only(make_state) -> None:
    state = make_state()
    compendium = CompendiumLoader("rules_data").load()
    remember_fragment(
        state,
        text="Old Mara knows the windmill password: blue lantern.",
        tags=["mara", "windmill"],
    )
    remember_fragment(
        state,
        text="Hidden goblin AC is 17.",
        tags=["goblin"],
        visibility="gm",
    )

    context = build_context_slice(
        state,
        actor_id="pc1",
        actions=compendium.actions,
        query="Ask Mara about the windmill password.",
    )
    messages = build_dm_messages(context, "DD 我询问 Mara 风车口令")
    serialized = repr(messages)

    assert context.memory_fragments
    assert "blue lantern" in serialized
    assert "Hidden goblin AC" not in serialized
    assert "'armor_class': 16" not in serialized


def test_dm_context_filters_hidden_world_flags_and_effect_audit_fields(make_state) -> None:
    state = make_state()
    state.world.flags["campaign_rewards"] = {
        "starter.first_victory": {
            "gold": 12,
            "experience": 50,
            "items": [{"item_id": "srd.potion_of_healing", "quantity": 1}],
        }
    }
    state.world.flags["dc_table"] = {"secret_door": 20}
    state.world.flags["dynamic_zones"] = {"dock": {"name": "码头"}}
    state.world.active_effects.append(
        {
            "effect_id": "world-effect-secret",
            "source_action_id": "srd.detect_magic",
            "effect_type": "detect_magic_aura",
            "scope": {"zone_id": "start"},
            "duration": {"minutes": 10},
            "metadata": {"school": "divination"},
            "audit": {"node_path": "automation[1]"},
        }
    )
    compendium = CompendiumLoader("rules_data").load()

    context = build_context_slice(state, actor_id="pc1", actions=compendium.actions)
    messages = build_dm_messages(context, "DD 我环顾四周")
    serialized = repr(messages)

    assert context.visible_state["world"]["flags"] == {"dynamic_zones": {"dock": {"name": "码头"}}}
    assert "starter.first_victory" not in serialized
    assert "srd.potion_of_healing" not in serialized
    assert "secret_door" not in serialized
    assert "world-effect-secret" not in serialized
    assert "source_action_id" not in serialized
    assert "node_path" not in serialized
    assert "detect_magic_aura" in serialized

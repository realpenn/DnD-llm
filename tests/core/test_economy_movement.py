from __future__ import annotations

import pytest

from dnd_llm.core.automation.executor import AutomationError
from dnd_llm.core.compendium.loader import CompendiumLoader
from dnd_llm.core.persistence import AuditLog
from dnd_llm.core.tools import EngineTools


def test_direct_tool_calls_spend_action_budget_and_honor_idempotency(make_state) -> None:
    state = make_state()
    compendium = CompendiumLoader("rules_data").load()
    audit = AuditLog()
    tools = EngineTools(state, compendium, audit)

    first = tools.attack("pc1", "goblin1", "srd.shortsword_attack", idempotency_key="atk-1")
    roll_counter_after_first = state.roll_counter
    repeated = tools.attack("pc1", "goblin1", "srd.shortsword_attack", idempotency_key="atk-1")

    assert repeated == first
    assert state.roll_counter == roll_counter_after_first
    with pytest.raises(AutomationError, match="not enough action budget"):
        tools.attack("pc1", "goblin1", "srd.shortsword_attack", idempotency_key="atk-2")


def test_combat_movement_uses_tactical_graph_budget_and_opportunity_triggers(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["pc1"].speed_ft = 60
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.move("pc1", to_position_node_id="back", idempotency_key="move-1")
    move_change = [change for change in result["state_changes"] if change["type"] == "move"][0]

    assert state.encounter.combatants["pc1"].position_node_id == "back"
    assert move_change["movement_cost"] == 35
    assert move_change["opportunity_attack_triggers"] == ["goblin1"]
    assert state.encounter.action_budgets["pc1"]["movement"] == 25
    assert state.encounter.action_budgets["pc1"]["movement_used"] == 35


def test_barbarian_fast_movement_increases_combat_movement_without_heavy_armor(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"barbarian": 5}
    state.characters["pc1"].equipment = []
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.move("pc1", to_position_node_id="back", idempotency_key="fast-move")

    move_change = [change for change in result["state_changes"] if change["type"] == "move"][0]
    assert state.encounter.combatants["pc1"].position_node_id == "back"
    assert move_change["movement_cost"] == 35
    assert state.encounter.action_budgets["pc1"]["movement"] == 5
    assert state.encounter.action_budgets["pc1"]["movement_used"] == 35


def test_barbarian_fast_movement_does_not_apply_while_wearing_heavy_armor(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"barbarian": 5}
    state.characters["pc1"].equipment = ["srd.chain_mail"]
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="not enough movement budget"):
        tools.move("pc1", to_position_node_id="back", idempotency_key="heavy-fast-move")

    assert state.encounter.combatants["pc1"].position_node_id == "front"
    assert state.encounter.action_budgets["pc1"]["movement"] == 30
    assert state.encounter.action_budgets["pc1"]["movement_used"] == 0


def test_monk_unarmored_movement_increases_combat_movement_without_armor_or_shield(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"monk": 2}
    state.characters["pc1"].equipment = []
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.move("pc1", to_position_node_id="back", idempotency_key="monk-move")

    move_change = [change for change in result["state_changes"] if change["type"] == "move"][0]
    assert state.encounter.combatants["pc1"].position_node_id == "back"
    assert move_change["movement_cost"] == 35
    assert state.encounter.action_budgets["pc1"]["movement"] == 5
    assert state.encounter.action_budgets["pc1"]["movement_used"] == 35


@pytest.mark.parametrize("equipment", [["srd.leather_armor"], ["srd.shield"]])
def test_monk_unarmored_movement_does_not_apply_with_armor_or_shield(
    make_state,
    equipment: list[str],
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"monk": 2}
    state.characters["pc1"].equipment = equipment
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="not enough movement budget"):
        tools.move("pc1", to_position_node_id="back", idempotency_key="armored-monk-move")

    assert state.encounter.combatants["pc1"].position_node_id == "front"
    assert state.encounter.action_budgets["pc1"]["movement"] == 30
    assert state.encounter.action_budgets["pc1"]["movement_used"] == 0


def test_exhaustion_reduces_combat_movement_budget(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["pc1"].speed_ft = 40
    state.characters["pc1"].status_effects.append(
        {"effect_id": "exhaustion-test", "condition": "exhaustion", "level": 2}
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="not enough movement budget"):
        tools.move("pc1", to_position_node_id="back", idempotency_key="move-exhausted")

    assert state.encounter.combatants["pc1"].position_node_id == "front"


def test_exploration_movement_must_follow_zone_edges(make_state) -> None:
    state = make_state()
    state.encounter = None
    state.world.zone_edges = {"start": ["ruins"], "ruins": ["start"]}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.move("pc1", to_zone_id="ruins", idempotency_key="zone-1")

    assert result["success"] is True
    assert state.characters["pc1"].zone_id == "ruins"
    assert state.world.current_zone_id == "ruins"
    with pytest.raises(ValueError, match="not connected"):
        tools.move("pc1", to_zone_id="vault", idempotency_key="zone-2")

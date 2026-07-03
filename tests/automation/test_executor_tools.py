from __future__ import annotations

import re

import pytest

from dnd_llm.core.automation.definitions import ActionDefinition
from dnd_llm.core.automation.executor import AutomationError, AutomationExecutor
from dnd_llm.core.compendium.loader import CompendiumLoader
from dnd_llm.core.dice import RollDie, RollResult, RollService
from dnd_llm.core.effect_lifecycle import tick_effects
from dnd_llm.core.models import Combatant, Monster
from dnd_llm.core.persistence import AuditLog
from dnd_llm.core.resolver import ActionResolver, PlayerActionDraft
from dnd_llm.core.rules.class_features import (
    second_story_work_climb_speed,
    second_story_work_jump_ability,
)
from dnd_llm.core.rules.conditions import (
    can_hover_from_effects,
    can_walk_on_liquid_surface_from_effects,
    darkvision_range_from_effects,
    effective_speed,
    fly_speed_from_effects,
    swim_speed_from_effects,
    truesight_range_from_effects,
    xray_vision_range_from_effects,
)
from dnd_llm.core.tools import EngineTools
from dnd_llm.orchestrator.turn import roll_initiative


class _FixedSingleDieRollService:
    def __init__(self, values: list[int]) -> None:
        self.values = values
        self.counter = 0

    def roll(self, expression: str, advantage: str | None = None) -> RollResult:
        modifier = 0
        total = 0
        dice: list[RollDie] = []
        for match in re.finditer(
            r"([+-]?)(?:(\d*)d(\d+)|(\d+))",
            expression.replace(" ", ""),
            re.IGNORECASE,
        ):
            sign = -1 if match.group(1) == "-" else 1
            if match.group(3):
                value = self.values.pop(0)
                sides = int(match.group(3))
                die = RollDie(sides=sides, value=value, kept=True)
                dice.append(die)
                total += sign * value
            else:
                value = sign * int(match.group(4))
                modifier += value
                total += value
        counter = self.counter
        self.counter += 1
        return RollResult(
            roll_id=f"fixed-{counter}",
            expression=expression,
            seed=0,
            counter=counter,
            advantage=advantage,
            dice=dice,
            modifier_total=modifier,
            total=total,
            display=f"{expression}: fixed => {total}",
        )


def test_cure_wounds_changes_hp_and_writes_audit(make_state) -> None:
    state = make_state()
    compendium = CompendiumLoader("rules_data").load()
    audit = AuditLog()
    tools = EngineTools(state, compendium, audit)

    result = tools.cast_spell("pc1", "srd.cure_wounds", ["pc2"], 1)

    assert result["success"] is True
    assert state.characters["pc1"].spell_slots["1"] == 0
    assert state.encounter is not None
    assert state.encounter.combatants["pc2"].hp_current > 4
    assert audit.events
    assert all(event.event_id.startswith("event-") for event in audit.events)


def test_life_domain_disciple_of_life_adds_spell_slot_healing(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"cleric": 3}
    state.characters["pc1"].subclasses = {"cleric": "life"}
    state.characters["pc1"].actions.append("srd.disciple_of_life")
    state.characters["pc2"].hp_current = 1
    state.characters["pc2"].hp_max = 20
    state.encounter.combatants["pc2"].hp_current = 1
    state.encounter.combatants["pc2"].hp_max = 20
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell("pc1", "srd.cure_wounds", ["pc2"], 1)

    assert result["success"] is True
    healing_change = next(
        change for change in result["state_changes"] if change["type"] == "healing"
    )
    assert healing_change["amount"] == result["dice_rolls"][0]["total"] + 3
    assert healing_change["disciple_of_life_bonus"] == 3
    assert healing_change["disciple_of_life_source"] == "srd.disciple_of_life"


def test_life_domain_blessed_healer_heals_self_after_spell_slot_heals_other(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"cleric": 6}
    caster.subclasses = {"cleric": "life"}
    caster.actions.extend(["srd.disciple_of_life", "srd.blessed_healer"])
    caster.spell_slots["2"] = 1
    state.encounter.combatants["pc1"].hp_current = 2
    state.encounter.combatants["pc1"].hp_max = 20
    state.encounter.combatants["pc2"].hp_current = 1
    state.encounter.combatants["pc2"].hp_max = 20
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell("pc1", "srd.cure_wounds", ["pc2"], 2)

    assert result["success"] is True
    healing_changes = [change for change in result["state_changes"] if change["type"] == "healing"]
    target_healing = next(change for change in healing_changes if change["target_id"] == "pc2")
    self_healing = next(change for change in healing_changes if change.get("blessed_healer_source"))
    assert target_healing["disciple_of_life_bonus"] == 4
    assert target_healing["amount"] == result["dice_rolls"][0]["total"] + 4
    assert self_healing == {
        "type": "healing",
        "target_id": "pc1",
        "amount": 4,
        "applied": 4,
        "blessed_healer_bonus": 4,
        "blessed_healer_source": "srd.blessed_healer",
        "path": "automation[1]",
    }
    assert state.encounter.combatants["pc1"].hp_current == 6


def test_life_domain_blessed_healer_does_not_trigger_on_self_only_healing(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"cleric": 6}
    caster.subclasses = {"cleric": "life"}
    caster.actions.extend(["srd.disciple_of_life", "srd.blessed_healer"])
    caster.spell_slots["1"] = 1
    state.encounter.combatants["pc1"].hp_current = 2
    state.encounter.combatants["pc1"].hp_max = 20
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell("pc1", "srd.cure_wounds", ["pc1"], 1)

    assert result["success"] is True
    assert not any(change.get("blessed_healer_source") for change in result["state_changes"])


def test_non_life_cleric_cure_wounds_does_not_gain_disciple_of_life(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"cleric": 3}
    state.characters["pc2"].hp_current = 1
    state.encounter.combatants["pc2"].hp_current = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell("pc1", "srd.cure_wounds", ["pc2"], 1)

    assert result["success"] is True
    healing_change = next(
        change for change in result["state_changes"] if change["type"] == "healing"
    )
    assert healing_change["amount"] == result["dice_rolls"][0]["total"]
    assert "disciple_of_life_bonus" not in healing_change


def test_wizard_ritual_adept_casts_spellbook_ritual_without_spell_slot(make_state) -> None:
    state = make_state()
    caster = state.characters["pc1"]
    caster.class_levels = {"wizard": 1}
    caster.actions = ["srd.detect_magic", "srd.ritual_adept"]
    caster.known_spells = ["srd.spell.detect_magic"]
    caster.prepared_spells = []
    caster.spell_slots = {"1": 0}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell("pc1", "srd.detect_magic", [], 1, as_ritual=True)

    assert result["success"] is True
    assert caster.spell_slots["1"] == 0
    ritual_change = next(
        change for change in result["state_changes"] if change["type"] == "ritual_casting"
    )
    assert ritual_change == {
        "type": "ritual_casting",
        "actor_id": "pc1",
        "spell_id": "srd.spell.detect_magic",
        "base_spell_slot_level": 1,
        "spell_slot_expended": False,
        "casting_time_extra_minutes": 10,
        "source": "wizard_spellbook",
    }


def test_ritual_casting_requires_ritual_tag_and_spellbook_or_prepared_spell(make_state) -> None:
    state = make_state()
    caster = state.characters["pc1"]
    caster.class_levels = {"wizard": 1}
    caster.actions = ["srd.magic_missile", "srd.detect_magic", "srd.ritual_adept"]
    caster.spell_slots = {"1": 0}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    caster.known_spells = ["srd.spell.magic_missile"]
    with pytest.raises(AutomationError, match="Ritual tag"):
        tools.cast_spell("pc1", "srd.magic_missile", ["goblin1"], 1, as_ritual=True)

    caster.known_spells = []
    with pytest.raises(AutomationError, match="spellbook"):
        tools.cast_spell("pc1", "srd.detect_magic", [], 1, as_ritual=True)

    caster.known_spells = ["srd.spell.detect_magic"]
    with pytest.raises(AutomationError, match="higher level"):
        tools.cast_spell("pc1", "srd.detect_magic", [], 2, as_ritual=True)


def test_prepared_ritual_spell_can_be_cast_as_ritual_without_wizard_feature(make_state) -> None:
    state = make_state()
    caster = state.characters["pc1"]
    caster.class_levels = {"cleric": 1}
    caster.actions = ["srd.detect_magic"]
    caster.known_spells = []
    caster.prepared_spells = ["srd.spell.detect_magic"]
    caster.spell_slots = {"1": 0}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell("pc1", "srd.detect_magic", [], 1, as_ritual=True)

    assert result["success"] is True
    ritual_change = next(
        change for change in result["state_changes"] if change["type"] == "ritual_casting"
    )
    assert ritual_change["source"] == "prepared_spell"
    assert caster.spell_slots["1"] == 0


def test_resolver_accepts_wizard_ritual_without_spell_slot(make_state) -> None:
    state = make_state()
    caster = state.characters["pc1"]
    caster.class_levels = {"wizard": 1}
    caster.actions = ["srd.detect_magic", "srd.ritual_adept"]
    caster.known_spells = ["srd.spell.detect_magic"]
    caster.spell_slots = {"1": 0}
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions, compendium.items)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="cast_spell",
            candidate_action_id="srd.detect_magic",
            params={"slot_level": 1, "as_ritual": True},
        )
    )

    assert result.status == "accepted"
    assert result.action_id == "srd.detect_magic"


def test_life_domain_preserve_life_heals_bloodied_target_to_half_hp(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"cleric": 3}
    state.characters["pc1"].subclasses = {"cleric": "life"}
    state.characters["pc1"].actions.append("srd.preserve_life")
    state.characters["pc1"].resources["srd.resource.channel_divinity"] = 2
    state.characters["pc2"].hp_current = 1
    state.characters["pc2"].hp_max = 8
    state.encounter.combatants["pc2"].hp_current = 1
    state.encounter.combatants["pc2"].hp_max = 8
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.preserve_life",
        ["pc2"],
        {"preserve_life_points": {"pc2": 3}},
        idempotency_key="preserve-life",
    )

    assert result["success"] is True
    assert state.characters["pc1"].resources["srd.resource.channel_divinity"] == 1
    assert state.encounter.action_budgets["pc1"]["action"] == 0
    assert state.encounter.combatants["pc2"].hp_current == 4
    healing_change = next(
        change for change in result["state_changes"] if change["type"] == "healing"
    )
    assert healing_change["amount"] == 3
    assert healing_change["applied"] == 3
    assert healing_change["preserve_life_cap"] == 4
    assert healing_change["source_action_id"] == "srd.preserve_life"


def test_life_domain_preserve_life_rejects_healing_above_half_before_cost(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"cleric": 3}
    state.characters["pc1"].subclasses = {"cleric": "life"}
    state.characters["pc1"].actions.append("srd.preserve_life")
    state.characters["pc1"].resources["srd.resource.channel_divinity"] = 2
    state.characters["pc2"].hp_current = 1
    state.characters["pc2"].hp_max = 8
    state.encounter.combatants["pc2"].hp_current = 1
    state.encounter.combatants["pc2"].hp_max = 8
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="above half HP"):
        tools.perform_action(
            "pc1",
            "srd.preserve_life",
            ["pc2"],
            {"preserve_life_points": {"pc2": 4}},
            idempotency_key="preserve-life-too-much",
        )

    assert state.characters["pc1"].resources["srd.resource.channel_divinity"] == 2
    budget = state.encounter.action_budgets.get("pc1")
    assert budget is None or budget["action"] == 1
    assert state.encounter.combatants["pc2"].hp_current == 1


def test_land_druid_lands_aid_deals_save_half_necrotic_and_heals_area_target(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"druid": 3}
    state.characters["pc1"].subclasses = {"druid": "land"}
    state.characters["pc1"].abilities["wis"] = 16
    state.characters["pc1"].actions.append("srd.lands_aid")
    state.characters["pc1"].resources["srd.resource.wild_shape"] = 2
    state.encounter.combatants["pc2"].hp_current = 2
    state.encounter.combatants["pc2"].hp_max = 8
    state.encounter.combatants["goblin1"].hp_current = 7
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([20, 6, 5]),  # save, damage, healing
    )

    result = tools.perform_action(
        "pc1",
        "srd.lands_aid",
        ["goblin1"],
        {
            "lands_aid_area_target_ids": ["goblin1", "pc2"],
            "lands_aid_healing_target_id": "pc2",
        },
        idempotency_key="lands-aid",
    )

    assert result["success"] is True
    assert state.characters["pc1"].resources["srd.resource.wild_shape"] == 1
    assert state.encounter.action_budgets["pc1"]["action"] == 0
    assert state.encounter.combatants["goblin1"].hp_current == 4
    assert state.encounter.combatants["pc2"].hp_current == 7
    save_result = result["node_results"]["automation[1]"]
    assert save_result["ability"] == "con"
    assert save_result["dc"] == 13
    assert save_result["dc_source"] == "spell_save_dc:druid"
    assert save_result["success"] is True
    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert damage_change["target_id"] == "goblin1"
    assert damage_change["amount"] == 3
    assert damage_change["damage_type"] == "necrotic"
    healing_change = next(
        change for change in result["state_changes"] if change["type"] == "healing"
    )
    assert healing_change["target_id"] == "pc2"
    assert healing_change["amount"] == 5
    assert healing_change["applied"] == 5


def test_land_druid_lands_aid_rejects_healing_target_outside_area_before_cost(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"druid": 3}
    state.characters["pc1"].subclasses = {"druid": "land"}
    state.characters["pc1"].actions.append("srd.lands_aid")
    state.characters["pc1"].resources["srd.resource.wild_shape"] = 2
    state.encounter.combatants["pc2"].hp_current = 2
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1, 6, 5]),
    )

    with pytest.raises(AutomationError, match="healing target must be in the area"):
        tools.perform_action(
            "pc1",
            "srd.lands_aid",
            ["goblin1"],
            {
                "lands_aid_area_target_ids": ["goblin1"],
                "lands_aid_healing_target_id": "pc2",
            },
            idempotency_key="lands-aid-outside-area",
        )

    assert state.characters["pc1"].resources["srd.resource.wild_shape"] == 2
    budget = state.encounter.action_budgets.get("pc1")
    assert budget is None or budget["action"] == 1
    assert state.encounter.combatants["pc2"].hp_current == 2


def test_fiend_warlock_dark_ones_blessing_grants_temp_hp_on_own_kill(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"warlock": 3}
    state.characters["pc1"].subclasses = {"warlock": "fiend"}
    state.characters["pc1"].abilities["cha"] = 16
    state.characters["pc1"].actions.append("srd.dark_ones_blessing")
    state.encounter.combatants["goblin1"].hp_current = 1
    state.encounter.combatants["goblin1"].position_node_id = "back"
    damage_action = _fixed_damage_action("test.fiend_kill", amount=1)

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        damage_action,
        actor_id="pc1",
        targets=["goblin1"],
        idempotency_key="fiend-own-kill",
    )

    assert state.encounter.combatants["goblin1"].hp_current == 0
    assert state.characters["pc1"].temp_hp == 6
    assert state.encounter.combatants["pc1"].temp_hp == 6
    blessing = next(
        change
        for change in result.state_changes
        if change.get("source_action_id") == "srd.dark_ones_blessing"
    )
    assert blessing["amount"] == 6
    assert blessing["reducer_id"] == "pc1"
    assert blessing["reduced_enemy_id"] == "goblin1"


def test_fiend_warlock_dark_ones_blessing_triggers_on_nearby_ally_kill(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"warlock": 3}
    state.characters["pc1"].subclasses = {"warlock": "fiend"}
    state.characters["pc1"].abilities["cha"] = 16
    state.characters["pc1"].actions.append("srd.dark_ones_blessing")
    state.encounter.combatants["pc1"].position_node_id = "front"
    state.encounter.combatants["pc2"].position_node_id = "front"
    state.encounter.combatants["goblin1"].position_node_id = "cover"
    state.encounter.combatants["goblin1"].hp_current = 1
    damage_action = _fixed_damage_action("test.ally_kill_near_fiend", amount=1)

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        damage_action,
        actor_id="pc2",
        targets=["goblin1"],
        idempotency_key="fiend-nearby-ally-kill",
    )

    assert state.characters["pc1"].temp_hp == 6
    blessing = next(
        change
        for change in result.state_changes
        if change.get("source_action_id") == "srd.dark_ones_blessing"
    )
    assert blessing["target_id"] == "pc1"
    assert blessing["reducer_id"] == "pc2"


def test_fiend_warlock_dark_ones_blessing_ignores_distant_ally_kill(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"warlock": 3}
    state.characters["pc1"].subclasses = {"warlock": "fiend"}
    state.characters["pc1"].abilities["cha"] = 16
    state.characters["pc1"].actions.append("srd.dark_ones_blessing")
    state.encounter.combatants["pc1"].position_node_id = "front"
    state.encounter.combatants["pc2"].position_node_id = "front"
    state.encounter.combatants["goblin1"].position_node_id = "back"
    state.encounter.combatants["goblin1"].hp_current = 1
    damage_action = _fixed_damage_action("test.ally_kill_far_from_fiend", amount=1)

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        damage_action,
        actor_id="pc2",
        targets=["goblin1"],
        idempotency_key="fiend-distant-ally-kill",
    )

    assert state.characters["pc1"].temp_hp == 0
    assert not any(
        change.get("source_action_id") == "srd.dark_ones_blessing"
        for change in result.state_changes
    )


def test_use_item_consumes_inventory_without_spending_spell_slot(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].inventory["srd.potion_of_healing"] = 1
    state.characters["pc1"].hp_current = 5
    state.encounter.combatants["pc1"].hp_current = 5
    compendium = CompendiumLoader("rules_data").load()
    audit = AuditLog()
    tools = EngineTools(state, compendium, audit)

    result = tools.use_item(
        "pc1",
        "srd.potion_of_healing",
        ["pc1"],
        idempotency_key="use-potion",
    )
    repeated = tools.use_item(
        "pc1",
        "srd.potion_of_healing",
        ["pc1"],
        idempotency_key="use-potion",
    )

    assert repeated == result
    assert result["action_id"] == "srd.use_potion_of_healing"
    assert state.characters["pc1"].inventory["srd.potion_of_healing"] == 0
    assert state.characters["pc1"].spell_slots["1"] == 1
    assert state.encounter.combatants["pc1"].hp_current > 5
    assert any(
        change["type"] == "cost"
        and change["resource"] == "srd.potion_of_healing"
        and change["after"] == 0
        for change in result["state_changes"]
    )


def test_use_item_rejects_unknown_item_id_without_action_fallback(make_state) -> None:
    state = make_state()
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(KeyError, match="unknown item"):
        tools.use_item(
            "pc1",
            "srd.fireball",
            ["goblin1"],
            idempotency_key="item-action-fallback",
        )

    assert state.characters["pc1"].spell_slots["1"] == 1
    assert state.encounter is not None
    assert state.encounter.combatants["goblin1"].hp_current == 7


def test_fast_hands_magic_item_rejects_item_that_is_already_bonus_action(
    make_state,
) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"rogue": 3}
    character.subclasses = {"rogue": "thief"}
    character.actions.append("srd.fast_hands_magic_item")
    character.inventory["srd.potion_of_healing"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(ValueError, match="normally uses an action"):
        tools.use_item(
            "pc1",
            "srd.potion_of_healing",
            ["pc1"],
            fast_hands=True,
            idempotency_key="fast-hands-potion",
        )

    assert character.inventory["srd.potion_of_healing"] == 1


def test_second_wind_spends_class_resource_and_heals_by_fighter_level(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].actions.append("srd.second_wind")
    state.characters["pc1"].resources["srd.resource.second_wind"] = 2
    state.characters["pc1"].hp_current = 1
    state.encounter.combatants["pc1"].hp_current = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action("pc1", "srd.second_wind", [], idempotency_key="second-wind")

    assert result["success"] is True
    assert state.characters["pc1"].resources["srd.resource.second_wind"] == 1
    assert state.encounter.combatants["pc1"].hp_current == 12
    healing_change = next(
        change for change in result["state_changes"] if change["type"] == "healing"
    )
    assert healing_change["amount"] == 11
    assert healing_change["applied"] == 11
    assert result["dice_rolls"][0]["expression"] == "1d10"


def test_second_wind_tactical_shift_moves_half_speed_without_opportunity_attack(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"fighter": 5}
    state.characters["pc1"].actions.append("srd.second_wind")
    state.characters["pc1"].resources["srd.resource.second_wind"] = 3
    state.characters["pc1"].hp_current = 1
    state.characters["pc1"].hp_max = 30
    state.encounter.combatants["pc1"].hp_current = 1
    state.encounter.combatants["pc1"].hp_max = 30
    state.encounter.combatants["pc1"].speed_ft = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.second_wind",
        [],
        params={"tactical_shift_to_position_node_id": "back"},
        idempotency_key="second-wind-tactical-shift",
    )

    move_change = next(
        change
        for change in result["state_changes"]
        if change["type"] == "move" and change.get("feature") == "tactical_shift"
    )
    assert result["success"] is True
    assert state.characters["pc1"].resources["srd.resource.second_wind"] == 2
    assert state.encounter.combatants["pc1"].position_node_id == "back"
    assert move_change["movement_cost"] == 35
    assert move_change["movement_limit"] == 40
    assert move_change["opportunity_attack_triggers"] == []
    assert state.encounter.action_budgets["pc1"]["movement"] == 80
    assert state.encounter.action_budgets["pc1"]["movement_used"] == 35


def test_second_wind_tactical_shift_rejects_over_half_speed_before_spending(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"fighter": 5}
    state.characters["pc1"].actions.append("srd.second_wind")
    state.characters["pc1"].resources["srd.resource.second_wind"] = 1
    state.encounter.combatants["pc1"].speed_ft = 30
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="cannot exceed half Speed"):
        tools.perform_action(
            "pc1",
            "srd.second_wind",
            [],
            params={"tactical_shift_to_position_node_id": "back"},
            idempotency_key="second-wind-tactical-shift-too-far",
        )

    assert state.characters["pc1"].resources["srd.resource.second_wind"] == 1
    assert state.encounter.action_budgets["pc1"]["bonus_action"] == 1
    assert state.encounter.combatants["pc1"].position_node_id == "front"


def test_second_wind_tactical_shift_requires_fighter_level_five_before_spending(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"fighter": 4}
    state.characters["pc1"].actions.append("srd.second_wind")
    state.characters["pc1"].resources["srd.resource.second_wind"] = 1
    state.encounter.combatants["pc1"].speed_ft = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="requires Fighter level 5"):
        tools.perform_action(
            "pc1",
            "srd.second_wind",
            [],
            params={"tactical_shift_to_position_node_id": "back"},
            idempotency_key="second-wind-tactical-shift-too-low",
        )

    assert state.characters["pc1"].resources["srd.resource.second_wind"] == 1
    assert state.encounter.action_budgets["pc1"]["bonus_action"] == 1
    assert state.encounter.combatants["pc1"].position_node_id == "front"


def test_action_surge_spends_class_resource_and_adds_action_budget(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"fighter": 2}
    state.characters["pc1"].actions.append("srd.action_surge")
    state.characters["pc1"].resources["srd.resource.action_surge"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action("pc1", "srd.action_surge", [], idempotency_key="action-surge")

    assert result["success"] is True
    assert state.characters["pc1"].resources["srd.resource.action_surge"] == 0
    assert state.encounter is not None
    assert state.encounter.action_budgets["pc1"]["action"] == 2
    assert any(
        change["type"] == "resource_delta"
        and change["resource"] == "budget.action"
        and change["after"] == 2
        for change in result["state_changes"]
    )


def test_action_surge_can_be_used_twice_per_rest_but_once_per_turn_at_level_17(
    make_state,
) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"fighter": 17}
    state.characters["pc1"].actions.append("srd.action_surge")
    state.characters["pc1"].resources["srd.resource.action_surge"] = 2
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    first = tools.perform_action(
        "pc1",
        "srd.action_surge",
        [],
        idempotency_key="action-surge-level-17-first",
    )

    assert first["success"] is True
    assert state.characters["pc1"].resources["srd.resource.action_surge"] == 1
    assert any(
        change["type"] == "action_surge_used" and change["source_action_id"] == "srd.action_surge"
        for change in first["state_changes"]
    )

    with pytest.raises(AutomationError, match="Action Surge already used this turn"):
        tools.perform_action(
            "pc1",
            "srd.action_surge",
            [],
            idempotency_key="action-surge-level-17-same-turn",
        )
    assert state.characters["pc1"].resources["srd.resource.action_surge"] == 1

    lifecycle = tick_effects(state, trigger="self_turn_start", actor_id="pc1")
    assert lifecycle.expired[0]["condition"] == "action_surge_used"

    second = tools.perform_action(
        "pc1",
        "srd.action_surge",
        [],
        idempotency_key="action-surge-level-17-second",
    )

    assert second["success"] is True
    assert state.characters["pc1"].resources["srd.resource.action_surge"] == 0


def test_bardic_inspiration_spends_resource_and_applies_scaled_die(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"bard": 5}
    state.characters["pc1"].abilities["cha"] = 16
    state.characters["pc1"].actions.append("srd.bardic_inspiration")
    state.characters["pc1"].resources["srd.resource.bardic_inspiration"] = 3
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.bardic_inspiration",
        ["pc2"],
        idempotency_key="bardic-inspiration",
    )

    assert result["success"] is True
    assert state.characters["pc1"].resources["srd.resource.bardic_inspiration"] == 2
    assert state.encounter.action_budgets["pc1"]["bonus_action"] == 0
    effect = state.encounter.combatants["pc2"].status_effects[-1]
    assert effect["condition"] == "bardic_inspiration"
    assert effect["passive_modifiers"] == {
        "bardic_inspiration_die": "d8",
        "applies_to": "failed_d20_test",
    }


def test_bardic_inspiration_rejects_self_target_before_spending_resource(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"bard": 1}
    state.characters["pc1"].actions.append("srd.bardic_inspiration")
    state.characters["pc1"].resources["srd.resource.bardic_inspiration"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="target cannot be self"):
        tools.perform_action(
            "pc1",
            "srd.bardic_inspiration",
            ["pc1"],
            idempotency_key="bardic-inspiration-self",
        )

    assert state.characters["pc1"].resources["srd.resource.bardic_inspiration"] == 1
    assert state.encounter.action_budgets == {}


def test_lore_bard_cutting_words_subtracts_bardic_die_and_spends_reaction(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"bard": 3}
    character.subclasses = {"bard": "lore"}
    character.actions.append("srd.cutting_words")
    character.resources["srd.resource.bardic_inspiration"] = 2
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([3]),
    )

    result = tools.perform_action(
        "pc1",
        "srd.cutting_words",
        ["goblin1"],
        {
            "cutting_words_roll_type": "attack_roll",
            "cutting_words_roll_total": 15,
            "cutting_words_target_ac": 14,
        },
        idempotency_key="cutting-words",
    )

    assert result["success"] is True
    assert character.resources["srd.resource.bardic_inspiration"] == 1
    assert state.encounter.action_budgets["pc1"]["reaction"] == 0
    cutting_words = result["node_results"]["automation[1]"]
    assert cutting_words == {
        "target_id": "goblin1",
        "roll_type": "attack_roll",
        "bardic_inspiration_die": "d6",
        "cutting_words_roll": 3,
        "original_total": 15,
        "adjusted_total": 12,
        "success_threshold": 14,
        "success_after": False,
    }


def test_lore_bard_cutting_words_rejects_failed_trigger_before_cost(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"bard": 3}
    character.subclasses = {"bard": "lore"}
    character.actions.append("srd.cutting_words")
    character.resources["srd.resource.bardic_inspiration"] = 2
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([3]),
    )

    with pytest.raises(AutomationError, match="requires a successful roll"):
        tools.perform_action(
            "pc1",
            "srd.cutting_words",
            ["goblin1"],
            {
                "cutting_words_roll_type": "ability_check",
                "cutting_words_roll_total": 11,
                "cutting_words_dc": 12,
            },
            idempotency_key="cutting-words-failed-trigger",
        )

    assert character.resources["srd.resource.bardic_inspiration"] == 2
    assert state.encounter.action_budgets == {}


def test_font_of_inspiration_restores_bardic_inspiration_with_spell_slot(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"bard": 5}
    character.abilities["cha"] = 16
    character.actions.append("srd.font_of_inspiration_restore_bardic_inspiration_slot_1")
    character.resources["srd.resource.bardic_inspiration"] = 2
    character.spell_slots["1"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.font_of_inspiration_restore_bardic_inspiration_slot_1",
        [],
        idempotency_key="font-of-inspiration-restore",
    )

    assert result["success"] is True
    assert character.spell_slots["1"] == 0
    assert character.resources["srd.resource.bardic_inspiration"] == 3
    assert state.encounter.action_budgets == {}
    assert any(
        change["type"] == "resource_delta"
        and change["resource"] == "srd.resource.bardic_inspiration"
        and change["before"] == 2
        and change["after"] == 3
        for change in result["state_changes"]
    )

    character.resources["srd.resource.bardic_inspiration"] = 3
    character.spell_slots["1"] = 1
    with pytest.raises(
        AutomationError,
        match="resource srd.resource.bardic_inspiration would exceed maximum 3",
    ):
        tools.perform_action(
            "pc1",
            "srd.font_of_inspiration_restore_bardic_inspiration_slot_1",
            [],
            idempotency_key="font-of-inspiration-full",
        )

    assert character.spell_slots["1"] == 1
    assert character.resources["srd.resource.bardic_inspiration"] == 3


def test_divine_spark_heal_spends_channel_divinity_and_adds_wisdom_modifier(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"cleric": 2}
    state.characters["pc1"].abilities["wis"] = 16
    state.characters["pc1"].actions.append("srd.divine_spark_heal")
    state.characters["pc1"].resources["srd.resource.channel_divinity"] = 2
    state.characters["pc2"].hp_current = 1
    state.encounter.combatants["pc2"].hp_current = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.divine_spark_heal",
        ["pc2"],
        idempotency_key="divine-spark-heal",
    )

    assert result["success"] is True
    assert state.characters["pc1"].resources["srd.resource.channel_divinity"] == 1
    assert state.encounter.action_budgets["pc1"]["action"] == 0
    healing_change = next(
        change for change in result["state_changes"] if change["type"] == "healing"
    )
    assert result["dice_rolls"][0]["expression"] == "1d8"
    assert healing_change["amount"] == result["dice_rolls"][0]["total"] + 3
    assert healing_change["applied"] == min(7, healing_change["amount"])


def test_divine_spark_radiant_uses_cleric_spell_save_dc_and_half_damage(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"cleric": 2}
    state.characters["pc1"].abilities["wis"] = 16
    state.characters["pc1"].actions.append("srd.divine_spark_radiant")
    state.characters["pc1"].resources["srd.resource.channel_divinity"] = 2
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.divine_spark_radiant",
        ["goblin1"],
        idempotency_key="divine-spark-radiant",
    )

    assert result["success"] is True
    assert state.characters["pc1"].resources["srd.resource.channel_divinity"] == 1
    save_result = result["node_results"]["automation[1]"]
    assert save_result["dc"] == 13
    assert save_result["dc_source"] == "spell_save_dc:cleric"
    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert result["dice_rolls"][1]["expression"] == "1d8"
    assert damage_change["amount"] == result["dice_rolls"][1]["total"] + 3
    expected_applied = (
        damage_change["amount"] // 2 if save_result["success"] else damage_change["amount"]
    )
    assert damage_change["applied"] == expected_applied
    assert damage_change["damage_type"] == "radiant"


def test_turn_undead_rejects_non_undead_target_before_spending_resource(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"cleric": 2}
    state.characters["pc1"].abilities["wis"] = 16
    state.characters["pc1"].actions.append("srd.turn_undead")
    state.characters["pc1"].resources["srd.resource.channel_divinity"] = 2
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="target must be undead"):
        tools.perform_action(
            "pc1",
            "srd.turn_undead",
            ["goblin1"],
            idempotency_key="turn-undead-bad-target",
        )

    assert state.characters["pc1"].resources["srd.resource.channel_divinity"] == 2
    assert state.encounter.action_budgets == {}


def test_turn_undead_applies_failed_save_effects_and_ends_on_damage(make_state) -> None:
    state = make_state()
    state.rng_seed = 7
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"cleric": 2}
    state.characters["pc1"].abilities["wis"] = 16
    state.characters["pc1"].actions.append("srd.turn_undead")
    state.characters["pc1"].resources["srd.resource.channel_divinity"] = 2
    state.encounter.combatants["skeleton1"] = Combatant(
        id="skeleton1",
        entity_id="skeleton1",
        name="Skeleton",
        side="monsters",
        hp_current=13,
        hp_max=13,
        armor_class=14,
        speed_ft=30,
        creature_type="undead",
        abilities={"str": 10, "dex": 16, "con": 15, "int": 6, "wis": 8, "cha": 5},
        position_node_id="cover",
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.turn_undead",
        ["skeleton1"],
        idempotency_key="turn-undead",
    )

    assert result["success"] is True
    assert state.characters["pc1"].resources["srd.resource.channel_divinity"] == 1
    assert state.encounter.action_budgets["pc1"]["action"] == 0
    save_result = result["node_results"]["automation[1]"]
    assert save_result["dc"] == 13
    assert save_result["dc_source"] == "spell_save_dc:cleric"
    assert save_result["success"] is False
    effects = state.encounter.combatants["skeleton1"].status_effects
    assert [effect["condition"] for effect in effects] == [
        "frightened",
        "incapacitated",
        "turned",
    ]
    assert len({effect["effect_id"] for effect in effects}) == 3
    assert all(
        effect["duration"] == {"until": "duration_1_minute", "break_on_damage": True}
        for effect in effects
    )
    assert effects[2]["passive_modifiers"] == {"must_move_away_from_source": True}

    damage_action = ActionDefinition(
        id="test.damage_turned",
        name="Damage Turned",
        localization={"en": "Damage Turned", "zh": "伤害驱散目标", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={"normal_ft": 5},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "damage", "amount": 1, "damage_type": "bludgeoning"},
        ],
    )
    damage = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        damage_action,
        actor_id="pc2",
        targets=["skeleton1"],
        idempotency_key="damage-turned",
    )

    assert state.encounter.combatants["skeleton1"].hp_current == 12
    assert state.encounter.combatants["skeleton1"].status_effects == []
    expired = next(change for change in damage.state_changes if change["type"] == "effect_expired")
    assert expired["target_id"] == "skeleton1"
    assert expired["trigger"] == "damage"
    assert {removed["condition"] for removed in expired["removed"]} == {
        "frightened",
        "incapacitated",
        "turned",
    }


def test_sear_undead_adds_radiant_damage_without_ending_turn_effect(make_state) -> None:
    state = make_state()
    state.rng_seed = 7
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"cleric": 5}
    state.characters["pc1"].abilities["wis"] = 16
    state.characters["pc1"].actions.append("srd.turn_undead")
    state.characters["pc1"].resources["srd.resource.channel_divinity"] = 2
    state.encounter.combatants["skeleton1"] = Combatant(
        id="skeleton1",
        entity_id="skeleton1",
        name="Skeleton",
        side="monsters",
        hp_current=13,
        hp_max=13,
        armor_class=14,
        speed_ft=30,
        creature_type="undead",
        abilities={"str": 10, "dex": 16, "con": 15, "int": 6, "wis": 8, "cha": 5},
        position_node_id="cover",
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.turn_undead",
        ["skeleton1"],
        idempotency_key="sear-undead",
    )

    assert result["node_results"]["automation[1]"]["success"] is False
    assert result["dice_rolls"][1]["expression"] == "3d8"
    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert damage_change["damage_type"] == "radiant"
    assert damage_change["amount"] == result["dice_rolls"][1]["total"]
    assert damage_change["applied"] == min(13, damage_change["amount"])
    assert state.encounter.combatants["skeleton1"].hp_current == 13 - damage_change["applied"]
    assert [
        effect["condition"] for effect in state.encounter.combatants["skeleton1"].status_effects
    ] == ["frightened", "incapacitated", "turned"]
    assert not any(change["type"] == "effect_expired" for change in result["state_changes"])


def test_wild_shape_wolf_spends_resource_adds_temp_hp_and_blocks_spellcasting(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"druid": 2}
    state.characters["pc1"].actions.append("srd.wild_shape_wolf")
    state.characters["pc1"].resources["srd.resource.wild_shape"] = 2
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.wild_shape_wolf",
        [],
        idempotency_key="wild-shape-wolf",
    )

    assert result["success"] is True
    assert state.characters["pc1"].resources["srd.resource.wild_shape"] == 1
    assert state.encounter.action_budgets["pc1"]["bonus_action"] == 0
    assert state.encounter.combatants["pc1"].temp_hp == 2
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["condition"] == "wild_shape"
    assert effect["stacking_policy"] == "replace_condition"
    assert effect["passive_modifiers"]["wild_shape_form"] == "srd.wolf"
    assert effect["passive_modifiers"]["armor_class_override"] == 12
    assert effect["passive_modifiers"]["speed_override_ft"] == 40
    assert effect["passive_modifiers"]["blocks_spellcasting"] is True

    with pytest.raises(AutomationError, match="cannot cast spells"):
        tools.cast_spell("pc1", "srd.cure_wounds", ["pc2"], 1)

    assert state.characters["pc1"].spell_slots["1"] == 1


def test_wild_companion_spends_wild_shape_and_binds_fey_familiar(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"druid": 2}
    state.characters["pc1"].actions.append("srd.wild_companion_wild_shape")
    state.characters["pc1"].resources["srd.resource.wild_shape"] = 2
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.wild_companion_wild_shape",
        [],
        idempotency_key="wild-companion",
    )

    assert result["success"] is True
    assert state.characters["pc1"].resources["srd.resource.wild_shape"] == 1
    effect = state.world.active_effects[-1]
    assert effect["effect_type"] == "familiar_bound"
    assert effect["duration"] == {"until": "long_rest_or_reduced_to_0_hp"}
    assert effect["metadata"] == {
        "spirit_form": True,
        "shares_senses": True,
        "creature_type": "fey",
        "no_material_components": True,
    }


def test_pact_of_the_chain_casts_find_familiar_without_spell_slot(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 1}
    character.feature_choices = {"warlock.eldritch_invocation.pact_of_the_chain": "selected"}
    character.actions.extend(["srd.pact_of_the_chain", "srd.pact_of_the_chain_find_familiar"])
    character.known_spells = ["srd.spell.find_familiar"]
    character.spell_slots = {"1": 1}
    character.spell_slots_max = {"1": 1}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.pact_of_the_chain_find_familiar",
        [],
        idempotency_key="pact-chain-find-familiar",
    )

    assert result["success"] is True
    assert character.spell_slots["1"] == 1
    effect = state.world.active_effects[-1]
    assert effect["effect_type"] == "familiar_bound"
    assert effect["duration"] == {"until": "dismissed_or_reduced_to_0_hp"}
    assert effect["metadata"] == {
        "spirit_form": True,
        "shares_senses": True,
        "pact_of_the_chain": True,
        "can_forgo_attack_for_familiar_reaction": True,
        "special_forms": [
            "imp",
            "pseudodragon",
            "quasit",
            "skeleton",
            "sphinx_of_wonder",
            "sprite",
            "venomous_snake",
        ],
    }


def test_investment_of_chain_master_adds_srd_familiar_metadata(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 5}
    character.feature_choices = {
        "warlock.eldritch_invocation.pact_of_the_chain": "selected",
        "warlock.eldritch_invocation.investment_of_the_chain_master": "selected",
    }
    character.actions.extend(
        [
            "srd.pact_of_the_chain",
            "srd.pact_of_the_chain_find_familiar",
            "srd.investment_of_the_chain_master",
        ]
    )
    character.known_spells = ["srd.spell.find_familiar"]
    character.spell_slots = {"1": 0}
    character.spell_slots_max = {"1": 1}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(
        AutomationError,
        match="Investment of the Chain Master requires investment_familiar_speed fly or swim",
    ):
        tools.perform_action(
            "pc1",
            "srd.pact_of_the_chain_find_familiar",
            [],
            idempotency_key="investment-chain-missing-speed",
        )

    result = tools.perform_action(
        "pc1",
        "srd.pact_of_the_chain_find_familiar",
        [],
        {"investment_familiar_speed": "swim"},
        idempotency_key="investment-chain-find-familiar",
    )

    assert result["success"] is True
    assert character.spell_slots["1"] == 0
    effect = state.world.active_effects[-1]
    assert effect["effect_type"] == "familiar_bound"
    assert effect["metadata"] == {
        "spirit_form": True,
        "shares_senses": True,
        "pact_of_the_chain": True,
        "can_forgo_attack_for_familiar_reaction": True,
        "special_forms": [
            "imp",
            "pseudodragon",
            "quasit",
            "skeleton",
            "sphinx_of_wonder",
            "sprite",
            "venomous_snake",
        ],
        "investment_of_the_chain_master": True,
        "aerial_or_aquatic_speed": "swim",
        "aerial_or_aquatic_speed_ft": 40,
        "quick_attack_bonus_action_command": True,
        "can_convert_bludgeoning_piercing_slashing_to": ["necrotic", "radiant"],
        "uses_warlock_spell_save_dc": True,
        "warlock_reaction_can_grant_resistance": True,
    }


def test_pact_of_the_tome_prepared_ritual_casts_without_spell_slot(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 1}
    character.feature_choices = {
        "warlock.eldritch_invocation.pact_of_the_tome": "selected",
        "warlock.eldritch_invocation.pact_of_the_tome.cantrip.1": "srd.spell.fire_bolt",
        "warlock.eldritch_invocation.pact_of_the_tome.cantrip.2": "srd.spell.guidance",
        "warlock.eldritch_invocation.pact_of_the_tome.cantrip.3": "srd.spell.mage_hand",
        "warlock.eldritch_invocation.pact_of_the_tome.ritual.1": "srd.spell.detect_magic",
        "warlock.eldritch_invocation.pact_of_the_tome.ritual.2": "srd.spell.speak_with_animals",
    }
    character.actions = [
        "srd.pact_of_the_tome",
        "srd.fire_bolt",
        "srd.guidance",
        "srd.mage_hand",
        "srd.detect_magic",
        "srd.speak_with_animals",
    ]
    character.prepared_spells = [
        "srd.spell.fire_bolt",
        "srd.spell.guidance",
        "srd.spell.mage_hand",
        "srd.spell.detect_magic",
        "srd.spell.speak_with_animals",
    ]
    character.spell_slots = {"1": 0}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell("pc1", "srd.detect_magic", [], 1, as_ritual=True)

    assert result["success"] is True
    ritual_change = next(
        change for change in result["state_changes"] if change["type"] == "ritual_casting"
    )
    assert ritual_change["source"] == "prepared_spell"
    assert ritual_change["spell_slot_expended"] is False
    assert character.spell_slots["1"] == 0


def test_pact_of_the_blade_binds_srd_melee_weapon_and_uses_charisma(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 1}
    character.feature_choices = {"warlock.eldritch_invocation.pact_of_the_blade": "selected"}
    character.abilities["cha"] = 18
    character.actions = ["srd.pact_of_the_blade", "srd.pact_of_the_blade_weapon"]
    state.encounter.combatants["goblin1"].hp_current = 20
    state.encounter.combatants["goblin1"].hp_max = 20
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([6, 4]),
    )

    with pytest.raises(AutomationError, match="pact_weapon_action_id"):
        tools.perform_action(
            "pc1",
            "srd.pact_of_the_blade_weapon",
            [],
            idempotency_key="pact-blade-missing-weapon",
        )

    pact_weapon = tools.perform_action(
        "pc1",
        "srd.pact_of_the_blade_weapon",
        [],
        {"pact_weapon_action_id": "srd.longsword_attack"},
        idempotency_key="pact-blade-longsword",
    )
    attack = tools.perform_action(
        "pc1",
        "srd.longsword_attack",
        ["goblin1"],
        {"use_pact_weapon_ability": True, "pact_weapon_damage_type": "psychic"},
        idempotency_key="pact-blade-longsword-attack",
    )

    assert pact_weapon["success"] is True
    assert state.encounter.action_budgets["pc1"]["bonus_action"] == 0
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["condition"] is None
    assert effect["passive_modifiers"]["pact_weapon_action_id"] == "srd.longsword_attack"
    assert effect["passive_modifiers"]["pact_weapon_damage_types"] == [
        "normal",
        "necrotic",
        "psychic",
        "radiant",
    ]

    attack_roll = attack["node_results"]["automation[1]"]
    assert attack_roll["base_attack_bonus"] == 4
    assert attack_roll["base_total"] == 10
    assert attack_roll["passive_adjustment"] == 2
    assert attack_roll["total"] == 12
    assert attack_roll["hit"] is True
    assert attack_roll["passive_sources"] == [
        {
            "effect_id": effect["effect_id"],
            "source_action_id": "srd.pact_of_the_blade_weapon",
            "modifier": "pact_weapon_attack_ability",
            "ability": "cha",
            "selected_action_id": "srd.longsword_attack",
            "amount": 2,
        }
    ]
    damage_change = next(change for change in attack["state_changes"] if change["type"] == "damage")
    assert damage_change["damage_type"] == "psychic"
    assert damage_change["amount"] == 8
    assert damage_change["passive_damage_bonus"] == 2
    assert damage_change["passive_sources"] == [
        {
            "effect_id": effect["effect_id"],
            "source_action_id": "srd.pact_of_the_blade_weapon",
            "modifier": "pact_weapon_damage_ability",
            "ability": "cha",
            "selected_action_id": "srd.longsword_attack",
            "amount": 2,
        }
    ]
    assert state.encounter.combatants["goblin1"].hp_current == 12


def test_thirsting_blade_allows_one_extra_attack_with_pact_weapon(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 5}
    character.feature_choices = {
        "warlock.eldritch_invocation.pact_of_the_blade": "selected",
        "warlock.eldritch_invocation.thirsting_blade": "selected",
    }
    character.abilities["cha"] = 18
    character.actions = [
        "srd.pact_of_the_blade",
        "srd.pact_of_the_blade_weapon",
        "srd.thirsting_blade",
    ]
    state.encounter.combatants["goblin1"].hp_current = 30
    state.encounter.combatants["goblin1"].hp_max = 30
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([6, 4, 6, 4]),
    )

    tools.perform_action(
        "pc1",
        "srd.pact_of_the_blade_weapon",
        [],
        {"pact_weapon_action_id": "srd.longsword_attack"},
        idempotency_key="thirsting-pact-weapon",
    )
    first = tools.perform_action(
        "pc1",
        "srd.longsword_attack",
        ["goblin1"],
        {"use_pact_weapon_ability": True},
        idempotency_key="thirsting-first-attack",
    )
    with pytest.raises(AutomationError, match="not enough action budget"):
        tools.perform_action(
            "pc1",
            "srd.longsword_attack",
            ["goblin1"],
            {"use_pact_weapon_ability": True},
            idempotency_key="thirsting-ordinary-second",
        )
    second = tools.perform_action(
        "pc1",
        "srd.longsword_attack",
        ["goblin1"],
        {
            "use_pact_weapon_ability": True,
            "use_thirsting_blade_extra_attack": True,
        },
        idempotency_key="thirsting-extra-attack",
    )

    assert state.encounter.action_budgets["pc1"]["action"] == 0
    assert any(
        change["type"] == "thirsting_blade_pact_weapon_attack_this_turn"
        and change["pact_weapon_action_id"] == "srd.longsword_attack"
        for change in first["state_changes"]
    )
    assert not [change for change in second["state_changes"] if change["type"] == "action_economy"]
    assert any(
        change["type"] == "thirsting_blade_extra_attack_used"
        and change["pact_weapon_action_id"] == "srd.longsword_attack"
        for change in second["state_changes"]
    )
    damage_changes = [
        change
        for result in (first, second)
        for change in result["state_changes"]
        if change["type"] == "damage"
    ]
    assert [change["amount"] for change in damage_changes] == [8, 8]
    assert state.encounter.combatants["goblin1"].hp_current == 14

    with pytest.raises(AutomationError, match="already used this turn"):
        tools.perform_action(
            "pc1",
            "srd.longsword_attack",
            ["goblin1"],
            {
                "use_pact_weapon_ability": True,
                "use_thirsting_blade_extra_attack": True,
            },
            idempotency_key="thirsting-extra-repeated",
        )


def test_eldritch_smite_spends_pact_slot_on_hit_and_can_knock_prone(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 5}
    character.feature_choices = {
        "warlock.eldritch_invocation.pact_of_the_blade": "selected",
        "warlock.eldritch_invocation.eldritch_smite": "selected",
    }
    character.abilities["cha"] = 18
    character.actions = [
        "srd.pact_of_the_blade",
        "srd.pact_of_the_blade_weapon",
        "srd.eldritch_smite",
    ]
    character.spell_slots = {"3": 1}
    character.spell_slots_max = {"3": 2}
    state.encounter.combatants["goblin1"].size = "huge"
    state.encounter.combatants["goblin1"].hp_current = 40
    state.encounter.combatants["goblin1"].hp_max = 40
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([10, 4, 16]),
    )

    tools.perform_action(
        "pc1",
        "srd.pact_of_the_blade_weapon",
        [],
        {"pact_weapon_action_id": "srd.longsword_attack"},
        idempotency_key="eldritch-smite-pact-weapon",
    )
    result = tools.perform_action(
        "pc1",
        "srd.longsword_attack",
        ["goblin1"],
        {
            "use_pact_weapon_ability": True,
            "use_eldritch_smite": True,
            "eldritch_smite_prone": True,
        },
        idempotency_key="eldritch-smite-hit",
    )

    assert character.spell_slots["3"] == 0
    assert any(
        change["type"] == "cost"
        and change["resource"] == "spell_slot_3"
        and change["source_action_id"] == "srd.eldritch_smite"
        for change in result["state_changes"]
    )
    assert any(
        change["type"] == "eldritch_smite_used" and change["pact_spell_slot_level"] == 3
        for change in result["state_changes"]
    )
    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert damage_change["extra_damage"] == [
        {
            "amount": 16,
            "applied": 16,
            "damage_type": "force",
            "sources": [
                {
                    "feature": "eldritch_smite",
                    "source_action_id": "srd.eldritch_smite",
                    "pact_spell_slot_level": 3,
                    "dice": "4d8",
                    "damage_type": "force",
                }
            ],
        }
    ]
    prone = next(
        change
        for change in result["state_changes"]
        if change.get("condition") == "prone"
        and change.get("source_action_id") == "srd.eldritch_smite"
    )
    assert prone["target_id"] == "goblin1"
    assert state.encounter.combatants["goblin1"].status_effects[-1]["condition"] == "prone"
    assert state.encounter.combatants["goblin1"].hp_current == 16

    with pytest.raises(AutomationError, match="Eldritch Smite already used this turn"):
        tools.perform_action(
            "pc1",
            "srd.longsword_attack",
            ["goblin1"],
            {"use_pact_weapon_ability": True, "use_eldritch_smite": True},
            idempotency_key="eldritch-smite-repeated",
        )


def test_eldritch_smite_miss_does_not_spend_slot_and_invalid_prone_size_rejects(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 5}
    character.feature_choices = {
        "warlock.eldritch_invocation.pact_of_the_blade": "selected",
        "warlock.eldritch_invocation.eldritch_smite": "selected",
    }
    character.actions = [
        "srd.pact_of_the_blade",
        "srd.pact_of_the_blade_weapon",
        "srd.eldritch_smite",
    ]
    character.spell_slots = {"3": 1}
    character.spell_slots_max = {"3": 2}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1]),
    )
    tools.perform_action(
        "pc1",
        "srd.pact_of_the_blade_weapon",
        [],
        {"pact_weapon_action_id": "srd.longsword_attack"},
        idempotency_key="eldritch-smite-miss-pact-weapon",
    )

    miss = tools.perform_action(
        "pc1",
        "srd.longsword_attack",
        ["goblin1"],
        {"use_pact_weapon_ability": True, "use_eldritch_smite": True},
        idempotency_key="eldritch-smite-miss",
    )

    assert character.spell_slots["3"] == 1
    assert not [
        change
        for change in miss["state_changes"]
        if change.get("source_action_id") == "srd.eldritch_smite"
    ]

    gargantuan_state = make_state()
    assert gargantuan_state.encounter is not None
    gargantuan_character = gargantuan_state.characters["pc1"]
    gargantuan_character.class_levels = {"warlock": 5}
    gargantuan_character.feature_choices = {
        "warlock.eldritch_invocation.pact_of_the_blade": "selected",
        "warlock.eldritch_invocation.eldritch_smite": "selected",
    }
    gargantuan_character.actions = [
        "srd.pact_of_the_blade",
        "srd.pact_of_the_blade_weapon",
        "srd.eldritch_smite",
    ]
    gargantuan_character.spell_slots = {"3": 1}
    gargantuan_character.spell_slots_max = {"3": 2}
    gargantuan_state.encounter.combatants["goblin1"].size = "gargantuan"
    gargantuan_tools = EngineTools(gargantuan_state, compendium, AuditLog())
    gargantuan_tools.perform_action(
        "pc1",
        "srd.pact_of_the_blade_weapon",
        [],
        {"pact_weapon_action_id": "srd.longsword_attack"},
        idempotency_key="eldritch-smite-gargantuan-pact-weapon",
    )

    with pytest.raises(
        AutomationError, match="Eldritch Smite Prone target must be Huge or smaller"
    ):
        gargantuan_tools.perform_action(
            "pc1",
            "srd.longsword_attack",
            ["goblin1"],
            {
                "use_pact_weapon_ability": True,
                "use_eldritch_smite": True,
                "eldritch_smite_prone": True,
            },
            idempotency_key="eldritch-smite-gargantuan",
        )


def test_master_of_myriad_forms_casts_alter_self_without_spell_slot(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 5}
    character.feature_choices = {"warlock.eldritch_invocation.master_of_myriad_forms": "selected"}
    character.actions.extend(
        ["srd.master_of_myriad_forms", "srd.master_of_myriad_forms_alter_self"]
    )
    character.spell_slots = {"2": 1}
    character.spell_slots_max = {"2": 1}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.master_of_myriad_forms_alter_self",
        [],
        idempotency_key="master-myriad-alter-self",
    )

    assert result["success"] is True
    assert character.spell_slots["2"] == 1
    assert state.encounter is not None
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.master_of_myriad_forms_alter_self"
    assert effect["duration"] == {"until": "concentration_1_hour"}
    assert effect["tick_on"] == "self_turn"
    assert effect["concentration"] is True
    assert effect["passive_modifiers"] == {
        "alter_self_modes": [
            "aquatic_adaptation",
            "change_appearance",
            "natural_weapons",
        ]
    }


def test_ascendant_step_casts_levitate_without_spell_slot(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 5}
    character.feature_choices = {"warlock.eldritch_invocation.ascendant_step": "selected"}
    character.actions.extend(["srd.ascendant_step", "srd.ascendant_step_levitate"])
    character.spell_slots = {"2": 1}
    character.spell_slots_max = {"2": 1}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.ascendant_step_levitate",
        [],
        idempotency_key="ascendant-step-levitate",
    )

    assert result["success"] is True
    assert character.spell_slots["2"] == 1
    assert state.encounter is not None
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.ascendant_step_levitate"
    assert effect["duration"] == {"until": "concentration_10_minutes"}
    assert effect["tick_on"] == "movement"
    assert effect["concentration"] is True
    assert effect["passive_modifiers"] == {"levitated": True, "vertical_move_ft": 20}


def test_one_with_shadows_casts_invisibility_without_spell_slot_in_dim_light(
    make_state,
) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 5}
    character.feature_choices = {"warlock.eldritch_invocation.one_with_shadows": "selected"}
    character.actions.extend(["srd.one_with_shadows", "srd.one_with_shadows_invisibility"])
    character.spell_slots = {"2": 1}
    character.spell_slots_max = {"2": 1}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="One with Shadows requires Dim Light or Darkness"):
        tools.perform_action(
            "pc1",
            "srd.one_with_shadows_invisibility",
            [],
            idempotency_key="one-with-shadows-no-light",
        )

    result = tools.perform_action(
        "pc1",
        "srd.one_with_shadows_invisibility",
        [],
        params={"in_dim_light_or_darkness": True},
        idempotency_key="one-with-shadows-invisibility",
    )

    assert result["success"] is True
    assert character.spell_slots["2"] == 1
    assert state.encounter is not None
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.one_with_shadows_invisibility"
    assert effect["condition"] == "invisible"
    assert effect["duration"] == {"until": "duration_1_hour_or_attacks_or_casts"}
    assert effect["tick_on"] == "target_action"
    assert effect["concentration"] is True


def test_gaze_of_two_minds_records_srd_connection_metadata(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 5}
    character.feature_choices = {"warlock.eldritch_invocation.gaze_of_two_minds": "selected"}
    character.actions.extend(["srd.gaze_of_two_minds", "srd.gaze_of_two_minds_touch"])
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="target must be willing"):
        tools.perform_action(
            "pc1",
            "srd.gaze_of_two_minds_touch",
            ["pc2"],
            idempotency_key="gaze-two-minds-not-willing",
        )

    result = tools.perform_action(
        "pc1",
        "srd.gaze_of_two_minds_touch",
        ["pc2"],
        params={"target_willing": True},
        idempotency_key="gaze-two-minds-touch",
    )

    assert result["success"] is True
    assert state.encounter is not None
    assert state.encounter.action_budgets["pc1"]["bonus_action"] == 0
    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.gaze_of_two_minds_touch"
    assert effect["effect_type"] == "gaze_of_two_minds_connection"
    assert effect["scope"] == {"target": "explicit", "target_ids": ["pc2"], "target_id": "pc2"}
    assert effect["duration"] == {"until": "end_of_next_turn_or_not_maintained"}
    assert effect["metadata"] == {
        "perceive_through_target_senses": True,
        "benefits_from_target_special_senses": True,
        "can_cast_spells_from_target_space_within_60_ft": True,
        "same_plane_required_to_maintain": True,
        "requires_bonus_action_to_maintain": True,
        "initial_touch_required": True,
    }
    assert result["state_changes"][-1]["type"] == "world_effect"


def test_gift_of_depths_casts_water_breathing_without_spell_slot_once_per_long_rest(
    make_state,
) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 5}
    character.feature_choices = {"warlock.eldritch_invocation.gift_of_the_depths": "selected"}
    character.actions.extend(["srd.gift_of_the_depths", "srd.gift_of_the_depths_water_breathing"])
    character.resources["srd.resource.gift_of_the_depths"] = 1
    character.spell_slots = {"3": 1}
    character.spell_slots_max = {"3": 1}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.gift_of_the_depths_water_breathing",
        ["pc2"],
        idempotency_key="gift-depths-water-breathing",
    )

    assert result["success"] is True
    assert character.resources["srd.resource.gift_of_the_depths"] == 0
    assert character.spell_slots["3"] == 1
    assert state.encounter is not None
    effect = state.encounter.combatants["pc2"].status_effects[-1]
    assert effect["source_action_id"] == "srd.gift_of_the_depths_water_breathing"
    assert effect["duration"] == {"until": "duration_24_hours"}
    assert effect["tick_on"] == "environment"
    assert effect["passive_modifiers"] == {"can_breathe_underwater": True}

    long = tools.long_rest(["pc1"], idempotency_key="gift-depths-long-rest")

    assert long["results"]["pc1"]["restored_resources"]["srd.resource.gift_of_the_depths"] == 1
    assert character.resources["srd.resource.gift_of_the_depths"] == 1


def test_wild_resurgence_restores_wild_shape_with_spell_slot_only_when_empty(
    make_state,
) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"druid": 5}
    character.actions.append("srd.wild_resurgence_restore_wild_shape_slot_1")
    character.resources["srd.resource.wild_shape"] = 0
    character.spell_slots["1"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.wild_resurgence_restore_wild_shape_slot_1",
        [],
        idempotency_key="wild-resurgence-restore",
    )

    assert result["success"] is True
    assert character.spell_slots["1"] == 0
    assert character.resources["srd.resource.wild_shape"] == 1
    assert any(
        change["type"] == "wild_resurgence_restore_wild_shape"
        and change["before"] == 0
        and change["after"] == 1
        for change in result["state_changes"]
    )

    character.resources["srd.resource.wild_shape"] = 1
    character.spell_slots["1"] = 1
    with pytest.raises(
        AutomationError,
        match="Wild Resurgence requires no Wild Shape uses remaining",
    ):
        tools.perform_action(
            "pc1",
            "srd.wild_resurgence_restore_wild_shape_slot_1",
            [],
            idempotency_key="wild-resurgence-not-empty",
        )

    assert character.spell_slots["1"] == 1
    assert character.resources["srd.resource.wild_shape"] == 1


def test_wild_resurgence_converts_wild_shape_to_level_1_spell_slot_once_per_long_rest(
    make_state,
) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"druid": 5}
    character.actions.append("srd.wild_resurgence_create_spell_slot")
    character.resources["srd.resource.wild_shape"] = 1
    character.resources["srd.resource.wild_resurgence_spell_slot"] = 1
    character.spell_slots["1"] = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.wild_resurgence_create_spell_slot",
        [],
        idempotency_key="wild-resurgence-create-slot",
    )

    assert result["success"] is True
    assert character.resources["srd.resource.wild_shape"] == 0
    assert character.resources["srd.resource.wild_resurgence_spell_slot"] == 0
    assert character.spell_slots["1"] == 1
    assert any(
        change["type"] == "resource_delta"
        and change["resource"] == "spell_slot_1"
        and change["after"] == 1
        for change in result["state_changes"]
    )

    long = tools.long_rest(["pc1"], idempotency_key="wild-resurgence-long-rest")

    assert (
        long["results"]["pc1"]["restored_resources"]["srd.resource.wild_resurgence_spell_slot"] == 1
    )
    assert character.resources["srd.resource.wild_resurgence_spell_slot"] == 1


def test_favored_enemy_hunters_mark_spends_class_resource_not_spell_slot(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"ranger": 1}
    state.characters["pc1"].actions.append("srd.favored_enemy_hunters_mark")
    state.characters["pc1"].resources["srd.resource.favored_enemy_hunters_mark"] = 2
    state.characters["pc1"].spell_slots["1"] = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.favored_enemy_hunters_mark",
        ["goblin1"],
        idempotency_key="favored-enemy-hunters-mark",
    )

    assert result["success"] is True
    assert state.characters["pc1"].resources["srd.resource.favored_enemy_hunters_mark"] == 1
    assert state.characters["pc1"].spell_slots["1"] == 0
    assert state.encounter.action_budgets["pc1"]["bonus_action"] == 0
    effect = state.encounter.combatants["goblin1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.favored_enemy_hunters_mark"
    assert effect["concentration"] is True
    assert effect["passive_modifiers"] == {
        "hunters_mark": True,
        "attacker_bonus_damage": "1d6",
        "damage_type": "force",
        "tracking_advantage": True,
    }


def test_hunters_mark_adds_force_damage_to_marked_target_hit(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    target = state.encounter.combatants["goblin1"]
    target.hp_current = 20
    target.hp_max = 20
    target.resistances = ["force"]
    target.status_effects.append(
        {
            "effect_id": "hunters-mark-test",
            "source_action_id": "srd.favored_enemy_hunters_mark",
            "target_id": "goblin1",
            "applied_by": "pc1",
            "passive_modifiers": {
                "hunters_mark": True,
                "attacker_bonus_damage": "1d6",
                "damage_type": "force",
            },
        }
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([12, 2, 4]),
    )

    result = tools.perform_action(
        "pc1",
        "srd.shortsword_attack",
        ["goblin1"],
        idempotency_key="hunters-mark-force-damage",
    )

    assert result["success"] is True
    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert damage_change["amount"] == 5
    assert damage_change["applied"] == 5
    assert damage_change["extra_damage"] == [
        {
            "amount": 4,
            "applied": 2,
            "damage_type": "force",
            "sources": [
                {
                    "feature": "hunters_mark",
                    "source_action_id": "srd.favored_enemy_hunters_mark",
                    "effect_id": "hunters-mark-test",
                    "dice": "1d6",
                    "damage_type": "force",
                }
            ],
        }
    ]
    assert damage_change["total_applied"] == 7
    assert state.encounter.combatants["goblin1"].hp_current == 13


def test_hunters_lore_reveals_marked_target_defenses(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"ranger": 3}
    state.characters["pc1"].subclasses = {"ranger": "hunter"}
    state.characters["pc1"].actions.append("srd.hunters_lore")
    target = state.encounter.combatants["goblin1"]
    target.immunities = ["poison"]
    target.resistances = ["cold"]
    target.vulnerabilities = ["radiant"]
    target.status_effects.append(
        {
            "effect_id": "hunters-lore-mark",
            "source_action_id": "srd.favored_enemy_hunters_mark",
            "target_id": "goblin1",
            "applied_by": "pc1",
            "passive_modifiers": {"hunters_mark": True},
        }
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.hunters_lore",
        ["goblin1"],
        idempotency_key="hunters-lore",
    )

    lore = result["node_results"]["automation[1]"]
    assert lore == {
        "target_id": "goblin1",
        "marked_by_hunters_mark": True,
        "immunities": ["poison"],
        "resistances": ["cold"],
        "vulnerabilities": ["radiant"],
        "has_any": True,
    }


def test_hunters_lore_requires_own_hunters_mark(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"ranger": 3}
    state.characters["pc1"].subclasses = {"ranger": "hunter"}
    state.characters["pc1"].actions.append("srd.hunters_lore")
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="marked by your Hunter's Mark"):
        tools.perform_action(
            "pc1",
            "srd.hunters_lore",
            ["goblin1"],
            idempotency_key="hunters-lore-unmarked",
        )


def test_colossus_slayer_adds_weapon_damage_once_per_turn(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"ranger": 3}
    state.characters["pc1"].subclasses = {"ranger": "hunter"}
    state.characters["pc1"].feature_choices = {"ranger.hunter.hunters_prey": "colossus_slayer"}
    target = state.encounter.combatants["goblin1"]
    target.hp_current = 30
    target.hp_max = 40
    target.armor_class = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([10, 2, 5, 10, 2]),
    )

    first = tools.perform_action(
        "pc1",
        "srd.shortsword_attack",
        ["goblin1"],
        idempotency_key="colossus-slayer-first",
    )
    assert state.encounter is not None
    tools.economy.set("pc1", "action", 1)
    second = tools.perform_action(
        "pc1",
        "srd.shortsword_attack",
        ["goblin1"],
        idempotency_key="colossus-slayer-second",
    )

    first_damage = next(change for change in first["state_changes"] if change["type"] == "damage")
    second_damage = next(change for change in second["state_changes"] if change["type"] == "damage")
    assert first_damage["amount"] == 10
    assert first_damage["colossus_slayer_bonus"] == 5
    assert second_damage["amount"] == 5
    assert "colossus_slayer_bonus" not in second_damage
    assert any(change["type"] == "colossus_slayer" for change in first["state_changes"])


def test_colossus_slayer_requires_target_missing_hit_points(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"ranger": 3}
    state.characters["pc1"].subclasses = {"ranger": "hunter"}
    state.characters["pc1"].feature_choices = {"ranger.hunter.hunters_prey": "colossus_slayer"}
    target = state.encounter.combatants["goblin1"]
    target.hp_current = 40
    target.hp_max = 40
    target.armor_class = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([10, 2]),
    )

    result = tools.perform_action(
        "pc1",
        "srd.shortsword_attack",
        ["goblin1"],
        idempotency_key="colossus-slayer-full-hp",
    )

    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert damage_change["amount"] == 5
    assert "colossus_slayer_bonus" not in damage_change


def test_horde_breaker_makes_same_weapon_attack_after_original_attack(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"ranger": 3}
    state.characters["pc1"].subclasses = {"ranger": "hunter"}
    state.characters["pc1"].feature_choices = {"ranger.hunter.hunters_prey": "horde_breaker"}
    state.encounter.combatants["goblin1"].armor_class = 30
    state.encounter.combatants["goblin2"] = Combatant(
        id="goblin2",
        entity_id="goblin2",
        name="Second Target",
        side="monsters",
        hp_current=20,
        hp_max=20,
        armor_class=1,
        position_node_id="cover",
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1, 10, 4]),
    )

    result = tools.perform_action(
        "pc1",
        "srd.shortsword_attack",
        ["goblin1"],
        params={"use_horde_breaker": True, "horde_breaker_target_id": "goblin2"},
        idempotency_key="horde-breaker",
    )

    assert result["success"] is True
    damage_changes = [change for change in result["state_changes"] if change["type"] == "damage"]
    assert [change["target_id"] for change in damage_changes] == ["goblin2"]
    assert damage_changes[0]["amount"] == 7
    assert state.encounter.combatants["goblin1"].hp_current == 7
    assert state.encounter.combatants["goblin2"].hp_current == 13
    assert result["node_results"]["automation[1]"]["hit"] is False
    assert result["node_results"]["automation[2].horde_breaker.attack_roll"]["hit"] is True
    assert any(change["type"] == "horde_breaker" for change in result["state_changes"])


def test_horde_breaker_rejects_target_not_within_five_feet_of_original(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"ranger": 3}
    state.characters["pc1"].subclasses = {"ranger": "hunter"}
    state.characters["pc1"].feature_choices = {"ranger.hunter.hunters_prey": "horde_breaker"}
    state.encounter.combatants["goblin2"] = Combatant(
        id="goblin2",
        entity_id="goblin2",
        name="Distant Target",
        side="monsters",
        hp_current=20,
        hp_max=20,
        armor_class=1,
        position_node_id="back",
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="within 5 feet"):
        tools.perform_action(
            "pc1",
            "srd.shortsword_attack",
            ["goblin1"],
            params={"use_horde_breaker": True, "horde_breaker_target_id": "goblin2"},
            idempotency_key="horde-breaker-too-far",
        )

    assert state.encounter.action_budgets == {}


def test_horde_breaker_rejects_target_already_attacked_this_turn(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"ranger": 3}
    state.characters["pc1"].subclasses = {"ranger": "hunter"}
    state.characters["pc1"].feature_choices = {"ranger.hunter.hunters_prey": "horde_breaker"}
    state.encounter.combatants["pc1"].status_effects.append(
        {
            "effect_id": "already-attacked-goblin2",
            "source_action_id": "srd.shortsword_attack",
            "target_id": "pc1",
            "applied_by": "pc1",
            "condition": "weapon_attack_target_this_turn",
            "audit": {"attacked_target_id": "goblin2"},
        }
    )
    state.encounter.combatants["goblin2"] = Combatant(
        id="goblin2",
        entity_id="goblin2",
        name="Already Attacked Target",
        side="monsters",
        hp_current=20,
        hp_max=20,
        armor_class=1,
        position_node_id="cover",
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="already attacked this turn"):
        tools.perform_action(
            "pc1",
            "srd.shortsword_attack",
            ["goblin1"],
            params={"use_horde_breaker": True, "horde_breaker_target_id": "goblin2"},
            idempotency_key="horde-breaker-already-attacked",
        )


def test_sneak_attack_adds_damage_on_finesse_attack_with_advantage(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].armor_class = 1
    state.encounter.combatants["goblin1"].status_effects.append(
        {"effect_id": "blinded-test", "condition": "blinded"}
    )
    state.characters["pc1"].class_levels = {"rogue": 1}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.shortsword_attack",
        ["goblin1"],
        params={"use_sneak_attack": True},
        idempotency_key="sneak-advantage",
    )

    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    sneak_change = next(
        change for change in result["state_changes"] if change["type"] == "sneak_attack"
    )
    assert result["success"] is True
    assert result["dice_rolls"][0]["advantage"] == "advantage"
    assert result["dice_rolls"][2]["expression"] == "1d6"
    assert damage_change["sneak_attack_bonus"] == result["dice_rolls"][2]["total"]
    assert damage_change["sneak_attack_sources"][0]["qualifies_by"] == "advantage"
    assert sneak_change["condition"] == "sneak_attack_used"
    assert any(
        effect["condition"] == "sneak_attack_used"
        for effect in state.encounter.combatants["pc1"].status_effects
    )


def test_sneak_attack_qualifies_with_ally_near_target_without_advantage(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].armor_class = 1
    state.characters["pc1"].class_levels = {"rogue": 3}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.shortsword_attack",
        ["goblin1"],
        params={"use_sneak_attack": True},
        idempotency_key="sneak-ally",
    )

    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert result["dice_rolls"][0]["advantage"] is None
    assert result["dice_rolls"][2]["expression"] == "2d6"
    assert damage_change["sneak_attack_sources"][0]["qualifies_by"] == "ally_within_5ft"


def test_cunning_strike_poison_forgoes_sneak_attack_die_and_applies_poisoned(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].armor_class = 1
    state.encounter.combatants["goblin1"].abilities = {
        "str": 10,
        "dex": 10,
        "con": 1,
        "int": 10,
        "wis": 10,
        "cha": 10,
    }
    character = state.characters["pc1"]
    character.class_levels = {"rogue": 5}
    character.abilities["dex"] = 20
    character.proficiency_bonus = 3
    character.equipment.append("srd.poisoners_kit")
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.shortsword_attack",
        ["goblin1"],
        params={"use_sneak_attack": True, "cunning_strike": "poison"},
        idempotency_key="cunning-strike-poison",
    )

    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    cunning_change = next(
        change
        for change in result["state_changes"]
        if change["type"] == "cunning_strike" and change["effect"] == "poison"
    )
    poison_effect = state.encounter.combatants["goblin1"].status_effects[-1]

    assert result["success"] is True
    assert result["dice_rolls"][2]["expression"] == "2d6"
    assert damage_change["sneak_attack_sources"][0]["cunning_strike"] == {
        "effect": "poison",
        "die_cost": 1,
        "forgone_dice": "1d6",
    }
    poison_save = result["node_results"]["automation[2].cunning_strike.poison"]
    assert poison_save["dc"] == 16
    assert poison_save["dc_source"] == "cunning_strike:dex+proficiency"
    assert poison_save["success"] is False
    assert cunning_change["saving_throw_success"] is False
    assert poison_effect["condition"] == "poisoned"
    assert poison_effect["source_action_id"] == "srd.cunning_strike"
    assert poison_effect["tick_on"] == "target_turn_end"
    assert poison_effect["duration"]["repeat_save"] == {
        "ability": "con",
        "dc": 16,
        "dc_source": "cunning_strike:dex+proficiency",
        "end_on_success": True,
    }


def test_cunning_strike_poison_requires_poisoners_kit_before_spending_action(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].armor_class = 1
    state.characters["pc1"].class_levels = {"rogue": 5}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(
        AutomationError,
        match="Cunning Strike Poison requires a Poisoner's Kit",
    ):
        tools.perform_action(
            "pc1",
            "srd.shortsword_attack",
            ["goblin1"],
            params={"use_sneak_attack": True, "cunning_strike": "poison"},
            idempotency_key="cunning-strike-poison-no-kit",
        )

    assert state.encounter.action_budgets == {}


def test_cunning_strike_trip_applies_prone_on_failed_dex_save(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    target = state.encounter.combatants["goblin1"]
    target.armor_class = 1
    target.size = "large"
    target.abilities = {
        "str": 10,
        "dex": 1,
        "con": 10,
        "int": 10,
        "wis": 10,
        "cha": 10,
    }
    character = state.characters["pc1"]
    character.class_levels = {"rogue": 5}
    character.abilities["dex"] = 20
    character.proficiency_bonus = 3
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.shortsword_attack",
        ["goblin1"],
        params={"use_sneak_attack": True, "cunning_strike": "trip"},
        idempotency_key="cunning-strike-trip",
    )

    trip_save = result["node_results"]["automation[2].cunning_strike.trip"]
    assert result["dice_rolls"][2]["expression"] == "2d6"
    assert trip_save["ability"] == "dex"
    assert trip_save["dc"] == 16
    assert trip_save["success"] is False
    assert target.status_effects[-1]["condition"] == "prone"
    assert any(
        change["type"] == "condition" and change["condition"] == "prone"
        for change in result["state_changes"]
    )


def test_cunning_strike_trip_rejects_huge_target_before_spending_action(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].size = "huge"
    state.characters["pc1"].class_levels = {"rogue": 5}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(
        AutomationError,
        match="Cunning Strike Trip requires a Large or smaller target",
    ):
        tools.perform_action(
            "pc1",
            "srd.shortsword_attack",
            ["goblin1"],
            params={"use_sneak_attack": True, "cunning_strike": "trip"},
            idempotency_key="cunning-strike-trip-huge",
        )

    assert state.encounter.action_budgets == {}


def test_cunning_strike_withdraw_moves_half_speed_without_opportunity_attack(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].armor_class = 1
    state.characters["pc1"].class_levels = {"rogue": 5}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.shortsword_attack",
        ["goblin1"],
        params={
            "use_sneak_attack": True,
            "cunning_strike": "withdraw",
            "cunning_strike_withdraw_to_position_node_id": "cover",
        },
        idempotency_key="cunning-strike-withdraw",
    )

    withdraw_change = next(
        change
        for change in result["state_changes"]
        if change["type"] == "cunning_strike" and change["effect"] == "withdraw"
    )
    assert result["dice_rolls"][2]["expression"] == "2d6"
    assert state.encounter.combatants["pc1"].position_node_id == "cover"
    assert withdraw_change["from"] == "front"
    assert withdraw_change["to"] == "cover"
    assert withdraw_change["movement_cost"] == 5
    assert withdraw_change["movement_limit"] == 15
    assert withdraw_change["opportunity_attack_triggers"] == []
    assert state.encounter.action_budgets["pc1"]["movement_used"] == 5


def test_uncanny_dodge_halves_attack_damage_and_spends_reaction(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"rogue": 5}
    state.characters["pc1"].actions.append("srd.uncanny_dodge")
    state.encounter.combatants["pc1"].armor_class = 1
    state.encounter.combatants["pc1"].hp_current = 10
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "goblin1",
        "srd.bandit_scimitar",
        ["pc1"],
        params={"use_uncanny_dodge": True},
        idempotency_key="uncanny-dodge-hit",
    )

    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    dodge_change = next(
        change for change in result["state_changes"] if change["type"] == "uncanny_dodge"
    )

    assert result["success"] is True
    assert result["node_results"]["automation[1]"]["hit"] is True
    assert dodge_change["original_amount"] == damage_change["amount_before_uncanny_dodge"]
    assert dodge_change["halved_amount"] == dodge_change["original_amount"] // 2
    assert damage_change["amount"] == dodge_change["halved_amount"]
    assert damage_change["uncanny_dodge"]["source_action_id"] == "srd.uncanny_dodge"
    assert state.encounter.combatants["pc1"].hp_current == 10 - damage_change["applied"]
    assert state.encounter.action_budgets["pc1"]["reaction"] == 0


def test_uncanny_dodge_requires_rogue_level_five_before_spending_attack(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["pc1"].armor_class = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="Uncanny Dodge requires Rogue level 5"):
        tools.perform_action(
            "goblin1",
            "srd.bandit_scimitar",
            ["pc1"],
            params={"use_uncanny_dodge": True},
            idempotency_key="uncanny-dodge-no-rogue",
        )

    assert state.encounter.action_budgets == {}


def test_uncanny_dodge_requires_available_reaction_before_spending_attack(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"rogue": 5}
    state.encounter.combatants["pc1"].armor_class = 1
    state.encounter.action_budgets["pc1"] = {
        "action": 1,
        "bonus_action": 1,
        "reaction": 0,
        "movement": 30,
        "movement_used": 0,
        "free": 1,
    }
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="not enough reaction budget"):
        tools.perform_action(
            "goblin1",
            "srd.bandit_scimitar",
            ["pc1"],
            params={"use_uncanny_dodge": True},
            idempotency_key="uncanny-dodge-no-reaction",
        )

    assert "goblin1" not in state.encounter.action_budgets
    assert state.encounter.action_budgets["pc1"]["reaction"] == 0


def test_sneak_attack_only_applies_once_per_turn(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].armor_class = 1
    state.encounter.combatants["goblin1"].status_effects.append(
        {"effect_id": "blinded-test", "condition": "blinded"}
    )
    state.characters["pc1"].class_levels = {"rogue": 1}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    first = tools.perform_action(
        "pc1",
        "srd.shortsword_attack",
        ["goblin1"],
        params={"use_sneak_attack": True},
        idempotency_key="sneak-once-first",
    )
    tools.economy.add("pc1", "action", 1)
    second = tools.perform_action(
        "pc1",
        "srd.shortsword_attack",
        ["goblin1"],
        params={"use_sneak_attack": True},
        idempotency_key="sneak-once-second",
    )

    first_damage = next(change for change in first["state_changes"] if change["type"] == "damage")
    second_damage = next(change for change in second["state_changes"] if change["type"] == "damage")
    assert "sneak_attack_bonus" in first_damage
    assert "sneak_attack_bonus" not in second_damage
    assert (
        sum(
            1
            for effect in state.encounter.combatants["pc1"].status_effects
            if effect["condition"] == "sneak_attack_used"
        )
        == 1
    )


def test_steady_aim_grants_next_attack_advantage_and_sets_movement_to_zero(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"rogue": 3}
    state.characters["pc1"].actions.append("srd.steady_aim")
    state.encounter.combatants["goblin1"].armor_class = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    aim = tools.perform_action(
        "pc1",
        "srd.steady_aim",
        [],
        idempotency_key="steady-aim",
    )
    attack = tools.perform_action(
        "pc1",
        "srd.shortsword_attack",
        ["goblin1"],
        idempotency_key="steady-aim-attack",
    )

    assert aim["success"] is True
    assert state.encounter.action_budgets["pc1"]["bonus_action"] == 0
    assert state.encounter.action_budgets["pc1"]["movement"] == 0
    assert any(
        change["type"] == "resource_delta"
        and change["resource"] == "budget.movement"
        and change["before"] == 30
        and change["after"] == 0
        for change in aim["state_changes"]
    )
    assert attack["dice_rolls"][0]["advantage"] == "advantage"
    attack_node = attack["node_results"]["automation[1]"]
    assert attack_node["status_sources"][0]["condition"] == "steady_aim"
    assert attack_node["status_sources"][0]["modifier"] == "attack_roll_advantage"
    assert any(
        change["type"] == "effect_expired"
        and change["trigger"] == "attack"
        and change["removed"][0]["condition"] == "steady_aim"
        for change in attack["state_changes"]
    )
    assert not any(
        effect["condition"] == "steady_aim"
        for effect in state.encounter.combatants["pc1"].status_effects
    )


def test_steady_aim_rejects_after_movement_used_before_bonus_action_spent(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"rogue": 3}
    state.characters["pc1"].actions.append("srd.steady_aim")
    state.encounter.action_budgets["pc1"] = {
        "action": 1,
        "bonus_action": 1,
        "reaction": 1,
        "movement": 25,
        "movement_used": 5,
        "free": 1,
    }
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="requires no movement used this turn"):
        tools.perform_action("pc1", "srd.steady_aim", [], idempotency_key="steady-aim-moved")

    assert state.encounter.action_budgets["pc1"]["bonus_action"] == 1
    assert not any(
        effect["condition"] == "steady_aim"
        for effect in state.encounter.combatants["pc1"].status_effects
    )


def test_class_feature_execution_rejects_unmet_class_requirements(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"fighter": 1}
    state.characters["pc1"].actions.append("srd.action_surge")
    state.characters["pc1"].resources["srd.resource.action_surge"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="requires fighter level 2"):
        tools.perform_action("pc1", "srd.action_surge", [], idempotency_key="bad-surge")

    assert state.characters["pc1"].resources["srd.resource.action_surge"] == 1
    assert state.encounter is not None
    assert state.encounter.action_budgets == {}


def test_thief_fast_hands_sleight_of_hand_uses_bonus_action_and_thieves_tools(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"rogue": 3}
    character.subclasses = {"rogue": "thief"}
    character.actions.append("srd.fast_hands_sleight_of_hand")
    character.skill_proficiencies = ["sleight_of_hand"]
    character.tool_proficiencies = ["thieves_tools"]
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([10]),
    )

    result = tools.perform_action(
        "pc1",
        "srd.fast_hands_sleight_of_hand",
        [],
        idempotency_key="fast-hands-sleight",
    )

    check = result["node_results"]["automation[1]"]
    assert result["success"] is True
    assert state.encounter.action_budgets["pc1"]["bonus_action"] == 0
    assert check["ability"] == "dex"
    assert check["skill"] == "sleight_of_hand"
    assert check["tool"] == "thieves_tools"
    assert check["proficiency_sources"] == [
        "skill:sleight_of_hand",
        "tool:thieves_tools",
    ]
    assert result["dice_rolls"][0]["advantage"] == "advantage"


def test_thief_fast_hands_requires_thieves_tools_before_bonus_action_spent(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"rogue": 3}
    character.subclasses = {"rogue": "thief"}
    character.actions.append("srd.fast_hands_sleight_of_hand")
    character.tool_proficiencies = []
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="Thieves' Tools proficiency"):
        tools.perform_action(
            "pc1",
            "srd.fast_hands_sleight_of_hand",
            [],
            idempotency_key="fast-hands-no-tools",
        )

    assert "pc1" not in state.encounter.action_budgets


def test_thief_second_story_work_sets_climb_speed_and_jump_ability(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"rogue": 3}
    character.subclasses = {"rogue": "thief"}
    character.speed_ft = 35

    assert second_story_work_climb_speed(character) == 35
    assert second_story_work_jump_ability(character) == "dex"


def test_cunning_action_dash_spends_bonus_action_and_adds_movement(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"rogue": 2}
    state.characters["pc1"].actions.append("srd.cunning_action_dash")
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.cunning_action_dash",
        [],
        idempotency_key="cunning-action-dash",
    )

    assert result["success"] is True
    assert state.encounter is not None
    assert state.encounter.action_budgets["pc1"]["action"] == 1
    assert state.encounter.action_budgets["pc1"]["bonus_action"] == 0
    assert state.encounter.action_budgets["pc1"]["movement"] == 60
    assert any(
        change["type"] == "resource_delta"
        and change["resource"] == "budget.movement"
        and change["after"] == 60
        for change in result["state_changes"]
    )


def test_patient_defense_takes_disengage_as_bonus_action(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"monk": 2}
    state.characters["pc1"].actions.append("srd.patient_defense")
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.patient_defense",
        [],
        idempotency_key="patient-defense",
    )

    assert result["success"] is True
    assert state.encounter.action_budgets["pc1"]["bonus_action"] == 0
    conditions = {
        effect["condition"] for effect in state.encounter.combatants["pc1"].status_effects
    }
    assert conditions == {"disengaged"}
    assert state.characters["pc1"].resources.get("srd.resource.focus_points", 0) == 0


def test_patient_defense_focus_spends_focus_and_dodges(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"monk": 2}
    state.characters["pc1"].actions.append("srd.patient_defense_focus")
    state.characters["pc1"].resources["srd.resource.focus_points"] = 2
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.patient_defense_focus",
        [],
        idempotency_key="patient-defense-focus",
    )

    assert result["success"] is True
    assert state.characters["pc1"].resources["srd.resource.focus_points"] == 1
    assert state.encounter.action_budgets["pc1"]["bonus_action"] == 0
    conditions = {
        effect["condition"] for effect in state.encounter.combatants["pc1"].status_effects
    }
    assert conditions == {"disengaged", "dodging"}


def test_monk_unarmed_strike_uses_martial_arts_die_and_dexterity(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].armor_class = 1
    state.characters["pc1"].class_levels = {"monk": 1}
    state.characters["pc1"].actions.append("srd.monk_unarmed_strike")
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.monk_unarmed_strike",
        ["goblin1"],
        idempotency_key="monk-unarmed-strike",
    )

    attack_node = result["node_results"]["automation[1]"]
    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert result["success"] is True
    assert attack_node["ability"] == "dex"
    assert attack_node["base_attack_bonus"] == 4
    assert attack_node["attack_bonus_sources"] == [
        {"kind": "ability", "ability": "dex", "amount": 2},
        {"kind": "proficiency", "amount": 2},
    ]
    assert result["dice_rolls"][0]["expression"] == "1d20+4"
    assert result["dice_rolls"][1]["expression"] == "1d6"
    assert damage_change["damage_type"] == "bludgeoning"
    assert damage_change["amount"] == result["dice_rolls"][1]["total"] + 2


def test_monk_level_five_unarmed_strike_uses_scaled_martial_arts_die(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].armor_class = 1
    state.characters["pc1"].class_levels = {"monk": 5}
    state.characters["pc1"].actions.append("srd.monk_unarmed_strike")
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([10, 4]),
    )

    result = tools.perform_action(
        "pc1",
        "srd.monk_unarmed_strike",
        ["goblin1"],
        idempotency_key="monk-level-five-unarmed-strike",
    )

    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert result["success"] is True
    assert result["dice_rolls"][1]["expression"] == "1d8"
    assert damage_change["amount"] == 6


def test_monk_empowered_strikes_can_make_unarmed_damage_force(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].armor_class = 1
    character = state.characters["pc1"]
    character.class_levels = {"monk": 6}
    character.actions.extend(["srd.monk_unarmed_strike", "srd.empowered_strikes"])
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([10, 4]),
    )

    result = tools.perform_action(
        "pc1",
        "srd.monk_unarmed_strike",
        ["goblin1"],
        params={"empowered_strikes_damage_type": "force"},
        idempotency_key="monk-empowered-strikes-force",
    )

    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert result["success"] is True
    assert damage_change["damage_type"] == "force"
    assert damage_change["amount"] == 6


def test_empowered_strikes_requires_monk_level_six_before_spending_focus(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].armor_class = 1
    character = state.characters["pc1"]
    character.class_levels = {"monk": 5}
    character.actions.append("srd.flurry_of_blows")
    character.resources["srd.resource.focus_points"] = 5
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="Empowered Strikes requires Monk level 6"):
        tools.perform_action(
            "pc1",
            "srd.flurry_of_blows",
            ["goblin1"],
            params={
                "strike_1_target": "goblin1",
                "strike_2_target": "goblin1",
                "empowered_strikes_damage_type": "force",
            },
            idempotency_key="empowered-strikes-too-low",
        )

    assert character.resources["srd.resource.focus_points"] == 5


def test_flurry_of_blows_spends_focus_and_can_split_strikes(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].armor_class = 1
    state.encounter.combatants["zombie1"] = Combatant(
        id="zombie1",
        entity_id="zombie1",
        name="Zombie",
        side="monsters",
        hp_current=22,
        hp_max=22,
        armor_class=1,
        position_node_id="cover",
    )
    state.characters["pc1"].class_levels = {"monk": 2}
    state.characters["pc1"].actions.append("srd.flurry_of_blows")
    state.characters["pc1"].resources["srd.resource.focus_points"] = 2
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.flurry_of_blows",
        ["goblin1"],
        params={"strike_1_target": "goblin1", "strike_2_target": "zombie1"},
        idempotency_key="flurry-of-blows",
    )

    damage_changes = [change for change in result["state_changes"] if change["type"] == "damage"]
    assert result["success"] is True
    assert state.characters["pc1"].resources["srd.resource.focus_points"] == 1
    assert state.encounter.action_budgets["pc1"]["bonus_action"] == 0
    assert [change["target_id"] for change in damage_changes] == ["goblin1", "zombie1"]
    assert result["node_results"]["automation[1]"]["target_id"] == "goblin1"
    assert result["node_results"]["automation[4]"]["target_id"] == "zombie1"
    assert [roll["expression"] for roll in result["dice_rolls"]] == [
        "1d20+4",
        "1d6",
        "1d20+4",
        "1d6",
    ]


def test_level_five_flurry_of_blows_uses_scaled_martial_arts_die(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].armor_class = 1
    state.characters["pc1"].class_levels = {"monk": 5}
    state.characters["pc1"].actions.append("srd.flurry_of_blows")
    state.characters["pc1"].resources["srd.resource.focus_points"] = 5
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([10, 3, 10, 4]),
    )

    result = tools.perform_action(
        "pc1",
        "srd.flurry_of_blows",
        ["goblin1"],
        params={"strike_1_target": "goblin1", "strike_2_target": "goblin1"},
        idempotency_key="level-five-flurry-of-blows",
    )

    assert result["success"] is True
    assert [roll["expression"] for roll in result["dice_rolls"]] == [
        "1d20+4",
        "1d8",
        "1d20+4",
        "1d8",
    ]


def test_open_hand_wholeness_of_body_heals_self_and_spends_resource(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    combatant = state.encounter.combatants["pc1"]
    character.class_levels = {"monk": 6}
    character.subclasses = {"monk": "open_hand"}
    character.abilities["wis"] = 16
    character.actions.append("srd.wholeness_of_body")
    character.resources["srd.resource.wholeness_of_body"] = 3
    combatant.hp_current = 5
    combatant.hp_max = 20
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([4]),
    )

    result = tools.perform_action(
        "pc1",
        "srd.wholeness_of_body",
        [],
        idempotency_key="wholeness-of-body",
    )

    healing_change = next(
        change for change in result["state_changes"] if change["type"] == "healing"
    )
    assert result["success"] is True
    assert healing_change["amount"] == 7
    assert healing_change["applied"] == 7
    assert combatant.hp_current == 12
    assert character.resources["srd.resource.wholeness_of_body"] == 2
    assert state.encounter.action_budgets["pc1"]["bonus_action"] == 0


def test_open_hand_wholeness_of_body_healing_has_minimum_one(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    combatant = state.encounter.combatants["pc1"]
    character.class_levels = {"monk": 6}
    character.subclasses = {"monk": "open_hand"}
    character.abilities["wis"] = 8
    character.actions.append("srd.wholeness_of_body")
    character.resources["srd.resource.wholeness_of_body"] = 1
    combatant.hp_current = 5
    combatant.hp_max = 20
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1]),
    )

    result = tools.perform_action(
        "pc1",
        "srd.wholeness_of_body",
        [],
        idempotency_key="wholeness-of-body-minimum",
    )

    healing_change = next(
        change for change in result["state_changes"] if change["type"] == "healing"
    )
    assert result["success"] is True
    assert healing_change["amount"] == 1
    assert healing_change["applied"] == 1
    assert combatant.hp_current == 6


def test_open_hand_technique_addle_blocks_opportunity_attacks(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].armor_class = 1
    state.characters["pc1"].class_levels = {"monk": 3}
    state.characters["pc1"].subclasses = {"monk": "open_hand"}
    state.characters["pc1"].actions.extend(["srd.flurry_of_blows", "srd.open_hand_technique"])
    state.characters["pc1"].resources["srd.resource.focus_points"] = 3
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([10, 4, 10, 4]),
    )

    result = tools.perform_action(
        "pc1",
        "srd.flurry_of_blows",
        ["goblin1"],
        params={
            "strike_1_target": "goblin1",
            "strike_2_target": "goblin1",
            "open_hand_technique_by_strike": {"1": "addle"},
        },
        idempotency_key="open-hand-addle",
    )

    assert result["success"] is True
    effect = state.encounter.combatants["goblin1"].status_effects[-1]
    assert effect["condition"] == "open_hand_addled"
    assert effect["passive_modifiers"] == {"cannot_make_opportunity_attacks": True}
    state.encounter.combatants["pc1"].position_node_id = "cover"
    move_result = tools.move(
        "pc1",
        to_position_node_id="back",
        idempotency_key="move-away-from-addled-goblin",
    )
    move_change = next(
        change for change in move_result["state_changes"] if change["type"] == "move"
    )
    assert move_change["opportunity_attack_triggers"] == []


def test_open_hand_technique_topple_applies_prone_on_failed_dex_save(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].armor_class = 1
    state.characters["pc1"].class_levels = {"monk": 3}
    state.characters["pc1"].subclasses = {"monk": "open_hand"}
    state.characters["pc1"].actions.extend(["srd.flurry_of_blows", "srd.open_hand_technique"])
    state.characters["pc1"].resources["srd.resource.focus_points"] = 3
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([10, 4, 1, 10, 4]),
    )

    result = tools.perform_action(
        "pc1",
        "srd.flurry_of_blows",
        ["goblin1"],
        params={
            "strike_1_target": "goblin1",
            "strike_2_target": "goblin1",
            "open_hand_technique_by_strike": {"1": "topple"},
        },
        idempotency_key="open-hand-topple",
    )

    open_hand_change = next(
        change for change in result["state_changes"] if change["type"] == "open_hand_technique"
    )
    assert result["success"] is True
    assert open_hand_change["effect"] == "topple"
    assert open_hand_change["saving_throw_success"] is False
    assert state.encounter.combatants["goblin1"].status_effects[-1]["condition"] == "prone"
    save_result = result["node_results"]["automation[2].open_hand_technique.topple"]
    assert save_result["dc_source"] == "monk_focus:wis+proficiency"


def test_open_hand_technique_push_moves_target_away_on_failed_str_save(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    assert state.encounter.tactical_graph is not None
    state.encounter.tactical_graph["nodes"]["far"] = {
        "node_id": "far",
        "name": "Far",
        "tags": [],
        "capacity": None,
        "default_cover": "none",
        "terrain": "normal",
    }
    state.encounter.tactical_graph["edges"].append(
        {
            "source": "cover",
            "target": "far",
            "distance_ft": 15,
            "movement_cost": None,
            "line_of_sight": True,
            "cover": "none",
            "difficult_terrain": False,
        }
    )
    state.encounter.combatants["goblin1"].armor_class = 1
    state.characters["pc1"].class_levels = {"monk": 3}
    state.characters["pc1"].subclasses = {"monk": "open_hand"}
    state.characters["pc1"].actions.extend(["srd.flurry_of_blows", "srd.open_hand_technique"])
    state.characters["pc1"].resources["srd.resource.focus_points"] = 3
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([10, 4, 1, 10, 4]),
    )

    result = tools.perform_action(
        "pc1",
        "srd.flurry_of_blows",
        ["goblin1"],
        params={
            "strike_1_target": "goblin1",
            "strike_2_target": "goblin1",
            "open_hand_technique_by_strike": {"1": "push"},
            "open_hand_push_to_position_node_id": "far",
        },
        idempotency_key="open-hand-push",
    )

    open_hand_change = next(
        change for change in result["state_changes"] if change["type"] == "open_hand_technique"
    )
    assert result["success"] is True
    assert open_hand_change["effect"] == "push"
    assert open_hand_change["saving_throw_success"] is False
    assert open_hand_change["from"] == "cover"
    assert open_hand_change["to"] == "far"
    assert open_hand_change["forced_movement_distance"] == 15
    assert state.encounter.combatants["goblin1"].position_node_id == "far"


def test_open_hand_technique_rejects_non_open_hand_before_spending_focus(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].armor_class = 1
    state.characters["pc1"].class_levels = {"monk": 3}
    state.characters["pc1"].actions.append("srd.flurry_of_blows")
    state.characters["pc1"].resources["srd.resource.focus_points"] = 3
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="Open Hand Technique requires"):
        tools.perform_action(
            "pc1",
            "srd.flurry_of_blows",
            ["goblin1"],
            params={"open_hand_technique": "topple"},
            idempotency_key="open-hand-rejects-non-subclass",
        )

    assert state.characters["pc1"].resources["srd.resource.focus_points"] == 3


def test_step_of_the_wind_focus_uses_speed_and_marks_jump_distance(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"monk": 2}
    state.characters["pc1"].actions.append("srd.step_of_the_wind_focus")
    state.characters["pc1"].resources["srd.resource.focus_points"] = 2
    state.characters["pc1"].speed_ft = 40
    state.encounter.combatants["pc1"].speed_ft = 40
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.step_of_the_wind_focus",
        [],
        idempotency_key="step-of-the-wind-focus",
    )

    assert result["success"] is True
    assert state.characters["pc1"].resources["srd.resource.focus_points"] == 1
    assert state.encounter.action_budgets["pc1"]["bonus_action"] == 0
    assert state.encounter.action_budgets["pc1"]["movement"] == 100
    conditions = {
        effect["condition"] for effect in state.encounter.combatants["pc1"].status_effects
    }
    assert conditions == {"disengaged", "jump_distance_doubled"}
    assert any(
        change["type"] == "resource_delta"
        and change["resource"] == "budget.movement"
        and change["after"] == 100
        for change in result["state_changes"]
    )


def test_lay_on_hands_spends_chosen_pool_points_and_heals(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"paladin": 1}
    state.characters["pc1"].actions.append("srd.lay_on_hands")
    state.characters["pc1"].resources["srd.resource.lay_on_hands"] = 5
    state.characters["pc1"].hp_current = 3
    state.encounter.combatants["pc1"].hp_current = 3
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.lay_on_hands",
        ["pc1"],
        {"lay_on_hands_points": 4},
        idempotency_key="lay-on-hands",
    )

    assert result["success"] is True
    assert state.characters["pc1"].resources["srd.resource.lay_on_hands"] == 1
    assert state.encounter.combatants["pc1"].hp_current == 7
    assert state.encounter.action_budgets["pc1"]["bonus_action"] == 0
    assert any(
        change["type"] == "cost"
        and change["resource"] == "srd.resource.lay_on_hands"
        and change["amount"] == 4
        and change["param"] == "lay_on_hands_points"
        for change in result["state_changes"]
    )


def test_lay_on_hands_rejects_points_above_pool_before_spending_budget(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"paladin": 1}
    state.characters["pc1"].actions.append("srd.lay_on_hands")
    state.characters["pc1"].resources["srd.resource.lay_on_hands"] = 3
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="resource srd.resource.lay_on_hands is insufficient"):
        tools.perform_action(
            "pc1",
            "srd.lay_on_hands",
            ["pc1"],
            {"lay_on_hands_points": 4},
            idempotency_key="lay-on-hands-too-much",
        )

    assert state.characters["pc1"].resources["srd.resource.lay_on_hands"] == 3
    assert state.encounter.action_budgets["pc1"]["bonus_action"] == 1


def test_lay_on_hands_removes_poisoned_for_five_pool_points(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"paladin": 1}
    state.characters["pc1"].actions.append("srd.lay_on_hands_remove_poisoned")
    state.characters["pc1"].resources["srd.resource.lay_on_hands"] = 5
    state.encounter.combatants["pc2"].status_effects.append(
        {"effect_id": "poisoned-test", "condition": "poisoned"}
    )
    state.encounter.combatants["pc2"].hp_current = 2
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.lay_on_hands_remove_poisoned",
        ["pc2"],
        idempotency_key="lay-on-hands-poisoned",
    )

    assert result["success"] is True
    assert state.characters["pc1"].resources["srd.resource.lay_on_hands"] == 0
    assert state.encounter.combatants["pc2"].status_effects == []
    assert state.encounter.combatants["pc2"].hp_current == 2
    assert any(change["type"] == "remove_condition" for change in result["state_changes"])


def test_paladins_smite_casts_divine_smite_without_spell_slot_once_per_long_rest(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"paladin": 2}
    character.actions.append("srd.paladins_smite_divine_smite")
    character.resources["srd.resource.paladins_smite"] = 1
    character.spell_slots["1"] = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.paladins_smite_divine_smite",
        [],
        idempotency_key="paladins-smite",
    )

    assert result["success"] is True
    assert character.resources["srd.resource.paladins_smite"] == 0
    assert character.spell_slots["1"] == 0
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.paladins_smite_divine_smite"
    assert effect["passive_modifiers"] == {
        "next_melee_hit_bonus_damage": "2d8",
        "damage_type": "radiant",
    }

    long = tools.long_rest(["pc1"], idempotency_key="paladins-smite-long-rest")

    assert long["results"]["pc1"]["restored_resources"]["srd.resource.paladins_smite"] == 1
    assert character.resources["srd.resource.paladins_smite"] == 1


def test_faithful_steed_casts_find_steed_without_spell_slot_once_per_long_rest(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"paladin": 5}
    character.actions.append("srd.faithful_steed_find_steed")
    character.resources["srd.resource.faithful_steed"] = 1
    character.spell_slots["2"] = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell(
        "pc1",
        "srd.faithful_steed_find_steed",
        [],
        2,
        idempotency_key="faithful-steed",
    )

    assert result["success"] is True
    assert character.resources["srd.resource.faithful_steed"] == 0
    assert character.spell_slots["2"] == 0
    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.faithful_steed_find_steed"
    assert effect["effect_type"] == "steed_bound"
    assert effect["metadata"] == {"mount": True, "telepathic_bond": True}

    long = tools.long_rest(["pc1"], idempotency_key="faithful-steed-long-rest")

    assert long["results"]["pc1"]["restored_resources"]["srd.resource.faithful_steed"] == 1
    assert character.resources["srd.resource.faithful_steed"] == 1


def test_paladin_aura_of_protection_adds_cha_to_allied_saving_throw(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    paladin = state.characters["pc1"]
    paladin.class_levels = {"paladin": 6}
    paladin.abilities["cha"] = 16
    paladin.actions.append("srd.aura_of_protection")
    action = ActionDefinition(
        id="test.aura_save",
        name="Aura Save",
        localization={"en": "Aura Save", "zh": "灵光豁免", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={"normal_ft": 5},
        target_policy={"min": 1, "max": 1, "harmful": False},
        automation=[{"type": "saving_throw", "ability": "dex", "difficulty_tier": "medium"}],
    )

    result = AutomationExecutor(
        state,
        _FixedSingleDieRollService([10]),
        AuditLog(),
    ).execute(action, actor_id="goblin1", targets=["pc2"])

    save_node = result.node_results["automation[0]"]
    assert save_node["passive_adjustment"] == 3
    assert save_node["passive_sources"] == [
        {
            "source_action_id": "srd.aura_of_protection",
            "modifier": "aura_of_protection",
            "source_actor_id": "pc1",
            "target_id": "pc2",
            "distance_ft": 0,
            "amount": 3,
        }
    ]

    compendium = CompendiumLoader("rules_data").load()
    direct_save = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([10]),
    ).roll_save("pc2", "dex", difficulty_tier="medium", idempotency_key="aura-direct-save")
    assert direct_save["passive_bonus"] == 3
    assert direct_save["passive_bonus_sources"][0]["modifier"] == "aura_of_protection"


def test_paladin_aura_of_protection_inactive_while_incapacitated(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    paladin = state.characters["pc1"]
    paladin.class_levels = {"paladin": 6}
    paladin.abilities["cha"] = 16
    state.encounter.combatants["pc1"].status_effects.append({"condition": "incapacitated"})
    action = ActionDefinition(
        id="test.incapacitated_aura_save",
        name="Incapacitated Aura Save",
        localization={"en": "Incapacitated Aura Save", "zh": "失能灵光豁免", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={"normal_ft": 5},
        target_policy={"min": 1, "max": 1, "harmful": False},
        automation=[{"type": "saving_throw", "ability": "dex", "difficulty_tier": "medium"}],
    )

    result = AutomationExecutor(
        state,
        _FixedSingleDieRollService([10]),
        AuditLog(),
    ).execute(action, actor_id="goblin1", targets=["pc2"])

    save_node = result.node_results["automation[0]"]
    assert save_node["passive_adjustment"] == 0
    assert save_node["passive_sources"] == []


def test_dark_ones_own_luck_adds_d10_to_direct_check_and_long_rest_restores(
    make_state,
) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 6}
    character.subclasses = {"warlock": "fiend"}
    character.abilities["cha"] = 16
    character.resources["srd.resource.dark_ones_own_luck"] = 3
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([10, 7]),
    )

    result = tools.roll_check(
        "pc1",
        "cha",
        difficulty_tier="hard",
        use_dark_ones_own_luck=True,
        idempotency_key="dark-luck-check",
    )

    assert result["total"] == 20
    assert result["success"] is True
    assert result["dark_ones_own_luck"] == {
        "resource": "srd.resource.dark_ones_own_luck",
        "resource_before": 3,
        "resource_after": 2,
        "roll_total": 7,
        "total_before": 13,
        "total_after": 20,
        "spent": True,
        "success": True,
    }
    assert character.resources["srd.resource.dark_ones_own_luck"] == 2

    long_rest = tools.long_rest(["pc1"], idempotency_key="dark-luck-long-rest")

    assert long_rest["results"]["pc1"]["restored_resources"]["srd.resource.dark_ones_own_luck"] == 1
    assert character.resources["srd.resource.dark_ones_own_luck"] == 3


def test_dark_ones_own_luck_adds_d10_to_automation_saving_throw(make_state) -> None:
    state = make_state()
    target = state.characters["pc2"]
    target.class_levels = {"warlock": 6}
    target.subclasses = {"warlock": "fiend"}
    target.abilities["cha"] = 14
    target.resources["srd.resource.dark_ones_own_luck"] = 2
    action = ActionDefinition(
        id="test.dark_luck_save",
        name="Dark Luck Save",
        localization={"en": "Dark Luck Save", "zh": "黑暗主运气豁免", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={"normal_ft": 5},
        target_policy={"min": 1, "max": 1, "harmful": False},
        automation=[{"type": "saving_throw", "ability": "dex", "difficulty_tier": "medium"}],
    )

    result = AutomationExecutor(
        state,
        _FixedSingleDieRollService([9, 6]),
        AuditLog(),
    ).execute(
        action,
        actor_id="goblin1",
        targets=["pc2"],
        params={"use_dark_ones_own_luck": True},
    )

    save_node = result.node_results["automation[0]"]
    assert save_node["total"] == 15
    assert save_node["success"] is True
    assert save_node["dark_ones_own_luck"] == {
        "resource": "srd.resource.dark_ones_own_luck",
        "resource_before": 2,
        "resource_after": 1,
        "roll_total": 6,
        "total_before": 9,
        "total_after": 15,
        "spent": True,
    }
    assert target.resources["srd.resource.dark_ones_own_luck"] == 1
    assert any(
        change["type"] == "dark_ones_own_luck"
        and change["source_action_id"] == "srd.dark_ones_own_luck"
        for change in result.state_changes
    )


def test_fighter_indomitable_rerolls_failed_direct_saving_throw(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"fighter": 9}
    character.saving_throw_proficiencies = ["con"]
    character.resources["srd.resource.indomitable"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([3, 2]),
    )

    result = tools.roll_save(
        "pc1",
        "con",
        difficulty_tier="medium",
        use_indomitable=True,
        idempotency_key="indomitable-direct-save",
    )

    assert result["total"] == 15
    assert result["success"] is True
    assert result["roll"]["expression"] == "1d20+13"
    assert result["indomitable"] == {
        "resource": "srd.resource.indomitable",
        "resource_before": 1,
        "resource_after": 0,
        "fighter_level_bonus": 9,
        "original_roll": {
            "roll_id": "fixed-0",
            "expression": "1d20+4",
            "seed": 0,
            "counter": 0,
            "advantage": None,
            "dice": [{"sides": 20, "value": 3, "kept": True}],
            "modifier_total": 4,
            "total": 7,
            "display": "1d20+4: fixed => 7",
            "replayed": False,
        },
        "total_before": 7,
        "reroll_total": 15,
        "total_after": 15,
        "spent": True,
        "success": True,
    }
    assert character.resources["srd.resource.indomitable"] == 0


def test_fighter_indomitable_automation_save_must_use_new_roll_even_if_failed(
    make_state,
) -> None:
    state = make_state()
    target = state.characters["pc2"]
    target.class_levels = {"fighter": 9}
    target.resources["srd.resource.indomitable"] = 1
    action = ActionDefinition(
        id="test.indomitable_save",
        name="Indomitable Save",
        localization={"en": "Indomitable Save", "zh": "不屈豁免", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={"normal_ft": 5},
        target_policy={"min": 1, "max": 1, "harmful": False},
        automation=[{"type": "saving_throw", "ability": "dex", "difficulty_tier": "medium"}],
    )

    result = AutomationExecutor(
        state,
        _FixedSingleDieRollService([14, 1]),
        AuditLog(),
    ).execute(
        action,
        actor_id="goblin1",
        targets=["pc2"],
        params={"use_indomitable": True},
    )

    save_node = result.node_results["automation[0]"]
    assert save_node["total"] == 10
    assert save_node["success"] is False
    assert save_node["indomitable"] == {
        "resource": "srd.resource.indomitable",
        "resource_before": 1,
        "resource_after": 0,
        "fighter_level_bonus": 9,
        "total_before": 14,
        "reroll_base_total": 10,
        "passive_adjustment": 0,
        "total_after": 10,
        "spent": True,
        "success": False,
    }
    assert target.resources["srd.resource.indomitable"] == 0
    assert any(
        change["type"] == "indomitable" and change["source_action_id"] == "srd.indomitable"
        for change in result.state_changes
    )


def test_fighter_studied_attacks_grants_targeted_advantage_after_miss(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"fighter": 13}
    state.encounter.initiative_order = ["pc1", "goblin1", "goblin2"]
    state.encounter.combatants["goblin1"].armor_class = 30
    state.encounter.combatants["goblin2"] = Combatant(
        id="goblin2",
        entity_id="goblin2",
        name="Goblin 2",
        side="monsters",
        hp_current=20,
        hp_max=20,
        armor_class=1,
        position_node_id="cover",
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([5, 10, 4, 12, 5]),
    )

    miss = tools.perform_action(
        "pc1",
        "srd.shortsword_attack",
        ["goblin1"],
        idempotency_key="studied-attacks-miss",
    )

    assert miss["node_results"]["automation[1]"]["hit"] is False
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["condition"] == "studied_attacks"
    assert effect["source_action_id"] == "srd.studied_attacks"
    assert effect["passive_modifiers"] == {
        "studied_attacks_advantage": True,
        "studied_attacks_target_id": "goblin1",
    }
    assert effect["duration"] == {"until": "end_of_next_turn", "remaining_ticks": 2}
    assert effect["tick_on"] == "self_turn_end"

    tools.economy.add("pc1", "action", 1)
    other_target = tools.perform_action(
        "pc1",
        "srd.shortsword_attack",
        ["goblin2"],
        idempotency_key="studied-attacks-other-target",
    )

    assert other_target["dice_rolls"][0]["advantage"] is None
    assert any(
        existing["condition"] == "studied_attacks"
        for existing in state.encounter.combatants["pc1"].status_effects
    )

    state.encounter.combatants["goblin1"].armor_class = 1
    tools.economy.add("pc1", "action", 1)
    studied_target = tools.perform_action(
        "pc1",
        "srd.shortsword_attack",
        ["goblin1"],
        idempotency_key="studied-attacks-target",
    )

    attack_node = studied_target["node_results"]["automation[1]"]
    assert studied_target["dice_rolls"][0]["advantage"] == "advantage"
    assert attack_node["status_advantage"] == "advantage"
    assert attack_node["status_sources"][0]["modifier"] == "studied_attacks_advantage"
    assert any(
        change["type"] == "effect_expired"
        and change["trigger"] == "studied_attacks_attack"
        and change["removed"][0]["condition"] == "studied_attacks"
        for change in studied_target["state_changes"]
    )
    assert not any(
        existing["condition"] == "studied_attacks"
        for existing in state.encounter.combatants["pc1"].status_effects
    )


def test_fighter_studied_attacks_expires_at_end_of_next_turn(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"fighter": 13}
    state.encounter.initiative_order = ["pc1", "goblin1"]
    state.encounter.combatants["goblin1"].armor_class = 30
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([5]),
    )

    tools.perform_action(
        "pc1",
        "srd.shortsword_attack",
        ["goblin1"],
        idempotency_key="studied-attacks-expiry",
    )

    first_tick = tick_effects(state, trigger="self_turn_end", actor_id="pc1")
    assert first_tick.ticked[0]["condition"] == "studied_attacks"
    assert first_tick.ticked[0]["remaining_ticks_after"] == 1

    second_tick = tick_effects(state, trigger="self_turn_end", actor_id="pc1")
    assert second_tick.expired[0]["condition"] == "studied_attacks"
    assert not any(
        effect["condition"] == "studied_attacks"
        for effect in state.encounter.combatants["pc1"].status_effects
    )


def test_armor_of_shadows_casts_mage_armor_without_spell_slot(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 1}
    character.abilities["dex"] = 14
    character.armor_class = 10
    character.feature_choices = {"warlock.eldritch_invocation.armor_of_shadows": "selected"}
    character.actions.extend(["srd.armor_of_shadows", "srd.armor_of_shadows_mage_armor"])
    character.spell_slots["1"] = 0
    state.encounter.combatants["pc1"].armor_class = 10
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.armor_of_shadows_mage_armor",
        [],
        idempotency_key="armor-of-shadows",
    )

    assert result["success"] is True
    assert character.spell_slots["1"] == 0
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.armor_of_shadows_mage_armor"
    assert effect["passive_modifiers"] == {"armor_class_formula": "13+dex_modifier"}

    attack = AutomationExecutor(
        state,
        _FixedSingleDieRollService([10]),
        AuditLog(),
    ).execute(_attack_action(attack_bonus=4), actor_id="goblin1", targets=["pc1"])
    attack_node = attack.node_results["automation[1]"]
    assert attack_node["base_ac"] == 10
    assert attack_node["ac"] == 15
    assert attack_node["hit"] is False
    assert attack_node["armor_class_sources"][0]["source_action_id"] == (
        "srd.armor_of_shadows_mage_armor"
    )


def test_armor_of_shadows_rejects_mage_armor_while_wearing_armor(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 1}
    character.feature_choices = {"warlock.eldritch_invocation.armor_of_shadows": "selected"}
    character.actions.extend(["srd.armor_of_shadows", "srd.armor_of_shadows_mage_armor"])
    character.equipment = ["srd.leather_armor"]
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="Mage Armor target must not be wearing armor"):
        tools.perform_action(
            "pc1",
            "srd.armor_of_shadows_mage_armor",
            [],
            idempotency_key="armor-of-shadows-armored",
        )

    assert state.encounter.combatants["pc1"].status_effects == []


def test_fiendish_vigor_casts_false_life_without_spell_slot(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 2}
    character.feature_choices = {"warlock.eldritch_invocation.fiendish_vigor": "selected"}
    character.actions.extend(["srd.fiendish_vigor", "srd.fiendish_vigor_false_life"])
    character.spell_slots["1"] = 0
    state.encounter.combatants["pc1"].temp_hp = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.fiendish_vigor_false_life",
        [],
        idempotency_key="fiendish-vigor",
    )

    assert result["success"] is True
    assert character.spell_slots["1"] == 0
    assert state.encounter.combatants["pc1"].temp_hp == 12
    assert result["state_changes"][-1] == {
        "type": "temp_hp",
        "target_id": "pc1",
        "before": 0,
        "after": 12,
        "path": "automation[1]",
    }
    assert result["dice_rolls"] == []


def test_fiendish_vigor_keeps_higher_existing_temp_hp(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 2}
    character.feature_choices = {"warlock.eldritch_invocation.fiendish_vigor": "selected"}
    character.actions.extend(["srd.fiendish_vigor", "srd.fiendish_vigor_false_life"])
    state.encounter.combatants["pc1"].temp_hp = 15
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.fiendish_vigor_false_life",
        [],
        idempotency_key="fiendish-vigor-higher-temp-hp",
    )

    assert result["success"] is True
    assert state.encounter.combatants["pc1"].temp_hp == 15
    assert result["state_changes"][-1]["before"] == 15
    assert result["state_changes"][-1]["after"] == 15


def test_mask_of_many_faces_casts_disguise_self_without_spell_slot(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 2}
    character.feature_choices = {"warlock.eldritch_invocation.mask_of_many_faces": "selected"}
    character.actions.extend(["srd.mask_of_many_faces", "srd.mask_of_many_faces_disguise_self"])
    character.spell_slots["1"] = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.mask_of_many_faces_disguise_self",
        [],
        idempotency_key="mask-of-many-faces",
    )

    assert result["success"] is True
    assert character.spell_slots["1"] == 0
    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.mask_of_many_faces_disguise_self"
    assert effect["effect_type"] == "illusory_disguise"
    assert effect["scope"] == {"target": "self"}
    assert effect["duration"] == {"until": "duration_1_hour"}
    assert effect["metadata"] == {"requires_investigation_to_notice": True}
    assert result["state_changes"][-1]["type"] == "world_effect"
    assert result["state_changes"][-1]["effect_type"] == "illusory_disguise"


def test_misty_visions_casts_silent_image_without_spell_slot(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 2}
    character.feature_choices = {"warlock.eldritch_invocation.misty_visions": "selected"}
    character.actions.extend(["srd.misty_visions", "srd.misty_visions_silent_image"])
    character.spell_slots["1"] = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.misty_visions_silent_image",
        [],
        idempotency_key="misty-visions",
    )

    assert result["success"] is True
    assert character.spell_slots["1"] == 0
    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.misty_visions_silent_image"
    assert effect["effect_type"] == "silent_illusion"
    assert effect["concentration"] is True
    assert effect["scope"] == {"target": "point", "range_ft": 60, "cube_ft": 15}
    assert effect["duration"] == {"until": "concentration_10_minutes"}
    assert effect["metadata"] == {"visual_only": True, "concentration": True}
    assert result["state_changes"][-1]["type"] == "world_effect"
    assert result["state_changes"][-1]["effect_type"] == "silent_illusion"
    assert result["state_changes"][-1]["concentration"] is True


def test_otherworldly_leap_casts_jump_on_self_without_spell_slot(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 2}
    character.feature_choices = {"warlock.eldritch_invocation.otherworldly_leap": "selected"}
    character.actions.extend(["srd.otherworldly_leap", "srd.otherworldly_leap_jump"])
    character.spell_slots["1"] = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.otherworldly_leap_jump",
        [],
        idempotency_key="otherworldly-leap",
    )

    assert result["success"] is True
    assert character.spell_slots["1"] == 0
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.otherworldly_leap_jump"
    assert effect["passive_modifiers"] == {"jump_distance_multiplier": 3}
    assert effect["duration"] == {"until": "duration_1_minute"}
    assert effect["tick_on"] == "movement"
    assert result["state_changes"][-1]["type"] == "passive_effect"
    assert result["state_changes"][-1]["target_id"] == "pc1"
    assert result["state_changes"][-1]["passive_modifiers"] == {"jump_distance_multiplier": 3}


def test_divine_sense_spends_paladin_channel_divinity_and_applies_detection(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"paladin": 3}
    character.actions.append("srd.divine_sense")
    character.resources["srd.resource.channel_divinity"] = 2
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action("pc1", "srd.divine_sense", [], idempotency_key="divine-sense")

    assert result["success"] is True
    assert character.resources["srd.resource.channel_divinity"] == 1
    assert state.encounter.action_budgets["pc1"]["bonus_action"] == 0
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["condition"] == "divine_sense"
    assert effect["duration"] == {"until": "duration_10_minutes"}
    assert effect["tick_on"] == "self_turn_start"
    assert effect["passive_modifiers"] == {
        "detect_creature_types": ["celestial", "fiend", "undead"],
        "detect_radius_ft": 60,
        "detect_consecrated_or_desecrated": True,
        "ends_if_condition": "incapacitated",
    }


def test_devotion_paladin_sacred_weapon_boosts_selected_melee_weapon_attack(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"paladin": 3}
    character.subclasses = {"paladin": "devotion"}
    character.abilities["cha"] = 16
    character.actions.extend(["srd.sacred_weapon", "srd.longsword_attack"])
    character.resources["srd.resource.channel_divinity"] = 2
    state.encounter.combatants["goblin1"].hp_current = 7
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([5, 4]),
    )

    sacred = tools.perform_action(
        "pc1",
        "srd.sacred_weapon",
        [],
        {"sacred_weapon_action_id": "srd.longsword_attack"},
        idempotency_key="sacred-weapon",
    )
    attack = tools.perform_action(
        "pc1",
        "srd.longsword_attack",
        ["goblin1"],
        {"sacred_weapon_damage_type": "radiant"},
        idempotency_key="sacred-weapon-attack",
    )

    assert sacred["success"] is True
    assert character.resources["srd.resource.channel_divinity"] == 1
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["condition"] == "sacred_weapon"
    assert effect["passive_modifiers"]["sacred_weapon_action_id"] == "srd.longsword_attack"
    attack_roll = attack["node_results"]["automation[1]"]
    assert attack_roll["base_total"] == 9
    assert attack_roll["passive_adjustment"] == 3
    assert attack_roll["total"] == 12
    assert attack_roll["hit"] is True
    assert attack_roll["passive_sources"] == [
        {
            "effect_id": effect["effect_id"],
            "source_action_id": "srd.sacred_weapon",
            "modifier": "sacred_weapon_attack_bonus",
            "ability": "cha",
            "minimum": 1,
            "amount": 3,
            "selected_action_id": "srd.longsword_attack",
        }
    ]
    damage_change = next(change for change in attack["state_changes"] if change["type"] == "damage")
    assert damage_change["damage_type"] == "radiant"
    assert damage_change["amount"] == 6
    assert state.encounter.combatants["goblin1"].hp_current == 1


def test_devotion_paladin_sacred_weapon_requires_weapon_selection_before_cost(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"paladin": 3}
    character.subclasses = {"paladin": "devotion"}
    character.actions.append("srd.sacred_weapon")
    character.resources["srd.resource.channel_divinity"] = 2
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="sacred_weapon_action_id"):
        tools.perform_action(
            "pc1",
            "srd.sacred_weapon",
            [],
            {},
            idempotency_key="sacred-weapon-missing-selection",
        )

    assert character.resources["srd.resource.channel_divinity"] == 2
    assert state.encounter.action_budgets == {}


def test_rage_applies_srd_passive_effects_and_blocks_spellcasting(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"barbarian": 1}
    state.characters["pc1"].actions.extend(["srd.rage", "srd.cure_wounds"])
    state.characters["pc1"].resources["srd.resource.rage"] = 2
    state.characters["pc1"].spell_slots["1"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action("pc1", "srd.rage", [], idempotency_key="rage")

    assert result["success"] is True
    assert state.characters["pc1"].resources["srd.resource.rage"] == 1
    assert state.encounter.action_budgets["pc1"]["bonus_action"] == 0
    rage_effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert rage_effect["condition"] == "raging"
    assert rage_effect["duration"] == {"until": "end_of_next_turn", "remaining_ticks": 2}
    assert rage_effect["tick_on"] == "self_turn_end"
    assert rage_effect["passive_modifiers"]["damage_resistances"] == [
        "bludgeoning",
        "piercing",
        "slashing",
    ]

    with pytest.raises(AutomationError, match="cannot cast spells"):
        tools.cast_spell("pc1", "srd.cure_wounds", ["pc1"], 1)
    assert state.characters["pc1"].spell_slots["1"] == 1

    check_action = ActionDefinition(
        id="test.str_check",
        name="Test Strength Check",
        localization={"en": "Test Strength Check", "zh": "测试力量检定", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={"self": True},
        target_policy={"min": 0, "max": 0, "self": True},
        automation=[
            {"type": "target", "mode": "self"},
            {"type": "ability_check", "ability": "str", "difficulty_tier": "medium"},
        ],
    )
    check = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        check_action,
        actor_id="pc1",
    )
    assert check.node_results["automation[1]"]["status_advantage"] == "advantage"

    save_action = ActionDefinition(
        id="test.str_save",
        name="Test Strength Save",
        localization={"en": "Test Strength Save", "zh": "测试力量豁免", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={},
        target_policy={"min": 1, "max": 1, "harmful": False},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "saving_throw", "ability": "str", "difficulty_tier": "medium"},
        ],
    )
    save = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        save_action,
        actor_id="goblin1",
        targets=["pc1"],
    )
    assert save.node_results["automation[1]"]["status_advantage"] == "advantage"

    damage_action = ActionDefinition(
        id="test.slashing_damage",
        name="Test Slashing Damage",
        localization={"en": "Test Slashing Damage", "zh": "测试挥砍伤害", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "damage", "amount": 9, "damage_type": "slashing"},
        ],
    )
    damage = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        damage_action,
        actor_id="goblin1",
        targets=["pc1"],
    )
    damage_change = next(change for change in damage.state_changes if change["type"] == "damage")
    assert damage_change["amount"] == 9
    assert damage_change["applied"] == 4


def test_berserker_mindless_rage_ends_charmed_frightened_and_grants_immunity(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"barbarian": 6}
    character.subclasses = {"barbarian": "berserker"}
    character.actions.extend(["srd.rage", "srd.mindless_rage"])
    character.resources["srd.resource.rage"] = 1
    state.encounter.combatants["pc1"].status_effects.extend(
        [
            {"effect_id": "charm-test", "condition": "charmed"},
            {"effect_id": "fright-test", "condition": "frightened"},
        ]
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.rage",
        [],
        idempotency_key="mindless-rage",
    )

    assert result["success"] is True
    rage_effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert rage_effect["condition"] == "raging"
    assert rage_effect["passive_modifiers"]["condition_immunities"] == [
        "charmed",
        "frightened",
    ]
    mindless_change = next(
        change for change in result["state_changes"] if change["type"] == "mindless_rage"
    )
    assert mindless_change["source_action_id"] == "srd.mindless_rage"
    assert mindless_change["removed"] == {"charmed": 1, "frightened": 1}
    assert [effect["condition"] for effect in state.encounter.combatants["pc1"].status_effects] == [
        "raging"
    ]

    charm_action = ActionDefinition(
        id="test.charm",
        name="Test Charm",
        localization={"en": "Test Charm", "zh": "测试魅惑", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "condition", "condition": "charmed"},
        ],
    )
    charm = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        charm_action,
        actor_id="goblin1",
        targets=["pc1"],
    )

    immune_change = next(
        change for change in charm.state_changes if change["type"] == "condition_immune"
    )
    assert immune_change["condition"] == "charmed"
    assert immune_change["immunity_sources"][0]["source_action_id"] == "srd.rage"
    assert [effect["condition"] for effect in state.encounter.combatants["pc1"].status_effects] == [
        "raging"
    ]


def test_non_berserker_rage_does_not_gain_mindless_rage_immunity(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"barbarian": 6}
    character.actions.append("srd.rage")
    character.resources["srd.resource.rage"] = 1
    state.encounter.combatants["pc1"].status_effects.append(
        {"effect_id": "charm-test", "condition": "charmed"}
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action("pc1", "srd.rage", [], idempotency_key="rage-no-mindless")

    rage_effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert "condition_immunities" not in rage_effect["passive_modifiers"]
    assert not any(change["type"] == "mindless_rage" for change in result["state_changes"])
    assert [effect["condition"] for effect in state.encounter.combatants["pc1"].status_effects] == [
        "charmed",
        "raging",
    ]


def test_reckless_attack_grants_strength_attack_advantage(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"barbarian": 2}
    state.characters["pc1"].actions.extend(["srd.reckless_attack", "srd.longsword_attack"])
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action("pc1", "srd.reckless_attack", [])

    assert result["success"] is True
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["condition"] == "reckless_attack"
    assert effect["duration"] == {"until": "start_of_next_turn"}
    assert effect["tick_on"] == "self_turn_start"
    assert effect["passive_modifiers"] == {
        "weapon_attack_advantage_by_ability": ["str"],
        "incoming_attack_advantage": True,
    }

    attack = tools.perform_action("pc1", "srd.longsword_attack", ["goblin1"])
    attack_node = attack["node_results"]["automation[1]"]
    assert attack["dice_rolls"][0]["advantage"] == "advantage"
    assert attack_node["ability"] == "str"
    assert attack_node["status_advantage"] == "advantage"
    assert attack_node["status_sources"][0]["modifier"] == "weapon_attack_advantage_by_ability"


def test_reckless_attack_does_not_grant_dex_attack_advantage(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"barbarian": 2}
    state.characters["pc1"].actions.append("srd.reckless_attack")
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    tools.perform_action("pc1", "srd.reckless_attack", [])
    attack = tools.perform_action("pc1", "srd.shortsword_attack", ["goblin1"])

    attack_node = attack["node_results"]["automation[1]"]
    assert attack["dice_rolls"][0]["advantage"] is None
    assert attack_node["ability"] == "dex"
    assert attack_node["status_advantage"] is None


def test_reckless_attack_grants_incoming_attack_advantage(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"barbarian": 2}
    state.characters["pc1"].actions.append("srd.reckless_attack")
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    tools.perform_action("pc1", "srd.reckless_attack", [])
    attack = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        _attack_action(),
        actor_id="goblin1",
        targets=["pc1"],
    )

    attack_node = attack.node_results["automation[1]"]
    assert attack.dice_rolls[0]["advantage"] == "advantage"
    assert attack_node["status_advantage"] == "advantage"
    assert attack_node["status_sources"][0]["modifier"] == "incoming_attack_advantage"


def test_innate_sorcery_boosts_sorcerer_spell_dc_and_attack_rolls(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"sorcerer": 1}
    state.characters["pc1"].abilities["cha"] = 16
    state.characters["pc1"].actions.append("srd.innate_sorcery")
    state.characters["pc1"].resources["srd.resource.innate_sorcery"] = 2
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.innate_sorcery",
        [],
        idempotency_key="innate-sorcery",
    )

    assert result["success"] is True
    assert state.characters["pc1"].resources["srd.resource.innate_sorcery"] == 1
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["condition"] == "innate_sorcery"
    assert effect["passive_modifiers"] == {
        "spell_save_dc_bonus": {"sorcerer": 1},
        "spell_attack_advantage_classes": ["sorcerer"],
    }

    save_action = ActionDefinition(
        id="test.sorcerer_save_spell",
        name="Sorcerer Save Spell",
        localization={"en": "Sorcerer Save Spell", "zh": "术法师豁免法术", "aliases": []},
        source="test",
        rules_version="test",
        action_type="spell",
        action_economy="none",
        range={"normal_ft": 30},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "saving_throw", "ability": "wis", "dc_from": {"spell_save_dc": "sorcerer"}},
        ],
    )
    save = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        save_action,
        actor_id="pc1",
        targets=["goblin1"],
        idempotency_key="innate-sorcery-save",
    )
    save_node = save.node_results["automation[1]"]
    assert save_node["dc"] == 14
    assert save_node["dc_source"] == "spell_save_dc:sorcerer+1"

    attack_action = ActionDefinition(
        id="test.sorcerer_attack_spell",
        name="Sorcerer Attack Spell",
        localization={"en": "Sorcerer Attack Spell", "zh": "术法师攻击法术", "aliases": []},
        source="test",
        rules_version="test",
        action_type="spell",
        action_economy="none",
        range={"normal_ft": 60},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "attack_roll", "attack_bonus": 5},
        ],
    )
    attack = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        attack_action,
        actor_id="pc1",
        targets=["goblin1"],
        idempotency_key="innate-sorcery-attack",
    )
    attack_node = attack.node_results["automation[1]"]
    assert attack_node["status_advantage"] == "advantage"
    assert attack_node["status_sources"][0]["modifier"] == "spell_attack_advantage_classes"
    assert attack.dice_rolls[0]["advantage"] == "advantage"


def test_magical_cunning_recovers_half_of_expended_pact_magic_slots(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 3}
    character.actions.append("srd.magical_cunning")
    character.resources["srd.resource.magical_cunning"] = 1
    character.spell_slots = {"2": 0}
    character.spell_slots_max = {"2": 2}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.magical_cunning",
        [],
        idempotency_key="magical-cunning",
    )

    assert result["success"] is True
    assert character.resources["srd.resource.magical_cunning"] == 0
    assert character.spell_slots == {"2": 1}
    assert any(
        change["type"] == "pact_magic_recovery"
        and change["recovered"] == {"2": 1}
        and change["after"] == {"2": 1}
        for change in result["state_changes"]
    )


def test_font_of_magic_converts_spell_slot_to_capped_sorcery_points(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"sorcerer": 2}
    state.characters["pc1"].actions.append("srd.font_of_magic_convert_slot_1")
    state.characters["pc1"].resources["srd.resource.sorcery_points"] = 1
    state.characters["pc1"].spell_slots["1"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.font_of_magic_convert_slot_1",
        [],
        idempotency_key="font-convert-slot-1",
    )

    assert result["success"] is True
    assert state.characters["pc1"].spell_slots["1"] == 0
    assert state.characters["pc1"].resources["srd.resource.sorcery_points"] == 2
    assert any(
        change["type"] == "resource_delta"
        and change["resource"] == "srd.resource.sorcery_points"
        and change["after"] == 2
        for change in result["state_changes"]
    )

    state.characters["pc1"].spell_slots["1"] = 1
    with pytest.raises(
        AutomationError,
        match="resource srd.resource.sorcery_points would exceed maximum 2",
    ):
        tools.perform_action(
            "pc1",
            "srd.font_of_magic_convert_slot_1",
            [],
            idempotency_key="font-convert-slot-1-over-cap",
        )

    assert state.characters["pc1"].spell_slots["1"] == 1
    assert state.characters["pc1"].resources["srd.resource.sorcery_points"] == 2


def test_font_of_magic_creates_spell_slot_from_sorcery_points(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"sorcerer": 3}
    state.characters["pc1"].actions.append("srd.font_of_magic_create_slot_2")
    state.characters["pc1"].resources["srd.resource.sorcery_points"] = 3
    state.characters["pc1"].spell_slots["2"] = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.font_of_magic_create_slot_2",
        [],
        idempotency_key="font-create-slot-2",
    )

    assert result["success"] is True
    assert state.characters["pc1"].resources["srd.resource.sorcery_points"] == 0
    assert state.characters["pc1"].spell_slots["2"] == 1
    assert state.encounter.action_budgets["pc1"]["bonus_action"] == 0
    assert any(
        change["type"] == "resource_delta"
        and change["resource"] == "spell_slot_2"
        and change["after"] == 1
        for change in result["state_changes"]
    )


def test_rage_adds_srd_strength_weapon_damage_bonus(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"barbarian": 1}
    state.characters["pc1"].actions.append("srd.rage")
    state.characters["pc1"].resources["srd.resource.rage"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())
    tools.perform_action("pc1", "srd.rage", [], idempotency_key="rage-damage")

    weapon_action = ActionDefinition(
        id="test.str_weapon",
        name="Test Strength Weapon",
        localization={"en": "Test Strength Weapon", "zh": "测试力量武器", "aliases": []},
        source="test",
        rules_version="test",
        action_type="weapon_attack",
        action_economy="none",
        range={"normal_ft": 5},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "attack_roll", "attack_bonus": 99},
            {
                "type": "damage",
                "amount": 5,
                "damage_type": "slashing",
                "ability": "str",
                "requires_hit": True,
            },
        ],
    )

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        weapon_action,
        actor_id="pc1",
        targets=["goblin1"],
    )

    damage_change = next(change for change in result.state_changes if change["type"] == "damage")
    assert damage_change["amount"] == 7
    assert damage_change["passive_damage_bonus"] == 2
    assert damage_change["passive_sources"][0]["source_action_id"] == "srd.rage"


def test_berserker_frenzy_adds_rage_damage_bonus_d6s_to_first_reckless_rage_hit(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].hp_current = 50
    state.encounter.combatants["goblin1"].hp_max = 50
    character = state.characters["pc1"]
    character.class_levels = {"barbarian": 3}
    character.subclasses = {"barbarian": "berserker"}
    character.actions.extend(["srd.rage", "srd.reckless_attack", "srd.frenzy"])
    character.resources["srd.resource.rage"] = 3
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())
    tools.perform_action("pc1", "srd.rage", [], idempotency_key="frenzy-rage")
    tools.perform_action("pc1", "srd.reckless_attack", [], idempotency_key="frenzy-reckless")
    weapon_action = ActionDefinition(
        id="test.frenzy_str_weapon",
        name="Test Frenzy Strength Weapon",
        localization={"en": "Test Frenzy Strength Weapon", "zh": "测试狂乱力量武器", "aliases": []},
        source="test",
        rules_version="test",
        action_type="weapon_attack",
        action_economy="none",
        range={"normal_ft": 5},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "attack_roll", "attack_bonus": 99, "ability": "str"},
            {
                "type": "damage",
                "amount": 5,
                "damage_type": "slashing",
                "ability": "str",
                "requires_hit": True,
            },
        ],
    )

    result = AutomationExecutor(
        state,
        _FixedSingleDieRollService([10, 5]),
        AuditLog(),
    ).execute(
        weapon_action,
        actor_id="pc1",
        targets=["goblin1"],
    )

    damage_change = next(change for change in result.state_changes if change["type"] == "damage")
    frenzy_change = next(change for change in result.state_changes if change["type"] == "frenzy")
    assert damage_change["amount"] == 12
    assert damage_change["passive_damage_bonus"] == 2
    assert damage_change["frenzy_bonus"] == 5
    assert damage_change["frenzy_sources"] == [
        {
            "feature": "frenzy",
            "source_action_id": "srd.frenzy",
            "barbarian_level": 3,
            "rage_damage_bonus": 2,
            "dice": "2d6",
            "damage_type": "slashing",
        }
    ]
    assert frenzy_change["condition"] == "frenzy_used"
    assert any(
        effect["condition"] == "frenzy_used"
        for effect in state.encounter.combatants["pc1"].status_effects
    )


def test_berserker_frenzy_applies_only_once_per_turn(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].hp_current = 50
    state.encounter.combatants["goblin1"].hp_max = 50
    character = state.characters["pc1"]
    character.class_levels = {"barbarian": 3}
    character.subclasses = {"barbarian": "berserker"}
    character.actions.extend(["srd.rage", "srd.reckless_attack", "srd.frenzy"])
    character.resources["srd.resource.rage"] = 3
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())
    tools.perform_action("pc1", "srd.rage", [], idempotency_key="frenzy-once-rage")
    tools.perform_action("pc1", "srd.reckless_attack", [], idempotency_key="frenzy-once-reckless")
    weapon_action = ActionDefinition(
        id="test.frenzy_once_str_weapon",
        name="Test Frenzy Once Strength Weapon",
        localization={
            "en": "Test Frenzy Once Strength Weapon",
            "zh": "测试狂乱一次",
            "aliases": [],
        },
        source="test",
        rules_version="test",
        action_type="weapon_attack",
        action_economy="none",
        range={"normal_ft": 5},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "attack_roll", "attack_bonus": 99, "ability": "str"},
            {
                "type": "damage",
                "amount": 5,
                "damage_type": "slashing",
                "ability": "str",
                "requires_hit": True,
            },
        ],
    )

    first = AutomationExecutor(
        state,
        _FixedSingleDieRollService([10, 5]),
        AuditLog(),
    ).execute(weapon_action, actor_id="pc1", targets=["goblin1"])
    second = AutomationExecutor(
        state,
        _FixedSingleDieRollService([10]),
        AuditLog(),
    ).execute(weapon_action, actor_id="pc1", targets=["goblin1"])

    first_damage = next(change for change in first.state_changes if change["type"] == "damage")
    second_damage = next(change for change in second.state_changes if change["type"] == "damage")
    assert "frenzy_bonus" in first_damage
    assert "frenzy_bonus" not in second_damage
    assert (
        sum(
            1
            for effect in state.encounter.combatants["pc1"].status_effects
            if effect["condition"] == "frenzy_used"
        )
        == 1
    )


def test_berserker_frenzy_requires_berserker_subclass(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"barbarian": 3}
    character.actions.extend(["srd.rage", "srd.reckless_attack"])
    character.resources["srd.resource.rage"] = 3
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())
    tools.perform_action("pc1", "srd.rage", [], idempotency_key="frenzy-non-subclass-rage")
    tools.perform_action(
        "pc1",
        "srd.reckless_attack",
        [],
        idempotency_key="frenzy-non-subclass-reckless",
    )
    weapon_action = ActionDefinition(
        id="test.no_frenzy_str_weapon",
        name="Test No Frenzy Strength Weapon",
        localization={"en": "Test No Frenzy Strength Weapon", "zh": "测试非狂乱", "aliases": []},
        source="test",
        rules_version="test",
        action_type="weapon_attack",
        action_economy="none",
        range={"normal_ft": 5},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "attack_roll", "attack_bonus": 99, "ability": "str"},
            {
                "type": "damage",
                "amount": 5,
                "damage_type": "slashing",
                "ability": "str",
                "requires_hit": True,
            },
        ],
    )

    result = AutomationExecutor(
        state,
        _FixedSingleDieRollService([10]),
        AuditLog(),
    ).execute(weapon_action, actor_id="pc1", targets=["goblin1"])

    damage_change = next(change for change in result.state_changes if change["type"] == "damage")
    assert damage_change["amount"] == 7
    assert "frenzy_bonus" not in damage_change


def test_award_accepts_only_gold_or_loaded_srd_items(make_state) -> None:
    state = make_state()
    compendium = CompendiumLoader("rules_data").load()
    audit = AuditLog()
    tools = EngineTools(state, compendium, audit)

    gold = tools.award(["pc1"], "gold:5", idempotency_key="award-gold")
    item = tools.award(
        ["pc1"],
        "item:srd.potion_of_healing",
        idempotency_key="award-srd-item",
    )

    assert gold["reward"] == {"kind": "gold", "amount": 5}
    assert state.characters["pc1"].gold == 5
    assert item["reward"] == {
        "kind": "item",
        "item_id": "srd.potion_of_healing",
        "quantity": 1,
    }
    assert state.characters["pc1"].inventory["srd.potion_of_healing"] == 1

    with pytest.raises(ValueError, match="unknown reward id"):
        tools.award(["pc1"], "item:srd.imaginary_sword", idempotency_key="award-bad-item")
    with pytest.raises(ValueError, match="gold reward must be positive"):
        tools.award(["pc1"], "gold:-1", idempotency_key="award-negative-gold")

    assert state.characters["pc1"].gold == 5
    assert "srd.imaginary_sword" not in state.characters["pc1"].inventory
    assert [event.tool_name for event in audit.events] == ["award", "award"]


def test_award_applies_predefined_campaign_reward_from_state(make_state) -> None:
    state = make_state()
    state.world.flags["campaign_rewards"] = {
        "starter.first_victory": {
            "gold": 12,
            "experience": 50,
            "items": [{"item_id": "srd.potion_of_healing", "quantity": 2}],
        }
    }
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.award(["pc1"], "starter.first_victory", idempotency_key="award-pack")

    assert result["reward"] == {
        "kind": "campaign_reward",
        "reward_id": "starter.first_victory",
        "gold": 12,
        "experience": 50,
        "items": [{"item_id": "srd.potion_of_healing", "quantity": 2}],
    }
    assert state.characters["pc1"].gold == 12
    assert state.characters["pc1"].experience == 50
    assert state.characters["pc1"].inventory["srd.potion_of_healing"] == 2
    assert [change["type"] for change in result["changes"]] == [
        "gold",
        "experience",
        "item",
    ]


def test_srd_healing_potion_variants_use_table_dice(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].inventory["srd.potion_of_supreme_healing"] = 1
    state.characters["pc1"].hp_current = 1
    state.encounter.combatants["pc1"].hp_current = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.use_item(
        "pc1",
        "srd.potion_of_supreme_healing",
        ["pc1"],
        idempotency_key="use-supreme-potion",
    )

    assert result["success"] is True
    assert result["action_id"] == "srd.use_potion_of_supreme_healing"
    assert result["dice_rolls"][0]["expression"] == "10d4+20"
    assert state.characters["pc1"].inventory["srd.potion_of_supreme_healing"] == 0


def test_elixir_of_health_removes_srd_conditions_and_magical_contagions(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    target = state.encounter.combatants["pc2"]
    target.status_effects.extend(
        [
            {"effect_id": "blind", "condition": "blinded", "source_action_id": "test"},
            {"effect_id": "deaf", "condition": "deafened", "source_action_id": "test"},
            {"effect_id": "paralysis", "condition": "paralyzed", "source_action_id": "test"},
            {"effect_id": "poison", "condition": "poisoned", "source_action_id": "test"},
            {
                "effect_id": "combat-contagion",
                "source_action_id": "test",
                "passive_modifiers": {"magical_contagion": True},
            },
            {"effect_id": "prone", "condition": "prone", "source_action_id": "test"},
        ]
    )
    state.characters["pc2"].status_effects.append(
        {
            "effect_id": "character-contagion",
            "source_action_id": "test",
            "metadata": {"magical_contagion": True},
        }
    )
    state.characters["pc1"].inventory["srd.elixir_of_health"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.use_item(
        "pc1",
        "srd.elixir_of_health",
        ["pc2"],
        idempotency_key="use-elixir",
    )

    assert result["success"] is True
    assert state.characters["pc1"].inventory["srd.elixir_of_health"] == 0
    assert {effect.get("condition") for effect in target.status_effects} == {"prone"}
    assert state.characters["pc2"].status_effects == []
    remove_change = next(
        change for change in result["state_changes"] if change["type"] == "remove_condition"
    )
    assert remove_change["removed"] == {
        "blinded": 1,
        "deafened": 1,
        "paralyzed": 1,
        "poisoned": 1,
    }
    assert remove_change["removed_markers"] == {"magical_contagion": 2}
    assert {entry["owner_type"] for entry in remove_change["removed_owners"]} == {
        "character",
        "combatant",
    }


def test_invisibility_potion_expires_on_later_attack(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].inventory["srd.potion_of_invisibility"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    potion = tools.use_item(
        "pc1",
        "srd.potion_of_invisibility",
        ["pc1"],
        idempotency_key="use-invisibility-potion",
    )
    assert potion["success"] is True
    assert any(
        effect.get("condition") == "invisible"
        for effect in state.encounter.combatants["pc1"].status_effects
    )

    attack = tools.attack(
        "pc1",
        "goblin1",
        "srd.shortsword_attack",
        idempotency_key="attack-breaks-invisibility",
    )

    assert attack["success"] is True
    assert not [
        effect
        for effect in state.encounter.combatants["pc1"].status_effects
        if effect.get("condition") == "invisible"
    ]
    expiry = next(
        change for change in attack["state_changes"] if change["type"] == "effect_expired"
    )
    assert expiry["trigger"] == "attack"
    assert expiry["removed"][0]["condition"] == "invisible"


def test_invisibility_potion_expires_on_later_spell(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].inventory["srd.potion_of_invisibility"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    potion = tools.use_item(
        "pc1",
        "srd.potion_of_invisibility",
        ["pc1"],
        idempotency_key="use-invisibility-potion-before-spell",
    )
    assert potion["success"] is True

    spell = tools.cast_spell(
        "pc1",
        "srd.cure_wounds",
        ["pc2"],
        1,
        idempotency_key="spell-breaks-invisibility-potion",
    )

    assert spell["success"] is True
    assert not [
        effect
        for effect in state.encounter.combatants["pc1"].status_effects
        if effect.get("condition") == "invisible"
    ]
    expiry = next(change for change in spell["state_changes"] if change["type"] == "effect_expired")
    assert expiry["trigger"] == "spell"
    assert expiry["removed"][0]["source_action_id"] == "srd.use_potion_of_invisibility"


def test_invisibility_potion_expires_when_drinker_later_deals_damage(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].inventory["srd.potion_of_invisibility"] = 1
    state.characters["pc1"].inventory["srd.potion_of_poison"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    potion = tools.use_item(
        "pc1",
        "srd.potion_of_invisibility",
        ["pc1"],
        idempotency_key="use-invisibility-potion-before-damage",
    )
    assert potion["success"] is True
    tools.economy.set("pc1", "bonus_action", 1)

    poison = tools.use_item(
        "pc1",
        "srd.potion_of_poison",
        ["goblin1"],
        idempotency_key="damage-breaks-invisibility-potion",
    )

    assert poison["success"] is True
    assert any(
        change.get("type") == "damage" and int(change.get("applied", 0)) > 0
        for change in poison["state_changes"]
    )
    assert not [
        effect
        for effect in state.encounter.combatants["pc1"].status_effects
        if effect.get("condition") == "invisible"
    ]
    expiry = next(
        change for change in poison["state_changes"] if change["type"] == "effect_expired"
    )
    assert expiry["trigger"] == "damage"
    assert expiry["removed"][0]["condition"] == "invisible"


def test_invisibility_potion_expires_after_one_hour(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].inventory["srd.potion_of_invisibility"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    potion = tools.use_item(
        "pc1",
        "srd.potion_of_invisibility",
        ["pc1"],
        idempotency_key="use-invisibility-potion-duration",
    )

    assert potion["success"] is True
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["condition"] == "invisible"
    assert effect["duration"] == {"until": "duration_1_hour_or_attack_damage_spell"}
    assert effect["tick_on"] == "self_turn_start"

    for _ in range(599):
        lifecycle = tick_effects(state, trigger="self_turn_start", actor_id="pc1")
        assert not lifecycle.expired

    final_lifecycle = tick_effects(state, trigger="self_turn_start", actor_id="pc1")

    assert final_lifecycle.expired[0]["condition"] == "invisible"
    assert final_lifecycle.expired[0]["source_action_id"] == "srd.use_potion_of_invisibility"
    assert not [
        effect
        for effect in state.encounter.combatants["pc1"].status_effects
        if effect.get("condition") == "invisible"
    ]


def test_potion_of_vitality_removes_conditions_and_maximizes_hit_dice_healing(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    combatant = state.encounter.combatants["pc1"]
    character.inventory["srd.potion_of_vitality"] = 1
    character.status_effects = [
        {"effect_id": "char-exhaustion", "condition": "exhaustion", "level": 2},
        {"effect_id": "char-poisoned", "condition": "poisoned"},
    ]
    combatant.status_effects = [
        {"effect_id": "combat-exhaustion", "condition": "exhaustion", "level": 1},
        {"effect_id": "combat-poisoned", "condition": "poisoned"},
    ]
    character.hp_current = 1
    combatant.hp_current = 1
    character.hit_dice = {"d10": 1}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    potion = tools.use_item(
        "pc1",
        "srd.potion_of_vitality",
        ["pc1"],
        idempotency_key="use-vitality-potion",
    )
    roll_counter_after_potion = state.roll_counter
    rest = tools.short_rest(
        "pc1",
        {"d10": 1},
        idempotency_key="vitality-potion-short-rest",
    )

    assert potion["success"] is True
    assert character.inventory["srd.potion_of_vitality"] == 0
    remove_change = next(
        change for change in potion["state_changes"] if change["type"] == "remove_condition"
    )
    assert remove_change["removed"] == {"exhaustion": 2, "poisoned": 2}
    assert {entry["owner_type"] for entry in remove_change["removed_owners"]} == {
        "character",
        "combatant",
    }
    assert all(
        effect.get("condition") not in {"exhaustion", "poisoned"}
        for effect in character.status_effects
    )
    assert all(
        effect.get("condition") not in {"exhaustion", "poisoned"}
        for effect in combatant.status_effects
    )
    character_vitality = character.status_effects[-1]
    combatant_vitality = combatant.status_effects[-1]
    assert character_vitality["source_action_id"] == "srd.use_potion_of_vitality"
    assert combatant_vitality["source_action_id"] == "srd.use_potion_of_vitality"
    assert character_vitality["passive_modifiers"] == {"hit_die_healing_maximized": True}
    assert character_vitality["duration"] == {"until": "duration_24_hours"}
    assert character_vitality["tick_on"] == "environment"

    assert rest["hp_before"] == 1
    assert rest["hp_after"] == 12
    assert rest["healing_rolls"] == [
        {
            "die": "d10",
            "roll_id": None,
            "roll_total": 10,
            "con_modifier": 2,
            "healing": 12,
            "hit_die_healing_maximized": True,
            "passive_sources": [
                {
                    "effect_id": character_vitality["effect_id"],
                    "source_action_id": "srd.use_potion_of_vitality",
                    "modifier": "hit_die_healing_maximized",
                }
            ],
        }
    ]
    assert rest["dice_rolls"] == []
    assert state.roll_counter == roll_counter_after_potion
    assert character.hit_dice["d10"] == 0
    assert combatant.hp_current == 12


def test_potion_of_diminution_applies_reduce_effect_for_rolled_hours(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.inventory["srd.potion_of_diminution"] = 1
    state.encounter.combatants["goblin1"].armor_class = 1
    state.encounter.combatants["goblin1"].hp_current = 30
    state.encounter.combatants["goblin1"].hp_max = 30
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([2, 10, 10, 10, 3, 4]),
    )

    potion = tools.use_item(
        "pc1",
        "srd.potion_of_diminution",
        ["pc1"],
        idempotency_key="use-diminution-potion",
    )
    strength_check = tools.roll_check(
        "pc1",
        "str",
        difficulty_tier="medium",
        idempotency_key="diminution-potion-strength-check",
    )
    strength_save = tools.roll_save(
        "pc1",
        "str",
        difficulty_tier="medium",
        idempotency_key="diminution-potion-strength-save",
    )
    attack = tools.perform_action(
        "pc1",
        "srd.shortsword_attack",
        ["goblin1"],
        idempotency_key="diminution-potion-weapon-hit",
    )

    assert potion["success"] is True
    assert character.inventory["srd.potion_of_diminution"] == 0
    assert potion["dice_rolls"][0]["expression"] == "1d4"
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.use_potion_of_diminution"
    assert effect["condition"] is None
    assert effect["passive_modifiers"] == {
        "size_change": "reduce",
        "size_category_delta": -1,
        "ability_check_disadvantage_abilities": ["str"],
        "saving_throw_disadvantage_abilities": ["str"],
        "reduce_weapon_damage_penalty": "1d4",
    }
    assert effect["duration"] == {
        "until": "duration_1d4_hours",
        "duration_roll": {
            "dice": "1d4",
            "unit": "hours",
            "roll_id": "fixed-0",
            "rolled": 2,
            "ticks_per_unit": 600,
        },
        "remaining_ticks": 1200,
    }
    assert effect["tick_on"] == "self_turn_start"
    assert effect["concentration"] is False
    assert strength_check["roll"]["advantage"] == "disadvantage"
    assert strength_check["status_sources"][0]["modifier"] == (
        "ability_check_disadvantage_abilities"
    )
    assert strength_save["roll"]["advantage"] == "disadvantage"
    assert strength_save["status_sources"][0]["modifier"] == ("saving_throw_disadvantage_abilities")
    damage = next(change for change in attack["state_changes"] if change["type"] == "damage")
    assert damage["amount_before_reduce_weapon_damage_penalty"] == 6
    assert damage["reduce_weapon_damage_penalty"] == 4
    assert damage["amount"] == 2
    assert damage["applied"] == 2
    assert damage["reduce_weapon_damage_sources"][0]["source_action_id"] == (
        "srd.use_potion_of_diminution"
    )

    for _ in range(1199):
        lifecycle = tick_effects(state, trigger="self_turn_start", actor_id="pc1")
        assert lifecycle.expired == []
    final_lifecycle = tick_effects(state, trigger="self_turn_start", actor_id="pc1")
    assert final_lifecycle.expired[0]["source_action_id"] == "srd.use_potion_of_diminution"
    assert state.encounter.combatants["pc1"].status_effects == []


def test_potion_of_hill_giant_strength_sets_strength_for_checks_saves_and_weapon_attacks(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.inventory["srd.potion_of_hill_giant_strength"] = 1
    character.actions.append("srd.longsword_attack")
    state.encounter.combatants["goblin1"].armor_class = 1
    state.encounter.combatants["goblin1"].hp_current = 30
    state.encounter.combatants["goblin1"].hp_max = 30
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([10, 10, 10, 4]),
    )

    potion = tools.use_item(
        "pc1",
        "srd.potion_of_hill_giant_strength",
        ["pc1"],
        idempotency_key="use-hill-giant-strength-potion",
    )
    strength_check = tools.roll_check(
        "pc1",
        "str",
        difficulty_tier="medium",
        idempotency_key="hill-giant-strength-check",
    )
    strength_save = tools.roll_save(
        "pc1",
        "str",
        difficulty_tier="medium",
        idempotency_key="hill-giant-strength-save",
    )
    attack = tools.perform_action(
        "pc1",
        "srd.longsword_attack",
        ["goblin1"],
        idempotency_key="hill-giant-strength-longsword",
    )

    assert potion["success"] is True
    assert character.inventory["srd.potion_of_hill_giant_strength"] == 0
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.use_potion_of_hill_giant_strength"
    assert effect["condition"] is None
    assert effect["passive_modifiers"] == {
        "ability_score_set": {"str": 21},
        "giant_strength_type": "hill",
    }
    assert effect["duration"] == {"until": "duration_1_hour"}
    assert effect["tick_on"] == "self_turn_start"
    assert strength_check["bonus"] == 5
    assert strength_check["roll"]["expression"] == "1d20+5"
    assert strength_save["bonus"] == 5
    assert strength_save["roll"]["expression"] == "1d20+5"

    attack_node = attack["node_results"]["automation[1]"]
    assert attack_node["base_attack_bonus"] == 4
    assert attack_node["passive_adjustment"] == 3
    assert attack_node["total"] == 17
    assert attack_node["passive_sources"][0]["modifier"] == "ability_score_set"
    assert attack_node["passive_sources"][0]["score"] == 21
    assert attack_node["passive_sources"][0]["amount"] == 3
    damage = next(change for change in attack["state_changes"] if change["type"] == "damage")
    assert damage["amount"] == 9
    assert damage["applied"] == 9
    assert damage["passive_damage_bonus"] == 3
    assert damage["passive_sources"][0]["modifier"] == "ability_score_set"
    assert damage["passive_sources"][0]["score"] == 21
    assert damage["passive_sources"][0]["amount"] == 3

    for _ in range(599):
        lifecycle = tick_effects(state, trigger="self_turn_start", actor_id="pc1")
        assert lifecycle.expired == []
    final_lifecycle = tick_effects(state, trigger="self_turn_start", actor_id="pc1")
    assert final_lifecycle.expired[0]["source_action_id"] == (
        "srd.use_potion_of_hill_giant_strength"
    )
    assert state.encounter.combatants["pc1"].status_effects == []


def test_potion_of_giant_strength_does_not_lower_equal_or_higher_strength(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.abilities["str"] = 22
    character.inventory["srd.potion_of_hill_giant_strength"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([10]),
    )

    potion = tools.use_item(
        "pc1",
        "srd.potion_of_hill_giant_strength",
        ["pc1"],
        idempotency_key="use-hill-giant-strength-no-effect",
    )
    strength_check = tools.roll_check(
        "pc1",
        "str",
        difficulty_tier="medium",
        idempotency_key="hill-giant-strength-no-lower-check",
    )

    assert potion["success"] is True
    assert character.inventory["srd.potion_of_hill_giant_strength"] == 0
    assert state.encounter.combatants["pc1"].status_effects[-1]["passive_modifiers"] == {
        "ability_score_set": {"str": 21},
        "giant_strength_type": "hill",
    }
    assert strength_check["bonus"] == 6
    assert strength_check["roll"]["expression"] == "1d20+6"


def test_potion_of_animal_friendship_casts_level_three_spell_at_dc_13(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.inventory["srd.potion_of_animal_friendship"] = 1
    for index in range(1, 4):
        state.encounter.combatants[f"wolf{index}"] = Combatant(
            id=f"wolf{index}",
            entity_id=f"wolf{index}",
            name=f"Wolf {index}",
            side="monsters",
            hp_current=11,
            hp_max=11,
            armor_class=13,
            creature_type="beast",
            position_node_id="cover",
            abilities={"wis": 10},
        )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1, 20, 1]),
    )

    result = tools.use_item(
        "pc1",
        "srd.potion_of_animal_friendship",
        ["wolf1", "wolf2", "wolf3"],
        idempotency_key="use-animal-friendship-potion",
    )

    assert result["success"] is True
    assert character.inventory["srd.potion_of_animal_friendship"] == 0
    assert [roll["expression"] for roll in result["dice_rolls"]] == [
        "1d20+0",
        "1d20+0",
        "1d20+0",
    ]
    save = result["node_results"]["automation[1]"]
    assert save["dc"] == 13
    assert save["dc_source"] == "dc_ref:srd.potion_of_animal_friendship.wis_save"
    assert [
        change["target_id"]
        for change in result["state_changes"]
        if change["type"] == "condition" and change["condition"] == "charmed"
    ] == ["wolf1", "wolf3"]
    assert state.encounter.combatants["wolf2"].status_effects == []
    effect = state.encounter.combatants["wolf1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.use_potion_of_animal_friendship"
    assert effect["applied_by"] == "pc1"
    assert effect["condition"] == "charmed"
    assert effect["duration"] == {
        "until": "duration_24_hours_or_harmed",
        "break_on_damage": True,
        "break_on_damage_by": "applied_by_or_allies",
    }
    assert effect["tick_on"] == "duration_or_damage"


def test_potion_of_animal_friendship_requires_beast_before_cost(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].inventory["srd.potion_of_animal_friendship"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="target must be beast"):
        tools.use_item(
            "pc1",
            "srd.potion_of_animal_friendship",
            ["goblin1"],
            idempotency_key="animal-friendship-non-beast",
        )

    assert state.characters["pc1"].inventory["srd.potion_of_animal_friendship"] == 1
    assert state.encounter.action_budgets == {}


def test_potion_of_animal_friendship_ends_only_on_applier_or_ally_damage(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].inventory["srd.potion_of_animal_friendship"] = 1
    state.encounter.combatants["wolf1"] = Combatant(
        id="wolf1",
        entity_id="wolf1",
        name="Wolf One",
        side="neutral",
        hp_current=20,
        hp_max=20,
        armor_class=13,
        creature_type="beast",
        position_node_id="cover",
        abilities={"wis": 10},
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1]),
    )
    potion = tools.use_item(
        "pc1",
        "srd.potion_of_animal_friendship",
        ["wolf1"],
        idempotency_key="animal-friendship-break-source",
    )

    enemy_damage = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        _damage_action(1, damage_type="slashing"),
        actor_id="goblin1",
        targets=["wolf1"],
        idempotency_key="enemy-damages-charmed-beast",
    )

    assert potion["success"] is True
    assert any(
        effect.get("condition") == "charmed"
        for effect in state.encounter.combatants["wolf1"].status_effects
    )
    assert not [
        change for change in enemy_damage.state_changes if change.get("type") == "effect_expired"
    ]
    ally_damage = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        _damage_action(1, damage_type="slashing"),
        actor_id="pc2",
        targets=["wolf1"],
        idempotency_key="ally-damages-charmed-beast",
    )
    expiry = next(
        change for change in ally_damage.state_changes if change["type"] == "effect_expired"
    )
    assert expiry["trigger"] == "damage"
    assert expiry["removed"][0]["source_action_id"] == "srd.use_potion_of_animal_friendship"
    assert state.encounter.combatants["wolf1"].status_effects == []


def test_oil_of_sharpness_makes_selected_weapon_plus_three(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.inventory["srd.oil_of_sharpness"] = 1
    character.actions.append("srd.longsword_attack")
    state.encounter.combatants["goblin1"].hp_current = 20
    state.encounter.combatants["goblin1"].hp_max = 20
    state.encounter.combatants["goblin1"].armor_class = 12
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([5, 4]),
    )

    oil = tools.use_item(
        "pc1",
        "srd.oil_of_sharpness",
        ["pc1"],
        params={"oil_of_sharpness_action_id": "srd.longsword_attack"},
        idempotency_key="apply-oil-of-sharpness",
    )
    attack = tools.perform_action(
        "pc1",
        "srd.longsword_attack",
        ["goblin1"],
        idempotency_key="oil-of-sharpness-longsword-attack",
    )

    assert oil["success"] is True
    assert character.inventory["srd.oil_of_sharpness"] == 0
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.apply_oil_of_sharpness"
    assert effect["passive_modifiers"] == {
        "weapon_enhancement_bonus": 3,
        "weapon_bonus_action_id": "srd.longsword_attack",
        "coated_weapon_is_magical": True,
        "oil_of_sharpness": True,
    }
    assert effect["duration"] == {"until": "oil_sharpness_replaced_or_weapon_lost"}
    assert effect["tick_on"] == "weapon_attack"

    attack_node = attack["node_results"]["automation[1]"]
    assert attack_node["base_total"] == 9
    assert attack_node["passive_adjustment"] == 3
    assert attack_node["total"] == 12
    assert attack_node["hit"] is True
    assert attack_node["passive_sources"][0]["modifier"] == "weapon_enhancement_bonus"
    assert attack_node["passive_sources"][0]["selected_action_id"] == "srd.longsword_attack"
    damage = next(change for change in attack["state_changes"] if change["type"] == "damage")
    assert damage["amount"] == 9
    assert damage["applied"] == 9
    assert damage["passive_damage_bonus"] == 3
    assert damage["passive_sources"][0]["modifier"] == "weapon_enhancement_bonus"
    assert damage["passive_sources"][0]["selected_action_id"] == "srd.longsword_attack"


def test_oil_of_sharpness_requires_supported_weapon_before_cost(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.inventory["srd.oil_of_sharpness"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="oil_of_sharpness_action_id"):
        tools.use_item(
            "pc1",
            "srd.oil_of_sharpness",
            ["pc1"],
            params={},
            idempotency_key="oil-sharpness-missing-weapon",
        )
    with pytest.raises(AutomationError, match="Oil of Sharpness requires"):
        tools.use_item(
            "pc1",
            "srd.oil_of_sharpness",
            ["pc1"],
            params={"oil_of_sharpness_action_id": "srd.shortbow_attack"},
            idempotency_key="oil-sharpness-invalid-weapon",
        )

    assert character.inventory["srd.oil_of_sharpness"] == 1
    assert state.encounter.action_budgets == {}
    assert state.encounter.combatants["pc1"].status_effects == []


def test_oil_of_etherealness_records_etherealness_world_effect(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.inventory["srd.oil_of_etherealness"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.use_item(
        "pc1",
        "srd.oil_of_etherealness",
        ["pc1"],
        idempotency_key="apply-oil-of-etherealness",
    )

    assert result["success"] is True
    assert character.inventory["srd.oil_of_etherealness"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "srd.oil_of_etherealness"
    assert cost_change["amount"] == 1
    assert cost_change["param"] == "oil_of_etherealness_vials"
    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.apply_oil_of_etherealness"
    assert effect["effect_type"] == "etherealness"
    assert effect["concentration"] is False
    assert effect["scope"] == {"target": "explicit", "target_ids": ["pc1"], "target_id": "pc1"}
    assert effect["duration"] == {"until": "duration_1_hour"}
    assert effect["metadata"] == {
        "spell_definition_id": "srd.spell.etherealness",
        "equipment_worn_and_carried_included": True,
        "application_time_minutes": 10,
        "concentration": False,
    }


def test_oil_of_etherealness_requires_extra_vials_for_larger_targets_before_cost(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.inventory["srd.oil_of_etherealness"] = 2
    state.encounter.combatants["pc1"].size = "huge"
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="srd.oil_of_etherealness is insufficient"):
        tools.use_item(
            "pc1",
            "srd.oil_of_etherealness",
            ["pc1"],
            idempotency_key="oil-etherealness-insufficient-huge",
        )

    assert character.inventory["srd.oil_of_etherealness"] == 2
    assert state.world.active_effects == []

    character.inventory["srd.oil_of_etherealness"] = 3
    result = tools.use_item(
        "pc1",
        "srd.oil_of_etherealness",
        ["pc1"],
        idempotency_key="oil-etherealness-huge",
    )

    assert result["success"] is True
    assert character.inventory["srd.oil_of_etherealness"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["amount"] == 3
    assert cost_change["param"] == "oil_of_etherealness_vials"


def test_oil_of_slipperiness_applies_freedom_of_movement_effect(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.inventory["srd.oil_of_slipperiness"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.use_item(
        "pc1",
        "srd.oil_of_slipperiness",
        ["pc1"],
        idempotency_key="apply-oil-of-slipperiness",
    )

    assert result["success"] is True
    assert character.inventory["srd.oil_of_slipperiness"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "srd.oil_of_slipperiness"
    assert cost_change["amount"] == 1
    assert cost_change["param"] == "oil_of_slipperiness_vials"
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.apply_oil_of_slipperiness"
    assert effect["passive_modifiers"] == {
        "freedom_of_movement": True,
        "difficult_terrain_unaffected": True,
        "magical_speed_reduction_immunity": True,
        "magical_paralyzed_restrained_immunity": True,
        "swim_speed_equals_speed": True,
        "nonmagical_restraints_escape_movement_cost_ft": 5,
    }
    assert effect["duration"] == {"until": "duration_8_hours"}
    assert effect["tick_on"] == "self_turn_start"
    assert swim_speed_from_effects(30, state.encounter.combatants["pc1"].status_effects) == 30


def test_oil_of_slipperiness_larger_target_vial_cost_is_checked_before_effect(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.inventory["srd.oil_of_slipperiness"] = 1
    state.encounter.combatants["pc1"].size = "large"
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="srd.oil_of_slipperiness is insufficient"):
        tools.use_item(
            "pc1",
            "srd.oil_of_slipperiness",
            ["pc1"],
            idempotency_key="oil-slipperiness-insufficient-large",
        )

    assert character.inventory["srd.oil_of_slipperiness"] == 1
    assert state.encounter.combatants["pc1"].status_effects == []


def test_oil_of_slipperiness_poured_on_ground_records_grease_area(
    make_state,
) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.inventory["srd.oil_of_slipperiness"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.use_item(
        "pc1",
        "srd.oil_of_slipperiness",
        [],
        action_id="srd.pour_oil_of_slipperiness_on_ground",
        idempotency_key="pour-oil-of-slipperiness-ground",
    )

    assert result["success"] is True
    assert character.inventory["srd.oil_of_slipperiness"] == 0
    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.pour_oil_of_slipperiness_on_ground"
    assert effect["effect_type"] == "grease_area"
    assert effect["concentration"] is False
    assert effect["scope"] == {"target": "ground_area", "shape": "square", "size_ft": 10}
    assert effect["duration"] == {"until": "duration_8_hours"}
    assert effect["metadata"] == {
        "spell_definition_id": "srd.spell.grease",
        "duplicates_spell_effect": True,
        "concentration": False,
    }


def test_boots_of_elvenkind_grant_silent_steps_and_stealth_advantage(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.inventory["srd.boots_of_elvenkind"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    boots = tools.use_item(
        "pc1",
        "srd.boots_of_elvenkind",
        idempotency_key="wear-boots-of-elvenkind",
    )
    stealth = tools.roll_check(
        "pc1",
        "dex",
        skill="Stealth",
        difficulty_tier="medium",
        idempotency_key="boots-stealth-check",
    )
    perception = tools.roll_check(
        "pc1",
        "dex",
        skill="Perception",
        difficulty_tier="medium",
        idempotency_key="boots-perception-check",
    )

    assert boots["success"] is True
    assert character.inventory["srd.boots_of_elvenkind"] == 1
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.wear_boots_of_elvenkind"
    assert effect["passive_modifiers"] == {
        "silent_steps": True,
        "ability_check_advantage_skills": [{"ability": "dex", "skill": "stealth"}],
    }
    assert effect["duration"] == {"until": "while_wearing_boots_of_elvenkind"}
    assert stealth["roll"]["advantage"] == "advantage"
    assert stealth["status_sources"][0]["modifier"] == "ability_check_advantage_skills"
    assert stealth["status_sources"][0]["source_action_id"] == "srd.wear_boots_of_elvenkind"
    assert perception["roll"]["advantage"] is None
    assert perception["status_sources"] == []


def test_boots_of_elvenkind_item_requirement_accepts_equipment_and_rejects_missing(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="actor does not have item srd.boots_of_elvenkind"):
        tools.use_item(
            "pc1",
            "srd.boots_of_elvenkind",
            idempotency_key="missing-boots-of-elvenkind",
        )

    assert state.encounter.combatants["pc1"].status_effects == []

    state.characters["pc1"].equipment.append("srd.boots_of_elvenkind")
    result = tools.use_item(
        "pc1",
        "srd.boots_of_elvenkind",
        idempotency_key="equipped-boots-of-elvenkind",
    )

    assert result["success"] is True
    assert state.encounter.combatants["pc1"].status_effects[-1]["source_action_id"] == (
        "srd.wear_boots_of_elvenkind"
    )


def test_robe_of_eyes_grants_sight_perception_and_special_senses(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.inventory["srd.robe_of_eyes"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    robe = tools.use_item(
        "pc1",
        "srd.robe_of_eyes",
        ["pc1"],
        action_id="srd.wear_robe_of_eyes",
        idempotency_key="wear-robe-of-eyes",
    )
    sight_perception = tools.roll_check(
        "pc1",
        "wis",
        skill="Perception",
        difficulty_tier="medium",
        relies_on_sight=True,
        idempotency_key="robe-sight-perception",
    )
    hearing_perception = tools.roll_check(
        "pc1",
        "wis",
        skill="Perception",
        difficulty_tier="medium",
        idempotency_key="robe-hearing-perception",
    )

    assert robe["success"] is True
    assert character.inventory["srd.robe_of_eyes"] == 1
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.wear_robe_of_eyes"
    assert effect["passive_modifiers"] == {
        "ability_check_advantage_skills": [
            {"ability": "wis", "skill": "perception", "requires_context": "sight"}
        ],
        "darkvision_ft": 120,
        "truesight_ft": 120,
        "robe_of_eyes_drawback_light": True,
        "robe_of_eyes_drawback_daylight": True,
    }
    assert effect["duration"] == {"until": "while_wearing_robe_of_eyes"}
    assert sight_perception["roll"]["advantage"] == "advantage"
    assert sight_perception["status_sources"][0]["source_action_id"] == "srd.wear_robe_of_eyes"
    assert sight_perception["status_sources"][0]["contexts"] == ["sight"]
    assert hearing_perception["roll"]["advantage"] is None
    assert hearing_perception["status_sources"] == []
    assert darkvision_range_from_effects(state.encounter.combatants["pc1"].status_effects) == 120
    assert truesight_range_from_effects(state.encounter.combatants["pc1"].status_effects) == 120


def test_robe_of_eyes_light_and_daylight_drawbacks_apply_blinded_with_repeat_save(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].inventory["srd.robe_of_eyes"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    light = tools.use_item(
        "pc1",
        "srd.robe_of_eyes",
        ["pc1"],
        action_id="srd.robe_of_eyes_light_drawback",
        idempotency_key="robe-light-drawback",
    )
    light_effect = state.encounter.combatants["pc1"].status_effects[-1]
    lifecycle = tick_effects(
        state,
        trigger="self_turn_end",
        actor_id="pc1",
        roll_service=_FixedSingleDieRollService([20]),
    )
    daylight = tools.use_item(
        "pc1",
        "srd.robe_of_eyes",
        ["pc1"],
        action_id="srd.robe_of_eyes_daylight_drawback",
        idempotency_key="robe-daylight-drawback",
    )
    daylight_effect = state.encounter.combatants["pc1"].status_effects[-1]

    assert light["success"] is True
    assert light_effect["condition"] == "blinded"
    assert light_effect["duration"]["repeat_save"] == {
        "ability": "con",
        "dc": 11,
        "dc_source": "dc_ref:srd.robe_of_eyes.light_con_save",
        "end_on_success": True,
    }
    assert lifecycle.expired[0]["condition"] == "blinded"
    assert lifecycle.expired[0]["repeat_save"]["dc"] == 11
    assert lifecycle.expired[0]["repeat_save"]["success"] is True
    assert daylight["success"] is True
    assert daylight_effect["condition"] == "blinded"
    assert daylight_effect["duration"]["repeat_save"] == {
        "ability": "con",
        "dc": 15,
        "dc_source": "dc_ref:srd.robe_of_eyes.daylight_con_save",
        "end_on_success": True,
    }


def test_robe_of_the_archmagi_requires_sorcerer_warlock_or_wizard(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.inventory["srd.robe_of_the_archmagi"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="requires one of sorcerer, warlock, wizard"):
        tools.use_item(
            "pc1",
            "srd.robe_of_the_archmagi",
            ["pc1"],
            action_id="srd.wear_robe_of_the_archmagi",
            idempotency_key="wear-archmagi-robe-fighter",
        )

    character.class_levels = {"wizard": 1}
    result = tools.use_item(
        "pc1",
        "srd.robe_of_the_archmagi",
        ["pc1"],
        action_id="srd.wear_robe_of_the_archmagi",
        idempotency_key="wear-archmagi-robe-wizard",
    )

    assert result["success"] is True
    assert character.inventory["srd.robe_of_the_archmagi"] == 1
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.wear_robe_of_the_archmagi"
    assert effect["duration"] == {"until": "while_wearing_robe_of_the_archmagi"}
    assert effect["passive_modifiers"] == {
        "armor_class_formula": "15+dex_modifier",
        "armor_class_requires_unarmored": True,
        "saving_throw_advantage_contexts": ["spell", "magical_effect"],
        "spell_save_dc_bonus": {
            "sorcerer": 2,
            "warlock": 2,
            "wizard": 2,
        },
        "spell_attack_bonus": {
            "sorcerer": 2,
            "warlock": 2,
            "wizard": 2,
        },
    }


def test_robe_of_the_archmagi_applies_srd_benefits_without_extra_rules(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"wizard": 5}
    character.abilities["dex"] = 14
    character.abilities["int"] = 16
    character.equipment = []
    character.armor_class = 10
    character.inventory["srd.robe_of_the_archmagi"] = 1
    state.encounter.combatants["pc1"].armor_class = 10
    state.encounter.combatants["goblin1"].armor_class = 12
    state.encounter.combatants["goblin1"].abilities = {"wis": 10}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    robe = tools.use_item(
        "pc1",
        "srd.robe_of_the_archmagi",
        ["pc1"],
        action_id="srd.wear_robe_of_the_archmagi",
        idempotency_key="wear-archmagi-robe",
    )
    unarmored_attack = AutomationExecutor(
        state,
        _FixedSingleDieRollService([13]),
        AuditLog(),
    ).execute(_attack_action(attack_bonus=0), actor_id="goblin1", targets=["pc1"])
    character.equipment = ["srd.leather_armor"]
    character.armor_class = 11
    state.encounter.combatants["pc1"].armor_class = 11
    armored_attack = AutomationExecutor(
        state,
        _FixedSingleDieRollService([1]),
        AuditLog(),
    ).execute(_attack_action(attack_bonus=0), actor_id="goblin1", targets=["pc1"])

    spell_save_action = ActionDefinition(
        id="test.archmagi.spell_save",
        name="Archmagi Spell Save",
        localization={"en": "Archmagi Spell Save", "zh": "大法师法袍法术豁免", "aliases": []},
        source="test",
        rules_version="test",
        action_type="spell",
        action_economy="none",
        range={"normal_ft": 30},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {
                "type": "saving_throw",
                "ability": "wis",
                "difficulty_tier": "medium",
                "contexts": ["spell"],
            },
        ],
    )
    spell_save = AutomationExecutor(
        state,
        _FixedSingleDieRollService([10]),
        AuditLog(),
    ).execute(spell_save_action, actor_id="goblin1", targets=["pc1"])

    magical_effect_save_action = ActionDefinition(
        id="test.archmagi.magical_effect_save",
        name="Archmagi Magical Effect Save",
        localization={
            "en": "Archmagi Magical Effect Save",
            "zh": "大法师法袍魔法效果豁免",
            "aliases": [],
        },
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={"normal_ft": 30},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {
                "type": "saving_throw",
                "ability": "wis",
                "difficulty_tier": "medium",
                "contexts": ["magical_effect"],
            },
        ],
    )
    magical_effect_save = AutomationExecutor(
        state,
        _FixedSingleDieRollService([10]),
        AuditLog(),
    ).execute(magical_effect_save_action, actor_id="goblin1", targets=["pc1"])

    ordinary_save_action = ActionDefinition(
        id="test.archmagi.ordinary_save",
        name="Archmagi Ordinary Save",
        localization={
            "en": "Archmagi Ordinary Save",
            "zh": "大法师法袍普通豁免",
            "aliases": [],
        },
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={"normal_ft": 30},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "saving_throw", "ability": "wis", "difficulty_tier": "medium"},
        ],
    )
    ordinary_save = AutomationExecutor(
        state,
        _FixedSingleDieRollService([10]),
        AuditLog(),
    ).execute(ordinary_save_action, actor_id="goblin1", targets=["pc1"])

    spell_dc_action = ActionDefinition(
        id="test.archmagi.spell_dc",
        name="Archmagi Spell DC",
        localization={"en": "Archmagi Spell DC", "zh": "大法师法袍法术 DC", "aliases": []},
        source="test",
        rules_version="test",
        action_type="spell",
        action_economy="none",
        range={"normal_ft": 30},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "saving_throw", "ability": "wis", "dc_from": {"spell_save_dc": "wizard"}},
        ],
    )
    spell_dc = AutomationExecutor(
        state,
        _FixedSingleDieRollService([10]),
        AuditLog(),
    ).execute(spell_dc_action, actor_id="pc1", targets=["goblin1"])

    spell_attack_action = ActionDefinition(
        id="test.archmagi.spell_attack",
        name="Archmagi Spell Attack",
        localization={
            "en": "Archmagi Spell Attack",
            "zh": "大法师法袍法术攻击",
            "aliases": [],
        },
        source="test",
        rules_version="test",
        action_type="spell",
        action_economy="none",
        range={"normal_ft": 30},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "attack_roll", "attack_bonus": 5},
        ],
    )
    spell_attack = AutomationExecutor(
        state,
        _FixedSingleDieRollService([5]),
        AuditLog(),
    ).execute(spell_attack_action, actor_id="pc1", targets=["goblin1"])

    assert robe["success"] is True
    unarmored_attack_node = unarmored_attack.node_results["automation[1]"]
    assert unarmored_attack_node["base_ac"] == 10
    assert unarmored_attack_node["ac"] == 17
    assert unarmored_attack_node["armor_class_sources"][0] == {
        "effect_id": state.encounter.combatants["pc1"].status_effects[-1]["effect_id"],
        "source_action_id": "srd.wear_robe_of_the_archmagi",
        "modifier": "armor_class_formula",
        "formula": "15+dex_modifier",
        "value": 17,
    }
    armored_attack_node = armored_attack.node_results["automation[1]"]
    assert armored_attack_node["base_ac"] == 11
    assert armored_attack_node["ac"] == 11
    assert armored_attack_node["armor_class_sources"] == []

    spell_save_node = spell_save.node_results["automation[1]"]
    assert spell_save.dice_rolls[0]["advantage"] == "advantage"
    assert spell_save_node["status_sources"][0]["modifier"] == ("saving_throw_advantage_contexts")
    assert spell_save_node["status_sources"][0]["contexts"] == ["spell"]
    magical_save_node = magical_effect_save.node_results["automation[1]"]
    assert magical_effect_save.dice_rolls[0]["advantage"] == "advantage"
    assert magical_save_node["status_sources"][0]["contexts"] == ["magical_effect"]
    assert ordinary_save.dice_rolls[0]["advantage"] is None
    assert ordinary_save.node_results["automation[1]"]["status_sources"] == []

    spell_dc_node = spell_dc.node_results["automation[1]"]
    assert spell_dc_node["dc"] == 15
    assert spell_dc_node["dc_source"] == "spell_save_dc:wizard+2"
    spell_attack_node = spell_attack.node_results["automation[1]"]
    assert spell_attack.dice_rolls[0]["expression"] == "1d20+7"
    assert spell_attack_node["base_attack_bonus"] == 7
    assert spell_attack_node["attack_bonus_sources"][-1] == {
        "kind": "passive",
        "effect_id": state.encounter.combatants["pc1"].status_effects[-1]["effect_id"],
        "source_action_id": "srd.wear_robe_of_the_archmagi",
        "modifier": "spell_attack_bonus",
        "classes": ["wizard"],
        "amount": 2,
    }
    assert spell_attack_node["hit"] is True


def test_robe_of_useful_items_initializes_fixed_and_random_patches(
    make_state,
) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.inventory["srd.robe_of_useful_items"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([4, 1, 60, 84, 97]),
    )

    result = tools.use_item(
        "pc1",
        "srd.robe_of_useful_items",
        ["pc1"],
        action_id="srd.initialize_robe_of_useful_items_patches",
        idempotency_key="initialize-useful-robe",
    )

    assert result["success"] is True
    assert [roll["expression"] for roll in result["dice_rolls"]] == [
        "4d4",
        "1d100",
        "1d100",
        "1d100",
        "1d100",
    ]
    assert character.resources["srd.robe_of_useful_items.initialized"] == 1
    assert character.resources["srd.robe_of_useful_items.patch.dagger"] == 2
    assert character.resources["srd.robe_of_useful_items.patch.rope_coiled"] == 2
    assert character.resources["srd.robe_of_useful_items.patch.bag_of_100_gp"] == 1
    assert character.resources["srd.robe_of_useful_items.patch.potions_of_healing"] == 1
    assert character.resources["srd.robe_of_useful_items.patch.mastiffs"] == 1
    assert character.resources["srd.robe_of_useful_items.patch.portable_ram"] == 1
    init_change = next(
        change
        for change in result["state_changes"]
        if change["type"] == "robe_of_useful_items_initialized"
    )
    assert init_change["extra_patch_roll"] == 4
    assert init_change["random_rolls"] == [
        {"roll": 1, "patch": "bag_of_100_gp"},
        {"roll": 60, "patch": "potions_of_healing"},
        {"roll": 84, "patch": "mastiffs"},
        {"roll": 97, "patch": "portable_ram"},
    ]

    with pytest.raises(AutomationError, match="already initialized"):
        tools.use_item(
            "pc1",
            "srd.robe_of_useful_items",
            ["pc1"],
            action_id="srd.initialize_robe_of_useful_items_patches",
            idempotency_key="initialize-useful-robe-again",
        )


def test_robe_of_useful_items_detaches_item_gold_and_world_effect_patches(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.inventory["srd.robe_of_useful_items"] = 1
    character.resources["srd.robe_of_useful_items.initialized"] = 1
    character.resources["srd.robe_of_useful_items.patch.dagger"] = 1
    character.resources["srd.robe_of_useful_items.patch.bag_of_100_gp"] = 1
    character.resources["srd.robe_of_useful_items.patch.mastiffs"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    dagger = tools.use_item(
        "pc1",
        "srd.robe_of_useful_items",
        ["pc1"],
        action_id="srd.detach_robe_of_useful_items_patch",
        params={"robe_of_useful_items_patch": "dagger"},
        idempotency_key="useful-robe-dagger",
    )
    tools.economy.reset_turn_start("pc1", 30)
    gold = tools.use_item(
        "pc1",
        "srd.robe_of_useful_items",
        ["pc1"],
        action_id="srd.detach_robe_of_useful_items_patch",
        params={"robe_of_useful_items_patch": "bag_of_100_gp"},
        idempotency_key="useful-robe-gold",
    )
    tools.economy.reset_turn_start("pc1", 30)
    mastiffs = tools.use_item(
        "pc1",
        "srd.robe_of_useful_items",
        ["pc1"],
        action_id="srd.detach_robe_of_useful_items_patch",
        params={"robe_of_useful_items_patch": "mastiffs"},
        idempotency_key="useful-robe-mastiffs",
    )

    assert dagger["success"] is True
    assert character.inventory["srd.dagger"] == 1
    dagger_change = next(
        change
        for change in dagger["state_changes"]
        if change["type"] == "robe_of_useful_items_patch"
    )
    assert dagger_change["generated"] == [
        {
            "type": "item",
            "actor_id": "pc1",
            "patch": "dagger",
            "item_id": "srd.dagger",
            "quantity": 1,
            "before": 0,
            "after": 1,
        }
    ]
    assert character.resources["srd.robe_of_useful_items.patch.dagger"] == 0

    assert gold["success"] is True
    assert character.gold == 100
    gold_change = next(
        change for change in gold["state_changes"] if change["type"] == "robe_of_useful_items_patch"
    )
    assert gold_change["generated"][0]["type"] == "gold"
    assert gold_change["generated"][0]["amount"] == 100

    assert mastiffs["success"] is True
    assert state.world.active_effects[-1]["effect_type"] == "robe_of_useful_items_creature"
    assert state.world.active_effects[-1]["metadata"] == {
        "creature": "mastiff",
        "count": 2,
        "patch": "mastiffs",
    }
    assert character.inventory["srd.robe_of_useful_items"] == 0
    assert character.resources["srd.robe_of_useful_items.initialized"] == 0
    assert any(
        change["type"] == "robe_of_useful_items_depleted" for change in mastiffs["state_changes"]
    )


def test_robe_of_useful_items_rejects_unavailable_patch_before_action_spend(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.inventory["srd.robe_of_useful_items"] = 1
    character.resources["srd.robe_of_useful_items.initialized"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="patch dagger is unavailable"):
        tools.use_item(
            "pc1",
            "srd.robe_of_useful_items",
            ["pc1"],
            action_id="srd.detach_robe_of_useful_items_patch",
            params={"robe_of_useful_items_patch": "dagger"},
            idempotency_key="useful-robe-missing-dagger",
        )

    assert state.encounter.action_budgets == {}
    assert character.inventory["srd.robe_of_useful_items"] == 1


def test_rod_of_absorption_initializes_newly_found_energy(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.inventory["srd.rod_of_absorption"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([7]),
    )

    result = tools.use_item(
        "pc1",
        "srd.rod_of_absorption",
        ["pc1"],
        action_id="srd.initialize_rod_of_absorption_energy",
        idempotency_key="initialize-rod-absorption",
    )

    assert result["success"] is True
    assert result["dice_rolls"][0]["expression"] == "1d10"
    assert character.resources["srd.rod_of_absorption.stored_levels"] == 7
    assert character.resources["srd.rod_of_absorption.lifetime_absorbed_levels"] == 7
    assert character.resources["srd.rod_of_absorption.initialized"] == 1
    init_change = next(
        change
        for change in result["state_changes"]
        if change["type"] == "rod_of_absorption_initialized"
    )
    assert init_change["stored_levels_after"] == 7

    with pytest.raises(AutomationError, match="already initialized"):
        tools.use_item(
            "pc1",
            "srd.rod_of_absorption",
            ["pc1"],
            action_id="srd.initialize_rod_of_absorption_energy",
            idempotency_key="initialize-rod-absorption-again",
        )


def test_rod_of_absorption_absorbs_targeted_non_area_spell_with_reaction(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.inventory["srd.rod_of_absorption"] = 1
    character.resources["srd.rod_of_absorption.initialized"] = 1
    character.resources["srd.rod_of_absorption.stored_levels"] = 6
    character.resources["srd.rod_of_absorption.lifetime_absorbed_levels"] = 6
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.use_item(
        "pc1",
        "srd.rod_of_absorption",
        ["pc1"],
        action_id="srd.rod_of_absorption_absorb_spell",
        params={
            "absorbed_spell_level": 3,
            "targeting_only_you": True,
            "creates_area_of_effect": False,
        },
        idempotency_key="rod-absorb-spell",
    )

    assert result["success"] is True
    assert state.encounter.action_budgets["pc1"]["reaction"] == 0
    assert character.resources["srd.rod_of_absorption.stored_levels"] == 9
    assert character.resources["srd.rod_of_absorption.lifetime_absorbed_levels"] == 9
    absorb_change = next(
        change
        for change in result["state_changes"]
        if change["type"] == "rod_of_absorption_spell_absorbed"
    )
    assert absorb_change["spell_effect_canceled"] is True
    assert absorb_change["caster_resources_wasted"] is True
    assert absorb_change["absorbed_spell_level"] == 3


def test_rod_of_absorption_rejects_invalid_absorption_before_reaction_spend(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.inventory["srd.rod_of_absorption"] = 1
    character.resources["srd.rod_of_absorption.initialized"] = 1
    character.resources["srd.rod_of_absorption.stored_levels"] = 1
    character.resources["srd.rod_of_absorption.lifetime_absorbed_levels"] = 49
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="cannot absorb an area-of-effect spell"):
        tools.use_item(
            "pc1",
            "srd.rod_of_absorption",
            ["pc1"],
            action_id="srd.rod_of_absorption_absorb_spell",
            params={
                "absorbed_spell_level": 1,
                "targeting_only_you": True,
                "creates_area_of_effect": True,
            },
            idempotency_key="rod-absorb-area",
        )
    with pytest.raises(AutomationError, match="cannot store that spell level"):
        tools.use_item(
            "pc1",
            "srd.rod_of_absorption",
            ["pc1"],
            action_id="srd.rod_of_absorption_absorb_spell",
            params={
                "absorbed_spell_level": 2,
                "targeting_only_you": True,
                "creates_area_of_effect": False,
            },
            idempotency_key="rod-absorb-over-cap",
        )

    assert state.encounter.action_budgets == {}
    assert character.resources["srd.rod_of_absorption.stored_levels"] == 1
    assert character.resources["srd.rod_of_absorption.lifetime_absorbed_levels"] == 49


def test_rod_of_absorption_stored_energy_replaces_spell_slot(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.inventory["srd.rod_of_absorption"] = 1
    character.spell_slots = {"1": 0, "3": 0}
    character.spell_slots_max = {"1": 4, "3": 2}
    character.resources["srd.rod_of_absorption.initialized"] = 1
    character.resources["srd.rod_of_absorption.stored_levels"] = 5
    character.resources["srd.rod_of_absorption.lifetime_absorbed_levels"] = 12
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell(
        "pc1",
        "srd.cure_wounds",
        ["pc2"],
        3,
        use_rod_of_absorption=True,
        idempotency_key="rod-cast-cure-wounds",
    )

    assert result["success"] is True
    assert character.spell_slots == {"1": 0, "3": 0}
    assert character.resources["srd.rod_of_absorption.stored_levels"] == 2
    cost_change = next(
        change
        for change in result["state_changes"]
        if change.get("resource") == "srd.rod_of_absorption.stored_levels"
    )
    assert cost_change["amount"] == 3
    assert cost_change["created_spell_slot_level"] == 3
    assert cost_change["spell_slot_expended"] is False


def test_rod_of_absorption_rejects_invalid_stored_energy_cast_and_depletes_nonmagical(
    make_state,
) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.inventory["srd.rod_of_absorption"] = 1
    character.spell_slots = {"1": 0, "3": 0}
    character.spell_slots_max = {"1": 4, "3": 2}
    character.resources["srd.rod_of_absorption.initialized"] = 1
    character.resources["srd.rod_of_absorption.stored_levels"] = 2
    character.resources["srd.rod_of_absorption.lifetime_absorbed_levels"] = 49
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="insufficient stored spell energy"):
        tools.cast_spell(
            "pc1",
            "srd.cure_wounds",
            ["pc2"],
            3,
            use_rod_of_absorption=True,
            idempotency_key="rod-cast-insufficient-energy",
        )

    assert state.encounter is not None
    assert state.encounter.action_budgets["pc1"]["action"] == 1
    character.resources["srd.rod_of_absorption.stored_levels"] = 3
    character.resources["srd.rod_of_absorption.lifetime_absorbed_levels"] = 50
    depleted = tools.cast_spell(
        "pc1",
        "srd.cure_wounds",
        ["pc2"],
        3,
        use_rod_of_absorption=True,
        idempotency_key="rod-cast-depletes",
    )

    assert character.resources["srd.rod_of_absorption.stored_levels"] == 0
    assert character.inventory["srd.rod_of_absorption"] == 0
    assert character.resources["srd.rod_of_absorption.initialized"] == 0
    assert any(
        change["type"] == "rod_of_absorption_depleted" for change in depleted["state_changes"]
    )


def test_rod_of_alertness_grants_perception_and_initiative_advantage(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.inventory["srd.rod_of_alertness"] = 1
    compendium = CompendiumLoader("rules_data").load()
    audit = AuditLog()
    tools = EngineTools(state, compendium, audit)

    result = tools.use_item(
        "pc1",
        "srd.rod_of_alertness",
        ["pc1"],
        action_id="srd.hold_rod_of_alertness",
        idempotency_key="hold-rod-alertness",
    )
    perception = tools.roll_check(
        "pc1",
        "wis",
        skill="Perception",
        difficulty_tier="medium",
        idempotency_key="rod-alertness-perception",
    )
    roll_initiative(state, audit)
    groups = {group["group_key"]: group for group in audit.events[-1].tool_result["groups"]}

    assert result["success"] is True
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.hold_rod_of_alertness"
    assert effect["passive_modifiers"]["ability_check_advantage_skills"] == [
        {"ability": "wis", "skill": "perception"}
    ]
    assert perception["status_advantage"] == "advantage"
    assert perception["status_sources"][0]["source_action_id"] == "srd.hold_rod_of_alertness"
    assert groups["combatant:pc1"]["initiative_advantage_sources"] == ["rod_of_alertness"]
    assert any(roll["advantage"] == "advantage" for roll in audit.events[-1].dice_rolls)


def test_rod_of_alertness_casts_listed_srd_spells_without_spell_slots(
    make_state,
) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.inventory["srd.rod_of_alertness"] = 1
    character.spell_slots["1"] = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.use_item(
        "pc1",
        "srd.rod_of_alertness",
        [],
        action_id="srd.rod_of_alertness_detect_magic",
        idempotency_key="rod-alertness-detect-magic",
    )

    assert result["success"] is True
    assert character.spell_slots["1"] == 0
    assert not any(change.get("resource") == "spell_slot_1" for change in result["state_changes"])
    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.rod_of_alertness_detect_magic"
    assert effect["effect_type"] == "detect_magic"
    assert effect["metadata"]["spell_definition_id"] == "srd.spell.detect_magic"
    assert effect["metadata"]["duplicates_spell_effect"] is True


def test_rod_of_alertness_protective_aura_once_until_next_dawn(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.inventory["srd.rod_of_alertness"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.use_item(
        "pc1",
        "srd.rod_of_alertness",
        ["pc2"],
        action_id="srd.rod_of_alertness_protective_aura",
        idempotency_key="rod-alertness-aura",
    )

    assert result["success"] is True
    assert character.resources["srd.rod_of_alertness.protective_aura_used_until_next_dawn"] == 1
    aura = state.world.active_effects[-1]
    assert aura["effect_type"] == "rod_of_alertness_protective_aura"
    assert aura["scope"]["bright_light_radius_ft"] == 60
    assert aura["scope"]["dim_light_additional_ft"] == 60
    assert aura["duration"] == {"until": "duration_10_minutes_or_magic_action_to_remove"}
    assert aura["metadata"]["reset_trigger"] == "next_dawn"
    pc2_effect = state.encounter.combatants["pc2"].status_effects[-1]
    assert pc2_effect["passive_modifiers"] == {
        "armor_class_bonus": 1,
        "saving_throw_bonus": 1,
        "sense_invisible_creature_locations_in_same_bright_light": True,
    }

    attack = AutomationExecutor(
        state,
        _FixedSingleDieRollService([14]),
        AuditLog(),
    ).execute(_attack_action(attack_bonus=0), actor_id="goblin1", targets=["pc2"])
    attack_node = attack.node_results["automation[1]"]
    assert attack_node["ac"] == 15
    assert attack_node["hit"] is False
    assert attack_node["armor_class_sources"][0]["source_action_id"] == (
        "srd.rod_of_alertness_protective_aura"
    )

    save_action = ActionDefinition(
        id="test.rod_alertness_save",
        name="Rod Alertness Save",
        localization={"en": "Rod Alertness Save", "zh": "警觉法杖豁免", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={"normal_ft": 5},
        target_policy={"min": 1, "max": 1, "harmful": False},
        automation=[{"type": "saving_throw", "ability": "dex", "difficulty_tier": "medium"}],
    )
    save = AutomationExecutor(
        state,
        _FixedSingleDieRollService([10]),
        AuditLog(),
    ).execute(save_action, actor_id="goblin1", targets=["pc2"])
    save_node = save.node_results["automation[0]"]
    assert save_node["passive_adjustment"] == 1
    assert save_node["passive_sources"][0]["modifier"] == "saving_throw_bonus"
    assert save_node["passive_sources"][0]["source_action_id"] == (
        "srd.rod_of_alertness_protective_aura"
    )

    direct_save = tools.roll_save(
        "pc2",
        "dex",
        difficulty_tier="medium",
        idempotency_key="rod-alertness-direct-save",
    )
    assert direct_save["passive_bonus"] == 1
    assert direct_save["passive_bonus_sources"][0]["source_action_id"] == (
        "srd.rod_of_alertness_protective_aura"
    )

    state.encounter.action_budgets["pc1"]["action"] = 1
    with pytest.raises(AutomationError, match="can't be used again until the next dawn"):
        tools.use_item(
            "pc1",
            "srd.rod_of_alertness",
            ["pc2"],
            action_id="srd.rod_of_alertness_protective_aura",
            idempotency_key="rod-alertness-aura-again",
        )
    assert state.encounter.action_budgets["pc1"]["action"] == 1


def test_ring_of_swimming_grants_fixed_swim_speed(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.inventory["srd.ring_of_swimming"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.use_item(
        "pc1",
        "srd.ring_of_swimming",
        idempotency_key="wear-ring-of-swimming",
    )

    assert result["success"] is True
    assert character.inventory["srd.ring_of_swimming"] == 1
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.wear_ring_of_swimming"
    assert effect["passive_modifiers"] == {"swim_speed_ft": 40}
    assert effect["duration"] == {"until": "while_wearing_ring_of_swimming"}
    assert swim_speed_from_effects(30, state.encounter.combatants["pc1"].status_effects) == 40


def test_ring_of_water_walking_casts_water_walk_on_self_only(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.inventory["srd.ring_of_water_walking"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.use_item(
        "pc1",
        "srd.ring_of_water_walking",
        ["pc1"],
        action_id="srd.ring_of_water_walking_water_walk",
        idempotency_key="ring-of-water-walking-self",
    )

    assert result["success"] is True
    assert character.inventory["srd.ring_of_water_walking"] == 1
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.ring_of_water_walking_water_walk"
    assert effect["passive_modifiers"] == {"walk_on_liquid_surface": True}
    assert effect["duration"] == {"until": "duration_1_hour"}
    assert effect["tick_on"] == "movement"
    assert can_walk_on_liquid_surface_from_effects(state.encounter.combatants["pc1"].status_effects)


def test_ring_of_water_walking_rejects_non_self_target_before_effect(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.inventory["srd.ring_of_water_walking"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="target must be self"):
        tools.use_item(
            "pc1",
            "srd.ring_of_water_walking",
            ["pc2"],
            action_id="srd.ring_of_water_walking_water_walk",
            idempotency_key="ring-of-water-walking-other-target",
        )

    assert character.inventory["srd.ring_of_water_walking"] == 1
    assert state.encounter.combatants["pc1"].status_effects == []
    assert state.encounter.combatants["pc2"].status_effects == []


def test_ring_of_xray_vision_repeated_use_can_cause_exhaustion_and_resets_on_long_rest(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.inventory["srd.ring_of_xray_vision"] = 1
    compendium = CompendiumLoader("rules_data").load()
    action = compendium.action("srd.use_ring_of_xray_vision")
    roll_service = _FixedSingleDieRollService([1])
    executor = AutomationExecutor(state, roll_service, AuditLog())

    first = executor.execute(
        action,
        actor_id="pc1",
        targets=["pc1"],
        idempotency_key="ring-xray-first",
    )
    executor.economy.reset_turn_start("pc1", 30)
    second = executor.execute(
        action,
        actor_id="pc1",
        targets=["pc1"],
        idempotency_key="ring-xray-second",
    )

    first_strain = first.node_results["automation[1]"]
    second_strain = second.node_results["automation[1]"]
    assert first_strain["had_prior_use"] is False
    assert first_strain["saving_throw"] is None
    assert second_strain["had_prior_use"] is True
    assert second_strain["saving_throw"]["dc"] == 15
    assert second_strain["saving_throw"]["dc_source"] == ("dc_ref:srd.ring_of_xray_vision.con_save")
    assert second_strain["saving_throw"]["success"] is False
    assert second_strain["condition"]["condition"] == "exhaustion"
    assert character.inventory["srd.ring_of_xray_vision"] == 1
    assert xray_vision_range_from_effects(state.encounter.combatants["pc1"].status_effects) == 30
    xray_effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert xray_effect["source_action_id"] == "srd.use_ring_of_xray_vision"
    assert xray_effect["duration"] == {"until": "duration_1_minute"}
    assert xray_effect["tick_on"] == "self_turn_start"
    assert xray_effect["passive_modifiers"]["xray_vision_penetration"] == {
        "stone_ft": 1,
        "common_metal_in": 1,
        "wood_or_dirt_ft": 3,
    }
    assert any(
        effect.get("passive_modifiers", {}).get("ring_of_xray_vision_used_before_long_rest") is True
        for effect in character.status_effects
    )
    assert character.status_effects[-2]["condition"] == "exhaustion"
    assert character.status_effects[-2]["level"] == 1

    tools = EngineTools(state, compendium, AuditLog())
    long_rest = tools.long_rest(["pc1"], idempotency_key="ring-xray-long-rest")

    removed = long_rest["results"]["pc1"]["removed_long_rest_effects"]
    assert removed[0]["passive_modifiers"] == {"ring_of_xray_vision_used_before_long_rest": True}
    assert not any(
        effect.get("passive_modifiers", {}).get("ring_of_xray_vision_used_before_long_rest") is True
        for effect in character.status_effects
    )
    assert not any(effect.get("condition") == "exhaustion" for effect in character.status_effects)


def test_ring_of_xray_vision_rejects_non_self_target_before_effect(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].inventory["srd.ring_of_xray_vision"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="target must be self"):
        tools.use_item(
            "pc1",
            "srd.ring_of_xray_vision",
            ["pc2"],
            action_id="srd.use_ring_of_xray_vision",
            idempotency_key="ring-xray-other-target",
        )

    assert state.characters["pc1"].status_effects == []
    assert state.encounter.combatants["pc1"].status_effects == []
    assert state.encounter.combatants["pc2"].status_effects == []


def test_potion_of_heroism_grants_timed_temp_hp_and_bless_without_concentration(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].inventory["srd.potion_of_heroism"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([10, 3, 4]),
    )

    potion = tools.use_item(
        "pc1",
        "srd.potion_of_heroism",
        ["pc1"],
        idempotency_key="use-heroism-potion",
    )
    attack = tools.perform_action(
        "pc1",
        "srd.shortsword_attack",
        ["goblin1"],
        idempotency_key="heroism-blessed-attack",
    )

    assert potion["success"] is True
    assert state.characters["pc1"].inventory["srd.potion_of_heroism"] == 0
    assert state.encounter.combatants["pc1"].temp_hp == 10
    assert state.encounter.combatants["pc1"].temp_hp_source_effect_id is not None
    effects = state.encounter.combatants["pc1"].status_effects
    temp_hp_effect = next(effect for effect in effects if effect["audit"].get("temp_hp_source"))
    bless_effect = next(
        effect
        for effect in effects
        if effect.get("passive_modifiers", {}).get("attack_roll_bonus_dice") == "1d4"
    )
    assert temp_hp_effect["source_action_id"] == "srd.use_potion_of_heroism"
    assert temp_hp_effect["duration"] == {"until": "duration_1_hour"}
    assert bless_effect["source_action_id"] == "srd.use_potion_of_heroism"
    assert bless_effect["passive_modifiers"] == {
        "attack_roll_bonus_dice": "1d4",
        "saving_throw_bonus_dice": "1d4",
    }
    assert bless_effect["concentration"] is False
    attack_node = attack["node_results"]["automation[1]"]
    assert any(roll["expression"] == "1d4" for roll in attack["dice_rolls"])
    assert attack_node["passive_sources"][0]["source_action_id"] == ("srd.use_potion_of_heroism")

    for _ in range(599):
        lifecycle = tick_effects(state, trigger="self_turn_start", actor_id="pc1")
        assert lifecycle.expired == []
    final_lifecycle = tick_effects(state, trigger="self_turn_start", actor_id="pc1")
    temp_hp_expiry = next(entry for entry in final_lifecycle.expired if "temp_hp_expired" in entry)
    assert temp_hp_expiry["source_action_id"] == "srd.use_potion_of_heroism"
    assert temp_hp_expiry["temp_hp_expired"] == {"before": 10, "after": 0}
    assert state.encounter.combatants["pc1"].temp_hp == 0
    assert state.encounter.combatants["pc1"].temp_hp_source_effect_id is None
    assert state.encounter.combatants["pc1"].status_effects == []


def test_timed_temp_hp_expiry_does_not_clear_newer_higher_temp_hp(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 2}
    character.feature_choices = {"warlock.eldritch_invocation.fiendish_vigor": "selected"}
    character.actions.extend(["srd.fiendish_vigor", "srd.fiendish_vigor_false_life"])
    character.inventory["srd.potion_of_heroism"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    tools.use_item(
        "pc1",
        "srd.potion_of_heroism",
        ["pc1"],
        idempotency_key="use-heroism-before-higher-temp-hp",
    )
    tools.perform_action(
        "pc1",
        "srd.fiendish_vigor_false_life",
        [],
        idempotency_key="higher-temp-hp",
    )

    assert state.encounter.combatants["pc1"].temp_hp == 12
    assert state.encounter.combatants["pc1"].temp_hp_source_effect_id is None
    for _ in range(600):
        final_lifecycle = tick_effects(state, trigger="self_turn_start", actor_id="pc1")
    assert any(
        entry["source_action_id"] == "srd.use_potion_of_heroism"
        for entry in final_lifecycle.expired
    )
    assert state.encounter.combatants["pc1"].temp_hp == 12


def test_potion_of_climbing_applies_climb_speed_and_strength_athletics_advantage(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].inventory["srd.potion_of_climbing"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    potion = tools.use_item(
        "pc1",
        "srd.potion_of_climbing",
        ["pc1"],
        idempotency_key="use-climbing-potion",
    )
    athletics = tools.roll_check(
        "pc1",
        "str",
        skill="Athletics",
        difficulty_tier="medium",
        idempotency_key="climbing-potion-athletics",
    )
    dex_athletics = tools.roll_check(
        "pc1",
        "dex",
        skill="Athletics",
        difficulty_tier="medium",
        idempotency_key="climbing-potion-dex-athletics",
    )
    perception = tools.roll_check(
        "pc1",
        "str",
        skill="Perception",
        difficulty_tier="medium",
        idempotency_key="climbing-potion-perception",
    )

    assert potion["success"] is True
    assert state.characters["pc1"].inventory["srd.potion_of_climbing"] == 0
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.use_potion_of_climbing"
    assert effect["condition"] is None
    assert effect["passive_modifiers"] == {
        "climb_speed_equals_speed": True,
        "ability_check_advantage_skills": [{"ability": "str", "skill": "athletics"}],
    }
    assert effect["duration"] == {"until": "duration_1_hour"}
    assert effect["tick_on"] == "self_turn_start"
    assert athletics["roll"]["advantage"] == "advantage"
    assert athletics["status_sources"][0]["modifier"] == "ability_check_advantage_skills"
    assert athletics["status_sources"][0]["source_action_id"] == "srd.use_potion_of_climbing"
    assert dex_athletics["roll"]["advantage"] is None
    assert dex_athletics["status_sources"] == []
    assert perception["roll"]["advantage"] is None
    assert perception["status_sources"] == []


def test_potion_of_clairvoyance_records_non_concentration_sensor_world_effect(
    make_state,
) -> None:
    state = make_state()
    state.characters["pc1"].inventory["srd.potion_of_clairvoyance"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.use_item(
        "pc1",
        "srd.potion_of_clairvoyance",
        ["pc1"],
        idempotency_key="use-clairvoyance-potion",
    )

    assert result["success"] is True
    assert state.characters["pc1"].inventory["srd.potion_of_clairvoyance"] == 0
    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.use_potion_of_clairvoyance"
    assert effect["effect_type"] == "clairvoyant_sensor"
    assert effect["concentration"] is False
    assert effect["scope"] == {"target": "known_or_obvious_location", "range_ft": 5280}
    assert effect["duration"] == {"until": "duration_10_minutes"}
    assert effect["metadata"] == {"choose_sight_or_hearing": True, "concentration": False}
    world_effect_change = next(
        change for change in result["state_changes"] if change["type"] == "world_effect"
    )
    assert world_effect_change["effect_type"] == "clairvoyant_sensor"
    assert world_effect_change["concentration"] is False


def test_potion_of_mind_reading_records_non_concentration_detect_thoughts_world_effect(
    make_state,
) -> None:
    state = make_state()
    state.characters["pc1"].inventory["srd.potion_of_mind_reading"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.use_item(
        "pc1",
        "srd.potion_of_mind_reading",
        ["pc1"],
        idempotency_key="use-mind-reading-potion",
    )

    assert result["success"] is True
    assert state.characters["pc1"].inventory["srd.potion_of_mind_reading"] == 0
    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.use_potion_of_mind_reading"
    assert effect["effect_type"] == "detect_thoughts"
    assert effect["concentration"] is False
    assert effect["scope"] == {"target": "self", "radius_ft": 30}
    assert effect["duration"] == {"until": "duration_10_minutes"}
    assert effect["metadata"] == {
        "surface_thoughts": True,
        "save_dc": 13,
        "concentration": False,
    }
    world_effect_change = next(
        change for change in result["state_changes"] if change["type"] == "world_effect"
    )
    assert world_effect_change["effect_type"] == "detect_thoughts"
    assert world_effect_change["concentration"] is False


def test_potion_of_flying_applies_srd_fly_speed_and_hover(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].inventory["srd.potion_of_flying"] = 1
    state.encounter.combatants["pc1"].speed_ft = 40
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.use_item(
        "pc1",
        "srd.potion_of_flying",
        ["pc1"],
        idempotency_key="use-flying-potion",
    )

    assert result["success"] is True
    assert state.characters["pc1"].inventory["srd.potion_of_flying"] == 0
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.use_potion_of_flying"
    assert effect["condition"] is None
    assert effect["passive_modifiers"] == {
        "fly_speed_equals_speed": True,
        "can_hover": True,
        "fall_if_airborne_on_expiry": True,
    }
    assert effect["duration"] == {"until": "duration_1_hour"}
    assert effect["tick_on"] == "self_turn_start"
    assert fly_speed_from_effects(40, state.encounter.combatants["pc1"].status_effects) == 40
    assert can_hover_from_effects(state.encounter.combatants["pc1"].status_effects) is True

    for _ in range(599):
        lifecycle = tick_effects(state, trigger="self_turn_start", actor_id="pc1")
        assert lifecycle.expired == []
    final_lifecycle = tick_effects(state, trigger="self_turn_start", actor_id="pc1")
    assert final_lifecycle.expired[0]["source_action_id"] == "srd.use_potion_of_flying"
    assert fly_speed_from_effects(40, state.encounter.combatants["pc1"].status_effects) is None
    assert can_hover_from_effects(state.encounter.combatants["pc1"].status_effects) is False


def test_potion_of_gaseous_form_applies_srd_gaseous_effects_without_concentration(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].inventory["srd.potion_of_gaseous_form"] = 1
    state.characters["pc1"].spell_slots["1"] = 1
    state.encounter.combatants["pc1"].hp_current = 12
    state.encounter.combatants["pc1"].hp_max = 12
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    potion = tools.use_item(
        "pc1",
        "srd.potion_of_gaseous_form",
        ["pc1"],
        idempotency_key="use-gaseous-form-potion",
    )
    dex_save = tools.roll_save(
        "pc1",
        "dex",
        difficulty_tier="medium",
        idempotency_key="gaseous-form-dex-save",
    )
    damage = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        _damage_action(9, damage_type="slashing"),
        actor_id="goblin1",
        targets=["pc1"],
        idempotency_key="slashing-damage-after-gaseous-form",
    )

    assert potion["success"] is True
    assert state.characters["pc1"].inventory["srd.potion_of_gaseous_form"] == 0
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.use_potion_of_gaseous_form"
    assert effect["condition"] is None
    assert effect["passive_modifiers"] == {
        "gaseous_form": True,
        "fly_speed_ft": 10,
        "can_hover": True,
        "can_enter_creature_space": True,
        "damage_resistances": ["bludgeoning", "piercing", "slashing"],
        "condition_immunities": ["prone"],
        "saving_throw_advantage_abilities": ["str", "dex", "con"],
        "can_pass_through_narrow_openings": True,
        "liquids_treated_as_solid": True,
        "cannot_talk": True,
        "cannot_manipulate_objects": True,
        "cannot_drop_or_use_carried_objects": True,
        "blocks_attacks": True,
        "blocks_spellcasting": True,
        "can_end_as_bonus_action": True,
    }
    assert effect["duration"] == {"until": "duration_1_hour"}
    assert effect["tick_on"] == "self_turn_start"
    assert effect["concentration"] is False
    assert fly_speed_from_effects(30, state.encounter.combatants["pc1"].status_effects) == 10
    assert can_hover_from_effects(state.encounter.combatants["pc1"].status_effects) is True
    assert dex_save["roll"]["advantage"] == "advantage"
    assert dex_save["status_sources"][0]["modifier"] == "saving_throw_advantage_abilities"

    damage_change = next(change for change in damage.state_changes if change["type"] == "damage")
    assert damage_change["amount"] == 9
    assert damage_change["applied"] == 4
    assert state.encounter.combatants["pc1"].hp_current == 8

    with pytest.raises(AutomationError, match="cannot cast spells"):
        tools.cast_spell(
            "pc1",
            "srd.cure_wounds",
            ["pc1"],
            1,
            idempotency_key="gaseous-form-blocks-spellcasting",
        )
    with pytest.raises(AutomationError, match="cannot attack"):
        tools.perform_action(
            "pc1",
            "srd.shortsword_attack",
            ["goblin1"],
            idempotency_key="gaseous-form-blocks-attacks",
        )

    resolver = ActionResolver(state, compendium.actions, compendium.items)
    rejected = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="attack",
            target_ids=["goblin1"],
            candidate_action_id="srd.shortsword_attack",
        )
    )
    assert rejected.status == "rejected"
    assert "cannot attack" in str(rejected.reason)

    for _ in range(599):
        lifecycle = tick_effects(state, trigger="self_turn_start", actor_id="pc1")
        assert lifecycle.expired == []
    final_lifecycle = tick_effects(state, trigger="self_turn_start", actor_id="pc1")
    assert final_lifecycle.expired[0]["source_action_id"] == "srd.use_potion_of_gaseous_form"
    assert state.encounter.combatants["pc1"].status_effects == []
    assert fly_speed_from_effects(30, state.encounter.combatants["pc1"].status_effects) is None


def test_potion_of_growth_applies_enlarge_effect_without_concentration(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].inventory["srd.potion_of_growth"] = 1
    state.encounter.combatants["goblin1"].armor_class = 1
    state.encounter.combatants["goblin1"].hp_current = 30
    state.encounter.combatants["goblin1"].hp_max = 30
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([10, 10, 10, 2, 4]),
    )

    potion = tools.use_item(
        "pc1",
        "srd.potion_of_growth",
        ["pc1"],
        idempotency_key="use-growth-potion",
    )
    strength_check = tools.roll_check(
        "pc1",
        "str",
        difficulty_tier="medium",
        idempotency_key="growth-potion-strength-check",
    )
    strength_save = tools.roll_save(
        "pc1",
        "str",
        difficulty_tier="medium",
        idempotency_key="growth-potion-strength-save",
    )
    attack = tools.perform_action(
        "pc1",
        "srd.shortsword_attack",
        ["goblin1"],
        idempotency_key="growth-potion-weapon-hit",
    )

    assert potion["success"] is True
    assert state.characters["pc1"].inventory["srd.potion_of_growth"] == 0
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.use_potion_of_growth"
    assert effect["condition"] is None
    assert effect["passive_modifiers"] == {
        "size_change": "enlarge",
        "size_category_delta": 1,
        "ability_check_advantage_abilities": ["str"],
        "saving_throw_advantage_abilities": ["str"],
        "enlarge_weapon_damage_bonus": "1d4",
    }
    assert effect["duration"] == {"until": "duration_10_minutes"}
    assert effect["tick_on"] == "self_turn_start"
    assert effect["concentration"] is False
    assert strength_check["roll"]["advantage"] == "advantage"
    assert strength_check["status_sources"][0]["modifier"] == ("ability_check_advantage_abilities")
    assert strength_save["roll"]["advantage"] == "advantage"
    assert strength_save["status_sources"][0]["modifier"] == ("saving_throw_advantage_abilities")

    damage = next(change for change in attack["state_changes"] if change["type"] == "damage")
    assert damage["amount"] == 9
    assert damage["applied"] == 9
    assert damage["enlarge_weapon_damage_bonus"] == 4
    assert damage["enlarge_weapon_damage_sources"][0]["source_action_id"] == (
        "srd.use_potion_of_growth"
    )
    assert damage["enlarge_weapon_damage_sources"][0]["damage_type"] == "piercing"

    for _ in range(99):
        lifecycle = tick_effects(state, trigger="self_turn_start", actor_id="pc1")
        assert lifecycle.expired == []
    final_lifecycle = tick_effects(state, trigger="self_turn_start", actor_id="pc1")
    assert final_lifecycle.expired[0]["source_action_id"] == "srd.use_potion_of_growth"
    assert state.encounter.combatants["pc1"].status_effects == []


def test_potion_of_speed_applies_haste_without_concentration_or_lethargy(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].inventory["srd.potion_of_speed"] = 1
    state.encounter.combatants["pc1"].speed_ft = 30
    state.encounter.combatants["pc1"].armor_class = 16
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([12]),
    )

    potion = tools.use_item(
        "pc1",
        "srd.potion_of_speed",
        ["pc1"],
        idempotency_key="use-speed-potion",
    )
    attack = tools.perform_action(
        "goblin1",
        "srd.shortsword_attack",
        ["pc1"],
        idempotency_key="speed-potion-ac-check",
    )

    assert potion["success"] is True
    assert state.characters["pc1"].inventory["srd.potion_of_speed"] == 0
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.use_potion_of_speed"
    assert effect["condition"] is None
    assert effect["passive_modifiers"] == {
        "armor_class_bonus": 2,
        "speed_multiplier": 2,
        "extra_action_limited": True,
        "no_haste_lethargy_on_expiry": True,
    }
    assert effect["duration"] == {"until": "duration_1_minute"}
    assert effect["tick_on"] == "self_turn_start"
    assert effect["concentration"] is False
    assert effective_speed(30, state.encounter.combatants["pc1"].status_effects) == 60
    attack_node = attack["node_results"]["automation[1]"]
    assert attack_node["total"] == 17
    assert attack_node["ac"] == 18
    assert attack_node["hit"] is False
    assert attack_node["armor_class_sources"][0]["modifier"] == "armor_class_bonus"
    assert attack_node["armor_class_sources"][0]["source_action_id"] == ("srd.use_potion_of_speed")

    for _ in range(9):
        lifecycle = tick_effects(state, trigger="self_turn_start", actor_id="pc1")
        assert lifecycle.expired == []
    final_lifecycle = tick_effects(state, trigger="self_turn_start", actor_id="pc1")
    assert final_lifecycle.expired[0]["source_action_id"] == "srd.use_potion_of_speed"
    assert state.encounter.combatants["pc1"].status_effects == []


def test_potion_of_resistance_applies_selected_srd_damage_resistance(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].inventory["srd.potion_of_resistance"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    potion = tools.use_item(
        "pc1",
        "srd.potion_of_resistance",
        ["pc1"],
        params={"damage_type": "Fire"},
        idempotency_key="use-resistance-potion",
    )
    damage = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        _damage_action(9, damage_type="fire"),
        actor_id="goblin1",
        targets=["pc1"],
        idempotency_key="fire-damage-after-resistance-potion",
    )

    assert potion["success"] is True
    assert state.characters["pc1"].inventory["srd.potion_of_resistance"] == 0
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.use_potion_of_resistance"
    assert effect["condition"] is None
    assert effect["passive_modifiers"] == {"damage_resistances": "fire"}
    assert effect["duration"] == {"until": "duration_1_hour"}
    assert effect["tick_on"] == "self_turn_start"
    damage_change = next(change for change in damage.state_changes if change["type"] == "damage")
    assert damage_change["amount"] == 9
    assert damage_change["applied"] == 4
    assert state.encounter.combatants["pc1"].hp_current == 6


def test_potion_of_resistance_requires_srd_damage_type_before_cost(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].inventory["srd.potion_of_resistance"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="damage_type"):
        tools.use_item(
            "pc1",
            "srd.potion_of_resistance",
            ["pc1"],
            params={},
            idempotency_key="resistance-potion-missing-type",
        )
    with pytest.raises(AutomationError, match="damage_type must be one of"):
        tools.use_item(
            "pc1",
            "srd.potion_of_resistance",
            ["pc1"],
            params={"damage_type": "slashing"},
            idempotency_key="resistance-potion-invalid-type",
        )

    assert state.characters["pc1"].inventory["srd.potion_of_resistance"] == 1
    assert state.encounter.action_budgets == {}
    assert state.encounter.combatants["pc1"].status_effects == []


def test_potion_of_invulnerability_applies_all_damage_resistance_for_one_minute(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].inventory["srd.potion_of_invulnerability"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    potion = tools.use_item(
        "pc1",
        "srd.potion_of_invulnerability",
        ["pc1"],
        idempotency_key="use-invulnerability-potion",
    )
    damage = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        _damage_action(9, damage_type="force"),
        actor_id="goblin1",
        targets=["pc1"],
        idempotency_key="force-damage-after-invulnerability-potion",
    )

    assert potion["success"] is True
    assert state.characters["pc1"].inventory["srd.potion_of_invulnerability"] == 0
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.use_potion_of_invulnerability"
    assert effect["condition"] is None
    assert effect["passive_modifiers"] == {"all_damage_resistance": True}
    assert effect["duration"] == {"until": "duration_1_minute"}
    assert effect["tick_on"] == "self_turn_start"
    damage_change = next(change for change in damage.state_changes if change["type"] == "damage")
    assert damage_change["amount"] == 9
    assert damage_change["applied"] == 4

    for _ in range(9):
        lifecycle = tick_effects(state, trigger="self_turn_start", actor_id="pc1")
        assert lifecycle.expired == []
    final_lifecycle = tick_effects(state, trigger="self_turn_start", actor_id="pc1")
    assert final_lifecycle.expired[0]["source_action_id"] == "srd.use_potion_of_invulnerability"
    assert state.encounter.combatants["pc1"].status_effects == []


def test_potion_of_poison_deals_poison_damage_and_poisoned_on_failed_save(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].inventory["srd.potion_of_poison"] = 1
    state.characters["pc1"].hp_current = 10
    state.encounter.combatants["pc1"].hp_current = 10
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([6, 1]),
    )

    result = tools.use_item(
        "pc1",
        "srd.potion_of_poison",
        ["pc1"],
        idempotency_key="use-poison-potion-failed-save",
    )

    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    poison_effect = state.encounter.combatants["pc1"].status_effects[-1]
    save = result["node_results"]["automation[2]"]
    assert result["success"] is True
    assert result["dice_rolls"][0]["expression"] == "4d6"
    assert damage_change["damage_type"] == "poison"
    assert damage_change["amount"] == 6
    assert damage_change["applied"] == 6
    assert save["dc"] == 13
    assert save["dc_source"] == "dc_ref:srd.potion_of_poison.con_save"
    assert save["success"] is False
    assert poison_effect["condition"] == "poisoned"
    assert poison_effect["source_action_id"] == "srd.use_potion_of_poison"
    assert poison_effect["duration"] == {"until": "duration_1_hour"}
    assert poison_effect["tick_on"] == "self_turn_start"
    assert state.characters["pc1"].inventory["srd.potion_of_poison"] == 0


def test_potion_of_poison_successful_save_still_deals_damage_without_poisoned(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].inventory["srd.potion_of_poison"] = 1
    state.characters["pc1"].hp_current = 10
    state.encounter.combatants["pc1"].hp_current = 10
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([5, 20]),
    )

    result = tools.use_item(
        "pc1",
        "srd.potion_of_poison",
        ["pc1"],
        idempotency_key="use-poison-potion-successful-save",
    )

    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    save = result["node_results"]["automation[2]"]
    assert damage_change["applied"] == 5
    assert save["success"] is True
    assert not [
        effect
        for effect in state.encounter.combatants["pc1"].status_effects
        if effect.get("condition") == "poisoned"
    ]
    assert state.characters["pc1"].inventory["srd.potion_of_poison"] == 0


def test_potion_of_water_breathing_applies_srd_underwater_breathing(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].inventory["srd.potion_of_water_breathing"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.use_item(
        "pc1",
        "srd.potion_of_water_breathing",
        ["pc1"],
        idempotency_key="use-water-breathing-potion",
    )

    assert result["success"] is True
    assert state.characters["pc1"].inventory["srd.potion_of_water_breathing"] == 0
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.use_potion_of_water_breathing"
    assert effect["condition"] is None
    assert effect["passive_modifiers"] == {"can_breathe_underwater": True}
    assert effect["duration"] == {"until": "duration_24_hours"}
    assert effect["tick_on"] == "environment"


def test_hazard_requires_traceable_params(make_state) -> None:
    state = make_state()
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    try:
        tools.apply_hazard(["pc1"], "srd.falling_30ft", {"source": "llm_guess"})
    except ValueError as exc:
        assert "traceable" in str(exc)
    else:
        raise AssertionError("hazard accepted untraceable params")

    result = tools.apply_hazard(["pc1"], "srd.falling_30ft", {"source": "map"})
    assert result["success"] is True
    assert any(
        change["type"] == "condition" and change["condition"] == "prone"
        for change in result["state_changes"]
    )


def test_monk_slow_fall_reduces_falling_damage_and_spends_reaction(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"monk": 4}
    state.characters["pc1"].actions.append("srd.slow_fall")
    state.characters["pc1"].hp_current = 10
    state.encounter.combatants["pc1"].hp_current = 10
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([6]),
    )

    result = tools.apply_hazard(
        ["pc1"],
        "srd.falling_30ft",
        {"source": "map", "use_slow_fall": True},
    )

    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    slow_fall_change = next(
        change for change in result["state_changes"] if change["type"] == "slow_fall"
    )
    economy_change = next(
        change
        for change in result["state_changes"]
        if change.get("source_action_id") == "srd.slow_fall" and change["type"] == "action_economy"
    )
    assert damage_change["amount_before_slow_fall"] == 6
    assert damage_change["amount"] == 0
    assert damage_change["applied"] == 0
    assert damage_change["slow_fall"]["reduction_cap"] == 20
    assert slow_fall_change["reduction"] == 6
    assert economy_change["after"]["reaction"] == 0
    assert state.encounter.combatants["pc1"].hp_current == 10
    assert any(
        change["type"] == "condition" and change["condition"] == "prone"
        for change in result["state_changes"]
    )


def test_slow_fall_requires_monk_level_four_before_hazard_damage(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"monk": 3}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="Slow Fall requires Monk level 4"):
        tools.apply_hazard(
            ["pc1"],
            "srd.falling_30ft",
            {"source": "map", "use_slow_fall": True},
        )

    assert state.encounter.action_budgets == {}


def test_slow_fall_requires_falling_damage(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"monk": 4}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="Slow Fall requires falling damage"):
        tools.apply_hazard(
            ["pc1"],
            "srd.burning_oil",
            {"source": "map", "use_slow_fall": True},
        )


def test_monk_deflect_attacks_reduces_attack_damage_and_spends_reaction(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"monk": 3}
    character.actions.append("srd.deflect_attacks")
    state.encounter.combatants["pc1"].armor_class = 1
    state.encounter.combatants["pc1"].hp_current = 10
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([10, 4, 3]),
    )

    result = tools.perform_action(
        "goblin1",
        "srd.bandit_scimitar",
        ["pc1"],
        params={"use_deflect_attacks": True},
        idempotency_key="deflect-attacks-reduce",
    )

    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    deflect_change = next(
        change for change in result["state_changes"] if change["type"] == "deflect_attacks"
    )
    economy_change = next(
        change
        for change in result["state_changes"]
        if change.get("source_action_id") == "srd.deflect_attacks"
        and change["type"] == "action_economy"
    )
    assert result["success"] is True
    assert damage_change["amount_before_deflect_attacks"] == 5
    assert damage_change["amount"] == 0
    assert damage_change["applied"] == 0
    assert deflect_change["reduction_cap"] == 8
    assert deflect_change["reduction"] == 5
    assert deflect_change["reduced_amount"] == 0
    assert damage_change["deflect_attacks"]["source_action_id"] == "srd.deflect_attacks"
    assert economy_change["after"]["reaction"] == 0
    assert state.encounter.combatants["pc1"].hp_current == 10


def test_monk_deflect_attacks_redirects_when_damage_is_reduced_to_zero(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"monk": 3}
    character.actions.append("srd.deflect_attacks")
    character.resources["srd.resource.focus_points"] = 3
    state.encounter.combatants["pc1"].armor_class = 1
    state.encounter.combatants["goblin1"].abilities["dex"] = 10
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([10, 4, 10, 1, 2, 3]),
    )

    result = tools.perform_action(
        "goblin1",
        "srd.bandit_scimitar",
        ["pc1"],
        params={
            "use_deflect_attacks": True,
            "deflect_attacks_redirect_target_id": "goblin1",
        },
        idempotency_key="deflect-attacks-redirect",
    )

    redirect_change = next(
        change for change in result["state_changes"] if change["type"] == "deflect_attacks_redirect"
    )
    cost_change = next(
        change
        for change in result["state_changes"]
        if change["type"] == "cost" and change["source_action_id"] == "srd.deflect_attacks"
    )
    assert result["success"] is True
    assert redirect_change["saving_throw_success"] is False
    assert redirect_change["damage_type"] == "slashing"
    assert redirect_change["martial_arts_die"] == "d6"
    assert redirect_change["damage_amount"] == 7
    assert redirect_change["damage_applied"] == 7
    assert cost_change["before"] == 3
    assert cost_change["after"] == 2
    assert character.resources["srd.resource.focus_points"] == 2
    assert state.encounter.combatants["goblin1"].hp_current == 0
    save_result = result["node_results"]["automation[2].deflect_attacks.redirect"]
    assert save_result["dc_source"] == "monk_focus:wis+proficiency"


def test_deflect_attacks_requires_monk_level_three_before_spending_attack(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"monk": 2}
    state.encounter.combatants["pc1"].armor_class = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="Deflect Attacks requires Monk level 3"):
        tools.perform_action(
            "goblin1",
            "srd.bandit_scimitar",
            ["pc1"],
            params={"use_deflect_attacks": True},
            idempotency_key="deflect-attacks-no-monk",
        )

    assert state.encounter.action_budgets == {}


def test_monk_stunning_strike_failed_save_stuns_and_spends_focus(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"monk": 5}
    character.proficiency_bonus = 3
    character.actions.extend(["srd.monk_unarmed_strike", "srd.stunning_strike"])
    character.resources["srd.resource.focus_points"] = 5
    state.encounter.combatants["goblin1"].abilities["con"] = 10
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([10, 4, 1]),
    )

    result = tools.perform_action(
        "pc1",
        "srd.monk_unarmed_strike",
        ["goblin1"],
        params={"use_stunning_strike": True},
        idempotency_key="stunning-strike-failed-save",
    )

    stunning_change = next(
        change for change in result["state_changes"] if change["type"] == "stunning_strike"
    )
    condition_change = next(
        change
        for change in result["state_changes"]
        if change["type"] == "condition" and change["condition"] == "stunned"
    )
    save_result = result["node_results"]["automation[2].stunning_strike"]
    assert result["success"] is True
    assert character.resources["srd.resource.focus_points"] == 4
    assert stunning_change["saving_throw_success"] is False
    assert stunning_change["dc"] == 12
    assert save_result["dc_source"] == "monk_focus:wis+proficiency"
    assert save_result["total"] == 1
    assert condition_change["duration"] == {"until": "start_of_next_turn"}
    assert condition_change["tick_on"] == "self_turn_start"
    assert any(
        effect["condition"] == "stunned" and effect["source_action_id"] == "srd.stunning_strike"
        for effect in state.encounter.combatants["goblin1"].status_effects
    )


def test_monk_stunning_strike_success_halves_speed_and_next_attack_has_advantage(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"monk": 5}
    character.proficiency_bonus = 3
    character.actions.extend(["srd.monk_unarmed_strike", "srd.stunning_strike"])
    character.resources["srd.resource.focus_points"] = 5
    goblin = state.encounter.combatants["goblin1"]
    goblin.abilities["con"] = 10
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([10, 1, 20]),
    )

    result = tools.perform_action(
        "pc1",
        "srd.monk_unarmed_strike",
        ["goblin1"],
        params={"use_stunning_strike": True},
        idempotency_key="stunning-strike-successful-save",
    )

    slowed_effect = next(
        effect
        for effect in goblin.status_effects
        if effect["condition"] == "stunning_strike_slowed"
    )
    assert result["success"] is True
    assert result["node_results"]["automation[2].stunning_strike"]["success"] is True
    assert slowed_effect["passive_modifiers"] == {
        "speed_multiplier": 0.5,
        "incoming_attack_advantage": True,
        "consume_on_incoming_attack": True,
    }
    assert effective_speed(goblin.speed_ft, goblin.status_effects) == 15

    attack = AutomationExecutor(
        state,
        _FixedSingleDieRollService([5, 2]),
        AuditLog(),
    ).execute(
        _attack_action(),
        actor_id="pc2",
        targets=["goblin1"],
        idempotency_key="stunning-strike-next-attack",
    )

    attack_node = attack.node_results["automation[1]"]
    assert attack.dice_rolls[0]["advantage"] == "advantage"
    assert attack_node["status_advantage"] == "advantage"
    assert attack_node["status_sources"][0]["modifier"] == "incoming_attack_advantage"
    assert any(change["type"] == "effect_expired" for change in attack.state_changes)
    assert not any(
        effect["condition"] == "stunning_strike_slowed" for effect in goblin.status_effects
    )


def test_stunning_strike_can_be_used_only_once_per_turn(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"monk": 5}
    character.proficiency_bonus = 3
    character.actions.extend(["srd.monk_unarmed_strike", "srd.stunning_strike"])
    character.resources["srd.resource.focus_points"] = 5
    state.encounter.combatants["goblin1"].abilities["con"] = 10
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([10, 4, 1]),
    )

    tools.perform_action(
        "pc1",
        "srd.monk_unarmed_strike",
        ["goblin1"],
        params={"use_stunning_strike": True},
        idempotency_key="stunning-strike-once-first",
    )

    with pytest.raises(AutomationError, match="only once per turn"):
        tools.perform_action(
            "pc1",
            "srd.monk_unarmed_strike",
            ["goblin1"],
            params={"use_stunning_strike": True},
            idempotency_key="stunning-strike-once-second",
        )

    assert character.resources["srd.resource.focus_points"] == 4


def test_stunning_strike_requires_focus_before_spending_action(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"monk": 5}
    character.proficiency_bonus = 3
    character.actions.extend(["srd.monk_unarmed_strike", "srd.stunning_strike"])
    character.resources["srd.resource.focus_points"] = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="focus_points"):
        tools.perform_action(
            "pc1",
            "srd.monk_unarmed_strike",
            ["goblin1"],
            params={"use_stunning_strike": True},
            idempotency_key="stunning-strike-no-focus",
        )

    assert state.encounter.action_budgets == {}
    assert character.resources["srd.resource.focus_points"] == 0


def test_stunning_strike_does_not_spend_focus_on_miss(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"monk": 5}
    character.proficiency_bonus = 3
    character.actions.extend(["srd.monk_unarmed_strike", "srd.stunning_strike"])
    character.resources["srd.resource.focus_points"] = 5
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1]),
    )

    result = tools.perform_action(
        "pc1",
        "srd.monk_unarmed_strike",
        ["goblin1"],
        params={"use_stunning_strike": True},
        idempotency_key="stunning-strike-miss",
    )

    assert result["success"] is True
    assert character.resources["srd.resource.focus_points"] == 5
    assert not any(
        change.get("source_action_id") == "srd.stunning_strike"
        for change in result["state_changes"]
    )
    assert not state.encounter.combatants["goblin1"].status_effects


def test_stunning_strike_requires_monk_weapon_or_unarmed_strike(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"monk": 5}
    character.proficiency_bonus = 3
    character.actions.extend(["srd.longsword_attack", "srd.stunning_strike"])
    character.resources["srd.resource.focus_points"] = 5
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="Monk weapon or Unarmed Strike"):
        tools.perform_action(
            "pc1",
            "srd.longsword_attack",
            ["goblin1"],
            params={"use_stunning_strike": True},
            idempotency_key="stunning-strike-longsword",
        )

    assert state.encounter.action_budgets == {}
    assert character.resources["srd.resource.focus_points"] == 5


def test_dehydration_hazard_applies_srd_exhaustion(make_state) -> None:
    state = make_state()
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.apply_hazard(["pc1"], "srd.dehydration", {"source": "rules_discrete"})

    condition_change = [
        change for change in result["state_changes"] if change["type"] == "condition"
    ][0]
    assert condition_change["condition"] == "exhaustion"
    assert condition_change["level_before"] == 0
    assert condition_change["level_after"] == 1
    assert state.characters["pc1"].status_effects[-1]["condition"] == "exhaustion"


def test_strong_wind_hazard_applies_ranged_weapon_disadvantage(make_state) -> None:
    state = make_state()
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    wind = tools.apply_hazard(["pc1"], "srd.strong_wind", {"source": "rules_discrete"})
    attack = tools.perform_action(
        "pc1",
        "srd.bandit_light_crossbow",
        ["goblin1"],
        idempotency_key="wind-ranged-attack",
    )

    assert any(change["type"] == "passive_effect" for change in wind["state_changes"])
    assert not any(
        change["type"] == "condition" and change.get("condition") == "prone"
        for change in wind["state_changes"]
    )
    attack_roll = attack["dice_rolls"][0]
    attack_node = attack["node_results"]["automation[1]"]
    assert attack_roll["advantage"] == "disadvantage"
    assert attack_node["status_advantage"] == "disadvantage"
    assert attack_node["status_sources"][0]["modifier"] == "ranged_weapon_attack_disadvantage"


def test_automation_checks_record_dc_source(make_state) -> None:
    state = make_state()
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action("pc1", "srd.hide", [])

    assert result["success"] is True
    assert result["node_results"]["automation[1]"]["dc_source"] == "difficulty_tier:medium"


def test_saving_throw_uses_combatant_or_backing_entity_abilities(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.monsters["goblin_entity"] = Monster(
        id="goblin_entity",
        name="Goblin",
        abilities={"str": 8, "dex": 18, "con": 10, "int": 10, "wis": 8, "cha": 8},
        hp_current=7,
        hp_max=7,
        armor_class=12,
    )
    state.encounter.combatants["goblin1"].entity_id = "goblin_entity"
    state.encounter.combatants["goblin1"].abilities.clear()
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action("pc1", "srd.sacred_flame", ["goblin1"])

    assert result["success"] is True
    assert result["dice_rolls"][0]["expression"] == "1d20+4"


def test_roll_save_uses_saving_throw_proficiency_and_audits(make_state) -> None:
    state = make_state()
    state.characters["pc1"].saving_throw_proficiencies = ["con"]
    compendium = CompendiumLoader("rules_data").load()
    audit = AuditLog()
    tools = EngineTools(state, compendium, audit)

    result = tools.roll_save("pc1", "con", difficulty_tier="medium", idempotency_key="save-1")
    repeated = tools.roll_save("pc1", "con", difficulty_tier="medium", idempotency_key="save-1")

    assert repeated == result
    assert result["tool"] == "roll_save"
    assert result["proficient"] is True
    assert result["bonus"] == 4
    assert result["roll"]["expression"] == "1d20+4"
    assert audit.events[-1].tool_name == "roll_save"


def test_roll_save_applies_barbarian_danger_sense_to_dex_saves(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"barbarian": 2}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.roll_save("pc1", "dex", difficulty_tier="medium", idempotency_key="danger-1")

    assert result["roll"]["advantage"] == "advantage"
    assert result["roll"]["expression"] == "1d20+2"

    state.encounter.combatants["pc1"].status_effects.append(
        {"effect_id": "incapacitated-test", "condition": "incapacitated"}
    )
    incapacitated = tools.roll_save(
        "pc1",
        "dex",
        difficulty_tier="medium",
        idempotency_key="danger-incapacitated",
    )

    assert incapacitated["roll"]["advantage"] is None


def test_roll_check_uses_skill_and_tool_proficiency(make_state) -> None:
    state = make_state()
    state.characters["pc1"].skill_proficiencies = ["sleight_of_hand"]
    state.characters["pc1"].tool_proficiencies = ["thieves_tools"]
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.roll_check(
        "pc1",
        "dex",
        skill="Sleight of Hand",
        tool="Thieves' Tools",
        difficulty_tier="medium",
    )

    assert result["skill"] == "sleight_of_hand"
    assert result["tool"] == "thieves_tools"
    assert result["proficient"] is True
    assert result["proficiency_sources"] == ["skill:sleight_of_hand", "tool:thieves_tools"]
    assert result["bonus"] == 4
    assert result["roll"]["expression"] == "1d20+4"
    assert result["roll"]["advantage"] == "advantage"


def test_roll_check_applies_skill_expertise(make_state) -> None:
    state = make_state()
    state.characters["pc1"].skill_proficiencies = ["stealth"]
    state.characters["pc1"].skill_expertise = ["stealth"]
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.roll_check("pc1", "dex", skill="Stealth", difficulty_tier="medium")

    assert result["proficient"] is True
    assert result["proficiency_sources"] == ["skill:stealth", "feature:expertise:stealth"]
    assert result["bonus"] == 6
    assert result["roll"]["expression"] == "1d20+6"


def test_roll_check_applies_bard_jack_of_all_trades_to_unproficient_skill(
    make_state,
) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"bard": 2}
    state.characters["pc1"].skill_proficiencies = []
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.roll_check("pc1", "dex", skill="Stealth", difficulty_tier="medium")

    assert result["proficient"] is False
    assert result["proficiency_sources"] == ["feature:jack_of_all_trades"]
    assert result["bonus"] == 3
    assert result["roll"]["expression"] == "1d20+3"


def test_roll_check_applies_cleric_thaumaturge_to_int_arcana_and_religion(
    make_state,
) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"cleric": 1}
    state.characters["pc1"].feature_choices = {"cleric.divine_order": "thaumaturge"}
    state.characters["pc1"].abilities["int"] = 10
    state.characters["pc1"].abilities["wis"] = 16
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    arcana = tools.roll_check(
        "pc1",
        "int",
        skill="Arcana",
        difficulty_tier="medium",
        idempotency_key="thaumaturge-arcana",
    )
    religion = tools.roll_check(
        "pc1",
        "int",
        skill="Religion",
        difficulty_tier="medium",
        idempotency_key="thaumaturge-religion",
    )
    history = tools.roll_check(
        "pc1",
        "int",
        skill="History",
        difficulty_tier="medium",
        idempotency_key="thaumaturge-history",
    )

    assert arcana["proficient"] is False
    assert arcana["proficiency_sources"] == ["feature:divine_order_thaumaturge"]
    assert arcana["bonus"] == 3
    assert arcana["roll"]["expression"] == "1d20+3"
    assert religion["proficiency_sources"] == ["feature:divine_order_thaumaturge"]
    assert religion["bonus"] == 3
    assert history["proficiency_sources"] == []
    assert history["bonus"] == 0


def test_roll_check_cleric_protector_does_not_gain_thaumaturge_bonus(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"cleric": 1}
    state.characters["pc1"].feature_choices = {"cleric.divine_order": "protector"}
    state.characters["pc1"].abilities["int"] = 10
    state.characters["pc1"].abilities["wis"] = 16
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.roll_check("pc1", "int", skill="Arcana", difficulty_tier="medium")

    assert result["proficiency_sources"] == []
    assert result["bonus"] == 0


def test_roll_check_applies_druid_magician_to_int_arcana_and_nature(
    make_state,
) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"druid": 1}
    state.characters["pc1"].feature_choices = {"druid.primal_order": "magician"}
    state.characters["pc1"].abilities["int"] = 10
    state.characters["pc1"].abilities["wis"] = 8
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    arcana = tools.roll_check(
        "pc1",
        "int",
        skill="Arcana",
        difficulty_tier="medium",
        idempotency_key="magician-arcana",
    )
    nature = tools.roll_check(
        "pc1",
        "int",
        skill="Nature",
        difficulty_tier="medium",
        idempotency_key="magician-nature",
    )
    religion = tools.roll_check(
        "pc1",
        "int",
        skill="Religion",
        difficulty_tier="medium",
        idempotency_key="magician-religion",
    )

    assert arcana["proficiency_sources"] == ["feature:primal_order_magician"]
    assert arcana["bonus"] == 1
    assert arcana["roll"]["expression"] == "1d20+1"
    assert nature["proficiency_sources"] == ["feature:primal_order_magician"]
    assert nature["bonus"] == 1
    assert religion["proficiency_sources"] == []
    assert religion["bonus"] == 0


def test_roll_check_druid_warden_does_not_gain_magician_bonus(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"druid": 1}
    state.characters["pc1"].feature_choices = {"druid.primal_order": "warden"}
    state.characters["pc1"].abilities["int"] = 10
    state.characters["pc1"].abilities["wis"] = 16
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.roll_check("pc1", "int", skill="Nature", difficulty_tier="medium")

    assert result["proficiency_sources"] == []
    assert result["bonus"] == 0


def test_roll_check_primal_knowledge_uses_strength_for_eligible_rage_skill(
    make_state,
) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"barbarian": 3}
    state.characters["pc1"].status_effects.append(
        {
            "effect_id": "rage-test",
            "condition": "raging",
            "source_action_id": "srd.rage",
            "passive_modifiers": {"ability_check_advantage_abilities": ["str"]},
        }
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.roll_check(
        "pc1",
        "dex",
        skill="Stealth",
        difficulty_tier="medium",
        use_primal_knowledge=True,
    )

    assert result["ability"] == "str"
    assert result["original_ability"] == "dex"
    assert result["skill"] == "stealth"
    assert result["bonus"] == 3
    assert result["roll"]["expression"] == "1d20+3"
    assert result["roll"]["advantage"] == "advantage"
    assert result["primal_knowledge"] == {
        "feature": "primal_knowledge",
        "skill": "stealth",
        "original_ability": "dex",
        "ability": "str",
    }
    assert result["status_sources"][0]["modifier"] == "ability_check_advantage_abilities"


def test_roll_check_remarkable_athlete_advantages_strength_athletics(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"fighter": 3}
    state.characters["pc1"].subclasses = {"fighter": "champion"}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.roll_check("pc1", "str", skill="Athletics", difficulty_tier="medium")

    assert result["ability"] == "str"
    assert result["skill"] == "athletics"
    assert result["roll"]["advantage"] == "advantage"
    assert result["status_sources"][0]["modifier"] == "remarkable_athlete"
    assert result["status_sources"][0]["source_action_id"] == "srd.remarkable_athlete"


def test_roll_check_tactical_mind_can_turn_failed_check_into_success(make_state) -> None:
    state = make_state()
    state.rng_seed = 1
    state.characters["pc1"].class_levels = {"fighter": 2}
    state.characters["pc1"].resources["srd.resource.second_wind"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.roll_check(
        "pc1",
        "dex",
        difficulty_tier="hard",
        use_tactical_mind=True,
        idempotency_key="tactical-mind-success",
    )

    assert result["roll"]["total"] == 18
    assert result["tactical_mind"] == {
        "resource": "srd.resource.second_wind",
        "resource_before": 1,
        "resource_after": 0,
        "roll_total": 8,
        "total_before": 18,
        "total_after": 26,
        "spent": True,
        "success": True,
    }
    assert result["total"] == 26
    assert result["success"] is True
    assert state.characters["pc1"].resources["srd.resource.second_wind"] == 0


def test_roll_check_tactical_mind_does_not_spend_second_wind_if_still_failed(
    make_state,
) -> None:
    state = make_state()
    state.rng_seed = 1
    state.characters["pc1"].class_levels = {"fighter": 2}
    state.characters["pc1"].resources["srd.resource.second_wind"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.roll_check(
        "pc1",
        "wis",
        difficulty_tier="medium",
        use_tactical_mind=True,
        idempotency_key="tactical-mind-fail",
    )

    assert result["roll"]["total"] == 5
    assert result["tactical_mind"]["roll_total"] == 8
    assert result["tactical_mind"]["total_after"] == 13
    assert result["tactical_mind"]["spent"] is False
    assert result["success"] is False
    assert state.characters["pc1"].resources["srd.resource.second_wind"] == 1


def test_roll_check_applies_exhaustion_d20_penalty(make_state) -> None:
    state = make_state()
    state.characters["pc1"].status_effects.append(
        {"effect_id": "exhaustion-test", "condition": "exhaustion", "level": 2}
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.roll_check("pc1", "dex", difficulty_tier="medium")

    assert result["bonus"] == -2
    assert result["d20_penalty"] == 4
    assert result["d20_penalty_sources"] == [{"condition": "exhaustion", "level": 2, "penalty": 4}]
    assert result["roll"]["expression"] == "1d20-2"


def test_automation_attack_applies_exhaustion_d20_penalty(make_state) -> None:
    state = make_state()
    state.characters["pc1"].status_effects.append(
        {"effect_id": "exhaustion-test", "condition": "exhaustion", "level": 2}
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action("pc1", "srd.shortsword_attack", ["goblin1"])

    attack_node = result["node_results"]["automation[1]"]
    assert result["dice_rolls"][0]["expression"] == "1d20+1"
    assert attack_node["base_attack_bonus"] == 5
    assert attack_node["d20_penalty"] == 4
    assert attack_node["exhaustion_level"] == 2


def test_automation_saving_throw_uses_backing_character_proficiency(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].saving_throw_proficiencies = ["con"]
    state.encounter.combatants["pc1"].abilities = {
        "str": 10,
        "dex": 10,
        "con": 14,
        "int": 10,
        "wis": 10,
        "cha": 10,
    }
    action = ActionDefinition(
        id="test.con_save",
        name="Con Save",
        localization={"en": "Con Save", "zh": "体质豁免", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={"normal_ft": 5},
        target_policy={"min": 1, "max": 1, "harmful": False},
        automation=[{"type": "saving_throw", "ability": "con", "difficulty_tier": "medium"}],
    )

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="pc2",
        targets=["pc1"],
    )

    save_node = result.node_results["automation[0]"]
    assert result.dice_rolls[0]["expression"] == "1d20+4"
    assert save_node["bonus"] == 4
    assert save_node["proficient"] is True


def test_automation_saving_throw_applies_barbarian_danger_sense(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"barbarian": 2}
    action = ActionDefinition(
        id="test.dex_save",
        name="Dex Save",
        localization={"en": "Dex Save", "zh": "敏捷豁免", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={"normal_ft": 5},
        target_policy={"min": 1, "max": 1, "harmful": False},
        automation=[{"type": "saving_throw", "ability": "dex", "difficulty_tier": "medium"}],
    )

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="pc2",
        targets=["pc1"],
    )

    save_node = result.node_results["automation[0]"]
    assert result.dice_rolls[0]["advantage"] == "advantage"
    assert save_node["status_advantage"] == "advantage"
    assert save_node["status_sources"] == [
        {"kind": "advantage", "modifier": "danger_sense", "ability": "dex"}
    ]

    state.encounter.combatants["pc1"].status_effects.append(
        {"effect_id": "incapacitated-test", "condition": "incapacitated"}
    )
    incapacitated = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="pc2",
        targets=["pc1"],
    )

    incapacitated_save = incapacitated.node_results["automation[0]"]
    assert incapacitated.dice_rolls[0]["advantage"] is None
    assert incapacitated_save["status_advantage"] is None
    assert incapacitated_save["status_sources"] == []


def test_monk_evasion_takes_no_damage_on_successful_dex_save(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"monk": 7}
    state.characters["pc1"].saving_throw_proficiencies = ["dex"]
    action = ActionDefinition(
        id="test.dex_save_half_damage",
        name="Dex Save Half Damage",
        localization={"en": "Dex Save Half Damage", "zh": "敏捷半伤", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={"normal_ft": 5},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "saving_throw", "ability": "dex", "difficulty_tier": "medium"},
            {"type": "damage", "amount": 10, "damage_type": "fire", "save_half": True},
        ],
    )

    result = AutomationExecutor(
        state,
        _FixedSingleDieRollService([12]),
        AuditLog(),
    ).execute(action, actor_id="goblin1", targets=["pc1"])

    damage_change = next(change for change in result.state_changes if change["type"] == "damage")
    assert result.node_results["automation[0]"]["success"] is True
    assert damage_change["amount"] == 0
    assert damage_change["applied"] == 0
    assert damage_change["amount_before_evasion"] == 10
    assert damage_change["evasion"] == {
        "source_action_id": "srd.evasion",
        "save_ability": "dex",
        "saving_throw_success": True,
        "amount_before_evasion": 10,
        "amount_after_evasion": 0,
    }
    assert state.encounter.combatants["pc1"].hp_current == 10


def test_monk_evasion_halves_damage_on_failed_dex_save(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"monk": 7}
    state.characters["pc1"].saving_throw_proficiencies = ["dex"]
    action = ActionDefinition(
        id="test.dex_save_half_damage",
        name="Dex Save Half Damage",
        localization={"en": "Dex Save Half Damage", "zh": "敏捷半伤", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={"normal_ft": 5},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "saving_throw", "ability": "dex", "difficulty_tier": "medium"},
            {"type": "damage", "amount": 10, "damage_type": "fire", "save_half": True},
        ],
    )

    result = AutomationExecutor(
        state,
        _FixedSingleDieRollService([1]),
        AuditLog(),
    ).execute(action, actor_id="goblin1", targets=["pc1"])

    damage_change = next(change for change in result.state_changes if change["type"] == "damage")
    assert result.node_results["automation[0]"]["success"] is False
    assert damage_change["amount"] == 5
    assert damage_change["applied"] == 5
    assert damage_change["evasion"]["saving_throw_success"] is False
    assert damage_change["evasion"]["amount_after_evasion"] == 5
    assert state.encounter.combatants["pc1"].hp_current == 5


def test_monk_evasion_does_not_apply_to_non_dex_save(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"monk": 7}
    action = ActionDefinition(
        id="test.con_save_half_damage",
        name="Con Save Half Damage",
        localization={"en": "Con Save Half Damage", "zh": "体质半伤", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={"normal_ft": 5},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "saving_throw", "ability": "con", "difficulty_tier": "medium"},
            {"type": "damage", "amount": 10, "damage_type": "poison", "save_half": True},
        ],
    )

    result = AutomationExecutor(
        state,
        _FixedSingleDieRollService([13]),
        AuditLog(),
    ).execute(action, actor_id="goblin1", targets=["pc1"])

    damage_change = next(change for change in result.state_changes if change["type"] == "damage")
    assert result.node_results["automation[0]"]["success"] is True
    assert damage_change["amount"] == 5
    assert damage_change["applied"] == 5
    assert "evasion" not in damage_change
    assert state.encounter.combatants["pc1"].hp_current == 5


def test_monk_evasion_disabled_while_incapacitated(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"monk": 7}
    state.characters["pc1"].saving_throw_proficiencies = ["dex"]
    state.encounter.combatants["pc1"].status_effects.append(
        {"effect_id": "incapacitated-test", "condition": "incapacitated"}
    )
    action = ActionDefinition(
        id="test.dex_save_half_damage",
        name="Dex Save Half Damage",
        localization={"en": "Dex Save Half Damage", "zh": "敏捷半伤", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={"normal_ft": 5},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "saving_throw", "ability": "dex", "difficulty_tier": "medium"},
            {"type": "damage", "amount": 10, "damage_type": "fire", "save_half": True},
        ],
    )

    result = AutomationExecutor(
        state,
        _FixedSingleDieRollService([12]),
        AuditLog(),
    ).execute(action, actor_id="goblin1", targets=["pc1"])

    damage_change = next(change for change in result.state_changes if change["type"] == "damage")
    assert result.node_results["automation[0]"]["success"] is True
    assert damage_change["amount"] == 5
    assert damage_change["applied"] == 5
    assert "evasion" not in damage_change
    assert state.encounter.combatants["pc1"].hp_current == 5


def test_automation_ability_check_uses_backing_character_skill_proficiency(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].skill_proficiencies = ["stealth"]
    state.encounter.combatants["pc1"].abilities = {
        "str": 10,
        "dex": 10,
        "con": 10,
        "int": 10,
        "wis": 10,
        "cha": 10,
    }
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action("pc1", "srd.hide", [])

    check_node = result["node_results"]["automation[1]"]
    assert result["dice_rolls"][0]["expression"] == "1d20+2"
    assert check_node["skill"] == "stealth"
    assert check_node["proficient"] is True
    assert check_node["bonus"] == 2


def test_automation_ability_check_applies_skill_expertise(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].skill_proficiencies = ["stealth"]
    state.characters["pc1"].skill_expertise = ["stealth"]
    state.characters["pc1"].actions.append("srd.hide")
    state.encounter.combatants["pc1"].abilities = {
        "str": 10,
        "dex": 10,
        "con": 10,
        "int": 10,
        "wis": 10,
        "cha": 10,
    }
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action("pc1", "srd.hide", [])

    check_node = result["node_results"]["automation[1]"]
    assert result["dice_rolls"][0]["expression"] == "1d20+4"
    assert check_node["proficient"] is True
    assert check_node["proficiency_sources"] == ["skill:stealth", "feature:expertise:stealth"]
    assert check_node["bonus"] == 4


def test_automation_ability_check_applies_bard_jack_of_all_trades(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"bard": 2}
    state.characters["pc1"].skill_proficiencies = []
    state.characters["pc1"].actions.append("srd.hide")
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action("pc1", "srd.hide", [])

    check_node = result["node_results"]["automation[1]"]
    assert result["dice_rolls"][0]["expression"] == "1d20+3"
    assert check_node["proficient"] is False
    assert check_node["proficiency_sources"] == ["feature:jack_of_all_trades"]
    assert check_node["bonus"] == 3


def test_automation_ability_check_applies_cleric_thaumaturge(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"cleric": 1}
    state.characters["pc1"].feature_choices = {"cleric.divine_order": "thaumaturge"}
    state.characters["pc1"].abilities["int"] = 10
    state.characters["pc1"].abilities["wis"] = 16
    action = ActionDefinition(
        id="test.arcana_check",
        name="Arcana Check",
        localization={"en": "Arcana Check", "zh": "奥秘检定", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={"self": True},
        target_policy={"min": 0, "max": 0, "self": True, "harmful": False},
        automation=[
            {
                "type": "ability_check",
                "ability": "int",
                "skill": "arcana",
                "difficulty_tier": "medium",
            }
        ],
    )

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="pc1",
        targets=[],
    )

    check_node = result.node_results["automation[0]"]
    assert result.dice_rolls[0]["expression"] == "1d20+3"
    assert check_node["proficient"] is False
    assert check_node["proficiency_sources"] == ["feature:divine_order_thaumaturge"]
    assert check_node["bonus"] == 3


def test_automation_ability_check_applies_druid_magician(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"druid": 1}
    state.characters["pc1"].feature_choices = {"druid.primal_order": "magician"}
    state.characters["pc1"].abilities["int"] = 10
    state.characters["pc1"].abilities["wis"] = 16
    action = ActionDefinition(
        id="test.nature_check",
        name="Nature Check",
        localization={"en": "Nature Check", "zh": "自然检定", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={"self": True},
        target_policy={"min": 0, "max": 0, "self": True, "harmful": False},
        automation=[
            {
                "type": "ability_check",
                "ability": "int",
                "skill": "nature",
                "difficulty_tier": "medium",
            }
        ],
    )

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="pc1",
        targets=[],
    )

    check_node = result.node_results["automation[0]"]
    assert result.dice_rolls[0]["expression"] == "1d20+3"
    assert check_node["proficient"] is False
    assert check_node["proficiency_sources"] == ["feature:primal_order_magician"]
    assert check_node["bonus"] == 3


def test_automation_ability_check_primal_knowledge_uses_strength_while_raging(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"barbarian": 3}
    state.encounter.combatants["pc1"].status_effects.append(
        {
            "effect_id": "rage-test",
            "condition": "raging",
            "source_action_id": "srd.rage",
            "passive_modifiers": {"ability_check_advantage_abilities": ["str"]},
        }
    )
    action = ActionDefinition(
        id="test.primal_knowledge_check",
        name="Primal Knowledge Check",
        localization={"en": "Primal Knowledge Check", "zh": "原初知识检定", "aliases": []},
        source="test",
        rules_version="test",
        action_type="class_feature",
        action_economy="none",
        range={"self": True},
        target_policy={"min": 0, "max": 0, "self": True, "harmful": False},
        automation=[
            {
                "type": "ability_check",
                "ability": "dex",
                "skill": "stealth",
                "difficulty_tier": "medium",
            }
        ],
    )

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="pc1",
        params={"use_primal_knowledge": True},
    )

    check_node = result.node_results["automation[0]"]
    assert check_node["ability"] == "str"
    assert check_node["original_ability"] == "dex"
    assert check_node["bonus"] == 3
    assert check_node["status_advantage"] == "advantage"
    assert check_node["primal_knowledge"] == {
        "feature": "primal_knowledge",
        "skill": "stealth",
        "original_ability": "dex",
        "ability": "str",
    }
    assert result.dice_rolls[0]["expression"] == "1d20+3"
    assert result.dice_rolls[0]["advantage"] == "advantage"


def test_automation_ability_check_remarkable_athlete_advantages_athletics(
    make_state,
) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"fighter": 3}
    state.characters["pc1"].subclasses = {"fighter": "champion"}
    action = ActionDefinition(
        id="test.remarkable_athlete_check",
        name="Remarkable Athlete Check",
        localization={"en": "Remarkable Athlete Check", "zh": "卓越运动员检定", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={"self": True},
        target_policy={"min": 0, "max": 0, "harmful": False},
        automation=[
            {
                "type": "ability_check",
                "ability": "str",
                "skill": "athletics",
                "difficulty_tier": "medium",
            }
        ],
    )

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="pc1",
    )

    check_node = result.node_results["automation[0]"]
    assert check_node["status_advantage"] == "advantage"
    assert check_node["status_sources"][0]["modifier"] == "remarkable_athlete"
    assert check_node["status_sources"][0]["source_action_id"] == "srd.remarkable_athlete"
    assert result.dice_rolls[0]["advantage"] == "advantage"


def test_automation_ability_check_tactical_mind_spends_second_wind_on_success(
    make_state,
) -> None:
    state = make_state()
    state.rng_seed = 1
    state.characters["pc1"].class_levels = {"fighter": 2}
    state.characters["pc1"].resources["srd.resource.second_wind"] = 1
    action = ActionDefinition(
        id="test.tactical_mind_check",
        name="Tactical Mind Check",
        localization={"en": "Tactical Mind Check", "zh": "战术头脑检定", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={"self": True},
        target_policy={"min": 0, "max": 0, "harmful": False},
        automation=[{"type": "ability_check", "ability": "dex", "difficulty_tier": "hard"}],
    )

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="pc1",
        params={"use_tactical_mind": True},
    )

    check_node = result.node_results["automation[0]"]
    assert result.dice_rolls[0]["total"] == 18
    assert result.dice_rolls[1]["expression"] == "1d10"
    assert check_node["tactical_mind"]["roll_total"] == 8
    assert check_node["total"] == 26
    assert check_node["success"] is True
    assert state.characters["pc1"].resources["srd.resource.second_wind"] == 0
    assert any(
        change["type"] == "tactical_mind"
        and change["resource"] == "srd.resource.second_wind"
        and change["after"] == 0
        for change in result.state_changes
    )


def test_lesser_restoration_removes_core_conditions(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    pc2 = state.encounter.combatants["pc2"]
    pc2.status_effects.extend(
        [
            {"effect_id": "e1", "condition": "poisoned", "source_action_id": "test"},
            {"effect_id": "e2", "condition": "prone", "source_action_id": "test"},
        ]
    )
    state.characters["pc1"].spell_slots["2"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell("pc1", "srd.lesser_restoration", ["pc2"], 2)

    assert result["success"] is True
    assert {effect["condition"] for effect in pc2.status_effects} == {"prone"}
    assert any(change["type"] == "remove_condition" for change in result["state_changes"])


def test_aid_increases_hp_max_and_current_hp(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    pc2 = state.encounter.combatants["pc2"]
    state.characters["pc1"].spell_slots["2"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell("pc1", "srd.aid", ["pc2"], 2)

    assert result["success"] is True
    assert pc2.hp_max == 13
    assert pc2.hp_current == 9
    assert any(change["type"] == "max_hp_delta" for change in result["state_changes"])


def test_greater_invisibility_applies_concentration_invisible_without_attack_break(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"bard": 7}
    state.characters["pc1"].spell_slots["4"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell(
        "pc1",
        "srd.greater_invisibility",
        ["pc1"],
        4,
        idempotency_key="cast-greater-invisibility",
    )

    assert result["success"] is True
    assert state.characters["pc1"].spell_slots["4"] == 0
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.greater_invisibility"
    assert effect["condition"] == "invisible"
    assert effect["duration"] == {"until": "concentration_1_minute"}
    assert effect["tick_on"] == "target_turn_start"
    assert effect["concentration"] is True

    tools.economy.set("pc1", "action", 1)
    attack = tools.attack(
        "pc1",
        "goblin1",
        "srd.shortsword_attack",
        idempotency_key="greater-invisibility-attack",
    )

    assert attack["success"] is True
    assert any(
        active.get("source_action_id") == "srd.greater_invisibility"
        and active.get("condition") == "invisible"
        for active in state.encounter.combatants["pc1"].status_effects
    )
    assert not [
        change
        for change in attack["state_changes"]
        if change.get("type") == "effect_expired"
        and any(
            removed.get("source_action_id") == "srd.greater_invisibility"
            for removed in change.get("removed", [])
        )
    ]

    lifecycle = tick_effects(state, trigger="target_turn_start", actor_id="pc1")
    assert lifecycle.ticked[0]["remaining_ticks_before"] == 10
    assert lifecycle.ticked[0]["remaining_ticks_after"] == 9


@pytest.mark.parametrize(
    ("class_name", "ability", "dc_source"),
    [
        ("druid", "wis", "spell_save_dc:druid"),
        ("sorcerer", "cha", "spell_save_dc:sorcerer"),
        ("wizard", "int", "spell_save_dc:wizard"),
    ],
)
def test_ice_storm_uses_allowed_class_spell_dc_and_halves_both_damage_types(
    make_state,
    class_name: str,
    ability: str,
    dc_source: str,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {class_name: 9}
    caster.abilities[ability] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["4"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"dex": 10}
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([20, 10, 6]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.ice_storm",
        ["goblin1"],
        4,
        idempotency_key=f"cast-ice-storm-{class_name}",
    )

    assert result["success"] is True
    assert caster.spell_slots["4"] == 0
    save_node = result["node_results"]["automation[1]"]
    assert save_node["dc"] == 16
    assert save_node["dc_source"] == dc_source
    assert save_node["success"] is True
    damage_changes = [change for change in result["state_changes"] if change["type"] == "damage"]
    assert [change["damage_type"] for change in damage_changes] == ["bludgeoning", "cold"]
    assert [change["amount"] for change in damage_changes] == [5, 3]
    assert [change["applied"] for change in damage_changes] == [5, 3]
    assert [roll["expression"] for roll in result["dice_rolls"]] == [
        "1d20+0",
        "2d10",
        "4d6",
    ]
    effect = state.world.active_effects[-1]
    assert effect["effect_type"] == "difficult_terrain"
    assert effect["scope"] == {"shape": "cylinder", "radius_ft": 20, "height_ft": 40}
    assert effect["duration"] == {"until": "end_of_next_turn"}
    assert effect["metadata"] == {
        "ground_in_cylinder": True,
        "source": "hailstones",
    }


def test_ice_storm_upcast_adds_only_bludgeoning_damage_die(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"druid": 9}
    caster.abilities["wis"] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["4"] = 0
    caster.spell_slots["5"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"dex": 10}
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1, 10, 6]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.ice_storm",
        ["goblin1"],
        5,
        idempotency_key="cast-ice-storm-upcast",
    )

    assert result["success"] is True
    assert caster.spell_slots["4"] == 0
    assert caster.spell_slots["5"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_5"
    assert cost_change["base_spell_slot_level"] == 4
    assert cost_change["spell_slot_level"] == 5
    damage_changes = [change for change in result["state_changes"] if change["type"] == "damage"]
    assert [change["damage_type"] for change in damage_changes] == ["bludgeoning", "cold"]
    assert [change["amount"] for change in damage_changes] == [10, 6]
    assert [roll["expression"] for roll in result["dice_rolls"]] == [
        "1d20+0",
        "3d10",
        "4d6",
    ]


def test_blight_uses_actor_spell_dc_and_plant_auto_fails_save(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"druid": 7}
    caster.abilities["wis"] = 16
    caster.proficiency_bonus = 3
    caster.spell_slots["4"] = 1
    target = state.encounter.combatants["goblin1"]
    target.creature_type = "plant"
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell(
        "pc1",
        "srd.blight",
        ["goblin1"],
        4,
        idempotency_key="cast-blight-plant",
    )

    assert result["success"] is True
    assert caster.spell_slots["4"] == 0
    save_node = result["node_results"]["automation[1]"]
    assert save_node["dc"] == 14
    assert save_node["dc_source"] == "spell_save_dc:druid"
    assert save_node["auto_failed"] is True
    assert save_node["status_sources"][0] == {
        "kind": "auto_fail",
        "modifier": "auto_fail_creature_types",
        "creature_type": "plant",
    }
    assert [roll["expression"] for roll in result["dice_rolls"]] == ["8d8"]
    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert damage_change["damage_type"] == "necrotic"
    assert damage_change["amount"] == damage_change["applied"]


def test_blight_upcast_spends_requested_slot_and_adds_damage_die(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"druid": 7}
    caster.abilities["wis"] = 16
    caster.proficiency_bonus = 3
    caster.spell_slots["4"] = 0
    caster.spell_slots["5"] = 1
    target = state.encounter.combatants["goblin1"]
    target.creature_type = "plant"
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell(
        "pc1",
        "srd.blight",
        ["goblin1"],
        5,
        idempotency_key="cast-blight-upcast",
    )

    assert result["success"] is True
    assert caster.spell_slots["4"] == 0
    assert caster.spell_slots["5"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_5"
    assert cost_change["base_spell_slot_level"] == 4
    assert cost_change["spell_slot_level"] == 5
    assert [roll["expression"] for roll in result["dice_rolls"]] == ["9d8"]


@pytest.mark.parametrize(
    ("class_name", "ability", "dc_source"),
    [
        ("druid", "wis", "spell_save_dc:druid"),
        ("sorcerer", "cha", "spell_save_dc:sorcerer"),
        ("wizard", "int", "spell_save_dc:wizard"),
    ],
)
def test_cone_of_cold_uses_allowed_class_spell_dc_and_half_damage_on_success(
    make_state,
    class_name: str,
    ability: str,
    dc_source: str,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {class_name: 9}
    caster.abilities[ability] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["5"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"con": 10}
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([20, 8]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.cone_of_cold",
        ["goblin1"],
        5,
        idempotency_key=f"cast-cone-of-cold-{class_name}",
    )

    assert result["success"] is True
    assert caster.spell_slots["5"] == 0
    save_node = result["node_results"]["automation[1]"]
    assert save_node["dc"] == 16
    assert save_node["dc_source"] == dc_source
    assert save_node["success"] is True
    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert damage_change["damage_type"] == "cold"
    assert damage_change["amount"] == 4
    assert damage_change["applied"] == 4
    assert [roll["expression"] for roll in result["dice_rolls"]] == ["1d20+0", "8d8"]
    assert result["messages"] == [
        "A creature killed by Cone of Cold becomes a frozen statue until it thaws."
    ]


def test_cone_of_cold_upcast_spends_requested_slot_and_adds_damage_die(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"druid": 11}
    caster.abilities["wis"] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["5"] = 0
    caster.spell_slots["6"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"con": 10}
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1, 8]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.cone_of_cold",
        ["goblin1"],
        6,
        idempotency_key="cast-cone-of-cold-upcast",
    )

    assert result["success"] is True
    assert caster.spell_slots["5"] == 0
    assert caster.spell_slots["6"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_6"
    assert cost_change["base_spell_slot_level"] == 5
    assert cost_change["spell_slot_level"] == 6
    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert damage_change["damage_type"] == "cold"
    assert damage_change["amount"] == 8
    assert [roll["expression"] for roll in result["dice_rolls"]] == ["1d20+0", "9d8"]


def test_flame_strike_uses_cleric_spell_dc_and_halves_both_damage_types(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"cleric": 9}
    caster.abilities["wis"] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["5"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"dex": 10}
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([20, 6, 4]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.flame_strike",
        ["goblin1"],
        5,
        idempotency_key="cast-flame-strike",
    )

    assert result["success"] is True
    assert caster.spell_slots["5"] == 0
    save_node = result["node_results"]["automation[1]"]
    assert save_node["dc"] == 16
    assert save_node["dc_source"] == "spell_save_dc:cleric"
    assert save_node["success"] is True
    damage_changes = [change for change in result["state_changes"] if change["type"] == "damage"]
    assert [change["damage_type"] for change in damage_changes] == ["fire", "radiant"]
    assert [change["amount"] for change in damage_changes] == [3, 2]
    assert [change["applied"] for change in damage_changes] == [3, 2]
    assert [roll["expression"] for roll in result["dice_rolls"]] == ["1d20+0", "5d6", "5d6"]


def test_flame_strike_upcast_adds_dice_to_fire_and_radiant_damage(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"cleric": 11}
    caster.abilities["wis"] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["5"] = 0
    caster.spell_slots["6"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"dex": 10}
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1, 6, 6]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.flame_strike",
        ["goblin1"],
        6,
        idempotency_key="cast-flame-strike-upcast",
    )

    assert result["success"] is True
    assert caster.spell_slots["5"] == 0
    assert caster.spell_slots["6"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_6"
    assert cost_change["base_spell_slot_level"] == 5
    assert cost_change["spell_slot_level"] == 6
    save_node = result["node_results"]["automation[1]"]
    assert save_node["dc"] == 16
    assert save_node["dc_source"] == "spell_save_dc:cleric"
    assert save_node["success"] is False
    damage_changes = [change for change in result["state_changes"] if change["type"] == "damage"]
    assert [change["damage_type"] for change in damage_changes] == ["fire", "radiant"]
    assert [change["amount"] for change in damage_changes] == [6, 6]
    assert [roll["expression"] for roll in result["dice_rolls"]] == ["1d20+0", "6d6", "6d6"]


def test_harm_uses_cleric_spell_dc_and_half_damage_on_success(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"cleric": 11}
    caster.abilities["wis"] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["6"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"con": 10}
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([20, 8]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.harm",
        ["goblin1"],
        6,
        idempotency_key="cast-harm-success",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    save_node = result["node_results"]["automation[1]"]
    assert save_node["dc"] == 16
    assert save_node["dc_source"] == "spell_save_dc:cleric"
    assert save_node["success"] is True
    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert damage_change["damage_type"] == "necrotic"
    assert damage_change["amount"] == 4
    assert damage_change["applied"] == 4
    assert target.hp_current == 76
    assert target.hp_max == 80
    assert not any(change["type"] == "max_hp_delta" for change in result["state_changes"])
    assert target.status_effects == []
    assert [roll["expression"] for roll in result["dice_rolls"]] == ["1d20+0", "14d6"]


def test_harm_failed_save_reduces_hp_max_not_below_one_and_marks_reduction(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"cleric": 11}
    caster.abilities["wis"] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["5"] = 1
    caster.spell_slots["6"] = 1
    caster.gold = 100
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"con": 10}
    target.hp_current = 5
    target.hp_max = 5
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1, 8]),
    )

    harm_result = tools.cast_spell(
        "pc1",
        "srd.harm",
        ["goblin1"],
        6,
        idempotency_key="cast-harm-failed-save",
    )

    assert harm_result["success"] is True
    save_node = harm_result["node_results"]["automation[1]"]
    assert save_node["dc"] == 16
    assert save_node["dc_source"] == "spell_save_dc:cleric"
    assert save_node["success"] is False
    damage_change = next(
        change for change in harm_result["state_changes"] if change["type"] == "damage"
    )
    assert damage_change["amount"] == 8
    assert damage_change["applied"] == 5
    max_hp_change = next(
        change for change in harm_result["state_changes"] if change["type"] == "max_hp_delta"
    )
    assert max_hp_change["amount"] == -8
    assert max_hp_change["hp_max_before"] == 5
    assert max_hp_change["hp_max_after"] == 1
    assert max_hp_change["hp_max_reduction"] == 4
    assert target.hp_current == 0
    assert target.hp_max == 1
    marker = target.status_effects[-1]
    assert marker["effect_markers"] == ["hp_max_reduction"]
    assert marker["metadata"] == {"hp_max_reduction": 4}

    tools.economy.set("pc1", "action", 1)
    restoration_result = tools.perform_action(
        "pc1",
        "srd.greater_restoration",
        ["goblin1"],
        {"slot_level": 5, "greater_restoration_choice": "hp_max_reduction"},
        idempotency_key="greater-restoration-after-harm",
    )

    greater_restore = next(
        change
        for change in restoration_result["state_changes"]
        if change["type"] == "greater_restoration"
    )
    assert greater_restore["removed_markers"] == {"hp_max_reduction": 1}
    assert greater_restore["hp_max_restored"] == [
        {
            "owner_type": "combatant",
            "owner_id": "goblin1",
            "amount": 4,
            "hp_max_before": 1,
            "hp_max_after": 5,
            "hp_current_before": 0,
            "hp_current_after": 0,
        }
    ]
    assert target.hp_max == 5
    assert target.status_effects == []


@pytest.mark.parametrize(
    ("class_name", "ability", "dc_source"),
    [
        ("sorcerer", "cha", "spell_save_dc:sorcerer"),
        ("wizard", "int", "spell_save_dc:wizard"),
    ],
)
def test_chain_lightning_uses_allowed_class_spell_dc_and_half_damage_on_success(
    make_state,
    class_name: str,
    ability: str,
    dc_source: str,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {class_name: 11}
    caster.abilities[ability] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["6"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"dex": 10}
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([20, 8]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.chain_lightning",
        ["goblin1"],
        6,
        idempotency_key=f"cast-chain-lightning-{class_name}",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    save_node = result["node_results"]["automation[1]"]
    assert save_node["dc"] == 16
    assert save_node["dc_source"] == dc_source
    assert save_node["success"] is True
    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert damage_change["damage_type"] == "lightning"
    assert damage_change["amount"] == 4
    assert damage_change["applied"] == 4
    assert [roll["expression"] for roll in result["dice_rolls"]] == ["1d20+0", "10d8"]


def test_chain_lightning_upcast_adds_one_target_per_slot_above_six(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"wizard": 13}
    caster.abilities["int"] = 18
    caster.proficiency_bonus = 5
    caster.spell_slots["6"] = 1
    caster.spell_slots["7"] = 1
    target_ids = ["goblin1", "goblin2", "goblin3", "goblin4", "goblin5"]
    for index, target_id in enumerate(target_ids, start=1):
        if target_id not in state.encounter.combatants:
            state.encounter.combatants[target_id] = Combatant(
                id=target_id,
                entity_id=target_id,
                name=f"Chain Target {index}",
                side="monsters",
                hp_current=80,
                hp_max=80,
                armor_class=12,
            )
        target = state.encounter.combatants[target_id]
        target.abilities = {"dex": 10}
        target.hp_current = 80
        target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()

    with pytest.raises(AutomationError, match="too many targets"):
        EngineTools(state, compendium, AuditLog()).cast_spell(
            "pc1",
            "srd.chain_lightning",
            target_ids,
            6,
            idempotency_key="cast-chain-lightning-too-many-base",
        )

    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1, 1, 1, 1, 1, 8, 8, 8, 8, 8]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.chain_lightning",
        target_ids,
        7,
        idempotency_key="cast-chain-lightning-upcast",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 1
    assert caster.spell_slots["7"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_7"
    assert cost_change["base_spell_slot_level"] == 6
    assert cost_change["spell_slot_level"] == 7
    damage_changes = [change for change in result["state_changes"] if change["type"] == "damage"]
    assert [change["target_id"] for change in damage_changes] == target_ids
    assert [change["damage_type"] for change in damage_changes] == ["lightning"] * 5
    assert [change["amount"] for change in damage_changes] == [8, 8, 8, 8, 8]
    assert [roll["expression"] for roll in result["dice_rolls"]] == [
        "1d20+0",
        "1d20+0",
        "1d20+0",
        "1d20+0",
        "1d20+0",
        "10d8",
        "10d8",
        "10d8",
        "10d8",
        "10d8",
    ]


@pytest.mark.parametrize(
    ("class_name", "ability", "dc_source"),
    [
        ("sorcerer", "cha", "spell_save_dc:sorcerer"),
        ("wizard", "int", "spell_save_dc:wizard"),
    ],
)
def test_disintegrate_uses_allowed_class_spell_dc_and_no_damage_on_success(
    make_state,
    class_name: str,
    ability: str,
    dc_source: str,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {class_name: 11}
    caster.abilities[ability] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["6"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"dex": 10}
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([20]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.disintegrate",
        ["goblin1"],
        6,
        idempotency_key=f"cast-disintegrate-{class_name}",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    save_node = result["node_results"]["automation[1]"]
    assert save_node["dc"] == 16
    assert save_node["dc_source"] == dc_source
    assert save_node["success"] is True
    assert [change for change in result["state_changes"] if change["type"] == "damage"] == []
    assert target.hp_current == 80
    assert [roll["expression"] for roll in result["dice_rolls"]] == ["1d20+0"]
    assert result["messages"] == ["The target succeeds; Disintegrate deals no damage."]


def test_disintegrate_upcast_adds_three_damage_dice_and_records_srd_aftermath(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"wizard": 13}
    caster.abilities["int"] = 18
    caster.proficiency_bonus = 5
    caster.spell_slots["6"] = 0
    caster.spell_slots["7"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"dex": 10}
    target.hp_current = 50
    target.hp_max = 50
    compendium = CompendiumLoader("rules_data").load()
    action = compendium.action("srd.disintegrate")
    assert action.properties["zero_hp_disintegrates_target_and_nonmagical_worn_carried"] is True
    assert action.properties["revival_only_by"] == ["True Resurrection", "Wish"]
    assert (
        action.properties["auto_disintegrates_large_or_smaller_nonmagical_object_or_magical_force"]
        is True
    )
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1, 8, 8]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.disintegrate",
        ["goblin1"],
        7,
        idempotency_key="cast-disintegrate-upcast",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    assert caster.spell_slots["7"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_7"
    assert cost_change["base_spell_slot_level"] == 6
    assert cost_change["spell_slot_level"] == 7
    save_node = result["node_results"]["automation[1]"]
    assert save_node["dc"] == 17
    assert save_node["dc_source"] == "spell_save_dc:wizard"
    assert save_node["success"] is False
    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert damage_change["damage_type"] == "force"
    assert damage_change["amount"] == 56
    assert damage_change["applied"] == 50
    assert target.hp_current == 0
    assert [roll["expression"] for roll in result["dice_rolls"]] == [
        "1d20+0",
        "10d6+40+3d6",
    ]
    assert result["messages"] == [
        "If this damage reduces the target to 0 HP, apply the SRD disintegration aftermath."
    ]


def test_circle_of_death_uses_actor_spell_dc_and_deals_necrotic_area_damage(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"warlock": 11}
    caster.abilities["cha"] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["6"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"con": 10}
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([20, 8]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.circle_of_death",
        ["goblin1"],
        6,
        idempotency_key="cast-circle-of-death",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    save_node = result["node_results"]["automation[1]"]
    assert save_node["dc"] == 16
    assert save_node["dc_source"] == "spell_save_dc:warlock"
    assert save_node["success"] is True
    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert damage_change["damage_type"] == "necrotic"
    assert damage_change["amount"] == 4
    assert damage_change["applied"] == 4
    assert [roll["expression"] for roll in result["dice_rolls"]] == ["1d20+0", "8d8"]


def test_circle_of_death_upcast_spends_requested_slot_and_adds_two_damage_dice(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"sorcerer": 11}
    caster.abilities["cha"] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["6"] = 0
    caster.spell_slots["7"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"con": 10}
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1, 8]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.circle_of_death",
        ["goblin1"],
        7,
        idempotency_key="cast-circle-of-death-upcast",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    assert caster.spell_slots["7"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_7"
    assert cost_change["base_spell_slot_level"] == 6
    assert cost_change["spell_slot_level"] == 7
    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert damage_change["damage_type"] == "necrotic"
    assert damage_change["amount"] == 8
    assert [roll["expression"] for roll in result["dice_rolls"]] == ["1d20+0", "10d8"]


@pytest.mark.parametrize(
    ("class_name", "ability", "dc_source"),
    [
        ("sorcerer", "cha", "spell_save_dc:sorcerer"),
        ("warlock", "cha", "spell_save_dc:warlock"),
        ("wizard", "int", "spell_save_dc:wizard"),
    ],
)
def test_finger_of_death_uses_allowed_class_spell_dc_and_half_damage_on_success(
    make_state,
    class_name: str,
    ability: str,
    dc_source: str,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {class_name: 13}
    caster.abilities[ability] = 18
    caster.proficiency_bonus = 5
    caster.spell_slots["7"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"con": 10}
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([20, 8]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.finger_of_death",
        ["goblin1"],
        7,
        idempotency_key=f"cast-finger-of-death-{class_name}",
    )

    assert result["success"] is True
    assert caster.spell_slots["7"] == 0
    save_node = result["node_results"]["automation[1]"]
    assert save_node["dc"] == 17
    assert save_node["dc_source"] == dc_source
    assert save_node["success"] is True
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_7"
    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert damage_change["damage_type"] == "necrotic"
    assert damage_change["amount"] == 19
    assert damage_change["applied"] == 19
    assert [roll["expression"] for roll in result["dice_rolls"]] == ["1d20+0", "7d8+30"]


def test_finger_of_death_records_srd_zombie_result_for_killed_humanoid(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"wizard": 13}
    caster.abilities["int"] = 18
    caster.proficiency_bonus = 5
    caster.spell_slots["7"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"con": 10}
    target.creature_type = "humanoid"
    target.hp_current = 35
    target.hp_max = 35
    compendium = CompendiumLoader("rules_data").load()
    action = compendium.action("srd.finger_of_death")
    assert action.properties["humanoid_killed_rises_as"] == "srd.zombie"
    assert action.properties["humanoid_killed_rises_at"] == "start_of_caster_next_turn"
    assert action.properties["zombie_follows_verbal_orders"] is True
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1, 8]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.finger_of_death",
        ["goblin1"],
        7,
        idempotency_key="cast-finger-of-death-kill",
    )

    assert result["success"] is True
    assert caster.spell_slots["7"] == 0
    assert target.hp_current == 0
    save_node = result["node_results"]["automation[1]"]
    assert save_node["dc"] == 17
    assert save_node["dc_source"] == "spell_save_dc:wizard"
    assert save_node["success"] is False
    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert damage_change["damage_type"] == "necrotic"
    assert damage_change["amount"] == 38
    assert damage_change["applied"] == 35
    assert result["messages"] == [
        "If a Humanoid is killed by this spell, it rises at the start of the caster's next turn "
        "as a Zombie that follows the caster's verbal orders."
    ]


def test_fire_storm_uses_actor_spell_dc_and_records_srd_area_metadata(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"cleric": 13}
    caster.abilities["wis"] = 18
    caster.proficiency_bonus = 5
    caster.spell_slots["7"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"dex": 10}
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([20, 10]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.fire_storm",
        ["goblin1"],
        7,
        idempotency_key="cast-fire-storm",
    )

    assert result["success"] is True
    assert caster.spell_slots["7"] == 0
    save_node = result["node_results"]["automation[1]"]
    assert save_node["dc"] == 17
    assert save_node["dc_source"] == "spell_save_dc:cleric"
    assert save_node["success"] is True
    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert damage_change["damage_type"] == "fire"
    assert damage_change["amount"] == 5
    assert damage_change["applied"] == 5
    assert [roll["expression"] for roll in result["dice_rolls"]] == ["1d20+0", "7d10"]
    assert result["messages"] == [
        "The fire storm uses up to ten contiguous 10-foot cubes; "
        "flammable objects not worn or carried in the area start burning."
    ]


@pytest.mark.parametrize(
    ("class_name", "ability", "dc_source"),
    [
        ("sorcerer", "cha", "spell_save_dc:sorcerer"),
        ("wizard", "int", "spell_save_dc:wizard"),
    ],
)
def test_meteor_swarm_uses_allowed_class_spell_dc_and_halves_both_damage_types(
    make_state,
    class_name: str,
    ability: str,
    dc_source: str,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {class_name: 17}
    caster.abilities[ability] = 20
    caster.proficiency_bonus = 6
    caster.spell_slots["9"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"dex": 10}
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([20, 6, 4]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.meteor_swarm",
        ["goblin1"],
        9,
        idempotency_key=f"cast-meteor-swarm-{class_name}",
    )

    assert result["success"] is True
    assert caster.spell_slots["9"] == 0
    save_node = result["node_results"]["automation[1]"]
    assert save_node["dc"] == 19
    assert save_node["dc_source"] == dc_source
    assert save_node["success"] is True
    damage_changes = [change for change in result["state_changes"] if change["type"] == "damage"]
    assert [change["damage_type"] for change in damage_changes] == ["fire", "bludgeoning"]
    assert [change["amount"] for change in damage_changes] == [3, 2]
    assert [change["applied"] for change in damage_changes] == [3, 2]
    assert [roll["expression"] for roll in result["dice_rolls"]] == [
        "1d20+0",
        "20d6",
        "20d6",
    ]


def test_mass_cure_wounds_uses_actor_spellcasting_modifier_for_each_target(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"cleric": 9}
    caster.abilities["wis"] = 18
    caster.spell_slots["5"] = 1
    caster.hp_current = 1
    caster.hp_max = 20
    ally = state.characters["pc2"]
    ally.hp_current = 2
    ally.hp_max = 20
    state.encounter.combatants["pc1"].hp_current = 1
    state.encounter.combatants["pc1"].hp_max = 20
    state.encounter.combatants["pc2"].hp_current = 2
    state.encounter.combatants["pc2"].hp_max = 20
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell(
        "pc1",
        "srd.mass_cure_wounds",
        ["pc1", "pc2"],
        5,
        idempotency_key="cast-mass-cure-wounds",
    )

    assert result["success"] is True
    assert caster.spell_slots["5"] == 0
    rolls = [roll for roll in result["dice_rolls"] if roll["expression"] == "5d8"]
    assert len(rolls) == 2
    healing_changes = [change for change in result["state_changes"] if change["type"] == "healing"]
    assert [change["target_id"] for change in healing_changes] == ["pc1", "pc2"]
    for change, roll in zip(healing_changes, rolls, strict=True):
        assert change["amount"] == roll["total"] + 4


def test_mass_cure_wounds_upcast_spends_requested_slot_and_adds_healing_die(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"cleric": 9}
    caster.abilities["wis"] = 18
    caster.spell_slots["5"] = 0
    caster.spell_slots["6"] = 1
    ally = state.characters["pc2"]
    ally.hp_current = 2
    ally.hp_max = 20
    state.encounter.combatants["pc2"].hp_current = 2
    state.encounter.combatants["pc2"].hp_max = 20
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell(
        "pc1",
        "srd.mass_cure_wounds",
        ["pc2"],
        6,
        idempotency_key="cast-mass-cure-wounds-upcast",
    )

    assert result["success"] is True
    assert caster.spell_slots["5"] == 0
    assert caster.spell_slots["6"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_6"
    assert cost_change["base_spell_slot_level"] == 5
    assert cost_change["spell_slot_level"] == 6
    assert [roll["expression"] for roll in result["dice_rolls"]] == ["6d8"]
    healing_change = next(
        change for change in result["state_changes"] if change["type"] == "healing"
    )
    assert healing_change["amount"] == result["dice_rolls"][0]["total"] + 4


def test_heal_restores_70_hp_and_removes_srd_conditions(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"cleric": 11}
    caster.spell_slots["6"] = 1
    target = state.encounter.combatants["pc2"]
    target.hp_current = 4
    target.hp_max = 100
    target.status_effects = [
        {"effect_id": "blind", "condition": "blinded"},
        {"effect_id": "deaf", "condition": "deafened"},
        {"effect_id": "poison", "condition": "poisoned"},
        {"effect_id": "fright", "condition": "frightened"},
    ]
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell(
        "pc1",
        "srd.heal",
        ["pc2"],
        6,
        idempotency_key="cast-heal",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    healing_change = next(
        change for change in result["state_changes"] if change["type"] == "healing"
    )
    assert healing_change["amount"] == 70
    assert healing_change["applied"] == 70
    assert target.hp_current == 74
    condition_change = next(
        change for change in result["state_changes"] if change["type"] == "remove_condition"
    )
    assert condition_change["removed"] == {
        "blinded": 1,
        "deafened": 1,
        "poisoned": 1,
    }
    assert [effect["condition"] for effect in target.status_effects] == ["frightened"]


def test_heal_upcast_increases_healing_by_10_per_slot_above_six(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"druid": 13}
    caster.spell_slots["6"] = 0
    caster.spell_slots["7"] = 1
    target = state.encounter.combatants["pc2"]
    target.hp_current = 4
    target.hp_max = 100
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell(
        "pc1",
        "srd.heal",
        ["pc2"],
        7,
        idempotency_key="cast-heal-upcast",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    assert caster.spell_slots["7"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_7"
    assert cost_change["base_spell_slot_level"] == 6
    assert cost_change["spell_slot_level"] == 7
    healing_change = next(
        change for change in result["state_changes"] if change["type"] == "healing"
    )
    assert healing_change["amount"] == 80
    assert healing_change["applied"] == 80
    assert target.hp_current == 84


def test_hold_monster_uses_actor_spell_dc_and_repeat_save_duration(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"wizard": 9}
    caster.abilities["int"] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["5"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"wis": 8}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.hold_monster",
        ["goblin1"],
        5,
        idempotency_key="cast-hold-monster",
    )

    assert result["success"] is True
    assert caster.spell_slots["5"] == 0
    save_node = result["node_results"]["automation[1]"]
    assert save_node["dc"] == 16
    assert save_node["dc_source"] == "spell_save_dc:wizard"
    assert save_node["success"] is False
    effect = state.encounter.combatants["goblin1"].status_effects[-1]
    assert effect["condition"] == "paralyzed"
    assert effect["source_action_id"] == "srd.hold_monster"
    assert effect["duration"] == {
        "until": "concentration_1_minute",
        "repeat_save": {
            "ability": "wis",
            "dc": 16,
            "dc_source": "spell_save_dc:wizard",
            "end_on_success": True,
        },
    }
    assert effect["tick_on"] == "target_turn_end"
    assert effect["concentration"] is True

    lifecycle = tick_effects(
        state,
        trigger="target_turn_end",
        actor_id="goblin1",
        roll_service=_FixedSingleDieRollService([20]),
    )

    assert lifecycle.expired[0]["condition"] == "paralyzed"
    assert lifecycle.expired[0]["repeat_save"]["dc"] == 16
    assert lifecycle.expired[0]["repeat_save"]["success"] is True


def test_irresistible_dance_failed_save_charms_and_applies_combat_modifiers(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"wizard": 11}
    caster.abilities["int"] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["6"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"wis": 8, "dex": 14}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.irresistible_dance",
        ["goblin1"],
        6,
        idempotency_key="cast-irresistible-dance-fail",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    save_node = result["node_results"]["automation[1]"]
    assert save_node["dc"] == 16
    assert save_node["dc_source"] == "spell_save_dc:wizard"
    assert save_node["success"] is False
    effect = target.status_effects[-1]
    assert effect["condition"] == "charmed"
    assert effect["source_action_id"] == "srd.irresistible_dance"
    assert effect["passive_modifiers"] == {
        "must_spend_all_movement_dancing_in_place": True,
        "saving_throw_disadvantage_abilities": ["dex"],
        "attack_roll_disadvantage": True,
        "incoming_attack_advantage": True,
    }
    assert effect["duration"] == {
        "until": "concentration_1_minute",
        "repeat_save": {
            "ability": "wis",
            "dc": 16,
            "dc_source": "spell_save_dc:wizard",
            "end_on_success": True,
            "trigger": "target_action",
        },
    }
    assert effect["tick_on"] == "target_action"
    assert effect["concentration"] is True
    condition_change = next(
        change for change in result["state_changes"] if change["type"] == "condition"
    )
    assert condition_change["passive_modifiers"]["attack_roll_disadvantage"] is True

    attack = AutomationExecutor(
        state,
        _FixedSingleDieRollService([10, 3]),
        AuditLog(),
    ).execute(
        _weapon_attack_action(),
        actor_id="goblin1",
        targets=["pc2"],
    )

    attack_node = attack.node_results["automation[1]"]
    assert attack.dice_rolls[0]["advantage"] == "disadvantage"
    assert attack_node["status_advantage"] == "disadvantage"
    assert attack_node["status_sources"][0]["modifier"] == "attack_roll_disadvantage"

    incoming_attack = AutomationExecutor(
        state,
        _FixedSingleDieRollService([10, 3]),
        AuditLog(),
    ).execute(
        _weapon_attack_action(),
        actor_id="pc1",
        targets=["goblin1"],
    )

    incoming_attack_node = incoming_attack.node_results["automation[1]"]
    assert incoming_attack.dice_rolls[0]["advantage"] == "advantage"
    assert incoming_attack_node["status_advantage"] == "advantage"
    assert incoming_attack_node["status_sources"][0]["modifier"] == "incoming_attack_advantage"

    lifecycle = tick_effects(
        state,
        trigger="target_action",
        actor_id="goblin1",
        roll_service=_FixedSingleDieRollService([20]),
    )

    assert lifecycle.expired[0]["condition"] == "charmed"
    assert lifecycle.expired[0]["repeat_save"]["dc"] == 16
    assert lifecycle.expired[0]["repeat_save"]["success"] is True


def test_irresistible_dance_successful_save_applies_short_dance_only(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"bard": 11}
    caster.abilities["cha"] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["6"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"wis": 10}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([20]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.irresistible_dance",
        ["goblin1"],
        6,
        idempotency_key="cast-irresistible-dance-success",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    save_node = result["node_results"]["automation[1]"]
    assert save_node["dc"] == 16
    assert save_node["dc_source"] == "spell_save_dc:bard"
    assert save_node["success"] is True
    effect = target.status_effects[-1]
    assert effect["condition"] is None
    assert effect["source_action_id"] == "srd.irresistible_dance"
    assert effect["passive_modifiers"] == {
        "must_spend_all_movement_dancing_in_place": True,
    }
    assert effect["duration"] == {"until": "end_of_next_turn"}
    assert effect["tick_on"] == "target_turn_end"
    assert effect["concentration"] is True
    assert not any(change["type"] == "condition" for change in result["state_changes"])

    lifecycle = tick_effects(state, trigger="target_turn_end", actor_id="goblin1")
    assert lifecycle.expired[0]["source_action_id"] == "srd.irresistible_dance"
    assert target.status_effects == []


def test_mass_suggestion_charms_failed_targets_and_ends_on_applier_or_ally_damage(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"bard": 11}
    caster.abilities["cha"] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["6"] = 1
    state.encounter.combatants["goblin1"].abilities = {"wis": 10}
    state.encounter.combatants["goblin1"].hp_current = 20
    state.encounter.combatants["goblin1"].hp_max = 20
    state.encounter.combatants["goblin2"] = Combatant(
        id="goblin2",
        entity_id="goblin2",
        name="Goblin 2",
        side="monsters",
        hp_current=20,
        hp_max=20,
        armor_class=12,
        abilities={"wis": 10},
        position_node_id="cover",
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1, 20]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.mass_suggestion",
        ["goblin1", "goblin2"],
        6,
        idempotency_key="cast-mass-suggestion",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    assert [roll["expression"] for roll in result["dice_rolls"]] == ["1d20+0", "1d20+0"]
    save_node = result["node_results"]["automation[1]"]
    assert save_node["dc"] == 16
    assert save_node["dc_source"] == "spell_save_dc:bard"
    assert save_node["target_id"] == "goblin2"
    assert save_node["success"] is True
    condition_changes = [
        change
        for change in result["state_changes"]
        if change["type"] == "condition" and change["condition"] == "charmed"
    ]
    assert [change["target_id"] for change in condition_changes] == ["goblin1"]
    assert state.encounter.combatants["goblin2"].status_effects == []
    effect = state.encounter.combatants["goblin1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.mass_suggestion"
    assert effect["applied_by"] == "pc1"
    assert effect["condition"] == "charmed"
    assert effect["duration"] == {
        "until": "duration_24_hours_or_harmed",
        "break_on_damage": True,
        "break_on_damage_by": "applied_by_or_allies",
    }
    assert effect["passive_modifiers"] == {
        "compelled_suggestion": True,
        "mass_suggestion": True,
        "suggestion_word_limit": 25,
        "targets_must_hear_and_understand": True,
        "suggestion_must_sound_achievable": True,
        "suggestion_cannot_obviously_damage_targets_or_allies": True,
        "pursues_suggestion_to_best_ability": True,
        "ends_when_suggested_activity_completed": True,
    }
    assert effect["tick_on"] == "duration_or_damage"

    enemy_damage = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        _damage_action(1, damage_type="slashing"),
        actor_id="goblin2",
        targets=["goblin1"],
        idempotency_key="enemy-damages-mass-suggestion-target",
    )

    assert not [
        change for change in enemy_damage.state_changes if change.get("type") == "effect_expired"
    ]
    assert any(
        active_effect.get("condition") == "charmed"
        for active_effect in state.encounter.combatants["goblin1"].status_effects
    )
    ally_damage = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        _damage_action(1, damage_type="slashing"),
        actor_id="pc2",
        targets=["goblin1"],
        idempotency_key="ally-damages-mass-suggestion-target",
    )

    expiry = next(
        change for change in ally_damage.state_changes if change["type"] == "effect_expired"
    )
    assert expiry["trigger"] == "damage"
    assert expiry["removed"][0]["source_action_id"] == "srd.mass_suggestion"
    assert state.encounter.combatants["goblin1"].status_effects == []


def test_mass_suggestion_upcast_uses_longer_duration_from_slot(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"sorcerer": 13}
    caster.abilities["cha"] = 18
    caster.proficiency_bonus = 5
    caster.spell_slots["6"] = 0
    caster.spell_slots["7"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"wis": 10}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.mass_suggestion",
        ["goblin1"],
        7,
        idempotency_key="cast-mass-suggestion-upcast",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    assert caster.spell_slots["7"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_7"
    assert cost_change["base_spell_slot_level"] == 6
    assert cost_change["spell_slot_level"] == 7
    effect = target.status_effects[-1]
    assert effect["source_action_id"] == "srd.mass_suggestion"
    assert effect["condition"] == "charmed"
    assert effect["duration"] == {
        "until": "duration_10_days_or_harmed",
        "break_on_damage": True,
        "break_on_damage_by": "applied_by_or_allies",
    }


def test_hold_monster_rejects_extra_target_without_upcast_before_spending_slot(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"wizard": 9}
    caster.abilities["int"] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["5"] = 1
    state.encounter.combatants["goblin2"] = Combatant(
        id="goblin2",
        entity_id="goblin2",
        name="Goblin 2",
        side="monsters",
        hp_current=7,
        hp_max=7,
        armor_class=12,
        position_node_id="cover",
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="too many targets"):
        tools.cast_spell(
            "pc1",
            "srd.hold_monster",
            ["goblin1", "goblin2"],
            5,
            idempotency_key="cast-hold-monster-too-many",
        )

    assert caster.spell_slots["5"] == 1


def test_hold_monster_upcast_allows_additional_target_and_spends_requested_slot(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"wizard": 9}
    caster.abilities["int"] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["5"] = 0
    caster.spell_slots["6"] = 1
    state.encounter.combatants["goblin1"].abilities = {"wis": 8}
    state.encounter.combatants["goblin2"] = Combatant(
        id="goblin2",
        entity_id="goblin2",
        name="Goblin 2",
        side="monsters",
        hp_current=7,
        hp_max=7,
        armor_class=12,
        abilities={"wis": 8},
        position_node_id="cover",
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1, 1]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.hold_monster",
        ["goblin1", "goblin2"],
        6,
        idempotency_key="cast-hold-monster-upcast",
    )

    assert result["success"] is True
    assert caster.spell_slots["5"] == 0
    assert caster.spell_slots["6"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_6"
    assert cost_change["base_spell_slot_level"] == 5
    assert cost_change["spell_slot_level"] == 6
    condition_changes = [
        change for change in result["state_changes"] if change["type"] == "condition"
    ]
    assert [change["target_id"] for change in condition_changes] == ["goblin1", "goblin2"]
    assert all(change["condition"] == "paralyzed" for change in condition_changes)


def test_greater_restoration_requires_choice_before_spending_cost(make_state) -> None:
    state = make_state()
    caster = state.characters["pc1"]
    caster.class_levels = {"cleric": 9}
    caster.spell_slots["5"] = 1
    caster.gold = 100
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="missing required parameter"):
        tools.perform_action(
            "pc1",
            "srd.greater_restoration",
            ["pc2"],
            {"slot_level": 5},
            idempotency_key="greater-restoration-missing-choice",
        )

    assert caster.spell_slots["5"] == 1
    assert caster.gold == 100


def test_globe_of_invulnerability_records_concentration_spell_barrier(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"wizard": 11}
    caster.spell_slots["6"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell(
        "pc1",
        "srd.globe_of_invulnerability",
        [],
        6,
        idempotency_key="cast-globe-of-invulnerability",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_6"

    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.globe_of_invulnerability"
    assert effect["effect_type"] == "globe_of_invulnerability"
    assert effect["concentration"] is True
    assert effect["scope"] == {"target": "self_centered_emanation", "radius_ft": 10}
    assert effect["duration"] == {"until": "concentration_1_minute"}
    assert effect["tick_on"] == "self_turn_end"
    assert effect["metadata"] == {
        "immobile": True,
        "shimmering_barrier": True,
        "spells_must_be_cast_from_outside_barrier": True,
        "protected_targets": "creatures_and_objects_within_barrier",
        "outside_spell_can_target_inside_but_has_no_effect": True,
        "area_inside_excluded_from_outside_spell_areas": True,
        "blocks_spell_level_lte": 5,
    }
    world_effect_change = next(
        change for change in result["state_changes"] if change["type"] == "world_effect"
    )
    assert world_effect_change["effect_type"] == "globe_of_invulnerability"
    assert world_effect_change["concentration"] is True

    lifecycle = tick_effects(state, trigger="self_turn_end", actor_id="pc1")
    assert lifecycle.ticked[0]["remaining_ticks_before"] == 10
    assert lifecycle.ticked[0]["remaining_ticks_after"] == 9


def test_globe_of_invulnerability_upcast_records_higher_blocked_spell_level(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"sorcerer": 13}
    caster.spell_slots["6"] = 0
    caster.spell_slots["7"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell(
        "pc1",
        "srd.globe_of_invulnerability",
        [],
        7,
        idempotency_key="cast-globe-of-invulnerability-upcast",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    assert caster.spell_slots["7"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_7"
    assert cost_change["base_spell_slot_level"] == 6
    assert cost_change["spell_slot_level"] == 7
    effect = state.world.active_effects[-1]
    assert effect["metadata"]["blocks_spell_level_lte"] == 6


def test_forbiddance_spends_slot_records_ward_and_does_not_consume_ruby_dust(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"cleric": 11}
    caster.spell_slots["6"] = 1
    caster.gold = 1000
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools._execute_action(
        action_id="srd.forbiddance",
        actor_id="pc1",
        targets=[],
        params={
            "slot_level": 6,
            "forbiddance_damage_type": "Radiant",
            "forbiddance_creature_types": ["Fiend", "Undead"],
        },
        idempotency_key="cast-forbiddance",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    assert caster.gold == 1000
    cost_changes = [change for change in result["state_changes"] if change["type"] == "cost"]
    assert [change["resource"] for change in cost_changes] == ["spell_slot_6"]

    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.forbiddance"
    assert effect["effect_type"] == "forbiddance_ward"
    assert effect["concentration"] is False
    assert effect["scope"] == {
        "target": "touched_area",
        "max_floor_area_sq_ft": 40000,
        "height_ft": 30,
    }
    assert effect["duration"] == {"until": "duration_1_day"}
    assert effect["tick_on"] == "self_turn_end"
    assert effect["metadata"] == {
        "blocks_teleport_into_area": True,
        "blocks_portals_into_area": True,
        "proofs_against_planar_travel": True,
        "blocked_planar_routes": [
            "astral_plane",
            "ethereal_plane",
            "feywild",
            "shadowfell",
            "plane_shift",
        ],
        "chosen_creature_types": ["fiend", "undead"],
        "damage_type": "radiant",
        "damage": "5d10",
        "repeat_damage_triggers": [
            "chosen_creature_enters_area_first_time_on_turn",
            "chosen_creature_ends_turn_in_area",
        ],
        "password_prevents_spell_damage_when_spoken_on_entry": True,
        "password_param": "forbiddance_password",
        "area_cannot_overlap_another_forbiddance": True,
        "permanent_if_cast_daily_same_location_days": 30,
        "material_components_consumed_on_permanent_cast": True,
    }
    world_effect_change = next(
        change for change in result["state_changes"] if change["type"] == "world_effect"
    )
    assert world_effect_change["effect_type"] == "forbiddance_ward"
    assert world_effect_change["concentration"] is False

    lifecycle = tick_effects(state, trigger="self_turn_end", actor_id="pc1")
    assert lifecycle.ticked[0]["remaining_ticks_before"] == 14400
    assert lifecycle.ticked[0]["remaining_ticks_after"] == 14399


def test_forbiddance_can_be_cast_as_ritual_without_spending_spell_slot(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"cleric": 11}
    caster.prepared_spells = ["srd.spell.forbiddance"]
    caster.spell_slots["6"] = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools._execute_action(
        action_id="srd.forbiddance",
        actor_id="pc1",
        targets=[],
        params={
            "slot_level": 6,
            "as_ritual": True,
            "forbiddance_damage_type": "necrotic",
            "forbiddance_creature_types": ["aberration"],
        },
        idempotency_key="ritual-forbiddance",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    ritual_change = next(
        change for change in result["state_changes"] if change["type"] == "ritual_casting"
    )
    assert ritual_change == {
        "type": "ritual_casting",
        "actor_id": "pc1",
        "spell_id": "srd.spell.forbiddance",
        "base_spell_slot_level": 6,
        "spell_slot_expended": False,
        "casting_time_extra_minutes": 10,
        "source": "prepared_spell",
    }
    assert not [
        change
        for change in result["state_changes"]
        if change["type"] == "cost" and change["resource"] == "spell_slot_6"
    ]
    assert state.world.active_effects[-1]["metadata"]["chosen_creature_types"] == ["aberration"]


def test_forbiddance_rejects_non_srd_choices_before_spending_slot(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"cleric": 11}
    caster.spell_slots["6"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="forbiddance_damage_type must be one of"):
        tools._execute_action(
            action_id="srd.forbiddance",
            actor_id="pc1",
            targets=[],
            params={
                "slot_level": 6,
                "forbiddance_damage_type": "fire",
                "forbiddance_creature_types": ["fiend"],
            },
            idempotency_key="forbiddance-bad-damage-type",
        )

    assert caster.spell_slots["6"] == 1
    assert state.world.active_effects == []

    with pytest.raises(AutomationError, match="forbiddance_creature_types must contain only"):
        tools._execute_action(
            action_id="srd.forbiddance",
            actor_id="pc1",
            targets=[],
            params={
                "slot_level": 6,
                "forbiddance_damage_type": "radiant",
                "forbiddance_creature_types": ["dragon"],
            },
            idempotency_key="forbiddance-bad-creature-type",
        )

    assert caster.spell_slots["6"] == 1
    assert state.world.active_effects == []


def test_cloudkill_uses_actor_spell_dc_deals_poison_and_records_fog(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"wizard": 9}
    caster.abilities["int"] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["5"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"con": 10}
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1, 8]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.cloudkill",
        ["goblin1"],
        5,
        idempotency_key="cast-cloudkill",
    )

    assert result["success"] is True
    assert caster.spell_slots["5"] == 0
    save_node = result["node_results"]["automation[1]"]
    assert save_node["dc"] == 16
    assert save_node["dc_source"] == "spell_save_dc:wizard"
    assert save_node["success"] is False
    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert damage_change["damage_type"] == "poison"
    assert damage_change["amount"] == 8
    assert [roll["expression"] for roll in result["dice_rolls"]] == ["1d20+0", "5d8"]

    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.cloudkill"
    assert effect["effect_type"] == "cloudkill_fog"
    assert effect["concentration"] is True
    assert effect["duration"] == {"until": "concentration_10_minutes"}
    assert effect["scope"] == {"shape": "sphere", "radius_ft": 20, "range_ft": 120}
    assert effect["metadata"] == {
        "heavily_obscured": True,
        "dispersed_by_strong_wind": True,
        "moves_away_from_caster_ft_at_start_of_turn": 10,
        "repeat_save_triggers": [
            "sphere_moves_into_space",
            "creature_enters_area",
            "creature_ends_turn_in_area",
        ],
        "repeat_save_once_per_turn": True,
        "repeat_save": {
            "ability": "con",
            "dc_from": {"spell_save_dc": "actor"},
            "damage": "5d8 poison",
            "higher_level_damage_increase": "1d8 per slot above 5",
        },
    }
    world_effect_change = next(
        change for change in result["state_changes"] if change["type"] == "world_effect"
    )
    assert world_effect_change["effect_type"] == "cloudkill_fog"
    assert world_effect_change["concentration"] is True


def test_cloudkill_upcast_spends_requested_slot_and_adds_damage_die(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"wizard": 9}
    caster.abilities["int"] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["5"] = 0
    caster.spell_slots["6"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"con": 10}
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1, 8]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.cloudkill",
        ["goblin1"],
        6,
        idempotency_key="cast-cloudkill-upcast",
    )

    assert result["success"] is True
    assert caster.spell_slots["5"] == 0
    assert caster.spell_slots["6"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_6"
    assert cost_change["base_spell_slot_level"] == 5
    assert cost_change["spell_slot_level"] == 6
    assert [roll["expression"] for roll in result["dice_rolls"]] == ["1d20+0", "6d8"]


def test_insect_plague_uses_actor_spell_dc_deals_piercing_and_records_swarm(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"cleric": 9}
    caster.abilities["wis"] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["5"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"con": 10}
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1, 10]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.insect_plague",
        ["goblin1"],
        5,
        idempotency_key="cast-insect-plague",
    )

    assert result["success"] is True
    assert caster.spell_slots["5"] == 0
    save_node = result["node_results"]["automation[1]"]
    assert save_node["dc"] == 16
    assert save_node["dc_source"] == "spell_save_dc:cleric"
    assert save_node["success"] is False
    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert damage_change["damage_type"] == "piercing"
    assert damage_change["amount"] == 10
    assert [roll["expression"] for roll in result["dice_rolls"]] == ["1d20+0", "4d10"]

    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.insect_plague"
    assert effect["effect_type"] == "insect_plague_swarm"
    assert effect["concentration"] is True
    assert effect["duration"] == {"until": "concentration_10_minutes"}
    assert effect["tick_on"] == "self_turn_end"
    assert effect["scope"] == {"shape": "sphere", "radius_ft": 20, "range_ft": 300}
    assert effect["metadata"] == {
        "lightly_obscured": True,
        "difficult_terrain": True,
        "repeat_save_triggers": [
            "creature_enters_area",
            "creature_ends_turn_in_area",
        ],
        "repeat_save_once_per_turn": True,
        "repeat_save": {
            "ability": "con",
            "dc_from": {"spell_save_dc": "actor"},
            "damage": "4d10 piercing",
            "higher_level_damage_increase": "1d10 per slot above 5",
        },
    }
    world_effect_change = next(
        change for change in result["state_changes"] if change["type"] == "world_effect"
    )
    assert world_effect_change["effect_type"] == "insect_plague_swarm"
    assert world_effect_change["concentration"] is True

    lifecycle = tick_effects(state, trigger="self_turn_end", actor_id="pc1")
    assert lifecycle.ticked[0]["remaining_ticks_before"] == 100
    assert lifecycle.ticked[0]["remaining_ticks_after"] == 99


def test_insect_plague_upcast_spends_requested_slot_and_adds_damage_die(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"druid": 9}
    caster.abilities["wis"] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["5"] = 0
    caster.spell_slots["6"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"con": 10}
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1, 10]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.insect_plague",
        ["goblin1"],
        6,
        idempotency_key="cast-insect-plague-upcast",
    )

    assert result["success"] is True
    assert caster.spell_slots["5"] == 0
    assert caster.spell_slots["6"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_6"
    assert cost_change["base_spell_slot_level"] == 5
    assert cost_change["spell_slot_level"] == 6
    assert [roll["expression"] for roll in result["dice_rolls"]] == ["1d20+0", "5d10"]


def test_teleportation_circle_spends_inks_and_records_expiring_portal(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"wizard": 9}
    caster.spell_slots["5"] = 1
    caster.gold = 50
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell(
        "pc1",
        "srd.teleportation_circle",
        [],
        5,
        idempotency_key="cast-teleportation-circle",
    )

    assert result["success"] is True
    assert caster.spell_slots["5"] == 0
    assert caster.gold == 0
    cost_resources = [
        change["resource"] for change in result["state_changes"] if change["type"] == "cost"
    ]
    assert cost_resources == ["spell_slot_5", "gold"]

    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.teleportation_circle"
    assert effect["effect_type"] == "teleportation_circle_portal"
    assert effect["concentration"] is False
    assert effect["scope"] == {"target": "point", "radius_ft": 5, "range_ft": 10}
    assert effect["duration"] == {"until": "end_of_next_turn", "remaining_ticks": 2}
    assert effect["tick_on"] == "self_turn_end"
    assert effect["metadata"] == {
        "requires_known_sigil_sequence": True,
        "destination": "permanent_teleportation_circle",
        "same_plane_required": True,
        "portal_open_until_end_of_next_turn": True,
        "entering_creature_appears_within_ft_of_destination_circle": 5,
        "nearest_unoccupied_space_if_destination_occupied": True,
        "initial_known_material_plane_destination_count": 2,
        "learn_new_sigil_sequence_study_minutes": 1,
        "permanent_circle_daily_castings_required": 365,
    }
    world_effect_change = next(
        change for change in result["state_changes"] if change["type"] == "world_effect"
    )
    assert world_effect_change["effect_type"] == "teleportation_circle_portal"

    first_tick = tick_effects(state, trigger="self_turn_end", actor_id="pc1")
    assert first_tick.ticked[0]["remaining_ticks_before"] == 2
    assert first_tick.ticked[0]["remaining_ticks_after"] == 1
    assert state.world.active_effects[-1]["duration"]["remaining_ticks"] == 1

    second_tick = tick_effects(state, trigger="self_turn_end", actor_id="pc1")
    assert second_tick.expired[0]["source_action_id"] == "srd.teleportation_circle"
    assert state.world.active_effects == []


def test_transport_via_plants_spends_slot_and_records_timed_plant_link(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"druid": 11}
    caster.spell_slots["6"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell(
        "pc1",
        "srd.transport_via_plants",
        [],
        6,
        idempotency_key="cast-transport-via-plants",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_6"

    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.transport_via_plants"
    assert effect["effect_type"] == "transport_via_plants_link"
    assert effect["concentration"] is False
    assert effect["scope"] == {"target": "large_or_larger_inanimate_plant", "range_ft": 10}
    assert effect["duration"] == {"until": "duration_1_minute"}
    assert effect["tick_on"] == "self_turn_end"
    assert effect["metadata"] == {
        "destination": "another_plant",
        "same_plane_required": True,
        "destination_must_have_been_seen_or_touched_before": True,
        "any_creature_can_use": True,
        "movement_cost_ft": 5,
        "enter_target_plant_and_exit_destination_plant": True,
    }
    world_effect_change = next(
        change for change in result["state_changes"] if change["type"] == "world_effect"
    )
    assert world_effect_change["effect_type"] == "transport_via_plants_link"
    assert world_effect_change["concentration"] is False

    lifecycle = tick_effects(state, trigger="self_turn_end", actor_id="pc1")
    assert lifecycle.ticked[0]["remaining_ticks_before"] == 10
    assert lifecycle.ticked[0]["remaining_ticks_after"] == 9


def test_word_of_recall_spends_slot_and_records_instant_sanctuary_teleport(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"cleric": 11}
    caster.spell_slots["6"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools._execute_action(
        action_id="srd.word_of_recall",
        actor_id="pc1",
        targets=["pc1", "pc2"],
        params={"slot_level": 6, "target_willing": True},
        idempotency_key="cast-word-of-recall",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_6"

    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.word_of_recall"
    assert effect["effect_type"] == "word_of_recall_teleport"
    assert effect["concentration"] is False
    assert effect["scope"] == {"target": "explicit", "range_ft": 5, "target_ids": ["pc1", "pc2"]}
    assert "target_id" not in effect["scope"]
    assert effect["duration"] == {"until": "instant"}
    assert effect["metadata"] == {
        "teleports_actor": True,
        "max_willing_companions": 5,
        "companions_must_be_within_ft": 5,
        "requires_previously_designated_sanctuary": True,
        "no_effect_without_prepared_sanctuary": True,
        "appears_nearest_unoccupied_space_to_designated_spot": True,
        "designates_sanctuary_by_casting_this_spell_there": True,
        "destination": "previously_designated_sanctuary",
    }
    world_effect_change = next(
        change for change in result["state_changes"] if change["type"] == "world_effect"
    )
    assert world_effect_change["effect_type"] == "word_of_recall_teleport"
    assert world_effect_change["concentration"] is False
    assert world_effect_change["scope"] == effect["scope"]


def test_etherealness_records_border_ethereal_world_effect_and_upcast_targets(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"wizard": 15}
    caster.spell_slots["8"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools._execute_action(
        action_id="srd.etherealness",
        actor_id="pc1",
        targets=["pc1", "pc2"],
        params={"slot_level": 8, "target_willing": True},
        idempotency_key="cast-etherealness-upcast",
    )

    assert result["success"] is True
    assert caster.spell_slots["8"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_8"
    assert cost_change["base_spell_slot_level"] == 7
    assert cost_change["spell_slot_level"] == 8

    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.etherealness"
    assert effect["effect_type"] == "etherealness"
    assert effect["concentration"] is False
    assert effect["scope"] == {
        "target": "explicit",
        "range_ft": 10,
        "target_ids": ["pc1", "pc2"],
    }
    assert effect["duration"] == {"until": "duration_8_hours"}
    assert effect["tick_on"] == "self_turn_end"
    assert effect["metadata"] == {
        "border_ethereal": True,
        "current_plane_must_border_ethereal": True,
        "ends_instantly_if_cast_on_ethereal_or_nonbordering_plane": True,
        "can_move_in_any_direction": True,
        "vertical_movement_extra_cost_per_foot": 1,
        "perceives_origin_plane_gray": True,
        "origin_plane_vision_range_ft": 60,
        "can_affect_only_ethereal_plane": True,
        "can_be_affected_only_by_ethereal_plane": True,
        "non_ethereal_creatures_cannot_perceive_or_interact_without_special_ability": True,
        "returns_to_origin_plane_when_spell_ends": True,
        "returns_to_corresponding_space": True,
        "shunted_to_nearest_unoccupied_space_if_occupied": True,
        "shunted_force_damage_per_ft": 2,
        "willing_creatures_must_be_within_ft": 10,
        "higher_level_targets_per_slot_above_7": 3,
        "includes_self": True,
    }
    world_effect_change = next(
        change for change in result["state_changes"] if change["type"] == "world_effect"
    )
    assert world_effect_change["effect_type"] == "etherealness"
    assert world_effect_change["concentration"] is False
    assert world_effect_change["scope"] == effect["scope"]

    lifecycle = tick_effects(state, trigger="self_turn_end", actor_id="pc1")
    assert lifecycle.ticked[0]["remaining_ticks_before"] == 4800
    assert lifecycle.ticked[0]["remaining_ticks_after"] == 4799


def test_etherealness_requires_self_target_before_spending_slot(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"cleric": 13}
    caster.actions.append("srd.etherealness")
    caster.spell_slots["7"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())
    resolver = ActionResolver(state, compendium.actions)

    rejected = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="以太化盟友",
            target_ids=["pc2"],
            candidate_action_id="srd.etherealness",
            params={"slot_level": 7, "target_willing": True},
        )
    )
    assert rejected.status == "rejected"
    assert rejected.reason == "target list must include self"

    with pytest.raises(AutomationError, match="target list must include self"):
        tools._execute_action(
            action_id="srd.etherealness",
            actor_id="pc1",
            targets=["pc2"],
            params={"slot_level": 7, "target_willing": True},
            idempotency_key="cast-etherealness-without-self",
        )

    assert caster.spell_slots["7"] == 1
    assert state.world.active_effects == []


def test_true_seeing_spends_component_and_grants_timed_truesight(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"cleric": 11}
    caster.spell_slots["6"] = 1
    caster.gold = 25
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="target must be willing"):
        tools._execute_action(
            action_id="srd.true_seeing",
            actor_id="pc1",
            targets=["pc2"],
            params={"slot_level": 6},
            idempotency_key="cast-true-seeing-unwilling",
        )

    result = tools._execute_action(
        action_id="srd.true_seeing",
        actor_id="pc1",
        targets=["pc2"],
        params={"slot_level": 6, "target_willing": True},
        idempotency_key="cast-true-seeing",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    assert caster.gold == 0
    cost_resources = [
        change["resource"] for change in result["state_changes"] if change["type"] == "cost"
    ]
    assert cost_resources == ["spell_slot_6", "gold"]

    effect = state.encounter.combatants["pc2"].status_effects[-1]
    assert effect["source_action_id"] == "srd.true_seeing"
    assert effect["condition"] is None
    assert effect["passive_modifiers"] == {"truesight_ft": 120}
    assert effect["duration"] == {"until": "duration_1_hour"}
    assert effect["tick_on"] == "self_turn_end"
    assert effect["concentration"] is False
    assert truesight_range_from_effects(state.encounter.combatants["pc2"].status_effects) == 120
    passive_change = next(
        change for change in result["state_changes"] if change["type"] == "passive_effect"
    )
    assert passive_change["target_id"] == "pc2"
    assert passive_change["passive_modifiers"] == {"truesight_ft": 120}

    lifecycle = tick_effects(state, trigger="self_turn_end", actor_id="pc1")
    assert lifecycle.ticked[0]["remaining_ticks_before"] == 600
    assert lifecycle.ticked[0]["remaining_ticks_after"] == 599
    assert (
        state.encounter.combatants["pc2"].status_effects[-1]["duration"]["remaining_ticks"] == 599
    )


def test_find_the_path_records_concentration_navigation_sense(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"cleric": 11}
    caster.spell_slots["6"] = 1
    caster.gold = 100
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell(
        "pc1",
        "srd.find_the_path",
        ["pc1"],
        6,
        idempotency_key="cast-find-the-path",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    assert caster.gold == 100
    cost_changes = [change for change in result["state_changes"] if change["type"] == "cost"]
    assert [change["resource"] for change in cost_changes] == ["spell_slot_6"]

    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.find_the_path"
    assert effect["condition"] is None
    assert effect["duration"] == {"until": "concentration_1_day"}
    assert effect["tick_on"] == "self_turn_end"
    assert effect["concentration"] is True
    assert effect["passive_modifiers"] == {
        "find_the_path": True,
        "senses_most_direct_physical_route": True,
        "requires_familiar_named_location": True,
        "fails_for_other_plane_destination": True,
        "fails_for_moving_destination": True,
        "fails_for_unspecific_destination": True,
        "same_plane_required_to_know_distance_and_direction": True,
        "knows_distance_and_direction_to_destination": True,
        "knows_most_direct_path_when_choosing_paths": True,
    }
    passive_change = next(
        change for change in result["state_changes"] if change["type"] == "passive_effect"
    )
    assert passive_change["target_id"] == "pc1"
    assert passive_change["passive_modifiers"]["find_the_path"] is True

    lifecycle = tick_effects(state, trigger="self_turn_end", actor_id="pc1")
    assert lifecycle.ticked[0]["remaining_ticks_before"] == 14400
    assert lifecycle.ticked[0]["remaining_ticks_after"] == 14399
    assert (
        state.encounter.combatants["pc1"].status_effects[-1]["duration"]["remaining_ticks"] == 14399
    )


def test_passwall_spends_slot_and_records_timed_passage(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"wizard": 9}
    caster.spell_slots["5"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell(
        "pc1",
        "srd.passwall",
        [],
        5,
        idempotency_key="cast-passwall",
    )

    assert result["success"] is True
    assert caster.spell_slots["5"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_5"

    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.passwall"
    assert effect["effect_type"] == "passwall_passage"
    assert effect["concentration"] is False
    assert effect["scope"] == {"target": "point_on_surface", "range_ft": 30}
    assert effect["duration"] == {"until": "duration_1_hour"}
    assert effect["tick_on"] == "self_turn_end"
    assert effect["metadata"] == {
        "surface_types": ["wooden", "plaster", "stone"],
        "surface_examples": ["wall", "ceiling", "floor"],
        "max_width_ft": 5,
        "max_height_ft": 8,
        "max_depth_ft": 20,
        "creates_no_structural_instability": True,
        "ejects_occupants_to_nearest_unoccupied_space_on_expiry": True,
    }
    world_effect_change = next(
        change for change in result["state_changes"] if change["type"] == "world_effect"
    )
    assert world_effect_change["effect_type"] == "passwall_passage"

    tick = tick_effects(state, trigger="self_turn_end", actor_id="pc1")
    assert tick.ticked[0]["remaining_ticks_before"] == 600
    assert tick.ticked[0]["remaining_ticks_after"] == 599
    assert state.world.active_effects[-1]["duration"]["remaining_ticks"] == 599


def test_move_earth_spends_slot_and_records_concentration_terrain_reshaping(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"druid": 11}
    caster.spell_slots["6"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell(
        "pc1",
        "srd.move_earth",
        [],
        6,
        idempotency_key="cast-move-earth",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_6"

    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.move_earth"
    assert effect["effect_type"] == "move_earth_terrain_reshaping"
    assert effect["concentration"] is True
    assert effect["scope"] == {"target": "terrain_area", "range_ft": 120, "max_side_ft": 40}
    assert effect["duration"] == {"until": "concentration_2_hours"}
    assert effect["tick_on"] == "self_turn_end"
    assert effect["metadata"] == {
        "terrain_types": ["dirt", "sand", "clay"],
        "max_area_side_ft": 40,
        "allowed_shapes": [
            "raise_elevation",
            "lower_elevation",
            "create_trench",
            "fill_trench",
            "erect_wall",
            "flatten_wall",
            "form_pillar",
        ],
        "max_change_fraction_of_largest_dimension": 0.5,
        "changes_complete_after_minutes": 10,
        "creatures_cannot_usually_be_trapped_or_injured_by_slow_movement": True,
        "can_choose_new_area_every_minutes": 10,
        "cannot_manipulate_natural_stone_or_stone_construction": True,
        "rocks_and_structures_shift_to_accommodate_new_terrain": True,
        "unstable_structures_might_collapse": True,
        "does_not_directly_affect_plant_growth": True,
        "moved_earth_carries_plants_along": True,
    }
    world_effect_change = next(
        change for change in result["state_changes"] if change["type"] == "world_effect"
    )
    assert world_effect_change["effect_type"] == "move_earth_terrain_reshaping"
    assert world_effect_change["concentration"] is True

    tick = tick_effects(state, trigger="self_turn_end", actor_id="pc1")
    assert tick.ticked[0]["remaining_ticks_before"] == 1200
    assert tick.ticked[0]["remaining_ticks_after"] == 1199
    assert state.world.active_effects[-1]["duration"]["remaining_ticks"] == 1199


def test_wind_walk_applies_cloud_form_and_allows_only_dash(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"druid": 11}
    caster.spell_slots["6"] = 1
    state.encounter.combatants["pc2"].hp_current = 20
    state.encounter.combatants["pc2"].hp_max = 20
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="target must be willing"):
        tools._execute_action(
            action_id="srd.wind_walk",
            actor_id="pc1",
            targets=["pc1", "pc2"],
            params={"slot_level": 6},
            idempotency_key="cast-wind-walk-unwilling",
        )

    result = tools._execute_action(
        action_id="srd.wind_walk",
        actor_id="pc1",
        targets=["pc1", "pc2"],
        params={"slot_level": 6, "target_willing": True},
        idempotency_key="cast-wind-walk",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_6"
    expected_modifiers = {
        "wind_walk_cloud_form": True,
        "gaseous_form": True,
        "fly_speed_ft": 300,
        "can_hover": True,
        "condition_immunities": ["prone"],
        "damage_resistances": ["bludgeoning", "piercing", "slashing"],
        "allowed_action_ids": ["srd.dash"],
        "allowed_unimplemented_magic_actions": [
            "begin_reverting_to_normal_form",
        ],
        "revert_to_normal_form": {
            "action_economy": "magic_action",
            "transformation_duration": "duration_1_minute",
            "condition_during_transformation": "stunned",
        },
        "revert_to_cloud_form": {
            "action_economy": "magic_action",
            "transformation_duration": "duration_1_minute",
        },
        "cloud_form_end_descent": {
            "descent_ft_per_round": 60,
            "duration_rounds": 10,
            "lands_safely_if_reaches_ground": True,
            "falls_remaining_distance_after_rounds": 10,
        },
    }
    pc1_effect = state.encounter.combatants["pc1"].status_effects[-1]
    pc2_effect = state.encounter.combatants["pc2"].status_effects[-1]
    assert pc1_effect["source_action_id"] == "srd.wind_walk"
    assert pc1_effect["condition"] is None
    assert pc1_effect["passive_modifiers"] == expected_modifiers
    assert pc1_effect["duration"] == {"until": "duration_8_hours"}
    assert pc1_effect["tick_on"] == "self_turn_end"
    assert pc1_effect["concentration"] is False
    assert pc2_effect["passive_modifiers"] == expected_modifiers
    assert fly_speed_from_effects(30, state.encounter.combatants["pc1"].status_effects) == 300
    assert can_hover_from_effects(state.encounter.combatants["pc1"].status_effects) is True

    damage = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        _damage_action(9, damage_type="slashing"),
        actor_id="goblin1",
        targets=["pc2"],
        idempotency_key="slashing-damage-after-wind-walk",
    )
    damage_change = next(change for change in damage.state_changes if change["type"] == "damage")
    assert damage_change["amount"] == 9
    assert damage_change["applied"] == 4
    assert state.encounter.combatants["pc2"].hp_current == 16

    with pytest.raises(AutomationError, match="can only take allowed actions"):
        tools.perform_action(
            "pc2",
            "srd.dodge",
            [],
            idempotency_key="wind-walk-blocks-dodge",
        )
    dash = tools.perform_action(
        "pc2",
        "srd.dash",
        [],
        idempotency_key="wind-walk-allows-dash",
    )
    assert dash["success"] is True

    resolver = ActionResolver(state, compendium.actions, compendium.items)
    rejected = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc2",
            verb="dodge",
            target_ids=[],
            candidate_action_id="srd.dodge",
        )
    )
    assert rejected.status == "rejected"
    assert "can only take allowed actions" in str(rejected.reason)

    lifecycle = tick_effects(state, trigger="self_turn_end", actor_id="pc1")
    assert len(lifecycle.ticked) == 2
    assert {entry["remaining_ticks_before"] for entry in lifecycle.ticked} == {4800}
    assert {entry["remaining_ticks_after"] for entry in lifecycle.ticked} == {4799}


def test_tree_stride_spends_slot_and_applies_concentration_transport_ability(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"druid": 9}
    caster.spell_slots["5"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell(
        "pc1",
        "srd.tree_stride",
        ["pc1"],
        5,
        idempotency_key="cast-tree-stride",
    )

    assert result["success"] is True
    assert caster.spell_slots["5"] == 0
    effect = state.encounter.combatants["pc1"].status_effects[-1]
    assert effect["source_action_id"] == "srd.tree_stride"
    assert effect["condition"] is None
    assert effect["duration"] == {"until": "concentration_1_minute"}
    assert effect["tick_on"] == "self_turn_end"
    assert effect["concentration"] is True
    assert effect["passive_modifiers"] == {
        "tree_stride": True,
        "tree_stride_range_ft": 500,
        "same_kind_living_tree_required": True,
        "tree_must_be_at_least_actor_size": True,
        "enter_tree_movement_cost_ft": 5,
        "destination_exit_movement_cost_ft": 5,
        "knows_same_kind_tree_locations_within_ft": 500,
        "appears_within_ft_of_destination_tree": 5,
        "returns_within_ft_of_entered_tree_if_no_movement_left": 5,
        "uses_per_turn": 1,
        "must_end_turn_outside_tree": True,
    }
    passive_change = next(
        change for change in result["state_changes"] if change["type"] == "passive_effect"
    )
    assert passive_change["target_id"] == "pc1"
    assert passive_change["passive_modifiers"]["tree_stride"] is True

    lifecycle = tick_effects(state, trigger="self_turn_end", actor_id="pc1")
    assert lifecycle.ticked[0]["remaining_ticks_before"] == 10
    assert lifecycle.ticked[0]["remaining_ticks_after"] == 9


def test_wall_of_force_spends_slot_and_records_concentration_barrier(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"wizard": 9}
    caster.spell_slots["5"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell(
        "pc1",
        "srd.wall_of_force",
        [],
        5,
        idempotency_key="cast-wall-of-force",
    )

    assert result["success"] is True
    assert caster.spell_slots["5"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_5"

    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.wall_of_force"
    assert effect["effect_type"] == "wall_of_force"
    assert effect["concentration"] is True
    assert effect["scope"] == {"target": "point", "range_ft": 120}
    assert effect["duration"] == {"until": "concentration_10_minutes"}
    assert effect["tick_on"] == "self_turn_end"
    assert effect["metadata"] == {
        "invisible": True,
        "orientation_options": ["horizontal", "vertical", "angled"],
        "can_be_free_floating": True,
        "can_rest_on_solid_surface": True,
        "hemispherical_dome_max_radius_ft": 10,
        "globe_max_radius_ft": 10,
        "flat_panel_count": 10,
        "flat_panel_width_ft": 10,
        "flat_panel_height_ft": 10,
        "flat_panels_must_be_contiguous": True,
        "thickness_inches": 0.25,
        "pushes_creatures_to_chosen_side_if_cutting_space": True,
        "blocks_physical_passage": True,
        "immune_to_all_damage": True,
        "not_dispelled_by_dispel_magic": True,
        "destroyed_by_disintegrate": True,
        "extends_into_ethereal_plane": True,
        "blocks_ethereal_travel": True,
    }
    world_effect_change = next(
        change for change in result["state_changes"] if change["type"] == "world_effect"
    )
    assert world_effect_change["effect_type"] == "wall_of_force"
    assert world_effect_change["concentration"] is True

    lifecycle = tick_effects(state, trigger="self_turn_end", actor_id="pc1")
    assert lifecycle.ticked[0]["remaining_ticks_before"] == 100
    assert lifecycle.ticked[0]["remaining_ticks_after"] == 99


def test_forcecage_consumes_ruby_dust_and_records_concentration_prison(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"wizard": 13}
    caster.spell_slots["7"] = 1
    caster.gold = 1500
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell(
        "pc1",
        "srd.forcecage",
        [],
        7,
        idempotency_key="cast-forcecage",
    )

    assert result["success"] is True
    assert caster.spell_slots["7"] == 0
    assert caster.gold == 0
    cost_resources = [
        change["resource"] for change in result["state_changes"] if change["type"] == "cost"
    ]
    assert cost_resources == ["spell_slot_7", "gold"]

    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.forcecage"
    assert effect["effect_type"] == "forcecage_prison"
    assert effect["concentration"] is True
    assert effect["scope"] == {"target": "area", "range_ft": 100, "shape": "cube"}
    assert effect["duration"] == {"until": "concentration_1_hour"}
    assert effect["tick_on"] == "self_turn_end"
    assert effect["metadata"] == {
        "immobile": True,
        "invisible": True,
        "composed_of_magical_force": True,
        "form_options": ["cage", "solid_box"],
        "cage_max_side_ft": 20,
        "cage_bar_diameter_inches": 0.5,
        "cage_bar_spacing_inches": 0.5,
        "solid_box_max_side_ft": 10,
        "solid_box_blocks_matter": True,
        "solid_box_blocks_spells_in_or_out": True,
        "creatures_completely_inside_area_are_trapped": True,
        "pushes_partial_or_too_large_creatures_outward": True,
        "cannot_leave_by_nonmagical_means": True,
        "teleport_or_interplanar_exit_requires_save": {
            "ability": "cha",
            "dc_from": {"spell_save_dc": "actor"},
            "success": "magic_can_exit_cage",
            "failure": "does_not_exit_and_spell_or_effect_is_wasted",
        },
        "extends_into_ethereal_plane": True,
        "blocks_ethereal_travel": True,
        "not_dispelled_by_dispel_magic": True,
    }
    world_effect_change = next(
        change for change in result["state_changes"] if change["type"] == "world_effect"
    )
    assert world_effect_change["effect_type"] == "forcecage_prison"
    assert world_effect_change["concentration"] is True

    lifecycle = tick_effects(state, trigger="self_turn_end", actor_id="pc1")
    assert lifecycle.ticked[0]["remaining_ticks_before"] == 600
    assert lifecycle.ticked[0]["remaining_ticks_after"] == 599


def test_forcecage_requires_consumed_component_before_spending_slot(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"bard": 13}
    caster.spell_slots["7"] = 1
    caster.gold = 1499
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="gold is insufficient"):
        tools.cast_spell(
            "pc1",
            "srd.forcecage",
            [],
            7,
            idempotency_key="cast-forcecage-no-ruby-dust",
        )

    assert caster.spell_slots["7"] == 1
    assert caster.gold == 1499
    assert state.world.active_effects == []


def test_wall_of_stone_spends_slot_and_records_supported_stone_wall(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"druid": 9}
    caster.spell_slots["5"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell(
        "pc1",
        "srd.wall_of_stone",
        [],
        5,
        idempotency_key="cast-wall-of-stone",
    )

    assert result["success"] is True
    assert caster.spell_slots["5"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_5"

    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.wall_of_stone"
    assert effect["effect_type"] == "wall_of_stone"
    assert effect["concentration"] is True
    assert effect["scope"] == {"target": "point", "range_ft": 120}
    assert effect["duration"] == {"until": "concentration_10_minutes"}
    assert effect["tick_on"] == "self_turn_end"
    assert effect["metadata"] == {
        "nonmagical": True,
        "material": "solid_stone",
        "standard_panel_count": 10,
        "standard_panel_width_ft": 10,
        "standard_panel_height_ft": 10,
        "standard_panel_thickness_inches": 6,
        "thin_panel_width_ft": 10,
        "thin_panel_height_ft": 20,
        "thin_panel_thickness_inches": 3,
        "panels_must_be_contiguous": True,
        "pushes_creatures_to_chosen_side_if_cutting_space": True,
        "enclosed_creature_escape_save": {
            "ability": "dex",
            "on_success": "may_use_reaction_to_move_up_to_speed_out_of_enclosure",
        },
        "can_have_any_shape": True,
        "cannot_occupy_creature_or_object_space": True,
        "does_not_need_vertical_orientation_or_firm_foundation": True,
        "must_merge_with_and_be_supported_by_existing_stone": True,
        "can_bridge_chasm_or_create_ramp": True,
        "span_over_20_ft_requires_halved_panels_for_support": True,
        "can_create_crude_battlements": True,
        "panel_ac": 15,
        "panel_hp_per_inch_of_thickness": 30,
        "damage_immunities": ["poison", "psychic"],
        "panel_destroyed_at_0_hp": True,
        "connected_panels_may_collapse_at_gm_discretion": True,
        "permanent_if_concentration_full_duration": True,
        "cannot_be_dispelled_when_permanent": True,
        "disappears_when_spell_ends_unless_permanent": True,
    }
    world_effect_change = next(
        change for change in result["state_changes"] if change["type"] == "world_effect"
    )
    assert world_effect_change["effect_type"] == "wall_of_stone"
    assert world_effect_change["concentration"] is True

    lifecycle = tick_effects(state, trigger="self_turn_end", actor_id="pc1")
    assert lifecycle.ticked[0]["remaining_ticks_before"] == 100
    assert lifecycle.ticked[0]["remaining_ticks_after"] == 99


def test_blade_barrier_deals_force_and_records_concentration_wall(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"cleric": 11}
    caster.abilities["wis"] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["6"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"dex": 10}
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1, 10]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.blade_barrier",
        ["goblin1"],
        6,
        idempotency_key="cast-blade-barrier",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    save_node = result["node_results"]["automation[1]"]
    assert save_node["dc"] == 16
    assert save_node["dc_source"] == "spell_save_dc:cleric"
    assert save_node["success"] is False
    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert damage_change["damage_type"] == "force"
    assert damage_change["amount"] == 10
    assert damage_change["applied"] == 10
    assert [roll["expression"] for roll in result["dice_rolls"]] == ["1d20+0", "6d10"]

    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.blade_barrier"
    assert effect["effect_type"] == "blade_barrier"
    assert effect["concentration"] is True
    assert effect["scope"] == {"target": "wall", "range_ft": 90}
    assert effect["duration"] == {"until": "concentration_10_minutes"}
    assert effect["tick_on"] == "self_turn_end"
    assert effect["metadata"] == {
        "magical_energy_blades": True,
        "shape_options": ["straight_wall", "ringed_wall"],
        "straight_wall_max_length_ft": 100,
        "straight_wall_max_height_ft": 20,
        "wall_thickness_ft": 5,
        "ringed_wall_max_diameter_ft": 60,
        "ringed_wall_max_height_ft": 20,
        "ringed_wall_thickness_ft": 5,
        "provides_cover": "three_quarters",
        "difficult_terrain": True,
        "initial_save": {
            "ability": "dex",
            "damage": "6d10 force",
            "save_half": True,
        },
        "repeat_save_triggers": [
            "creature_enters_wall_space",
            "creature_ends_turn_in_wall_space",
        ],
        "repeat_save_once_per_turn": True,
        "repeat_save": {
            "ability": "dex",
            "dc_from": {"spell_save_dc": "actor"},
            "damage": "6d10 force",
            "save_half": True,
        },
    }
    world_effect_change = next(
        change for change in result["state_changes"] if change["type"] == "world_effect"
    )
    assert world_effect_change["effect_type"] == "blade_barrier"
    assert world_effect_change["concentration"] is True

    lifecycle = tick_effects(state, trigger="self_turn_end", actor_id="pc1")
    assert lifecycle.ticked[0]["remaining_ticks_before"] == 100
    assert lifecycle.ticked[0]["remaining_ticks_after"] == 99


def test_wall_of_ice_deals_initial_cold_and_records_concentration_wall(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"wizard": 11}
    caster.abilities["int"] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["6"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"dex": 10}
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1, 6]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.wall_of_ice",
        ["goblin1"],
        6,
        idempotency_key="cast-wall-of-ice",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    save_node = result["node_results"]["automation[1]"]
    assert save_node["dc"] == 16
    assert save_node["dc_source"] == "spell_save_dc:wizard"
    assert save_node["success"] is False
    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert damage_change["damage_type"] == "cold"
    assert damage_change["amount"] == 6
    assert damage_change["applied"] == 6
    assert [roll["expression"] for roll in result["dice_rolls"]] == ["1d20+0", "10d6"]

    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.wall_of_ice"
    assert effect["effect_type"] == "wall_of_ice"
    assert effect["concentration"] is True
    assert effect["scope"] == {"target": "solid_surface", "range_ft": 120}
    assert effect["duration"] == {"until": "concentration_10_minutes"}
    assert effect["tick_on"] == "self_turn_end"
    assert effect["metadata"] == {
        "solid_surface_required": True,
        "shape_options": ["hemispherical_dome", "globe", "flat_panels"],
        "hemispherical_dome_max_radius_ft": 10,
        "globe_max_radius_ft": 10,
        "flat_panel_count": 10,
        "flat_panel_width_ft": 10,
        "flat_panel_height_ft": 10,
        "flat_panels_must_be_contiguous": True,
        "thickness_ft": 1,
        "pushes_creatures_to_chosen_side_if_cutting_space": True,
        "initial_save": {
            "ability": "dex",
            "damage": "10d6 cold",
            "save_half": True,
            "higher_level_damage_increase": "2d6 per slot above 6",
        },
        "object_ac": 12,
        "hp_per_10_ft_section": 30,
        "damage_immunities": ["cold", "poison", "psychic"],
        "damage_vulnerabilities": ["fire"],
        "section_destroyed_at_0_hp": True,
        "destroyed_section_leaves_frigid_air": True,
        "frigid_air": {
            "trigger": "creature_moves_through_first_time_on_turn",
            "save": {
                "ability": "con",
                "damage": "5d6 cold",
                "save_half": True,
                "higher_level_damage_increase": "1d6 per slot above 6",
            },
        },
    }
    world_effect_change = next(
        change for change in result["state_changes"] if change["type"] == "world_effect"
    )
    assert world_effect_change["effect_type"] == "wall_of_ice"
    assert world_effect_change["concentration"] is True

    lifecycle = tick_effects(state, trigger="self_turn_end", actor_id="pc1")
    assert lifecycle.ticked[0]["remaining_ticks_before"] == 100
    assert lifecycle.ticked[0]["remaining_ticks_after"] == 99


def test_wall_of_ice_upcast_adds_initial_damage_dice(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"wizard": 13}
    caster.abilities["int"] = 18
    caster.proficiency_bonus = 5
    caster.spell_slots["6"] = 0
    caster.spell_slots["7"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"dex": 10}
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1, 6]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.wall_of_ice",
        ["goblin1"],
        7,
        idempotency_key="cast-wall-of-ice-upcast",
    )

    assert result["success"] is True
    assert caster.spell_slots["7"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_7"
    assert cost_change["base_spell_slot_level"] == 6
    assert cost_change["spell_slot_level"] == 7
    assert [roll["expression"] for roll in result["dice_rolls"]] == ["1d20+0", "12d6"]


def test_wall_of_thorns_deals_initial_piercing_and_records_concentration_wall(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"druid": 11}
    caster.abilities["wis"] = 18
    caster.proficiency_bonus = 4
    caster.spell_slots["6"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"dex": 10}
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1, 8]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.wall_of_thorns",
        ["goblin1"],
        6,
        idempotency_key="cast-wall-of-thorns",
    )

    assert result["success"] is True
    assert caster.spell_slots["6"] == 0
    save_node = result["node_results"]["automation[1]"]
    assert save_node["dc"] == 16
    assert save_node["dc_source"] == "spell_save_dc:druid"
    assert save_node["success"] is False
    damage_change = next(change for change in result["state_changes"] if change["type"] == "damage")
    assert damage_change["damage_type"] == "piercing"
    assert damage_change["amount"] == 8
    assert damage_change["applied"] == 8
    assert [roll["expression"] for roll in result["dice_rolls"]] == ["1d20+0", "7d8"]

    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.wall_of_thorns"
    assert effect["effect_type"] == "wall_of_thorns"
    assert effect["concentration"] is True
    assert effect["scope"] == {"target": "solid_surface", "range_ft": 120}
    assert effect["duration"] == {"until": "concentration_10_minutes"}
    assert effect["tick_on"] == "self_turn_end"
    assert effect["metadata"] == {
        "solid_surface_required": True,
        "shape_options": ["wall", "circle"],
        "wall_max_length_ft": 60,
        "wall_max_height_ft": 10,
        "wall_thickness_ft": 5,
        "circle_diameter_ft": 20,
        "circle_max_height_ft": 20,
        "circle_thickness_ft": 5,
        "blocks_line_of_sight": True,
        "initial_save": {
            "ability": "dex",
            "damage": "7d8 piercing",
            "save_half": True,
            "higher_level_damage_increase": "1d8 per slot above 6",
        },
        "movement_cost_per_foot": 4,
        "repeat_save_triggers": [
            "creature_enters_wall",
            "creature_ends_turn_in_wall",
        ],
        "repeat_save_once_per_turn": True,
        "repeat_save": {
            "ability": "dex",
            "dc_from": {"spell_save_dc": "actor"},
            "damage": "7d8 slashing",
            "save_half": True,
            "higher_level_damage_increase": "1d8 per slot above 6",
        },
    }
    world_effect_change = next(
        change for change in result["state_changes"] if change["type"] == "world_effect"
    )
    assert world_effect_change["effect_type"] == "wall_of_thorns"
    assert world_effect_change["concentration"] is True

    lifecycle = tick_effects(state, trigger="self_turn_end", actor_id="pc1")
    assert lifecycle.ticked[0]["remaining_ticks_before"] == 100
    assert lifecycle.ticked[0]["remaining_ticks_after"] == 99


def test_wall_of_thorns_upcast_adds_both_damage_dice_metadata_and_initial_roll(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"druid": 13}
    caster.abilities["wis"] = 18
    caster.proficiency_bonus = 5
    caster.spell_slots["6"] = 0
    caster.spell_slots["7"] = 1
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"dex": 10}
    target.hp_current = 80
    target.hp_max = 80
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([1, 8]),
    )

    result = tools.cast_spell(
        "pc1",
        "srd.wall_of_thorns",
        ["goblin1"],
        7,
        idempotency_key="cast-wall-of-thorns-upcast",
    )

    assert result["success"] is True
    assert caster.spell_slots["7"] == 0
    cost_change = next(change for change in result["state_changes"] if change["type"] == "cost")
    assert cost_change["resource"] == "spell_slot_7"
    assert cost_change["base_spell_slot_level"] == 6
    assert cost_change["spell_slot_level"] == 7
    assert [roll["expression"] for roll in result["dice_rolls"]] == ["1d20+0", "8d8"]
    effect = state.world.active_effects[-1]
    assert (
        effect["metadata"]["repeat_save"]["higher_level_damage_increase"] == "1d8 per slot above 6"
    )


def test_greater_restoration_removes_one_exhaustion_level_and_spends_component(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"cleric": 9}
    caster.spell_slots["5"] = 1
    caster.gold = 100
    target_character = state.characters["pc2"]
    target_combatant = state.encounter.combatants["pc2"]
    target_character.status_effects = [
        {"effect_id": "char-exhaustion", "condition": "exhaustion", "level": 2}
    ]
    target_combatant.status_effects = [
        {"effect_id": "combat-exhaustion", "condition": "exhaustion", "level": 1}
    ]
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.greater_restoration",
        ["pc2"],
        {"slot_level": 5, "greater_restoration_choice": "exhaustion"},
        idempotency_key="greater-restoration-exhaustion",
    )

    assert result["success"] is True
    assert caster.spell_slots["5"] == 0
    assert caster.gold == 0
    cost_resources = [
        change["resource"] for change in result["state_changes"] if change["type"] == "cost"
    ]
    assert cost_resources == ["spell_slot_5", "gold"]
    greater_restore = next(
        change for change in result["state_changes"] if change["type"] == "greater_restoration"
    )
    assert greater_restore["choice"] == "exhaustion"
    assert greater_restore["removed"] == {"exhaustion": 1}
    assert greater_restore["removed_owners"] == [
        {
            "owner_type": "character",
            "owner_id": "pc2",
            "condition": "exhaustion",
            "count": 1,
            "level_before": 2,
            "level_after": 1,
        }
    ]
    assert target_character.status_effects == [
        {"effect_id": "char-exhaustion", "condition": "exhaustion", "level": 1}
    ]
    assert target_combatant.status_effects == [
        {"effect_id": "combat-exhaustion", "condition": "exhaustion", "level": 1}
    ]


def test_greater_restoration_removes_selected_condition_or_marked_effect(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"cleric": 9}
    caster.spell_slots["5"] = 3
    caster.gold = 300
    target = state.encounter.combatants["pc2"]
    target.status_effects = [
        {"effect_id": "charm", "condition": "charmed"},
        {"effect_id": "stone", "condition": "petrified"},
        {"effect_id": "fright", "condition": "frightened"},
        {"effect_id": "curse", "effect_markers": ["curse"]},
        {"effect_id": "ability-loss", "metadata": {"ability_score_reduction": True}},
    ]
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    condition_result = tools.perform_action(
        "pc1",
        "srd.greater_restoration",
        ["pc2"],
        {"slot_level": 5, "greater_restoration_choice": "charmed_or_petrified"},
        idempotency_key="greater-restoration-condition",
    )
    tools.economy.set("pc1", "action", 1)
    marker_result = tools.perform_action(
        "pc1",
        "srd.greater_restoration",
        ["pc2"],
        {"slot_level": 5, "greater_restoration_choice": "ability_score_reduction"},
        idempotency_key="greater-restoration-ability",
    )
    tools.economy.set("pc1", "action", 1)
    curse_result = tools.perform_action(
        "pc1",
        "srd.greater_restoration",
        ["pc2"],
        {"slot_level": 5, "greater_restoration_choice": "curse"},
        idempotency_key="greater-restoration-curse",
    )

    condition_change = next(
        change
        for change in condition_result["state_changes"]
        if change["type"] == "greater_restoration"
    )
    marker_change = next(
        change
        for change in marker_result["state_changes"]
        if change["type"] == "greater_restoration"
    )
    curse_change = next(
        change
        for change in curse_result["state_changes"]
        if change["type"] == "greater_restoration"
    )
    assert condition_change["removed"] == {"charmed": 1, "petrified": 1}
    assert marker_change["removed_markers"] == {"ability_score_reduction": 1}
    assert curse_change["removed_markers"] == {"curse": 1}
    assert {effect.get("effect_id") for effect in target.status_effects} == {"fright"}
    assert caster.spell_slots["5"] == 0
    assert caster.gold == 0


def test_greater_restoration_restores_hp_max_reduction(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc1"]
    caster.class_levels = {"cleric": 9}
    caster.spell_slots["5"] = 1
    caster.gold = 100
    target_character = state.characters["pc2"]
    target_combatant = state.encounter.combatants["pc2"]
    target_character.hp_max = 4
    target_character.hp_current = 4
    target_combatant.hp_max = 4
    target_combatant.hp_current = 4
    target_combatant.status_effects = [
        {
            "effect_id": "hp-drain",
            "effect_markers": ["hp_max_reduction"],
            "metadata": {"hp_max_reduction": 4},
        }
    ]
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.greater_restoration",
        ["pc2"],
        {"slot_level": 5, "greater_restoration_choice": "hp_max_reduction"},
        idempotency_key="greater-restoration-hp-max",
    )

    greater_restore = next(
        change for change in result["state_changes"] if change["type"] == "greater_restoration"
    )
    assert greater_restore["removed_markers"] == {"hp_max_reduction": 1}
    assert greater_restore["hp_max_restored"] == [
        {
            "owner_type": "character",
            "owner_id": "pc2",
            "amount": 4,
            "hp_max_before": 4,
            "hp_max_after": 8,
            "hp_current_before": 4,
            "hp_current_after": 4,
        },
        {
            "owner_type": "combatant",
            "owner_id": "pc2",
            "amount": 4,
            "hp_max_before": 4,
            "hp_max_after": 8,
            "hp_current_before": 4,
            "hp_current_after": 4,
        },
    ]
    assert target_character.hp_max == 8
    assert target_combatant.hp_max == 8
    assert target_combatant.status_effects == []


def test_max_hp_delta_can_follow_last_damage_taken(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    target = state.encounter.combatants["pc2"]
    action = ActionDefinition(
        id="test.drain",
        name="Drain",
        localization={"en": "Drain", "zh": "吸取"},
        source="test",
        rules_version="test",
        action_type="spell",
        action_economy="action",
        range={"normal_ft": 60},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "damage", "amount": 3, "damage_type": "necrotic"},
            {"type": "max_hp_delta", "amount_from": "-last_damage_taken"},
        ],
    )

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="pc1",
        targets=["pc2"],
    )

    assert result.success is True
    assert target.hp_max == 5
    assert target.hp_current == 1
    assert result.state_changes[-1]["amount"] == -3


def test_bless_records_passive_effect_modifiers(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    pc2 = state.encounter.combatants["pc2"]
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell("pc1", "srd.bless", ["pc2"], 1)

    assert result["success"] is True
    effect = pc2.status_effects[-1]
    assert effect["source_action_id"] == "srd.bless"
    assert effect["passive_modifiers"]["attack_roll_bonus_dice"] == "1d4"
    assert effect["concentration"] is True
    assert any(change["type"] == "passive_effect" for change in result["state_changes"])

    attack_result = tools.perform_action("pc2", "srd.shortsword_attack", ["goblin1"])
    attack_node = attack_result["node_results"]["automation[1]"]
    assert any(roll["expression"] == "1d4" for roll in attack_result["dice_rolls"])
    assert attack_node["passive_adjustment"] > 0
    assert attack_node["passive_sources"][0]["source_action_id"] == "srd.bless"


def test_multitarget_concentration_spell_keeps_new_targets(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell("pc1", "srd.bless", ["pc1", "pc2"], 1)

    assert result["success"] is True
    blessed_targets = {
        combatant_id
        for combatant_id, combatant in state.encounter.combatants.items()
        if any(effect.get("source_action_id") == "srd.bless" for effect in combatant.status_effects)
    }
    assert blessed_targets == {"pc1", "pc2"}


def test_new_concentration_spell_clears_previous_concentration_effects(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].spell_slots["1"] = 2
    pc2 = state.encounter.combatants["pc2"]
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    tools.cast_spell("pc1", "srd.bless", ["pc2"], 1)
    result = tools.cast_spell("pc1", "srd.shield_of_faith", ["pc2"], 1)

    source_ids = {effect["source_action_id"] for effect in pc2.status_effects}
    assert "srd.bless" not in source_ids
    assert "srd.shield_of_faith" in source_ids
    cleared = [
        change for change in result["state_changes"] if change["type"] == "concentration_cleared"
    ]
    assert cleared
    assert cleared[0]["removed"][0]["source_action_id"] == "srd.bless"


def test_world_concentration_spell_clears_previous_concentration_effects(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["pc2"].status_effects.append(
        {
            "effect_id": "old-bless",
            "source_action_id": "srd.bless",
            "applied_by": "pc1",
            "concentration": True,
            "passive_modifiers": {"attack_roll_bonus_dice": "1d4"},
        }
    )
    state.characters["pc1"].spell_slots["1"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell("pc1", "srd.detect_magic", [], 1)

    assert state.encounter.combatants["pc2"].status_effects == []
    assert state.world.active_effects[-1]["source_action_id"] == "srd.detect_magic"
    assert state.world.active_effects[-1]["concentration"] is True
    assert any(change["type"] == "concentration_cleared" for change in result["state_changes"])


def test_damage_triggers_failed_concentration_save_and_clears_effect(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["pc2"].status_effects.append(
        {
            "effect_id": "old-bless",
            "source_action_id": "srd.bless",
            "applied_by": "pc1",
            "concentration": True,
            "passive_modifiers": {"attack_roll_bonus_dice": "1d4"},
        }
    )
    action = _damage_action(60)

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="goblin1",
        targets=["pc1"],
    )

    concentration_change = [
        change for change in result.state_changes if change["type"] == "concentration_save"
    ][0]
    assert concentration_change["success"] is False
    assert concentration_change["dc"] == 30
    assert concentration_change["removed"][0]["source_action_id"] == "srd.bless"
    assert state.encounter.combatants["pc2"].status_effects == []


def test_successful_concentration_save_keeps_effect(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].abilities["con"] = 30
    state.encounter.combatants["pc2"].status_effects.append(
        {
            "effect_id": "old-bless",
            "source_action_id": "srd.bless",
            "applied_by": "pc1",
            "concentration": True,
            "passive_modifiers": {"attack_roll_bonus_dice": "1d4"},
        }
    )
    action = _damage_action(1)

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="goblin1",
        targets=["pc1"],
    )

    concentration_change = [
        change for change in result.state_changes if change["type"] == "concentration_save"
    ][0]
    assert concentration_change["success"] is True
    assert concentration_change["dc"] == 10
    assert concentration_change["removed"] == []
    assert state.encounter.combatants["pc2"].status_effects[0]["source_action_id"] == "srd.bless"


def test_eldritch_mind_grants_advantage_on_concentration_saves(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    warlock = state.characters["pc1"]
    warlock.class_levels = {"warlock": 1}
    warlock.feature_choices = {"warlock.eldritch_invocation": "eldritch_mind"}
    warlock.actions.append("srd.eldritch_mind")
    warlock.abilities["con"] = 30
    state.encounter.combatants["pc2"].status_effects.append(
        {
            "effect_id": "old-bless",
            "source_action_id": "srd.bless",
            "applied_by": "pc1",
            "concentration": True,
            "passive_modifiers": {"attack_roll_bonus_dice": "1d4"},
        }
    )
    action = _damage_action(1)

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="goblin1",
        targets=["pc1"],
    )

    concentration_change = [
        change for change in result.state_changes if change["type"] == "concentration_save"
    ][0]
    concentration_roll = result.dice_rolls[-1]
    assert concentration_change["success"] is True
    assert concentration_change["advantage"] == "advantage"
    assert concentration_change["advantage_sources"] == [
        {
            "source_action_id": "srd.eldritch_mind",
            "modifier": "concentration_save_advantage",
        }
    ]
    assert concentration_roll["advantage"] == "advantage"
    assert len(concentration_roll["dice"]) == 2
    assert state.encounter.combatants["pc2"].status_effects[0]["source_action_id"] == "srd.bless"


def test_agonizing_blast_adds_charisma_modifier_to_eldritch_blast_damage(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    warlock = state.characters["pc1"]
    warlock.class_levels = {"warlock": 2}
    warlock.abilities["cha"] = 18
    warlock.feature_choices = {
        "warlock.eldritch_invocation.agonizing_blast.cantrip": "srd.spell.eldritch_blast"
    }
    warlock.actions.extend(["srd.eldritch_blast", "srd.agonizing_blast"])
    state.encounter.combatants["goblin1"].armor_class = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell(
        "pc1",
        "srd.eldritch_blast",
        ["goblin1"],
        0,
        idempotency_key="agonizing-blast-eldritch-blast",
    )

    damage_change = [change for change in result["state_changes"] if change["type"] == "damage"][0]
    damage_roll = [roll for roll in result["dice_rolls"] if roll["expression"] == "1d10"][0]
    assert damage_change["passive_damage_bonus"] == 4
    assert damage_change["passive_sources"] == [
        {
            "source_action_id": "srd.agonizing_blast",
            "modifier": "warlock_agonizing_blast",
            "spell_id": "srd.spell.eldritch_blast",
            "amount": 4,
        }
    ]
    assert damage_change["amount"] == damage_roll["total"] + 4


def test_repelling_blast_pushes_large_or_smaller_target_on_hit(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    assert state.encounter.tactical_graph is not None
    state.encounter.tactical_graph["nodes"]["far"] = {
        "node_id": "far",
        "name": "Far",
        "tags": [],
        "capacity": None,
        "default_cover": "none",
        "terrain": "normal",
    }
    state.encounter.tactical_graph["edges"].append(
        {
            "source": "cover",
            "target": "far",
            "distance_ft": 10,
            "movement_cost": None,
            "line_of_sight": True,
            "cover": "none",
            "difficult_terrain": False,
        }
    )
    warlock = state.characters["pc1"]
    warlock.class_levels = {"warlock": 2}
    warlock.feature_choices = {
        "warlock.eldritch_invocation.repelling_blast.cantrip": "srd.spell.eldritch_blast"
    }
    warlock.actions.extend(["srd.eldritch_blast", "srd.repelling_blast"])
    state.encounter.combatants["goblin1"].armor_class = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([10, 4]),
    )

    result = tools.perform_action(
        "pc1",
        "srd.eldritch_blast",
        ["goblin1"],
        params={
            "slot_level": 0,
            "use_repelling_blast": True,
            "repelling_blast_to_position_node_id": "far",
        },
        idempotency_key="repelling-blast-hit",
    )

    repelling_change = next(
        change for change in result["state_changes"] if change["type"] == "repelling_blast"
    )
    assert result["success"] is True
    assert repelling_change["source_action_id"] == "srd.repelling_blast"
    assert repelling_change["from"] == "cover"
    assert repelling_change["to"] == "far"
    assert repelling_change["forced_movement_distance"] == 10
    assert state.encounter.combatants["goblin1"].position_node_id == "far"


def test_guidance_adds_passive_dice_to_ability_checks(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["pc1"].status_effects.append(
        {
            "effect_id": "guidance-test",
            "source_action_id": "srd.guidance",
            "passive_modifiers": {"ability_check_bonus_dice": "1d4"},
        }
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action("pc1", "srd.hide", [])

    check_node = result["node_results"]["automation[1]"]
    assert any(roll["expression"] == "1d4" for roll in result["dice_rolls"])
    assert check_node["passive_adjustment"] > 0
    assert check_node["passive_sources"][0]["source_action_id"] == "srd.guidance"


def test_petrified_target_has_resistance_to_all_automation_damage(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["pc1"].status_effects.append(
        {"effect_id": "petrified-test", "condition": "petrified"}
    )
    action = _damage_action(9)

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="goblin1",
        targets=["pc1"],
    )

    damage_change = [change for change in result.state_changes if change["type"] == "damage"][0]
    assert damage_change["amount"] == 9
    assert damage_change["applied"] == 4
    assert state.encounter.combatants["pc1"].hp_current == 6


def test_petrified_target_has_resistance_to_gm_damage(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["pc1"].status_effects.append(
        {"effect_id": "petrified-test", "condition": "petrified"}
    )
    tools = EngineTools(state, CompendiumLoader("rules_data").load(), AuditLog())

    result = tools.apply_damage("pc1", 9, "force", "test")

    assert result["applied"] == 4
    assert result["damage_type"] == "force"
    assert state.encounter.combatants["pc1"].hp_current == 6


def test_gm_damage_rejects_non_srd_damage_types_and_negative_amounts(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    audit = AuditLog()
    tools = EngineTools(state, CompendiumLoader("rules_data").load(), audit)

    with pytest.raises(ValueError, match="unknown damage type"):
        tools.apply_damage("pc1", 3, "plasma", "test")
    with pytest.raises(ValueError, match="damage amount cannot be negative"):
        tools.apply_damage("pc1", -1, "force", "test")

    assert state.encounter.combatants["pc1"].hp_current == 10
    assert audit.events == []


def test_gm_healing_rejects_negative_amounts(make_state) -> None:
    state = make_state()
    audit = AuditLog()
    tools = EngineTools(state, CompendiumLoader("rules_data").load(), audit)

    with pytest.raises(ValueError, match="healing amount cannot be negative"):
        tools.apply_healing("pc1", -1, "test")

    assert state.characters["pc1"].hp_current == 10
    assert audit.events == []


def test_petrified_target_is_immune_to_poisoned_condition_from_automation(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["pc1"].status_effects.append(
        {"effect_id": "petrified-test", "condition": "petrified"}
    )
    action = ActionDefinition(
        id="test.poisoned",
        name="Test Poisoned",
        localization={"en": "Test Poisoned", "zh": "测试中毒", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "condition", "condition": "poisoned"},
        ],
    )

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="goblin1",
        targets=["pc1"],
    )

    immune_change = [
        change for change in result.state_changes if change["type"] == "condition_immune"
    ][0]
    assert immune_change["condition"] == "poisoned"
    assert immune_change["immunity_sources"][0]["condition"] == "petrified"
    assert [effect["condition"] for effect in state.encounter.combatants["pc1"].status_effects] == [
        "petrified"
    ]


def test_petrified_target_is_immune_to_poisoned_condition_from_gm_tool(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["pc1"].status_effects.append(
        {"effect_id": "petrified-test", "condition": "petrified"}
    )
    tools = EngineTools(state, CompendiumLoader("rules_data").load(), AuditLog())

    result = tools.apply_condition("pc1", "poisoned", "test")

    assert result["applied"] is False
    assert result["immune"] is True
    assert [effect["condition"] for effect in state.encounter.combatants["pc1"].status_effects] == [
        "petrified"
    ]


def test_gm_condition_rejects_non_srd_conditions(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    audit = AuditLog()
    tools = EngineTools(state, CompendiumLoader("rules_data").load(), audit)

    with pytest.raises(ValueError, match="unknown condition"):
        tools.apply_condition("pc1", "bleeding-from-nowhere", "test")

    assert state.encounter.combatants["pc1"].status_effects == []
    assert audit.events == []


def test_exhaustion_condition_accumulates_and_level_six_kills(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    action = ActionDefinition(
        id="test.exhaustion",
        name="Test Exhaustion",
        localization={"en": "Test Exhaustion", "zh": "测试力竭", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "condition", "condition": "exhaustion"},
        ],
    )
    executor = AutomationExecutor(state, RollService(state), AuditLog())

    result = None
    for _ in range(6):
        result = executor.execute(action, actor_id="goblin1", targets=["pc1"])

    assert result is not None
    condition_change = [change for change in result.state_changes if change["type"] == "condition"][
        0
    ]
    death_change = [change for change in result.state_changes if change["type"] == "death"][0]
    assert condition_change["level_before"] == 5
    assert condition_change["level_after"] == 6
    assert death_change["reason"] == "exhaustion"
    assert state.characters["pc1"].status_effects[-1]["level"] == 6
    assert state.characters["pc1"].dead is True
    assert state.encounter.combatants["pc1"].dead is True
    assert state.encounter.combatants["pc1"].hp_current == 0


def _damage_action(amount: int, *, damage_type: str = "force") -> ActionDefinition:
    return ActionDefinition(
        id=f"test.damage.{amount}",
        name="Test Damage",
        localization={"en": "Test Damage", "zh": "测试伤害", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "damage", "amount": amount, "damage_type": damage_type},
        ],
        audit_label="Test Damage",
    )


def _attack_action(attack_bonus: int = 99) -> ActionDefinition:
    return ActionDefinition(
        id="test.attack",
        name="Test Attack",
        localization={"en": "Test Attack", "zh": "测试攻击", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={"normal_ft": 5},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "attack_roll", "attack_bonus": attack_bonus},
            {
                "type": "damage",
                "dice": "1d6",
                "damage_type": "force",
                "requires_hit": True,
            },
        ],
        audit_label="Test Attack",
    )


def _weapon_attack_action(attack_bonus: int = 99) -> ActionDefinition:
    return ActionDefinition(
        id="test.weapon_attack",
        name="Test Weapon Attack",
        localization={"en": "Test Weapon Attack", "zh": "测试武器攻击", "aliases": []},
        source="test",
        rules_version="test",
        action_type="weapon_attack",
        action_economy="none",
        range={"normal_ft": 5},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "attack_roll", "attack_bonus": attack_bonus},
            {
                "type": "damage",
                "dice": "1d6",
                "damage_type": "force",
                "requires_hit": True,
            },
        ],
        audit_label="Test Weapon Attack",
    )


def test_bane_subtracts_passive_dice_from_saving_throws(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].status_effects.append(
        {
            "effect_id": "bane-test",
            "source_action_id": "srd.bane",
            "passive_modifiers": {"saving_throw_penalty_dice": "1d4"},
        }
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action("pc1", "srd.sacred_flame", ["goblin1"])

    save_node = result["node_results"]["automation[1]"]
    assert any(roll["expression"] == "1d4" for roll in result["dice_rolls"])
    assert save_node["passive_adjustment"] < 0
    assert save_node["passive_sources"][0]["source_action_id"] == "srd.bane"


def test_passive_armor_class_minimum_changes_attack_resolution(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].status_effects.append(
        {
            "effect_id": "barkskin-test",
            "source_action_id": "srd.barkskin",
            "passive_modifiers": {"armor_class_minimum": 16},
        }
    )
    action = _attack_action(attack_bonus=0)

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="pc1",
        targets=["goblin1"],
    )

    attack_node = result.node_results["automation[1]"]
    assert attack_node["base_ac"] == 12
    assert attack_node["ac"] == 16
    assert attack_node["armor_class_sources"][0]["modifier"] == "armor_class_minimum"
    assert attack_node["hit"] is False


def test_draconic_resilience_sets_unarmored_base_ac(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"sorcerer": 3}
    state.characters["pc1"].subclasses = {"sorcerer": "draconic"}
    state.characters["pc1"].abilities["dex"] = 14
    state.characters["pc1"].abilities["cha"] = 16
    state.characters["pc1"].equipment = []
    state.characters["pc1"].armor_class = 10
    state.encounter.combatants["pc1"].armor_class = 10
    action = _attack_action(attack_bonus=0)

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="goblin1",
        targets=["pc1"],
    )

    attack_node = result.node_results["automation[1]"]
    assert attack_node["base_ac"] == 10
    assert attack_node["ac"] == 15
    assert attack_node["armor_class_sources"][0] == {
        "modifier": "draconic_resilience",
        "source_action_id": "srd.draconic_resilience",
        "formula": "10+dex_modifier+cha_modifier",
        "value": 15,
    }


def test_draconic_resilience_ac_does_not_apply_while_wearing_armor(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"sorcerer": 3}
    state.characters["pc1"].subclasses = {"sorcerer": "draconic"}
    state.characters["pc1"].abilities["dex"] = 14
    state.characters["pc1"].abilities["cha"] = 16
    state.characters["pc1"].equipment = ["srd.leather_armor"]
    state.characters["pc1"].armor_class = 11
    state.encounter.combatants["pc1"].armor_class = 11
    action = _attack_action(attack_bonus=0)

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="goblin1",
        targets=["pc1"],
    )

    attack_node = result.node_results["automation[1]"]
    assert attack_node["base_ac"] == 11
    assert attack_node["ac"] == 11
    assert not any(
        source.get("source_action_id") == "srd.draconic_resilience"
        for source in attack_node["armor_class_sources"]
    )


def test_draconic_elemental_affinity_adds_cha_to_one_matching_spell_damage_roll(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"sorcerer": 6}
    character.subclasses = {"sorcerer": "draconic"}
    character.abilities["cha"] = 16
    character.feature_choices = {"sorcerer.draconic.elemental_affinity": "fire"}
    state.encounter.combatants["goblin1"].hp_current = 30
    state.encounter.combatants["goblin1"].hp_max = 30
    action = ActionDefinition(
        id="test.draconic_fire_spell",
        name="Test Draconic Fire Spell",
        localization={"en": "Test Draconic Fire Spell", "zh": "测试龙族火焰法术", "aliases": []},
        source="test",
        rules_version="test",
        action_type="spell",
        action_economy="action",
        range={},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "damage", "amount": 5, "damage_type": "fire"},
            {"type": "damage", "amount": 5, "damage_type": "fire"},
        ],
    )

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="pc1",
        targets=["goblin1"],
    )

    damage_changes = [change for change in result.state_changes if change["type"] == "damage"]
    assert [change["amount"] for change in damage_changes] == [8, 5]
    assert damage_changes[0]["passive_damage_bonus"] == 3
    assert damage_changes[0]["passive_sources"] == [
        {
            "source_action_id": "srd.elemental_affinity",
            "modifier": "draconic_elemental_affinity",
            "damage_type": "fire",
            "amount": 3,
        }
    ]
    assert "passive_damage_bonus" not in damage_changes[1]


def test_draconic_elemental_affinity_grants_chosen_damage_resistance(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"sorcerer": 6}
    character.subclasses = {"sorcerer": "draconic"}
    character.feature_choices = {"sorcerer.draconic.elemental_affinity": "cold"}
    state.encounter.combatants["pc1"].hp_current = 20
    state.encounter.combatants["pc1"].hp_max = 20
    action = ActionDefinition(
        id="test.cold_damage",
        name="Test Cold Damage",
        localization={"en": "Test Cold Damage", "zh": "测试寒冷伤害", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "damage", "amount": 9, "damage_type": "cold"},
        ],
    )

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="goblin1",
        targets=["pc1"],
    )

    damage_change = next(change for change in result.state_changes if change["type"] == "damage")
    assert damage_change["amount"] == 9
    assert damage_change["applied"] == 4
    assert state.encounter.combatants["pc1"].hp_current == 16


def test_land_druid_natures_ward_grants_poisoned_immunity(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"druid": 10}
    character.subclasses = {"druid": "land"}
    character.actions.append("srd.natures_ward")
    action = ActionDefinition(
        id="test.poisoned_condition",
        name="Test Poisoned Condition",
        localization={"en": "Test Poisoned Condition", "zh": "测试中毒状态", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "condition", "condition": "poisoned"},
        ],
    )

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="goblin1",
        targets=["pc1"],
    )

    immune_change = next(
        change for change in result.state_changes if change["type"] == "condition_immune"
    )
    assert immune_change["condition"] == "poisoned"
    assert immune_change["immunity_sources"] == [
        {
            "source_action_id": "srd.natures_ward",
            "modifier": "druid_natures_ward_poisoned_immunity",
            "immune_condition": "poisoned",
        }
    ]
    assert not any(
        effect.get("condition") == "poisoned"
        for effect in state.encounter.combatants["pc1"].status_effects
    )


def test_land_druid_natures_ward_grants_current_land_damage_resistance(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"druid": 10}
    character.subclasses = {"druid": "land"}
    character.actions.append("srd.natures_ward")
    character.feature_choices = {"druid.land.current_land": "polar"}
    state.encounter.combatants["pc1"].hp_current = 20
    state.encounter.combatants["pc1"].hp_max = 20
    action = ActionDefinition(
        id="test.cold_damage",
        name="Test Cold Damage",
        localization={"en": "Test Cold Damage", "zh": "测试寒冷伤害", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "damage", "amount": 9, "damage_type": "cold"},
        ],
    )

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="goblin1",
        targets=["pc1"],
    )

    damage_change = next(change for change in result.state_changes if change["type"] == "damage")
    assert damage_change["amount"] == 9
    assert damage_change["applied"] == 4
    assert state.encounter.combatants["pc1"].hp_current == 16


def test_land_druid_natures_sanctuary_creates_srd_cube_world_effect(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"druid": 14}
    character.subclasses = {"druid": "land"}
    character.feature_choices = {"druid.land.current_land": "polar"}
    character.actions.extend(["srd.natures_ward", "srd.natures_sanctuary"])
    character.resources["srd.resource.wild_shape"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.natures_sanctuary",
        [],
        params={"natures_sanctuary_position_node_id": "cover"},
        idempotency_key="natures-sanctuary",
    )

    assert result["success"] is True
    assert character.resources["srd.resource.wild_shape"] == 0
    assert state.encounter.action_budgets["pc1"]["action"] == 0
    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.natures_sanctuary"
    assert effect["effect_type"] == "natures_sanctuary"
    assert effect["concentration"] is False
    assert effect["scope"] == {
        "shape": "cube",
        "size_ft": 15,
        "position_node_id": "cover",
        "range_ft": 120,
        "on_ground": True,
    }
    assert effect["duration"] == {"until": "duration_1_minute"}
    assert effect["metadata"] == {
        "spectral_trees_and_vines": True,
        "on_ground": True,
        "cube_size_ft": 15,
        "created_with_magic_action": True,
        "cost_resource": "srd.resource.wild_shape",
        "half_cover_for_caster_and_allies_in_area": True,
        "allies_gain_current_natures_ward_resistance_in_area": True,
        "current_natures_ward_resistance": "cold",
        "ends_if_caster_incapacitated_or_dies": True,
        "can_move_as_bonus_action": True,
        "move_distance_ft": 60,
        "range_from_caster_ft": 120,
        "position_node_id": "cover",
    }
    world_effect_change = next(
        change for change in result["state_changes"] if change["type"] == "world_effect"
    )
    assert world_effect_change["effect_type"] == "natures_sanctuary"
    assert world_effect_change["scope"] == effect["scope"]


def test_land_druid_natures_sanctuary_move_updates_active_cube(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"druid": 14}
    character.subclasses = {"druid": "land"}
    character.actions.append("srd.natures_sanctuary_move")
    state.world.active_effects.append(
        {
            "effect_id": "sanctuary",
            "source_action_id": "srd.natures_sanctuary",
            "applied_by": "pc1",
            "effect_type": "natures_sanctuary",
            "concentration": False,
            "scope": {
                "shape": "cube",
                "size_ft": 15,
                "position_node_id": "cover",
                "range_ft": 120,
                "on_ground": True,
            },
            "duration": {"until": "duration_1_minute"},
            "metadata": {"position_node_id": "cover"},
        }
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.natures_sanctuary_move",
        [],
        params={"natures_sanctuary_position_node_id": "back"},
        idempotency_key="natures-sanctuary-move",
    )

    assert result["success"] is True
    assert state.encounter.action_budgets["pc1"]["bonus_action"] == 0
    effect = state.world.active_effects[-1]
    assert effect["scope"]["position_node_id"] == "back"
    assert effect["metadata"]["position_node_id"] == "back"
    assert effect["metadata"]["last_moved_by_bonus_action"] is True
    move_change = next(
        change for change in result["state_changes"] if change["type"] == "natures_sanctuary_move"
    )
    assert move_change == {
        "type": "natures_sanctuary_move",
        "actor_id": "pc1",
        "effect_id": "sanctuary",
        "from": "cover",
        "to": "back",
        "path": "automation[0]",
    }


def test_land_druid_natures_sanctuary_rejects_out_of_range_before_cost(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    graph = state.encounter.tactical_graph
    assert graph is not None
    graph["nodes"]["far"] = {
        "node_id": "far",
        "name": "Far",
        "tags": [],
        "capacity": None,
        "default_cover": "none",
        "terrain": "normal",
    }
    graph["edges"].append(
        {
            "source": "back",
            "target": "far",
            "distance_ft": 100,
            "movement_cost": None,
            "line_of_sight": True,
            "cover": "none",
            "difficult_terrain": False,
        }
    )
    character = state.characters["pc1"]
    character.class_levels = {"druid": 14}
    character.subclasses = {"druid": "land"}
    character.actions.append("srd.natures_sanctuary")
    character.resources["srd.resource.wild_shape"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="within 120 feet"):
        tools.perform_action(
            "pc1",
            "srd.natures_sanctuary",
            [],
            params={"natures_sanctuary_position_node_id": "far"},
            idempotency_key="natures-sanctuary-too-far",
        )

    assert character.resources["srd.resource.wild_shape"] == 1
    assert state.encounter.action_budgets == {}
    assert state.world.active_effects == []


def test_land_druid_natures_sanctuary_move_requires_active_cube_before_bonus_action(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"druid": 14}
    character.subclasses = {"druid": "land"}
    character.actions.append("srd.natures_sanctuary_move")
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="active Cube"):
        tools.perform_action(
            "pc1",
            "srd.natures_sanctuary_move",
            [],
            params={"natures_sanctuary_position_node_id": "back"},
            idempotency_key="natures-sanctuary-move-no-cube",
        )

    assert state.encounter.action_budgets == {}


def test_land_druid_natures_sanctuary_move_rejects_over_sixty_feet_before_bonus_action(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    graph = state.encounter.tactical_graph
    assert graph is not None
    graph["nodes"]["far"] = {
        "node_id": "far",
        "name": "Far",
        "tags": [],
        "capacity": None,
        "default_cover": "none",
        "terrain": "normal",
    }
    graph["edges"].append(
        {
            "source": "back",
            "target": "far",
            "distance_ft": 70,
            "movement_cost": None,
            "line_of_sight": True,
            "cover": "none",
            "difficult_terrain": False,
        }
    )
    character = state.characters["pc1"]
    character.class_levels = {"druid": 14}
    character.subclasses = {"druid": "land"}
    character.actions.append("srd.natures_sanctuary_move")
    state.world.active_effects.append(
        {
            "effect_id": "sanctuary",
            "source_action_id": "srd.natures_sanctuary",
            "applied_by": "pc1",
            "effect_type": "natures_sanctuary",
            "concentration": False,
            "scope": {
                "shape": "cube",
                "size_ft": 15,
                "position_node_id": "cover",
                "range_ft": 120,
                "on_ground": True,
            },
            "duration": {"until": "duration_1_minute"},
            "metadata": {"position_node_id": "cover"},
        }
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="cannot exceed 60 feet"):
        tools.perform_action(
            "pc1",
            "srd.natures_sanctuary_move",
            [],
            params={"natures_sanctuary_position_node_id": "far"},
            idempotency_key="natures-sanctuary-move-too-far",
        )

    assert state.world.active_effects[-1]["scope"]["position_node_id"] == "cover"
    assert state.encounter.action_budgets == {}


def test_barbarian_unarmored_defense_sets_base_ac_and_allows_shield(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"barbarian": 1}
    state.characters["pc1"].abilities["dex"] = 14
    state.characters["pc1"].abilities["con"] = 16
    state.characters["pc1"].equipment = ["srd.shield"]
    state.characters["pc1"].armor_class = 10
    state.encounter.combatants["pc1"].armor_class = 10
    action = _attack_action(attack_bonus=0)

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="goblin1",
        targets=["pc1"],
    )

    attack_node = result.node_results["automation[1]"]
    assert attack_node["base_ac"] == 10
    assert attack_node["ac"] == 15
    assert attack_node["armor_class_sources"][0] == {
        "modifier": "barbarian_unarmored_defense",
        "source_action_id": "srd.barbarian_unarmored_defense",
        "formula": "10+dex_modifier+con_modifier",
        "value": 15,
    }


def test_barbarian_unarmored_defense_does_not_apply_while_wearing_armor(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"barbarian": 1}
    state.characters["pc1"].abilities["dex"] = 14
    state.characters["pc1"].abilities["con"] = 16
    state.characters["pc1"].equipment = ["srd.leather_armor"]
    state.characters["pc1"].armor_class = 11
    state.encounter.combatants["pc1"].armor_class = 11
    action = _attack_action(attack_bonus=0)

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="goblin1",
        targets=["pc1"],
    )

    attack_node = result.node_results["automation[1]"]
    assert attack_node["base_ac"] == 11
    assert attack_node["ac"] == 11
    assert not any(
        source.get("source_action_id") == "srd.barbarian_unarmored_defense"
        for source in attack_node["armor_class_sources"]
    )


def test_monk_unarmored_defense_sets_base_ac_without_armor_or_shield(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"monk": 1}
    state.characters["pc1"].abilities["dex"] = 16
    state.characters["pc1"].abilities["wis"] = 14
    state.characters["pc1"].equipment = []
    state.characters["pc1"].armor_class = 10
    state.encounter.combatants["pc1"].armor_class = 10
    action = _attack_action(attack_bonus=0)

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="goblin1",
        targets=["pc1"],
    )

    attack_node = result.node_results["automation[1]"]
    assert attack_node["base_ac"] == 10
    assert attack_node["ac"] == 15
    assert attack_node["armor_class_sources"][0] == {
        "modifier": "monk_unarmored_defense",
        "source_action_id": "srd.monk_unarmored_defense",
        "formula": "10+dex_modifier+wis_modifier",
        "value": 15,
    }


def test_monk_unarmored_defense_does_not_apply_while_wielding_shield(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"monk": 1}
    state.characters["pc1"].abilities["dex"] = 16
    state.characters["pc1"].abilities["wis"] = 14
    state.characters["pc1"].equipment = ["srd.shield"]
    state.characters["pc1"].armor_class = 10
    state.encounter.combatants["pc1"].armor_class = 10
    action = _attack_action(attack_bonus=0)

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="goblin1",
        targets=["pc1"],
    )

    attack_node = result.node_results["automation[1]"]
    assert attack_node["base_ac"] == 10
    assert attack_node["ac"] == 10
    assert not any(
        source.get("source_action_id") == "srd.monk_unarmored_defense"
        for source in attack_node["armor_class_sources"]
    )


def test_potent_cantrip_deals_half_damage_on_attack_cantrip_miss(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"wizard": 3}
    state.characters["pc1"].subclasses = {"wizard": "evocation"}
    compendium = CompendiumLoader("rules_data").load()

    result = AutomationExecutor(
        state,
        _FixedSingleDieRollService([1, 7]),
        AuditLog(),
    ).execute(
        compendium.action("srd.fire_bolt"),
        actor_id="pc1",
        targets=["goblin1"],
    )

    assert result.success is True
    assert result.node_results["automation[1]"]["hit"] is False
    damage_change = next(change for change in result.state_changes if change["type"] == "damage")
    assert damage_change["amount"] == 3
    assert damage_change["potent_cantrip"] == {
        "source_action_id": "srd.potent_cantrip",
        "trigger": "missed_attack",
        "target_id": "goblin1",
        "action_id": "srd.fire_bolt",
        "damage_node_type": "damage",
        "amount_before_half": 7,
        "amount_after_half": 3,
    }


def test_potent_cantrip_does_not_apply_to_non_evoker_attack_cantrip_miss(
    make_state,
) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"wizard": 3}
    compendium = CompendiumLoader("rules_data").load()

    result = AutomationExecutor(
        state,
        _FixedSingleDieRollService([1]),
        AuditLog(),
    ).execute(
        compendium.action("srd.fire_bolt"),
        actor_id="pc1",
        targets=["goblin1"],
    )

    assert result.success is True
    assert result.node_results["automation[1]"]["hit"] is False
    assert not any(change["type"] == "damage" for change in result.state_changes)


def test_potent_cantrip_deals_half_damage_on_successful_cantrip_save(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"wizard": 3}
    state.characters["pc1"].subclasses = {"wizard": "evocation"}
    compendium = CompendiumLoader("rules_data").load()

    result = AutomationExecutor(
        state,
        _FixedSingleDieRollService([20, 5]),
        AuditLog(),
    ).execute(
        compendium.action("srd.acid_splash"),
        actor_id="pc1",
        targets=["goblin1"],
    )

    assert result.success is True
    assert result.node_results["automation[1]"]["success"] is True
    damage_change = next(change for change in result.state_changes if change["type"] == "damage")
    assert damage_change["path"] == "automation[2].potent_cantrip[0]"
    assert damage_change["amount"] == 2
    assert damage_change["potent_cantrip"] == {
        "source_action_id": "srd.potent_cantrip",
        "trigger": "successful_save",
        "target_id": "goblin1",
        "action_id": "srd.acid_splash",
        "damage_node_type": "damage",
        "amount_before_half": 5,
        "amount_after_half": 2,
    }


def test_potent_cantrip_does_not_apply_to_non_evoker_successful_cantrip_save(
    make_state,
) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"wizard": 3}
    compendium = CompendiumLoader("rules_data").load()

    result = AutomationExecutor(
        state,
        _FixedSingleDieRollService([20]),
        AuditLog(),
    ).execute(
        compendium.action("srd.acid_splash"),
        actor_id="pc1",
        targets=["goblin1"],
    )

    assert result.success is True
    assert result.node_results["automation[1]"]["success"] is True
    assert not any(change["type"] == "damage" for change in result.state_changes)


def test_poisoned_attacker_has_attack_disadvantage(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["pc1"].status_effects.append(
        {"effect_id": "poisoned-test", "condition": "poisoned"}
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action("pc1", "srd.shortsword_attack", ["goblin1"])

    attack_roll = result["dice_rolls"][0]
    attack_node = result["node_results"]["automation[1]"]
    assert attack_roll["advantage"] == "disadvantage"
    assert attack_node["status_advantage"] == "disadvantage"
    assert attack_node["status_sources"][0]["condition"] == "poisoned"


def test_grappled_attacker_has_disadvantage_against_non_grappler(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["pc1"].status_effects.append(
        {
            "effect_id": "grappled-test",
            "condition": "grappled",
            "source_action_id": "test.grapple",
            "applied_by": "goblin1",
        }
    )
    action = _attack_action()

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="pc1",
        targets=["pc2"],
    )

    attack_roll = result.dice_rolls[0]
    attack_node = result.node_results["automation[1]"]
    assert attack_roll["advantage"] == "disadvantage"
    assert attack_node["status_advantage"] == "disadvantage"
    assert attack_node["status_sources"][0]["condition"] == "grappled"
    assert attack_node["status_sources"][0]["grappler_id"] == "goblin1"


def test_grappled_attacker_does_not_have_grapple_disadvantage_against_grappler(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["pc1"].status_effects.append(
        {
            "effect_id": "grappled-test",
            "condition": "grappled",
            "source_action_id": "test.grapple",
            "applied_by": "goblin1",
        }
    )
    action = _attack_action()

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="pc1",
        targets=["goblin1"],
    )

    attack_roll = result.dice_rolls[0]
    attack_node = result.node_results["automation[1]"]
    assert attack_roll["advantage"] is None
    assert attack_node["status_advantage"] is None
    assert attack_node["status_sources"] == []


def test_blinded_target_grants_attack_advantage(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].status_effects.append(
        {"effect_id": "blinded-test", "condition": "blinded"}
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action("pc1", "srd.shortsword_attack", ["goblin1"])

    attack_roll = result["dice_rolls"][0]
    attack_node = result["node_results"]["automation[1]"]
    assert attack_roll["advantage"] == "advantage"
    assert attack_node["status_advantage"] == "advantage"
    assert attack_node["status_sources"][0]["condition"] == "blinded"


def test_status_advantage_and_disadvantage_cancel(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["pc1"].status_effects.append(
        {"effect_id": "poisoned-test", "condition": "poisoned"}
    )
    state.encounter.combatants["goblin1"].status_effects.append(
        {"effect_id": "blinded-test", "condition": "blinded"}
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action("pc1", "srd.shortsword_attack", ["goblin1"])

    attack_roll = result["dice_rolls"][0]
    attack_node = result["node_results"]["automation[1]"]
    assert attack_roll["advantage"] is None
    assert attack_node["status_advantage"] is None
    assert {source["condition"] for source in attack_node["status_sources"]} == {
        "blinded",
        "poisoned",
    }


def test_prone_target_grants_nearby_attack_advantage(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].status_effects.append(
        {"effect_id": "prone-test", "condition": "prone"}
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action("pc1", "srd.shortsword_attack", ["goblin1"])

    attack_roll = result["dice_rolls"][0]
    attack_node = result["node_results"]["automation[1]"]
    assert attack_node["distance_ft"] == 5
    assert attack_roll["advantage"] == "advantage"
    assert attack_node["status_sources"][0]["condition"] == "prone"


def test_prone_target_causes_ranged_attack_disadvantage(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].position_node_id = "back"
    state.encounter.combatants["goblin1"].status_effects.append(
        {"effect_id": "prone-test", "condition": "prone"}
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action("pc1", "srd.fire_bolt", ["goblin1"])

    attack_roll = result["dice_rolls"][0]
    attack_node = result["node_results"]["automation[1]"]
    assert attack_node["distance_ft"] == 35
    assert attack_roll["advantage"] == "disadvantage"
    assert attack_node["status_sources"][0]["condition"] == "prone"


def test_paralyzed_target_hit_within_five_feet_is_critical(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].status_effects.append(
        {"effect_id": "paralyzed-test", "condition": "paralyzed"}
    )
    action = _attack_action()

    result = AutomationExecutor(state, RollService(state), AuditLog()).execute(
        action,
        actor_id="pc1",
        targets=["goblin1"],
    )

    attack_node = result.node_results["automation[1]"]
    damage_rolls = [roll for roll in result.dice_rolls if roll["expression"] == "1d6"]
    assert attack_node["distance_ft"] == 5
    assert attack_node["hit"] is True
    assert attack_node["critical"] is True
    assert attack_node["auto_critical_sources"][0]["condition"] == "paralyzed"
    assert len(damage_rolls) == 2


def test_champion_improved_critical_scores_weapon_critical_on_natural_19(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.rng_seed = 30
    state.characters["pc1"].class_levels = {"fighter": 3}
    state.characters["pc1"].subclasses = {"fighter": "champion"}
    state.encounter.combatants["goblin1"].armor_class = 30
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.longsword_attack",
        ["goblin1"],
        idempotency_key="champion-natural-19",
    )

    attack_node = result["node_results"]["automation[1]"]
    damage_rolls = [roll for roll in result["dice_rolls"] if roll["expression"] == "1d8+2"]
    assert attack_node["natural"] == 19
    assert attack_node["hit"] is True
    assert attack_node["critical"] is True
    assert attack_node["critical_threshold"] == 19
    assert attack_node["critical_threshold_sources"][0]["source_action_id"] == (
        "srd.improved_critical"
    )
    assert len(damage_rolls) == 2


def test_champion_superior_critical_scores_weapon_critical_on_natural_18(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"fighter": 15}
    state.characters["pc1"].subclasses = {"fighter": "champion"}
    state.encounter.combatants["goblin1"].armor_class = 30
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([18, 4, 5]),
    )

    result = tools.perform_action(
        "pc1",
        "srd.longsword_attack",
        ["goblin1"],
        idempotency_key="champion-natural-18",
    )

    attack_node = result["node_results"]["automation[1]"]
    damage_rolls = [roll for roll in result["dice_rolls"] if roll["expression"] == "1d8+2"]
    assert attack_node["natural"] == 18
    assert attack_node["hit"] is True
    assert attack_node["critical"] is True
    assert attack_node["critical_threshold"] == 18
    assert attack_node["critical_threshold_sources"][0]["source_action_id"] == (
        "srd.superior_critical"
    )
    assert len(damage_rolls) == 2


def test_champion_before_superior_critical_does_not_crit_on_natural_18(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"fighter": 14}
    state.characters["pc1"].subclasses = {"fighter": "champion"}
    state.encounter.combatants["goblin1"].armor_class = 30
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(
        state,
        compendium,
        AuditLog(),
        roll_service=_FixedSingleDieRollService([18]),
    )

    result = tools.perform_action(
        "pc1",
        "srd.longsword_attack",
        ["goblin1"],
        idempotency_key="champion-level-14-natural-18",
    )

    attack_node = result["node_results"]["automation[1]"]
    assert attack_node["natural"] == 18
    assert attack_node["hit"] is False
    assert attack_node["critical"] is False
    assert attack_node["critical_threshold"] == 19
    assert attack_node["critical_threshold_sources"][0]["source_action_id"] == (
        "srd.improved_critical"
    )
    assert not any(change["type"] == "damage" for change in result["state_changes"])


def test_fighter_without_champion_does_not_crit_on_natural_19(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.rng_seed = 30
    state.characters["pc1"].class_levels = {"fighter": 3}
    state.encounter.combatants["goblin1"].armor_class = 30
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.longsword_attack",
        ["goblin1"],
        idempotency_key="fighter-natural-19",
    )

    attack_node = result["node_results"]["automation[1]"]
    assert attack_node["natural"] == 19
    assert attack_node["hit"] is False
    assert attack_node["critical"] is False
    assert attack_node["critical_threshold"] == 20
    assert attack_node["critical_threshold_sources"] == []
    assert not any(change["type"] == "damage" for change in result["state_changes"])


def test_remarkable_athlete_moves_half_speed_after_critical_hit(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.rng_seed = 30
    state.characters["pc1"].class_levels = {"fighter": 3}
    state.characters["pc1"].subclasses = {"fighter": "champion"}
    state.encounter.combatants["goblin1"].armor_class = 30
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action(
        "pc1",
        "srd.longsword_attack",
        ["goblin1"],
        params={"remarkable_athlete_to_position_node_id": "cover"},
        idempotency_key="remarkable-athlete-move",
    )

    move_change = next(
        change
        for change in result["state_changes"]
        if change["type"] == "move" and change.get("feature") == "remarkable_athlete"
    )
    assert result["node_results"]["automation[1]"]["critical"] is True
    assert state.encounter.combatants["pc1"].position_node_id == "cover"
    assert move_change["source_action_id"] == "srd.remarkable_athlete"
    assert move_change["from"] == "front"
    assert move_change["to"] == "cover"
    assert move_change["movement_cost"] == 5
    assert move_change["movement_limit"] == 15
    assert move_change["opportunity_attack_triggers"] == []
    assert state.encounter.action_budgets["pc1"]["movement_used"] == 5


def test_remarkable_athlete_rejects_over_half_speed_before_spending_action(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.rng_seed = 30
    state.characters["pc1"].class_levels = {"fighter": 3}
    state.characters["pc1"].subclasses = {"fighter": "champion"}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(
        AutomationError,
        match="Remarkable Athlete movement cannot exceed half Speed",
    ):
        tools.perform_action(
            "pc1",
            "srd.longsword_attack",
            ["goblin1"],
            params={"remarkable_athlete_to_position_node_id": "back"},
            idempotency_key="remarkable-athlete-too-far",
        )

    assert state.encounter.action_budgets == {}


def test_restrained_target_has_dex_save_disadvantage(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].status_effects.append(
        {"effect_id": "restrained-test", "condition": "restrained"}
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action("pc1", "srd.sacred_flame", ["goblin1"])

    save_roll = result["dice_rolls"][0]
    save_node = result["node_results"]["automation[1]"]
    assert save_roll["advantage"] == "disadvantage"
    assert save_node["status_advantage"] == "disadvantage"
    assert save_node["status_sources"][0]["condition"] == "restrained"


def test_paralyzed_target_auto_fails_dex_saving_throw(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].status_effects.append(
        {"effect_id": "paralyzed-test", "condition": "paralyzed"}
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action("pc1", "srd.sacred_flame", ["goblin1"])

    save_node = result["node_results"]["automation[1]"]
    assert save_node["auto_failed"] is True
    assert save_node["status_sources"][0]["condition"] == "paralyzed"
    assert "1d20" not in {roll["expression"].split("+")[0] for roll in result["dice_rolls"]}
    assert any(change["type"] == "damage" for change in result["state_changes"])


def test_poisoned_actor_has_ability_check_disadvantage(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["pc1"].status_effects.append(
        {"effect_id": "poisoned-test", "condition": "poisoned"}
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.perform_action("pc1", "srd.hide", [])

    check_roll = result["dice_rolls"][0]
    check_node = result["node_results"]["automation[1]"]
    assert check_roll["advantage"] == "disadvantage"
    assert check_node["status_advantage"] == "disadvantage"
    assert check_node["status_sources"][0]["condition"] == "poisoned"


def test_incapacitating_condition_blocks_actions_before_budget_spend(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["pc1"].status_effects.append(
        {"effect_id": "stunned-test", "condition": "stunned"}
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="cannot take action while stunned"):
        tools.perform_action("pc1", "srd.shortsword_attack", ["goblin1"])

    assert state.encounter.action_budgets == {}


def test_charmed_actor_cannot_target_charmer_with_harmful_action(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["pc1"].status_effects.append(
        {
            "effect_id": "charmed-test",
            "condition": "charmed",
            "source_action_id": "test.charm",
            "applied_by": "goblin1",
        }
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="cannot target the charmer"):
        tools.perform_action("pc1", "srd.shortsword_attack", ["goblin1"])

    assert state.encounter.action_budgets == {}


def test_charmed_target_gate_matches_charmer_entity_id(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.monsters["goblin_entity"] = Monster(
        id="goblin_entity",
        name="Goblin",
        abilities={"str": 8, "dex": 14, "con": 10, "int": 10, "wis": 8, "cha": 8},
        hp_current=7,
        hp_max=7,
        armor_class=12,
    )
    state.encounter.combatants["goblin1"].entity_id = "goblin_entity"
    state.encounter.combatants["pc1"].status_effects.append(
        {
            "effect_id": "charmed-test",
            "condition": "charmed",
            "source_action_id": "test.charm",
            "applied_by": "goblin_entity",
        }
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="cannot target the charmer"):
        tools.perform_action("pc1", "srd.shortsword_attack", ["goblin1"])

    assert state.encounter.action_budgets == {}


def test_incapacitating_condition_blocks_bonus_action_before_slot_spend(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].spell_slots["1"] = 1
    state.encounter.combatants["pc1"].status_effects.append(
        {"effect_id": "paralyzed-test", "condition": "paralyzed"}
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="cannot take bonus_action while paralyzed"):
        tools.cast_spell("pc1", "srd.healing_word", ["pc2"], 1)

    assert state.characters["pc1"].spell_slots["1"] == 1


def test_restrained_actor_cannot_move(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["pc1"].status_effects.append(
        {"effect_id": "restrained-test", "condition": "restrained"}
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(AutomationError, match="cannot move while restrained"):
        tools.move("pc1", to_position_node_id="cover")

    assert state.encounter.combatants["pc1"].position_node_id == "front"


def test_detect_magic_records_world_effect(make_state) -> None:
    state = make_state()
    state.characters["pc1"].spell_slots["1"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.cast_spell("pc1", "srd.detect_magic", [], 1)

    assert result["success"] is True
    effect = state.world.active_effects[-1]
    assert effect["source_action_id"] == "srd.detect_magic"
    assert effect["effect_type"] == "detect_magic"
    assert effect["scope"]["radius_ft"] == 30
    assert any(change["type"] == "world_effect" for change in result["state_changes"])


def _fixed_damage_action(action_id: str, *, amount: int) -> ActionDefinition:
    return ActionDefinition(
        id=action_id,
        name="Fixed Damage",
        localization={"en": "Fixed Damage", "zh": "固定伤害", "aliases": []},
        source="test",
        rules_version="test",
        action_type="test",
        action_economy="none",
        range={"normal_ft": 120},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "damage", "amount": amount, "damage_type": "force"},
        ],
    )

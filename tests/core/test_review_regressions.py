from __future__ import annotations

import pytest

from dnd_llm.core.automation.executor import AutomationError
from dnd_llm.core.compendium.loader import CompendiumLoader
from dnd_llm.core.dice import RollService
from dnd_llm.core.models import Combatant, Monster
from dnd_llm.core.persistence import AuditLog
from dnd_llm.core.rules.death import roll_death_save
from dnd_llm.core.rules.rests import ARCANE_RECOVERY_RESOURCE
from dnd_llm.core.tools import EngineTools


def test_zero_hp_actor_is_rejected_before_action_execution(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].hp_current = 0
    state.characters["pc1"].dead = True
    state.encounter.combatants["pc1"].hp_current = 0
    state.encounter.combatants["pc1"].dead = True
    tools = EngineTools(state, CompendiumLoader("rules_data").load(), AuditLog())

    with pytest.raises(AutomationError, match="actor is dead"):
        tools.perform_action(
            "pc1",
            "srd.shortsword_attack",
            ["goblin1"],
            idempotency_key="dead-actor-attack",
        )


def test_normal_healing_rejects_dead_target_and_clears_death_saves_on_recovery(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    caster = state.characters["pc2"]
    caster.spell_slots = {"1": 1}
    target = state.characters["pc1"]
    combatant = state.encounter.combatants["pc1"]
    for entity in (target, combatant):
        entity.hp_current = 0
        entity.dead = True
        entity.death_save_failures = 3
    tools = EngineTools(state, CompendiumLoader("rules_data").load(), AuditLog())

    with pytest.raises(AutomationError, match="dead creatures cannot regain"):
        tools.cast_spell(
            "pc2",
            "srd.cure_wounds",
            ["pc1"],
            1,
            idempotency_key="heal-dead-target",
        )
    assert caster.spell_slots == {"1": 1}

    for entity in (target, combatant):
        entity.dead = False
        entity.stable = False
        entity.death_save_failures = 2
    result = tools.cast_spell(
        "pc2",
        "srd.cure_wounds",
        ["pc1"],
        1,
        idempotency_key="heal-dying-target",
    )

    assert result["success"] is True
    assert target.hp_current > 0
    assert target.death_save_successes == 0
    assert target.death_save_failures == 0
    assert target.stable is False
    assert target.dead is False
    assert combatant.death_save_failures == 0


def test_combatant_damage_syncs_to_backing_monster(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    combatant = state.encounter.combatants["goblin1"]
    state.monsters["goblin1"] = Monster(
        id="goblin1",
        name="Goblin",
        abilities={"str": 8, "dex": 14, "con": 10, "int": 10, "wis": 8, "cha": 8},
        hp_current=combatant.hp_current,
        hp_max=combatant.hp_max,
        armor_class=combatant.armor_class,
    )
    tools = EngineTools(state, CompendiumLoader("rules_data").load(), AuditLog())

    tools.apply_hazard(
        ["goblin1"],
        "srd.falling_10ft",
        {"source": "map"},
        idempotency_key="monster-hp-sync",
    )

    assert state.monsters["goblin1"].hp_current == combatant.hp_current
    assert combatant.hp_current < combatant.hp_max


def test_zombie_undead_fortitude_is_resolved_when_damage_drops_it_to_zero(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["zombie1"] = Combatant(
        id="zombie1",
        entity_id="zombie1",
        name="Zombie",
        side="monsters",
        hp_current=1,
        hp_max=15,
        armor_class=8,
        abilities={"con": 16},
        position_node_id="front",
        traits=["undead_fortitude"],
    )
    tools = EngineTools(state, CompendiumLoader("rules_data").load(), AuditLog())

    result = tools.apply_hazard(
        ["zombie1"],
        "srd.falling_10ft",
        {"source": "map"},
        idempotency_key="zombie-undead-fortitude",
    )

    fortitude = next(
        change for change in result["state_changes"] if change["type"] == "undead_fortitude"
    )
    assert fortitude["dc"] >= 6
    assert fortitude["damage_type"] == "bludgeoning"


def test_wolf_pack_tactics_trait_grants_attack_advantage(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    for wolf_id in ("wolf1", "wolf2"):
        state.encounter.combatants[wolf_id] = Combatant(
            id=wolf_id,
            entity_id=wolf_id,
            name="Wolf",
            side="monsters",
            hp_current=11,
            hp_max=11,
            armor_class=12,
            abilities={"str": 14, "dex": 15, "con": 12, "int": 3, "wis": 12, "cha": 6},
            position_node_id="front",
            actions=["srd.wolf_bite"],
            traits=["pack_tactics"],
        )
    tools = EngineTools(state, CompendiumLoader("rules_data").load(), AuditLog())

    result = tools.perform_action(
        "wolf1",
        "srd.wolf_bite",
        ["pc1"],
        idempotency_key="wolf-pack-tactics",
    )

    attack = result["node_results"]["automation[1]"]
    assert any(source.get("modifier") == "pack_tactics" for source in attack["status_sources"])


def test_failed_short_rest_rolls_back_character_rng_and_audit(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"wizard": 1}
    character.hp_current = 1
    character.hit_dice = {"d6": 1}
    character.resources[ARCANE_RECOVERY_RESOURCE] = 1
    character.spell_slots = {"1": 0}
    character.spell_slots_max = {"1": 2}
    audit = AuditLog()
    tools = EngineTools(state, CompendiumLoader("rules_data").load(), audit)
    before = character.to_dict()

    with pytest.raises(ValueError, match="Arcane Recovery"):
        tools.short_rest(
            "pc1",
            {"d6": 1},
            arcane_recovery_slots={"2": 1},
            idempotency_key="short-rest-rollback",
        )

    assert character.to_dict() == before
    assert state.roll_counter == 0
    assert state.event_counter == 0
    assert audit.events == []


def test_stable_character_cannot_roll_another_death_save(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.hp_current = 0
    character.stable = True

    with pytest.raises(ValueError, match="stable creatures"):
        roll_death_save(character, RollService(state))

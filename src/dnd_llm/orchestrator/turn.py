from __future__ import annotations

from typing import Any

from ..core.dice import RollService
from ..core.models import Character, Combatant, Encounter, GameState
from ..core.persistence import AuditLog
from ..core.rules.class_features import (
    UNCANNY_METABOLISM_RESOURCE,
    has_barbarian_feature,
    has_fighter_champion_feature,
    has_monk_feature,
    has_rogue_thief_feature,
    monk_martial_arts_die,
    monk_perfect_focus_applies,
)

FOCUS_POINTS_RESOURCE = "srd.resource.focus_points"
THIEFS_REFLEXES_ACTION_ID = "srd.thiefs_reflexes"


def roll_initiative(state: GameState, audit_log: AuditLog) -> list[str]:
    if state.encounter is None:
        raise ValueError("initiative requires an encounter")
    roll_service = RollService(state)
    scored: list[tuple[int, str, list[str], dict[str, object]]] = []
    uncanny_metabolism_results: list[dict[str, object]] = []
    uncanny_metabolism_rolls: list[dict[str, object]] = []
    perfect_focus_results: list[dict[str, object]] = []
    for group_key, combatant_ids in _initiative_groups(state).items():
        modifier, modifier_sources = _initiative_modifier(state, combatant_ids)
        advantage, advantage_sources = _initiative_advantage(state, combatant_ids)
        roll = roll_service.roll(_initiative_expression(modifier), advantage=advantage)
        scored.append(
            (
                roll.total,
                group_key,
                combatant_ids,
                roll.to_dict()
                | {
                    "initiative_modifier": modifier,
                    "initiative_modifier_sources": modifier_sources,
                    "initiative_advantage_sources": advantage_sources,
                },
            )
        )
        for combatant_id in combatant_ids:
            uncanny_metabolism = _apply_uncanny_metabolism(
                state,
                combatant_id,
                roll_service,
            )
            if uncanny_metabolism is None:
                perfect_focus = _apply_perfect_focus(state, combatant_id)
                if perfect_focus is not None:
                    perfect_focus_results.append(perfect_focus)
                continue
            uncanny_metabolism_results.append(uncanny_metabolism)
            healing_roll = uncanny_metabolism.get("healing_roll")
            if isinstance(healing_roll, dict):
                uncanny_metabolism_rolls.append(healing_roll)
    scored.sort(key=lambda item: (-item[0], item[1]))
    initiative_entries, thiefs_reflexes_results = _initiative_entries_with_thiefs_reflexes(
        state,
        scored,
    )
    state.encounter.initiative_order = [
        combatant_id
        for _, _, combatant_ids, _ in initiative_entries
        for combatant_id in combatant_ids
    ]
    state.encounter.turn_index = 0
    state.encounter.round_number = 1
    audit_log.append(
        state,
        idempotency_key=f"initiative:{state.event_counter}",
        tool_name="orchestrator.roll_initiative",
        tool_result={
            "initiative_order": state.encounter.initiative_order,
            "groups": [
                {
                    "group_key": group_key,
                    "combatant_ids": combatant_ids,
                    "initiative": score,
                    "initiative_modifier": roll_dict["initiative_modifier"],
                    "initiative_modifier_sources": roll_dict["initiative_modifier_sources"],
                    "initiative_advantage_sources": roll_dict["initiative_advantage_sources"],
                }
                for score, group_key, combatant_ids, roll_dict in scored
            ],
            "uncanny_metabolism": uncanny_metabolism_results,
            "perfect_focus": perfect_focus_results,
            "thiefs_reflexes": thiefs_reflexes_results,
        },
        dice_rolls=[roll for _, _, _, roll in scored] + uncanny_metabolism_rolls,
    )
    return state.encounter.initiative_order


def _apply_uncanny_metabolism(
    state: GameState,
    combatant_id: str,
    roll_service: RollService,
) -> dict[str, object] | None:
    if state.encounter is None:
        return None
    combatant = state.encounter.combatants[combatant_id]
    character = state.characters.get(combatant.entity_id) or state.characters.get(combatant.id)
    if character is None or not has_monk_feature(character, level=2):
        return None
    uses_before = int(character.resources.get(UNCANNY_METABOLISM_RESOURCE, 1))
    if uses_before <= 0:
        return None
    monk_level = int(character.class_levels.get("monk", 0))
    focus_before = max(0, int(character.resources.get(FOCUS_POINTS_RESOURCE, monk_level)))
    focus_after = monk_level
    character_hp_before = int(character.hp_current)
    combatant_hp_before = int(combatant.hp_current)
    can_restore_focus = focus_before < focus_after
    can_heal_character = character_hp_before < int(character.hp_max)
    can_heal_combatant = combatant_hp_before < int(combatant.hp_max)
    if not (can_restore_focus or can_heal_character or can_heal_combatant):
        return None
    die = monk_martial_arts_die(character)
    roll = roll_service.roll(f"1{die}")
    healing = monk_level + roll.total
    character.resources[FOCUS_POINTS_RESOURCE] = focus_after
    character.resources[UNCANNY_METABOLISM_RESOURCE] = uses_before - 1
    character.hp_current = min(int(character.hp_max), character_hp_before + healing)
    combatant.hp_current = min(int(combatant.hp_max), combatant_hp_before + healing)
    return {
        "combatant_id": combatant_id,
        "character_id": character.id,
        "source_action_id": "srd.uncanny_metabolism",
        "resource": UNCANNY_METABOLISM_RESOURCE,
        "resource_before": uses_before,
        "resource_after": uses_before - 1,
        "focus_before": focus_before,
        "focus_after": focus_after,
        "martial_arts_die": die,
        "healing_roll": roll.to_dict(),
        "healing_roll_total": roll.total,
        "healing": healing,
        "character_hp_before": character_hp_before,
        "character_hp_after": character.hp_current,
        "combatant_hp_before": combatant_hp_before,
        "combatant_hp_after": combatant.hp_current,
    }


def _apply_perfect_focus(state: GameState, combatant_id: str) -> dict[str, object] | None:
    if state.encounter is None:
        return None
    combatant = state.encounter.combatants[combatant_id]
    character = state.characters.get(combatant.entity_id) or state.characters.get(combatant.id)
    if character is None or not monk_perfect_focus_applies(character):
        return None
    monk_level = int(character.class_levels.get("monk", 0))
    focus_before = max(0, int(character.resources.get(FOCUS_POINTS_RESOURCE, monk_level)))
    focus_after = min(monk_level, 4)
    if focus_before > 3 or focus_before >= focus_after:
        return None
    character.resources[FOCUS_POINTS_RESOURCE] = focus_after
    return {
        "combatant_id": combatant_id,
        "character_id": character.id,
        "source_action_id": "srd.perfect_focus",
        "resource": FOCUS_POINTS_RESOURCE,
        "resource_before": focus_before,
        "resource_after": focus_after,
        "requires_uncanny_metabolism_not_used": True,
    }


def _initiative_entries_with_thiefs_reflexes(
    state: GameState,
    scored: list[tuple[int, str, list[str], dict[str, object]]],
) -> tuple[list[tuple[int, str, list[str], dict[str, object]]], list[dict[str, object]]]:
    if state.encounter is None:
        return scored, []
    entries: list[tuple[int, str, list[str], dict[str, object]]] = []
    results: list[dict[str, object]] = []
    for score, group_key, combatant_ids, roll_dict in scored:
        entries.append((score, group_key, combatant_ids, roll_dict))
        for combatant_id in combatant_ids:
            combatant = state.encounter.combatants.get(combatant_id)
            if combatant is None:
                continue
            source = _initiative_source(state, combatant)
            if not isinstance(source, Character) or not has_rogue_thief_feature(
                source,
                level=17,
            ):
                continue
            second_turn_initiative = score - 10
            entries.append(
                (
                    second_turn_initiative,
                    f"{group_key}:thiefs_reflexes:{combatant_id}",
                    [combatant_id],
                    {},
                )
            )
            results.append(
                {
                    "combatant_id": combatant_id,
                    "character_id": source.id,
                    "source_action_id": THIEFS_REFLEXES_ACTION_ID,
                    "normal_initiative": score,
                    "second_turn_initiative": second_turn_initiative,
                    "initiative_penalty": -10,
                    "round": 1,
                }
            )
    entries.sort(key=lambda item: (-item[0], item[1]))
    return entries, results


def advance_turn(encounter: Encounter) -> str | None:
    if not encounter.initiative_order:
        return None
    encounter.turn_index = (encounter.turn_index + 1) % len(encounter.initiative_order)
    if encounter.turn_index == 0:
        encounter.round_number += 1
        if encounter.round_number > 1:
            _remove_first_round_extra_turns(encounter)
    return encounter.current_combatant_id


def _remove_first_round_extra_turns(encounter: Encounter) -> None:
    seen: set[str] = set()
    pruned: list[str] = []
    for combatant_id in encounter.initiative_order:
        if combatant_id in seen:
            continue
        seen.add(combatant_id)
        pruned.append(combatant_id)
    if len(pruned) == len(encounter.initiative_order):
        return
    current = encounter.current_combatant_id
    encounter.initiative_order = pruned
    encounter.turn_index = pruned.index(current) if current in pruned else 0


def _initiative_groups(state: GameState) -> dict[str, list[str]]:
    if state.encounter is None:
        return {}
    groups: dict[str, list[str]] = {}
    for combatant_id, combatant in state.encounter.combatants.items():
        if combatant.side == "party":
            group_key = f"combatant:{combatant_id}"
        else:
            group_key = f"monster:{combatant.side}:{combatant.name.casefold()}"
        groups.setdefault(group_key, []).append(combatant_id)
    for combatant_ids in groups.values():
        combatant_ids.sort()
    return groups


def _initiative_modifier(state: GameState, combatant_ids: list[str]) -> tuple[int, list[str]]:
    if state.encounter is None or not combatant_ids:
        return 0, []
    combatant = state.encounter.combatants[combatant_ids[0]]
    source = _initiative_source(state, combatant)
    dexterity = int(getattr(source, "abilities", {}).get("dex", 10))
    modifier = (dexterity - 10) // 2
    sources = [f"dex:{modifier}"]
    feats = getattr(source, "feats", [])
    if isinstance(source, Character) and "alert" in feats:
        proficiency_bonus = int(source.proficiency_bonus)
        modifier += proficiency_bonus
        sources.append(f"alert:{proficiency_bonus}")
    return modifier, sources


def _initiative_advantage(
    state: GameState, combatant_ids: list[str]
) -> tuple[str | None, list[str]]:
    if state.encounter is None or not combatant_ids:
        return None, []
    combatant = state.encounter.combatants[combatant_ids[0]]
    source = _initiative_source(state, combatant)
    sources: list[str] = []
    if isinstance(source, Character) and has_barbarian_feature(source, level=7):
        sources.append("feral_instinct")
    if isinstance(source, Character) and has_fighter_champion_feature(source, level=3):
        sources.append("remarkable_athlete")
    sources.extend(_passive_initiative_advantage_sources(state, combatant))
    return ("advantage" if sources else None), sources


def _initiative_source(state: GameState, combatant: Combatant) -> Character | Combatant:
    return (
        state.characters.get(combatant.entity_id) or state.characters.get(combatant.id) or combatant
    )


def _passive_initiative_advantage_sources(state: GameState, combatant: Combatant) -> list[str]:
    sources: list[str] = []
    for effect in _initiative_status_effects(state, combatant):
        modifiers = effect.get("passive_modifiers", {})
        if not isinstance(modifiers, dict) or modifiers.get("initiative_advantage") is not True:
            continue
        source = modifiers.get("initiative_advantage_source")
        if not isinstance(source, str) or not source:
            source = effect.get("source_action_id") or effect.get("effect_id")
        if isinstance(source, str) and source not in sources:
            sources.append(source)
    return sources


def _initiative_status_effects(state: GameState, combatant: Combatant) -> list[dict[str, Any]]:
    effects = list(combatant.status_effects)
    backing = state.characters.get(combatant.entity_id) or state.characters.get(combatant.id)
    if backing is not None:
        effects.extend(backing.status_effects)
    return effects


def _initiative_expression(modifier: int) -> str:
    if modifier == 0:
        return "1d20"
    if modifier > 0:
        return f"1d20+{modifier}"
    return f"1d20{modifier}"

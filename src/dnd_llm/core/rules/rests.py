from __future__ import annotations

from typing import Any

from ..dice import RollResult, RollService
from ..models import Character
from .class_features import (
    DARK_ONES_OWN_LUCK_RESOURCE,
    GIFT_OF_DEPTHS_RESOURCE,
    INDOMITABLE_RESOURCE,
    NATURAL_RECOVERY_CIRCLE_SPELL_RESOURCE,
    NATURAL_RECOVERY_SPELL_SLOTS_RESOURCE,
    NATURES_VEIL_RESOURCE,
    PERSISTENT_RAGE_INITIATIVE_RESTORE_RESOURCE,
    RELENTLESS_RAGE_USES_SINCE_REST_RESOURCE,
    STROKE_OF_LUCK_RESOURCE,
    TIRELESS_RESOURCE,
    UNCANNY_METABOLISM_RESOURCE,
    WARLOCK_FIENDISH_RESILIENCE_CHOICE_KEY,
    WHOLENESS_OF_BODY_RESOURCE,
    dark_ones_own_luck_uses,
    fighter_indomitable_uses,
    has_druid_circle_of_the_land_feature,
    has_monk_open_hand_feature,
    has_warlock_fiend_feature,
    has_warlock_gift_of_depths,
    normalize_warlock_fiendish_resilience_damage_type,
    ranger_natures_veil_uses,
    ranger_tireless_uses,
)
from .conditions import exhaustion_level, lower_exhaustion
from .spell_slots import (
    spell_slot_maxima_for_class_levels,
    warlock_pact_slot_maxima_for_class_levels,
)

CLASS_HIT_DICE = {
    "barbarian": "d12",
    "bard": "d8",
    "cleric": "d8",
    "druid": "d8",
    "fighter": "d10",
    "monk": "d8",
    "paladin": "d10",
    "ranger": "d10",
    "rogue": "d8",
    "sorcerer": "d6",
    "warlock": "d8",
    "wizard": "d6",
}

SECOND_WIND_RESOURCE = "srd.resource.second_wind"
ACTION_SURGE_RESOURCE = "srd.resource.action_surge"
RAGE_RESOURCE = "srd.resource.rage"
LAY_ON_HANDS_RESOURCE = "srd.resource.lay_on_hands"
PALADINS_SMITE_RESOURCE = "srd.resource.paladins_smite"
FAITHFUL_STEED_RESOURCE = "srd.resource.faithful_steed"
FOCUS_POINTS_RESOURCE = "srd.resource.focus_points"
BARDIC_INSPIRATION_RESOURCE = "srd.resource.bardic_inspiration"
FAVORED_ENEMY_HUNTERS_MARK_RESOURCE = "srd.resource.favored_enemy_hunters_mark"
CHANNEL_DIVINITY_RESOURCE = "srd.resource.channel_divinity"
WILD_SHAPE_RESOURCE = "srd.resource.wild_shape"
WILD_RESURGENCE_SPELL_SLOT_RESOURCE = "srd.resource.wild_resurgence_spell_slot"
INNATE_SORCERY_RESOURCE = "srd.resource.innate_sorcery"
SORCERY_POINTS_RESOURCE = "srd.resource.sorcery_points"
SORCEROUS_RESTORATION_RESOURCE = "srd.resource.sorcerous_restoration"
MAGICAL_CUNNING_RESOURCE = "srd.resource.magical_cunning"
ARCANE_RECOVERY_RESOURCE = "srd.resource.arcane_recovery"


def short_rest(
    character: Character,
    hit_dice_to_spend: dict[str, int],
    roll_service: RollService,
    arcane_recovery_slots: dict[str, int] | None = None,
    natural_recovery_slots: dict[str, int] | None = None,
    fiendish_resilience_damage_type: str | None = None,
) -> dict[str, Any]:
    _validate_warlock_fiendish_resilience_choice(character, fiendish_resilience_damage_type)
    con_modifier = _ability_modifier(character, "con")
    before_hp = character.hp_current
    before_resources = dict(character.resources)
    before_slots = dict(character.spell_slots)
    before_pact_slots = dict(character.pact_spell_slots)
    exhaustion_before = exhaustion_level(character.status_effects)
    exhaustion_after = exhaustion_before
    spent: dict[str, int] = {}
    healing_rolls: list[RollResult] = []
    healing_entries: list[dict[str, Any]] = []
    total_healing = 0
    maximized_sources = _hit_die_healing_maximized_sources(character)

    for die, requested_count in sorted(hit_dice_to_spend.items()):
        if die not in _max_hit_dice(character):
            raise ValueError(f"unknown hit die {die}")
        available = character.hit_dice.get(die, 0)
        count = min(available, max(0, int(requested_count)))
        spent[die] = count
        character.hit_dice[die] = available - count
        for _ in range(count):
            if maximized_sources:
                roll_total = _die_size(die)
                healed = max(1, roll_total + con_modifier)
                healing_entries.append(
                    {
                        "die": die,
                        "roll_id": None,
                        "roll_total": roll_total,
                        "con_modifier": con_modifier,
                        "healing": healed,
                        "hit_die_healing_maximized": True,
                        "passive_sources": maximized_sources,
                    }
                )
            else:
                roll = roll_service.roll(f"1{die}")
                healed = max(1, roll.total + con_modifier)
                healing_rolls.append(roll)
                healing_entries.append(
                    {
                        "die": die,
                        "roll_id": roll.roll_id,
                        "roll_total": roll.total,
                        "con_modifier": con_modifier,
                        "healing": healed,
                    }
                )
            total_healing += healed

    character.hp_current = min(character.hp_max, character.hp_current + total_healing)
    restored_resources = _restore_short_rest_resources(character)
    reset_resources = _reset_rest_resources(character)
    spent_resources = _apply_sorcerous_restoration(character, restored_resources)
    restored_spell_slots = _restore_short_rest_spell_slots(character)
    spent_resources.update(
        _apply_arcane_recovery(character, arcane_recovery_slots, restored_spell_slots)
    )
    spent_resources.update(
        _apply_natural_recovery(character, natural_recovery_slots, restored_spell_slots)
    )
    if ranger_tireless_uses(character):
        _, exhaustion_after = lower_exhaustion(character.status_effects)
    if character.hp_current > 0:
        _clear_death_save_state(character)
    result = {
        "hp_before": before_hp,
        "hp_after": character.hp_current,
        "healing": character.hp_current - before_hp,
        "spent_hit_dice": spent,
        "hit_dice_after": dict(character.hit_dice),
        "resources_before": before_resources,
        "resources_after": dict(character.resources),
        "restored_resources": restored_resources,
        "reset_resources": reset_resources,
        "spent_resources": spent_resources,
        "spell_slots_before": before_slots,
        "spell_slots_after": dict(character.spell_slots),
        "restored_spell_slots": restored_spell_slots,
        "pact_spell_slots_before": before_pact_slots,
        "pact_spell_slots_after": dict(character.pact_spell_slots),
        "healing_rolls": healing_entries,
        "dice_rolls": [roll.to_dict() for roll in healing_rolls],
        "exhaustion_before": exhaustion_before,
        "exhaustion_after": exhaustion_after,
    }
    fiendish_resilience = _apply_warlock_fiendish_resilience_choice(
        character,
        fiendish_resilience_damage_type,
    )
    if fiendish_resilience is not None:
        result["fiendish_resilience"] = fiendish_resilience
    return result


def long_rest(
    character: Character,
    fiendish_resilience_damage_type: str | None = None,
) -> dict[str, Any]:
    _validate_warlock_fiendish_resilience_choice(character, fiendish_resilience_damage_type)
    before_hp = character.hp_current
    before_temp_hp = character.temp_hp
    before_slots = dict(character.spell_slots)
    before_pact_slots = dict(character.pact_spell_slots)
    before_hit_dice = dict(character.hit_dice)
    before_resources = dict(character.resources)
    exhaustion_before, exhaustion_after = lower_exhaustion(character.status_effects)
    resurrection_penalty_recovery = _recover_resurrection_penalty_effects(character)
    removed_long_rest_effects = _remove_long_rest_effects(character)

    character.hp_current = character.hp_max
    character.temp_hp = 0
    character.temp_hp_source_effect_id = None
    _clear_death_save_state(character)

    restored_slots = _spell_slot_maxima(character)
    if restored_slots:
        character.spell_slots = dict(restored_slots)
        character.spell_slots_max = dict(restored_slots)
    restored_pact_slots = warlock_pact_slot_maxima_for_class_levels(character.class_levels)
    character.pact_spell_slots = dict(restored_pact_slots)
    character.pact_spell_slots_max = dict(restored_pact_slots)

    maxima = _max_hit_dice(character)
    restored_hit_dice: dict[str, int] = {}
    for die, maximum in sorted(maxima.items()):
        current = min(character.hit_dice.get(die, 0), maximum)
        restored = maximum - current
        character.hit_dice[die] = maximum
        restored_hit_dice[die] = restored

    restored_resources = _restore_long_rest_resources(character)
    reset_resources = _reset_rest_resources(character)

    result = {
        "hp_before": before_hp,
        "hp_after": character.hp_current,
        "temp_hp_before": before_temp_hp,
        "temp_hp_after": character.temp_hp,
        "spell_slots_before": before_slots,
        "spell_slots_after": dict(character.spell_slots),
        "pact_spell_slots_before": before_pact_slots,
        "pact_spell_slots_after": dict(character.pact_spell_slots),
        "hit_dice_before": before_hit_dice,
        "hit_dice_after": dict(character.hit_dice),
        "restored_hit_dice": restored_hit_dice,
        "resources_before": before_resources,
        "resources_after": dict(character.resources),
        "restored_resources": restored_resources,
        "reset_resources": reset_resources,
        "exhaustion_before": exhaustion_before,
        "exhaustion_after": exhaustion_after,
        "resurrection_penalty_recovery": resurrection_penalty_recovery,
        "removed_long_rest_effects": removed_long_rest_effects,
    }
    fiendish_resilience = _apply_warlock_fiendish_resilience_choice(
        character,
        fiendish_resilience_damage_type,
    )
    if fiendish_resilience is not None:
        result["fiendish_resilience"] = fiendish_resilience
    return result


def _restore_short_rest_resources(character: Character) -> dict[str, int]:
    restored: dict[str, int] = {}
    maxima = resource_maxima(character)
    maximum = maxima.get(SECOND_WIND_RESOURCE, 0)
    if maximum:
        before = min(character.resources.get(SECOND_WIND_RESOURCE, maximum), maximum)
        after = min(maximum, before + 1)
        character.resources[SECOND_WIND_RESOURCE] = after
        restored[SECOND_WIND_RESOURCE] = after - before
    rage_max = maxima.get(RAGE_RESOURCE, 0)
    if rage_max:
        before = min(character.resources.get(RAGE_RESOURCE, rage_max), rage_max)
        after = min(rage_max, before + 1)
        character.resources[RAGE_RESOURCE] = after
        restored[RAGE_RESOURCE] = after - before
    action_surge_max = maxima.get(ACTION_SURGE_RESOURCE, 0)
    if action_surge_max:
        before = min(
            character.resources.get(ACTION_SURGE_RESOURCE, action_surge_max), action_surge_max
        )
        character.resources[ACTION_SURGE_RESOURCE] = action_surge_max
        restored[ACTION_SURGE_RESOURCE] = action_surge_max - before
    focus_points_max = maxima.get(FOCUS_POINTS_RESOURCE, 0)
    if focus_points_max:
        before = min(
            character.resources.get(FOCUS_POINTS_RESOURCE, focus_points_max), focus_points_max
        )
        character.resources[FOCUS_POINTS_RESOURCE] = focus_points_max
        restored[FOCUS_POINTS_RESOURCE] = focus_points_max - before
    bardic_inspiration_max = maxima.get(BARDIC_INSPIRATION_RESOURCE, 0)
    if bardic_inspiration_max and int(character.class_levels.get("bard", 0)) >= 5:
        before = min(
            character.resources.get(BARDIC_INSPIRATION_RESOURCE, bardic_inspiration_max),
            bardic_inspiration_max,
        )
        character.resources[BARDIC_INSPIRATION_RESOURCE] = bardic_inspiration_max
        restored[BARDIC_INSPIRATION_RESOURCE] = bardic_inspiration_max - before
    channel_divinity_max = maxima.get(CHANNEL_DIVINITY_RESOURCE, 0)
    if channel_divinity_max:
        before = min(
            character.resources.get(CHANNEL_DIVINITY_RESOURCE, channel_divinity_max),
            channel_divinity_max,
        )
        after = min(channel_divinity_max, before + 1)
        character.resources[CHANNEL_DIVINITY_RESOURCE] = after
        restored[CHANNEL_DIVINITY_RESOURCE] = after - before
    wild_shape_max = maxima.get(WILD_SHAPE_RESOURCE, 0)
    if wild_shape_max:
        before = min(character.resources.get(WILD_SHAPE_RESOURCE, wild_shape_max), wild_shape_max)
        after = min(wild_shape_max, before + 1)
        character.resources[WILD_SHAPE_RESOURCE] = after
        restored[WILD_SHAPE_RESOURCE] = after - before
    stroke_of_luck_max = maxima.get(STROKE_OF_LUCK_RESOURCE, 0)
    if stroke_of_luck_max:
        before = min(
            character.resources.get(STROKE_OF_LUCK_RESOURCE, stroke_of_luck_max),
            stroke_of_luck_max,
        )
        character.resources[STROKE_OF_LUCK_RESOURCE] = stroke_of_luck_max
        restored[STROKE_OF_LUCK_RESOURCE] = stroke_of_luck_max - before
    return restored


def _reset_rest_resources(character: Character) -> dict[str, int]:
    reset: dict[str, int] = {}
    if int(character.resources.get(RELENTLESS_RAGE_USES_SINCE_REST_RESOURCE, 0)) > 0:
        before = int(character.resources[RELENTLESS_RAGE_USES_SINCE_REST_RESOURCE])
        character.resources[RELENTLESS_RAGE_USES_SINCE_REST_RESOURCE] = 0
        reset[RELENTLESS_RAGE_USES_SINCE_REST_RESOURCE] = before
    return reset


def _restore_short_rest_spell_slots(character: Character) -> dict[str, int]:
    restored: dict[str, int] = {}
    pact_slots = warlock_pact_slot_maxima_for_class_levels(character.class_levels)
    for slot_level, maximum in sorted(pact_slots.items(), key=lambda item: int(item[0])):
        before = max(0, int(character.pact_spell_slots.get(slot_level, 0)))
        after = max(before, maximum)
        character.pact_spell_slots[slot_level] = after
        character.pact_spell_slots_max[slot_level] = max(
            int(character.pact_spell_slots_max.get(slot_level, 0)),
            maximum,
        )
        if after > before:
            restored[slot_level] = after - before
    return restored


def _apply_sorcerous_restoration(
    character: Character,
    restored_resources: dict[str, int],
) -> dict[str, int]:
    maxima = resource_maxima(character)
    if not maxima.get(SORCEROUS_RESTORATION_RESOURCE):
        return {}
    sorcery_points_max = maxima.get(SORCERY_POINTS_RESOURCE, 0)
    if not sorcery_points_max:
        return {}
    feature_uses = min(
        int(character.resources.get(SORCEROUS_RESTORATION_RESOURCE, 0)),
        maxima[SORCEROUS_RESTORATION_RESOURCE],
    )
    if feature_uses <= 0:
        return {}
    before_points = min(
        int(character.resources.get(SORCERY_POINTS_RESOURCE, 0)), sorcery_points_max
    )
    missing = max(0, sorcery_points_max - before_points)
    recovery_cap = int(character.class_levels.get("sorcerer", 0)) // 2
    restored = min(missing, recovery_cap)
    if restored <= 0:
        return {}
    character.resources[SORCERY_POINTS_RESOURCE] = before_points + restored
    character.resources[SORCEROUS_RESTORATION_RESOURCE] = feature_uses - 1
    restored_resources[SORCERY_POINTS_RESOURCE] = (
        restored_resources.get(SORCERY_POINTS_RESOURCE, 0) + restored
    )
    return {SORCEROUS_RESTORATION_RESOURCE: 1}


def _apply_arcane_recovery(
    character: Character,
    requested_slots: dict[str, int] | None,
    restored_spell_slots: dict[str, int],
) -> dict[str, int]:
    requested = {str(level): int(count) for level, count in (requested_slots or {}).items()}
    requested = {level: count for level, count in requested.items() if count > 0}
    if not requested:
        return {}
    maxima = resource_maxima(character)
    if not maxima.get(ARCANE_RECOVERY_RESOURCE):
        raise ValueError("Arcane Recovery is not available")
    feature_uses = min(
        int(character.resources.get(ARCANE_RECOVERY_RESOURCE, 0)),
        maxima[ARCANE_RECOVERY_RESOURCE],
    )
    if feature_uses <= 0:
        raise ValueError("Arcane Recovery has already been used")
    wizard_level = int(character.class_levels.get("wizard", 0))
    recovery_cap = (wizard_level + 1) // 2
    total_recovered_levels = 0
    spell_slot_maxima = _recoverable_spell_slot_maxima(character)
    for slot_level, count in requested.items():
        level = int(slot_level)
        if level >= 6:
            raise ValueError("Arcane Recovery cannot recover level 6 or higher spell slots")
        total_recovered_levels += level * count
        maximum = spell_slot_maxima.get(slot_level, 0)
        before = max(0, int(character.spell_slots.get(slot_level, 0)))
        if before + count > maximum:
            raise ValueError(f"Arcane Recovery cannot recover {count} level {slot_level} slots")
    if total_recovered_levels > recovery_cap:
        raise ValueError(f"Arcane Recovery cannot recover more than {recovery_cap} spell levels")
    for slot_level, count in requested.items():
        before = max(0, int(character.spell_slots.get(slot_level, 0)))
        character.spell_slots[slot_level] = before + count
        character.spell_slots_max[slot_level] = max(
            int(character.spell_slots_max.get(slot_level, 0)),
            spell_slot_maxima.get(slot_level, 0),
        )
        restored_spell_slots[slot_level] = restored_spell_slots.get(slot_level, 0) + count
    character.resources[ARCANE_RECOVERY_RESOURCE] = feature_uses - 1
    return {ARCANE_RECOVERY_RESOURCE: 1}


def _apply_natural_recovery(
    character: Character,
    requested_slots: dict[str, int] | None,
    restored_spell_slots: dict[str, int],
) -> dict[str, int]:
    requested = {str(level): int(count) for level, count in (requested_slots or {}).items()}
    requested = {level: count for level, count in requested.items() if count > 0}
    if not requested:
        return {}
    maxima = resource_maxima(character)
    if not maxima.get(NATURAL_RECOVERY_SPELL_SLOTS_RESOURCE):
        raise ValueError("Natural Recovery is not available")
    feature_uses = min(
        int(character.resources.get(NATURAL_RECOVERY_SPELL_SLOTS_RESOURCE, 0)),
        maxima[NATURAL_RECOVERY_SPELL_SLOTS_RESOURCE],
    )
    if feature_uses <= 0:
        raise ValueError("Natural Recovery has already been used")
    druid_level = int(character.class_levels.get("druid", 0))
    recovery_cap = (druid_level + 1) // 2
    total_recovered_levels = 0
    spell_slot_maxima = _recoverable_spell_slot_maxima(character)
    for slot_level, count in requested.items():
        level = int(slot_level)
        if level >= 6:
            raise ValueError("Natural Recovery cannot recover level 6 or higher spell slots")
        total_recovered_levels += level * count
        maximum = spell_slot_maxima.get(slot_level, 0)
        before = max(0, int(character.spell_slots.get(slot_level, 0)))
        if before + count > maximum:
            raise ValueError(f"Natural Recovery cannot recover {count} level {slot_level} slots")
    if total_recovered_levels > recovery_cap:
        raise ValueError(f"Natural Recovery cannot recover more than {recovery_cap} spell levels")
    for slot_level, count in requested.items():
        before = max(0, int(character.spell_slots.get(slot_level, 0)))
        character.spell_slots[slot_level] = before + count
        character.spell_slots_max[slot_level] = max(
            int(character.spell_slots_max.get(slot_level, 0)),
            spell_slot_maxima.get(slot_level, 0),
        )
        restored_spell_slots[slot_level] = restored_spell_slots.get(slot_level, 0) + count
    character.resources[NATURAL_RECOVERY_SPELL_SLOTS_RESOURCE] = feature_uses - 1
    return {NATURAL_RECOVERY_SPELL_SLOTS_RESOURCE: 1}


def _restore_long_rest_resources(character: Character) -> dict[str, int]:
    restored: dict[str, int] = {}
    maxima = resource_maxima(character)
    for resource, maximum in sorted(maxima.items()):
        before = min(character.resources.get(resource, maximum), maximum)
        character.resources[resource] = maximum
        restored[resource] = maximum - before
    return restored


def _remove_long_rest_effects(character: Character) -> list[dict[str, Any]]:
    removed: list[dict[str, Any]] = []
    retained: list[dict[str, Any]] = []
    for effect in character.status_effects:
        duration = effect.get("duration", {})
        if isinstance(duration, dict) and duration.get("until") == "long_rest":
            removed.append(
                {
                    "effect_id": effect.get("effect_id"),
                    "source_action_id": effect.get("source_action_id"),
                    "condition": effect.get("condition"),
                    "passive_modifiers": effect.get("passive_modifiers", {}),
                }
            )
            continue
        retained.append(effect)
    character.status_effects[:] = retained
    return removed


def _recover_resurrection_penalty_effects(character: Character) -> list[dict[str, Any]]:
    recovered: list[dict[str, Any]] = []
    retained: list[dict[str, Any]] = []
    for effect in character.status_effects:
        modifiers = effect.get("passive_modifiers", {})
        if not isinstance(modifiers, dict) or modifiers.get("resurrection_penalty") is not True:
            retained.append(effect)
            continue
        before = _resurrection_penalty_value(modifiers)
        after = max(0, before - 1)
        recovered.append(
            {
                "effect_id": effect.get("effect_id"),
                "source_action_id": effect.get("source_action_id"),
                "penalty_before": before,
                "penalty_after": after,
            }
        )
        if after <= 0:
            continue
        updated = dict(effect)
        updated_modifiers = dict(modifiers)
        updated_modifiers["d20_test_penalty"] = after
        updated_modifiers["resurrection_d20_test_penalty"] = -after
        updated["passive_modifiers"] = updated_modifiers
        retained.append(updated)
    character.status_effects[:] = retained
    return recovered


def _resurrection_penalty_value(modifiers: dict[str, Any]) -> int:
    value = modifiers.get("d20_test_penalty")
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return max(0, int(value))
    legacy = modifiers.get("resurrection_d20_test_penalty")
    if isinstance(legacy, bool):
        return 0
    if isinstance(legacy, (int, float)):
        return abs(int(legacy))
    return 0


def _apply_warlock_fiendish_resilience_choice(
    character: Character,
    damage_type: str | None,
) -> dict[str, Any] | None:
    if damage_type is None:
        return None
    if not has_warlock_fiend_feature(character, level=10):
        raise ValueError("Fiendish Resilience requires Fiend Patron Warlock level 10")
    normalized = normalize_warlock_fiendish_resilience_damage_type(damage_type)
    previous = character.feature_choices.get(WARLOCK_FIENDISH_RESILIENCE_CHOICE_KEY)
    character.feature_choices[WARLOCK_FIENDISH_RESILIENCE_CHOICE_KEY] = normalized
    result: dict[str, Any] = {
        "damage_type": normalized,
        "changed": previous != normalized,
        "source_action_id": "srd.fiendish_resilience",
    }
    if previous is not None:
        result["previous_damage_type"] = previous
    return result


def _validate_warlock_fiendish_resilience_choice(
    character: Character,
    damage_type: str | None,
) -> None:
    if damage_type is None:
        return
    if not has_warlock_fiend_feature(character, level=10):
        raise ValueError("Fiendish Resilience requires Fiend Patron Warlock level 10")
    normalize_warlock_fiendish_resilience_damage_type(damage_type)


def resource_maxima(character: Character) -> dict[str, int]:
    fighter_level = int(character.class_levels.get("fighter", 0))
    maxima: dict[str, int] = {}
    if fighter_level > 0:
        if fighter_level >= 10:
            uses = 4
        elif fighter_level >= 4:
            uses = 3
        else:
            uses = 2
        maxima[SECOND_WIND_RESOURCE] = uses
        if fighter_level >= 2:
            maxima[ACTION_SURGE_RESOURCE] = 2 if fighter_level >= 17 else 1
    barbarian_level = int(character.class_levels.get("barbarian", 0))
    if barbarian_level > 0:
        if barbarian_level >= 17:
            rage_uses = 6
        elif barbarian_level >= 12:
            rage_uses = 5
        elif barbarian_level >= 6:
            rage_uses = 4
        elif barbarian_level >= 3:
            rage_uses = 3
        else:
            rage_uses = 2
        maxima[RAGE_RESOURCE] = rage_uses
        if barbarian_level >= 15:
            maxima[PERSISTENT_RAGE_INITIATIVE_RESTORE_RESOURCE] = 1
    paladin_level = int(character.class_levels.get("paladin", 0))
    if paladin_level > 0:
        maxima[LAY_ON_HANDS_RESOURCE] = paladin_level * 5
    if paladin_level >= 2:
        maxima[PALADINS_SMITE_RESOURCE] = 1
    if paladin_level >= 5:
        maxima[FAITHFUL_STEED_RESOURCE] = 1
    monk_level = int(character.class_levels.get("monk", 0))
    if monk_level >= 2:
        maxima[FOCUS_POINTS_RESOURCE] = monk_level
        maxima[UNCANNY_METABOLISM_RESOURCE] = 1
    if has_monk_open_hand_feature(character, level=6):
        maxima[WHOLENESS_OF_BODY_RESOURCE] = max(1, _ability_modifier(character, "wis"))
    bard_level = int(character.class_levels.get("bard", 0))
    if bard_level > 0:
        maxima[BARDIC_INSPIRATION_RESOURCE] = max(1, _ability_modifier(character, "cha"))
    ranger_level = int(character.class_levels.get("ranger", 0))
    if ranger_level > 0:
        maxima[FAVORED_ENEMY_HUNTERS_MARK_RESOURCE] = 3 if ranger_level >= 5 else 2
    tireless_uses = ranger_tireless_uses(character)
    if tireless_uses:
        maxima[TIRELESS_RESOURCE] = tireless_uses
    natures_veil_uses = ranger_natures_veil_uses(character)
    if natures_veil_uses:
        maxima[NATURES_VEIL_RESOURCE] = natures_veil_uses
    cleric_level = int(character.class_levels.get("cleric", 0))
    if cleric_level >= 2:
        maxima[CHANNEL_DIVINITY_RESOURCE] = 2
    if paladin_level >= 3:
        maxima[CHANNEL_DIVINITY_RESOURCE] = max(maxima.get(CHANNEL_DIVINITY_RESOURCE, 0), 2)
    druid_level = int(character.class_levels.get("druid", 0))
    if druid_level >= 2:
        maxima[WILD_SHAPE_RESOURCE] = 2
    if druid_level >= 5:
        maxima[WILD_RESURGENCE_SPELL_SLOT_RESOURCE] = 1
    if has_druid_circle_of_the_land_feature(character, level=6):
        maxima[NATURAL_RECOVERY_SPELL_SLOTS_RESOURCE] = 1
        maxima[NATURAL_RECOVERY_CIRCLE_SPELL_RESOURCE] = 1
    sorcerer_level = int(character.class_levels.get("sorcerer", 0))
    if sorcerer_level >= 1:
        maxima[INNATE_SORCERY_RESOURCE] = 2
    if sorcerer_level >= 2:
        maxima[SORCERY_POINTS_RESOURCE] = sorcerer_level
    if sorcerer_level >= 5:
        maxima[SORCEROUS_RESTORATION_RESOURCE] = 1
    warlock_level = int(character.class_levels.get("warlock", 0))
    if warlock_level >= 2:
        maxima[MAGICAL_CUNNING_RESOURCE] = 1
    dark_ones_own_luck_max = dark_ones_own_luck_uses(character)
    if dark_ones_own_luck_max:
        maxima[DARK_ONES_OWN_LUCK_RESOURCE] = dark_ones_own_luck_max
    indomitable_max = fighter_indomitable_uses(character)
    if indomitable_max:
        maxima[INDOMITABLE_RESOURCE] = indomitable_max
    if int(character.class_levels.get("rogue", 0)) >= 20:
        maxima[STROKE_OF_LUCK_RESOURCE] = 1
    if has_warlock_gift_of_depths(character):
        maxima[GIFT_OF_DEPTHS_RESOURCE] = 1
    wizard_level = int(character.class_levels.get("wizard", 0))
    if wizard_level >= 1:
        maxima[ARCANE_RECOVERY_RESOURCE] = 1
    return maxima


def _max_hit_dice(character: Character) -> dict[str, int]:
    maxima: dict[str, int] = {}
    for class_name, level in character.class_levels.items():
        die = CLASS_HIT_DICE.get(class_name)
        if die is None:
            continue
        maxima[die] = maxima.get(die, 0) + max(0, int(level))
    for die, count in character.hit_dice.items():
        maxima[die] = max(maxima.get(die, 0), int(count))
    return maxima


def _die_size(die: str) -> int:
    if not die.startswith("d"):
        raise ValueError(f"invalid hit die {die}")
    return int(die[1:])


def _hit_die_healing_maximized_sources(character: Character) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for effect in character.status_effects:
        modifiers = effect.get("passive_modifiers", {})
        if not isinstance(modifiers, dict):
            continue
        if modifiers.get("hit_die_healing_maximized") is not True:
            continue
        sources.append(
            {
                "effect_id": effect.get("effect_id"),
                "source_action_id": effect.get("source_action_id"),
                "modifier": "hit_die_healing_maximized",
            }
        )
    return sources


def _spell_slot_maxima(character: Character) -> dict[str, int]:
    maxima: dict[str, int] = {
        str(slot_level): int(count) for slot_level, count in character.spell_slots_max.items()
    }
    _merge_slots(maxima, spell_slot_maxima_for_class_levels(character.class_levels))
    for slot_level, current in character.spell_slots.items():
        maxima[slot_level] = max(maxima.get(slot_level, 0), int(current))
    return maxima


def _recoverable_spell_slot_maxima(character: Character) -> dict[str, int]:
    maxima = spell_slot_maxima_for_class_levels(character.class_levels)
    _merge_slots(
        maxima,
        {str(slot_level): int(count) for slot_level, count in character.spell_slots_max.items()},
    )
    return maxima


def _merge_slots(target: dict[str, int], source: dict[str, int]) -> None:
    for level, count in source.items():
        target[level] = max(target.get(level, 0), count)


def _clear_death_save_state(character: Character) -> None:
    character.death_save_successes = 0
    character.death_save_failures = 0
    character.stable = False
    character.dead = False


def _ability_modifier(character: Character, ability: str) -> int:
    score = int(character.abilities.get(ability, 10))
    return (score - 10) // 2

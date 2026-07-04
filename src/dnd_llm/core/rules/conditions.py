from __future__ import annotations

from typing import Any

CORE_CONDITIONS = {
    "blinded",
    "charmed",
    "deafened",
    "exhaustion",
    "frightened",
    "grappled",
    "incapacitated",
    "invisible",
    "paralyzed",
    "petrified",
    "poisoned",
    "prone",
    "restrained",
    "stunned",
    "unconscious",
}


def has_condition(status_effects: list[dict[str, object]], condition: str) -> bool:
    return any(effect.get("condition") == condition for effect in status_effects)


def remove_condition(status_effects: list[dict[str, object]], condition: str) -> int:
    before = len(status_effects)
    status_effects[:] = [
        effect for effect in status_effects if effect.get("condition") != condition
    ]
    return before - len(status_effects)


def exhaustion_level(status_effects: list[dict[str, Any]]) -> int:
    return sum(_exhaustion_effect_level(effect) for effect in status_effects)


def exhaustion_d20_penalty(status_effects: list[dict[str, Any]]) -> int:
    return 2 * exhaustion_level(status_effects)


def effective_speed(speed_ft: int, status_effects: list[dict[str, Any]]) -> int:
    bonus = 0
    multiplier = 1.0
    for effect in status_effects:
        modifiers = effect.get("passive_modifiers", {})
        if not isinstance(modifiers, dict):
            continue
        speed_bonus = modifiers.get("speed_bonus_ft")
        if isinstance(speed_bonus, int) and not isinstance(speed_bonus, bool):
            bonus += speed_bonus
        speed_multiplier = modifiers.get("speed_multiplier")
        if isinstance(speed_multiplier, (int, float)) and not isinstance(speed_multiplier, bool):
            multiplier *= max(0.0, float(speed_multiplier))
    speed = max(0, speed_ft + bonus - 5 * exhaustion_level(status_effects))
    return int(speed * multiplier)


def fly_speed_from_effects(speed_ft: int, status_effects: list[dict[str, Any]]) -> int | None:
    fly_speeds: list[int] = []
    for effect in status_effects:
        modifiers = effect.get("passive_modifiers", {})
        if not isinstance(modifiers, dict):
            continue
        if modifiers.get("fly_speed_equals_speed") is True:
            fly_speeds.append(effective_speed(speed_ft, status_effects))
        fixed_speed = modifiers.get("fly_speed_ft")
        if isinstance(fixed_speed, int) and not isinstance(fixed_speed, bool):
            fly_speeds.append(fixed_speed)
    return max(fly_speeds) if fly_speeds else None


def swim_speed_from_effects(speed_ft: int, status_effects: list[dict[str, Any]]) -> int | None:
    swim_speeds: list[int] = []
    for effect in status_effects:
        modifiers = effect.get("passive_modifiers", {})
        if not isinstance(modifiers, dict):
            continue
        if modifiers.get("swim_speed_equals_speed") is True:
            swim_speeds.append(effective_speed(speed_ft, status_effects))
        fixed_speed = modifiers.get("swim_speed_ft")
        if isinstance(fixed_speed, int) and not isinstance(fixed_speed, bool):
            swim_speeds.append(fixed_speed)
    return max(swim_speeds) if swim_speeds else None


def climb_speed_from_effects(speed_ft: int, status_effects: list[dict[str, Any]]) -> int | None:
    climb_speeds: list[int] = []
    for effect in status_effects:
        modifiers = effect.get("passive_modifiers", {})
        if not isinstance(modifiers, dict):
            continue
        if modifiers.get("climb_speed_equals_speed") is True:
            climb_speeds.append(effective_speed(speed_ft, status_effects))
        fixed_speed = modifiers.get("climb_speed_ft")
        if isinstance(fixed_speed, int) and not isinstance(fixed_speed, bool):
            climb_speeds.append(fixed_speed)
    return max(climb_speeds) if climb_speeds else None


def can_hover_from_effects(status_effects: list[dict[str, Any]]) -> bool:
    return any(
        isinstance(effect.get("passive_modifiers"), dict)
        and effect["passive_modifiers"].get("can_hover") is True
        for effect in status_effects
    )


def can_walk_on_liquid_surface_from_effects(status_effects: list[dict[str, Any]]) -> bool:
    return any(
        isinstance(effect.get("passive_modifiers"), dict)
        and effect["passive_modifiers"].get("walk_on_liquid_surface") is True
        for effect in status_effects
    )


def xray_vision_range_from_effects(status_effects: list[dict[str, Any]]) -> int | None:
    ranges: list[int] = []
    for effect in status_effects:
        modifiers = effect.get("passive_modifiers", {})
        if not isinstance(modifiers, dict):
            continue
        range_ft = modifiers.get("xray_vision_range_ft")
        if isinstance(range_ft, int) and not isinstance(range_ft, bool):
            ranges.append(range_ft)
    return max(ranges) if ranges else None


def darkvision_range_from_effects(status_effects: list[dict[str, Any]]) -> int | None:
    ranges: list[tuple[int, int]] = []
    bonuses: list[tuple[int, int]] = []
    for index, effect in enumerate(status_effects):
        modifiers = effect.get("passive_modifiers", {})
        if not isinstance(modifiers, dict):
            continue
        range_ft = modifiers.get("darkvision_ft")
        if isinstance(range_ft, int) and not isinstance(range_ft, bool):
            ranges.append((index, range_ft))
        bonus_ft = modifiers.get("darkvision_existing_bonus_ft")
        if isinstance(bonus_ft, int) and not isinstance(bonus_ft, bool):
            bonuses.append((index, bonus_ft))
    candidates = [range_ft for _, range_ft in ranges]
    for bonus_index, bonus_ft in bonuses:
        other_ranges = [range_ft for index, range_ft in ranges if index != bonus_index]
        if other_ranges:
            candidates.append(max(other_ranges) + bonus_ft)
    return max(candidates) if candidates else None


def truesight_range_from_effects(status_effects: list[dict[str, Any]]) -> int | None:
    return _sense_range_from_effects(status_effects, "truesight_ft")


def blindsight_range_from_effects(status_effects: list[dict[str, Any]]) -> int | None:
    return _sense_range_from_effects(status_effects, "blindsight_ft")


def _sense_range_from_effects(
    status_effects: list[dict[str, Any]],
    modifier_key: str,
) -> int | None:
    ranges: list[int] = []
    for effect in status_effects:
        modifiers = effect.get("passive_modifiers", {})
        if not isinstance(modifiers, dict):
            continue
        range_ft = modifiers.get(modifier_key)
        if isinstance(range_ft, int) and not isinstance(range_ft, bool):
            ranges.append(range_ft)
    return max(ranges) if ranges else None


def raw_ability_score(entity: Any, ability: str) -> int:
    abilities = getattr(entity, "abilities", {})
    ability = ability.lower()
    return int(abilities.get(ability, abilities.get(ability.upper(), 10)))


def effective_ability_score(
    entity: Any,
    ability: str,
    *,
    status_effects: list[dict[str, Any]] | None = None,
) -> int:
    ability = ability.lower()
    score = _class_feature_ability_score(entity, ability, raw_ability_score(entity, ability))
    for effect in (
        status_effects if status_effects is not None else getattr(entity, "status_effects", [])
    ):
        modifiers = effect.get("passive_modifiers", {})
        if not isinstance(modifiers, dict):
            continue
        score_sets = modifiers.get("ability_score_set", {})
        if not isinstance(score_sets, dict):
            continue
        set_score = _ability_score_set_value(score_sets.get(ability.lower()))
        if set_score is None:
            set_score = _ability_score_set_value(score_sets.get(ability.upper()))
        if set_score is not None and set_score > score:
            score = set_score
    return score


def _class_feature_ability_score(entity: Any, ability: str, score: int) -> int:
    if ability not in {"str", "con"} or not _has_primal_champion(entity):
        return score
    return min(score + 4, 25)


def _has_primal_champion(entity: Any) -> bool:
    class_levels = getattr(entity, "class_levels", {})
    if not isinstance(class_levels, dict):
        return False
    return int(class_levels.get("barbarian", 0)) >= 20


def effective_ability_modifier(
    entity: Any,
    ability: str,
    *,
    status_effects: list[dict[str, Any]] | None = None,
) -> int:
    return (effective_ability_score(entity, ability, status_effects=status_effects) - 10) // 2


def ability_score_set_sources(
    entity: Any,
    ability: str,
    *,
    status_effects: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    ability = ability.lower()
    raw_score = raw_ability_score(entity, ability)
    base_score = _class_feature_ability_score(entity, ability, raw_score)
    sources: list[dict[str, Any]] = []
    class_feature_source = _class_feature_ability_score_source(entity, ability, raw_score)
    if class_feature_source is not None:
        sources.append(class_feature_source)
    for effect in (
        status_effects if status_effects is not None else getattr(entity, "status_effects", [])
    ):
        modifiers = effect.get("passive_modifiers", {})
        if not isinstance(modifiers, dict):
            continue
        score_sets = modifiers.get("ability_score_set", {})
        if not isinstance(score_sets, dict):
            continue
        set_score = _ability_score_set_value(score_sets.get(ability.lower()))
        if set_score is None:
            set_score = _ability_score_set_value(score_sets.get(ability.upper()))
        if set_score is None or set_score <= base_score:
            continue
        sources.append(
            {
                "condition": effect.get("condition"),
                "effect_id": effect.get("effect_id"),
                "source_action_id": effect.get("source_action_id"),
                "modifier": "ability_score_set",
                "ability": ability.lower(),
                "score": set_score,
            }
        )
    return sources


def _class_feature_ability_score_source(
    entity: Any,
    ability: str,
    score: int,
) -> dict[str, Any] | None:
    if ability not in {"str", "con"} or not _has_primal_champion(entity):
        return None
    feature_score = min(score + 4, 25)
    if feature_score <= score:
        return None
    return {
        "source_action_id": "srd.primal_champion",
        "modifier": "primal_champion_ability_score_increase",
        "ability": ability,
        "score": feature_score,
    }


def apply_exhaustion(
    status_effects: list[dict[str, Any]],
    effect: dict[str, Any],
    *,
    amount: int = 1,
) -> tuple[int, int, dict[str, Any]]:
    before = exhaustion_level(status_effects)
    after = before + max(0, amount)
    status_effects[:] = [
        existing for existing in status_effects if existing.get("condition") != "exhaustion"
    ]
    applied = dict(effect)
    applied["condition"] = "exhaustion"
    applied["level"] = after
    status_effects.append(applied)
    return before, after, applied


def lower_exhaustion(
    status_effects: list[dict[str, Any]],
    *,
    amount: int = 1,
) -> tuple[int, int]:
    before = exhaustion_level(status_effects)
    after = max(0, before - max(0, amount))
    base_effect = next(
        (effect for effect in status_effects if effect.get("condition") == "exhaustion"),
        None,
    )
    status_effects[:] = [
        effect for effect in status_effects if effect.get("condition") != "exhaustion"
    ]
    if after > 0 and base_effect is not None:
        retained = dict(base_effect)
        retained["level"] = after
        status_effects.append(retained)
    return before, after


def _exhaustion_effect_level(effect: dict[str, Any]) -> int:
    if effect.get("condition") != "exhaustion":
        return 0
    for key in ("level", "exhaustion_level"):
        level = _level_value(effect.get(key))
        if level is not None:
            return level
    metadata = effect.get("metadata", {})
    if isinstance(metadata, dict):
        for key in ("level", "exhaustion_level"):
            level = _level_value(metadata.get(key))
            if level is not None:
                return level
    return 1


def _level_value(raw: Any) -> int | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return max(0, raw)
    if isinstance(raw, str):
        try:
            return max(0, int(raw))
        except ValueError:
            return None
    return None


def _ability_score_set_value(raw: Any) -> int | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        try:
            return int(raw)
        except ValueError:
            return None
    return None

from __future__ import annotations

from typing import Any

from ..dice import RollService
from ..models import Character, Combatant
from .class_features import (
    champion_survivor_death_save_advantage,
    champion_survivor_death_save_counts_as_20,
)


def roll_death_save(
    entity: Character | Combatant,
    roll_service: RollService,
    *,
    feature_source: Character | None = None,
) -> dict[str, Any]:
    if entity.dead:
        raise ValueError("dead creatures cannot make death saving throws")
    if entity.hp_current > 0:
        raise ValueError("death saving throws require hp_current to be 0")

    feature_source = feature_source or (entity if isinstance(entity, Character) else None)
    defy_death = (
        champion_survivor_death_save_advantage(feature_source)
        if feature_source is not None
        else False
    )
    roll = roll_service.roll("1d20", advantage="advantage" if defy_death else None)
    natural = _kept_d20(roll.to_dict())
    survivor_counts_as_20 = (
        champion_survivor_death_save_counts_as_20(feature_source, natural=natural)
        if feature_source is not None
        else False
    )
    effective_natural = 20 if survivor_counts_as_20 else natural
    before = _death_state(entity)
    hp_before = entity.hp_current

    if natural == 1:
        entity.death_save_failures += 2
    elif effective_natural == 20:
        entity.hp_current = 1
        _clear_death_state(entity)
    elif effective_natural >= 10:
        entity.death_save_successes += 1
    else:
        entity.death_save_failures += 1

    if effective_natural != 20:
        entity.death_save_successes = min(entity.death_save_successes, 3)
        entity.death_save_failures = min(entity.death_save_failures, 3)
        entity.stable = entity.death_save_successes >= 3
        entity.dead = entity.death_save_failures >= 3

    return {
        "roll": roll.to_dict(),
        "natural": natural,
        "effective_natural": effective_natural,
        "hp_before": hp_before,
        "hp_after": entity.hp_current,
        "before": before,
        "after": _death_state(entity),
        "stable": entity.stable,
        "dead": entity.dead,
        "advantage_sources": ["srd.survivor"] if defy_death else [],
        "defy_death_counts_as_20": survivor_counts_as_20,
    }


def _death_state(entity: Character | Combatant) -> dict[str, Any]:
    return {
        "successes": entity.death_save_successes,
        "failures": entity.death_save_failures,
        "stable": entity.stable,
        "dead": entity.dead,
    }


def _clear_death_state(entity: Character | Combatant) -> None:
    entity.death_save_successes = 0
    entity.death_save_failures = 0
    entity.stable = False
    entity.dead = False


def _kept_d20(roll: dict[str, Any]) -> int:
    for die in roll.get("dice", []):
        if die.get("sides") == 20 and die.get("kept") is True:
            return int(die["value"])
    raise ValueError("death saving throw roll did not include a kept d20")

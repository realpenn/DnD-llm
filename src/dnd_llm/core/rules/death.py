from __future__ import annotations

from typing import Any

from ..dice import RollService
from ..models import Character, Combatant


def roll_death_save(
    entity: Character | Combatant,
    roll_service: RollService,
) -> dict[str, Any]:
    if entity.dead:
        raise ValueError("dead creatures cannot make death saving throws")
    if entity.hp_current > 0:
        raise ValueError("death saving throws require hp_current to be 0")

    roll = roll_service.roll("1d20")
    natural = roll.total
    before = _death_state(entity)
    hp_before = entity.hp_current

    if natural == 1:
        entity.death_save_failures += 2
    elif natural == 20:
        entity.hp_current = 1
        _clear_death_state(entity)
    elif natural >= 10:
        entity.death_save_successes += 1
    else:
        entity.death_save_failures += 1

    if natural != 20:
        entity.death_save_successes = min(entity.death_save_successes, 3)
        entity.death_save_failures = min(entity.death_save_failures, 3)
        entity.stable = entity.death_save_successes >= 3
        entity.dead = entity.death_save_failures >= 3

    return {
        "roll": roll.to_dict(),
        "natural": natural,
        "hp_before": hp_before,
        "hp_after": entity.hp_current,
        "before": before,
        "after": _death_state(entity),
        "stable": entity.stable,
        "dead": entity.dead,
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

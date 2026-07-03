from __future__ import annotations

from .models import Character, GameState
from .positioning import TacticalGraph


class InvariantViolation(RuntimeError):
    pass


def validate_game_state(state: GameState) -> list[str]:
    errors: list[str] = []
    for prefix, entity in _entities(state):
        if entity.hp_current < 0:
            errors.append(f"{prefix}: hp_current below zero")
        if entity.hp_current > entity.hp_max:
            errors.append(f"{prefix}: hp_current above hp_max")
        if getattr(entity, "temp_hp", 0) < 0:
            errors.append(f"{prefix}: temp_hp below zero")
        death_successes = getattr(entity, "death_save_successes", 0)
        death_failures = getattr(entity, "death_save_failures", 0)
        if death_successes < 0 or death_successes > 3:
            errors.append(f"{prefix}: death save successes out of range")
        if death_failures < 0 or death_failures > 3:
            errors.append(f"{prefix}: death save failures out of range")
        if getattr(entity, "stable", False) and getattr(entity, "dead", False):
            errors.append(f"{prefix}: cannot be both stable and dead")
        if isinstance(entity, Character):
            for level, slots in entity.spell_slots.items():
                if slots < 0:
                    errors.append(f"{prefix}: spell slot {level} below zero")
            if entity.gold < 0:
                errors.append(f"{prefix}: gold below zero")
            for resource, amount in entity.resources.items():
                if amount < 0:
                    errors.append(f"{prefix}: resource {resource} below zero")
    if state.encounter is not None and state.encounter.tactical_graph is not None:
        graph = TacticalGraph.from_dict(state.encounter.tactical_graph)
        for combatant_id, combatant in state.encounter.combatants.items():
            if (
                combatant.position_node_id is not None
                and combatant.position_node_id not in graph.nodes
            ):
                errors.append(f"combatant:{combatant_id}: unknown position node")
    return errors


def require_game_state_invariants(state: GameState) -> None:
    errors = validate_game_state(state)
    if errors:
        raise InvariantViolation("; ".join(errors))


def _entities(state: GameState):
    for character_id, character in state.characters.items():
        yield f"character:{character_id}", character
    for monster_id, monster in state.monsters.items():
        yield f"monster:{monster_id}", monster
    if state.encounter is not None:
        for combatant_id, combatant in state.encounter.combatants.items():
            yield f"combatant:{combatant_id}", combatant

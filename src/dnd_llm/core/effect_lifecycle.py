from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .dice import RollService
from .models import GameState
from .rules.checks import d20_expression
from .rules.conditions import exhaustion_d20_penalty, exhaustion_level


@dataclass
class EffectLifecycleResult:
    trigger: str
    actor_id: str
    expired: list[dict[str, Any]] = field(default_factory=list)
    ticked: list[dict[str, Any]] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.expired or self.ticked)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger": self.trigger,
            "actor_id": self.actor_id,
            "expired": self.expired,
            "ticked": self.ticked,
        }


def tick_effects(
    state: GameState,
    *,
    trigger: str,
    actor_id: str,
    roll_service: RollService | None = None,
) -> EffectLifecycleResult:
    result = EffectLifecycleResult(trigger=trigger, actor_id=actor_id)
    for owner_type, owner_id, effects in _effect_lists(state):
        retained: list[dict[str, Any]] = []
        for effect in effects:
            if not _matches_trigger(effect, trigger=trigger, actor_id=actor_id):
                retained.append(effect)
                continue
            duration = effect.setdefault("duration", {})
            if not isinstance(duration, dict):
                duration = {}
                effect["duration"] = duration
            repeat_save = _repeat_save(effect, trigger)
            repeat_save_entry = None
            if repeat_save is not None and roll_service is not None:
                repeat_save_entry = _roll_repeat_save(
                    state,
                    effect,
                    actor_id,
                    repeat_save,
                    roll_service,
                )
                if repeat_save_entry["success"] and bool(repeat_save.get("end_on_success", True)):
                    result.expired.append(
                        _entry(
                            effect,
                            owner_type=owner_type,
                            owner_id=owner_id,
                            trigger=trigger,
                            remaining_before=_remaining_ticks(duration) or 0,
                            remaining_after=0,
                            repeat_save=repeat_save_entry,
                        )
                    )
                    continue
            remaining_before = _remaining_ticks(duration)
            if remaining_before is None:
                retained.append(effect)
                continue
            remaining_after = remaining_before - 1
            entry = _entry(
                effect,
                owner_type=owner_type,
                owner_id=owner_id,
                trigger=trigger,
                remaining_before=remaining_before,
                remaining_after=max(remaining_after, 0),
                repeat_save=repeat_save_entry,
            )
            if remaining_after <= 0:
                _expire_temporary_hit_points(state, effect, owner_type, owner_id, entry)
                result.expired.append(entry)
            else:
                duration["remaining_ticks"] = remaining_after
                result.ticked.append(entry)
                retained.append(effect)
        effects[:] = retained
    return result


def _effect_lists(state: GameState) -> list[tuple[str, str, list[dict[str, Any]]]]:
    effect_lists: list[tuple[str, str, list[dict[str, Any]]]] = []
    effect_lists.extend(
        ("character", character_id, character.status_effects)
        for character_id, character in state.characters.items()
    )
    effect_lists.extend(
        ("monster", monster_id, monster.status_effects)
        for monster_id, monster in state.monsters.items()
    )
    if state.encounter is not None:
        effect_lists.extend(
            ("combatant", combatant_id, combatant.status_effects)
            for combatant_id, combatant in state.encounter.combatants.items()
        )
    effect_lists.append(("world", "world", state.world.active_effects))
    return effect_lists


def _expire_temporary_hit_points(
    state: GameState,
    effect: dict[str, Any],
    owner_type: str,
    owner_id: str,
    entry: dict[str, Any],
) -> None:
    audit = effect.get("audit", {})
    if not isinstance(audit, dict) or audit.get("temp_hp_source") is not True:
        return
    owner = _effect_owner(state, owner_type, owner_id)
    if owner is None:
        return
    effect_id = effect.get("effect_id")
    if getattr(owner, "temp_hp_source_effect_id", None) != effect_id:
        return
    before = int(getattr(owner, "temp_hp", 0))
    setattr(owner, "temp_hp", 0)
    setattr(owner, "temp_hp_source_effect_id", None)
    if owner_type == "combatant":
        entity_id = getattr(owner, "entity_id", None)
        if isinstance(entity_id, str) and entity_id in state.characters:
            state.characters[entity_id].temp_hp = 0
            state.characters[entity_id].temp_hp_source_effect_id = None
    entry["temp_hp_expired"] = {"before": before, "after": 0}


def _effect_owner(state: GameState, owner_type: str, owner_id: str) -> Any:
    if owner_type == "character":
        return state.characters.get(owner_id)
    if owner_type == "monster":
        return state.monsters.get(owner_id)
    if owner_type == "combatant" and state.encounter is not None:
        return state.encounter.combatants.get(owner_id)
    return None


def _matches_trigger(effect: dict[str, Any], *, trigger: str, actor_id: str) -> bool:
    if effect.get("tick_on") != trigger:
        return False
    target_id = effect.get("target_id")
    applied_by = effect.get("applied_by")
    if trigger.startswith("self_turn"):
        return target_id == actor_id or applied_by == actor_id
    if trigger.startswith("target_"):
        return target_id == actor_id
    return False


def _remaining_ticks(duration: dict[str, Any]) -> int | None:
    explicit = duration.get("remaining_ticks")
    if explicit is not None:
        return max(0, int(explicit))
    inferred = _initial_ticks(str(duration.get("until", "")))
    if inferred is not None:
        duration["remaining_ticks"] = inferred
    return inferred


def _initial_ticks(until: str) -> int | None:
    timed_until = until.split("_or_", 1)[0]
    if timed_until in {"start_of_next_turn", "end_of_next_turn", "end_of_current_turn"}:
        return 1
    if timed_until in {"duration_1_minute", "concentration_1_minute"}:
        return 10
    if timed_until in {"duration_10_minutes", "concentration_10_minutes"}:
        return 100
    if timed_until in {"duration_1_hour", "concentration_1_hour"}:
        return 600
    if timed_until in {"duration_2_hours", "concentration_2_hours"}:
        return 1200
    if timed_until in {"duration_8_hours", "concentration_8_hours"}:
        return 4800
    if timed_until in {"duration_1_day", "concentration_1_day"}:
        return 14400
    if timed_until in {"duration_24_hours", "concentration_24_hours"}:
        return 14400
    if timed_until in {"duration_10_days", "concentration_10_days"}:
        return 144000
    if timed_until in {"duration_30_days", "concentration_30_days"}:
        return 432000
    if timed_until in {"duration_366_days", "concentration_366_days"}:
        return 5270400
    return None


def _repeat_save(effect: dict[str, Any], trigger: str) -> dict[str, Any] | None:
    duration = effect.get("duration", {})
    if not isinstance(duration, dict):
        return None
    repeat_save = duration.get("repeat_save")
    if not isinstance(repeat_save, dict):
        return None
    if repeat_save.get("trigger", effect.get("tick_on")) != trigger:
        return None
    return repeat_save


def _roll_repeat_save(
    state: GameState,
    effect: dict[str, Any],
    actor_id: str,
    repeat_save: dict[str, Any],
    roll_service: RollService,
) -> dict[str, Any]:
    target = state.entity_for_actor(str(effect.get("target_id") or actor_id))
    ability = str(repeat_save["ability"]).lower()
    base_bonus, proficient = _saving_throw_bonus(state, target, ability)
    status_effects = getattr(target, "status_effects", [])
    exhaustion = exhaustion_level(status_effects)
    penalty = exhaustion_d20_penalty(status_effects)
    bonus = base_bonus - penalty
    roll = roll_service.roll(d20_expression(bonus))
    total = roll.total
    dc = int(repeat_save["dc"])
    return {
        "ability": ability,
        "dc": dc,
        "dc_source": repeat_save.get("dc_source"),
        "base_bonus": base_bonus,
        "bonus": bonus,
        "proficient": proficient,
        "exhaustion_level": exhaustion,
        "d20_penalty": penalty,
        "roll": roll.to_dict(),
        "total": total,
        "success": total >= dc,
    }


def _saving_throw_bonus(state: GameState, target: Any, ability: str) -> tuple[int, bool]:
    source = _ability_source(state, target)
    proficiency_source = _proficiency_source(state, target)
    proficient = ability.lower() in {
        str(item).lower() for item in getattr(proficiency_source, "saving_throw_proficiencies", [])
    }
    bonus = _ability_modifier(source, ability)
    if proficient:
        bonus += int(getattr(proficiency_source, "proficiency_bonus", 2))
    return bonus, proficient


def _ability_source(state: GameState, target: Any) -> Any:
    entity_id = getattr(target, "entity_id", None)
    if isinstance(entity_id, str):
        return state.characters.get(entity_id) or state.monsters.get(entity_id) or target
    return target


def _proficiency_source(state: GameState, target: Any) -> Any:
    return _ability_source(state, target)


def _ability_modifier(entity: Any, ability: str) -> int:
    abilities = getattr(entity, "abilities", {})
    score = int(abilities.get(ability.lower(), abilities.get(ability.upper(), 10)))
    return (score - 10) // 2


def _entry(
    effect: dict[str, Any],
    *,
    owner_type: str,
    owner_id: str,
    trigger: str,
    remaining_before: int,
    remaining_after: int,
    repeat_save: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry = {
        "owner_type": owner_type,
        "owner_id": owner_id,
        "effect_id": effect.get("effect_id"),
        "source_action_id": effect.get("source_action_id"),
        "condition": effect.get("condition"),
        "trigger": trigger,
        "remaining_ticks_before": remaining_before,
        "remaining_ticks_after": remaining_after,
    }
    if repeat_save is not None:
        entry["repeat_save"] = repeat_save
    return entry

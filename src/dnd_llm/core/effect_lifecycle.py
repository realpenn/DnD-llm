from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .dice import RollService
from .models import Character, Combatant, GameState, Monster
from .rules.checks import d20_expression
from .rules.class_features import (
    INDOMITABLE_MIGHT_ACTION_ID,
    indomitable_might_total_floor,
    is_wearing_heavy_armor,
    monk_self_restoration_applies,
    saving_throw_proficiency_sources,
)
from .rules.combat import apply_damage
from .rules.conditions import exhaustion_d20_penalty, exhaustion_level, remove_condition

SELF_RESTORATION_ACTION_ID = "srd.self_restoration"
SELF_RESTORATION_CONDITIONS = ("charmed", "frightened", "poisoned")
BANISHMENT_DEFAULT_DESTINATION = "random_location_on_gm_chosen_associated_plane"


@dataclass
class EffectLifecycleResult:
    trigger: str
    actor_id: str
    expired: list[dict[str, Any]] = field(default_factory=list)
    ticked: list[dict[str, Any]] = field(default_factory=list)
    removed: list[dict[str, Any]] = field(default_factory=list)
    damage: list[dict[str, Any]] = field(default_factory=list)
    healing: list[dict[str, Any]] = field(default_factory=list)
    choice_required: list[dict[str, Any]] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(
            self.expired
            or self.ticked
            or self.removed
            or self.damage
            or self.healing
            or self.choice_required
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger": self.trigger,
            "actor_id": self.actor_id,
            "expired": self.expired,
            "ticked": self.ticked,
            "removed": self.removed,
            "damage": self.damage,
            "healing": self.healing,
            "choice_required": self.choice_required,
        }


def tick_effects(
    state: GameState,
    *,
    trigger: str,
    actor_id: str,
    roll_service: RollService | None = None,
) -> EffectLifecycleResult:
    result = EffectLifecycleResult(trigger=trigger, actor_id=actor_id)
    pending_saving_throw_consumptions: list[tuple[str, dict[str, Any]]] = []
    expired_effect_ids: set[str] = set()
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
            ended_by_condition = _ended_by_condition(state, effect, actor_id)
            if ended_by_condition is not None:
                result.expired.append(
                    _entry(
                        effect,
                        owner_type=owner_type,
                        owner_id=owner_id,
                        trigger=trigger,
                        remaining_before=_remaining_ticks(duration) or 0,
                        remaining_after=0,
                        ended_by_condition=ended_by_condition,
                    )
                )
                _remember_expired_effect(effect, expired_effect_ids)
                continue
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
                pending_saving_throw_consumptions.append(
                    (str(effect.get("target_id") or actor_id), repeat_save_entry)
                )
                if not repeat_save_entry["success"]:
                    failure_damage = _repeat_save_failure_damage(
                        state,
                        effect,
                        actor_id,
                        repeat_save,
                        roll_service,
                    )
                    if failure_damage is not None:
                        repeat_save_entry["failure_damage"] = failure_damage
                        result.damage.append(failure_damage)
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
                    _remember_expired_effect(effect, expired_effect_ids)
                    continue
            healing_entry = _turn_start_healing(
                state,
                effect,
                owner_type,
                owner_id,
                actor_id,
                trigger,
            )
            if healing_entry is not None:
                result.healing.append(healing_entry)
            remaining_before = _remaining_ticks(duration)
            if remaining_before is None:
                if repeat_save_entry is not None:
                    result.ticked.append(
                        _entry(
                            effect,
                            owner_type=owner_type,
                            owner_id=owner_id,
                            trigger=trigger,
                            remaining_before=0,
                            remaining_after=0,
                            repeat_save=repeat_save_entry,
                        )
                    )
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
                permanent_banishment = _permanent_banishment_on_full_duration(
                    state,
                    effect,
                    owner_type,
                    owner_id,
                )
                if permanent_banishment is not None:
                    entry["banishment_completed"] = permanent_banishment["entry"]
                    retained.append(permanent_banishment["effect"])
                result.expired.append(entry)
                _remember_expired_effect(effect, expired_effect_ids)
            else:
                duration["remaining_ticks"] = remaining_after
                result.ticked.append(entry)
                retained.append(effect)
        effects[:] = retained
    for target_id, repeat_save_entry in pending_saving_throw_consumptions:
        consumed = _consume_next_saving_throw_disadvantage(state, target_id)
        if consumed:
            repeat_save_entry["consumed_effects"] = consumed
    if trigger == "self_turn_end":
        _apply_monk_self_restoration(state, actor_id, result)
    if expired_effect_ids:
        _expire_child_effects(state, expired_effect_ids, result)
    return result


def _remember_expired_effect(effect: dict[str, Any], expired_effect_ids: set[str]) -> None:
    effect_id = effect.get("effect_id")
    if isinstance(effect_id, str) and effect_id:
        expired_effect_ids.add(effect_id)


def _expire_child_effects(
    state: GameState,
    expired_parent_ids: set[str],
    result: EffectLifecycleResult,
) -> None:
    pending_parent_ids = set(expired_parent_ids)
    processed_parent_ids: set[str] = set()
    while pending_parent_ids:
        current_parent_ids = pending_parent_ids - processed_parent_ids
        if not current_parent_ids:
            return
        processed_parent_ids.update(current_parent_ids)
        next_parent_ids: set[str] = set()
        for owner_type, owner_id, effects in _effect_lists(state):
            retained: list[dict[str, Any]] = []
            for effect in effects:
                parent_effect_id = effect.get("parent_effect_id")
                if isinstance(parent_effect_id, str) and parent_effect_id in current_parent_ids:
                    duration = effect.get("duration", {})
                    if not isinstance(duration, dict):
                        duration = {}
                    effect_id = effect.get("effect_id")
                    if isinstance(effect_id, str) and effect_id:
                        result.ticked[:] = [
                            entry
                            for entry in result.ticked
                            if entry.get("effect_id") != effect_id
                        ]
                    entry = _entry(
                        effect,
                        owner_type=owner_type,
                        owner_id=owner_id,
                        trigger=result.trigger,
                        remaining_before=_remaining_ticks(duration) or 0,
                        remaining_after=0,
                    )
                    entry["expired_parent_effect_id"] = parent_effect_id
                    result.expired.append(entry)
                    if isinstance(effect_id, str) and effect_id:
                        next_parent_ids.add(effect_id)
                    continue
                retained.append(effect)
            effects[:] = retained
        pending_parent_ids = next_parent_ids


def _apply_monk_self_restoration(
    state: GameState,
    actor_id: str,
    result: EffectLifecycleResult,
) -> None:
    character = _character_for_actor(state, actor_id)
    if character is None or not monk_self_restoration_applies(character):
        return
    effect_lists = _target_effect_lists(state, actor_id)
    present = [
        condition
        for condition in SELF_RESTORATION_CONDITIONS
        if any(
            effect.get("condition") == condition
            for _, _, effects in effect_lists
            for effect in effects
        )
    ]
    if not present:
        return
    if len(present) > 1:
        result.choice_required.append(
            {
                "type": "self_restoration",
                "action_id": SELF_RESTORATION_ACTION_ID,
                "actor_id": actor_id,
                "conditions": present,
                "reason": "multiple_eligible_conditions",
            }
        )
        return
    condition = present[0]
    removed: dict[str, int] = {}
    removed_owners: list[dict[str, Any]] = []
    for owner_type, owner_id, effects in effect_lists:
        count = remove_condition(effects, condition)
        if not count:
            continue
        removed[condition] = removed.get(condition, 0) + count
        removed_owners.append(
            {
                "owner_type": owner_type,
                "owner_id": owner_id,
                "condition": condition,
                "count": count,
            }
        )
    if removed:
        result.removed.append(
            {
                "type": "self_restoration",
                "action_id": SELF_RESTORATION_ACTION_ID,
                "actor_id": actor_id,
                "removed": removed,
                "removed_owners": removed_owners,
            }
        )


def _character_for_actor(state: GameState, actor_id: str) -> Character | None:
    if actor_id in state.characters:
        return state.characters[actor_id]
    if state.encounter is not None and actor_id in state.encounter.combatants:
        combatant = state.encounter.combatants[actor_id]
        return state.characters.get(combatant.entity_id)
    return None


def _target_effect_lists(
    state: GameState, actor_id: str
) -> list[tuple[str, str, list[dict[str, Any]]]]:
    effect_lists: list[tuple[str, str, list[dict[str, Any]]]] = []
    seen: set[int] = set()

    def add(owner_type: str, owner_id: str, effects: list[dict[str, Any]]) -> None:
        list_id = id(effects)
        if list_id in seen:
            return
        seen.add(list_id)
        effect_lists.append((owner_type, owner_id, effects))

    if actor_id in state.characters:
        add("character", actor_id, state.characters[actor_id].status_effects)
    if actor_id in state.monsters:
        add("monster", actor_id, state.monsters[actor_id].status_effects)
    if state.encounter is not None and actor_id in state.encounter.combatants:
        combatant = state.encounter.combatants[actor_id]
        add("combatant", actor_id, combatant.status_effects)
        if combatant.entity_id in state.characters:
            add(
                "character",
                combatant.entity_id,
                state.characters[combatant.entity_id].status_effects,
            )
        if combatant.entity_id in state.monsters:
            add("monster", combatant.entity_id, state.monsters[combatant.entity_id].status_effects)
    return effect_lists


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


def _permanent_banishment_on_full_duration(
    state: GameState,
    effect: dict[str, Any],
    owner_type: str,
    owner_id: str,
) -> dict[str, Any] | None:
    modifiers = effect.get("passive_modifiers", {})
    if not isinstance(modifiers, dict):
        return None
    if modifiers.get("banished") is not True or modifiers.get("out_of_play") is not True:
        return None
    creature_types_raw = modifiers.get("does_not_return_if_full_duration_creature_types")
    if not isinstance(creature_types_raw, list):
        return None
    creature_types = {
        str(creature_type).lower()
        for creature_type in creature_types_raw
        if isinstance(creature_type, str) and creature_type
    }
    target_id = _effect_target_id(effect, owner_type, owner_id)
    if target_id is None:
        return None
    creature_type = _creature_type_for_actor(state, target_id).lower()
    if creature_type not in creature_types:
        return None
    destination = str(
        modifiers.get(
            "full_duration_transport_destination",
            BANISHMENT_DEFAULT_DESTINATION,
        )
    )
    entry = {
        "target_id": target_id,
        "creature_type": creature_type,
        "does_not_return": True,
        "destination": destination,
    }
    return {"entry": entry, "effect": _permanent_banishment_effect(effect, entry)}


def _turn_start_healing(
    state: GameState,
    effect: dict[str, Any],
    owner_type: str,
    owner_id: str,
    actor_id: str,
    trigger: str,
) -> dict[str, Any] | None:
    if trigger != "target_turn_start":
        return None
    modifiers = effect.get("passive_modifiers", {})
    if not isinstance(modifiers, dict):
        return None
    amount_raw = modifiers.get("regenerate_hit_points_at_turn_start")
    if amount_raw is None:
        return None
    amount = max(0, int(amount_raw))
    if amount <= 0:
        return None
    target_id = _effect_target_id(effect, owner_type, owner_id) or actor_id
    try:
        target = state.entity_for_actor(target_id)
    except KeyError:
        target = _effect_owner(state, owner_type, owner_id)
    if target is None or not hasattr(target, "hp_current") or not hasattr(target, "hp_max"):
        return None
    hp_before = int(getattr(target, "hp_current"))
    hp_max = int(getattr(target, "hp_max"))
    hp_after = min(hp_max, hp_before + amount)
    setattr(target, "hp_current", hp_after)
    _sync_linked_actor_hp(state, target, hp_after)
    return {
        "type": "healing",
        "source_action_id": effect.get("source_action_id"),
        "effect_id": effect.get("effect_id"),
        "target_id": target_id,
        "amount": amount,
        "applied": hp_after - hp_before,
        "hp_before": hp_before,
        "hp_after": hp_after,
        "trigger": trigger,
        "owner_type": owner_type,
        "owner_id": owner_id,
    }


def _sync_linked_actor_hp(state: GameState, target: Any, hp_current: int) -> None:
    entity_id = getattr(target, "entity_id", None)
    if isinstance(entity_id, str) and entity_id in state.characters:
        state.characters[entity_id].hp_current = hp_current
    target_id = getattr(target, "id", None)
    if state.encounter is None or not isinstance(target_id, str):
        return
    for combatant in state.encounter.combatants.values():
        if combatant.entity_id == target_id:
            combatant.hp_current = hp_current


def _effect_target_id(effect: dict[str, Any], owner_type: str, owner_id: str) -> str | None:
    target_id = effect.get("target_id")
    if isinstance(target_id, str) and target_id:
        return target_id
    if owner_type in {"character", "monster", "combatant"} and owner_id:
        return owner_id
    return None


def _creature_type_for_actor(state: GameState, actor_id: str) -> str:
    try:
        actor = state.entity_for_actor(actor_id)
    except KeyError:
        return "humanoid"
    entity_id = getattr(actor, "entity_id", None)
    if isinstance(entity_id, str) and entity_id in state.monsters:
        return str(state.monsters[entity_id].creature_type)
    return str(getattr(actor, "creature_type", "humanoid"))


def _permanent_banishment_effect(
    effect: dict[str, Any],
    entry: dict[str, Any],
) -> dict[str, Any]:
    permanent_effect = dict(effect)
    permanent_effect["effect_id"] = f"{effect.get('effect_id', 'effect')}:permanent_banishment"
    permanent_effect["condition"] = None
    permanent_effect["passive_modifiers"] = {
        "banished": True,
        "out_of_play": True,
        "permanent_banishment": True,
        "does_not_return": True,
        "full_duration_transport_destination": entry["destination"],
    }
    permanent_effect["duration"] = {}
    permanent_effect["tick_on"] = None
    permanent_effect["concentration"] = False
    audit = dict(permanent_effect.get("audit", {}))
    audit["permanent_banishment"] = entry
    permanent_effect["audit"] = audit
    return permanent_effect


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
        duration = effect.get("duration", {})
        if isinstance(duration, dict):
            turn_owner_id = duration.get("turn_owner_id")
            if isinstance(turn_owner_id, str) and turn_owner_id:
                return turn_owner_id == actor_id
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


def _ended_by_condition(state: GameState, effect: dict[str, Any], actor_id: str) -> str | None:
    modifiers = effect.get("passive_modifiers", {})
    if not isinstance(modifiers, dict):
        return None
    target_id = effect.get("target_id")
    checked_actor_id = target_id if isinstance(target_id, str) else actor_id
    conditions = _ending_conditions(modifiers)
    for condition in conditions:
        if _actor_has_condition(state, checked_actor_id, condition):
            return condition
    if modifiers.get("ends_if_heavy_armor") is True:
        character = _character_for_actor(state, checked_actor_id)
        if character is not None and is_wearing_heavy_armor(character):
            return "heavy_armor"
    return None


def _ending_conditions(modifiers: dict[str, Any]) -> list[str]:
    conditions: list[str] = []
    condition = modifiers.get("ends_if_condition")
    if isinstance(condition, str) and condition:
        conditions.append(condition)
    plural = modifiers.get("ends_if_conditions")
    if isinstance(plural, list):
        conditions.extend(str(item) for item in plural if isinstance(item, str) and item)
    return conditions


def _actor_has_condition(state: GameState, actor_id: str, condition: str) -> bool:
    return any(
        effect.get("condition") == condition
        for _, _, effects in _target_effect_lists(state, actor_id)
        for effect in effects
    )


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
    if timed_until in {"duration_12_hours", "concentration_12_hours"}:
        return 7200
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
    base_bonus, proficient, proficiency_sources = _saving_throw_bonus(state, target, ability)
    status_effects = getattr(target, "status_effects", [])
    exhaustion = exhaustion_level(status_effects)
    penalty = exhaustion_d20_penalty(status_effects)
    bonus = base_bonus - penalty
    status_advantage, status_sources = _saving_throw_status_advantage(target)
    roll = roll_service.roll(d20_expression(bonus), advantage=status_advantage)
    total = roll.total
    dc = int(repeat_save["dc"])
    indomitable_might = _indomitable_might_repeat_save(
        _proficiency_source(state, target),
        ability,
        total,
        dc,
    )
    if indomitable_might is not None:
        total = int(indomitable_might["total_after"])
    entry = {
        "ability": ability,
        "dc": dc,
        "dc_source": repeat_save.get("dc_source"),
        "base_bonus": base_bonus,
        "bonus": bonus,
        "proficient": proficient,
        "proficiency_sources": proficiency_sources,
        "exhaustion_level": exhaustion,
        "d20_penalty": penalty,
        "status_advantage": status_advantage,
        "status_sources": status_sources,
        "roll": roll.to_dict(),
        "total": total,
        "success": total >= dc,
    }
    if indomitable_might is not None:
        entry["indomitable_might"] = indomitable_might
    return entry


def _repeat_save_failure_damage(
    state: GameState,
    effect: dict[str, Any],
    actor_id: str,
    repeat_save: dict[str, Any],
    roll_service: RollService,
) -> dict[str, Any] | None:
    failure_damage = repeat_save.get("failure_damage")
    if not isinstance(failure_damage, dict):
        return None
    target_id = str(effect.get("target_id") or actor_id)
    target = state.entity_for_actor(target_id)
    dice = str(failure_damage["dice"])
    damage_type = str(failure_damage["damage_type"]).lower()
    hp_before = int(getattr(target, "hp_current"))
    temp_hp_before = int(getattr(target, "temp_hp", 0))
    roll = roll_service.roll(dice)
    applied = apply_damage(target, roll.total, damage_type)
    _sync_hp_state_for_target(state, target_id, target)
    return {
        "type": "repeat_save_failure_damage",
        "target_id": target_id,
        "effect_id": effect.get("effect_id"),
        "source_action_id": effect.get("source_action_id"),
        "damage_type": damage_type,
        "dice": dice,
        "roll": roll.to_dict(),
        "amount": roll.total,
        "applied": applied,
        "hp_before": hp_before,
        "hp_after": int(getattr(target, "hp_current")),
        "temp_hp_before": temp_hp_before,
        "temp_hp_after": int(getattr(target, "temp_hp", 0)),
    }


def _sync_hp_state_for_target(
    state: GameState,
    target_id: str,
    target: Character | Monster | Combatant,
) -> None:
    def copy_hp(source: Character | Monster | Combatant, destination: Any) -> None:
        for field_name in (
            "hp_current",
            "hp_max",
            "temp_hp",
            "temp_hp_source_effect_id",
            "death_save_successes",
            "death_save_failures",
            "stable",
            "dead",
        ):
            if hasattr(source, field_name) and hasattr(destination, field_name):
                setattr(destination, field_name, getattr(source, field_name))

    if isinstance(target, Combatant):
        if target.entity_id in state.characters:
            copy_hp(target, state.characters[target.entity_id])
        if target.entity_id in state.monsters:
            copy_hp(target, state.monsters[target.entity_id])
        return
    if isinstance(target, Character):
        if state.encounter is None:
            return
        for combatant in state.encounter.combatants.values():
            if combatant.entity_id == target.id or combatant.id == target_id:
                copy_hp(target, combatant)
        return
    if isinstance(target, Monster) and state.encounter is not None:
        for combatant in state.encounter.combatants.values():
            if combatant.entity_id == target.id or combatant.id == target_id:
                copy_hp(target, combatant)


def _indomitable_might_repeat_save(
    target: Any,
    ability: str,
    total: int,
    dc: int,
) -> dict[str, Any] | None:
    if not isinstance(target, Character):
        return None
    after_total = indomitable_might_total_floor(target, ability=ability, total=total)
    if after_total is None:
        return None
    return {
        "source_action_id": INDOMITABLE_MIGHT_ACTION_ID,
        "ability": ability.lower(),
        "strength_score": after_total,
        "total_before": total,
        "total_after": after_total,
        "success": after_total >= dc,
    }


def _saving_throw_status_advantage(target: Any) -> tuple[str | None, list[dict[str, Any]]]:
    disadvantage_sources: list[dict[str, Any]] = []
    for effect in getattr(target, "status_effects", []):
        modifiers = effect.get("passive_modifiers", {})
        if not isinstance(modifiers, dict):
            continue
        if modifiers.get("next_saving_throw_disadvantage") is not True:
            continue
        disadvantage_sources.append(
            {
                "kind": "disadvantage",
                "condition": effect.get("condition"),
                "effect_id": effect.get("effect_id"),
                "source_action_id": effect.get("source_action_id"),
                "modifier": "next_saving_throw_disadvantage",
            }
        )
    return ("disadvantage" if disadvantage_sources else None, disadvantage_sources)


def _consume_next_saving_throw_disadvantage(
    state: GameState,
    actor_id: str,
) -> list[dict[str, Any]]:
    removed: list[dict[str, Any]] = []
    for owner_type, owner_id, effects in _target_effect_lists(state, actor_id):
        retained: list[dict[str, Any]] = []
        for effect in effects:
            modifiers = effect.get("passive_modifiers", {})
            if (
                isinstance(modifiers, dict)
                and modifiers.get("next_saving_throw_disadvantage") is True
            ):
                removed.append(
                    {
                        "owner_type": owner_type,
                        "owner_id": owner_id,
                        "effect_id": effect.get("effect_id"),
                        "condition": effect.get("condition"),
                        "source_action_id": effect.get("source_action_id"),
                    }
                )
                continue
            retained.append(effect)
        effects[:] = retained
    return removed


def _saving_throw_bonus(
    state: GameState, target: Any, ability: str
) -> tuple[int, bool, list[dict[str, Any]]]:
    source = _ability_source(state, target)
    proficiency_source = _proficiency_source(state, target)
    proficiency_sources = saving_throw_proficiency_sources(proficiency_source, ability)
    proficient = bool(proficiency_sources)
    bonus = _ability_modifier(source, ability)
    if proficient:
        bonus += int(getattr(proficiency_source, "proficiency_bonus", 2))
    return bonus, proficient, proficiency_sources


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
    ended_by_condition: str | None = None,
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
    if ended_by_condition is not None:
        entry["ended_by_condition"] = ended_by_condition
    return entry

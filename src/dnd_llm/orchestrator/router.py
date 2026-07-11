from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core.automation.definitions import ActionDefinition, ItemDefinition
from ..core.memory import retrieve_memory
from ..core.models import Character, Combatant, GameState, Monster
from ..core.positioning import TacticalGraph
from ..core.rules.class_features import has_monk_open_hand_feature

VISIBLE_WORLD_FLAG_KEYS = {"dynamic_zones"}
ROUTER_STEP_OF_THE_WIND_ACTION_IDS = frozenset(
    {"srd.step_of_the_wind", "srd.step_of_the_wind_focus"}
)
ROUTER_FLEET_STEP_ACTION_ID = "srd.fleet_step"
ROUTER_FLEET_STEP_CONDITION = "fleet_step_available"
ROUTER_LIGHT_WEAPON_ATTACK_CONDITION = "light_weapon_attack_this_turn"
ROUTER_LIGHT_EXTRA_ATTACK_USED_CONDITION = "light_extra_attack_used_this_turn"


@dataclass
class ContextSlice:
    mode: str
    actor_id: str | None
    visible_state: dict[str, Any]
    affordances: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    memory_fragments: list[dict[str, Any]] = field(default_factory=list)


def build_context_slice(
    state: GameState,
    *,
    actor_id: str | None,
    actions: dict[str, ActionDefinition],
    items: dict[str, ItemDefinition] | None = None,
    query: str = "",
) -> ContextSlice:
    mode = "combat" if state.encounter is not None else state.session_mode
    visible_state: dict[str, Any] = {
        "campaign_id": state.campaign_id,
        "session_mode": mode,
        "world": _visible_world_state(state),
        "config": state.config.to_dict(),
    }
    if state.encounter is not None:
        visible_state["encounter"] = {
            "round_number": state.encounter.round_number,
            "current_combatant_id": state.encounter.current_combatant_id,
            "combatants": {
                key: {
                    "name": combatant.name,
                    "side": combatant.side,
                    "hp": _visible_hp(
                        combatant.hp_current,
                        combatant.hp_max,
                        strategy=state.config.hp_display_strategy,
                    ),
                    "position_node_id": combatant.position_node_id,
                }
                for key, combatant in state.encounter.combatants.items()
            },
        }
    affordances = []
    if (
        actor_id is not None
        and state.encounter is not None
        and actor_id == state.encounter.current_combatant_id
    ):
        actor_side = _actor_side(state, actor_id)
        action_ids = _action_ids_for_actor(state, actor_id, actions=actions, items=items)
        visible_actor_items = _visible_actor_items(
            state,
            actor_id,
            action_ids=action_ids,
            actions=actions,
            items=items,
        )
        if visible_actor_items:
            visible_state["actor"] = visible_actor_items
        for action_id in action_ids:
            action = actions.get(action_id)
            if action is None:
                continue
            if not _action_budget_available(state, actor_id, action):
                continue
            if not _action_items_available(state, actor_id, action):
                continue
            affordance = {
                "action_id": action.id,
                "name": action.localization.get("zh") or action.name,
                "economy": action.action_economy,
                "cost": action.cost.to_dict(),
                "target_type": _target_type(action),
                "target_policy": action.target_policy,
                "candidate_target_ids": _candidate_target_ids(
                    state,
                    actor_id=actor_id,
                    actor_side=actor_side,
                    action=action,
                ),
            }
            if action.action_type == "weapon_attack":
                affordance.update(_weapon_attack_affordance(state, actor_id, action))
            affordances.append(affordance)
    return ContextSlice(
        mode=mode,
        actor_id=actor_id,
        visible_state=visible_state,
        affordances=affordances,
        summary=state.summary,
        memory_fragments=[
            item.to_context_dict()
            for item in retrieve_memory(
                state,
                query=query,
                limit=3,
                visible_to=_memory_visibility_for_actor(state, actor_id),
            )
        ],
    )


def _memory_visibility_for_actor(state: GameState, actor_id: str | None) -> set[str]:
    visible_to = {"public"}
    if actor_id is None:
        return visible_to
    entity_id = actor_id
    if state.encounter is not None:
        combatant = state.encounter.combatants.get(actor_id)
        if combatant is not None:
            entity_id = combatant.entity_id
    visible_to.add(f"private:{entity_id}")
    return visible_to


def _visible_world_state(state: GameState) -> dict[str, Any]:
    return {
        "current_zone_id": state.world.current_zone_id,
        "time_index": state.world.time_index,
        "zone_edges": dict(state.world.zone_edges),
        "flags": {
            key: value for key, value in state.world.flags.items() if key in VISIBLE_WORLD_FLAG_KEYS
        },
        "active_effects": [_visible_world_effect(effect) for effect in state.world.active_effects],
    }


def _visible_world_effect(effect: dict[str, Any]) -> dict[str, Any]:
    return {
        key: effect[key]
        for key in ("effect_type", "scope", "duration", "metadata")
        if key in effect
    }


def _visible_hp(current: int, maximum: int, *, strategy: str) -> str:
    if maximum <= 0:
        return "unknown"
    if strategy == "exact":
        return f"{current}/{maximum}"
    ratio = current / maximum
    if ratio >= 0.75:
        return "Healthy"
    if ratio >= 0.5:
        return "Injured"
    if ratio >= 0.25:
        return "Bloodied"
    return "Critical"


def _actor_side(state: GameState, actor_id: str) -> str | None:
    if state.encounter is None:
        return None
    combatant = state.encounter.combatants.get(actor_id)
    return combatant.side if combatant is not None else None


def _action_ids_for_actor(
    state: GameState,
    actor_id: str,
    *,
    actions: dict[str, ActionDefinition],
    items: dict[str, ItemDefinition] | None,
) -> list[str]:
    actor_action_ids: list[str]
    if state.encounter is not None and actor_id in state.encounter.combatants:
        combatant = state.encounter.combatants[actor_id]
        if combatant.entity_id in state.characters:
            actor_action_ids = list(state.characters[combatant.entity_id].actions)
        elif combatant.entity_id in state.monsters:
            actor_action_ids = list(state.monsters[combatant.entity_id].actions)
        else:
            actor_action_ids = list(combatant.actions)
    else:
        actor = state.entity_for_actor(actor_id)
        actor_action_ids = list(getattr(actor, "actions", []))

    owner = _resource_owner(state, actor_id)
    owned_item_ids = _owned_item_ids(owner)
    item_action_ids: list[str] = []
    if items is not None:
        for item_id in owned_item_ids:
            item = items.get(item_id)
            if item is not None:
                item_action_ids.extend(item.actions)
    else:
        item_action_ids.extend(
            action.id for action in actions.values() if _action_item_id(action) in owned_item_ids
        )
    return list(dict.fromkeys([*actor_action_ids, *item_action_ids]))


def _visible_actor_items(
    state: GameState,
    actor_id: str,
    *,
    action_ids: list[str],
    actions: dict[str, ActionDefinition],
    items: dict[str, ItemDefinition] | None,
) -> dict[str, Any]:
    owner = _resource_owner(state, actor_id)
    relevant_item_ids: set[str] = set()
    for action_id in action_ids:
        action = actions.get(action_id)
        if action is None:
            continue
        relevant_item_ids.update(action.cost.items)
        item_id = _action_item_id(action)
        if item_id is not None:
            relevant_item_ids.add(item_id)
        if items is not None:
            relevant_item_ids.update(
                item.id for item in items.values() if action_id in item.actions
            )
    equipment = [
        str(item_id)
        for item_id in getattr(owner, "equipment", [])
        if str(item_id) in relevant_item_ids
    ]
    inventory = {
        str(item_id): int(quantity)
        for item_id, quantity in getattr(owner, "inventory", {}).items()
        if str(item_id) in relevant_item_ids and int(quantity) > 0
    }
    if not equipment and not inventory:
        return {}
    return {"equipment": equipment, "inventory": inventory}


def _owned_item_ids(actor: Character | Monster | Combatant | None) -> set[str]:
    if actor is None:
        return set()
    item_ids = {
        str(item_id)
        for item_id, quantity in getattr(actor, "inventory", {}).items()
        if int(quantity) > 0
    }
    item_ids.update(str(item_id) for item_id in getattr(actor, "equipment", []))
    return item_ids


def _action_item_id(action: ActionDefinition) -> str | None:
    item_id = action.properties.get("weapon_item_id", action.requirements.get("item"))
    return str(item_id) if isinstance(item_id, str) and item_id else None


def _action_items_available(
    state: GameState,
    actor_id: str,
    action: ActionDefinition,
) -> bool:
    owner = _resource_owner(state, actor_id)
    inventory = getattr(owner, "inventory", {})
    return all(
        int(inventory.get(item_id, 0)) >= amount for item_id, amount in action.cost.items.items()
    )


def _weapon_attack_affordance(
    state: GameState,
    actor_id: str,
    action: ActionDefinition,
) -> dict[str, Any]:
    properties = action.properties.get("weapon_properties", [])
    if isinstance(properties, str):
        properties = [properties]
    weapon_properties = {str(item).casefold() for item in properties}
    optional_params: dict[str, Any] = {}
    if "versatile" in weapon_properties:
        optional_params["two_handed"] = {"type": "boolean"}
    if "finesse" in weapon_properties:
        optional_params["weapon_ability"] = {
            "type": "string",
            "allowed_values": ["str", "dex"],
        }

    light_extra_attack = _light_extra_attack_available(state, actor_id, action)
    if light_extra_attack:
        optional_params["use_light_extra_attack"] = {"type": "boolean", "required_value": True}

    mastery_property = action.properties.get("weapon_mastery_property")
    if _weapon_mastery_available(state, actor_id, action, mastery_property):
        optional_params["use_weapon_mastery"] = {"type": "boolean"}

    payload: dict[str, Any] = {"optional_params": optional_params}
    if isinstance(mastery_property, str) and mastery_property:
        payload["weapon_mastery_property"] = mastery_property
    if light_extra_attack:
        payload["light_extra_attack_economy"] = (
            "none"
            if str(mastery_property).casefold() == "nick"
            and _weapon_mastery_available(state, actor_id, action, mastery_property)
            else "bonus_action"
        )
    return payload


def _weapon_mastery_available(
    state: GameState,
    actor_id: str,
    action: ActionDefinition,
    mastery_property: Any,
) -> bool:
    if not isinstance(mastery_property, str) or not mastery_property:
        return False
    owner = _resource_owner(state, actor_id)
    if not isinstance(owner, Character):
        return False
    weapon_item_id = action.properties.get("weapon_item_id")
    return (
        isinstance(weapon_item_id, str)
        and str(owner.feature_choices.get(f"weapon_mastery.{weapon_item_id}", "")).casefold()
        == mastery_property.casefold()
    )


def _light_extra_attack_available(
    state: GameState,
    actor_id: str,
    action: ActionDefinition,
) -> bool:
    properties = action.properties.get("weapon_properties", [])
    if isinstance(properties, str):
        properties = [properties]
    if "light" not in {str(item).casefold() for item in properties}:
        return False
    if state.encounter is not None and state.encounter.current_combatant_id != actor_id:
        return False
    actor = _actor_entity(state, actor_id)
    effects = _status_effects_for(state, actor)
    initial = next(
        (
            effect
            for effect in effects
            if effect.get("condition") == ROUTER_LIGHT_WEAPON_ATTACK_CONDITION
        ),
        None,
    )
    if initial is None:
        return False
    if action.properties.get("weapon_item_id") == initial.get("audit", {}).get("weapon_item_id"):
        return False
    return not any(
        effect.get("condition") == ROUTER_LIGHT_EXTRA_ATTACK_USED_CONDITION for effect in effects
    )


def _candidate_target_ids(
    state: GameState,
    *,
    actor_id: str,
    actor_side: str | None,
    action: ActionDefinition,
) -> list[str]:
    if state.encounter is None:
        return []
    policy = action.target_policy
    if int(policy.get("max", policy.get("min", 0)) or 0) == 0:
        return []
    if policy.get("self") is True:
        return [actor_id]
    harmful = bool(policy.get("harmful", False))
    candidates: list[str] = []
    for combatant_id, combatant in state.encounter.combatants.items():
        if harmful and actor_side is not None and combatant.side == actor_side:
            continue
        if not _target_in_range_and_los(state, actor_id, combatant_id, action):
            continue
        candidates.append(combatant_id)
    return candidates


def _action_budget_available(
    state: GameState,
    actor_id: str,
    action: ActionDefinition,
) -> bool:
    action_economy = action.action_economy
    if action.action_type == "weapon_attack" and _light_extra_attack_available(
        state,
        actor_id,
        action,
    ):
        mastery_property = action.properties.get("weapon_mastery_property")
        action_economy = (
            "none"
            if str(mastery_property).casefold() == "nick"
            and _weapon_mastery_available(state, actor_id, action, mastery_property)
            else "bonus_action"
        )
    if state.encounter is None or action_economy == "none":
        return True
    budget = state.encounter.action_budgets.get(actor_id)
    if budget is None:
        return True
    if _fleet_step_makes_step_available(state, actor_id, action):
        return True
    if action_economy == "movement":
        return int(budget.get("movement", 0)) > 0
    return int(budget.get(action_economy, 0)) > 0


def _fleet_step_makes_step_available(
    state: GameState,
    actor_id: str,
    action: ActionDefinition,
) -> bool:
    if action.id not in ROUTER_STEP_OF_THE_WIND_ACTION_IDS:
        return False
    owner = _resource_owner(state, actor_id)
    if not isinstance(owner, Character) or not has_monk_open_hand_feature(owner, level=11):
        return False
    actor = _actor_entity(state, actor_id)
    return any(
        effect.get("condition") == ROUTER_FLEET_STEP_CONDITION
        and effect.get("source_action_id") == ROUTER_FLEET_STEP_ACTION_ID
        for effect in _status_effects_for(state, actor)
    )


def _actor_entity(state: GameState, actor_id: str) -> Character | Monster | Combatant | None:
    try:
        return state.entity_for_actor(actor_id)
    except KeyError:
        return None


def _resource_owner(state: GameState, actor_id: str) -> Character | Monster | Combatant | None:
    actor = _actor_entity(state, actor_id)
    if isinstance(actor, Combatant) and actor.entity_id in state.characters:
        return state.characters[actor.entity_id]
    if isinstance(actor, Combatant) and actor.entity_id in state.monsters:
        return state.monsters[actor.entity_id]
    return actor


def _status_effects_for(
    state: GameState,
    actor: Character | Monster | Combatant | None,
) -> list[dict[str, Any]]:
    if actor is None:
        return []
    effects = list(getattr(actor, "status_effects", []))
    if isinstance(actor, Combatant) and actor.entity_id in state.characters:
        effects.extend(state.characters[actor.entity_id].status_effects)
    if isinstance(actor, Combatant) and actor.entity_id in state.monsters:
        effects.extend(state.monsters[actor.entity_id].status_effects)
    return effects


def _target_type(action: ActionDefinition) -> str:
    policy = action.target_policy
    if policy.get("self") is True:
        return "self"
    if int(policy.get("max", policy.get("min", 0)) or 0) == 0:
        return "none"
    return "hostile" if bool(policy.get("harmful", False)) else "creature"


def _target_in_range_and_los(
    state: GameState,
    actor_id: str,
    target_id: str,
    action: ActionDefinition,
) -> bool:
    if state.encounter is None or state.encounter.tactical_graph is None:
        return True
    actor = state.encounter.combatants.get(actor_id)
    target = state.encounter.combatants.get(target_id)
    if (
        actor is None
        or target is None
        or actor.position_node_id is None
        or target.position_node_id is None
    ):
        return True
    max_range = action.range.get("normal_ft") or action.range.get("reach_ft")
    if max_range is None:
        return True
    graph = TacticalGraph.from_dict(state.encounter.tactical_graph)
    distance = graph.shortest_distance(actor.position_node_id, target.position_node_id)
    return (
        distance is not None
        and distance <= int(max_range)
        and graph.has_line_of_sight(actor.position_node_id, target.position_node_id)
    )

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core.automation.definitions import ActionDefinition
from ..core.memory import retrieve_memory
from ..core.models import GameState
from ..core.positioning import TacticalGraph

VISIBLE_WORLD_FLAG_KEYS = {"dynamic_zones"}


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
        for action_id in _action_ids_for_actor(state, actor_id):
            action = actions.get(action_id)
            if action is None:
                continue
            if not _action_budget_available(state, actor_id, action):
                continue
            affordances.append(
                {
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
            )
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
            )
        ],
    )


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


def _action_ids_for_actor(state: GameState, actor_id: str) -> list[str]:
    if state.encounter is not None and actor_id in state.encounter.combatants:
        combatant = state.encounter.combatants[actor_id]
        if combatant.entity_id in state.characters:
            return list(state.characters[combatant.entity_id].actions)
        if combatant.entity_id in state.monsters:
            return list(state.monsters[combatant.entity_id].actions)
    actor = state.entity_for_actor(actor_id)
    return list(getattr(actor, "actions", []))


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
    if state.encounter is None or action.action_economy == "none":
        return True
    budget = state.encounter.action_budgets.get(actor_id)
    if budget is None:
        return True
    if action.action_economy == "movement":
        return int(budget.get("movement", 0)) > 0
    return int(budget.get(action.action_economy, 0)) > 0


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

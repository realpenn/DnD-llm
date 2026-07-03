from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dnd_llm.core.automation.definitions import ActionDefinition
from dnd_llm.core.models import GameState
from dnd_llm.core.positioning import TacticalGraph
from dnd_llm.core.resolver import PlayerActionDraft
from dnd_llm.core.rules.class_features import class_feature_speed_bonus
from dnd_llm.core.rules.conditions import effective_speed
from dnd_llm.orchestrator.tactics import MonsterTacticsLibrary


@dataclass
class TimeoutPolicy:
    timeout_seconds: int = 900


class TimeoutController:
    def __init__(self, policy: TimeoutPolicy | None = None):
        self.policy = policy or TimeoutPolicy()
        self.turn_started_at: dict[str, int] = {}

    def mark_turn_start(self, combatant_id: str, now: int) -> None:
        self.turn_started_at[combatant_id] = now

    def is_timed_out(self, combatant_id: str, now: int) -> bool:
        started = self.turn_started_at.get(combatant_id)
        if started is None:
            return False
        return now - started >= self.policy.timeout_seconds

    def takeover_draft(
        self,
        *,
        state: GameState,
        now: int,
        tactics: MonsterTacticsLibrary,
        actions: dict[str, ActionDefinition],
        roll_service: Any,
    ) -> PlayerActionDraft | None:
        if state.encounter is None or state.encounter.current_combatant_id is None:
            return None
        current = state.encounter.current_combatant_id
        if not self.is_timed_out(current, now):
            return None
        combatant = state.encounter.combatants[current]
        if combatant.side != "party":
            return tactics.draft_for_current_turn(
                state=state,
                actions=actions,
                roll_service=roll_service,
            )
        enemy = _nearest_enemy_id(state, current)
        if enemy is not None:
            attack_action_id = _best_owned_harmful_action_id(
                state,
                actor_id=current,
                target_id=enemy,
                actions=actions,
            )
            if attack_action_id is not None:
                return PlayerActionDraft(
                    actor_id=current,
                    verb=attack_action_id,
                    candidate_action_id=attack_action_id,
                    target_ids=[enemy],
                    raw_text="[timeout takeover] use owned action against nearest enemy",
                )
            move_to = _step_toward_enemy(state, actor_id=current, target_id=enemy, actions=actions)
            if move_to is not None:
                return PlayerActionDraft(
                    actor_id=current,
                    verb="srd.move",
                    candidate_action_id="srd.move",
                    params={"to_position_node_id": move_to},
                    raw_text="[timeout takeover] move toward nearest enemy",
                )
        support = _support_or_positioning_draft(state, actor_id=current, actions=actions)
        if support is not None:
            return support
        if "srd.dodge" in actions:
            return PlayerActionDraft(
                actor_id=current,
                verb="srd.dodge",
                candidate_action_id="srd.dodge",
                raw_text="[timeout takeover] no stronger legal fallback, dodge",
            )
        return None


def _nearest_enemy_id(state: GameState, actor_id: str) -> str | None:
    if state.encounter is None:
        return None
    actor = state.encounter.combatants.get(actor_id)
    if actor is None:
        return None
    enemies = [
        combatant
        for combatant in state.encounter.combatants.values()
        if combatant.side != actor.side and combatant.hp_current > 0
    ]
    if not enemies:
        return None
    graph = _tactical_graph(state)
    if graph is None or actor.position_node_id is None:
        return sorted(enemies, key=lambda combatant: (combatant.hp_current, combatant.id))[0].id
    with_distance = []
    for enemy in enemies:
        distance = (
            graph.shortest_distance(actor.position_node_id, enemy.position_node_id)
            if enemy.position_node_id is not None
            else None
        )
        if distance is not None:
            with_distance.append((distance, enemy.hp_current, enemy.id))
    if with_distance:
        return min(with_distance)[2]
    return sorted(enemies, key=lambda combatant: (combatant.hp_current, combatant.id))[0].id


def _best_owned_harmful_action_id(
    state: GameState,
    *,
    actor_id: str,
    target_id: str,
    actions: dict[str, ActionDefinition],
) -> str | None:
    for action_id in _owned_action_ids(state, actor_id):
        action = actions.get(action_id)
        if action is None:
            continue
        if not bool(action.target_policy.get("harmful", False)):
            continue
        if int(action.target_policy.get("min", 0) or 0) <= 0:
            continue
        if action.action_economy == "reaction":
            continue
        if _target_in_range(state, actor_id=actor_id, target_id=target_id, action=action):
            return action.id
    return None


def _owned_action_ids(state: GameState, actor_id: str) -> list[str]:
    if state.encounter is not None and actor_id in state.encounter.combatants:
        combatant = state.encounter.combatants[actor_id]
        if combatant.entity_id in state.characters:
            return list(state.characters[combatant.entity_id].actions)
        if combatant.entity_id in state.monsters:
            return list(state.monsters[combatant.entity_id].actions)
        return list(combatant.actions)
    entity = state.entity_for_actor(actor_id)
    return list(getattr(entity, "actions", []))


def _target_in_range(
    state: GameState,
    *,
    actor_id: str,
    target_id: str,
    action: ActionDefinition,
) -> bool:
    if state.encounter is None:
        return True
    graph = _tactical_graph(state)
    if graph is None:
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
    max_range = action.range.get("normal_ft")
    if max_range is None:
        return True
    distance = graph.shortest_distance(actor.position_node_id, target.position_node_id)
    if distance is None or distance > int(max_range):
        return False
    return graph.has_line_of_sight(actor.position_node_id, target.position_node_id)


def _step_toward_enemy(
    state: GameState,
    *,
    actor_id: str,
    target_id: str,
    actions: dict[str, ActionDefinition],
) -> str | None:
    if "srd.move" not in actions or state.encounter is None:
        return None
    graph = _tactical_graph(state)
    if graph is None:
        return None
    actor = state.encounter.combatants.get(actor_id)
    target = state.encounter.combatants.get(target_id)
    if (
        actor is None
        or target is None
        or actor.position_node_id is None
        or target.position_node_id is None
    ):
        return None
    current_distance = graph.shortest_distance(actor.position_node_id, target.position_node_id)
    if current_distance is None:
        return None
    budget = int(
        state.encounter.action_budgets.get(actor_id, {}).get(
            "movement",
            _effective_combatant_speed(state, actor_id),
        )
    )
    reachable = graph.reachable(actor.position_node_id, budget)
    candidates: list[tuple[int, int, str]] = []
    for node_id in reachable:
        if node_id == actor.position_node_id:
            continue
        distance = graph.shortest_distance(node_id, target.position_node_id)
        movement_cost = graph.shortest_distance(
            actor.position_node_id,
            node_id,
            movement_cost=True,
        )
        if distance is None or movement_cost is None or distance >= current_distance:
            continue
        candidates.append((distance, movement_cost, node_id))
    return min(candidates)[2] if candidates else None


def _effective_combatant_speed(state: GameState, actor_id: str) -> int:
    assert state.encounter is not None
    combatant = state.encounter.combatants[actor_id]
    effects = list(combatant.status_effects)
    base_speed = combatant.speed_ft
    if combatant.entity_id in state.characters:
        backing_character = state.characters[combatant.entity_id]
        effects.extend(backing_character.status_effects)
        base_speed += class_feature_speed_bonus(backing_character)
    if combatant.entity_id in state.monsters:
        effects.extend(state.monsters[combatant.entity_id].status_effects)
    return effective_speed(base_speed, effects)


def _support_or_positioning_draft(
    state: GameState,
    *,
    actor_id: str,
    actions: dict[str, ActionDefinition],
) -> PlayerActionDraft | None:
    ally_id = _nearest_ally_id(state, actor_id)
    if ally_id is not None and "srd.help" in actions:
        return PlayerActionDraft(
            actor_id=actor_id,
            verb="srd.help",
            candidate_action_id="srd.help",
            target_ids=[ally_id],
            raw_text="[timeout takeover] help nearby ally",
        )
    for action_id, reason in (
        ("srd.cunning_action_hide", "hide from danger"),
        ("srd.hide", "hide from danger"),
        ("srd.cunning_action_dash", "reposition for the next turn"),
        ("srd.dash", "reposition for the next turn"),
        ("srd.cunning_action_disengage", "withdraw carefully"),
        ("srd.disengage", "withdraw carefully"),
    ):
        if action_id in actions:
            return PlayerActionDraft(
                actor_id=actor_id,
                verb=action_id,
                candidate_action_id=action_id,
                raw_text=f"[timeout takeover] {reason}",
            )
    return None


def _nearest_ally_id(state: GameState, actor_id: str) -> str | None:
    if state.encounter is None:
        return None
    actor = state.encounter.combatants.get(actor_id)
    if actor is None:
        return None
    allies = [
        combatant
        for combatant in state.encounter.combatants.values()
        if combatant.id != actor_id and combatant.side == actor.side and combatant.hp_current > 0
    ]
    if not allies:
        return None
    graph = _tactical_graph(state)
    if graph is None or actor.position_node_id is None:
        return sorted(allies, key=lambda combatant: (combatant.hp_current, combatant.id))[0].id
    reachable: list[tuple[int, int, str]] = []
    for ally in allies:
        distance = (
            graph.shortest_distance(actor.position_node_id, ally.position_node_id)
            if ally.position_node_id is not None
            else None
        )
        if distance is not None and distance <= 5:
            reachable.append((distance, ally.hp_current, ally.id))
    return min(reachable)[2] if reachable else None


def _tactical_graph(state: GameState) -> TacticalGraph | None:
    if state.encounter is None or state.encounter.tactical_graph is None:
        return None
    return TacticalGraph.from_dict(state.encounter.tactical_graph)

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dnd_llm.core.automation.definitions import ActionDefinition
from dnd_llm.core.dice import RollService
from dnd_llm.core.models import Combatant, GameState
from dnd_llm.core.positioning import TacticalGraph
from dnd_llm.core.resolver import PlayerActionDraft


@dataclass(frozen=True)
class TacticOption:
    action_id: str
    weight: int = 1
    target: str = "nearest_enemy"
    when: dict[str, Any] = field(default_factory=dict)


@dataclass
class MonsterTacticProfile:
    monster_name: str
    options: list[TacticOption]
    use_llm: bool = False


DEFAULT_MONSTER_TACTICS = MonsterTacticProfile(
    monster_name="default",
    options=[
        TacticOption(action_id="srd.dodge", weight=1, target="self"),
    ],
)

ALWAYS_AVAILABLE_TACTIC_ACTIONS = frozenset({"srd.dodge", "srd.dash", "srd.disengage"})
SRD_MONSTER_TACTICS = {
    profile.monster_name.casefold(): profile
    for profile in [
        MonsterTacticProfile(
            monster_name="Bandit",
            options=[
                TacticOption("srd.bandit_scimitar", weight=2, target="nearest_enemy"),
                TacticOption("srd.bandit_light_crossbow", weight=2, target="lowest_hp_enemy"),
                TacticOption("srd.dodge", weight=1, target="self", when={"hp_ratio_lte": 0.35}),
            ],
        ),
        MonsterTacticProfile(
            monster_name="Bandit Captain",
            options=[
                TacticOption(
                    "srd.bandit_captain_multiattack",
                    weight=4,
                    target="nearest_enemy",
                    when={"enemy_within_ft": 5},
                ),
                TacticOption(
                    "srd.bandit_captain_pistol",
                    weight=2,
                    target="lowest_hp_enemy",
                    when={"enemy_beyond_ft": 5},
                ),
                TacticOption("srd.dodge", weight=1, target="self", when={"hp_ratio_lte": 0.35}),
            ],
            use_llm=True,
        ),
        MonsterTacticProfile(
            monster_name="Cultist",
            options=[
                TacticOption("srd.cultist_ritual_sickle", weight=3, target="nearest_enemy"),
                TacticOption("srd.cultist_ritual_sickle", weight=1, target="lowest_hp_enemy"),
                TacticOption("srd.dodge", weight=1, target="self", when={"hp_ratio_lte": 0.35}),
            ],
        ),
        MonsterTacticProfile(
            monster_name="Giant Rat",
            options=[
                TacticOption("srd.giant_rat_bite", weight=3, target="nearest_enemy"),
                TacticOption("srd.giant_rat_bite", weight=1, target="lowest_hp_enemy"),
                TacticOption("srd.dodge", weight=1, target="self", when={"hp_ratio_lte": 0.35}),
            ],
        ),
        MonsterTacticProfile(
            monster_name="Kobold Warrior",
            options=[
                TacticOption("srd.kobold_dagger", weight=2, target="nearest_enemy"),
                TacticOption("srd.kobold_dagger", weight=2, target="lowest_hp_enemy"),
                TacticOption("srd.dodge", weight=1, target="self", when={"hp_ratio_lte": 0.35}),
            ],
        ),
        MonsterTacticProfile(
            monster_name="Warrior Infantry",
            options=[
                TacticOption("srd.warrior_infantry_spear", weight=3, target="nearest_enemy"),
                TacticOption("srd.warrior_infantry_spear", weight=1, target="lowest_hp_enemy"),
                TacticOption("srd.dodge", weight=1, target="self", when={"hp_ratio_lte": 0.35}),
            ],
        ),
        MonsterTacticProfile(
            monster_name="Skeleton",
            options=[
                TacticOption("srd.skeleton_shortsword", weight=2, target="nearest_enemy"),
                TacticOption("srd.skeleton_shortbow", weight=2, target="lowest_hp_enemy"),
                TacticOption("srd.dodge", weight=1, target="self", when={"hp_ratio_lte": 0.35}),
            ],
        ),
        MonsterTacticProfile(
            monster_name="Wolf",
            options=[
                TacticOption("srd.wolf_bite", weight=3, target="nearest_enemy"),
                TacticOption("srd.wolf_bite", weight=1, target="lowest_hp_enemy"),
                TacticOption("srd.dodge", weight=1, target="self", when={"hp_ratio_lte": 0.35}),
            ],
        ),
        MonsterTacticProfile(
            monster_name="Zombie",
            options=[
                TacticOption("srd.zombie_slam", weight=3, target="nearest_enemy"),
                TacticOption("srd.zombie_slam", weight=1, target="lowest_hp_enemy"),
                TacticOption("srd.dodge", weight=1, target="self", when={"hp_ratio_lte": 0.35}),
            ],
        ),
    ]
}


class MonsterTacticsLibrary:
    def __init__(self, profiles: dict[str, MonsterTacticProfile] | None = None):
        self.profiles = dict(SRD_MONSTER_TACTICS)
        if profiles:
            self.profiles.update({key.casefold(): value for key, value in profiles.items()})

    def profile_for(self, actor: Combatant) -> MonsterTacticProfile:
        return self.profiles.get(actor.name.casefold(), DEFAULT_MONSTER_TACTICS)

    def uses_llm(self, actor: Combatant) -> bool:
        return self.profile_for(actor).use_llm

    def draft_for_current_turn(
        self,
        *,
        state: GameState,
        actions: dict[str, ActionDefinition],
        roll_service: RollService,
    ) -> PlayerActionDraft:
        if state.encounter is None or state.encounter.current_combatant_id is None:
            raise ValueError("monster tactics require an active encounter turn")
        actor_id = state.encounter.current_combatant_id
        actor = state.encounter.combatants[actor_id]
        if actor.side == "party":
            raise ValueError("current combatant is not a monster")
        profile = self.profile_for(actor)
        owned_actions = set(actor.actions)
        profile_options = (
            [] if profile is DEFAULT_MONSTER_TACTICS and owned_actions else profile.options
        )
        legal = [
            option
            for option in profile_options
            if option.action_id in actions
            and _action_available_to_actor(option.action_id, owned_actions)
            and _condition_matches(state, actor, option.when)
            and _option_has_legal_target(
                state=state,
                actor=actor,
                action=actions[option.action_id],
                target_policy=option.target,
            )
        ]
        if not legal and owned_actions:
            legal = [
                TacticOption(action_id=action_id)
                for action_id in sorted(owned_actions)
                if action_id in actions
                and _option_has_legal_target(
                    state=state,
                    actor=actor,
                    action=actions[action_id],
                    target_policy="nearest_enemy",
                )
            ]
        if not legal:
            fallback_action_id = "srd.dodge" if "srd.dodge" in actions else next(iter(actions))
            legal = [TacticOption(action_id=fallback_action_id, target="self")]
        option = _weighted_choice(legal, roll_service)
        targets = _select_targets(
            state=state,
            actor=actor,
            action=actions[option.action_id],
            target_policy=option.target,
        )
        return PlayerActionDraft(
            actor_id=actor_id,
            verb=option.action_id,
            candidate_action_id=option.action_id,
            target_ids=targets,
            raw_text=f"[monster tactic] {actor.name} uses {option.action_id}",
        )


def _weighted_choice(options: list[TacticOption], roll_service: RollService) -> TacticOption:
    total_weight = sum(max(0, option.weight) for option in options)
    if total_weight <= 0:
        return options[0]
    roll = roll_service.roll(f"1d{total_weight}")
    cursor = 0
    for option in options:
        cursor += max(0, option.weight)
        if roll.total <= cursor:
            return option
    return options[-1]


def _action_available_to_actor(action_id: str, owned_actions: set[str]) -> bool:
    return (
        not owned_actions
        or action_id in owned_actions
        or action_id in ALWAYS_AVAILABLE_TACTIC_ACTIONS
    )


def _condition_matches(state: GameState, actor: Combatant, when: dict[str, Any]) -> bool:
    if not when:
        return True
    hp_ratio_lte = when.get("hp_ratio_lte")
    if hp_ratio_lte is not None:
        maximum = max(actor.hp_max, 1)
        if actor.hp_current / maximum > float(hp_ratio_lte):
            return False
    enemy_within_ft = when.get("enemy_within_ft")
    if enemy_within_ft is not None and not _enemy_within_ft(state, actor, int(enemy_within_ft)):
        return False
    enemy_beyond_ft = when.get("enemy_beyond_ft")
    return enemy_beyond_ft is None or not _enemy_within_ft(state, actor, int(enemy_beyond_ft))


def _enemy_within_ft(state: GameState, actor: Combatant, distance_ft: int) -> bool:
    if state.encounter is None:
        return False
    enemies = [
        combatant
        for combatant in state.encounter.combatants.values()
        if combatant.side != actor.side and combatant.hp_current > 0 and not combatant.dead
    ]
    if not enemies:
        return False
    graph_data = state.encounter.tactical_graph
    if graph_data is None or actor.position_node_id is None:
        return True
    graph = TacticalGraph.from_dict(graph_data)
    for enemy in enemies:
        if enemy.position_node_id is None:
            continue
        distance = graph.shortest_distance(actor.position_node_id, enemy.position_node_id)
        if distance is not None and distance <= distance_ft:
            return True
    return False


def _option_has_legal_target(
    *,
    state: GameState,
    actor: Combatant,
    action: ActionDefinition,
    target_policy: str,
) -> bool:
    targets = _select_targets(
        state=state,
        actor=actor,
        action=action,
        target_policy=target_policy,
    )
    min_targets = int(action.target_policy.get("min", 0))
    if len(targets) < min_targets:
        return False
    if not targets or state.encounter is None:
        return True
    if not bool(action.target_policy.get("harmful", False)):
        return True
    graph_data = state.encounter.tactical_graph
    if graph_data is None or actor.position_node_id is None:
        return True
    graph = TacticalGraph.from_dict(graph_data)
    max_range = action.range.get("normal_ft") or action.range.get("reach_ft")
    if max_range is None:
        return True
    for target_id in targets:
        target = state.encounter.combatants.get(target_id)
        if target is None or target.position_node_id is None:
            continue
        distance = graph.shortest_distance(actor.position_node_id, target.position_node_id)
        if (
            distance is not None
            and distance <= int(max_range)
            and graph.has_line_of_sight(actor.position_node_id, target.position_node_id)
        ):
            return True
    return False


def _select_targets(
    *,
    state: GameState,
    actor: Combatant,
    action: ActionDefinition,
    target_policy: str,
) -> list[str]:
    if state.encounter is None:
        return []
    min_targets = int(action.target_policy.get("min", 0))
    max_targets = action.target_policy.get("max")
    if min_targets == 0 and (max_targets is None or int(max_targets) == 0):
        return []
    if target_policy == "self":
        return [actor.id] if action.target_policy.get("self") else []
    enemies = [
        combatant
        for combatant in state.encounter.combatants.values()
        if combatant.side != actor.side and combatant.hp_current > 0
    ]
    if not enemies:
        return []
    if target_policy == "lowest_hp_enemy":
        return [min(enemies, key=lambda combatant: (combatant.hp_current, combatant.id)).id]
    if target_policy == "nearest_enemy":
        graph_data = state.encounter.tactical_graph
        if graph_data is not None and actor.position_node_id is not None:
            graph = TacticalGraph.from_dict(graph_data)
            with_distance = [
                (
                    graph.shortest_distance(actor.position_node_id, enemy.position_node_id)
                    if enemy.position_node_id is not None
                    else None,
                    enemy.id,
                )
                for enemy in enemies
            ]
            reachable = [
                (distance, enemy_id) for distance, enemy_id in with_distance if distance is not None
            ]
            if reachable:
                return [min(reachable, key=lambda item: (item[0], item[1]))[1]]
    return [sorted(enemy.id for enemy in enemies)[0]]

from __future__ import annotations

from typing import Any

from ..models import Combatant, GameState
from ..positioning import TacticalGraph

HOLY_AURA_ACTION_ID = "srd.holy_aura"


def holy_aura_benefit_sources(
    state: GameState,
    actor_id: str,
) -> list[dict[str, Any]]:
    target_aliases = _entity_aliases(state, actor_id)
    target_combatant = _combatant_for_actor(state, actor_id)
    sources: list[dict[str, Any]] = []
    for effect in state.world.active_effects:
        if effect.get("source_action_id") != HOLY_AURA_ACTION_ID:
            continue
        metadata = effect.get("metadata", {})
        if not isinstance(metadata, dict):
            continue
        chosen = metadata.get("chosen_creature_ids", [])
        if not isinstance(chosen, list) or not any(
            target_aliases & _entity_aliases(state, str(chosen_id)) for chosen_id in chosen
        ):
            continue
        source_actor_id = effect.get("applied_by")
        if not isinstance(source_actor_id, str) or not source_actor_id:
            continue
        source_aliases = _entity_aliases(state, source_actor_id)
        source_combatant = _combatant_for_actor(state, source_actor_id)
        distance_ft = _aura_distance(
            state,
            source_aliases=source_aliases,
            target_aliases=target_aliases,
            source_combatant=source_combatant,
            target_combatant=target_combatant,
        )
        radius_ft = int(effect.get("scope", {}).get("radius_ft", 30))
        if distance_ft is None or distance_ft > radius_ft:
            continue
        source: dict[str, Any] = {
            "effect_id": effect.get("effect_id"),
            "source_action_id": HOLY_AURA_ACTION_ID,
            "source_actor_id": source_actor_id,
            "target_id": actor_id,
            "distance_ft": distance_ft,
            "radius_ft": radius_ft,
        }
        spell_save_dc = metadata.get("spell_save_dc")
        if isinstance(spell_save_dc, int) and not isinstance(spell_save_dc, bool):
            source["spell_save_dc"] = spell_save_dc
        sources.append(source)
    return sources


def _aura_distance(
    state: GameState,
    *,
    source_aliases: set[str],
    target_aliases: set[str],
    source_combatant: Combatant | None,
    target_combatant: Combatant | None,
) -> int | None:
    if source_aliases & target_aliases:
        return 0
    if (
        state.encounter is None
        or state.encounter.tactical_graph is None
        or source_combatant is None
        or target_combatant is None
        or source_combatant.position_node_id is None
        or target_combatant.position_node_id is None
    ):
        return None
    graph = TacticalGraph.from_dict(state.encounter.tactical_graph)
    return graph.shortest_distance(
        source_combatant.position_node_id,
        target_combatant.position_node_id,
    )


def _combatant_for_actor(state: GameState, actor_id: str) -> Combatant | None:
    if state.encounter is None:
        return None
    direct = state.encounter.combatants.get(actor_id)
    if direct is not None:
        return direct
    return next(
        (
            combatant
            for combatant in state.encounter.combatants.values()
            if combatant.entity_id == actor_id
        ),
        None,
    )


def _entity_aliases(state: GameState, entity_id: str) -> set[str]:
    aliases = {entity_id}
    if state.encounter is not None:
        combatant = state.encounter.combatants.get(entity_id)
        if combatant is not None:
            aliases.add(combatant.entity_id)
        aliases.update(
            combatant.id
            for combatant in state.encounter.combatants.values()
            if combatant.entity_id == entity_id
        )
    if entity_id in state.characters:
        aliases.add(state.characters[entity_id].id)
    if entity_id in state.monsters:
        aliases.add(state.monsters[entity_id].id)
    return aliases

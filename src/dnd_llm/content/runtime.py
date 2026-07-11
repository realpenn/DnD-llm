from __future__ import annotations

from dnd_llm.core.automation.definitions import EventDefinition
from dnd_llm.core.compendium.loader import Compendium
from dnd_llm.core.compendium.validators import RuleDataValidator
from dnd_llm.core.models import Character, Combatant, GameState
from dnd_llm.core.positioning import TacticalGraph

from .campaign_pack import CampaignPackDefinition
from .dynamic import dynamic_zones_for_state


def apply_campaign_pack(state: GameState, pack: CampaignPackDefinition) -> None:
    state.campaign_id = pack.campaign_id
    state.campaign_pack_version = pack.version
    state.rules_data_version = pack.rules_version
    state.world.current_zone_id = pack.start_zone_id
    state.world.zone_edges = {
        zone_id: [str(edge) for edge in zone.get("edges", [])]
        for zone_id, zone in pack.zones.items()
    }
    state.world.flags["campaign_rewards"] = _campaign_rewards_for_state(pack)
    for character in state.characters.values():
        if character.zone_id is None:
            character.zone_id = pack.start_zone_id


def register_campaign_pack_events(
    compendium: Compendium,
    pack: CampaignPackDefinition,
    *,
    validator: RuleDataValidator | None = None,
) -> None:
    rule_validator = validator or RuleDataValidator()
    for event_id, event_data in pack.events.items():
        report = rule_validator.validate_event(event_data)
        report.require_ok()
        event = EventDefinition.from_dict(event_data)
        if event.id != event_id:
            raise ValueError(f"campaign event key {event_id} does not match id {event.id}")
        compendium.events[event.id] = event


def tactical_graph_for_zone(pack: CampaignPackDefinition, zone_id: str) -> TacticalGraph:
    zone = pack.zones.get(zone_id)
    if zone is None:
        raise KeyError(f"unknown zone: {zone_id}")
    graph_data = zone.get("tactical_graph")
    if graph_data is None:
        raise ValueError(f"zone {zone_id} has no tactical graph")
    return TacticalGraph.from_dict(graph_data)


def zone_definition_for_state(
    state: GameState,
    pack: CampaignPackDefinition,
    zone_id: str,
) -> dict[str, object]:
    zone = pack.zones.get(zone_id)
    if zone is not None:
        return zone
    dynamic_zone = dynamic_zones_for_state(state).get(zone_id)
    if dynamic_zone is not None:
        return dynamic_zone
    raise KeyError(f"unknown zone: {zone_id}")


def tactical_graph_for_state_zone(
    state: GameState,
    pack: CampaignPackDefinition,
    zone_id: str,
) -> TacticalGraph:
    zone = zone_definition_for_state(state, pack, zone_id)
    graph_data = zone.get("tactical_graph")
    if graph_data is None:
        raise ValueError(f"zone {zone_id} has no tactical graph")
    if not isinstance(graph_data, dict):
        raise TypeError("zone tactical_graph must be an object")
    return TacticalGraph.from_dict(graph_data)


def encounter_id_for_zone(pack: CampaignPackDefinition, zone_id: str) -> str | None:
    zone = pack.zones.get(zone_id)
    if zone is None:
        raise KeyError(f"unknown zone: {zone_id}")
    encounter_id = zone.get("encounter_id")
    return str(encounter_id) if encounter_id is not None else None


def encounter_id_for_state_zone(
    state: GameState,
    pack: CampaignPackDefinition,
    zone_id: str,
) -> str | None:
    zone = zone_definition_for_state(state, pack, zone_id)
    encounter_id = zone.get("encounter_id")
    return str(encounter_id) if encounter_id is not None else None


def build_encounter_combatants(
    *,
    pack: CampaignPackDefinition,
    encounter_id: str,
    party: dict[str, Character],
    compendium: Compendium | None = None,
    party_start_node: str = "front",
    monster_start_node: str = "cover",
) -> dict[str, Combatant]:
    encounter = pack.encounters.get(encounter_id)
    if encounter is None:
        raise KeyError(f"unknown encounter: {encounter_id}")
    combatants: dict[str, Combatant] = {}
    monster_id_counts: dict[str, int] = {}
    for character in party.values():
        combatants[character.id] = Combatant(
            id=character.id,
            entity_id=character.id,
            name=character.name,
            side="party",
            hp_current=character.hp_current,
            hp_max=character.hp_max,
            armor_class=character.armor_class,
            speed_ft=character.speed_ft,
            abilities=dict(character.abilities),
            temp_hp=character.temp_hp,
            position_node_id=party_start_node,
            status_effects=[dict(effect) for effect in character.status_effects],
            actions=list(character.actions),
        )
    for monster in encounter.get("monsters", []):
        monster_id = str(monster.get("monster_id", "monster"))
        definition = compendium.monsters.get(monster_id) if compendium is not None else None
        count = int(monster.get("count", 1))
        for _index in range(count):
            base_id = monster_id.replace(".", "_")
            monster_id_counts[base_id] = monster_id_counts.get(base_id, 0) + 1
            combatant_id = f"{base_id}_{monster_id_counts[base_id]}"
            abilities = (
                monster.get("abilities")
                if "abilities" in monster
                else definition.abilities
                if definition is not None
                else {}
            )
            actions = (
                monster.get("actions")
                if "actions" in monster
                else definition.actions
                if definition is not None
                else []
            )
            combatants[combatant_id] = Combatant(
                id=combatant_id,
                entity_id=combatant_id,
                name=str(
                    monster.get("name", definition.name if definition is not None else "Monster")
                ),
                side="monsters",
                hp_current=int(
                    monster.get("hp", definition.hit_points if definition is not None else 7)
                ),
                hp_max=int(
                    monster.get("hp", definition.hit_points if definition is not None else 7)
                ),
                armor_class=int(
                    monster.get(
                        "armor_class", definition.armor_class if definition is not None else 12
                    )
                ),
                speed_ft=int(
                    monster.get("speed_ft", definition.speed_ft if definition is not None else 30)
                ),
                creature_type=str(
                    monster.get(
                        "creature_type",
                        definition.creature_type if definition is not None else "humanoid",
                    )
                ),
                abilities={str(key): int(value) for key, value in dict(abilities).items()},
                position_node_id=monster_start_node,
                actions=[str(action_id) for action_id in actions],
                resistances=list(
                    monster.get(
                        "resistances",
                        definition.resistances if definition is not None else [],
                    )
                ),
                immunities=list(
                    monster.get(
                        "immunities",
                        definition.immunities if definition is not None else [],
                    )
                ),
                vulnerabilities=list(
                    monster.get(
                        "vulnerabilities",
                        definition.vulnerabilities if definition is not None else [],
                    )
                ),
                condition_immunities=list(
                    monster.get(
                        "condition_immunities",
                        definition.condition_immunities if definition is not None else [],
                    )
                ),
                traits=list(
                    monster.get(
                        "traits",
                        definition.traits if definition is not None else [],
                    )
                ),
            )
    return combatants


def _campaign_rewards_for_state(pack: CampaignPackDefinition) -> dict[str, dict[str, object]]:
    rewards: dict[str, dict[str, object]] = {}
    for reward_id, reward in pack.rewards.items():
        items: list[dict[str, object]] = []
        for item in reward.get("items", []):
            if isinstance(item, str):
                items.append({"item_id": item, "quantity": 1})
            elif isinstance(item, dict):
                items.append(
                    {
                        "item_id": str(item.get("item_id", "")),
                        "quantity": int(item.get("quantity", 1)),
                    }
                )
        rewards[str(reward_id)] = {
            "gold": int(reward.get("gold", 0)),
            "experience": int(reward.get("experience", 0)),
            "items": items,
        }
    return rewards

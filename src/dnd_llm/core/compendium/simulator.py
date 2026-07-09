from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dnd_llm.core.automation.definitions import ActionDefinition
from dnd_llm.core.compendium.loader import Compendium
from dnd_llm.core.models import Character, Combatant, Encounter, GameState
from dnd_llm.core.persistence import AuditLog
from dnd_llm.core.positioning import PositionEdge, PositionNode, TacticalGraph
from dnd_llm.core.tools import EngineTools


@dataclass
class SimulationReport:
    action_id: str
    ok: bool
    result: dict[str, Any] | None = None
    error: str | None = None
    serialized_state: dict[str, Any] | None = None
    audit_events: list[dict[str, Any]] = field(default_factory=list)


class CompendiumSimulator:
    def __init__(self, compendium: Compendium):
        self.compendium = compendium

    def simulate_all_actions(self) -> list[SimulationReport]:
        return [self.simulate_action(action_id) for action_id in sorted(self.compendium.actions)]

    def simulate_all_hazards(self) -> list[SimulationReport]:
        return [self.simulate_hazard(hazard_id) for hazard_id in sorted(self.compendium.hazards)]

    def simulate_action(self, action_id: str) -> SimulationReport:
        action = self.compendium.action(action_id)
        state = _simulation_state(action)
        audit_log = AuditLog()
        tools = EngineTools(state, self.compendium, audit_log)
        try:
            targets = _targets_for_action(action.target_policy)
            if action.action_type == "spell":
                params = _spell_params_for_action(action)
                if params:
                    result = tools._execute_action(
                        action_id=action_id,
                        actor_id="pc_actor",
                        targets=targets,
                        params=params,
                        idempotency_key=f"simulate:{action_id}",
                    )
                else:
                    result = tools.cast_spell(
                        "pc_actor",
                        action_id,
                        targets,
                        action.cost.spell_slot_level or 1,
                        idempotency_key=f"simulate:{action_id}",
                    )
            elif action.action_economy == "movement":
                result = tools.move(
                    "pc_actor",
                    to_position_node_id="node_cover",
                    idempotency_key=f"simulate:{action_id}",
                )
            else:
                params = {"area_targets": targets, "simulation": True}
                allowed_damage_types = action.properties.get("allowed_damage_types")
                if isinstance(allowed_damage_types, list) and allowed_damage_types:
                    damage_type_param = str(
                        action.properties.get("damage_type_param", "damage_type")
                    )
                    params[damage_type_param] = str(allowed_damage_types[0])
                allowed_creature_types = action.properties.get("allowed_creature_types")
                if isinstance(allowed_creature_types, list) and allowed_creature_types:
                    creature_types_param = str(
                        action.properties.get("creature_types_param", "creature_types")
                    )
                    params[creature_types_param] = [str(allowed_creature_types[0])]
                _add_allowed_list_params(params, action)
                _add_fire_shield_params(params, action)
                if action.properties.get("requires_willing_target") is True:
                    params["target_willing"] = True
                if action.properties.get("pact_of_the_blade_weapon") is True:
                    params["pact_weapon_action_id"] = "srd.longsword_attack"
                if action.id == "srd.cutting_words":
                    params["cutting_words_roll_type"] = "attack_roll"
                    params["cutting_words_roll_total"] = 14
                    params["cutting_words_target_ac"] = 12
                if action.id == "srd.lands_aid":
                    params["lands_aid_area_target_ids"] = ["npc_enemy", "pc_ally"]
                    params["lands_aid_healing_target_id"] = "pc_ally"
                if action.id == "srd.sacred_weapon":
                    params["sacred_weapon_action_id"] = "srd.shortsword_attack"
                if action.id == "srd.restoring_touch":
                    params["lay_on_hands_points"] = 5
                    params["restoring_touch_conditions"] = ["blinded"]
                if action.properties.get("natures_sanctuary") is True:
                    params["natures_sanctuary_position_node_id"] = "node_cover"
                if action.properties.get("natures_sanctuary_move") is True:
                    params["natures_sanctuary_position_node_id"] = "node_back"
                if action.properties.get("oil_of_sharpness") is True:
                    params["oil_of_sharpness_action_id"] = "srd.shortsword_attack"
                if action.properties.get("robe_of_useful_items_detach_patch") is True:
                    params["robe_of_useful_items_patch"] = "dagger"
                if action.properties.get("rod_of_absorption_absorb_spell") is True:
                    params["absorbed_spell_level"] = 1
                    params["targeting_only_you"] = True
                    params["creates_area_of_effect"] = False
                if action.id == "srd.quivering_palm_release":
                    params["same_plane"] = True
                for param_name in action.cost.resource_params.values():
                    params.setdefault(param_name, 1)
                for node in action.automation:
                    if node.get("type") == "preserve_life_healing":
                        param_name = str(node.get("points_param", "preserve_life_points"))
                        params[param_name] = {target_id: 1 for target_id in targets}
                result = tools._execute_action(
                    action_id=action_id,
                    actor_id="pc_actor",
                    targets=targets,
                    params=params,
                    idempotency_key=f"simulate:{action_id}",
                )
            return SimulationReport(
                action_id=action_id,
                ok=True,
                result=result,
                serialized_state=state.to_dict(),
                audit_events=audit_log.to_dicts(),
            )
        except Exception as exc:  # pragma: no cover - report carries the failure.
            return SimulationReport(action_id=action_id, ok=False, error=str(exc))

    def simulate_hazard(self, hazard_id: str) -> SimulationReport:
        state = _simulation_state(hazard_id)
        audit_log = AuditLog()
        tools = EngineTools(state, self.compendium, audit_log)
        try:
            result = tools.apply_hazard(["pc_actor"], hazard_id, {"source": "rules_discrete"})
            return SimulationReport(
                action_id=hazard_id,
                ok=True,
                result=result,
                serialized_state=state.to_dict(),
                audit_events=audit_log.to_dicts(),
            )
        except Exception as exc:  # pragma: no cover - report carries the failure.
            return SimulationReport(action_id=hazard_id, ok=False, error=str(exc))


def _simulation_state(action: ActionDefinition | str) -> GameState:
    action_id = action.id if isinstance(action, ActionDefinition) else action
    inventory = {"srd.potion_of_healing": 1}
    resources = {"srd.resource.second_wind": 2}
    spell_slots = {"1": 4, "2": 3, "3": 2}
    gold = 0
    enemy_creature_type = "humanoid"
    enemy_status_effects: list[dict[str, Any]] = []
    enemy_resistances: list[str] = []
    ally_status_effects: list[dict[str, Any]] = []
    if isinstance(action, ActionDefinition):
        required_item = action.requirements.get("item")
        if isinstance(required_item, str) and required_item:
            inventory[required_item] = max(1, inventory.get(required_item, 0))
        for item_id, amount in action.cost.items.items():
            inventory[item_id] = max(1, amount)
        for resource, amount in action.cost.resources.items():
            resources[resource] = max(1, amount)
        for resource in action.cost.resource_params:
            resources[resource] = max(1, resources.get(resource, 0))
        if action.id == "srd.restoring_touch":
            resources["srd.resource.lay_on_hands"] = max(
                5,
                resources.get("srd.resource.lay_on_hands", 0),
            )
            ally_status_effects = [{"effect_id": "simulation-blinded", "condition": "blinded"}]
        gold = max(gold, int(action.cost.gold))
        if action.cost.spell_slot_level is not None:
            spell_slots[str(action.cost.spell_slot_level)] = max(
                1,
                spell_slots.get(str(action.cost.spell_slot_level), 0),
            )
        if action.properties.get("robe_of_useful_items_detach_patch") is True:
            resources["srd.robe_of_useful_items.initialized"] = 1
            resources["srd.robe_of_useful_items.patch.dagger"] = 1
        if action.properties.get("rod_of_absorption_absorb_spell") is True:
            resources["srd.rod_of_absorption.initialized"] = 1
            resources["srd.rod_of_absorption.lifetime_absorbed_levels"] = 1
            resources["srd.rod_of_absorption.stored_levels"] = 1
        creature_types = action.target_policy.get("creature_types")
        if isinstance(creature_types, list) and creature_types:
            enemy_creature_type = str(creature_types[0])
    class_levels = {"fighter": 1}
    subclasses: dict[str, str] = {}
    if isinstance(action, ActionDefinition):
        class_name = action.requirements.get("class")
        class_level_min = int(action.requirements.get("class_level_min", 1))
        if class_name is not None:
            class_levels = {str(class_name): max(1, class_level_min)}
            subclass_id = action.requirements.get("subclass")
            if subclass_id is not None:
                subclasses[str(class_name)] = str(subclass_id)
        elif action.requirements.get("class_any") is not None:
            class_any = action.requirements["class_any"]
            class_any_level_min = int(action.requirements.get("class_any_level_min", 1))
            if isinstance(class_any, str):
                class_levels = {class_any: max(1, class_any_level_min)}
            elif isinstance(class_any, list) and class_any:
                class_levels = {str(class_any[0]): max(1, class_any_level_min)}
        elif action.properties.get("spell_classes") is not None:
            spell_classes = action.properties["spell_classes"]
            spell_level = int(action.properties.get("spell_level", 1))
            if isinstance(spell_classes, str):
                class_levels = {spell_classes: max(1, spell_level)}
            elif isinstance(spell_classes, list) and spell_classes:
                class_levels = {str(spell_classes[0]): max(1, spell_level)}
        elif "class_level_min" in action.requirements:
            class_levels = {"fighter": max(1, class_level_min)}
        if action.id == "srd.hunters_lore":
            enemy_resistances = ["cold"]
            enemy_status_effects = [
                {
                    "effect_id": "simulation-hunters-mark",
                    "source_ref": "SRD 5.2.1 Hunter's Mark spell",
                    "source_action_id": "srd.favored_enemy_hunters_mark",
                    "target_id": "npc_enemy",
                    "applied_by": "pc_actor",
                    "condition": None,
                    "passive_modifiers": {
                        "hunters_mark": True,
                        "attacker_bonus_damage": "1d6",
                        "damage_type": "force",
                        "tracking_advantage": True,
                    },
                    "duration": {"until": "concentration_1_hour"},
                    "tick_on": "target_hit_or_tracking",
                    "concentration": True,
                    "stacking_policy": "replace",
                    "audit": {},
                }
            ]
        if action.id == "srd.quivering_palm_release":
            enemy_status_effects = [
                {
                    "effect_id": "simulation-quivering-palm",
                    "source_ref": "SRD 5.2.1 Monk Subclass: Warrior of the Open Hand, Level 17: Quivering Palm",
                    "source_action_id": "srd.quivering_palm",
                    "target_id": "npc_enemy",
                    "applied_by": "pc_actor",
                    "condition": "quivering_palm",
                    "passive_modifiers": {},
                    "duration": {"until": "duration_monk_level_days", "days": 17},
                    "tick_on": None,
                    "concentration": False,
                    "stacking_policy": "replace",
                    "audit": {"simulation": True},
                }
            ]
    actor = Character(
        id="pc_actor",
        name="Simulator",
        abilities={"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 10},
        class_levels=class_levels,
        subclasses=subclasses,
        proficiency_bonus=2,
        hp_current=12,
        hp_max=12,
        armor_class=16,
        hit_dice={"d10": 1},
        inventory=inventory,
        resources=resources,
        spell_slots=spell_slots,
        gold=gold,
        tool_proficiencies=["thieves_tools"] if class_levels.get("rogue", 0) else [],
        feature_choices={"ranger.hunter.hunters_prey": "colossus_slayer"}
        if subclasses.get("ranger") == "hunter"
        else {},
        actions=[action_id],
        zone_id="zone_start",
    )
    ally = Character(
        id="pc_ally",
        name="Ally",
        abilities={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
        class_levels={"cleric": 1},
        proficiency_bonus=2,
        hp_current=3,
        hp_max=9,
        armor_class=14,
        hit_dice={"d8": 1},
        status_effects=[dict(effect) for effect in ally_status_effects],
        actions=[],
        zone_id="zone_start",
    )
    graph = TacticalGraph(
        nodes={
            "node_front": PositionNode("node_front", "Front"),
            "node_cover": PositionNode("node_cover", "Cover", default_cover="half"),
            "node_back": PositionNode("node_back", "Back"),
        },
        edges=[
            PositionEdge("node_front", "node_cover", 5, cover="half"),
            PositionEdge("node_cover", "node_back", 25, cover="half"),
        ],
    )
    encounter = Encounter(
        id="simulation",
        initiative_order=["pc_actor", "npc_enemy", "pc_ally"],
        tactical_graph=graph.to_dict(),
        combatants={
            "pc_actor": Combatant(
                id="pc_actor",
                entity_id="pc_actor",
                name="Simulator",
                side="party",
                hp_current=12,
                hp_max=12,
                armor_class=16,
                speed_ft=30,
                position_node_id="node_front",
            ),
            "pc_ally": Combatant(
                id="pc_ally",
                entity_id="pc_ally",
                name="Ally",
                side="party",
                hp_current=3,
                hp_max=9,
                armor_class=14,
                speed_ft=30,
                status_effects=[dict(effect) for effect in ally_status_effects],
                position_node_id="node_front",
            ),
            "npc_enemy": Combatant(
                id="npc_enemy",
                entity_id="npc_enemy",
                name="Training Target",
                side="monsters",
                hp_current=11,
                hp_max=11,
                armor_class=12,
                speed_ft=30,
                creature_type=enemy_creature_type,
                status_effects=enemy_status_effects,
                resistances=enemy_resistances,
                position_node_id="node_cover",
            ),
        },
    )
    state = GameState(
        campaign_id="simulation",
        rng_seed=424242,
        characters={"pc_actor": actor, "pc_ally": ally},
        encounter=encounter,
    )
    if action_id == "srd.natures_sanctuary_move":
        state.world.active_effects.append(
            {
                "effect_id": "simulation-natures-sanctuary",
                "source_ref": "SRD 5.2.1 Druid Subclass: Circle of the Land, Level 14: Nature's Sanctuary",
                "source_action_id": "srd.natures_sanctuary",
                "applied_by": "pc_actor",
                "effect_type": "natures_sanctuary",
                "concentration": False,
                "scope": {
                    "shape": "cube",
                    "size_ft": 15,
                    "position_node_id": "node_cover",
                    "range_ft": 120,
                    "on_ground": True,
                },
                "duration": {"until": "duration_1_minute"},
                "metadata": {"position_node_id": "node_cover"},
                "audit": {"simulation": True},
            }
        )
    if isinstance(action, ActionDefinition):
        source_action_id = action.properties.get("requires_active_effect_source_action_id")
        if isinstance(source_action_id, str) and source_action_id:
            state.world.active_effects.append(
                {
                    "effect_id": f"simulation-active-effect-{source_action_id}",
                    "source_ref": "simulation",
                    "source_action_id": source_action_id,
                    "applied_by": "pc_actor",
                    "effect_type": "simulation_active_effect",
                    "concentration": False,
                    "scope": {"target": "self"},
                    "duration": {"until": "simulation"},
                    "metadata": {"simulation": True},
                    "audit": {"simulation": True},
                }
            )
        actor_source_action_id = action.properties.get("requires_actor_effect_source_action_id")
        if isinstance(actor_source_action_id, str) and actor_source_action_id:
            actor.status_effects.append(
                {
                    "effect_id": f"simulation-actor-effect-{actor_source_action_id}",
                    "source_ref": "simulation",
                    "source_action_id": actor_source_action_id,
                    "target_id": "pc_actor",
                    "applied_by": "npc_enemy",
                    "condition": None,
                    "passive_modifiers": {
                        "out_of_play": True,
                        "simulation": True,
                    },
                    "duration": {"until": "simulation"},
                    "tick_on": "self_turn_end",
                    "concentration": True,
                    "audit": {"simulation": True},
                }
            )
    return state


def _targets_for_action(target_policy: dict[str, Any]) -> list[str]:
    if int(target_policy.get("min", 0)) == 0:
        return []
    if target_policy.get("self"):
        return ["pc_actor"]
    if target_policy.get("harmful", False):
        return ["npc_enemy"]
    return ["pc_ally"]


def _spell_params_for_action(action: ActionDefinition) -> dict[str, Any]:
    params: dict[str, Any] = {}
    allowed_damage_types = action.properties.get("allowed_damage_types")
    if isinstance(allowed_damage_types, list) and allowed_damage_types:
        damage_type_param = str(action.properties.get("damage_type_param", "damage_type"))
        params[damage_type_param] = str(allowed_damage_types[0])
    allowed_creature_types = action.properties.get("allowed_creature_types")
    if isinstance(allowed_creature_types, list) and allowed_creature_types:
        creature_types_param = str(action.properties.get("creature_types_param", "creature_types"))
        params[creature_types_param] = [str(allowed_creature_types[0])]
    _add_allowed_list_params(params, action)
    if action.id == "srd.hallow":
        params["hallow_extra_effect_creature_types"] = ["aberration"]
    _add_fire_shield_params(params, action)
    if action.properties.get("requires_willing_target") is True:
        params["target_willing"] = True
    if action.properties.get("requires_dim_light_or_darkness") is True:
        params["in_dim_light_or_darkness"] = True
    if action.properties.get("greater_restoration") is True:
        choices = action.properties.get("greater_restoration_choices", [])
        if isinstance(choices, list) and choices:
            params["greater_restoration_choice"] = str(choices[0])
    for node in action.automation:
        if node.get("type") == "healing_pool":
            param_name = str(node.get("points_param", "healing_points"))
            targets = _targets_for_action(action.target_policy)
            params[param_name] = {target_id: 1 for target_id in targets}
    return params


def _add_allowed_list_params(params: dict[str, Any], action: ActionDefinition) -> None:
    specs = action.properties.get("allowed_list_params")
    if not isinstance(specs, dict):
        return
    required_counts = action.properties.get("required_list_param_counts")
    if not isinstance(required_counts, dict):
        required_counts = {}
    for param_name, allowed_raw in specs.items():
        if isinstance(allowed_raw, list) and allowed_raw:
            param = str(param_name)
            count = int(required_counts.get(param, 1))
            count = max(1, count)
            params[param] = [str(item) for item in allowed_raw[:count]]


def _add_fire_shield_params(params: dict[str, Any], action: ActionDefinition) -> None:
    allowed_types = action.properties.get("allowed_fire_shield_types")
    if not isinstance(allowed_types, list) or not allowed_types:
        return
    param_name = str(action.properties.get("fire_shield_type_param", "fire_shield_type"))
    params[param_name] = str(allowed_types[0])

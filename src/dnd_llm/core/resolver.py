from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .automation.definitions import ActionDefinition, ItemDefinition
from .economy import ActionBudget, EconomyTracker
from .models import Character, Combatant, GameState, Monster
from .positioning import TacticalGraph
from .rules.class_features import (
    WARLOCK_PACT_OF_BLADE_WEAPON_ACTION_IDS,
    bloodied_hp_cap,
    class_feature_speed_bonus,
    has_barbarian_feature,
    has_monk_open_hand_feature,
    has_rogue_thief_feature,
    has_warlock_eldritch_smite,
    has_warlock_investment_of_chain_master,
    has_warlock_repelling_blast,
    has_warlock_thirsting_blade,
    is_bloodied,
    is_wearing_armor,
    preserve_life_healing_pool,
    warlock_eldritch_spear_range_bonus,
)
from .rules.conditions import effective_speed
from .rules.rests import resource_maxima
from .rules.rituals import ritual_casting_eligibility
from .rules.spell_slots import warlock_pact_slot_maxima_for_class_levels

RESOLVER_CUNNING_STRIKE_EFFECTS = {"poison", "stealth_attack", "trip", "withdraw"}
RESOLVER_MAX_CUNNING_STRIKE_EFFECTS = 2
RESOLVER_BRUTAL_STRIKE_EFFECTS = {
    "forceful_blow",
    "hamstring_blow",
    "staggering_blow",
    "sundering_blow",
}
RESOLVER_IMPROVED_BRUTAL_STRIKE_EFFECTS = {"staggering_blow", "sundering_blow"}
RESOLVER_POISONERS_KIT_ITEM_ID = "srd.poisoners_kit"
RESOLVER_ATTACK_ACTION_TYPES = {"weapon_attack", "monster_attack", "unarmed_attack"}
RESOLVER_HIDE_ACTION_IDS = frozenset({"srd.hide", "srd.cunning_action_hide"})
RESOLVER_SUPREME_SNEAK_COVER_ALIASES = {
    "3_4": "three_quarters",
    "3_4_cover": "three_quarters",
    "three_quarters": "three_quarters",
    "three_quarters_cover": "three_quarters",
    "total": "total",
    "total_cover": "total",
}
RESOLVER_CREATURE_SIZE_RANKS = {
    "tiny": 1,
    "small": 2,
    "medium": 3,
    "medium_or_small": 3,
    "large": 4,
    "huge": 5,
    "gargantuan": 6,
}
RESOLVER_GREATER_RESTORATION_CHOICES = {
    "exhaustion",
    "charmed_or_petrified",
    "curse",
    "ability_score_reduction",
    "hp_max_reduction",
}
RESOLVER_RESTORING_TOUCH_ALLOWED_CONDITIONS = frozenset(
    {"blinded", "charmed", "deafened", "frightened", "paralyzed", "stunned"}
)
RESOLVER_RESTORING_TOUCH_CONDITION_POINT_COST = 5
RESOLVER_PACT_OF_BLADE_WEAPON_ACTION_ID = "srd.pact_of_the_blade_weapon"
RESOLVER_PACT_OF_CHAIN_FIND_FAMILIAR_ACTION_ID = "srd.pact_of_the_chain_find_familiar"
RESOLVER_THIRSTING_BLADE_ACTION_ID = "srd.thirsting_blade"
RESOLVER_ELDRITCH_SMITE_ACTION_ID = "srd.eldritch_smite"
RESOLVER_STEP_OF_THE_WIND_ACTION_IDS = frozenset(
    {"srd.step_of_the_wind", "srd.step_of_the_wind_focus"}
)
RESOLVER_FLEET_STEP_ACTION_ID = "srd.fleet_step"
RESOLVER_FLEET_STEP_CONDITION = "fleet_step_available"
RESOLVER_QUIVERING_PALM_RELEASE_ACTION_ID = "srd.quivering_palm_release"
RESOLVER_OIL_OF_ETHEREALNESS_ACTION_ID = "srd.apply_oil_of_etherealness"
RESOLVER_APPLY_OIL_OF_SLIPPERINESS_ACTION_ID = "srd.apply_oil_of_slipperiness"
RESOLVER_ROD_OF_ABSORPTION_ITEM_ID = "srd.rod_of_absorption"
RESOLVER_ROD_OF_ABSORPTION_STORED_LEVELS_RESOURCE = "srd.rod_of_absorption.stored_levels"
RESOLVER_ROD_OF_ABSORPTION_LIFETIME_ABSORBED_RESOURCE = (
    "srd.rod_of_absorption.lifetime_absorbed_levels"
)
RESOLVER_ROD_OF_ABSORPTION_INITIALIZED_RESOURCE = "srd.rod_of_absorption.initialized"
RESOLVER_ROD_OF_ABSORPTION_LIFETIME_CAP = 50
RESOLVER_ROD_OF_ABSORPTION_MAX_CREATED_SLOT_LEVEL = 5
RESOLVER_ROD_OF_ALERTNESS_PROTECTIVE_AURA_USED_RESOURCE = (
    "srd.rod_of_alertness.protective_aura_used_until_next_dawn"
)
RESOLVER_ROBE_OF_USEFUL_ITEMS_PATCH_PREFIX = "srd.robe_of_useful_items.patch."
RESOLVER_ROBE_OF_USEFUL_ITEMS_INITIALIZED_RESOURCE = "srd.robe_of_useful_items.initialized"
RESOLVER_THIRSTING_BLADE_PACT_WEAPON_ATTACK_CONDITION = (
    "thirsting_blade_pact_weapon_attack_this_turn"
)
RESOLVER_THIRSTING_BLADE_EXTRA_ATTACK_USED_CONDITION = "thirsting_blade_extra_attack_used"
RESOLVER_ELDRITCH_SMITE_USED_CONDITION = "eldritch_smite_used"
RESOLVER_COUNTERCHARM_CONDITIONS = frozenset({"charmed", "frightened"})
RESOLVER_COUNTERCHARM_RANGE_FT = 30


@dataclass
class PlayerActionDraft:
    actor_id: str
    verb: str
    target_ids: list[str] = field(default_factory=list)
    candidate_action_id: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""


@dataclass
class ResolverResult:
    status: str
    reason: str
    action_id: str | None = None
    confirm_required: bool = False
    candidates: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "action_id": self.action_id,
            "confirm_required": self.confirm_required,
            "candidates": self.candidates,
        }


class ActionResolver:
    def __init__(
        self,
        state: GameState,
        actions: dict[str, ActionDefinition],
        items: dict[str, ItemDefinition] | EconomyTracker | None = None,
        economy: EconomyTracker | None = None,
    ):
        if isinstance(items, EconomyTracker) and economy is None:
            economy = items
            items = None
        self.state = state
        self.actions = actions
        self.items: dict[str, ItemDefinition] = items if isinstance(items, dict) else {}
        self.economy = economy or EconomyTracker()

    def resolve(self, draft: PlayerActionDraft) -> ResolverResult:
        action = self._resolve_action(draft)
        if action is None:
            return ResolverResult(status="ambiguous", reason="no matching action", candidates=[])
        actor = self.state.entity_for_actor(draft.actor_id)
        item = self._item_for_draft(draft)
        ownership_error = self._ownership_error(draft.actor_id, actor, action, item)
        if ownership_error is not None:
            return ResolverResult(
                status="rejected",
                reason=ownership_error,
                action_id=action.id,
            )
        requirements_error = self._requirements_error(draft.actor_id, actor, action)
        if requirements_error is not None:
            return ResolverResult(
                status="rejected",
                reason=requirements_error,
                action_id=action.id,
            )
        allowed_action_error = self._allowed_action_error(actor, action)
        if allowed_action_error is not None:
            return ResolverResult(
                status="rejected",
                reason=allowed_action_error,
                action_id=action.id,
            )
        spellcasting_error = self._spellcasting_error(actor, action)
        if spellcasting_error is not None:
            return ResolverResult(
                status="rejected",
                reason=spellcasting_error,
                action_id=action.id,
            )
        attack_error = self._attack_error(actor, action)
        if attack_error is not None:
            return ResolverResult(
                status="rejected",
                reason=attack_error,
                action_id=action.id,
            )
        ritual_error = self._ritual_casting_error(draft, actor, action)
        if ritual_error is not None:
            return ResolverResult(
                status="rejected",
                reason=ritual_error,
                action_id=action.id,
            )
        fast_hands_error = self._fast_hands_item_error(draft, actor, action, item)
        if fast_hands_error is not None:
            return ResolverResult(
                status="rejected",
                reason=fast_hands_error,
                action_id=action.id,
            )
        investment_error = self._investment_of_chain_master_familiar_error(
            draft,
            actor,
            action,
        )
        if investment_error is not None:
            return ResolverResult(
                status="rejected",
                reason=investment_error,
                action_id=action.id,
            )
        damage_type_error = self._allowed_damage_type_param_error(draft, action)
        if damage_type_error is not None:
            return ResolverResult(
                status="rejected",
                reason=damage_type_error,
                action_id=action.id,
            )
        greater_restoration_error = self._greater_restoration_choice_error(draft, action)
        if greater_restoration_error is not None:
            return ResolverResult(
                status="rejected",
                reason=greater_restoration_error,
                action_id=action.id,
            )
        restoring_touch_error = self._restoring_touch_error(draft, action)
        if restoring_touch_error is not None:
            return ResolverResult(
                status="rejected",
                reason=restoring_touch_error,
                action_id=action.id,
            )
        oil_vial_check = self._prepare_size_based_oil_vial_cost(draft, action)
        if oil_vial_check is not None:
            return oil_vial_check
        action_economy = (
            "bonus_action" if self._uses_fast_hands_item(draft) else action.action_economy
        )
        fleet_step_error = self._fleet_step_error(draft, actor, action)
        if fleet_step_error is not None:
            return ResolverResult(
                status="rejected",
                reason=fleet_step_error,
                action_id=action.id,
            )
        thirsting_blade_check = self._check_thirsting_blade_extra_attack(draft, actor, action)
        if thirsting_blade_check is not None:
            return thirsting_blade_check
        eldritch_smite_check = self._check_eldritch_smite(draft, actor, action)
        if eldritch_smite_check is not None:
            return eldritch_smite_check
        rod_alertness_check = self._check_rod_of_alertness(draft, actor, action)
        if rod_alertness_check is not None:
            return rod_alertness_check
        instinctive_pounce_error = self._instinctive_pounce_error(draft, actor, action)
        if instinctive_pounce_error is not None:
            return ResolverResult(
                status="rejected",
                reason=instinctive_pounce_error,
                action_id=action.id,
            )
        if self._uses_thirsting_blade_extra_attack(draft):
            action_economy = "none"
        if self._uses_fleet_step(draft, actor, action):
            action_economy = "none"
        if self._quivering_palm_harmless_release(draft, action):
            action_economy = "none"
        budget = self._action_budget_for_check(draft.actor_id, actor)
        if not budget.can_spend(action_economy):
            return ResolverResult(
                status="rejected", reason="insufficient action economy", action_id=action.id
            )
        if action.cost.spell_slot_level is not None and not bool(draft.params.get("as_ritual")):
            resource_owner = self._resource_owner(draft.actor_id, actor)
            if self._uses_rod_of_absorption_spell_slot(draft):
                rod_error = self._rod_of_absorption_spell_slot_error(
                    draft,
                    action,
                    resource_owner,
                )
                if rod_error is not None:
                    return ResolverResult(
                        status="rejected",
                        reason=rod_error,
                        action_id=action.id,
                    )
            else:
                slots = getattr(resource_owner, "spell_slots", {})
                try:
                    slot_level = self._spell_slot_level_to_spend(draft, action)
                except ValueError as exc:
                    return ResolverResult(
                        status="rejected",
                        reason=str(exc),
                        action_id=action.id,
                    )
                if slots.get(str(slot_level), 0) <= 0:
                    return ResolverResult(
                        status="rejected", reason="insufficient spell slot", action_id=action.id
                    )
        rod_absorption_check = self._check_rod_of_absorption(draft, actor, action)
        if rod_absorption_check is not None:
            return rod_absorption_check
        resource_check = self._check_cost_resources(draft, actor, action)
        if resource_check is not None:
            return resource_check
        resource_delta_check = self._check_resource_delta_caps(draft, actor, action)
        if resource_delta_check is not None:
            return resource_delta_check
        pact_weapon_check = self._check_pact_of_blade_weapon_selection(draft, action)
        if pact_weapon_check is not None:
            return pact_weapon_check
        robe_patch_check = self._check_robe_of_useful_items_patch(draft, actor, action)
        if robe_patch_check is not None:
            return robe_patch_check
        target_check = self._check_targets(draft, action)
        if target_check is not None:
            return target_check
        self_only_check = self._check_self_only_targets(draft, action)
        if self_only_check is not None:
            return self_only_check
        requires_self_target_check = self._check_requires_self_target(draft, action)
        if requires_self_target_check is not None:
            return requires_self_target_check
        willing_target_check = self._check_willing_targets(draft, action)
        if willing_target_check is not None:
            return willing_target_check
        countercharm_check = self._check_countercharm(draft, action)
        if countercharm_check is not None:
            return countercharm_check
        uncanny_dodge_check = self._check_uncanny_dodge(draft, action)
        if uncanny_dodge_check is not None:
            return uncanny_dodge_check
        brutal_strike_check = self._check_brutal_strike(draft, actor, action)
        if brutal_strike_check is not None:
            return brutal_strike_check
        cunning_strike_check = self._check_cunning_strike(draft, actor, action)
        if cunning_strike_check is not None:
            return cunning_strike_check
        repelling_blast_check = self._check_repelling_blast(draft, actor, action)
        if repelling_blast_check is not None:
            return repelling_blast_check
        mage_armor_check = self._check_mage_armor_unarmored_targets(draft, actor, action)
        if mage_armor_check is not None:
            return mage_armor_check
        one_with_shadows_check = self._check_one_with_shadows_lighting(draft, action)
        if one_with_shadows_check is not None:
            return one_with_shadows_check
        range_check = self._check_range(draft, action)
        if range_check is not None:
            return range_check
        preserve_life_check = self._check_preserve_life(draft, actor, action)
        if preserve_life_check is not None:
            return preserve_life_check
        return ResolverResult(status="accepted", reason="accepted", action_id=action.id)

    def _resolve_action(self, draft: PlayerActionDraft) -> ActionDefinition | None:
        if draft.candidate_action_id is not None:
            action = self.actions.get(draft.candidate_action_id)
            if action is not None:
                return action
            return self._action_for_item(draft.candidate_action_id, draft)
        normalized = draft.verb.casefold().strip()
        matches = [
            action
            for action in self.actions.values()
            if action.id == normalized
            or action.name.casefold() == normalized
            or normalized
            in [str(alias).casefold() for alias in action.localization.get("aliases", [])]
        ]
        if len(matches) == 1:
            return matches[0]
        return None

    def _action_for_item(
        self,
        item_id: str,
        draft: PlayerActionDraft,
    ) -> ActionDefinition | None:
        item = self.items.get(item_id)
        if item is None:
            return None
        selected = draft.params.get("item_action_id") or draft.params.get("action_id")
        if selected is None:
            if len(item.actions) != 1:
                return None
            selected = item.actions[0]
        selected_action_id = str(selected)
        if selected_action_id not in item.actions:
            return None
        return self.actions.get(selected_action_id)

    def _item_for_draft(self, draft: PlayerActionDraft) -> ItemDefinition | None:
        if draft.verb != "use_item" or draft.candidate_action_id is None:
            return None
        return self.items.get(draft.candidate_action_id)

    def _ownership_error(
        self,
        actor_id: str,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
        item: ItemDefinition | None,
    ) -> str | None:
        if item is not None:
            owner = self._resource_owner(actor_id, actor)
            if not self._actor_has_item(owner, item.id):
                return f"actor does not have item {item.id}"
            if action.id not in item.actions:
                return f"item {item.id} does not provide action {action.id}"
            return None
        if action.action_type == "base_action":
            return None
        owner = self._action_owner(actor_id, actor)
        owned_actions = getattr(owner, "actions", [action.id])
        if (
            action.id not in owned_actions
            and not self._has_active_pact_weapon_action(actor, action)
            and not (isinstance(owner, Combatant) and not owned_actions)
            and not action.requirements.get("global", False)
        ):
            return "actor does not own action"
        return None

    def _fast_hands_item_error(
        self,
        draft: PlayerActionDraft,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
        item: ItemDefinition | None,
    ) -> str | None:
        if not self._uses_fast_hands_item(draft):
            return None
        if item is None:
            return "Fast Hands requires an item"
        owner = self._resource_owner(draft.actor_id, actor)
        if not isinstance(owner, Character) or not has_rogue_thief_feature(owner, level=3):
            return "Fast Hands magic item use requires Rogue Thief level 3"
        if "srd.fast_hands_magic_item" not in owner.actions:
            return "actor does not have Fast Hands magic item use"
        if action.action_type != "item" or action.action_economy != "action":
            return "Fast Hands requires a magic item action that normally uses an action"
        if action.requirements.get("item") != item.id:
            return f"action {action.id} does not require item {item.id}"
        return None

    def _investment_of_chain_master_familiar_error(
        self,
        draft: PlayerActionDraft,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> str | None:
        if action.id != RESOLVER_PACT_OF_CHAIN_FIND_FAMILIAR_ACTION_ID:
            return None
        owner = self._resource_owner(draft.actor_id, actor)
        if not isinstance(owner, Character) or not has_warlock_investment_of_chain_master(owner):
            return None
        if self._investment_familiar_speed_choice(draft.params) is None:
            return "Investment of the Chain Master requires investment_familiar_speed fly or swim"
        return None

    @staticmethod
    def _investment_familiar_speed_choice(params: dict[str, Any]) -> str | None:
        raw = params.get(
            "investment_familiar_speed", params.get("investment_of_chain_master_speed")
        )
        choice = str(raw).casefold().strip() if raw not in (None, "", False) else ""
        return {
            "fly": "fly",
            "flying": "fly",
            "飞行": "fly",
            "swim": "swim",
            "swimming": "swim",
            "游泳": "swim",
        }.get(choice)

    @staticmethod
    def _allowed_damage_type_param_error(
        draft: PlayerActionDraft,
        action: ActionDefinition,
    ) -> str | None:
        allowed_raw = action.properties.get("allowed_damage_types")
        if not isinstance(allowed_raw, list) or not allowed_raw:
            return None
        allowed = [str(damage_type) for damage_type in allowed_raw]
        raw = draft.params.get("damage_type")
        if raw is None or raw == "":
            return "missing required parameter damage_type"
        if isinstance(raw, (dict, list)):
            return "parameter damage_type must be a scalar"
        normalized = str(raw).casefold().strip()
        if normalized not in allowed:
            return f"damage_type must be one of: {', '.join(allowed)}"
        draft.params["damage_type"] = normalized
        return None

    @staticmethod
    def _greater_restoration_choice_error(
        draft: PlayerActionDraft,
        action: ActionDefinition,
    ) -> str | None:
        for node in action.automation:
            if node.get("type") != "greater_restoration":
                continue
            choice_param = str(node.get("choice_param", "greater_restoration_choice"))
            if choice_param not in draft.params:
                return f"missing required parameter {choice_param}"
            choice = str(draft.params[choice_param])
            allowed_choices = {str(item) for item in node.get("choices", [])}
            if choice not in allowed_choices or choice not in RESOLVER_GREATER_RESTORATION_CHOICES:
                expected = ", ".join(sorted(allowed_choices & RESOLVER_GREATER_RESTORATION_CHOICES))
                return f"unsupported Greater Restoration choice {choice}; choose {expected}"
        return None

    def _restoring_touch_error(
        self,
        draft: PlayerActionDraft,
        action: ActionDefinition,
    ) -> str | None:
        node = self._restoring_touch_node(action)
        if node is None:
            return None
        points_param = str(node.get("points_param", "lay_on_hands_points"))
        conditions_param = str(node.get("conditions_param", "restoring_touch_conditions"))
        try:
            total_points = self._positive_param_int(draft.params, points_param)
            conditions = self._restoring_touch_conditions(
                node,
                draft.params,
                conditions_param,
            )
        except ValueError as exc:
            return str(exc)
        point_cost = int(
            node.get(
                "point_cost_per_condition",
                RESOLVER_RESTORING_TOUCH_CONDITION_POINT_COST,
            )
        )
        condition_cost = point_cost * len(conditions)
        if total_points < condition_cost:
            return "Restoring Touch requires 5 Lay On Hands points per condition"
        if len(draft.target_ids) != 1:
            return "Restoring Touch requires exactly one target"
        target_id = draft.target_ids[0]
        try:
            target = self.state.entity_for_actor(target_id)
        except KeyError:
            return f"unknown target {target_id}"
        missing = [
            condition
            for condition in conditions
            if not any(
                effect.get("condition") == condition for effect in self._status_effects_for(target)
            )
        ]
        if missing:
            return "Restoring Touch target lacks condition(s): " + ", ".join(missing)
        draft.params[points_param] = total_points
        draft.params[conditions_param] = conditions
        return None

    @staticmethod
    def _restoring_touch_conditions(
        node: dict[str, Any],
        params: dict[str, Any],
        param_name: str,
    ) -> list[str]:
        allowed_raw = node.get(
            "allowed_conditions",
            sorted(RESOLVER_RESTORING_TOUCH_ALLOWED_CONDITIONS),
        )
        allowed = {
            str(condition).casefold().strip()
            for condition in allowed_raw
            if isinstance(condition, str)
        } & RESOLVER_RESTORING_TOUCH_ALLOWED_CONDITIONS
        if not allowed:
            raise ValueError("Restoring Touch has no supported conditions")
        raw = params.get(param_name)
        if raw is None:
            raise ValueError(f"missing required parameter {param_name}")
        if isinstance(raw, str):
            raw_values: list[Any] = [
                value.strip() for value in re.split(r"[,\s]+", raw) if value.strip()
            ]
        elif isinstance(raw, list):
            raw_values = raw
        else:
            raise ValueError(f"parameter {param_name} must be a list of conditions")
        if not raw_values:
            raise ValueError(f"parameter {param_name} must include at least one condition")
        conditions: list[str] = []
        for value in raw_values:
            if isinstance(value, (bool, dict, list)):
                raise ValueError(f"parameter {param_name} entries must be conditions")
            condition = str(value).casefold().strip()
            if condition not in allowed:
                expected = ", ".join(sorted(allowed))
                raise ValueError(f"{param_name} must contain only: {expected}")
            if condition in conditions:
                raise ValueError("Restoring Touch conditions must not repeat")
            conditions.append(condition)
        return conditions

    def _restoring_touch_node(self, action: ActionDefinition) -> dict[str, Any] | None:
        return next(
            (
                node
                for node in self._automation_nodes(action.automation)
                if node.get("type") == "restoring_touch"
            ),
            None,
        )

    def _instinctive_pounce_error(
        self,
        draft: PlayerActionDraft,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> str | None:
        for node in self._automation_nodes(action.automation):
            if node.get("type") != "instinctive_pounce_move":
                continue
            destination_param = str(
                node.get("destination_param", "instinctive_pounce_to_position_node_id")
            )
            destination = draft.params.get(destination_param)
            if destination is None:
                continue
            owner = self._resource_owner(draft.actor_id, actor)
            class_levels = getattr(owner, "class_levels", {})
            if not isinstance(class_levels, dict) or int(class_levels.get("barbarian", 0)) < 7:
                return "Instinctive Pounce requires Barbarian level 7"
            return self._instinctive_pounce_move_error(draft.actor_id, str(destination))
        return None

    def _instinctive_pounce_move_error(self, actor_id: str, destination: str) -> str | None:
        actor = self.state.entity_for_actor(actor_id)
        if not isinstance(actor, Combatant):
            return "Instinctive Pounce requires a combatant"
        if self.state.encounter is None or self.state.encounter.tactical_graph is None:
            return "Instinctive Pounce requires a combat tactical graph"
        if actor.position_node_id is None:
            return "Instinctive Pounce requires a current position"
        graph = TacticalGraph.from_dict(self.state.encounter.tactical_graph)
        if destination not in graph.nodes:
            return "Instinctive Pounce destination position does not exist"
        movement_cost = graph.shortest_distance(
            actor.position_node_id,
            destination,
            movement_cost=True,
        )
        if movement_cost is None:
            return "Instinctive Pounce destination position is not reachable"
        movement_limit = self._effective_speed(actor) // 2
        if int(movement_cost) > movement_limit:
            return "Instinctive Pounce movement cannot exceed half Speed"
        return None

    def _prepare_size_based_oil_vial_cost(
        self,
        draft: PlayerActionDraft,
        action: ActionDefinition,
    ) -> ResolverResult | None:
        cost_param = {
            RESOLVER_OIL_OF_ETHEREALNESS_ACTION_ID: "oil_of_etherealness_vials",
            RESOLVER_APPLY_OIL_OF_SLIPPERINESS_ACTION_ID: "oil_of_slipperiness_vials",
        }.get(action.id)
        if cost_param is None:
            return None
        if len(draft.target_ids) != 1:
            return ResolverResult(
                status="rejected",
                reason=f"{action.name} requires exactly one target",
                action_id=action.id,
            )
        try:
            target = self.state.entity_for_actor(draft.target_ids[0])
        except KeyError:
            return ResolverResult(
                status="rejected",
                reason=f"unknown target {draft.target_ids[0]}",
                action_id=action.id,
            )
        draft.params[cost_param] = self._size_based_oil_vials_required(target)
        return None

    @staticmethod
    def _size_based_oil_vials_required(
        target: Character | Monster | Combatant,
    ) -> int:
        size = str(getattr(target, "size", "medium")).casefold()
        rank = RESOLVER_CREATURE_SIZE_RANKS.get(size, RESOLVER_CREATURE_SIZE_RANKS["medium"])
        return 1 + max(0, rank - RESOLVER_CREATURE_SIZE_RANKS["medium"])

    @staticmethod
    def _uses_fast_hands_item(draft: PlayerActionDraft) -> bool:
        return draft.verb == "use_item" and draft.params.get("fast_hands") is True

    @staticmethod
    def _fleet_step_requested(draft: PlayerActionDraft) -> bool:
        return draft.params.get("use_fleet_step") is True or draft.params.get("fleet_step") is True

    def _uses_fleet_step(
        self,
        draft: PlayerActionDraft,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> bool:
        return (
            self._fleet_step_requested(draft)
            and action.id in RESOLVER_STEP_OF_THE_WIND_ACTION_IDS
            and self._current_fleet_step_window(draft.actor_id) is not None
            and isinstance(self._resource_owner(draft.actor_id, actor), Character)
        )

    def _fleet_step_error(
        self,
        draft: PlayerActionDraft,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> str | None:
        if not self._fleet_step_requested(draft):
            return None
        if action.id not in RESOLVER_STEP_OF_THE_WIND_ACTION_IDS:
            return "Fleet Step can only be used with Step of the Wind"
        owner = self._resource_owner(draft.actor_id, actor)
        if not isinstance(owner, Character) or not has_monk_open_hand_feature(owner, level=11):
            return "Fleet Step requires Open Hand Monk level 11"
        if self._current_fleet_step_window(draft.actor_id) is None:
            return "Fleet Step requires an immediately preceding non-Step Bonus Action"
        return None

    def _current_fleet_step_window(self, actor_id: str) -> dict[str, Any] | None:
        try:
            actor = self.state.entity_for_actor(actor_id)
        except KeyError:
            return None
        for effect in self._status_effects_for(actor):
            if (
                effect.get("condition") == RESOLVER_FLEET_STEP_CONDITION
                and effect.get("source_action_id") == RESOLVER_FLEET_STEP_ACTION_ID
            ):
                return effect
        return None

    @staticmethod
    def _quivering_palm_harmless_release(
        draft: PlayerActionDraft,
        action: ActionDefinition,
    ) -> bool:
        return action.id == RESOLVER_QUIVERING_PALM_RELEASE_ACTION_ID and (
            draft.params.get("harmless") is True or draft.params.get("end_harmlessly") is True
        )

    @staticmethod
    def _uses_rod_of_absorption_spell_slot(draft: PlayerActionDraft) -> bool:
        return (
            draft.params.get("use_rod_of_absorption") is True
            or draft.params.get("rod_of_absorption") is True
        )

    def _rod_of_absorption_spell_slot_error(
        self,
        draft: PlayerActionDraft,
        action: ActionDefinition,
        owner: Character | Monster | Combatant,
    ) -> str | None:
        if not isinstance(owner, Character):
            return "Rod of Absorption requires a spellcaster with spell slots"
        if not self._actor_has_item(owner, RESOLVER_ROD_OF_ABSORPTION_ITEM_ID):
            return "Rod of Absorption requires holding the rod"
        try:
            slot_level = self._rod_of_absorption_created_spell_slot_level(draft, action)
        except ValueError as exc:
            return str(exc)
        highest_slot_level = self._highest_own_spell_slot_level(owner)
        if highest_slot_level <= 0:
            return "Rod of Absorption requires a spellcaster with spell slots"
        if slot_level > highest_slot_level:
            return "Rod of Absorption cannot create a spell slot above your own spell slots"
        if slot_level > RESOLVER_ROD_OF_ABSORPTION_MAX_CREATED_SLOT_LEVEL:
            return "Rod of Absorption cannot create spell slots above level 5"
        stored = int(owner.resources.get(RESOLVER_ROD_OF_ABSORPTION_STORED_LEVELS_RESOURCE, 0))
        if stored < slot_level:
            return "Rod of Absorption has insufficient stored spell energy"
        return None

    @staticmethod
    def _rod_of_absorption_created_spell_slot_level(
        draft: PlayerActionDraft,
        action: ActionDefinition,
    ) -> int:
        base_slot_level = int(action.cost.spell_slot_level or 0)
        requested_slot_level = _optional_int(draft.params.get("slot_level"))
        slot_level = requested_slot_level if requested_slot_level is not None else base_slot_level
        if slot_level < base_slot_level:
            raise ValueError(
                "Rod of Absorption cannot create a lower-level slot than the spell requires"
            )
        return slot_level

    @staticmethod
    def _spell_slot_level_to_spend(
        draft: PlayerActionDraft,
        action: ActionDefinition,
    ) -> int:
        base_slot_level = int(action.cost.spell_slot_level or 0)
        requested_slot_level = _optional_int(draft.params.get("slot_level"))
        slot_level = requested_slot_level if requested_slot_level is not None else base_slot_level
        if slot_level < base_slot_level:
            raise ValueError(f"spell requires level {base_slot_level} slot or higher")
        return slot_level

    @staticmethod
    def _highest_own_spell_slot_level(actor: Character) -> int:
        levels: set[int] = set()
        for slot_map in (actor.spell_slots_max, actor.spell_slots):
            for level, count in slot_map.items():
                try:
                    numeric_level = int(level)
                    numeric_count = int(count)
                except (TypeError, ValueError):
                    continue
                if numeric_level > 0 and numeric_count > 0:
                    levels.add(numeric_level)
        return max(levels, default=0)

    def _check_rod_of_absorption(
        self,
        draft: PlayerActionDraft,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> ResolverResult | None:
        if action.properties.get("rod_of_absorption_initialize") is True:
            owner = self._resource_owner(draft.actor_id, actor)
            if (
                isinstance(owner, Character)
                and int(owner.resources.get(RESOLVER_ROD_OF_ABSORPTION_INITIALIZED_RESOURCE, 0)) > 0
            ):
                return ResolverResult(
                    status="rejected",
                    reason="Rod of Absorption energy is already initialized",
                    action_id=action.id,
                )
            return None
        if action.properties.get("rod_of_absorption_absorb_spell") is not True:
            return None
        owner = self._resource_owner(draft.actor_id, actor)
        if not isinstance(owner, Character):
            return ResolverResult(
                status="rejected",
                reason="Rod of Absorption requires a character owner",
                action_id=action.id,
            )
        spell_level_param = str(action.properties.get("spell_level_param", "absorbed_spell_level"))
        try:
            spell_level = self._required_spell_level_param(draft.params, spell_level_param)
        except ValueError as exc:
            return ResolverResult(status="rejected", reason=str(exc), action_id=action.id)
        targeting_param = str(
            action.properties.get("targeting_only_you_param", "targeting_only_you")
        )
        area_param = str(
            action.properties.get("creates_area_of_effect_param", "creates_area_of_effect")
        )
        targeting_only_you = draft.params.get(targeting_param)
        creates_area = draft.params.get(area_param)
        if not isinstance(targeting_only_you, bool):
            return ResolverResult(
                status="rejected",
                reason=f"parameter {targeting_param} must be a boolean",
                action_id=action.id,
            )
        if not isinstance(creates_area, bool):
            return ResolverResult(
                status="rejected",
                reason=f"parameter {area_param} must be a boolean",
                action_id=action.id,
            )
        if not targeting_only_you:
            return ResolverResult(
                status="rejected",
                reason="Rod of Absorption can absorb only a spell targeting only you",
                action_id=action.id,
            )
        if creates_area:
            return ResolverResult(
                status="rejected",
                reason="Rod of Absorption cannot absorb an area-of-effect spell",
                action_id=action.id,
            )
        lifetime = int(
            owner.resources.get(RESOLVER_ROD_OF_ABSORPTION_LIFETIME_ABSORBED_RESOURCE, 0)
        )
        if lifetime + spell_level > RESOLVER_ROD_OF_ABSORPTION_LIFETIME_CAP:
            return ResolverResult(
                status="rejected",
                reason="Rod of Absorption cannot store that spell level",
                action_id=action.id,
            )
        return None

    def _check_rod_of_alertness(
        self,
        draft: PlayerActionDraft,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> ResolverResult | None:
        if action.properties.get("rod_of_alertness_protective_aura") is not True:
            return None
        owner = self._resource_owner(draft.actor_id, actor)
        if not isinstance(owner, Character):
            return ResolverResult(
                status="rejected",
                reason="Rod of Alertness requires a character owner",
                action_id=action.id,
            )
        if int(owner.resources.get(RESOLVER_ROD_OF_ALERTNESS_PROTECTIVE_AURA_USED_RESOURCE, 0)) > 0:
            return ResolverResult(
                status="rejected",
                reason="Rod of Alertness Protective Aura can't be used again until the next dawn",
                action_id=action.id,
            )
        if self.state.encounter is None:
            return None
        actor_combatant = self.state.encounter.combatants.get(draft.actor_id)
        if actor_combatant is None:
            return None
        actor_aliases = self._entity_aliases(draft.actor_id)
        for target_id in draft.target_ids:
            if target_id in actor_aliases:
                continue
            target = self.state.encounter.combatants.get(target_id)
            if target is not None and target.side == actor_combatant.side:
                continue
            return ResolverResult(
                status="rejected",
                reason="Rod of Alertness Protective Aura affects only you and your allies",
                action_id=action.id,
            )
        return None

    @staticmethod
    def _required_spell_level_param(params: dict[str, Any], param_name: str) -> int:
        if param_name not in params:
            raise ValueError(f"missing required parameter {param_name}")
        value = params[param_name]
        if isinstance(value, bool):
            raise ValueError(f"parameter {param_name} must be an integer")
        try:
            spell_level = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"parameter {param_name} must be an integer") from exc
        if spell_level < 0 or spell_level > 9:
            raise ValueError("Rod of Absorption absorbed spell level must be 0-9")
        return spell_level

    def _requirements_error(
        self,
        actor_id: str,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> str | None:
        requirements = action.requirements
        class_name = requirements.get("class")
        class_level_min = requirements.get("class_level_min")
        if class_name is not None or class_level_min is not None:
            owner = self._action_owner(actor_id, actor)
            class_levels = getattr(owner, "class_levels", None)
            if not isinstance(class_levels, dict):
                return "actor does not meet class requirements"
            if class_name is not None:
                required_level = int(class_level_min or 1)
                actual_level = int(class_levels.get(str(class_name), 0))
                if actual_level < required_level:
                    return f"requires {class_name} level {required_level}"
            else:
                assert class_level_min is not None
                required_level = int(class_level_min)
                highest_class_level = max(
                    (int(level) for level in class_levels.values()), default=0
                )
                if highest_class_level < required_level:
                    return f"requires class level {required_level}"
        class_any = requirements.get("class_any")
        if class_any is not None:
            if isinstance(class_any, str):
                required_classes = [class_any]
            elif isinstance(class_any, list):
                required_classes = [str(item) for item in class_any]
            else:
                return "class_any requirement must be a string or list"
            required_classes = [class_name.lower() for class_name in required_classes if class_name]
            owner = self._action_owner(actor_id, actor)
            class_levels = getattr(owner, "class_levels", None)
            if not isinstance(class_levels, dict):
                return "actor does not meet class requirements"
            required_level = int(requirements.get("class_any_level_min", 1))
            if not any(
                int(class_levels.get(class_name, 0)) >= required_level
                for class_name in required_classes
            ):
                return f"requires one of {', '.join(required_classes)}"
        if (
            requirements.get("no_movement_used") is True
            and self._movement_used_this_turn(actor_id, actor) > 0
        ):
            return "requires no movement used this turn"
        subclass = requirements.get("subclass")
        if subclass is not None:
            if class_name is None:
                return "subclass requirement requires class"
            owner = self._action_owner(actor_id, actor)
            if not isinstance(owner, Character) or owner.subclasses.get(str(class_name)) != str(
                subclass
            ):
                return f"requires {class_name} subclass {subclass}"
        return None

    def _movement_used_this_turn(
        self,
        actor_id: str,
        actor: Character | Monster | Combatant,
    ) -> int:
        if self.state.encounter is not None:
            budget_data = self.state.encounter.action_budgets.get(actor_id)
            if budget_data is not None:
                if "movement_used" in budget_data:
                    return int(budget_data.get("movement_used", 0))
                return max(0, self._effective_speed(actor) - int(budget_data.get("movement", 0)))
        budget = self.economy.budget_for(actor_id, self._effective_speed(actor))
        return int(getattr(budget, "movement_used", 0))

    def _action_budget_for_check(
        self,
        actor_id: str,
        actor: Character | Monster | Combatant,
    ) -> ActionBudget:
        if self.state.encounter is not None and actor_id in self.state.encounter.action_budgets:
            return ActionBudget.from_dict(self.state.encounter.action_budgets[actor_id])
        return self.economy.budget_for(actor_id, self._effective_speed(actor))

    def _spellcasting_error(
        self,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> str | None:
        if action.action_type != "spell":
            return None
        for effect in self._status_effects_for(actor):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            if modifiers.get("blocks_spellcasting") is True:
                source = effect.get("source_action_id") or effect.get("condition") or "effect"
                return f"actor cannot cast spells while affected by {source}"
        return None

    def _allowed_action_error(
        self,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> str | None:
        for effect in self._status_effects_for(actor):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            allowed = modifiers.get("allowed_action_ids")
            if allowed is None:
                continue
            if isinstance(allowed, str):
                allowed_ids = {allowed}
            elif isinstance(allowed, list):
                allowed_ids = {str(item) for item in allowed}
            else:
                continue
            if action.id not in allowed_ids:
                source = effect.get("source_action_id") or effect.get("condition") or "effect"
                allowed_text = ", ".join(sorted(allowed_ids))
                return (
                    f"actor can only take allowed actions ({allowed_text}) "
                    f"while affected by {source}"
                )
        return None

    def _attack_error(
        self,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> str | None:
        if action.action_type not in RESOLVER_ATTACK_ACTION_TYPES:
            return None
        for effect in self._status_effects_for(actor):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            if modifiers.get("blocks_attacks") is True:
                source = effect.get("source_action_id") or effect.get("condition") or "effect"
                return f"actor cannot attack while affected by {source}"
        return None

    def _ritual_casting_error(
        self,
        draft: PlayerActionDraft,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> str | None:
        if not bool(draft.params.get("as_ritual", False)):
            return None
        owner = self._resource_owner(draft.actor_id, actor)
        if not isinstance(owner, Character):
            return "ritual casting requires a character"
        requested_slot_level = _optional_int(draft.params.get("slot_level"))
        eligibility = ritual_casting_eligibility(
            owner,
            action,
            requested_slot_level=requested_slot_level,
        )
        if not eligibility.allowed:
            return eligibility.reason
        return None

    def _check_cost_resources(
        self,
        draft: PlayerActionDraft,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> ResolverResult | None:
        owner = self._resource_owner(draft.actor_id, actor)
        for resource, amount in action.cost.resources.items():
            if self._resource_amount(owner, resource) < amount:
                return ResolverResult(
                    status="rejected",
                    reason=f"insufficient resource {resource}",
                    action_id=action.id,
                )
        for resource, param_name in action.cost.resource_params.items():
            try:
                amount = self._positive_param_int(draft.params, param_name)
            except ValueError as exc:
                return ResolverResult(
                    status="rejected",
                    reason=str(exc),
                    action_id=action.id,
                )
            if self._resource_amount(owner, resource) < amount:
                return ResolverResult(
                    status="rejected",
                    reason=f"insufficient resource {resource}",
                    action_id=action.id,
                )
        for item_id, amount in action.cost.items.items():
            if self._resource_amount(owner, item_id) < amount:
                return ResolverResult(
                    status="rejected",
                    reason=f"insufficient item {item_id}",
                    action_id=action.id,
                )
        if action.cost.gold and self._resource_amount(owner, "gold") < action.cost.gold:
            return ResolverResult(
                status="rejected", reason="insufficient gold", action_id=action.id
            )
        return None

    @staticmethod
    def _positive_param_int(params: dict[str, Any], param_name: str) -> int:
        if param_name not in params:
            raise ValueError(f"missing required parameter {param_name}")
        try:
            amount = int(params[param_name])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"parameter {param_name} must be an integer") from exc
        if amount <= 0:
            raise ValueError(f"parameter {param_name} must be positive")
        return amount

    @staticmethod
    def _resource_amount(actor: Character | Monster | Combatant, resource: str) -> int:
        if isinstance(actor, Character) and resource == "gold":
            return actor.gold
        if isinstance(actor, Character) and resource.startswith("spell_slot_"):
            return actor.spell_slots.get(resource.removeprefix("spell_slot_"), 0)
        if isinstance(actor, Character) and resource in actor.resources:
            return int(actor.resources.get(resource, 0))
        inventory = getattr(actor, "inventory", {})
        if isinstance(inventory, dict):
            return int(inventory.get(resource, 0))
        return 0

    @staticmethod
    def _actor_has_item(actor: Character | Monster | Combatant, item_id: str) -> bool:
        inventory = getattr(actor, "inventory", {})
        if isinstance(inventory, dict) and int(inventory.get(item_id, 0)) > 0:
            return True
        equipment = getattr(actor, "equipment", [])
        return isinstance(equipment, list) and item_id in {str(item) for item in equipment}

    def _check_resource_delta_caps(
        self,
        draft: PlayerActionDraft,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> ResolverResult | None:
        owner = self._resource_owner(draft.actor_id, actor)
        for node in self._automation_nodes(action.automation):
            if node.get("type") != "resource_delta" or "max_from" not in node:
                continue
            delta = int(node.get("delta", 0))
            resource = str(node["resource"])
            maximum = self._resource_delta_cap(owner, node)
            if maximum is not None and self._resource_amount(owner, resource) + delta > maximum:
                return ResolverResult(
                    status="rejected",
                    reason=f"resource {resource} would exceed maximum {maximum}",
                    action_id=action.id,
                )
        return None

    def _check_brutal_strike(
        self,
        draft: PlayerActionDraft,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> ResolverResult | None:
        try:
            effects = self._brutal_strike_effects(draft.params)
        except ValueError as exc:
            return ResolverResult(status="rejected", reason=str(exc), action_id=action.id)
        if not self._brutal_strike_requested(draft.params):
            return None
        if not effects:
            return ResolverResult(
                status="rejected",
                reason="Brutal Strike requires an effect choice",
                action_id=action.id,
            )
        owner = self._resource_owner(draft.actor_id, actor)
        if not isinstance(owner, Character) or not has_barbarian_feature(owner, level=9):
            return ResolverResult(
                status="rejected",
                reason="Brutal Strike requires Barbarian level 9",
                action_id=action.id,
            )
        for effect in effects:
            if effect in RESOLVER_IMPROVED_BRUTAL_STRIKE_EFFECTS and not has_barbarian_feature(
                owner,
                level=13,
            ):
                return ResolverResult(
                    status="rejected",
                    reason="Improved Brutal Strike requires Barbarian level 13",
                    action_id=action.id,
                )
        if len(effects) > 1 and not has_barbarian_feature(owner, level=17):
            return ResolverResult(
                status="rejected",
                reason="Improved Brutal Strike requires Barbarian level 17",
                action_id=action.id,
            )
        if not self._action_qualifies_for_brutal_strike(action):
            return ResolverResult(
                status="rejected",
                reason="Brutal Strike requires a weapon or Unarmed Strike attack",
                action_id=action.id,
            )
        attack_node = self._first_attack_roll_node(action)
        if attack_node is None or str(attack_node.get("ability", "str")).lower() != "str":
            return ResolverResult(
                status="rejected",
                reason="Brutal Strike requires a Strength-based attack roll",
                action_id=action.id,
            )
        if not any(
            effect_entry.get("condition") == "reckless_attack"
            for effect_entry in self._status_effects_for(actor)
        ):
            return ResolverResult(
                status="rejected",
                reason="Brutal Strike requires Reckless Attack",
                action_id=action.id,
            )
        if len(draft.target_ids) != 1:
            return ResolverResult(
                status="rejected",
                reason="Brutal Strike requires exactly one target",
                action_id=action.id,
            )
        if "forceful_blow" in effects:
            target_id = draft.target_ids[0]
            destination = self._brutal_strike_forceful_destination(
                draft.params,
                target_id=target_id,
            )
            if destination is None:
                return ResolverResult(
                    status="rejected",
                    reason="Brutal Strike Forceful Blow requires a destination position",
                    action_id=action.id,
                )
            plan_error = self._brutal_strike_forceful_error(
                draft.actor_id,
                target_id,
                destination,
            )
            if plan_error is not None:
                return ResolverResult(status="rejected", reason=plan_error, action_id=action.id)
            follow_destination = self._brutal_strike_forceful_follow_destination(
                draft.params,
                target_id=target_id,
            )
            if follow_destination is not None:
                follow_error = self._brutal_strike_forceful_follow_error(
                    draft.actor_id,
                    target_id,
                    follow_destination,
                    target_position=destination,
                )
                if follow_error is not None:
                    return ResolverResult(
                        status="rejected",
                        reason=follow_error,
                        action_id=action.id,
                    )
        return None

    @staticmethod
    def _resource_delta_cap(
        owner: Character | Monster | Combatant,
        node: dict[str, Any],
    ) -> int | None:
        max_from = node.get("max_from")
        if max_from is None:
            return None
        if not isinstance(max_from, dict):
            return None
        class_name = max_from.get("class_level")
        if isinstance(class_name, str):
            class_levels = getattr(owner, "class_levels", {})
            if not isinstance(class_levels, dict):
                return 0
            return max(0, int(class_levels.get(class_name, 0)))
        class_resource = max_from.get("class_resource")
        if isinstance(class_resource, str):
            if not isinstance(owner, Character):
                return 0
            return max(0, int(resource_maxima(owner).get(class_resource, 0)))
        return None

    @staticmethod
    def _brutal_strike_requested(params: dict[str, Any]) -> bool:
        return (
            params.get("use_brutal_strike") is True
            or params.get("brutal_strike_effects") not in (None, "", False)
            or params.get("brutal_strikes") not in (None, "", False)
            or params.get("brutal_strike_effect") not in (None, "", False)
            or params.get("brutal_strike") not in (None, "", False)
        )

    @staticmethod
    def _brutal_strike_effect(params: dict[str, Any]) -> str | None:
        effects = ActionResolver._brutal_strike_effects(params)
        return effects[0] if effects else None

    @staticmethod
    def _brutal_strike_effects(params: dict[str, Any]) -> list[str]:
        raw = params.get("brutal_strikes")
        if raw is None:
            raw = params.get("brutal_strike_effects")
        if raw is None:
            raw = params.get("brutal_strike_effect")
        if raw is None:
            raw = params.get("brutal_strike")
        if raw in (None, "", False):
            return []
        aliases = {
            "forceful": "forceful_blow",
            "forceful_blow": "forceful_blow",
            "hamstring": "hamstring_blow",
            "hamstring_blow": "hamstring_blow",
            "staggering": "staggering_blow",
            "staggering_blow": "staggering_blow",
            "sundering": "sundering_blow",
            "sundering_blow": "sundering_blow",
        }
        if isinstance(raw, str):
            raw_values = [part for part in re.split(r"[,;]+", raw) if part.strip()]
        elif isinstance(raw, (list, tuple)):
            raw_values = list(raw)
        else:
            raw_values = [raw]
        effects: list[str] = []
        for value in raw_values:
            normalized = str(value).casefold().strip().replace("-", "_").replace(" ", "_")
            effect = aliases.get(normalized, normalized)
            if effect not in RESOLVER_BRUTAL_STRIKE_EFFECTS:
                raise ValueError(f"unsupported Brutal Strike effect: {effect}")
            if effect in effects:
                raise ValueError(f"duplicate Brutal Strike effect: {effect}")
            effects.append(effect)
        if len(effects) > 2:
            raise ValueError("Improved Brutal Strike allows at most two effects")
        return effects

    def _action_qualifies_for_brutal_strike(self, action: ActionDefinition) -> bool:
        if action.action_type not in {"weapon_attack", "unarmed_attack"}:
            return False
        nodes = self._automation_nodes(action.automation)
        return any(node.get("type") == "attack_roll" for node in nodes) and any(
            node.get("type") == "damage" and node.get("requires_hit") is True for node in nodes
        )

    def _first_attack_roll_node(self, action: ActionDefinition) -> dict[str, Any] | None:
        return next(
            (
                node
                for node in self._automation_nodes(action.automation)
                if node.get("type") == "attack_roll"
            ),
            None,
        )

    @staticmethod
    def _brutal_strike_forceful_destination(
        params: dict[str, Any],
        *,
        target_id: str,
    ) -> str | None:
        by_target = params.get("brutal_strike_forceful_to_position_node_id_by_target")
        if isinstance(by_target, dict):
            selected = by_target.get(target_id)
            if selected not in (None, "", False):
                return str(selected)
        selected = params.get("brutal_strike_forceful_to_position_node_id")
        if selected in (None, "", False):
            return None
        return str(selected)

    @staticmethod
    def _brutal_strike_forceful_follow_destination(
        params: dict[str, Any],
        *,
        target_id: str,
    ) -> str | None:
        by_target = params.get("brutal_strike_forceful_follow_to_position_node_id_by_target")
        if isinstance(by_target, dict):
            selected = by_target.get(target_id)
            if selected not in (None, "", False):
                return str(selected)
        selected = params.get("brutal_strike_forceful_follow_to_position_node_id")
        if selected in (None, "", False):
            return None
        return str(selected)

    def _brutal_strike_forceful_error(
        self,
        actor_id: str,
        target_id: str,
        destination: str,
    ) -> str | None:
        actor = self.state.entity_for_actor(actor_id)
        target = self.state.entity_for_actor(target_id)
        if not isinstance(actor, Combatant) or not isinstance(target, Combatant):
            return "Brutal Strike Forceful Blow requires combatants"
        if self.state.encounter is None or self.state.encounter.tactical_graph is None:
            return "Brutal Strike Forceful Blow requires a combat tactical graph"
        if actor.position_node_id is None or target.position_node_id is None:
            return "Brutal Strike Forceful Blow requires current positions"
        graph = TacticalGraph.from_dict(self.state.encounter.tactical_graph)
        if destination not in graph.nodes:
            return "Brutal Strike Forceful Blow destination position does not exist"
        movement_distance = graph.shortest_distance(target.position_node_id, destination)
        if movement_distance is None:
            return "Brutal Strike Forceful Blow destination position is not reachable"
        if int(movement_distance) > 15:
            return "Brutal Strike Forceful Blow cannot exceed 15 feet"
        before_distance = graph.shortest_distance(actor.position_node_id, target.position_node_id)
        after_distance = graph.shortest_distance(actor.position_node_id, destination)
        if (
            before_distance is not None
            and after_distance is not None
            and after_distance <= before_distance
        ):
            return "Brutal Strike Forceful Blow destination must be away from the Barbarian"
        return None

    def _brutal_strike_forceful_follow_error(
        self,
        actor_id: str,
        target_id: str,
        destination: str,
        *,
        target_position: str | None = None,
    ) -> str | None:
        actor = self.state.entity_for_actor(actor_id)
        target = self.state.entity_for_actor(target_id)
        if not isinstance(actor, Combatant) or not isinstance(target, Combatant):
            return "Brutal Strike Forceful Blow follow movement requires combatants"
        if self.state.encounter is None or self.state.encounter.tactical_graph is None:
            return "Brutal Strike Forceful Blow follow movement requires a combat tactical graph"
        if actor.position_node_id is None or target.position_node_id is None:
            return "Brutal Strike Forceful Blow follow movement requires positions"
        graph = TacticalGraph.from_dict(self.state.encounter.tactical_graph)
        if destination not in graph.nodes:
            return "Brutal Strike Forceful Blow follow destination position does not exist"
        target_position = target_position or target.position_node_id
        movement_cost = graph.shortest_distance(
            actor.position_node_id,
            destination,
            movement_cost=True,
        )
        if movement_cost is None:
            return "Brutal Strike Forceful Blow follow destination position is not reachable"
        movement_limit = self._effective_speed(actor) // 2
        if int(movement_cost) > movement_limit:
            return "Brutal Strike Forceful Blow follow movement cannot exceed half Speed"
        before_distance = graph.shortest_distance(actor.position_node_id, target_position)
        after_distance = graph.shortest_distance(destination, target_position)
        if (
            before_distance is not None
            and after_distance is not None
            and after_distance >= before_distance
        ):
            return "Brutal Strike Forceful Blow follow destination must be toward the target"
        return None

    def _check_cunning_strike(
        self,
        draft: PlayerActionDraft,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> ResolverResult | None:
        try:
            effects = self._cunning_strike_choices(draft.params)
        except ValueError as exc:
            return ResolverResult(status="rejected", reason=str(exc), action_id=action.id)
        if not effects:
            return None
        if draft.params.get("use_sneak_attack") is not True:
            return ResolverResult(
                status="rejected",
                reason="Cunning Strike requires Sneak Attack",
                action_id=action.id,
            )
        if action.action_type != "weapon_attack" or not self._action_qualifies_for_sneak_attack(
            action
        ):
            return ResolverResult(
                status="rejected",
                reason="Cunning Strike requires a Sneak Attack weapon attack",
                action_id=action.id,
            )
        owner = self._resource_owner(draft.actor_id, actor)
        rogue_level = int(owner.class_levels.get("rogue", 0)) if isinstance(owner, Character) else 0
        if not isinstance(owner, Character) or rogue_level < 5:
            return ResolverResult(
                status="rejected",
                reason="Cunning Strike requires Rogue level 5",
                action_id=action.id,
            )
        if len(effects) > 1 and rogue_level < 11:
            return ResolverResult(
                status="rejected",
                reason="Improved Cunning Strike requires Rogue level 11",
                action_id=action.id,
            )
        if "poison" in effects and not self._has_item_on_person(
            owner,
            RESOLVER_POISONERS_KIT_ITEM_ID,
        ):
            return ResolverResult(
                status="rejected",
                reason="Cunning Strike Poison requires a Poisoner's Kit",
                action_id=action.id,
            )
        if "trip" in effects:
            for target_id in draft.target_ids:
                if not self._target_large_or_smaller(target_id):
                    return ResolverResult(
                        status="rejected",
                        reason="Cunning Strike Trip requires a Large or smaller target",
                        action_id=action.id,
                    )
        if "withdraw" in effects:
            destination = self._cunning_strike_withdraw_destination(draft.params)
            if destination is None:
                return ResolverResult(
                    status="rejected",
                    reason="Cunning Strike Withdraw requires a destination position",
                    action_id=action.id,
                )
            plan_error = self._cunning_strike_withdraw_error(draft.actor_id, destination)
            if plan_error is not None:
                return ResolverResult(status="rejected", reason=plan_error, action_id=action.id)
        if "stealth_attack" in effects:
            if not has_rogue_thief_feature(owner, level=9):
                return ResolverResult(
                    status="rejected",
                    reason="Supreme Sneak Stealth Attack requires Rogue Thief level 9",
                    action_id=action.id,
                )
            if not self._has_hide_invisible_condition(draft.actor_id):
                return ResolverResult(
                    status="rejected",
                    reason="Supreme Sneak Stealth Attack requires the Hide action's condition",
                    action_id=action.id,
                )
            if self._cunning_strike_stealth_attack_cover(draft.params) is None:
                return ResolverResult(
                    status="rejected",
                    reason=(
                        "Supreme Sneak Stealth Attack requires end-turn cover of "
                        "Three-Quarters Cover or Total Cover"
                    ),
                    action_id=action.id,
                )
        return None

    def _check_repelling_blast(
        self,
        draft: PlayerActionDraft,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> ResolverResult | None:
        if draft.params.get("use_repelling_blast") is not True:
            return None
        owner = self._resource_owner(draft.actor_id, actor)
        spell_id = action.properties.get("spell_definition_id")
        if not isinstance(owner, Character) or not has_warlock_repelling_blast(
            owner,
            spell_id=str(spell_id) if isinstance(spell_id, str) else None,
        ):
            return ResolverResult(
                status="rejected",
                reason="Repelling Blast requires the selected Warlock invocation",
                action_id=action.id,
            )
        if not self._action_qualifies_for_repelling_blast(action):
            return ResolverResult(
                status="rejected",
                reason="Repelling Blast requires a Warlock cantrip attack roll",
                action_id=action.id,
            )
        if not draft.target_ids:
            return ResolverResult(
                status="rejected",
                reason="Repelling Blast requires a target",
                action_id=action.id,
            )
        for target_id in draft.target_ids:
            if not self._target_large_or_smaller(target_id):
                return ResolverResult(
                    status="rejected",
                    reason="Repelling Blast target must be Large or smaller",
                    action_id=action.id,
                )
            destination = self._repelling_blast_destination(draft.params, target_id=target_id)
            if destination is None:
                return ResolverResult(
                    status="rejected",
                    reason="Repelling Blast requires a destination position",
                    action_id=action.id,
                )
            plan_error = self._repelling_blast_push_error(draft.actor_id, target_id, destination)
            if plan_error is not None:
                return ResolverResult(status="rejected", reason=plan_error, action_id=action.id)
        return None

    def _action_qualifies_for_repelling_blast(self, action: ActionDefinition) -> bool:
        if action.action_type != "spell":
            return False
        nodes = self._automation_nodes(action.automation)
        return any(node.get("type") == "attack_roll" for node in nodes) and any(
            node.get("type") == "damage" and node.get("requires_hit") is True for node in nodes
        )

    @staticmethod
    def _repelling_blast_destination(
        params: dict[str, Any],
        *,
        target_id: str,
    ) -> str | None:
        by_target = params.get("repelling_blast_to_position_node_id_by_target")
        if isinstance(by_target, dict):
            selected = by_target.get(target_id)
            if selected not in (None, "", False):
                return str(selected)
        selected = params.get("repelling_blast_to_position_node_id")
        if selected in (None, "", False):
            return None
        return str(selected)

    def _repelling_blast_push_error(
        self,
        actor_id: str,
        target_id: str,
        destination: str,
    ) -> str | None:
        actor = self.state.entity_for_actor(actor_id)
        target = self.state.entity_for_actor(target_id)
        if not isinstance(actor, Combatant) or not isinstance(target, Combatant):
            return "Repelling Blast requires combatants"
        if self.state.encounter is None or self.state.encounter.tactical_graph is None:
            return "Repelling Blast requires a combat tactical graph"
        if actor.position_node_id is None or target.position_node_id is None:
            return "Repelling Blast requires current positions"
        graph = TacticalGraph.from_dict(self.state.encounter.tactical_graph)
        if destination not in graph.nodes:
            return "Repelling Blast destination position does not exist"
        movement_distance = graph.shortest_distance(target.position_node_id, destination)
        if movement_distance is None:
            return "Repelling Blast destination position is not reachable"
        if int(movement_distance) > 10:
            return "Repelling Blast cannot exceed 10 feet"
        before_distance = graph.shortest_distance(actor.position_node_id, target.position_node_id)
        after_distance = graph.shortest_distance(actor.position_node_id, destination)
        if (
            before_distance is not None
            and after_distance is not None
            and after_distance <= before_distance
        ):
            return "Repelling Blast destination must be away from the Warlock"
        return None

    def _check_mage_armor_unarmored_targets(
        self,
        draft: PlayerActionDraft,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> ResolverResult | None:
        if action.properties.get("spell_definition_id") != "srd.spell.mage_armor":
            return None
        target_ids = list(draft.target_ids)
        if not target_ids and action.target_policy.get("self") is True:
            target_ids = [draft.actor_id]
        for target_id in target_ids:
            try:
                target = self.state.entity_for_actor(target_id)
            except KeyError:
                continue
            owner = self._resource_owner(target_id, target)
            if isinstance(owner, Character) and is_wearing_armor(owner):
                return ResolverResult(
                    status="rejected",
                    reason="Mage Armor target must not be wearing armor",
                    action_id=action.id,
                )
        return None

    @staticmethod
    def _check_one_with_shadows_lighting(
        draft: PlayerActionDraft,
        action: ActionDefinition,
    ) -> ResolverResult | None:
        if action.properties.get("requires_dim_light_or_darkness") is not True:
            return None
        if draft.params.get("in_dim_light_or_darkness") is True:
            return None
        return ResolverResult(
            status="rejected",
            reason="One with Shadows requires Dim Light or Darkness",
            action_id=action.id,
        )

    def _check_uncanny_dodge(
        self,
        draft: PlayerActionDraft,
        action: ActionDefinition,
    ) -> ResolverResult | None:
        try:
            target_id = self._uncanny_dodge_target_id(draft.target_ids, draft.params)
        except ValueError as exc:
            return ResolverResult(status="rejected", reason=str(exc), action_id=action.id)
        if target_id is None:
            return None
        if target_id not in set(draft.target_ids):
            return ResolverResult(
                status="rejected",
                reason="Uncanny Dodge target must be a target of the attack",
                action_id=action.id,
            )
        if not self._action_supports_uncanny_dodge(action):
            return ResolverResult(
                status="rejected",
                reason="Uncanny Dodge requires a hit from an attack roll",
                action_id=action.id,
            )
        try:
            target = self.state.entity_for_actor(target_id)
        except KeyError:
            return ResolverResult(
                status="rejected", reason="unknown Uncanny Dodge target", action_id=action.id
            )
        owner = self._resource_owner(target_id, target)
        if not isinstance(owner, Character) or int(owner.class_levels.get("rogue", 0)) < 5:
            return ResolverResult(
                status="rejected",
                reason="Uncanny Dodge requires Rogue level 5",
                action_id=action.id,
            )
        if not self._uncanny_dodge_attacker_visible(draft.actor_id, target_id, draft.params):
            return ResolverResult(
                status="rejected",
                reason="Uncanny Dodge requires a visible attacker",
                action_id=action.id,
            )
        budget = self._action_budget_for_check(target_id, target)
        if not budget.can_spend("reaction"):
            return ResolverResult(
                status="rejected",
                reason="insufficient reaction economy",
                action_id=action.id,
            )
        return None

    @staticmethod
    def _uncanny_dodge_target_id(
        targets: list[str],
        params: dict[str, Any],
    ) -> str | None:
        if params.get("use_uncanny_dodge") is not True:
            return None
        explicit = params.get("uncanny_dodge_target_id")
        if explicit is not None:
            return str(explicit)
        if len(targets) == 1:
            return str(targets[0])
        raise ValueError("Uncanny Dodge requires a target id")

    def _action_supports_uncanny_dodge(self, action: ActionDefinition) -> bool:
        if action.action_type not in RESOLVER_ATTACK_ACTION_TYPES:
            return False
        nodes = self._automation_nodes(action.automation)
        return any(node.get("type") == "attack_roll" for node in nodes) and any(
            node.get("type") == "damage" and node.get("requires_hit") is True for node in nodes
        )

    def _uncanny_dodge_attacker_visible(
        self,
        attacker_id: str,
        target_id: str,
        params: dict[str, Any],
    ) -> bool:
        explicit = params.get("uncanny_dodge_attacker_visible", params.get("attacker_visible"))
        if explicit is not None:
            return explicit is True
        if self.state.encounter is None or self.state.encounter.tactical_graph is None:
            return False
        attacker = self.state.encounter.combatants.get(attacker_id)
        target = self.state.encounter.combatants.get(target_id)
        if (
            attacker is None
            or target is None
            or attacker.position_node_id is None
            or target.position_node_id is None
        ):
            return False
        graph = TacticalGraph.from_dict(self.state.encounter.tactical_graph)
        return graph.has_line_of_sight(target.position_node_id, attacker.position_node_id)

    def _check_countercharm(
        self,
        draft: PlayerActionDraft,
        action: ActionDefinition,
    ) -> ResolverResult | None:
        if draft.params.get("use_countercharm") is not True:
            return None
        try:
            target_id = self._countercharm_target_id(draft.target_ids, draft.params)
        except ValueError as exc:
            return ResolverResult(status="rejected", reason=str(exc), action_id=action.id)
        if target_id not in set(draft.target_ids):
            return ResolverResult(
                status="rejected",
                reason="Countercharm target must be a target of the action",
                action_id=action.id,
            )
        if not self._action_supports_countercharm(action):
            return ResolverResult(
                status="rejected",
                reason="Countercharm requires a save against Charmed or Frightened",
                action_id=action.id,
            )
        bard_id = self._countercharm_bard_id(draft.params)
        if bard_id is None:
            return ResolverResult(
                status="rejected",
                reason="Countercharm requires an explicit Bard",
                action_id=action.id,
            )
        try:
            bard_entity = self.state.entity_for_actor(bard_id)
            target = self.state.entity_for_actor(target_id)
        except KeyError:
            return ResolverResult(
                status="rejected",
                reason="Countercharm requires known Bard and target",
                action_id=action.id,
            )
        bard_owner = self._resource_owner(bard_id, bard_entity)
        if not isinstance(bard_owner, Character) or int(bard_owner.class_levels.get("bard", 0)) < 7:
            return ResolverResult(
                status="rejected",
                reason="Countercharm requires Bard level 7",
                action_id=action.id,
            )
        budget = self._action_budget_for_check(bard_id, bard_entity)
        if not budget.can_spend("reaction"):
            return ResolverResult(
                status="rejected",
                reason="insufficient reaction economy",
                action_id=action.id,
            )
        if not self._countercharm_target_within_range(bard_id, bard_entity, target_id, target):
            return ResolverResult(
                status="rejected",
                reason="Countercharm requires target within 30 feet",
                action_id=action.id,
            )
        return None

    @staticmethod
    def _countercharm_target_id(targets: list[str], params: dict[str, Any]) -> str:
        explicit_target = params.get("countercharm_target_id")
        if explicit_target is not None:
            return str(explicit_target)
        if len(targets) == 1:
            return str(targets[0])
        raise ValueError("Countercharm requires an explicit target")

    @staticmethod
    def _countercharm_bard_id(params: dict[str, Any]) -> str | None:
        explicit_bard = params.get("countercharm_bard_id")
        if explicit_bard is None:
            explicit_bard = params.get("countercharm_actor_id")
        if explicit_bard is None:
            return None
        return str(explicit_bard)

    def _action_supports_countercharm(self, action: ActionDefinition) -> bool:
        nodes = self._automation_nodes(action.automation)
        has_saving_throw = any(node.get("type") == "saving_throw" for node in nodes)
        return has_saving_throw and any(
            node.get("type") == "condition"
            and str(node.get("condition", "")).lower() in RESOLVER_COUNTERCHARM_CONDITIONS
            and node.get("requires_failed_save") is True
            for node in nodes
        )

    def _countercharm_target_within_range(
        self,
        bard_id: str,
        bard: Character | Monster | Combatant,
        target_id: str,
        target: Character | Monster | Combatant,
    ) -> bool:
        if self._entity_aliases(bard_id) & self._entity_aliases(target_id):
            return True
        if self.state.encounter is None or self.state.encounter.tactical_graph is None:
            return False
        bard_combatant = self._combatant_for_entity(bard)
        target_combatant = self._combatant_for_entity(target)
        if (
            bard_combatant is None
            or target_combatant is None
            or bard_combatant.position_node_id is None
            or target_combatant.position_node_id is None
        ):
            return False
        graph = TacticalGraph.from_dict(self.state.encounter.tactical_graph)
        distance = graph.shortest_distance(
            bard_combatant.position_node_id,
            target_combatant.position_node_id,
        )
        return distance is not None and distance <= RESOLVER_COUNTERCHARM_RANGE_FT

    def _combatant_for_entity(
        self,
        entity: Character | Monster | Combatant,
    ) -> Combatant | None:
        if isinstance(entity, Combatant):
            return entity
        if self.state.encounter is None:
            return None
        entity_id = getattr(entity, "id", None)
        if entity_id is None:
            return None
        for combatant in self.state.encounter.combatants.values():
            if combatant.id == entity_id or combatant.entity_id == entity_id:
                return combatant
        return None

    @staticmethod
    def _cunning_strike_choice(params: dict[str, Any]) -> str | None:
        choices = ActionResolver._cunning_strike_choices(params)
        return choices[0] if choices else None

    @staticmethod
    def _cunning_strike_choices(params: dict[str, Any]) -> list[str]:
        raw = params.get(
            "cunning_strikes",
            params.get("cunning_strike_effects", params.get("cunning_strike_effect")),
        )
        if raw is None:
            raw = params.get("cunning_strike")
        if raw in (None, "", False):
            return []
        raw_values: list[Any]
        if isinstance(raw, str):
            raw_values = [part for part in re.split(r"[,;]+", raw) if part.strip()]
        elif isinstance(raw, (list, tuple)):
            raw_values = list(raw)
        else:
            raw_values = [raw]
        effects: list[str] = []
        for value in raw_values:
            effect = str(value).casefold().strip().replace("-", "_").replace(" ", "_")
            if effect not in RESOLVER_CUNNING_STRIKE_EFFECTS:
                raise ValueError(f"unsupported Cunning Strike effect: {effect}")
            if effect in effects:
                raise ValueError(f"duplicate Cunning Strike effect: {effect}")
            effects.append(effect)
        if len(effects) > RESOLVER_MAX_CUNNING_STRIKE_EFFECTS:
            raise ValueError("Improved Cunning Strike allows at most two effects")
        return effects

    @staticmethod
    def _has_item_on_person(actor: Character, item_id: str) -> bool:
        return item_id in actor.equipment or int(actor.inventory.get(item_id, 0)) > 0

    @staticmethod
    def _action_qualifies_for_sneak_attack(action: ActionDefinition) -> bool:
        properties = action.properties.get("weapon_properties", [])
        if isinstance(properties, str):
            properties = [properties]
        weapon_properties = {str(item).lower() for item in properties if isinstance(item, str)}
        if "finesse" in weapon_properties:
            return True
        weapon_category = str(action.properties.get("weapon_category", "")).lower()
        return weapon_category == "ranged"

    def _target_large_or_smaller(self, target_id: str) -> bool:
        target = self.state.entity_for_actor(target_id)
        size = str(getattr(target, "size", "medium")).casefold()
        rank = RESOLVER_CREATURE_SIZE_RANKS.get(size, RESOLVER_CREATURE_SIZE_RANKS["medium"])
        return rank <= RESOLVER_CREATURE_SIZE_RANKS["large"]

    def _target_huge_or_smaller(self, target_id: str) -> bool:
        target = self.state.entity_for_actor(target_id)
        size = str(getattr(target, "size", "medium")).casefold()
        rank = RESOLVER_CREATURE_SIZE_RANKS.get(size, RESOLVER_CREATURE_SIZE_RANKS["medium"])
        return rank <= RESOLVER_CREATURE_SIZE_RANKS["huge"]

    @staticmethod
    def _cunning_strike_withdraw_destination(params: dict[str, Any]) -> str | None:
        destination = params.get("cunning_strike_withdraw_to_position_node_id") or params.get(
            "withdraw_to_position_node_id"
        )
        if destination is None:
            return None
        return str(destination)

    @staticmethod
    def _cunning_strike_stealth_attack_cover(params: dict[str, Any]) -> str | None:
        raw = (
            params.get("cunning_strike_stealth_attack_end_turn_cover")
            or params.get("stealth_attack_end_turn_cover")
            or params.get("supreme_sneak_end_turn_cover")
            or params.get("end_turn_cover")
        )
        if raw in (None, "", False):
            return None
        cover = re.sub(r"[^a-z0-9]+", "_", str(raw).casefold()).strip("_")
        return RESOLVER_SUPREME_SNEAK_COVER_ALIASES.get(cover)

    def _cunning_strike_withdraw_error(self, actor_id: str, destination: str) -> str | None:
        actor = self.state.entity_for_actor(actor_id)
        if not isinstance(actor, Combatant):
            return "Cunning Strike Withdraw requires a combatant"
        if self.state.encounter is None or self.state.encounter.tactical_graph is None:
            return "Cunning Strike Withdraw requires a combat tactical graph"
        if actor.position_node_id is None:
            return "Cunning Strike Withdraw requires a current position"
        graph = TacticalGraph.from_dict(self.state.encounter.tactical_graph)
        if destination not in graph.nodes:
            return "Cunning Strike Withdraw destination position does not exist"
        movement_cost = graph.shortest_distance(
            actor.position_node_id,
            destination,
            movement_cost=True,
        )
        if movement_cost is None:
            return "Cunning Strike Withdraw destination position is not reachable"
        movement_limit = self._effective_speed(actor) // 2
        if int(movement_cost) > movement_limit:
            return "Cunning Strike Withdraw movement cannot exceed half Speed"
        return None

    def _has_hide_invisible_condition(self, actor_id: str) -> bool:
        actor = self.state.entity_for_actor(actor_id)
        return any(
            effect.get("condition") in {"hidden", "invisible"}
            and effect.get("source_action_id") in RESOLVER_HIDE_ACTION_IDS
            for effect in self._status_effects_for(actor)
        )

    def _automation_nodes(self, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        flattened: list[dict[str, Any]] = []
        for node in nodes:
            flattened.append(node)
            if node.get("type") != "branch":
                continue
            for branch_name in ("if_true", "if_false"):
                branch = node.get(branch_name, [])
                if isinstance(branch, list):
                    flattened.extend(self._automation_nodes(branch))
        return flattened

    def _status_effects_for(self, actor: Character | Monster | Combatant) -> list[dict[str, Any]]:
        effects = list(getattr(actor, "status_effects", []))
        if isinstance(actor, Combatant) and actor.entity_id in self.state.characters:
            effects.extend(self.state.characters[actor.entity_id].status_effects)
        if isinstance(actor, Combatant) and actor.entity_id in self.state.monsters:
            effects.extend(self.state.monsters[actor.entity_id].status_effects)
        return effects

    def _action_owner(
        self,
        actor_id: str,
        actor: Character | Monster | Combatant,
    ) -> Character | Monster | Combatant:
        if isinstance(actor, Combatant) and actor.entity_id in self.state.characters:
            return self.state.characters[actor.entity_id]
        if isinstance(actor, Combatant) and actor.entity_id in self.state.monsters:
            return self.state.monsters[actor.entity_id]
        if actor_id in self.state.characters:
            return self.state.characters[actor_id]
        if actor_id in self.state.monsters:
            return self.state.monsters[actor_id]
        return actor

    def _resource_owner(
        self,
        actor_id: str,
        actor: Character | Monster | Combatant,
    ) -> Character | Monster | Combatant:
        if isinstance(actor, Combatant) and actor.entity_id in self.state.characters:
            return self.state.characters[actor.entity_id]
        if isinstance(actor, Combatant) and actor.entity_id in self.state.monsters:
            return self.state.monsters[actor.entity_id]
        if actor_id in self.state.characters:
            return self.state.characters[actor_id]
        if actor_id in self.state.monsters:
            return self.state.monsters[actor_id]
        return actor

    def _effective_speed(self, actor: Character | Monster | Combatant) -> int:
        effects = list(getattr(actor, "status_effects", []))
        base_speed = int(getattr(actor, "speed_ft", 30))
        if isinstance(actor, Combatant) and actor.entity_id in self.state.characters:
            backing_character = self.state.characters[actor.entity_id]
            effects.extend(backing_character.status_effects)
            base_speed += class_feature_speed_bonus(backing_character)
        elif isinstance(actor, Character):
            base_speed += class_feature_speed_bonus(actor)
        if isinstance(actor, Combatant) and actor.entity_id in self.state.monsters:
            effects.extend(self.state.monsters[actor.entity_id].status_effects)
        return effective_speed(base_speed, effects)

    def _check_targets(
        self,
        draft: PlayerActionDraft,
        action: ActionDefinition,
    ) -> ResolverResult | None:
        policy = action.target_policy
        min_targets = int(policy.get("min", 0))
        max_targets = self._effective_max_targets(draft, action)
        if len(draft.target_ids) < min_targets:
            return ResolverResult(
                status="rejected", reason="not enough targets", action_id=action.id
            )
        if max_targets is not None and len(draft.target_ids) > max_targets:
            return ResolverResult(status="rejected", reason="too many targets", action_id=action.id)
        if bool(policy.get("exclude_self", False)):
            actor_aliases = self._entity_aliases(draft.actor_id)
            if any(target_id in actor_aliases for target_id in draft.target_ids):
                return ResolverResult(
                    status="rejected",
                    reason="target cannot be self",
                    action_id=action.id,
                )
        creature_types = policy.get("creature_types")
        if isinstance(creature_types, list) and creature_types:
            allowed = {str(creature_type).lower() for creature_type in creature_types}
            for target_id in draft.target_ids:
                try:
                    target_entity = self.state.entity_for_actor(target_id)
                except KeyError:
                    continue
                if self._creature_type_for(target_entity).lower() not in allowed:
                    expected = ", ".join(sorted(allowed))
                    return ResolverResult(
                        status="rejected",
                        reason=f"target must be {expected}",
                        action_id=action.id,
                    )
        if self.state.encounter is None:
            return None
        actor_combatant = self.state.encounter.combatants.get(draft.actor_id)
        if actor_combatant is None:
            return None
        harmful = bool(policy.get("harmful", False)) and not self._quivering_palm_harmless_release(
            draft,
            action,
        )
        allied_targets = []
        for target_id in draft.target_ids:
            target = self.state.encounter.combatants.get(target_id)
            if target is not None and target.side == actor_combatant.side:
                allied_targets.append(target_id)
        if harmful and allied_targets:
            has_pc_target = any(target_id.startswith("pc") for target_id in allied_targets)
            is_area_friendly_fire = self._is_area_friendly_fire(
                draft,
                action,
                allied_targets=allied_targets,
            )
            if has_pc_target and not self.state.config.pvp_enabled and not is_area_friendly_fire:
                return ResolverResult(
                    status="rejected", reason="pvp is disabled", action_id=action.id
                )
            mode = (
                self.state.config.friendly_fire
                if actor_combatant.side == "party"
                else action.friendly_fire_policy
            )
            if mode == "off":
                return ResolverResult(
                    status="rejected", reason="friendly fire is disabled", action_id=action.id
                )
            if mode == "confirm":
                return ResolverResult(
                    status="confirm_required",
                    reason="friendly fire confirmation required",
                    action_id=action.id,
                    confirm_required=True,
                )
        return None

    def _effective_max_targets(
        self,
        draft: PlayerActionDraft,
        action: ActionDefinition,
    ) -> int | None:
        max_targets = action.target_policy.get("max")
        if max_targets is None:
            return None
        maximum = int(max_targets)
        per_slot = action.target_policy.get("max_targets_per_slot_above")
        if per_slot is None:
            return maximum
        base_slot = action.target_policy.get("base_spell_slot_level", action.cost.spell_slot_level)
        if not isinstance(base_slot, int) or isinstance(base_slot, bool) or base_slot < 1:
            return maximum
        try:
            slot_level = self._spell_slot_level_to_spend(draft, action)
        except ValueError:
            slot_level = base_slot
        return maximum + max(0, slot_level - base_slot) * int(per_slot)

    def _check_self_only_targets(
        self,
        draft: PlayerActionDraft,
        action: ActionDefinition,
    ) -> ResolverResult | None:
        if action.properties.get("self_only") is not True:
            return None
        actor_aliases = self._entity_aliases(draft.actor_id)
        for target_id in draft.target_ids:
            if not (actor_aliases & self._entity_aliases(target_id)):
                return ResolverResult(
                    status="rejected",
                    reason="target must be self",
                    action_id=action.id,
                )
        return None

    def _check_requires_self_target(
        self,
        draft: PlayerActionDraft,
        action: ActionDefinition,
    ) -> ResolverResult | None:
        if action.properties.get("requires_self_target") is not True:
            return None
        actor_aliases = self._entity_aliases(draft.actor_id)
        if not any(
            actor_aliases & self._entity_aliases(target_id) for target_id in draft.target_ids
        ):
            return ResolverResult(
                status="rejected",
                reason="target list must include self",
                action_id=action.id,
            )
        return None

    def _check_willing_targets(
        self,
        draft: PlayerActionDraft,
        action: ActionDefinition,
    ) -> ResolverResult | None:
        if action.properties.get("requires_willing_target") is not True:
            return None
        for target_id in draft.target_ids:
            if not self._target_willing(draft.params, target_id):
                return ResolverResult(
                    status="rejected",
                    reason="target must be willing",
                    action_id=action.id,
                )
        return None

    @staticmethod
    def _target_willing(params: dict[str, Any], target_id: str) -> bool:
        target_willing = params.get("target_willing")
        if target_willing is True:
            return True
        if isinstance(target_willing, dict):
            return target_willing.get(target_id) is True
        willing_targets = params.get("willing_target_ids")
        if isinstance(willing_targets, list):
            return target_id in {str(candidate) for candidate in willing_targets}
        return False

    def _check_pact_of_blade_weapon_selection(
        self,
        draft: PlayerActionDraft,
        action: ActionDefinition,
    ) -> ResolverResult | None:
        if action.id != RESOLVER_PACT_OF_BLADE_WEAPON_ACTION_ID:
            return None
        selected = draft.params.get("pact_weapon_action_id")
        if selected is None:
            return ResolverResult(
                status="rejected",
                reason="missing required parameter pact_weapon_action_id",
                action_id=action.id,
            )
        if isinstance(selected, (dict, list)):
            return ResolverResult(
                status="rejected",
                reason="parameter pact_weapon_action_id must be a scalar",
                action_id=action.id,
            )
        selected_action_id = str(selected)
        if not selected_action_id:
            return ResolverResult(
                status="rejected",
                reason="parameter pact_weapon_action_id must be non-empty",
                action_id=action.id,
            )
        if selected_action_id not in WARLOCK_PACT_OF_BLADE_WEAPON_ACTION_IDS:
            return ResolverResult(
                status="rejected",
                reason="Pact of the Blade weapon must be an implemented SRD melee weapon",
                action_id=action.id,
            )
        return None

    def _check_robe_of_useful_items_patch(
        self,
        draft: PlayerActionDraft,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> ResolverResult | None:
        owner = self._resource_owner(draft.actor_id, actor)
        if action.properties.get("robe_of_useful_items_initialize") is True:
            initialized = (
                int(owner.resources.get(RESOLVER_ROBE_OF_USEFUL_ITEMS_INITIALIZED_RESOURCE, 0))
                if isinstance(owner, Character)
                else 0
            )
            if initialized > 0:
                return ResolverResult(
                    status="rejected",
                    reason="Robe of Useful Items patches are already initialized",
                    action_id=action.id,
                )
            return None
        if action.properties.get("robe_of_useful_items_detach_patch") is not True:
            return None
        if not isinstance(owner, Character):
            return ResolverResult(
                status="rejected",
                reason="Robe of Useful Items requires a character owner",
                action_id=action.id,
            )
        patch_param = str(action.properties.get("patch_param", "robe_of_useful_items_patch"))
        selected = draft.params.get(patch_param)
        if selected is None:
            return ResolverResult(
                status="rejected",
                reason=f"missing required parameter {patch_param}",
                action_id=action.id,
            )
        if isinstance(selected, (dict, list)):
            return ResolverResult(
                status="rejected",
                reason=f"parameter {patch_param} must be a scalar",
                action_id=action.id,
            )
        patch_key = str(selected).lower()
        allowed = action.properties.get("robe_of_useful_items_patch_keys", [])
        allowed_keys = {str(key) for key in allowed} if isinstance(allowed, list) else set()
        if patch_key not in allowed_keys:
            return ResolverResult(
                status="rejected",
                reason="Robe of Useful Items patch is not in the SRD patch table",
                action_id=action.id,
            )
        resource = f"{RESOLVER_ROBE_OF_USEFUL_ITEMS_PATCH_PREFIX}{patch_key}"
        if int(owner.resources.get(resource, 0)) <= 0:
            return ResolverResult(
                status="rejected",
                reason=f"Robe of Useful Items patch {patch_key} is unavailable",
                action_id=action.id,
            )
        return None

    def _check_thirsting_blade_extra_attack(
        self,
        draft: PlayerActionDraft,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> ResolverResult | None:
        if not self._uses_thirsting_blade_extra_attack(draft):
            return None
        owner = self._resource_owner(draft.actor_id, actor)
        if not isinstance(owner, Character) or not has_warlock_thirsting_blade(owner):
            return ResolverResult(
                status="rejected",
                reason="Thirsting Blade extra attack requires Warlock 5 with Pact of the Blade",
                action_id=action.id,
            )
        if action.action_type != "weapon_attack" or not self._has_active_pact_weapon_action(
            actor,
            action,
        ):
            return ResolverResult(
                status="rejected",
                reason="Thirsting Blade extra attack requires the selected pact weapon",
                action_id=action.id,
            )
        if not self._has_thirsting_blade_pact_weapon_attack_this_turn(actor, action.id):
            return ResolverResult(
                status="rejected",
                reason="Thirsting Blade extra attack requires a prior pact weapon attack this turn",
                action_id=action.id,
            )
        if self._has_thirsting_blade_extra_attack_used(actor):
            return ResolverResult(
                status="rejected",
                reason="Thirsting Blade extra attack already used this turn",
                action_id=action.id,
            )
        return None

    @staticmethod
    def _uses_thirsting_blade_extra_attack(draft: PlayerActionDraft) -> bool:
        return (
            draft.params.get("use_thirsting_blade_extra_attack") is True
            or draft.params.get("thirsting_blade_extra_attack") is True
        )

    def _has_thirsting_blade_pact_weapon_attack_this_turn(
        self,
        actor: Character | Monster | Combatant,
        action_id: str,
    ) -> bool:
        return any(
            effect.get("condition") == RESOLVER_THIRSTING_BLADE_PACT_WEAPON_ATTACK_CONDITION
            and effect.get("audit", {}).get("pact_weapon_action_id") == action_id
            for effect in self._status_effects_for(actor)
        )

    def _has_thirsting_blade_extra_attack_used(
        self,
        actor: Character | Monster | Combatant,
    ) -> bool:
        return any(
            effect.get("condition") == RESOLVER_THIRSTING_BLADE_EXTRA_ATTACK_USED_CONDITION
            and effect.get("source_action_id") == RESOLVER_THIRSTING_BLADE_ACTION_ID
            for effect in self._status_effects_for(actor)
        )

    def _check_eldritch_smite(
        self,
        draft: PlayerActionDraft,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> ResolverResult | None:
        if not self._uses_eldritch_smite(draft):
            return None
        owner = self._resource_owner(draft.actor_id, actor)
        if not isinstance(owner, Character) or not has_warlock_eldritch_smite(owner):
            return ResolverResult(
                status="rejected",
                reason="Eldritch Smite requires Warlock 5 with Pact of the Blade",
                action_id=action.id,
            )
        if action.action_type != "weapon_attack" or not self._is_melee_weapon_attack_action(action):
            return ResolverResult(
                status="rejected",
                reason="Eldritch Smite requires a pact weapon attack",
                action_id=action.id,
            )
        if not self._has_active_pact_weapon_action(actor, action):
            return ResolverResult(
                status="rejected",
                reason="Eldritch Smite requires the selected pact weapon",
                action_id=action.id,
            )
        if self._has_eldritch_smite_used(actor):
            return ResolverResult(
                status="rejected",
                reason="Eldritch Smite already used this turn",
                action_id=action.id,
            )
        pact_slot_level = self._pact_magic_slot_level(owner)
        if pact_slot_level is None or owner.spell_slots.get(str(pact_slot_level), 0) <= 0:
            return ResolverResult(
                status="rejected",
                reason="insufficient Pact Magic spell slot",
                action_id=action.id,
            )
        if self._eldritch_smite_prone_requested(draft):
            target_id = self._eldritch_smite_target_id(draft)
            if target_id is None:
                return ResolverResult(
                    status="rejected",
                    reason="Eldritch Smite requires a target",
                    action_id=action.id,
                )
            try:
                huge_or_smaller = self._target_huge_or_smaller(target_id)
            except KeyError:
                return ResolverResult(
                    status="rejected",
                    reason=f"unknown target {target_id}",
                    action_id=action.id,
                )
            if not huge_or_smaller:
                return ResolverResult(
                    status="rejected",
                    reason="Eldritch Smite Prone target must be Huge or smaller",
                    action_id=action.id,
                )
        return None

    @staticmethod
    def _uses_eldritch_smite(draft: PlayerActionDraft) -> bool:
        return (
            draft.params.get("use_eldritch_smite") is True
            or draft.params.get("eldritch_smite") is True
        )

    @staticmethod
    def _eldritch_smite_prone_requested(draft: PlayerActionDraft) -> bool:
        return (
            draft.params.get("eldritch_smite_prone") is True
            or draft.params.get("eldritch_smite_give_prone") is True
        )

    @staticmethod
    def _eldritch_smite_target_id(draft: PlayerActionDraft) -> str | None:
        selected = draft.params.get("eldritch_smite_target_id")
        if selected not in (None, "", False):
            return str(selected)
        if len(draft.target_ids) == 1:
            return str(draft.target_ids[0])
        return None

    @staticmethod
    def _pact_magic_slot_level(actor: Character) -> int | None:
        pact_slots = warlock_pact_slot_maxima_for_class_levels(actor.class_levels)
        if not pact_slots:
            return None
        return max(int(level) for level in pact_slots)

    def _has_eldritch_smite_used(
        self,
        actor: Character | Monster | Combatant,
    ) -> bool:
        return any(
            effect.get("condition") == RESOLVER_ELDRITCH_SMITE_USED_CONDITION
            and effect.get("source_action_id") == RESOLVER_ELDRITCH_SMITE_ACTION_ID
            for effect in self._status_effects_for(actor)
        )

    @staticmethod
    def _is_melee_weapon_attack_action(action: ActionDefinition) -> bool:
        if action.action_type != "weapon_attack":
            return False
        normal_range = action.range.get("normal_ft")
        if normal_range is None:
            return False
        return int(normal_range) <= 10

    def _has_active_pact_weapon_action(
        self,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> bool:
        if action.action_type != "weapon_attack":
            return False
        for effect in self._status_effects_for(actor):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            if modifiers.get("pact_weapon") is not True:
                continue
            if str(modifiers.get("pact_weapon_action_id", "")) == action.id:
                return True
        return False

    def _is_area_friendly_fire(
        self,
        draft: PlayerActionDraft,
        action: ActionDefinition,
        *,
        allied_targets: list[str],
    ) -> bool:
        if "shape" not in action.range and "area_targets" not in draft.params:
            return False
        non_allied_targets = set(draft.target_ids) - set(allied_targets)
        return bool(non_allied_targets)

    def _check_range(
        self,
        draft: PlayerActionDraft,
        action: ActionDefinition,
    ) -> ResolverResult | None:
        if draft.params.get("ignore_range") is True:
            return None
        if self.state.encounter is None or not draft.target_ids:
            return None
        graph_data = self.state.encounter.tactical_graph
        if not graph_data:
            return None
        graph = TacticalGraph.from_dict(graph_data)
        actor = self.state.encounter.combatants.get(draft.actor_id)
        if actor is None or actor.position_node_id is None:
            return None
        max_range = action.range.get("normal_ft")
        if max_range is None:
            return None
        effective_range = self._effective_action_range_ft(
            actor_id=draft.actor_id,
            actor=actor,
            action=action,
            base_range=int(max_range),
        )
        for target_id in draft.target_ids:
            target = self.state.encounter.combatants.get(target_id)
            if target is None or target.position_node_id is None:
                continue
            distance = graph.shortest_distance(actor.position_node_id, target.position_node_id)
            if distance is None or distance > effective_range:
                return ResolverResult(
                    status="rejected", reason="target out of range", action_id=action.id
                )
            if action.range.get("line_of_sight") is not False and not graph.has_line_of_sight(
                actor.position_node_id,
                target.position_node_id,
            ):
                return ResolverResult(
                    status="rejected", reason="line of sight blocked", action_id=action.id
                )
        return None

    def _effective_action_range_ft(
        self,
        *,
        actor_id: str,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
        base_range: int,
    ) -> int:
        if action.action_type != "spell":
            return base_range
        owner = self._resource_owner(actor_id, actor)
        if not isinstance(owner, Character):
            return base_range
        spell_id = action.properties.get("spell_definition_id")
        return base_range + warlock_eldritch_spear_range_bonus(
            owner,
            spell_id=str(spell_id) if isinstance(spell_id, str) else None,
        )

    def _check_preserve_life(
        self,
        draft: PlayerActionDraft,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> ResolverResult | None:
        if self._preserve_life_node(action) is None:
            return None
        error = self._preserve_life_error(draft, actor, action)
        if error is None:
            return None
        return ResolverResult(status="rejected", reason=error, action_id=action.id)

    def _preserve_life_error(
        self,
        draft: PlayerActionDraft,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> str | None:
        node = self._preserve_life_node(action)
        if node is None:
            return None
        param_name = str(node.get("points_param", "preserve_life_points"))
        try:
            allocations = self._parse_preserve_life_points(
                draft.params.get(param_name),
                draft.target_ids,
                param_name,
            )
        except ValueError as exc:
            return str(exc)
        owner = self._resource_owner(draft.actor_id, actor)
        if not isinstance(owner, Character):
            return "Preserve Life requires a character"
        pool = preserve_life_healing_pool(owner)
        if pool <= 0:
            return "Preserve Life requires Cleric Life Domain level 3"
        if sum(allocations.values()) > pool:
            return "Preserve Life points exceed available healing pool"
        for target_id, amount in allocations.items():
            try:
                target = self.state.entity_for_actor(target_id)
            except KeyError:
                return f"unknown target {target_id}"
            hp_current = int(getattr(target, "hp_current"))
            hp_max = int(getattr(target, "hp_max"))
            if not is_bloodied(hp_current=hp_current, hp_max=hp_max):
                return "Preserve Life target must be Bloodied"
            if amount > max(0, bloodied_hp_cap(hp_max) - hp_current):
                return "Preserve Life cannot heal a target above half HP"
        return None

    def _parse_preserve_life_points(
        self,
        raw_points: Any,
        targets: list[str],
        param_name: str,
    ) -> dict[str, int]:
        if raw_points is None:
            raise ValueError(f"missing required parameter {param_name}")
        if isinstance(raw_points, int) and not isinstance(raw_points, bool) and len(targets) == 1:
            allocations = {targets[0]: raw_points}
        elif isinstance(raw_points, dict):
            allocations = {
                str(target_id): self._positive_int_value(value, param_name)
                for target_id, value in raw_points.items()
            }
        else:
            raise ValueError(f"parameter {param_name} must be a target-to-points map")
        if set(allocations) != set(targets):
            raise ValueError("Preserve Life points must be assigned to exactly the targets")
        for amount in allocations.values():
            if amount <= 0:
                raise ValueError("Preserve Life points must be positive")
        return allocations

    @staticmethod
    def _positive_int_value(value: Any, param_name: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"parameter {param_name} must contain positive integers")
        try:
            amount = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"parameter {param_name} must contain positive integers") from exc
        if amount <= 0:
            raise ValueError(f"parameter {param_name} must contain positive integers")
        return amount

    def _preserve_life_node(self, action: ActionDefinition) -> dict[str, Any] | None:
        return next(
            (
                node
                for node in self._automation_nodes(action.automation)
                if node.get("type") == "preserve_life_healing"
            ),
            None,
        )

    def _entity_aliases(self, entity_id: str) -> set[str]:
        aliases = {entity_id}
        try:
            entity = self.state.entity_for_actor(entity_id)
        except KeyError:
            return aliases
        entity_base_id = getattr(entity, "id", None)
        if isinstance(entity_base_id, str):
            aliases.add(entity_base_id)
        entity_ref = getattr(entity, "entity_id", None)
        if isinstance(entity_ref, str):
            aliases.add(entity_ref)
        return aliases

    def _creature_type_for(self, entity: Character | Monster | Combatant) -> str:
        if isinstance(entity, Combatant):
            if entity.entity_id in self.state.monsters:
                return str(self.state.monsters[entity.entity_id].creature_type)
            if entity.entity_id in self.state.characters:
                return "humanoid"
        if isinstance(entity, Character):
            return "humanoid"
        return str(getattr(entity, "creature_type", "humanoid"))


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

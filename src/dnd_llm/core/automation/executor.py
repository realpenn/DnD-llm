from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..dice import RollResult, RollService
from ..economy import EconomyTracker
from ..models import Character, Combatant, GameState, Monster
from ..persistence import AuditLog
from ..positioning import TacticalGraph
from ..rules.checks import charisma_check_minimum_d20_adjustment, d20_expression
from ..rules.class_features import (
    DARK_ONES_OWN_LUCK_RESOURCE,
    ELUSIVE_ACTION_ID,
    FOCUS_POINTS_RESOURCE,
    INDOMITABLE_MIGHT_ACTION_ID,
    INDOMITABLE_RESOURCE,
    PERSISTENT_RAGE_ACTION_ID,
    PRIMAL_KNOWLEDGE_SKILLS,
    RELENTLESS_RAGE_ACTION_ID,
    RELENTLESS_RAGE_USES_SINCE_REST_RESOURCE,
    RELIABLE_TALENT_ACTION_ID,
    RELIABLE_TALENT_D20_FLOOR,
    STROKE_OF_LUCK_ACTION_ID,
    STROKE_OF_LUCK_D20,
    STROKE_OF_LUCK_RESOURCE,
    WARLOCK_PACT_OF_BLADE_WEAPON_ACTION_IDS,
    aura_of_devotion_applies,
    aura_of_protection_radius_ft,
    aura_of_protection_saving_throw_bonus,
    barbarian_rage_damage_bonus,
    barbarian_unarmored_defense_armor_class,
    blessed_healer_self_healing,
    bloodied_hp_cap,
    class_feature_speed_bonus,
    cleric_improved_blessed_strikes_temp_hp,
    cleric_potent_spellcasting_bonus,
    cleric_thaumaturge_check_bonus,
    dark_ones_blessing_temp_hp,
    disciple_of_life_healing_bonus,
    draconic_elemental_affinity_damage_bonus,
    draconic_elemental_affinity_damage_type,
    draconic_resilience_armor_class,
    druid_magician_check_bonus,
    druid_natures_ward_resistance_type,
    eldritch_master_applies,
    evasion_applies,
    has_barbarian_berserker_feature,
    has_barbarian_feature,
    has_cleric_blessed_strikes_divine_strike,
    has_cleric_blessed_strikes_potent_spellcasting,
    has_cleric_improved_blessed_strikes,
    has_colossus_slayer,
    has_condition,
    has_druid_circle_of_the_land_feature,
    has_escape_the_horde,
    has_fighter_champion_feature,
    has_fighter_feature,
    has_horde_breaker,
    has_monk_feature,
    has_monk_open_hand_feature,
    has_multiattack_defense,
    has_paladin_feature,
    has_precise_hunter,
    has_ranger_hunter_feature,
    has_relentless_hunter,
    has_relentless_rage,
    has_rogue_thief_feature,
    has_superior_hunters_defense,
    has_superior_hunters_prey,
    has_warlock_eldritch_mind,
    has_warlock_eldritch_smite,
    has_warlock_fiend_feature,
    has_warlock_investment_of_chain_master,
    has_warlock_repelling_blast,
    has_warlock_thirsting_blade,
    has_wizard_evocation_feature,
    indomitable_might_total_floor,
    is_bloodied,
    is_wearing_armor,
    is_wielding_shield,
    monk_disciplined_survivor_applies,
    monk_forgoing_food_drink_exhaustion_immunity,
    monk_martial_arts_die,
    monk_slow_fall_damage_reduction,
    monk_unarmored_defense_armor_class,
    persistent_rage_applies,
    preserve_life_healing_pool,
    ranger_hunters_mark_damage_dice,
    relentless_rage_dc,
    relentless_rage_success_hp,
    reliable_talent_d20_adjustment,
    remarkable_athlete_applies_to_check,
    rogue_elusive_applies,
    rogue_stroke_of_luck_applies,
    saving_throw_proficiency_sources,
    supreme_healing_applies,
    warlock_agonizing_blast_bonus,
    warlock_fiendish_resilience_damage_type,
)
from ..rules.conditions import (
    ability_score_set_sources,
    apply_exhaustion,
    effective_ability_modifier,
    effective_speed,
    exhaustion_d20_penalty,
    exhaustion_level,
    remove_condition,
)
from ..rules.difficulty import resolve_dc
from ..rules.rests import resource_maxima
from ..rules.rituals import ritual_casting_eligibility
from ..rules.spell_slots import warlock_pact_slot_maxima_for_class_levels
from .definitions import ActionDefinition
from .effects import EffectInstance
from .nodes import STATE_CHANGING_NODE_TYPES

ATTACK_ACTION_TYPES = {"weapon_attack", "monster_attack", "unarmed_attack"}
CUNNING_STRIKE_EFFECTS = {"poison", "stealth_attack", "trip", "withdraw"}
MAX_CUNNING_STRIKE_EFFECTS = 2
BRUTAL_STRIKE_EFFECTS = {
    "forceful_blow",
    "hamstring_blow",
    "staggering_blow",
    "sundering_blow",
}
IMPROVED_BRUTAL_STRIKE_EFFECTS = {"staggering_blow", "sundering_blow"}
IMPROVED_CUNNING_STRIKE_ACTION_ID = "srd.improved_cunning_strike"
SUPREME_SNEAK_ACTION_ID = "srd.supreme_sneak"
ESCAPE_THE_HORDE_ACTION_ID = "srd.escape_the_horde"
MULTIATTACK_DEFENSE_ACTION_ID = "srd.multiattack_defense"
HIDE_ACTION_IDS = frozenset({"srd.hide", "srd.cunning_action_hide"})
SUPREME_SNEAK_COVER_ALIASES = {
    "3_4": "three_quarters",
    "3_4_cover": "three_quarters",
    "three_quarters": "three_quarters",
    "three_quarters_cover": "three_quarters",
    "total": "total",
    "total_cover": "total",
}
SUPREME_SNEAK_COVERS = frozenset({"three_quarters", "total"})
OPEN_HAND_TECHNIQUE_EFFECTS = {"addle", "push", "topple"}
FOCUS_RESOURCE_ID = "srd.resource.focus_points"
CHANNEL_DIVINITY_RESOURCE_ID = "srd.resource.channel_divinity"
UNCANNY_DODGE_ACTION_ID = "srd.uncanny_dodge"
RAGE_ACTION_ID = "srd.rage"
ACTION_SURGE_ACTION_ID = "srd.action_surge"
ACTION_SURGE_USED_CONDITION = "action_surge_used"
INSTINCTIVE_POUNCE_ACTION_ID = "srd.instinctive_pounce"
BRUTAL_STRIKE_ACTION_ID = "srd.brutal_strike"
IMPROVED_BRUTAL_STRIKE_ACTION_ID = "srd.improved_brutal_strike"
MINDLESS_RAGE_ACTION_ID = "srd.mindless_rage"
MINDLESS_RAGE_CONDITION_IMMUNITIES = ("charmed", "frightened")
BLESSED_HEALER_ACTION_ID = "srd.blessed_healer"
CLERIC_BLESSED_STRIKES_ACTION_ID = "srd.blessed_strikes"
CLERIC_BLESSED_STRIKES_DIVINE_STRIKE_ACTION_ID = "srd.blessed_strikes_divine_strike"
CLERIC_BLESSED_STRIKES_DIVINE_STRIKE_USED_CONDITION = "blessed_strikes_divine_strike_used"
CLERIC_BLESSED_STRIKES_POTENT_SPELLCASTING_ACTION_ID = (
    "srd.blessed_strikes_potent_spellcasting"
)
CLERIC_IMPROVED_BLESSED_STRIKES_ACTION_ID = "srd.improved_blessed_strikes"
SUPREME_HEALING_ACTION_ID = "srd.supreme_healing"
AURA_OF_PROTECTION_ACTION_ID = "srd.aura_of_protection"
AURA_OF_COURAGE_ACTION_ID = "srd.aura_of_courage"
AURA_OF_DEVOTION_ACTION_ID = "srd.aura_of_devotion"
RADIANT_STRIKES_ACTION_ID = "srd.radiant_strikes"
CONJURE_MINOR_ELEMENTALS_ACTION_ID = "srd.conjure_minor_elementals"
CONJURE_MINOR_ELEMENTALS_EFFECT_TYPE = "conjure_minor_elementals_emanation"
CONJURE_MINOR_ELEMENTALS_DAMAGE_TYPE_PARAM = "conjure_minor_elementals_damage_type"
CONJURE_MINOR_ELEMENTALS_DAMAGE_TYPES = frozenset({"acid", "cold", "fire", "lightning"})
CONJURE_MINOR_ELEMENTALS_RADIUS_FT = 15
RESTORING_TOUCH_ALLOWED_CONDITIONS = frozenset(
    {"blinded", "charmed", "deafened", "frightened", "paralyzed", "stunned"}
)
RESTORING_TOUCH_CONDITION_POINT_COST = 5
DARK_ONES_OWN_LUCK_ACTION_ID = "srd.dark_ones_own_luck"
INDOMITABLE_ACTION_ID = "srd.indomitable"
DISCIPLINED_SURVIVOR_ACTION_ID = "srd.disciplined_survivor"
COUNTERCHARM_ACTION_ID = "srd.countercharm"
COUNTERCHARM_CONDITIONS = frozenset({"charmed", "frightened"})
COUNTERCHARM_RANGE_FT = 30
STUDIED_ATTACKS_ACTION_ID = "srd.studied_attacks"
STUDIED_ATTACKS_CONDITION = "studied_attacks"
PRECISE_HUNTER_ACTION_ID = "srd.precise_hunter"
FOE_SLAYER_ACTION_ID = "srd.foe_slayer"
DEFLECT_ATTACKS_ACTION_ID = "srd.deflect_attacks"
EVASION_ACTION_ID = "srd.evasion"
CUTTING_WORDS_ACTION_ID = "srd.cutting_words"
LANDS_AID_ACTION_ID = "srd.lands_aid"
NATURES_SANCTUARY_ACTION_ID = "srd.natures_sanctuary"
NATURES_SANCTUARY_MOVE_ACTION_ID = "srd.natures_sanctuary_move"
SACRED_WEAPON_ACTION_ID = "srd.sacred_weapon"
STUNNING_STRIKE_ACTION_ID = "srd.stunning_strike"
STUNNING_STRIKE_SLOWED_CONDITION = "stunning_strike_slowed"
FLURRY_OF_BLOWS_ACTION_ID = "srd.flurry_of_blows"
STEP_OF_THE_WIND_ACTION_ID = "srd.step_of_the_wind"
STEP_OF_THE_WIND_FOCUS_ACTION_ID = "srd.step_of_the_wind_focus"
STEP_OF_THE_WIND_ACTION_IDS = frozenset(
    {STEP_OF_THE_WIND_ACTION_ID, STEP_OF_THE_WIND_FOCUS_ACTION_ID}
)
FLEET_STEP_ACTION_ID = "srd.fleet_step"
FLEET_STEP_CONDITION = "fleet_step_available"
QUIVERING_PALM_ACTION_ID = "srd.quivering_palm"
QUIVERING_PALM_RELEASE_ACTION_ID = "srd.quivering_palm_release"
QUIVERING_PALM_CONDITION = "quivering_palm"
HEIGHTENED_FOCUS_COMPANION_CONDITION = "heightened_focus_step_of_the_wind_companion"
OPEN_HAND_TECHNIQUE_ACTION_ID = "srd.open_hand_technique"
REPELLING_BLAST_ACTION_ID = "srd.repelling_blast"
FAST_HANDS_SLEIGHT_OF_HAND_ACTION_ID = "srd.fast_hands_sleight_of_hand"
HUNTERS_LORE_ACTION_ID = "srd.hunters_lore"
FAVORED_ENEMY_HUNTERS_MARK_ACTION_ID = "srd.favored_enemy_hunters_mark"
RELENTLESS_HUNTER_ACTION_ID = "srd.relentless_hunter"
PACT_OF_BLADE_WEAPON_ACTION_ID = "srd.pact_of_the_blade_weapon"
PACT_OF_CHAIN_FIND_FAMILIAR_ACTION_ID = "srd.pact_of_the_chain_find_familiar"
THIRSTING_BLADE_ACTION_ID = "srd.thirsting_blade"
ELDRITCH_SMITE_ACTION_ID = "srd.eldritch_smite"
COLOSSUS_SLAYER_ACTION_ID = "srd.hunters_prey_colossus_slayer"
HORDE_BREAKER_ACTION_ID = "srd.hunters_prey_horde_breaker"
HORDE_BREAKER_USED_CONDITION = "horde_breaker_used"
SUPERIOR_HUNTERS_PREY_ACTION_ID = "srd.superior_hunters_prey"
SUPERIOR_HUNTERS_PREY_USED_CONDITION = "superior_hunters_prey_used"
SUPERIOR_HUNTERS_DEFENSE_ACTION_ID = "srd.superior_hunters_defense"
SUPERIOR_HUNTERS_DEFENSE_CONDITION = "superior_hunters_defense"
WEAPON_ATTACK_TARGET_THIS_TURN_CONDITION = "weapon_attack_target_this_turn"
THIRSTING_BLADE_PACT_WEAPON_ATTACK_CONDITION = "thirsting_blade_pact_weapon_attack_this_turn"
ROD_OF_ABSORPTION_ITEM_ID = "srd.rod_of_absorption"
ROD_OF_ABSORPTION_STORED_LEVELS_RESOURCE = "srd.rod_of_absorption.stored_levels"
ROD_OF_ABSORPTION_LIFETIME_ABSORBED_RESOURCE = "srd.rod_of_absorption.lifetime_absorbed_levels"
ROD_OF_ABSORPTION_INITIALIZED_RESOURCE = "srd.rod_of_absorption.initialized"
ROD_OF_ABSORPTION_LIFETIME_CAP = 50
ROD_OF_ABSORPTION_MAX_CREATED_SLOT_LEVEL = 5
ROD_OF_ALERTNESS_ITEM_ID = "srd.rod_of_alertness"
ROD_OF_ALERTNESS_PROTECTIVE_AURA_USED_RESOURCE = (
    "srd.rod_of_alertness.protective_aura_used_until_next_dawn"
)
ROBE_OF_USEFUL_ITEMS_PATCH_PREFIX = "srd.robe_of_useful_items.patch."
ROBE_OF_USEFUL_ITEMS_INITIALIZED_RESOURCE = "srd.robe_of_useful_items.initialized"
FOOD_DRINK_EXHAUSTION_HAZARD_IDS = frozenset({"srd.dehydration", "srd.malnutrition"})
THIRSTING_BLADE_EXTRA_ATTACK_USED_CONDITION = "thirsting_blade_extra_attack_used"
ELDRITCH_SMITE_USED_CONDITION = "eldritch_smite_used"
SLOW_FALL_ACTION_ID = "srd.slow_fall"
OIL_OF_SHARPNESS_ACTION_ID = "srd.apply_oil_of_sharpness"
OIL_OF_ETHEREALNESS_ACTION_ID = "srd.apply_oil_of_etherealness"
APPLY_OIL_OF_SLIPPERINESS_ACTION_ID = "srd.apply_oil_of_slipperiness"
FALLING_HAZARD_ACTION_IDS = {"srd.falling_10ft", "srd.falling_30ft"}
BASIC_WEAPON_DAMAGE_TYPES = {"bludgeoning", "piercing", "slashing"}
POISONERS_KIT_ITEM_ID = "srd.poisoners_kit"
THIEVES_TOOLS_ITEM_ID = "srd.thieves_tools"
CREATURE_SIZE_RANKS = {
    "tiny": 1,
    "small": 2,
    "medium": 3,
    "medium_or_small": 3,
    "large": 4,
    "huge": 5,
    "gargantuan": 6,
}
GREATER_RESTORATION_CHOICES = {
    "exhaustion",
    "charmed_or_petrified",
    "curse",
    "ability_score_reduction",
    "hp_max_reduction",
    "contact_other_plane_incapacitation",
}


class AutomationError(RuntimeError):
    pass


ACTION_BLOCKING_CONDITIONS = {
    "incapacitated",
    "paralyzed",
    "petrified",
    "stunned",
    "unconscious",
}
MOVEMENT_BLOCKING_CONDITIONS = ACTION_BLOCKING_CONDITIONS | {
    "grappled",
    "restrained",
}
SPELLCASTING_ABILITIES = {
    "bard": "cha",
    "cleric": "wis",
    "druid": "wis",
    "paladin": "cha",
    "ranger": "wis",
    "sorcerer": "cha",
    "warlock": "cha",
    "wizard": "int",
}


def _advantage_value(value: Any) -> str | None:
    return value if value in {"advantage", "disadvantage"} else None


def _merge_advantage(*values: str | None) -> str | None:
    has_advantage = any(value == "advantage" for value in values)
    has_disadvantage = any(value == "disadvantage" for value in values)
    if has_advantage and has_disadvantage:
        return None
    if has_advantage:
        return "advantage"
    if has_disadvantage:
        return "disadvantage"
    return None


def _proficiency_key(raw: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", raw.casefold()).strip("_")
    return re.sub(r"_+", "_", key)


def _skill_advantage_entry_matches(
    entry: Any,
    *,
    ability: str,
    skill: str | None,
    contexts: set[str] | None = None,
) -> bool:
    if skill is None:
        return False
    if isinstance(entry, str):
        return _proficiency_key(entry) == skill
    if not isinstance(entry, dict):
        return False
    entry_skill = entry.get("skill")
    if entry_skill is None or isinstance(entry_skill, (dict, list)):
        return False
    if _proficiency_key(str(entry_skill)) != skill:
        return False
    required_context = entry.get("requires_context")
    if required_context is not None:
        context_set = contexts or set()
        if isinstance(required_context, str):
            if required_context not in context_set:
                return False
        elif isinstance(required_context, list):
            if not {str(item) for item in required_context} <= context_set:
                return False
        else:
            return False
    entry_ability = entry.get("ability")
    if entry_ability is None or entry_ability == "":
        return True
    if isinstance(entry_ability, str):
        return ability.lower() == entry_ability.lower()
    if isinstance(entry_ability, list):
        return ability.lower() in {str(candidate).lower() for candidate in entry_ability}
    return False


@dataclass
class AutomationResult:
    action_id: str
    actor_id: str
    success: bool
    messages: list[str] = field(default_factory=list)
    state_changes: list[dict[str, Any]] = field(default_factory=list)
    dice_rolls: list[dict[str, Any]] = field(default_factory=list)
    node_results: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "actor_id": self.actor_id,
            "success": self.success,
            "messages": self.messages,
            "state_changes": self.state_changes,
            "dice_rolls": self.dice_rolls,
            "node_results": self.node_results,
        }


@dataclass
class _Context:
    action: ActionDefinition
    actor_id: str
    targets: list[str]
    original_targets: list[str]
    params: dict[str, Any]
    result: AutomationResult
    attack_hits: dict[str, bool] = field(default_factory=dict)
    attack_critical: dict[str, bool] = field(default_factory=dict)
    attack_advantage: dict[str, str | None] = field(default_factory=dict)
    brutal_strike_effects: dict[str, list[str]] = field(default_factory=dict)
    save_successes: dict[str, bool] = field(default_factory=dict)
    save_abilities: dict[str, str] = field(default_factory=dict)
    last_damage_taken: dict[str, int] = field(default_factory=dict)
    uncanny_dodge_reactions_spent: set[str] = field(default_factory=set)
    deflect_attacks_reactions_spent: set[str] = field(default_factory=set)
    deflect_attacks_reduction_remaining: dict[str, int] = field(default_factory=dict)
    deflect_attacks_redirect_applied: set[str] = field(default_factory=set)
    superior_hunters_defense_reactions_spent: set[str] = field(default_factory=set)
    slow_fall_reactions_spent: set[str] = field(default_factory=set)
    elemental_affinity_applied: bool = False
    remarkable_athlete_moved: bool = False
    eldritch_smite_targets: set[str] = field(default_factory=set)
    radiant_strikes_targets: set[str] = field(default_factory=set)
    open_hand_strike_index: int = 0
    ability_success: bool | None = None
    concentration_cleared: bool = False
    last_attack_node: dict[str, Any] | None = None
    horde_breaker_applied: bool = False
    horde_breaker_resolving: bool = False
    superior_hunters_prey_applied: bool = False
    improved_blessed_strikes_potent_spellcasting_applied: bool = False
    quivering_palm_applied: bool = False


@dataclass
class _SneakAttackResult:
    amount: int = 0
    rolls: list[RollResult] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    cunning_strike: dict[str, Any] | None = None


@dataclass
class _FrenzyResult:
    amount: int = 0
    rolls: list[RollResult] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class _BrutalStrikeResult:
    amount: int = 0
    effect: str | None = None
    effects: list[str] = field(default_factory=list)
    rolls: list[RollResult] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class _ExtraDamageResult:
    amount: int = 0
    damage_type: str = "untyped"
    rolls: list[RollResult] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class _DamageReductionResult:
    amount_before: int
    amount_after: int
    reduction: int
    rolls: list[RollResult] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)


class AutomationExecutor:
    def __init__(
        self,
        state: GameState,
        roll_service: RollService,
        audit_log: AuditLog,
        economy: EconomyTracker | None = None,
    ):
        self.state = state
        self.roll_service = roll_service
        self.audit_log = audit_log
        self.economy = economy or EconomyTracker(
            state.encounter.action_budgets if state.encounter is not None else None
        )

    def execute(
        self,
        action: ActionDefinition,
        *,
        actor_id: str,
        targets: list[str] | None = None,
        params: dict[str, Any] | None = None,
        idempotency_key: str = "automation",
        player_text: str | None = None,
        player_intent: dict[str, Any] | None = None,
    ) -> AutomationResult:
        result = AutomationResult(action_id=action.id, actor_id=actor_id, success=True)
        params = params or {}
        preexisting_actor_effect_ids = self._actor_effect_ids(actor_id)
        self._validate_target_policy(action, actor_id, targets or [], params)
        self._validate_self_only_targets(action, actor_id, targets or [])
        self._validate_requires_self_target(action, actor_id, targets or [])
        self._validate_target_size_max(action, targets or [])
        self._validate_targets_not_out_of_play(action, targets or [])
        self._validate_willing_targets(action, targets or [], params)
        self._validate_charmed_targets(action, actor_id, targets or [], params)
        self._validate_requirements(action, actor_id)
        self._validate_active_effect_requirement(action, actor_id)
        self._validate_action_surge_preconditions(action, actor_id)
        self._validate_actor_not_out_of_play(action, actor_id)
        self._validate_allowed_action_effects(action, actor_id)
        self._validate_spellcasting_allowed(action, actor_id)
        self._validate_attacks_allowed(action, actor_id)
        self._validate_mage_armor_unarmored_targets(action, actor_id, targets or [])
        self._validate_one_with_shadows_lighting(action, params)
        self._validate_ritual_casting(action, actor_id, params)
        self._validate_cunning_strike_preconditions(action, actor_id, targets or [], params)
        self._validate_brutal_strike_preconditions(action, actor_id, targets or [], params)
        self._validate_fast_hands_preconditions(action, actor_id)
        self._validate_deflect_attacks_preconditions(action, targets or [], params)
        self._validate_uncanny_dodge_preconditions(action, actor_id, targets or [], params)
        self._validate_superior_hunters_defense_preconditions(action, targets or [], params)
        self._validate_remarkable_athlete_preconditions(action, actor_id, params)
        self._validate_open_hand_technique_preconditions(action, actor_id, targets or [], params)
        self._validate_hunters_lore_preconditions(action, actor_id, targets or [])
        self._validate_horde_breaker_preconditions(action, actor_id, targets or [], params)
        self._validate_blessed_strikes_divine_strike_preconditions(
            action,
            actor_id,
            targets or [],
            params,
        )
        self._validate_improved_blessed_strikes_potent_spellcasting_preconditions(
            action,
            actor_id,
            params,
        )
        self._validate_superior_hunters_prey_preconditions(
            action,
            actor_id,
            targets or [],
            params,
        )
        self._validate_repelling_blast_preconditions(action, actor_id, targets or [], params)
        self._validate_slow_fall_preconditions(action, targets or [], params)
        self._validate_stunning_strike_preconditions(action, actor_id, targets or [], params)
        self._validate_quivering_palm_preconditions(action, actor_id, targets or [], params)
        self._validate_empowered_strikes_preconditions(action, actor_id, params)
        self._validate_heightened_focus_preconditions(action, actor_id, targets or [], params)
        self._validate_fleet_step_preconditions(action, actor_id, params)
        self._validate_preserve_life_preconditions(action, actor_id, targets or [], params)
        self._validate_cutting_words_preconditions(action, params)
        self._validate_countercharm_preconditions(action, targets or [], params)
        self._validate_lands_aid_preconditions(action, targets or [], params)
        self._validate_natures_sanctuary_preconditions(action, actor_id, params)
        self._validate_sacred_weapon_preconditions(action, params)
        self._validate_oil_of_sharpness_preconditions(action, params)
        self._prepare_size_based_oil_vial_cost(action, targets or [], params)
        self._validate_rod_of_absorption_preconditions(action, actor_id, params)
        self._validate_rod_of_alertness_preconditions(action, actor_id, targets or [])
        self._validate_robe_of_useful_items_preconditions(action, actor_id, params)
        self._validate_pact_of_blade_weapon_preconditions(action, params)
        self._validate_investment_of_chain_master_preconditions(action, actor_id, params)
        self._validate_thirsting_blade_preconditions(action, actor_id, params)
        self._validate_eldritch_smite_preconditions(action, actor_id, targets or [], params)
        self._validate_conjure_minor_elementals_damage_type(
            action,
            actor_id,
            targets or [],
            params,
        )
        self._validate_allowed_damage_type_param(action, params)
        self._validate_allowed_creature_types_param(action, params)
        self._validate_allowed_list_params(action, params)
        self._validate_fire_shield_type_param(action, params)
        self._validate_greater_restoration_preconditions(action, params)
        self._validate_restoring_touch_preconditions(action, actor_id, targets or [], params)
        self._validate_action_economy(action, actor_id, params)
        self._validate_resource_delta_caps(action, actor_id)
        self._validate_tactical_shift_preconditions(action, actor_id, params)
        self._validate_instinctive_pounce_preconditions(action, actor_id, params)
        self._validate_wild_resurgence_preconditions(action, actor_id)
        self._validate_cost(action, actor_id, params)
        self._spend_action_economy(action, actor_id, params, result)
        self._apply_cost(action, actor_id, params, result)
        ctx = _Context(
            action=action,
            actor_id=actor_id,
            targets=list(targets or []),
            original_targets=list(targets or []),
            params=params,
            result=result,
        )
        for index, node in enumerate(action.automation):
            self._execute_node(ctx, node, f"automation[{index}]", idempotency_key)
        self._mark_action_surge_used(ctx)
        self._expire_actor_effects_after_action(ctx, preexisting_actor_effect_ids)
        self._record_fleet_step_window(ctx)
        self.audit_log.append(
            self.state,
            idempotency_key=idempotency_key,
            player_text=player_text,
            player_intent=player_intent,
            tool_name="automation.execute",
            tool_args={"action_id": action.id, "actor_id": actor_id, "targets": targets or []},
            tool_result=result.to_dict(),
            automation_node_path="automation",
            dice_rolls=result.dice_rolls,
        )
        return result

    def _execute_node(
        self,
        ctx: _Context,
        node: dict[str, Any],
        path: str,
        idempotency_key: str,
    ) -> None:
        node_type = node["type"]
        before_changes = len(ctx.result.state_changes)

        if node_type == "target":
            self._node_target(ctx, node)
        elif node_type == "attack_roll":
            self._node_attack_roll(ctx, node, path)
        elif node_type == "saving_throw":
            self._node_saving_throw(ctx, node, path)
        elif node_type == "ability_check":
            self._node_ability_check(ctx, node, path)
        elif node_type == "damage":
            self._node_damage(ctx, node, path)
        elif node_type == "healing":
            self._node_healing(ctx, node, path)
        elif node_type == "cutting_words":
            self._node_cutting_words(ctx, path)
        elif node_type == "hunter_lore":
            self._node_hunters_lore(ctx, path)
        elif node_type == "temp_hp":
            self._node_temp_hp(ctx, node, path)
        elif node_type == "condition":
            self._node_condition(ctx, node, path)
        elif node_type == "remove_condition":
            self._node_remove_condition(ctx, node, path)
        elif node_type == "greater_restoration":
            self._node_greater_restoration(ctx, node, path)
        elif node_type == "restoring_touch":
            self._node_restoring_touch(ctx, node, path)
        elif node_type == "passive_effect":
            self._node_passive_effect(ctx, node, path)
        elif node_type == "world_effect":
            self._node_world_effect(ctx, node, path)
        elif node_type == "natures_sanctuary":
            self._node_natures_sanctuary(ctx, node, path)
        elif node_type == "natures_sanctuary_move":
            self._node_natures_sanctuary_move(ctx, node, path)
        elif node_type == "repeat_use_save_before_long_rest":
            self._node_repeat_use_save_before_long_rest(ctx, node, path)
        elif node_type == "rod_of_absorption_initialize":
            self._node_rod_of_absorption_initialize(ctx, node, path)
        elif node_type == "rod_of_absorption_absorb_spell":
            self._node_rod_of_absorption_absorb_spell(ctx, node, path)
        elif node_type == "rod_of_alertness_protective_aura":
            self._node_rod_of_alertness_protective_aura(ctx, node, path)
        elif node_type == "robe_of_useful_items_initialize":
            self._node_robe_of_useful_items_initialize(ctx, node, path)
        elif node_type == "robe_of_useful_items_patch":
            self._node_robe_of_useful_items_patch(ctx, node, path)
        elif node_type == "max_hp_delta":
            self._node_max_hp_delta(ctx, node, path)
        elif node_type == "pact_magic_recovery":
            self._node_pact_magic_recovery(ctx, path)
        elif node_type == "preserve_life_healing":
            self._node_preserve_life_healing(ctx, node, path)
        elif node_type == "wild_resurgence_restore_wild_shape":
            self._node_wild_resurgence_restore_wild_shape(ctx, path)
        elif node_type == "resource_delta":
            self._node_resource_delta(ctx, node, path)
        elif node_type == "heightened_focus_step_of_the_wind":
            self._node_heightened_focus_step_of_the_wind(ctx, node, path)
        elif node_type == "quivering_palm_release":
            self._node_quivering_palm_release(ctx, node, path)
        elif node_type == "tactical_shift_move":
            self._node_tactical_shift_move(ctx, node, path)
        elif node_type == "instinctive_pounce_move":
            self._node_instinctive_pounce_move(ctx, node, path)
        elif node_type == "move":
            self._node_move(ctx, node)
        elif node_type == "branch":
            condition = self._branch_condition(ctx, node)
            branch_name = "if_true" if condition else "if_false"
            branch = node.get(branch_name, [])
            for index, child in enumerate(branch):
                self._execute_node(
                    ctx,
                    child,
                    f"{path}.{branch_name}[{index}]",
                    idempotency_key,
                )
            if condition:
                self._execute_potent_cantrip_successful_save_damage(
                    ctx,
                    node,
                    path,
                    idempotency_key,
                )
        elif node_type == "text_result":
            ctx.result.messages.append(str(node.get("text", "")))
        else:
            raise AutomationError(f"unsupported automation node: {node_type}")

        if (
            node_type in STATE_CHANGING_NODE_TYPES
            and len(ctx.result.state_changes) > before_changes
        ):
            self.audit_log.append(
                self.state,
                idempotency_key=f"{idempotency_key}:{path}",
                tool_name="automation.node",
                tool_args={"action_id": ctx.action.id, "node": node},
                tool_result={"state_changes": ctx.result.state_changes[before_changes:]},
                automation_node_path=path,
                dice_rolls=ctx.result.dice_rolls,
            )

    def _node_target(self, ctx: _Context, node: dict[str, Any]) -> None:
        mode = node["mode"]
        if mode == "self":
            ctx.targets = [ctx.actor_id]
        elif mode == "explicit":
            if not ctx.targets:
                raise AutomationError("explicit target node requires targets")
        elif mode == "all":
            if self.state.encounter is None:
                raise AutomationError("all target mode requires an encounter")
            side = node.get("side")
            ctx.targets = [
                combatant_id
                for combatant_id, combatant in self.state.encounter.combatants.items()
                if side is None or combatant.side == side
            ]
        elif mode == "each":
            ctx.targets = list(ctx.targets)
        elif mode == "area":
            ctx.targets = list(ctx.params.get("area_targets", ctx.targets))
        elif mode == "param":
            param_name = str(node.get("param", ""))
            selected = ctx.params.get(param_name)
            if isinstance(selected, list):
                ctx.targets = [str(target_id) for target_id in selected]
            elif selected is not None:
                ctx.targets = [str(selected)]
            elif node.get("fallback") == "explicit_index":
                if not ctx.original_targets:
                    raise AutomationError(f"target param {param_name} did not resolve targets")
                fallback_index = int(node.get("fallback_index", 0))
                if 0 <= fallback_index < len(ctx.original_targets):
                    ctx.targets = [ctx.original_targets[fallback_index]]
                else:
                    ctx.targets = [ctx.original_targets[0]]
            elif node.get("fallback") == "explicit":
                ctx.targets = list(ctx.original_targets)
            else:
                raise AutomationError(f"target param {param_name} is required")
            if not ctx.targets:
                raise AutomationError(f"target param {param_name} did not resolve targets")
        else:
            raise AutomationError(f"unsupported target mode: {mode}")

    def _node_attack_roll(self, ctx: _Context, node: dict[str, Any], path: str) -> None:
        if ctx.action.action_type == "weapon_attack":
            ctx.last_attack_node = dict(node)
        ability = str(node.get("ability", "str")).lower()
        base_attack_bonus, attack_bonus_sources = self._attack_bonus(ctx, node, ability)
        node_advantage = _advantage_value(node.get("advantage"))
        actor = self._entity(ctx.actor_id)
        if bool(ctx.params.get("use_stroke_of_luck")):
            self._validate_stroke_of_luck_target_selection(ctx)
            self._validate_stroke_of_luck_available(actor)
        actor_exhaustion_level, exhaustion_penalty = self._exhaustion_details(actor)
        attack_bonus = base_attack_bonus - exhaustion_penalty
        for target_id in ctx.targets:
            target = self._entity(target_id)
            studied_attack_effect_ids = self._studied_attacks_effect_ids_for(actor, target_id)
            base_ac, ac, armor_class_sources = self._effective_armor_class(target)
            distance_ft = self._combat_distance(actor, target)
            status_advantage, status_sources = self._attack_status_advantage(
                actor,
                target,
                distance_ft,
                actor_id=ctx.actor_id,
                target_id=target_id,
                action=ctx.action,
                ability=ability,
                node_advantage=node_advantage,
            )
            effective_node_advantage = (
                None
                if any(source.get("kind") == "advantage_blocked" for source in status_sources)
                else node_advantage
            )
            advantage_before_brutal_strike = _merge_advantage(
                effective_node_advantage,
                status_advantage,
            )
            brutal_strike = self._brutal_strike_attack_forgo_advantage(
                ctx,
                node,
                target_id,
                ability,
                node_advantage=effective_node_advantage,
                status_advantage=status_advantage,
                status_sources=status_sources,
                advantage=advantage_before_brutal_strike,
            )
            advantage = None if brutal_strike is not None else advantage_before_brutal_strike
            roll = self.roll_service.roll(d20_expression(attack_bonus), advantage=advantage)
            adjustment, adjustment_rolls, adjustment_sources = self._passive_roll_adjustment(
                actor,
                bonus_key="attack_roll_bonus_dice",
                penalty_key="attack_roll_penalty_dice",
            )
            sacred_weapon_bonus, sacred_weapon_sources = self._sacred_weapon_attack_bonus(
                ctx,
                node,
            )
            adjustment += sacred_weapon_bonus
            adjustment_sources.extend(sacred_weapon_sources)
            pact_weapon_bonus, pact_weapon_sources = self._pact_weapon_attack_adjustment(ctx, node)
            adjustment += pact_weapon_bonus
            adjustment_sources.extend(pact_weapon_sources)
            strength_set_bonus, strength_set_sources = self._ability_score_set_attack_adjustment(
                ctx,
                node,
                ability,
            )
            adjustment += strength_set_bonus
            adjustment_sources.extend(strength_set_sources)
            enhancement_bonus, enhancement_sources = self._weapon_enhancement_bonus(ctx)
            adjustment += enhancement_bonus
            adjustment_sources.extend(enhancement_sources)
            sundering_bonus, sundering_sources, sundering_expiry = (
                self._sundering_blow_attack_adjustment(ctx, target_id, path)
            )
            adjustment += sundering_bonus
            adjustment_sources.extend(sundering_sources)
            ctx.result.dice_rolls.append(roll.to_dict())
            ctx.result.dice_rolls.extend(extra.to_dict() for extra in adjustment_rolls)
            natural = self._kept_d20(roll)
            total = roll.total + adjustment
            critical_threshold, critical_threshold_sources = self._critical_hit_threshold(
                ctx.actor_id,
                ctx.action,
            )
            natural_critical = natural >= critical_threshold
            hit = natural_critical or (natural != 1 and total >= ac)
            stroke_of_luck_result = self._apply_stroke_of_luck_to_failed_d20_test(
                ctx,
                actor,
                roll,
                total,
                path,
                use_stroke_of_luck=self._use_stroke_of_luck_for_target(ctx, target_id),
                failed=not hit,
                d20_test_type="attack_roll",
            )
            if stroke_of_luck_result is not None:
                natural = STROKE_OF_LUCK_D20
                total = int(stroke_of_luck_result["total_after"])
                natural_critical = natural >= critical_threshold
                hit = True
            auto_critical_sources = (
                self._target_auto_critical_sources(target, distance_ft) if hit else []
            )
            critical = (natural_critical and hit) or bool(auto_critical_sources)
            ctx.attack_hits[target_id] = hit
            ctx.attack_critical[target_id] = critical
            ctx.attack_advantage[target_id] = advantage
            if brutal_strike is not None:
                effects = [str(effect) for effect in brutal_strike.get("effects", [])]
                ctx.brutal_strike_effects[target_id] = effects
                self._mark_brutal_strike_used(ctx, target_id, effects)
            ctx.result.node_results[path] = {
                "target_id": target_id,
                "base_ac": base_ac,
                "ac": ac,
                "armor_class_sources": armor_class_sources,
                "distance_ft": distance_ft,
                "base_attack_bonus": base_attack_bonus,
                "attack_bonus_sources": attack_bonus_sources,
                "ability": ability,
                "exhaustion_level": actor_exhaustion_level,
                "d20_penalty": exhaustion_penalty,
                "base_total": roll.total,
                "passive_adjustment": adjustment,
                "passive_sources": adjustment_sources,
                "status_advantage": status_advantage,
                "status_sources": status_sources,
                "auto_critical_sources": auto_critical_sources,
                "critical_threshold": critical_threshold,
                "critical_threshold_sources": critical_threshold_sources,
                "total": total,
                "natural": natural,
                "hit": hit,
                "critical": critical,
            }
            if brutal_strike is not None:
                ctx.result.node_results[path]["brutal_strike"] = brutal_strike
            if stroke_of_luck_result is not None:
                ctx.result.node_results[path]["stroke_of_luck"] = stroke_of_luck_result
            if sundering_expiry is not None:
                ctx.result.state_changes.append(sundering_expiry)
            ctx.result.state_changes.extend(
                self._expire_target_effects_on_incoming_attack(target_id, path)
            )
            self._expire_studied_attacks_effects_on_attack(
                ctx,
                target_id,
                studied_attack_effect_ids,
                path,
            )
            self._apply_studied_attacks_on_miss(ctx, target_id, path)
            self._apply_multiattack_defense_on_hit(ctx, target_id, path)
            self._mark_weapon_attack_target_this_turn(ctx, target_id)
            self._mark_thirsting_blade_pact_weapon_attack_this_turn(ctx, target_id)
            self._mark_thirsting_blade_extra_attack_used(ctx, target_id)

    def _attack_bonus(
        self,
        ctx: _Context,
        node: dict[str, Any],
        ability: str,
    ) -> tuple[int, list[dict[str, Any]]]:
        actor = self._entity(ctx.actor_id)
        if "attack_bonus" in node:
            bonus = int(node["attack_bonus"])
            sources = [{"kind": "fixed", "amount": int(node["attack_bonus"])}]
            spell_bonus, spell_sources = self._spell_attack_bonus(actor, ctx.action)
            if spell_bonus:
                bonus += spell_bonus
                sources.extend(spell_sources)
            return bonus, sources
        bonus = self._ability_modifier(actor, ability)
        sources = [{"kind": "ability", "ability": ability, "amount": bonus}]
        if node.get("proficiency", True) is not False:
            proficiency_source = self._proficiency_source(actor)
            proficiency = int(getattr(proficiency_source, "proficiency_bonus", 2))
            bonus += proficiency
            sources.append({"kind": "proficiency", "amount": proficiency})
        extra_bonus = node.get("bonus")
        if isinstance(extra_bonus, int) and not isinstance(extra_bonus, bool):
            bonus += extra_bonus
            sources.append({"kind": "bonus", "amount": extra_bonus})
        spell_bonus, spell_sources = self._spell_attack_bonus(actor, ctx.action)
        if spell_bonus:
            bonus += spell_bonus
            sources.extend(spell_sources)
        return bonus, sources

    def _node_saving_throw(self, ctx: _Context, node: dict[str, Any], path: str) -> None:
        ability = str(node["ability"])
        dc, dc_source = self._resolve_node_dc(ctx, node)
        if (
            bool(ctx.params.get("use_dark_ones_own_luck"))
            and ctx.params.get("dark_ones_own_luck_target_id") is None
            and len(ctx.targets) > 1
        ):
            raise AutomationError("Dark One's Own Luck saving throw requires an explicit target")
        if (
            bool(ctx.params.get("use_indomitable"))
            and ctx.params.get("indomitable_target_id") is None
            and len(ctx.targets) > 1
        ):
            raise AutomationError("Indomitable saving throw requires an explicit target")
        if (
            bool(ctx.params.get("use_disciplined_survivor"))
            and ctx.params.get("disciplined_survivor_target_id") is None
            and len(ctx.targets) > 1
        ):
            raise AutomationError("Disciplined Survivor saving throw requires an explicit target")
        if bool(ctx.params.get("use_stroke_of_luck")):
            self._validate_stroke_of_luck_target_selection(ctx)
        if bool(ctx.params.get("use_countercharm")):
            self._validate_countercharm_target_selection(ctx)
        disciplined_survivor_target_id = ctx.params.get("disciplined_survivor_target_id")
        if (
            bool(ctx.params.get("use_disciplined_survivor"))
            and disciplined_survivor_target_id is not None
            and str(disciplined_survivor_target_id) not in ctx.targets
        ):
            raise AutomationError("Disciplined Survivor target must be one of the action targets")
        for target_id in ctx.targets:
            target = self._entity(target_id)
            use_dark_ones_own_luck = self._use_dark_ones_own_luck_for_save(ctx, target_id)
            if use_dark_ones_own_luck:
                self._validate_dark_ones_own_luck_available(target)
            use_indomitable = self._use_indomitable_for_save(ctx, target_id)
            if use_indomitable:
                self._validate_indomitable_available(target)
            use_disciplined_survivor = self._use_disciplined_survivor_for_save(ctx, target_id)
            if use_disciplined_survivor:
                self._validate_disciplined_survivor_available(target)
            use_stroke_of_luck = self._use_stroke_of_luck_for_target(ctx, target_id)
            if use_stroke_of_luck:
                self._validate_stroke_of_luck_available(target)
            use_countercharm = self._use_countercharm_for_save(ctx, target_id)
            if use_countercharm:
                self._validate_countercharm_save_node(ctx.action)
                self._validate_countercharm_available(ctx, target_id)
            if (
                sum(
                    [
                        use_indomitable,
                        use_disciplined_survivor,
                        use_stroke_of_luck,
                        use_countercharm,
                    ]
                )
                > 1
            ):
                raise AutomationError("choose only one failed saving throw feature")
            if node.get("auto_fail_willing_targets") is True and self._target_willing(
                ctx.params,
                target_id,
            ):
                ctx.save_successes[target_id] = False
                ctx.save_abilities[target_id] = ability.lower()
                ctx.result.node_results[path] = {
                    "target_id": target_id,
                    "ability": ability,
                    "dc": dc,
                    "dc_source": dc_source,
                    "auto_failed": True,
                    "status_sources": [
                        {
                            "kind": "auto_fail",
                            "modifier": "auto_fail_willing_targets",
                        }
                    ],
                    "success": False,
                }
                continue
            auto_fail_sources = self._saving_throw_auto_failure_sources(target, ability, node)
            if auto_fail_sources:
                if use_indomitable:
                    raise AutomationError("Indomitable requires a rolled failed saving throw")
                if use_disciplined_survivor:
                    raise AutomationError(
                        "Disciplined Survivor requires a rolled failed saving throw"
                    )
                if use_stroke_of_luck:
                    raise AutomationError("Stroke of Luck requires a rolled failed D20 Test")
                if use_countercharm:
                    raise AutomationError("Countercharm requires a rolled failed saving throw")
                ctx.save_successes[target_id] = False
                ctx.save_abilities[target_id] = ability.lower()
                ctx.result.node_results[path] = {
                    "target_id": target_id,
                    "ability": ability,
                    "dc": dc,
                    "dc_source": dc_source,
                    "auto_failed": True,
                    "status_sources": [
                        {"kind": "auto_fail", **source} for source in auto_fail_sources
                    ],
                    "success": False,
                }
                staggering_expiry = self._expire_next_saving_throw_disadvantage(target_id, path)
                if staggering_expiry is not None:
                    ctx.result.state_changes.append(staggering_expiry)
                continue
            base_bonus, proficient, proficiency_sources = self._saving_throw_bonus(
                target,
                ability,
            )
            target_exhaustion_level, exhaustion_penalty = self._exhaustion_details(target)
            bonus = base_bonus - exhaustion_penalty
            status_advantage, status_sources = self._saving_throw_status_advantage(
                target,
                ability,
                contexts=self._node_check_contexts(node),
            )
            roll = self.roll_service.roll(d20_expression(bonus), advantage=status_advantage)
            adjustment, adjustment_rolls, adjustment_sources = self._passive_roll_adjustment(
                target,
                bonus_key="saving_throw_bonus_dice",
                penalty_key="saving_throw_penalty_dice",
            )
            ctx.result.dice_rolls.append(roll.to_dict())
            ctx.result.dice_rolls.extend(extra.to_dict() for extra in adjustment_rolls)
            total = roll.total + adjustment
            dark_ones_own_luck_result = self._apply_dark_ones_own_luck_to_roll(
                ctx,
                target,
                total,
                path,
                use_dark_ones_own_luck=use_dark_ones_own_luck,
            )
            if dark_ones_own_luck_result is not None:
                total = int(dark_ones_own_luck_result["total_after"])
            indomitable_might_result = self._apply_indomitable_might_to_d20_test(
                self._proficiency_source(target),
                ability,
                total,
                dc,
            )
            if indomitable_might_result is not None:
                total = int(indomitable_might_result["total_after"])
            success = total >= dc
            stroke_of_luck_result = self._apply_stroke_of_luck_to_failed_d20_test(
                ctx,
                target,
                roll,
                total,
                path,
                use_stroke_of_luck=use_stroke_of_luck,
                failed=not success,
                d20_test_type="saving_throw",
            )
            if stroke_of_luck_result is not None:
                total = int(stroke_of_luck_result["total_after"])
                success = total >= dc
            indomitable_result = self._apply_indomitable_to_failed_save(
                ctx,
                target,
                total,
                dc,
                bonus,
                adjustment,
                status_advantage,
                path,
                use_indomitable=use_indomitable,
            )
            if indomitable_result is not None:
                total = int(indomitable_result["total_after"])
                success = bool(indomitable_result["success"])
            disciplined_survivor_result = self._apply_disciplined_survivor_to_failed_save(
                ctx,
                target,
                total,
                dc,
                bonus,
                adjustment,
                status_advantage,
                path,
                use_disciplined_survivor=use_disciplined_survivor,
            )
            if disciplined_survivor_result is not None:
                total = int(disciplined_survivor_result["total_after"])
                success = bool(disciplined_survivor_result["success"])
            countercharm_result = self._apply_countercharm_to_failed_save(
                ctx,
                target,
                total,
                dc,
                bonus,
                adjustment,
                path,
                use_countercharm=use_countercharm,
            )
            if countercharm_result is not None:
                total = int(countercharm_result["total_after"])
                success = bool(countercharm_result["success"])
            ctx.save_successes[target_id] = success
            ctx.save_abilities[target_id] = ability.lower()
            ctx.result.node_results[path] = {
                "target_id": target_id,
                "ability": ability,
                "dc": dc,
                "dc_source": dc_source,
                "bonus": bonus,
                "base_bonus": base_bonus,
                "proficient": proficient,
                "proficiency_sources": proficiency_sources,
                "exhaustion_level": target_exhaustion_level,
                "d20_penalty": exhaustion_penalty,
                "base_total": roll.total,
                "passive_adjustment": adjustment,
                "passive_sources": adjustment_sources,
                "status_advantage": status_advantage,
                "status_sources": status_sources,
                "total": total,
                "success": success,
            }
            if dark_ones_own_luck_result is not None:
                ctx.result.node_results[path]["dark_ones_own_luck"] = dark_ones_own_luck_result
            if indomitable_might_result is not None:
                ctx.result.node_results[path]["indomitable_might"] = indomitable_might_result
            if stroke_of_luck_result is not None:
                ctx.result.node_results[path]["stroke_of_luck"] = stroke_of_luck_result
            if indomitable_result is not None:
                ctx.result.node_results[path]["indomitable"] = indomitable_result
            if disciplined_survivor_result is not None:
                ctx.result.node_results[path]["disciplined_survivor"] = disciplined_survivor_result
            if countercharm_result is not None:
                ctx.result.node_results[path]["countercharm"] = countercharm_result
            staggering_expiry = self._expire_next_saving_throw_disadvantage(target_id, path)
            if staggering_expiry is not None:
                ctx.result.state_changes.append(staggering_expiry)

    def _node_ability_check(self, ctx: _Context, node: dict[str, Any], path: str) -> None:
        original_ability = str(node["ability"]).lower()
        ability = original_ability
        skill = _proficiency_key(str(node["skill"])) if node.get("skill") else None
        tool = _proficiency_key(str(node["tool"])) if node.get("tool") else None
        primal_knowledge = self._primal_knowledge_ability_check(
            ctx.actor_id,
            ability,
            skill,
            use_primal_knowledge=bool(ctx.params.get("use_primal_knowledge")),
        )
        if primal_knowledge is not None:
            ability = str(primal_knowledge["ability"])
        dc, dc_source = self._resolve_node_dc(ctx, node)
        actor = self._entity(ctx.actor_id)
        base_bonus, proficient, proficiency_sources, proficiency_advantage = (
            self._ability_check_bonus(
                actor,
                ability,
                skill=skill,
                tool=tool,
            )
        )
        actor_exhaustion_level, exhaustion_penalty = self._exhaustion_details(actor)
        bonus = base_bonus - exhaustion_penalty
        if bool(ctx.params.get("use_tactical_mind")) and bool(ctx.params.get("use_stroke_of_luck")):
            raise AutomationError("choose only one failed ability check feature")
        if bool(ctx.params.get("use_tactical_mind")):
            self._validate_tactical_mind_available(ctx.actor_id)
        if bool(ctx.params.get("use_dark_ones_own_luck")):
            self._validate_dark_ones_own_luck_available(actor)
        if bool(ctx.params.get("use_stroke_of_luck")):
            self._validate_stroke_of_luck_available(actor)
        status_advantage, status_sources = self._ability_check_status_advantage(
            actor,
            ability,
            skill=skill,
            contexts=self._node_check_contexts(node),
        )
        advantage = _merge_advantage(
            _advantage_value(node.get("advantage")),
            status_advantage,
            proficiency_advantage,
        )
        roll = self.roll_service.roll(d20_expression(bonus), advantage=advantage)
        adjustment, adjustment_rolls, adjustment_sources = self._passive_roll_adjustment(
            actor,
            bonus_key="ability_check_bonus_dice",
            penalty_key="ability_check_penalty_dice",
        )
        ctx.result.dice_rolls.append(roll.to_dict())
        ctx.result.dice_rolls.extend(extra.to_dict() for extra in adjustment_rolls)
        total = roll.total + adjustment
        reliable_talent_result = self._apply_reliable_talent_to_ability_check(
            self._proficiency_source(actor),
            roll,
            total,
            proficiency_sources,
            dc,
        )
        if reliable_talent_result is not None:
            total = int(reliable_talent_result["total_after"])
        glibness_result = self._apply_charisma_check_minimum_d20_to_ability_check(
            actor,
            ability,
            roll,
            total,
            dc,
            reliable_talent_result,
        )
        if glibness_result is not None:
            total = int(glibness_result["total_after"])
        dark_ones_own_luck_result = self._apply_dark_ones_own_luck_to_roll(
            ctx,
            actor,
            total,
            path,
            use_dark_ones_own_luck=bool(ctx.params.get("use_dark_ones_own_luck")),
        )
        if dark_ones_own_luck_result is not None:
            total = int(dark_ones_own_luck_result["total_after"])
        indomitable_might_result = self._apply_indomitable_might_to_d20_test(
            self._proficiency_source(actor),
            ability,
            total,
            dc,
        )
        if indomitable_might_result is not None:
            total = int(indomitable_might_result["total_after"])
        tactical_mind_result = self._apply_tactical_mind_to_ability_check(
            ctx,
            total,
            dc,
            path,
        )
        if tactical_mind_result is not None:
            total = int(tactical_mind_result["total_after"])
        stroke_of_luck_result = self._apply_stroke_of_luck_to_failed_d20_test(
            ctx,
            actor,
            roll,
            total,
            path,
            use_stroke_of_luck=bool(ctx.params.get("use_stroke_of_luck")),
            failed=total < dc,
            d20_test_type="ability_check",
        )
        if stroke_of_luck_result is not None:
            total = int(stroke_of_luck_result["total_after"])
        ctx.ability_success = total >= dc
        ctx.result.node_results[path] = {
            "actor_id": ctx.actor_id,
            "ability": ability,
            "original_ability": original_ability,
            "skill": skill,
            "tool": tool,
            "dc": dc,
            "dc_source": dc_source,
            "bonus": bonus,
            "base_bonus": base_bonus,
            "proficient": proficient,
            "proficiency_sources": proficiency_sources,
            "exhaustion_level": actor_exhaustion_level,
            "d20_penalty": exhaustion_penalty,
            "base_total": roll.total,
            "passive_adjustment": adjustment,
            "passive_sources": adjustment_sources,
            "status_advantage": status_advantage,
            "status_sources": status_sources,
            "total": total,
            "success": ctx.ability_success,
        }
        if primal_knowledge is not None:
            ctx.result.node_results[path]["primal_knowledge"] = primal_knowledge
        if reliable_talent_result is not None:
            ctx.result.node_results[path]["reliable_talent"] = reliable_talent_result
        if glibness_result is not None:
            ctx.result.node_results[path]["glibness"] = glibness_result
        if dark_ones_own_luck_result is not None:
            ctx.result.node_results[path]["dark_ones_own_luck"] = dark_ones_own_luck_result
        if indomitable_might_result is not None:
            ctx.result.node_results[path]["indomitable_might"] = indomitable_might_result
        if tactical_mind_result is not None:
            ctx.result.node_results[path]["tactical_mind"] = tactical_mind_result
        if stroke_of_luck_result is not None:
            ctx.result.node_results[path]["stroke_of_luck"] = stroke_of_luck_result

    def _node_damage(self, ctx: _Context, node: dict[str, Any], path: str) -> None:
        damage_type = self._pact_weapon_damage_type(
            ctx,
            self._empowered_strikes_damage_type(
                ctx,
                node,
                self._sacred_weapon_damage_type(
                    ctx,
                    node,
                    str(node.get("damage_type", "untyped")),
                ),
            ),
        )
        require_hit = bool(node.get("requires_hit", False))
        save_half = bool(node.get("save_half", False))
        shared_roll = bool(node.get("shared_roll", False))
        open_hand_strike_index = self._open_hand_damage_strike_index(ctx, node)
        shared_amount: int | None = None
        for target_id in ctx.targets:
            force_potent_half = bool(node.get("potent_cantrip_force_half", False))
            if self._skip_target_for_save_gate(ctx, node, target_id) and not force_potent_half:
                continue
            potent_cantrip = self._potent_cantrip_half_damage(
                ctx,
                node,
                target_id,
                require_hit=require_hit,
                force_half=force_potent_half,
            )
            if force_potent_half and potent_cantrip is None:
                continue
            if require_hit and not ctx.attack_hits.get(target_id, False):
                if potent_cantrip is not None:
                    ctx.result.messages.append(f"{target_id} was missed; Potent Cantrip applies")
                else:
                    ctx.result.messages.append(f"{target_id} was missed")
                    continue
            if shared_roll:
                if shared_amount is None:
                    shared_amount, rolls = self._roll_amount(ctx, node)
                    ctx.result.dice_rolls.extend(roll.to_dict() for roll in rolls)
                amount = shared_amount
            else:
                amount, rolls = self._roll_amount(ctx, node)
            ctx.result.dice_rolls.extend(roll.to_dict() for roll in rolls)
            if ctx.attack_critical.get(target_id, False) and "dice" in node:
                critical_extra_amount, extra_rolls = self._roll_amount(ctx, node)
                amount += critical_extra_amount
                ctx.result.dice_rolls.extend(roll.to_dict() for roll in extra_rolls)
            passive_bonus, passive_bonus_sources = self._passive_damage_bonus(ctx, node)
            amount += passive_bonus
            brutal_strike = self._brutal_strike_bonus(ctx, node, target_id, damage_type)
            amount += brutal_strike.amount
            ctx.result.dice_rolls.extend(roll.to_dict() for roll in brutal_strike.rolls)
            frenzy = self._frenzy_bonus(ctx, node, target_id, damage_type)
            amount += frenzy.amount
            ctx.result.dice_rolls.extend(roll.to_dict() for roll in frenzy.rolls)
            sneak_attack = self._sneak_attack_bonus(
                ctx,
                node,
                target_id,
                damage_type,
            )
            amount += sneak_attack.amount
            ctx.result.dice_rolls.extend(roll.to_dict() for roll in sneak_attack.rolls)
            colossus_slayer = self._colossus_slayer_bonus(ctx, target_id, damage_type)
            amount += colossus_slayer.amount
            ctx.result.dice_rolls.extend(roll.to_dict() for roll in colossus_slayer.rolls)
            enlarge_weapon_damage = self._enlarge_weapon_damage_bonus(
                ctx,
                target_id,
                damage_type,
            )
            amount += enlarge_weapon_damage.amount
            ctx.result.dice_rolls.extend(roll.to_dict() for roll in enlarge_weapon_damage.rolls)
            reduced_weapon_damage = self._reduced_weapon_damage_penalty(
                ctx,
                node,
                target_id,
                amount,
            )
            if reduced_weapon_damage is not None:
                amount = reduced_weapon_damage.amount_after
                ctx.result.dice_rolls.extend(roll.to_dict() for roll in reduced_weapon_damage.rolls)
            evasion = None
            amount_before_evasion = amount
            if save_half and potent_cantrip is None:
                evasion = self._evasion_adjustment(
                    target_id,
                    amount,
                    save_success=ctx.save_successes.get(target_id),
                    save_ability=ctx.save_abilities.get(target_id),
                )
                if evasion is not None:
                    amount = int(evasion["amount_after_evasion"])
                elif ctx.save_successes.get(target_id, False):
                    amount //= 2
            if potent_cantrip is not None:
                amount_before_potent_cantrip = amount
                amount //= 2
                potent_cantrip["amount_before_half"] = amount_before_potent_cantrip
                potent_cantrip["amount_after_half"] = amount
            amount_before_slow_fall = amount
            amount, slow_fall = self._apply_slow_fall_if_requested(
                ctx,
                target_id,
                amount,
                damage_type,
            )
            amount_before_deflect_attacks = amount
            amount, deflect_attacks = self._apply_deflect_attacks_if_requested(
                ctx,
                target_id,
                amount,
                damage_type,
                path,
            )
            extra_damage = self._marked_target_attack_damage_bonuses(ctx, target_id)
            eldritch_smite = self._eldritch_smite_bonus(ctx, target_id, path)
            if eldritch_smite.amount:
                extra_damage.append(eldritch_smite)
            radiant_strikes = self._radiant_strikes_bonus(ctx, target_id)
            if radiant_strikes.amount:
                extra_damage.append(radiant_strikes)
            blessed_strikes = self._blessed_strikes_divine_strike_bonus(ctx, target_id)
            if blessed_strikes.amount:
                extra_damage.append(blessed_strikes)
            conjure_minor_elementals = self._conjure_minor_elementals_bonus(ctx, target_id)
            if conjure_minor_elementals.amount:
                extra_damage.append(conjure_minor_elementals)
            for extra_result in extra_damage:
                ctx.result.dice_rolls.extend(roll.to_dict() for roll in extra_result.rolls)
            amount_before_uncanny_dodge = amount
            amount, uncanny_dodge = self._apply_uncanny_dodge_if_requested(
                ctx,
                target_id,
                amount,
                path,
            )
            superior_hunters_defense = self._apply_superior_hunters_defense_if_requested(
                ctx,
                target_id,
                amount,
                damage_type,
                path,
            )
            target_before = self._entity(target_id)
            hp_before = int(getattr(target_before, "hp_current"))
            temp_hp_before = int(getattr(target_before, "temp_hp", 0))
            damage_immunity_sources = self._passive_damage_immunity_sources(
                target_before,
                damage_type,
            )
            damage_resistance_sources = self._passive_damage_resistance_sources(
                target_before,
                damage_type,
            )
            damage_taken = self._mitigated_damage(target_before, amount, damage_type)
            applied = self._apply_damage(target_id, amount, damage_type, ctx=ctx, path=path)
            extra_damage_changes: list[dict[str, Any]] = []
            extra_damage_taken = 0
            extra_damage_applied = 0
            for extra_result in extra_damage:
                extra_superior_hunters_defense = self._apply_superior_hunters_defense_if_requested(
                    ctx,
                    target_id,
                    extra_result.amount,
                    extra_result.damage_type,
                    f"{path}.extra_damage",
                )
                target_for_extra = self._entity(target_id)
                extra_taken = self._mitigated_damage(
                    target_for_extra,
                    extra_result.amount,
                    extra_result.damage_type,
                )
                extra_applied = self._apply_damage(
                    target_id,
                    extra_result.amount,
                    extra_result.damage_type,
                    ctx=ctx,
                    path=f"{path}.extra_damage",
                )
                extra_damage_taken += extra_taken
                extra_damage_applied += extra_applied
                extra_damage_changes.append(
                    {
                        "amount": extra_result.amount,
                        "applied": extra_applied,
                        "damage_type": extra_result.damage_type,
                        "sources": extra_result.sources,
                    }
                )
                if extra_superior_hunters_defense is not None:
                    extra_damage_changes[-1]["superior_hunters_defense"] = (
                        extra_superior_hunters_defense
                    )
            hp_after = int(getattr(self._entity(target_id), "hp_current"))
            total_damage_taken = damage_taken + extra_damage_taken
            total_applied = applied + extra_damage_applied
            ctx.last_damage_taken[target_id] = total_damage_taken
            change = {
                "type": "damage",
                "target_id": target_id,
                "amount": amount,
                "applied": applied,
                "damage_type": damage_type,
                "path": path,
            }
            if uncanny_dodge is not None:
                change["uncanny_dodge"] = uncanny_dodge
                change["amount_before_uncanny_dodge"] = amount_before_uncanny_dodge
            if superior_hunters_defense is not None:
                change["superior_hunters_defense"] = superior_hunters_defense
            if slow_fall is not None:
                change["slow_fall"] = slow_fall
                change["amount_before_slow_fall"] = amount_before_slow_fall
            if deflect_attacks is not None:
                change["deflect_attacks"] = deflect_attacks
                change["amount_before_deflect_attacks"] = amount_before_deflect_attacks
            if evasion is not None:
                change["evasion"] = evasion
                change["amount_before_evasion"] = amount_before_evasion
            if passive_bonus:
                change["passive_damage_bonus"] = passive_bonus
                change["passive_sources"] = passive_bonus_sources
            if damage_immunity_sources:
                change["damage_immunity_sources"] = damage_immunity_sources
            if damage_resistance_sources:
                change["damage_resistance_sources"] = damage_resistance_sources
            if brutal_strike.amount:
                change["brutal_strike_bonus"] = brutal_strike.amount
                change["brutal_strike_sources"] = brutal_strike.sources
            if frenzy.amount:
                change["frenzy_bonus"] = frenzy.amount
                change["frenzy_sources"] = frenzy.sources
            if sneak_attack.amount:
                change["sneak_attack_bonus"] = sneak_attack.amount
                change["sneak_attack_sources"] = sneak_attack.sources
            if colossus_slayer.amount:
                change["colossus_slayer_bonus"] = colossus_slayer.amount
                change["colossus_slayer_sources"] = colossus_slayer.sources
            if enlarge_weapon_damage.amount:
                change["enlarge_weapon_damage_bonus"] = enlarge_weapon_damage.amount
                change["enlarge_weapon_damage_sources"] = enlarge_weapon_damage.sources
            if reduced_weapon_damage is not None:
                change["reduce_weapon_damage_penalty"] = reduced_weapon_damage.reduction
                change["amount_before_reduce_weapon_damage_penalty"] = (
                    reduced_weapon_damage.amount_before
                )
                change["reduce_weapon_damage_sources"] = reduced_weapon_damage.sources
            if extra_damage_changes:
                change["extra_damage"] = extra_damage_changes
                change["total_applied"] = total_applied
            if potent_cantrip is not None:
                change["potent_cantrip"] = potent_cantrip
            ctx.result.state_changes.append(change)
            self._apply_improved_blessed_strikes_potent_spellcasting_temp_hp(
                ctx,
                target_id,
                total_damage_taken,
                path,
            )
            relentless_rage = self._relentless_rage_after_drop_to_zero(
                target_id,
                hp_before=hp_before,
                hp_max=int(getattr(target_before, "hp_max")),
                temp_hp_before=temp_hp_before,
                total_damage_taken=total_damage_taken,
                total_applied=total_applied,
                path=path,
            )
            if relentless_rage is not None:
                relentless_change, relentless_rolls = relentless_rage
                ctx.result.dice_rolls.extend(roll.to_dict() for roll in relentless_rolls)
                ctx.result.state_changes.append(relentless_change)
            self._apply_superior_hunters_prey_if_requested(
                ctx,
                target_id,
                total_damage_taken,
                path,
            )
            if brutal_strike.amount:
                for brutal_strike_effect in brutal_strike.effects:
                    self._apply_brutal_strike_effect(
                        ctx,
                        target_id,
                        brutal_strike_effect,
                        path,
                    )
            for cunning_strike in self._cunning_strike_effects(sneak_attack.cunning_strike):
                self._apply_cunning_strike_effect(ctx, target_id, cunning_strike, path)
            self._apply_open_hand_technique_if_requested(
                ctx,
                target_id,
                path,
                strike_index=open_hand_strike_index,
            )
            self._apply_stunning_strike_if_requested(ctx, target_id, path)
            self._apply_quivering_palm_if_requested(ctx, target_id, path)
            self._apply_repelling_blast_if_requested(ctx, target_id, path)
            self._apply_eldritch_smite_prone_if_requested(ctx, target_id, path)
            if ctx.attack_critical.get(target_id, False):
                self._apply_remarkable_athlete_move_if_requested(ctx, path)
            concentration = self._concentration_save_after_damage(
                target_id,
                total_damage_taken,
                path,
            )
            if concentration is not None:
                concentration_change, concentration_roll = concentration
                ctx.result.dice_rolls.append(concentration_roll.to_dict())
                ctx.result.state_changes.append(concentration_change)
            if total_damage_taken > 0 and node.get("breaks_on_damage", True) is not False:
                ctx.result.state_changes.extend(
                    self._expire_target_effects_on_damage(
                        ctx,
                        target_id,
                        path,
                        damage_source_actor_id=ctx.actor_id,
                    )
                )
            hp_after = int(getattr(self._entity(target_id), "hp_current"))
            if hp_before > 0 and hp_after == 0 and total_applied > 0:
                ctx.result.state_changes.extend(
                    self._dark_ones_blessing_changes(
                        ctx.actor_id,
                        target_id,
                        path,
                    )
                )
        self._apply_horde_breaker_if_requested(ctx, node, path)

    def _node_healing(self, ctx: _Context, node: dict[str, Any], path: str) -> None:
        blessed_healer_triggered = False
        for target_id in ctx.targets:
            amount, rolls, supreme_healing = self._healing_amount(ctx, node)
            ctx.result.dice_rolls.extend(roll.to_dict() for roll in rolls)
            disciple_bonus = self._disciple_of_life_bonus(ctx)
            amount += disciple_bonus
            applied = self._apply_healing(target_id, amount)
            if target_id != ctx.actor_id and applied > 0:
                blessed_healer_triggered = True
            change: dict[str, Any] = {
                "type": "healing",
                "target_id": target_id,
                "amount": amount,
                "applied": applied,
                "path": path,
            }
            if disciple_bonus:
                change["disciple_of_life_bonus"] = disciple_bonus
                change["disciple_of_life_source"] = "srd.disciple_of_life"
            if supreme_healing is not None:
                change["supreme_healing"] = supreme_healing
            ctx.result.state_changes.append(change)
        if blessed_healer_triggered:
            blessed_bonus = self._blessed_healer_bonus(ctx)
            if blessed_bonus:
                applied = self._apply_healing(ctx.actor_id, blessed_bonus)
                ctx.result.state_changes.append(
                    {
                        "type": "healing",
                        "target_id": ctx.actor_id,
                        "amount": blessed_bonus,
                        "applied": applied,
                        "blessed_healer_bonus": blessed_bonus,
                        "blessed_healer_source": BLESSED_HEALER_ACTION_ID,
                        "path": path,
                    }
                )

    def _node_cutting_words(self, ctx: _Context, path: str) -> None:
        trigger = self._cutting_words_trigger(ctx.params)
        die = self._bardic_inspiration_die(ctx.actor_id)
        roll = self.roll_service.roll(die)
        ctx.result.dice_rolls.append(roll.to_dict())
        original_total = int(trigger["roll_total"])
        adjusted_total = original_total - roll.total
        result: dict[str, Any] = {
            "target_id": ctx.targets[0] if ctx.targets else None,
            "roll_type": trigger["roll_type"],
            "bardic_inspiration_die": die,
            "cutting_words_roll": roll.total,
            "original_total": original_total,
            "adjusted_total": adjusted_total,
        }
        threshold = trigger.get("success_threshold")
        if isinstance(threshold, int):
            result["success_threshold"] = threshold
            result["success_after"] = adjusted_total >= threshold
        if trigger["roll_type"] == "damage_roll":
            result["damage_before"] = original_total
            result["damage_after"] = max(0, adjusted_total)
            result["damage_reduction"] = original_total - result["damage_after"]
        ctx.result.node_results[path] = result
        ctx.result.messages.append("Cutting Words was applied to the triggering roll.")

    def _node_hunters_lore(self, ctx: _Context, path: str) -> None:
        results: list[dict[str, Any]] = []
        for target_id in ctx.targets:
            target = self._entity(target_id)
            results.append(
                {
                    "target_id": target_id,
                    "marked_by_hunters_mark": True,
                    "immunities": list(getattr(target, "immunities", [])),
                    "resistances": list(getattr(target, "resistances", [])),
                    "vulnerabilities": list(getattr(target, "vulnerabilities", [])),
                }
            )
        for result in results:
            result["has_any"] = bool(
                result["immunities"] or result["resistances"] or result["vulnerabilities"]
            )
        ctx.result.node_results[path] = results[0] if len(results) == 1 else results
        ctx.result.messages.append(
            "Hunter's Lore reveals the marked creature's immunities, resistances, and vulnerabilities."
        )

    def _node_preserve_life_healing(
        self,
        ctx: _Context,
        node: dict[str, Any],
        path: str,
    ) -> None:
        allocations = self._preserve_life_allocations(
            ctx.action,
            ctx.actor_id,
            ctx.targets,
            ctx.params,
        )
        for target_id in ctx.targets:
            amount = allocations[target_id]
            applied = self._apply_healing(target_id, amount)
            target = self._entity(target_id)
            ctx.result.state_changes.append(
                {
                    "type": "healing",
                    "target_id": target_id,
                    "amount": amount,
                    "applied": applied,
                    "path": path,
                    "source_action_id": ctx.action.id,
                    "preserve_life_cap": bloodied_hp_cap(int(getattr(target, "hp_max"))),
                    "preserve_life_points_param": node.get(
                        "points_param",
                        "preserve_life_points",
                    ),
                }
            )

    def _node_temp_hp(self, ctx: _Context, node: dict[str, Any], path: str) -> None:
        for target_id in ctx.targets:
            amount, rolls = self._roll_amount(ctx, node)
            ctx.result.dice_rolls.extend(roll.to_dict() for roll in rolls)
            target = self._entity(target_id)
            before = int(getattr(target, "temp_hp", 0))
            after = max(before, amount)
            source_effect_id: str | None = None
            if "duration" in node:
                source_effect_id = self._effect_id(target_id, path)
            setattr(target, "temp_hp", after)
            if source_effect_id is not None and after > before:
                self._set_temp_hp_source(target_id, target, source_effect_id)
            elif source_effect_id is None and after > before:
                self._clear_temp_hp_source(target_id, target)
            ctx.result.state_changes.append(
                {
                    "type": "temp_hp",
                    "target_id": target_id,
                    "before": before,
                    "after": getattr(target, "temp_hp"),
                    "path": path,
                }
            )
            if source_effect_id is not None and after > before:
                effect = EffectInstance(
                    effect_id=source_effect_id,
                    source_ref=ctx.action.source,
                    source_action_id=ctx.action.id,
                    target_id=target_id,
                    applied_by=ctx.actor_id,
                    condition=None,
                    passive_modifiers={},
                    duration=dict(node.get("duration", {})),
                    tick_on=node.get("tick_on"),
                    concentration=bool(node.get("concentration", False)),
                    stacking_policy=str(node.get("stacking_policy", "replace")),
                    audit={
                        "node_path": path,
                        "temporary_hit_points": after,
                        "temp_hp_source": True,
                    },
                )
                effects = getattr(target, "status_effects")
                if effect.stacking_policy == "replace":
                    effects[:] = [
                        existing
                        for existing in effects
                        if existing.get("source_action_id") != effect.source_action_id
                        or not (
                            isinstance(existing.get("audit"), dict)
                            and existing["audit"].get("temp_hp_source") is True
                        )
                    ]
                effects.append(effect.to_dict())
                ctx.result.state_changes.append(
                    {
                        "type": "temp_hp_duration",
                        "target_id": target_id,
                        "effect_id": effect.effect_id,
                        "duration": effect.duration,
                        "tick_on": effect.tick_on,
                        "path": path,
                    }
                )

    def _node_condition(self, ctx: _Context, node: dict[str, Any], path: str) -> None:
        concentration = bool(node.get("concentration", False))
        self._clear_existing_concentration_if_needed(ctx, concentration, path)
        condition = str(node["condition"])
        passive_modifiers = self._resolved_passive_modifiers(
            ctx,
            dict(node.get("passive_modifiers", {})),
        )
        for target_id in ctx.targets:
            if self._skip_target_for_save_gate(ctx, node, target_id):
                continue
            target = self._entity(target_id)
            immunity_sources = self._condition_immunity_sources(target, condition)
            if immunity_sources:
                ctx.result.state_changes.append(
                    {
                        "type": "condition_immune",
                        "target_id": target_id,
                        "condition": condition,
                        "immunity_sources": immunity_sources,
                        "path": path,
                    }
                )
                continue
            effect = EffectInstance(
                effect_id=self._effect_id(target_id, path),
                source_ref=ctx.action.source,
                source_action_id=ctx.action.id,
                target_id=target_id,
                applied_by=ctx.actor_id,
                condition=condition,
                passive_modifiers=passive_modifiers,
                duration=self._resolved_condition_duration(ctx, node),
                tick_on=node.get("tick_on"),
                concentration=concentration,
                stacking_policy=str(node.get("stacking_policy", "replace")),
                audit={"node_path": path},
            )
            if condition == "exhaustion":
                immunity_sources = self._food_drink_exhaustion_immunity_sources(
                    target, ctx.action.id
                )
                if immunity_sources:
                    ctx.result.state_changes.append(
                        {
                            "type": "condition_immune",
                            "target_id": target_id,
                            "condition": "exhaustion",
                            "immunity_sources": immunity_sources,
                            "path": path,
                        }
                    )
                    continue
                owner = self._persistent_condition_owner(target)
                before_level, after_level, applied_effect = apply_exhaustion(
                    getattr(owner, "status_effects"),
                    effect.to_dict(),
                )
                ctx.result.state_changes.append(
                    {
                        "type": "condition",
                        "target_id": target_id,
                        "condition": "exhaustion",
                        "effect_id": applied_effect.get("effect_id"),
                        "level_before": before_level,
                        "level_after": after_level,
                        "path": path,
                    }
                )
                death_change = self._exhaustion_death_change(
                    target_id,
                    target,
                    owner,
                    after_level,
                    path,
                )
                if death_change is not None:
                    ctx.result.state_changes.append(death_change)
                continue
            condition_owner = (
                self._persistent_condition_owner(target)
                if effect.duration.get("until") == "long_rest"
                else target
            )
            effects = getattr(condition_owner, "status_effects")
            if effect.stacking_policy == "replace":
                effects[:] = [
                    existing
                    for existing in effects
                    if existing.get("condition") != effect.condition
                    or existing.get("source_action_id") != effect.source_action_id
                ]
            elif effect.stacking_policy == "replace_condition":
                effects[:] = [
                    existing
                    for existing in effects
                    if existing.get("condition") != effect.condition
                ]
            effects.append(effect.to_dict())
            ctx.result.state_changes.append(
                {
                    "type": "condition",
                    "target_id": target_id,
                    "condition": effect.condition,
                    "path": path,
                }
            )
            if effect.passive_modifiers:
                ctx.result.state_changes[-1]["passive_modifiers"] = effect.passive_modifiers
            ctx.result.state_changes.extend(
                self._expire_effects_ended_by_condition(target_id, condition, path)
            )

    def _node_remove_condition(self, ctx: _Context, node: dict[str, Any], path: str) -> None:
        conditions = [str(condition) for condition in node.get("conditions", [])]
        effect_markers = [str(marker) for marker in node.get("effect_markers", [])]
        for target_id in ctx.targets:
            removed: dict[str, int] = {}
            removed_markers: dict[str, int] = {}
            removed_owners: list[dict[str, Any]] = []
            for condition in conditions:
                for owner_type, owner_id, effects in self._target_effect_lists(target_id):
                    count = remove_condition(effects, condition)
                    if count:
                        removed[condition] = removed.get(condition, 0) + count
                        removed_owners.append(
                            {
                                "owner_type": owner_type,
                                "owner_id": owner_id,
                                "condition": condition,
                                "count": count,
                            }
                        )
            for marker in effect_markers:
                for owner_type, owner_id, effects in self._target_effect_lists(target_id):
                    count = self._remove_effect_marker(effects, marker)
                    if count:
                        removed_markers[marker] = removed_markers.get(marker, 0) + count
                        removed_owners.append(
                            {
                                "owner_type": owner_type,
                                "owner_id": owner_id,
                                "effect_marker": marker,
                                "count": count,
                            }
                        )
            if removed or removed_markers:
                ctx.result.state_changes.append(
                    {
                        "type": "remove_condition",
                        "target_id": target_id,
                        "removed": removed,
                        "removed_markers": removed_markers,
                        "removed_owners": removed_owners,
                        "path": path,
                    }
                )

    def _node_greater_restoration(self, ctx: _Context, node: dict[str, Any], path: str) -> None:
        choice_param = str(node.get("choice_param", "greater_restoration_choice"))
        if choice_param not in ctx.params:
            raise AutomationError(f"missing required parameter {choice_param}")
        choice = str(ctx.params[choice_param])
        allowed_choices = {str(item) for item in node.get("choices", GREATER_RESTORATION_CHOICES)}
        if choice not in allowed_choices or choice not in GREATER_RESTORATION_CHOICES:
            expected = ", ".join(sorted(allowed_choices & GREATER_RESTORATION_CHOICES))
            raise AutomationError(
                f"unsupported Greater Restoration choice {choice}; choose {expected}"
            )
        for target_id in ctx.targets:
            change = self._greater_restoration_change(target_id, choice, path)
            if change is not None:
                ctx.result.state_changes.append(change)

    def _node_restoring_touch(self, ctx: _Context, node: dict[str, Any], path: str) -> None:
        conditions, total_points, condition_cost, healing_points = self._restoring_touch_plan(
            ctx.action,
            ctx.actor_id,
            ctx.targets,
            ctx.params,
            node,
        )
        for target_id in ctx.targets:
            removed_conditions, removed_owners = self._remove_conditions_for_target(
                target_id,
                conditions,
            )
            ctx.result.state_changes.append(
                {
                    "type": "remove_condition",
                    "target_id": target_id,
                    "removed": removed_conditions,
                    "removed_markers": {},
                    "removed_owners": removed_owners,
                    "path": path,
                    "source_action_id": ctx.action.id,
                    "restoring_touch_conditions": conditions,
                    "restoring_touch_condition_cost": condition_cost,
                    "lay_on_hands_points_spent": total_points,
                    "healing_points": healing_points,
                }
            )
            if healing_points <= 0:
                continue
            applied = self._apply_healing(target_id, healing_points)
            ctx.result.state_changes.append(
                {
                    "type": "healing",
                    "target_id": target_id,
                    "amount": healing_points,
                    "applied": applied,
                    "path": path,
                    "source_action_id": ctx.action.id,
                    "restoring_touch_condition_cost": condition_cost,
                    "lay_on_hands_points_spent": total_points,
                }
            )

    def _greater_restoration_change(
        self,
        target_id: str,
        choice: str,
        path: str,
    ) -> dict[str, Any] | None:
        if choice == "exhaustion":
            removed_exhaustion, removed_owners = self._remove_one_exhaustion_level(target_id)
            if not removed_exhaustion:
                return None
            return {
                "type": "greater_restoration",
                "target_id": target_id,
                "choice": choice,
                "removed": {"exhaustion": removed_exhaustion},
                "removed_markers": {},
                "removed_owners": removed_owners,
                "path": path,
            }
        if choice == "charmed_or_petrified":
            removed_conditions, removed_owners = self._remove_conditions_for_target(
                target_id,
                ["charmed", "petrified"],
            )
            if not removed_conditions:
                return None
            return {
                "type": "greater_restoration",
                "target_id": target_id,
                "choice": choice,
                "removed": removed_conditions,
                "removed_markers": {},
                "removed_owners": removed_owners,
                "path": path,
            }
        if choice == "curse":
            removed_markers, removed_owners = self._remove_effect_markers_for_target(
                target_id,
                ["curse", "cursed_item_attunement"],
            )
            if not removed_markers:
                return None
            return {
                "type": "greater_restoration",
                "target_id": target_id,
                "choice": choice,
                "removed": {},
                "removed_markers": removed_markers,
                "removed_owners": removed_owners,
                "path": path,
            }
        if choice == "ability_score_reduction":
            removed_markers, removed_owners = self._remove_effect_markers_for_target(
                target_id,
                ["ability_score_reduction"],
            )
            if not removed_markers:
                return None
            return {
                "type": "greater_restoration",
                "target_id": target_id,
                "choice": choice,
                "removed": {},
                "removed_markers": removed_markers,
                "removed_owners": removed_owners,
                "path": path,
            }
        if choice == "hp_max_reduction":
            removed_markers, removed_owners, hp_max_restored = self._remove_hp_max_reductions(
                target_id
            )
            if not removed_markers:
                return None
            return {
                "type": "greater_restoration",
                "target_id": target_id,
                "choice": choice,
                "removed": {},
                "removed_markers": removed_markers,
                "removed_owners": removed_owners,
                "hp_max_restored": hp_max_restored,
                "path": path,
            }
        if choice == "contact_other_plane_incapacitation":
            removed_markers, removed_owners = self._remove_effect_markers_for_target(
                target_id,
                ["contact_other_plane_incapacitation"],
            )
            if not removed_markers:
                return None
            return {
                "type": "greater_restoration",
                "target_id": target_id,
                "choice": choice,
                "removed": {},
                "removed_markers": removed_markers,
                "removed_owners": removed_owners,
                "path": path,
            }
        raise AutomationError(f"unsupported Greater Restoration choice {choice}")

    def _remove_one_exhaustion_level(self, target_id: str) -> tuple[int, list[dict[str, Any]]]:
        for owner_type, owner_id, effects in self._target_effect_lists(target_id):
            for index, effect in enumerate(effects):
                if effect.get("condition") != "exhaustion":
                    continue
                level_before = max(1, int(effect.get("level", 1)))
                owner_entry: dict[str, Any] = {
                    "owner_type": owner_type,
                    "owner_id": owner_id,
                    "condition": "exhaustion",
                    "count": 1,
                    "level_before": level_before,
                    "level_after": max(0, level_before - 1),
                }
                if level_before > 1:
                    effect["level"] = level_before - 1
                else:
                    del effects[index]
                return 1, [owner_entry]
        return 0, []

    def _remove_conditions_for_target(
        self,
        target_id: str,
        conditions: list[str],
    ) -> tuple[dict[str, int], list[dict[str, Any]]]:
        removed: dict[str, int] = {}
        removed_owners: list[dict[str, Any]] = []
        for condition in conditions:
            for owner_type, owner_id, effects in self._target_effect_lists(target_id):
                count = remove_condition(effects, condition)
                if count:
                    removed[condition] = removed.get(condition, 0) + count
                    removed_owners.append(
                        {
                            "owner_type": owner_type,
                            "owner_id": owner_id,
                            "condition": condition,
                            "count": count,
                        }
                    )
        return removed, removed_owners

    def _remove_effect_markers_for_target(
        self,
        target_id: str,
        markers: list[str],
    ) -> tuple[dict[str, int], list[dict[str, Any]]]:
        removed_markers: dict[str, int] = {}
        removed_owners: list[dict[str, Any]] = []
        for marker in markers:
            for owner_type, owner_id, effects in self._target_effect_lists(target_id):
                count = self._remove_effect_marker(effects, marker)
                if count:
                    removed_markers[marker] = removed_markers.get(marker, 0) + count
                    removed_owners.append(
                        {
                            "owner_type": owner_type,
                            "owner_id": owner_id,
                            "effect_marker": marker,
                            "count": count,
                        }
                    )
        return removed_markers, removed_owners

    def _remove_hp_max_reductions(
        self,
        target_id: str,
    ) -> tuple[dict[str, int], list[dict[str, Any]], list[dict[str, Any]]]:
        removed_markers: dict[str, int] = {}
        removed_owners: list[dict[str, Any]] = []
        restored_amount = 0
        seen_effect_ids: set[str] = set()
        for owner_type, owner_id, effects in self._target_effect_lists(target_id):
            retained: list[dict[str, Any]] = []
            count = 0
            for effect in effects:
                if not self._effect_has_marker(effect, "hp_max_reduction"):
                    retained.append(effect)
                    continue
                count += 1
                effect_id = effect.get("effect_id")
                if isinstance(effect_id, str) and effect_id in seen_effect_ids:
                    continue
                if isinstance(effect_id, str):
                    seen_effect_ids.add(effect_id)
                restored_amount += self._hp_max_reduction_amount(effect)
            if count:
                effects[:] = retained
                removed_markers["hp_max_reduction"] = (
                    removed_markers.get("hp_max_reduction", 0) + count
                )
                removed_owners.append(
                    {
                        "owner_type": owner_type,
                        "owner_id": owner_id,
                        "effect_marker": "hp_max_reduction",
                        "count": count,
                    }
                )
        if not removed_markers:
            return {}, [], []
        hp_max_restored = self._restore_hp_max_for_target(target_id, restored_amount)
        return removed_markers, removed_owners, hp_max_restored

    @staticmethod
    def _hp_max_reduction_amount(effect: dict[str, Any]) -> int:
        candidates: list[Any] = [effect.get("hp_max_reduction")]
        for effect_field in ("passive_modifiers", "metadata", "audit"):
            value = effect.get(effect_field)
            if isinstance(value, dict):
                candidates.append(value.get("hp_max_reduction"))
        for candidate in candidates:
            if isinstance(candidate, int) and not isinstance(candidate, bool) and candidate > 0:
                return candidate
        return 0

    def _restore_hp_max_for_target(self, target_id: str, amount: int) -> list[dict[str, Any]]:
        if amount <= 0:
            return []
        restored: list[dict[str, Any]] = []
        seen: set[int] = set()

        def add_entity(owner_type: str, owner_id: str, entity: Any) -> None:
            entity_identity = id(entity)
            if entity_identity in seen or not hasattr(entity, "hp_max"):
                return
            seen.add(entity_identity)
            hp_max_before = int(getattr(entity, "hp_max"))
            hp_current_before = int(getattr(entity, "hp_current", 0))
            hp_max_after = hp_max_before + amount
            setattr(entity, "hp_max", hp_max_after)
            restored.append(
                {
                    "owner_type": owner_type,
                    "owner_id": owner_id,
                    "amount": amount,
                    "hp_max_before": hp_max_before,
                    "hp_max_after": hp_max_after,
                    "hp_current_before": hp_current_before,
                    "hp_current_after": int(getattr(entity, "hp_current", hp_current_before)),
                }
            )

        if target_id in self.state.characters:
            add_entity("character", target_id, self.state.characters[target_id])
        if target_id in self.state.monsters:
            add_entity("monster", target_id, self.state.monsters[target_id])
        if self.state.encounter is not None and target_id in self.state.encounter.combatants:
            combatant = self.state.encounter.combatants[target_id]
            add_entity("combatant", target_id, combatant)
            if combatant.entity_id in self.state.characters:
                add_entity(
                    "character", combatant.entity_id, self.state.characters[combatant.entity_id]
                )
            if combatant.entity_id in self.state.monsters:
                add_entity("monster", combatant.entity_id, self.state.monsters[combatant.entity_id])
        return restored

    @staticmethod
    def _remove_effect_marker(effects: list[dict[str, Any]], marker: str) -> int:
        before = len(effects)
        effects[:] = [
            effect
            for effect in effects
            if not AutomationExecutor._effect_has_marker(effect, marker)
        ]
        return before - len(effects)

    @staticmethod
    def _effect_has_marker(effect: dict[str, Any], marker: str) -> bool:
        if effect.get(marker) is True:
            return True
        for marker_field in ("passive_modifiers", "metadata", "audit"):
            value = effect.get(marker_field, {})
            if isinstance(value, dict) and value.get(marker) is True:
                return True
        markers = effect.get("effect_markers", [])
        return isinstance(markers, list) and marker in {str(item) for item in markers}

    def _node_passive_effect(self, ctx: _Context, node: dict[str, Any], path: str) -> None:
        concentration = bool(node.get("concentration", False))
        passive_modifiers = self._resolved_passive_modifiers(ctx, dict(node["passive_modifiers"]))
        duration = self._resolved_effect_duration(ctx, node)
        clears_concentration = passive_modifiers.get("clear_existing_concentration") is True
        self._clear_existing_concentration_if_needed(
            ctx, concentration or clears_concentration, path
        )
        for target_id in ctx.targets:
            if self._skip_target_for_save_gate(ctx, node, target_id):
                continue
            target_modifiers = dict(passive_modifiers)
            target_duration = dict(duration)
            persistent_rage_change = self._apply_persistent_rage_if_available(
                ctx,
                node,
                target_id,
                target_modifiers,
                target_duration,
                path,
            )
            mindless_rage_change = self._apply_mindless_rage_if_available(
                ctx,
                node,
                target_id,
                target_modifiers,
                path,
            )
            effect = EffectInstance(
                effect_id=self._effect_id(target_id, path),
                source_ref=ctx.action.source,
                source_action_id=ctx.action.id,
                target_id=target_id,
                applied_by=ctx.actor_id,
                condition=node.get("condition"),
                passive_modifiers=target_modifiers,
                duration=target_duration,
                tick_on=node.get("tick_on"),
                concentration=concentration,
                stacking_policy=str(node.get("stacking_policy", "replace")),
                audit={"node_path": path},
            )
            effect_lists = (
                self._target_effect_lists(target_id) if node.get("persistent") is True else []
            )
            if not effect_lists:
                target = self._entity(target_id)
                effect_lists = [("entity", target_id, getattr(target, "status_effects"))]
            owners: list[dict[str, str]] = []
            for owner_type, owner_id, effects in effect_lists:
                if effect.stacking_policy == "replace":
                    effects[:] = [
                        existing
                        for existing in effects
                        if existing.get("source_action_id") != effect.source_action_id
                        or existing.get("condition") != effect.condition
                        or (
                            isinstance(existing.get("audit"), dict)
                            and existing["audit"].get("temp_hp_source") is True
                        )
                    ]
                elif effect.stacking_policy == "replace_condition":
                    effects[:] = [
                        existing
                        for existing in effects
                        if existing.get("condition") != effect.condition
                    ]
                effects.append(effect.to_dict())
                owners.append({"owner_type": owner_type, "owner_id": owner_id})
            ctx.result.state_changes.append(
                {
                    "type": "passive_effect",
                    "target_id": target_id,
                    "effect_id": effect.effect_id,
                    "condition": effect.condition,
                    "passive_modifiers": effect.passive_modifiers,
                    "duration": effect.duration,
                    "persistent": node.get("persistent") is True,
                    "owners": owners,
                    "path": path,
                }
            )
            if mindless_rage_change is not None:
                ctx.result.state_changes.append(mindless_rage_change)
            if persistent_rage_change is not None:
                ctx.result.state_changes.append(persistent_rage_change)

    def _node_repeat_use_save_before_long_rest(
        self,
        ctx: _Context,
        node: dict[str, Any],
        path: str,
    ) -> None:
        marker = str(node["marker"])
        ability = str(node["ability"]).lower()
        failure_condition = str(node.get("failure_condition", "exhaustion"))
        dc, dc_source = self._resolve_node_dc(ctx, node)
        for target_id in ctx.targets:
            target = self._entity(target_id)
            owner = self._persistent_condition_owner(target)
            owner_effects = getattr(owner, "status_effects")
            had_prior_use = any(self._effect_has_marker(effect, marker) for effect in owner_effects)
            save_entry: dict[str, Any] | None = None
            condition_entry: dict[str, Any] | None = None
            if had_prior_use:
                base_bonus, proficient, _ = self._saving_throw_bonus(target, ability)
                target_exhaustion_level, exhaustion_penalty = self._exhaustion_details(target)
                bonus = base_bonus - exhaustion_penalty
                status_advantage, status_sources = self._saving_throw_status_advantage(
                    target,
                    ability,
                )
                roll = self.roll_service.roll(d20_expression(bonus), advantage=status_advantage)
                ctx.result.dice_rolls.append(roll.to_dict())
                success = roll.total >= dc
                save_entry = {
                    "target_id": target_id,
                    "ability": ability,
                    "dc": dc,
                    "dc_source": dc_source,
                    "bonus": bonus,
                    "base_bonus": base_bonus,
                    "proficient": proficient,
                    "exhaustion_level": target_exhaustion_level,
                    "d20_penalty": exhaustion_penalty,
                    "status_advantage": status_advantage,
                    "status_sources": status_sources,
                    "total": roll.total,
                    "success": success,
                }
                if not success and failure_condition == "exhaustion":
                    effect = EffectInstance(
                        effect_id=self._effect_id(target_id, f"{path}.failure"),
                        source_ref=ctx.action.source,
                        source_action_id=ctx.action.id,
                        target_id=target_id,
                        applied_by=ctx.actor_id,
                        condition="exhaustion",
                        audit={"node_path": path, "repeat_use_marker": marker},
                    )
                    before_level, after_level, applied_effect = apply_exhaustion(
                        owner_effects,
                        effect.to_dict(),
                    )
                    condition_entry = {
                        "type": "condition",
                        "target_id": target_id,
                        "condition": "exhaustion",
                        "effect_id": applied_effect.get("effect_id"),
                        "level_before": before_level,
                        "level_after": after_level,
                        "path": path,
                    }
                    ctx.result.state_changes.append(condition_entry)
                    death_change = self._exhaustion_death_change(
                        target_id,
                        target,
                        owner,
                        after_level,
                        path,
                    )
                    if death_change is not None:
                        ctx.result.state_changes.append(death_change)
                elif not success:
                    raise AutomationError(
                        f"unsupported repeat use failure condition {failure_condition}"
                    )
            owner_effects[:] = [
                effect for effect in owner_effects if not self._effect_has_marker(effect, marker)
            ]
            marker_effect = EffectInstance(
                effect_id=self._effect_id(target_id, f"{path}.marker"),
                source_ref=ctx.action.source,
                source_action_id=ctx.action.id,
                target_id=target_id,
                applied_by=ctx.actor_id,
                passive_modifiers={marker: True},
                duration={"until": "long_rest"},
                stacking_policy="replace",
                audit={"node_path": path, "long_rest_marker": True},
            ).to_dict()
            owner_effects.append(marker_effect)
            marker_entry = {
                "type": "repeat_use_marker",
                "target_id": target_id,
                "effect_id": marker_effect["effect_id"],
                "marker": marker,
                "had_prior_use": had_prior_use,
                "duration": marker_effect["duration"],
                "path": path,
            }
            ctx.result.state_changes.append(marker_entry)
            ctx.result.node_results[path] = {
                "target_id": target_id,
                "marker": marker,
                "had_prior_use": had_prior_use,
                "saving_throw": save_entry,
                "condition": condition_entry,
            }

    def _node_rod_of_absorption_initialize(
        self,
        ctx: _Context,
        node: dict[str, Any],
        path: str,
    ) -> None:
        actor = self._resource_owner(ctx.actor_id)
        if not isinstance(actor, Character):
            raise AutomationError("Rod of Absorption requires a character owner")
        if int(actor.resources.get(ROD_OF_ABSORPTION_INITIALIZED_RESOURCE, 0)) > 0:
            raise AutomationError("Rod of Absorption energy is already initialized")
        roll = self.roll_service.roll(str(node["stored_energy_roll"]))
        ctx.result.dice_rolls.append(roll.to_dict())
        stored_before = int(actor.resources.get(ROD_OF_ABSORPTION_STORED_LEVELS_RESOURCE, 0))
        lifetime_before = int(actor.resources.get(ROD_OF_ABSORPTION_LIFETIME_ABSORBED_RESOURCE, 0))
        actor.resources[ROD_OF_ABSORPTION_STORED_LEVELS_RESOURCE] = roll.total
        actor.resources[ROD_OF_ABSORPTION_LIFETIME_ABSORBED_RESOURCE] = roll.total
        actor.resources[ROD_OF_ABSORPTION_INITIALIZED_RESOURCE] = 1
        change = {
            "type": "rod_of_absorption_initialized",
            "actor_id": ctx.actor_id,
            "stored_levels_before": stored_before,
            "stored_levels_after": roll.total,
            "lifetime_absorbed_levels_before": lifetime_before,
            "lifetime_absorbed_levels_after": roll.total,
            "roll": roll.to_dict(),
            "path": path,
        }
        ctx.result.state_changes.append(change)
        ctx.result.node_results[path] = {
            "stored_levels": roll.total,
            "lifetime_absorbed_levels": roll.total,
        }

    def _node_rod_of_absorption_absorb_spell(
        self,
        ctx: _Context,
        node: dict[str, Any],
        path: str,
    ) -> None:
        actor = self._resource_owner(ctx.actor_id)
        if not isinstance(actor, Character):
            raise AutomationError("Rod of Absorption requires a character owner")
        spell_level = self._rod_of_absorption_absorbed_spell_level(ctx.params, node)
        self._validate_rod_of_absorption_spell_can_be_absorbed(
            actor,
            spell_level=spell_level,
            targeting_only_you=self._required_bool_param(
                ctx.params,
                str(node["targeting_only_you_param"]),
            ),
            creates_area_of_effect=self._required_bool_param(
                ctx.params,
                str(node["creates_area_of_effect_param"]),
            ),
        )
        stored_before = int(actor.resources.get(ROD_OF_ABSORPTION_STORED_LEVELS_RESOURCE, 0))
        lifetime_before = int(actor.resources.get(ROD_OF_ABSORPTION_LIFETIME_ABSORBED_RESOURCE, 0))
        actor.resources[ROD_OF_ABSORPTION_STORED_LEVELS_RESOURCE] = stored_before + spell_level
        actor.resources[ROD_OF_ABSORPTION_LIFETIME_ABSORBED_RESOURCE] = (
            lifetime_before + spell_level
        )
        actor.resources[ROD_OF_ABSORPTION_INITIALIZED_RESOURCE] = 1
        change = {
            "type": "rod_of_absorption_spell_absorbed",
            "actor_id": ctx.actor_id,
            "absorbed_spell_level": spell_level,
            "spell_effect_canceled": True,
            "caster_resources_wasted": True,
            "stored_levels_before": stored_before,
            "stored_levels_after": stored_before + spell_level,
            "lifetime_absorbed_levels_before": lifetime_before,
            "lifetime_absorbed_levels_after": lifetime_before + spell_level,
            "path": path,
        }
        ctx.result.state_changes.append(change)
        ctx.result.node_results[path] = {
            "absorbed_spell_level": spell_level,
            "stored_levels": stored_before + spell_level,
            "lifetime_absorbed_levels": lifetime_before + spell_level,
            "spell_effect_canceled": True,
        }

    def _rod_of_absorption_absorbed_spell_level(
        self,
        params: dict[str, Any],
        node: dict[str, Any],
    ) -> int:
        param_name = str(node.get("spell_level_param", "absorbed_spell_level"))
        spell_level = self._required_int_param(params, param_name)
        if spell_level < 0 or spell_level > 9:
            raise AutomationError("Rod of Absorption absorbed spell level must be 0-9")
        return spell_level

    def _node_rod_of_alertness_protective_aura(
        self,
        ctx: _Context,
        node: dict[str, Any],
        path: str,
    ) -> None:
        actor = self._resource_owner(ctx.actor_id)
        if not isinstance(actor, Character):
            raise AutomationError("Rod of Alertness requires a character owner")
        used_before = int(actor.resources.get(ROD_OF_ALERTNESS_PROTECTIVE_AURA_USED_RESOURCE, 0))
        if used_before > 0:
            raise AutomationError(
                "Rod of Alertness Protective Aura can't be used again until the next dawn"
            )
        actor.resources[ROD_OF_ALERTNESS_PROTECTIVE_AURA_USED_RESOURCE] = 1
        bright_radius = int(node["bright_light_radius_ft"])
        dim_radius = int(node["dim_light_additional_ft"])
        duration = dict(
            node.get("duration", {"until": "duration_10_minutes_or_magic_action_to_remove"})
        )
        metadata = {
            "item_planted_in_ground": True,
            "bright_light_radius_ft": bright_radius,
            "dim_light_additional_ft": dim_radius,
            "allies_in_bright_light_armor_class_bonus": 1,
            "allies_in_bright_light_saving_throw_bonus": 1,
            "sense_invisible_creature_locations_in_same_bright_light": True,
            "ends_when_removed_by_magic_action": True,
            "reset_trigger": "next_dawn",
        }
        metadata.update(dict(node.get("metadata", {})))
        world_effect = {
            "effect_id": f"world-effect-{self.state.event_counter}-{len(self.state.world.active_effects)}",
            "source_ref": ctx.action.source,
            "source_action_id": ctx.action.id,
            "applied_by": ctx.actor_id,
            "effect_type": "rod_of_alertness_protective_aura",
            "concentration": False,
            "scope": {
                "target": "ground_at_actor",
                "actor_id": ctx.actor_id,
                "bright_light_radius_ft": bright_radius,
                "dim_light_additional_ft": dim_radius,
            },
            "duration": duration,
            "metadata": metadata,
            "audit": {"node_path": path},
        }
        self.state.world.active_effects.append(world_effect)

        target_ids = sorted({ctx.actor_id, *ctx.targets})
        passive_modifiers = dict(node["passive_modifiers"])
        passive_changes: list[dict[str, Any]] = []
        for target_id in target_ids:
            target = self._entity(target_id)
            effect = EffectInstance(
                effect_id=self._effect_id(target_id, path),
                source_ref=ctx.action.source,
                source_action_id=ctx.action.id,
                target_id=target_id,
                applied_by=ctx.actor_id,
                passive_modifiers=passive_modifiers,
                duration=duration,
                tick_on=node.get("tick_on", "aura"),
                stacking_policy=str(node.get("stacking_policy", "replace")),
                audit={
                    "node_path": path,
                    "requires_rod_of_alertness_bright_light": True,
                },
            )
            effects = getattr(target, "status_effects")
            if effect.stacking_policy == "replace":
                effects[:] = [
                    existing
                    for existing in effects
                    if existing.get("source_action_id") != effect.source_action_id
                    or existing.get("condition") != effect.condition
                ]
            elif effect.stacking_policy == "replace_condition":
                effects[:] = [
                    existing
                    for existing in effects
                    if existing.get("condition") != effect.condition
                ]
            effects.append(effect.to_dict())
            passive_changes.append(
                {
                    "type": "passive_effect",
                    "target_id": target_id,
                    "effect_id": effect.effect_id,
                    "condition": effect.condition,
                    "passive_modifiers": effect.passive_modifiers,
                    "duration": effect.duration,
                    "path": path,
                }
            )

        ctx.result.state_changes.append(
            {
                "type": "rod_of_alertness_protective_aura",
                "actor_id": ctx.actor_id,
                "resource": ROD_OF_ALERTNESS_PROTECTIVE_AURA_USED_RESOURCE,
                "before": used_before,
                "after": 1,
                "world_effect_id": world_effect["effect_id"],
                "bright_light_radius_ft": bright_radius,
                "dim_light_additional_ft": dim_radius,
                "affected_target_ids": target_ids,
                "path": path,
            }
        )
        ctx.result.state_changes.append(
            {
                "type": "world_effect",
                "effect_id": world_effect["effect_id"],
                "effect_type": world_effect["effect_type"],
                "concentration": world_effect["concentration"],
                "scope": world_effect["scope"],
                "path": path,
            }
        )
        ctx.result.state_changes.extend(passive_changes)
        ctx.result.node_results[path] = {
            "resource": ROD_OF_ALERTNESS_PROTECTIVE_AURA_USED_RESOURCE,
            "resource_before": used_before,
            "resource_after": 1,
            "world_effect_id": world_effect["effect_id"],
            "affected_target_ids": target_ids,
        }

    def _node_robe_of_useful_items_initialize(
        self,
        ctx: _Context,
        node: dict[str, Any],
        path: str,
    ) -> None:
        actor = self._resource_owner(ctx.actor_id)
        if not isinstance(actor, Character):
            raise AutomationError("Robe of Useful Items requires a character owner")
        if int(actor.resources.get(ROBE_OF_USEFUL_ITEMS_INITIALIZED_RESOURCE, 0)) > 0:
            raise AutomationError("Robe of Useful Items patches are already initialized")
        patch_counts: dict[str, int] = {}
        fixed_patches = node.get("fixed_patches", {})
        if not isinstance(fixed_patches, dict):
            raise AutomationError("Robe of Useful Items fixed_patches must be an object")
        for patch_key, count in fixed_patches.items():
            amount = int(count)
            if amount <= 0:
                continue
            normalized = str(patch_key)
            patch_counts[normalized] = patch_counts.get(normalized, 0) + amount

        extra_roll = self.roll_service.roll(str(node["extra_patch_roll"]))
        ctx.result.dice_rolls.append(extra_roll.to_dict())
        random_rolls: list[dict[str, Any]] = []
        for _ in range(extra_roll.total):
            table_roll = self.roll_service.roll("1d100")
            ctx.result.dice_rolls.append(table_roll.to_dict())
            patch_key = self._robe_of_useful_items_patch_for_roll(
                table_roll.total,
                node.get("extra_patch_table", []),
            )
            patch_counts[patch_key] = patch_counts.get(patch_key, 0) + 1
            random_rolls.append({"roll": table_roll.total, "patch": patch_key})

        resource_changes: list[dict[str, Any]] = []
        for patch_key, amount in sorted(patch_counts.items()):
            resource = self._robe_of_useful_items_patch_resource(patch_key)
            before = int(actor.resources.get(resource, 0))
            after = before + amount
            actor.resources[resource] = after
            resource_changes.append(
                {
                    "resource": resource,
                    "patch": patch_key,
                    "before": before,
                    "after": after,
                    "amount": amount,
                }
            )
        actor.resources[ROBE_OF_USEFUL_ITEMS_INITIALIZED_RESOURCE] = 1
        ctx.result.state_changes.append(
            {
                "type": "robe_of_useful_items_initialized",
                "actor_id": ctx.actor_id,
                "fixed_patches": dict(sorted(fixed_patches.items())),
                "extra_patch_roll": extra_roll.total,
                "random_rolls": random_rolls,
                "patch_counts": dict(sorted(patch_counts.items())),
                "resource_changes": resource_changes,
                "path": path,
            }
        )
        ctx.result.node_results[path] = {
            "extra_patch_count": extra_roll.total,
            "random_rolls": random_rolls,
            "patch_counts": dict(sorted(patch_counts.items())),
        }

    def _node_robe_of_useful_items_patch(
        self,
        ctx: _Context,
        node: dict[str, Any],
        path: str,
    ) -> None:
        actor = self._resource_owner(ctx.actor_id)
        if not isinstance(actor, Character):
            raise AutomationError("Robe of Useful Items requires a character owner")
        patch_param = str(node.get("patch_param", "robe_of_useful_items_patch"))
        patch_key = str(ctx.params.get(patch_param, "")).lower()
        patches = node.get("patches", {})
        if patch_key not in patches:
            raise AutomationError("Robe of Useful Items patch is not in the SRD patch table")
        resource = self._robe_of_useful_items_patch_resource(patch_key)
        before_patch = int(actor.resources.get(resource, 0))
        if before_patch <= 0:
            raise AutomationError(f"Robe of Useful Items patch {patch_key} is unavailable")
        actor.resources[resource] = before_patch - 1
        outcome = patches[patch_key]
        if not isinstance(outcome, dict):
            raise AutomationError("Robe of Useful Items patch outcome must be an object")
        change: dict[str, Any] = {
            "type": "robe_of_useful_items_patch",
            "actor_id": ctx.actor_id,
            "patch": patch_key,
            "resource": resource,
            "before": before_patch,
            "after": before_patch - 1,
            "path": path,
        }
        generated: list[dict[str, Any]] = []
        generated.extend(self._apply_robe_of_useful_items_gold(actor, ctx, outcome, patch_key))
        generated.extend(self._apply_robe_of_useful_items_items(actor, ctx, outcome, patch_key))
        generated.extend(
            self._apply_robe_of_useful_items_world_effect(ctx, outcome, patch_key, path)
        )
        change["generated"] = generated
        ctx.result.state_changes.append(change)
        depleted = self._deplete_robe_of_useful_items_if_empty(actor, ctx.actor_id)
        if depleted is not None:
            ctx.result.state_changes.append(depleted)
        ctx.result.node_results[path] = {
            "patch": patch_key,
            "generated": generated,
            "robe_depleted": depleted is not None,
        }

    @staticmethod
    def _robe_of_useful_items_patch_resource(patch_key: str) -> str:
        return f"{ROBE_OF_USEFUL_ITEMS_PATCH_PREFIX}{patch_key}"

    @staticmethod
    def _robe_of_useful_items_patch_for_roll(roll: int, table: Any) -> str:
        if not isinstance(table, list):
            raise AutomationError("Robe of Useful Items patch table must be a list")
        for entry in table:
            if not isinstance(entry, dict):
                continue
            minimum = int(entry.get("min", 0))
            maximum = int(entry.get("max", 0))
            if minimum <= roll <= maximum:
                patch = entry.get("patch")
                if not isinstance(patch, str) or not patch:
                    raise AutomationError("Robe of Useful Items table entry is missing patch")
                return patch
        raise AutomationError(f"Robe of Useful Items d100 roll {roll} is outside the table")

    def _apply_robe_of_useful_items_gold(
        self,
        actor: Character,
        ctx: _Context,
        outcome: dict[str, Any],
        patch_key: str,
    ) -> list[dict[str, Any]]:
        gold = outcome.get("gold")
        if not isinstance(gold, int) or isinstance(gold, bool) or gold <= 0:
            return []
        before = actor.gold
        actor.gold = before + gold
        return [
            {
                "type": "gold",
                "actor_id": ctx.actor_id,
                "patch": patch_key,
                "amount": gold,
                "before": before,
                "after": actor.gold,
            }
        ]

    def _apply_robe_of_useful_items_items(
        self,
        actor: Character,
        ctx: _Context,
        outcome: dict[str, Any],
        patch_key: str,
    ) -> list[dict[str, Any]]:
        items = outcome.get("items", [])
        if not isinstance(items, list):
            raise AutomationError("Robe of Useful Items outcome items must be a list")
        generated: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                raise AutomationError("Robe of Useful Items item outcome must be an object")
            item_id = str(item["item_id"])
            quantity = int(item.get("quantity", 1))
            before = int(actor.inventory.get(item_id, 0))
            actor.inventory[item_id] = before + quantity
            entry: dict[str, Any] = {
                "type": "item",
                "actor_id": ctx.actor_id,
                "patch": patch_key,
                "item_id": item_id,
                "quantity": quantity,
                "before": before,
                "after": actor.inventory[item_id],
            }
            metadata = item.get("metadata")
            if isinstance(metadata, dict):
                entry["metadata"] = metadata
            generated.append(entry)
        return generated

    def _apply_robe_of_useful_items_world_effect(
        self,
        ctx: _Context,
        outcome: dict[str, Any],
        patch_key: str,
        path: str,
    ) -> list[dict[str, Any]]:
        world_effect = outcome.get("world_effect")
        if world_effect is None:
            return []
        if not isinstance(world_effect, dict):
            raise AutomationError("Robe of Useful Items world_effect must be an object")
        metadata = dict(world_effect.get("metadata", {}))
        metadata["patch"] = patch_key
        effect = {
            "effect_id": f"world-effect-{self.state.event_counter}-{len(self.state.world.active_effects)}",
            "source_ref": ctx.action.source,
            "source_action_id": ctx.action.id,
            "applied_by": ctx.actor_id,
            "effect_type": str(world_effect["effect_type"]),
            "concentration": False,
            "scope": dict(world_effect.get("scope", {"zone_id": self.state.world.current_zone_id})),
            "duration": dict(world_effect.get("duration", {})),
            "metadata": metadata,
            "audit": {"node_path": path, "robe_of_useful_items_patch": patch_key},
        }
        self.state.world.active_effects.append(effect)
        return [
            {
                "type": "world_effect",
                "effect_id": effect["effect_id"],
                "effect_type": effect["effect_type"],
                "patch": patch_key,
                "scope": effect["scope"],
                "metadata": metadata,
            }
        ]

    def _deplete_robe_of_useful_items_if_empty(
        self,
        actor: Character,
        actor_id: str,
    ) -> dict[str, Any] | None:
        remaining = sum(
            int(amount)
            for resource, amount in actor.resources.items()
            if resource.startswith(ROBE_OF_USEFUL_ITEMS_PATCH_PREFIX)
        )
        if remaining > 0:
            return None
        item_id = "srd.robe_of_useful_items"
        before = int(actor.inventory.get(item_id, 0))
        if before > 0:
            actor.inventory[item_id] = max(0, before - 1)
        actor.resources[ROBE_OF_USEFUL_ITEMS_INITIALIZED_RESOURCE] = 0
        return {
            "type": "robe_of_useful_items_depleted",
            "actor_id": actor_id,
            "item_id": item_id,
            "remaining_patches": 0,
            "inventory_before": before,
            "inventory_after": int(actor.inventory.get(item_id, 0)),
        }

    def _resolved_effect_duration(self, ctx: _Context, node: dict[str, Any]) -> dict[str, Any]:
        duration = dict(node.get("duration", {}))
        duration = self._resolved_duration_from_slot(ctx, duration)
        duration = self._resolved_duration_from_param(ctx, duration)
        duration = self._resolved_duration_repeat_save(ctx, duration)
        duration_roll = node.get("duration_roll")
        if not isinstance(duration_roll, dict):
            return duration
        dice = str(duration_roll["dice"])
        unit = str(duration_roll.get("unit", ""))
        ticks_per_unit = int(duration_roll["ticks_per_unit"])
        roll = self.roll_service.roll(dice)
        ctx.result.dice_rolls.append(roll.to_dict())
        duration["duration_roll"] = {
            "dice": dice,
            "unit": unit,
            "roll_id": roll.roll_id,
            "rolled": roll.total,
            "ticks_per_unit": ticks_per_unit,
        }
        duration["remaining_ticks"] = roll.total * ticks_per_unit
        return duration

    def _resolved_condition_duration(self, ctx: _Context, node: dict[str, Any]) -> dict[str, Any]:
        duration = dict(node.get("duration", {}))
        duration = self._resolved_duration_from_slot(ctx, duration)
        duration = self._resolved_duration_from_param(ctx, duration)
        duration = self._resolved_duration_repeat_save(ctx, duration)
        return duration

    def _resolved_duration_repeat_save(
        self,
        ctx: _Context,
        duration: dict[str, Any],
    ) -> dict[str, Any]:
        repeat_save = duration.get("repeat_save")
        if not isinstance(repeat_save, dict):
            return duration
        resolved_repeat_save = dict(repeat_save)
        dc_from = resolved_repeat_save.pop("dc_from", None)
        if dc_from is not None:
            dc, dc_source = self._resolve_dynamic_dc(ctx, dc_from)
            resolved_repeat_save["dc"] = dc
            resolved_repeat_save["dc_source"] = dc_source
        failure_damage = resolved_repeat_save.get("failure_damage")
        if isinstance(failure_damage, dict):
            resolved_repeat_save["failure_damage"] = self._resolved_repeat_save_failure_damage(
                ctx,
                failure_damage,
            )
        duration["repeat_save"] = resolved_repeat_save
        return duration

    def _resolved_repeat_save_failure_damage(
        self,
        ctx: _Context,
        failure_damage: dict[str, Any],
    ) -> dict[str, Any]:
        damage = dict(failure_damage)
        if "dice" in damage:
            damage["dice"] = self._scaled_dice_expression(ctx, damage)
        return {
            "dice": str(damage["dice"]),
            "damage_type": str(damage["damage_type"]),
        }

    def _resolved_duration_from_slot(
        self,
        ctx: _Context,
        duration: dict[str, Any],
    ) -> dict[str, Any]:
        spec = duration.pop("duration_from_slot", None)
        if spec is None:
            return duration
        if not isinstance(spec, dict):
            raise AutomationError("duration_from_slot must be an object")
        by_slot = spec.get("by_slot_level", {})
        if not isinstance(by_slot, dict):
            raise AutomationError("duration_from_slot.by_slot_level must be an object")
        slot_level = self._spell_slot_level_to_spend(ctx.action, ctx.params)
        scaled_until = by_slot.get(str(slot_level))
        if scaled_until is not None:
            duration["until"] = str(scaled_until)
        return duration

    def _resolved_duration_from_param(
        self,
        ctx: _Context,
        duration: dict[str, Any],
    ) -> dict[str, Any]:
        spec = duration.pop("duration_from_param", None)
        if spec is None:
            return duration
        if not isinstance(spec, dict):
            raise AutomationError("duration_from_param must be an object")
        param_name = str(spec.get("param", ""))
        if not param_name:
            raise AutomationError("duration_from_param.param must be a string")
        by_value = spec.get("by_value", {})
        if not isinstance(by_value, dict):
            raise AutomationError("duration_from_param.by_value must be an object")
        selected = ctx.params.get(param_name)
        if selected is None:
            raise AutomationError(f"missing required parameter {param_name}")
        if isinstance(selected, dict):
            raise AutomationError(f"parameter {param_name} must be a scalar or one-item list")
        if isinstance(selected, list):
            if len(selected) != 1:
                raise AutomationError(f"parameter {param_name} must contain exactly one choice")
            selected = selected[0]
        if isinstance(selected, (dict, list)):
            raise AutomationError(f"parameter {param_name} must be a scalar")
        normalized = str(selected).casefold().strip()
        resolved_until = by_value.get(normalized)
        if resolved_until is None:
            expected = ", ".join(sorted(str(key) for key in by_value))
            raise AutomationError(f"{param_name} must map to one of: {expected}")
        duration["until"] = str(resolved_until)
        return duration

    def _resolved_passive_modifiers(
        self,
        ctx: _Context,
        modifiers: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            key: self._resolved_passive_modifier_value(ctx, value)
            for key, value in modifiers.items()
        }

    def _resolved_passive_modifier_value(self, ctx: _Context, value: Any) -> Any:
        if isinstance(value, dict) and set(value) == {"param"}:
            param_name = str(value["param"])
            selected = ctx.params.get(param_name)
            if selected is None:
                raise AutomationError(f"missing required parameter {param_name}")
            if isinstance(selected, (dict, list)):
                raise AutomationError(f"parameter {param_name} must be a scalar")
            return str(selected)
        if isinstance(value, dict) and set(value) == {"param_list"}:
            param_name = str(value["param_list"])
            selected = ctx.params.get(param_name)
            if selected is None:
                raise AutomationError(f"missing required parameter {param_name}")
            if isinstance(selected, dict):
                raise AutomationError(f"parameter {param_name} must be a list")
            if isinstance(selected, list):
                if not selected:
                    raise AutomationError(f"parameter {param_name} must not be empty")
                return [str(item) for item in selected]
            return [str(selected)]
        if isinstance(value, dict) and set(value) == {"slot_scaled"}:
            spec = value["slot_scaled"]
            if not isinstance(spec, dict):
                raise AutomationError("slot_scaled passive modifier must be an object")
            base_value = int(spec["base_value"])
            base_slot_level = int(
                spec.get("base_spell_slot_level", ctx.action.cost.spell_slot_level or 0)
            )
            value_per_slot = int(spec.get("value_per_slot_above", 1))
            slot_level = self._spell_slot_level_to_spend(ctx.action, ctx.params)
            return base_value + max(0, slot_level - base_slot_level) * value_per_slot
        if not isinstance(value, dict) or "class_level_die" not in value:
            return value
        class_name = str(value["class_level_die"])
        owner = self._resource_owner(ctx.actor_id)
        class_levels = getattr(owner, "class_levels", {})
        if not isinstance(class_levels, dict):
            return str(value.get("default", "d6"))
        class_level = int(class_levels.get(class_name, 0))
        die = str(value.get("default", "d6"))
        tiers = value.get("tiers", [])
        if isinstance(tiers, list):
            for tier in tiers:
                if not isinstance(tier, dict):
                    continue
                if class_level >= int(tier.get("level", 0)):
                    die = str(tier.get("die", die))
        return die

    def _slot_scaled_metadata(self, ctx: _Context, node: dict[str, Any]) -> dict[str, int]:
        metadata_from_slot = node.get("metadata_from_slot", {})
        if not isinstance(metadata_from_slot, dict):
            raise AutomationError("metadata_from_slot must be an object")
        resolved: dict[str, int] = {}
        for key, spec in metadata_from_slot.items():
            if not isinstance(spec, dict):
                raise AutomationError("metadata_from_slot entries must be objects")
            base_slot_level = int(
                spec.get("base_spell_slot_level", ctx.action.cost.spell_slot_level or 0)
            )
            base_value = int(spec["base_value"])
            per_slot = int(spec.get("value_per_slot_above", 1))
            slot_level = self._spell_slot_level_to_spend(ctx.action, ctx.params)
            resolved[str(key)] = base_value + max(0, slot_level - base_slot_level) * per_slot
        return resolved

    def _resolved_world_metadata(
        self,
        ctx: _Context,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            key: self._resolved_passive_modifier_value(ctx, value)
            for key, value in metadata.items()
        }

    @staticmethod
    def _skip_target_for_save_gate(
        ctx: _Context,
        node: dict[str, Any],
        target_id: str,
    ) -> bool:
        if (
            bool(node.get("requires_failed_save", False))
            and ctx.save_successes.get(target_id) is not False
        ):
            return True
        return bool(node.get("requires_successful_save", False)) and (
            ctx.save_successes.get(target_id) is not True
        )

    def _effect_id(self, target_id: str, path: str) -> str:
        safe_path = re.sub(r"[^a-zA-Z0-9]+", "-", path).strip("-") or "effect"
        return f"effect-{self.state.event_counter}-{target_id}-{safe_path}"

    def _node_world_effect(self, ctx: _Context, node: dict[str, Any], path: str) -> None:
        concentration = self._node_requires_concentration(node)
        self._clear_existing_concentration_if_needed(ctx, concentration, path)
        scope = dict(node.get("scope", {"zone_id": self.state.world.current_zone_id}))
        if scope.get("target") == "explicit":
            scope["target_ids"] = list(ctx.targets)
            if len(ctx.targets) == 1:
                scope["target_id"] = ctx.targets[0]
        metadata = self._resolved_world_metadata(ctx, dict(node.get("metadata", {})))
        metadata.update(self._slot_scaled_metadata(ctx, node))
        metadata.update(self._investment_of_chain_master_familiar_metadata(ctx, node))
        effect = {
            "effect_id": f"world-effect-{self.state.event_counter}-{len(self.state.world.active_effects)}",
            "source_ref": ctx.action.source,
            "source_action_id": ctx.action.id,
            "applied_by": ctx.actor_id,
            "effect_type": str(node["effect_type"]),
            "concentration": concentration,
            "scope": scope,
            "duration": self._resolved_effect_duration(ctx, node),
            "metadata": metadata,
            "audit": {"node_path": path},
        }
        if "tick_on" in node:
            effect["tick_on"] = str(node["tick_on"])
        self.state.world.active_effects.append(effect)
        ctx.result.state_changes.append(
            {
                "type": "world_effect",
                "effect_id": effect["effect_id"],
                "effect_type": effect["effect_type"],
                "concentration": effect["concentration"],
                "scope": effect["scope"],
                "path": path,
            }
        )

    def _node_natures_sanctuary(
        self,
        ctx: _Context,
        node: dict[str, Any],
        path: str,
    ) -> None:
        position_node_id = self._natures_sanctuary_destination(ctx.params, node)
        actor = self._resource_owner(ctx.actor_id)
        current_resistance = (
            druid_natures_ward_resistance_type(actor) if isinstance(actor, Character) else None
        )
        metadata = {
            "spectral_trees_and_vines": True,
            "on_ground": True,
            "cube_size_ft": 15,
            "created_with_magic_action": True,
            "cost_resource": "srd.resource.wild_shape",
            "half_cover_for_caster_and_allies_in_area": True,
            "allies_gain_current_natures_ward_resistance_in_area": True,
            "current_natures_ward_resistance": current_resistance,
            "ends_if_caster_incapacitated_or_dies": True,
            "can_move_as_bonus_action": True,
            "move_distance_ft": 60,
            "range_from_caster_ft": 120,
            "position_node_id": position_node_id,
        }
        metadata.update(self._resolved_world_metadata(ctx, dict(node.get("metadata", {}))))
        effect = {
            "effect_id": f"world-effect-{self.state.event_counter}-{len(self.state.world.active_effects)}",
            "source_ref": ctx.action.source,
            "source_action_id": ctx.action.id,
            "applied_by": ctx.actor_id,
            "effect_type": "natures_sanctuary",
            "concentration": False,
            "scope": {
                "shape": "cube",
                "size_ft": 15,
                "position_node_id": position_node_id,
                "range_ft": 120,
                "on_ground": True,
            },
            "duration": {"until": "duration_1_minute"},
            "metadata": metadata,
            "audit": {"node_path": path},
        }
        self.state.world.active_effects.append(effect)
        ctx.result.state_changes.append(
            {
                "type": "world_effect",
                "effect_id": effect["effect_id"],
                "effect_type": effect["effect_type"],
                "concentration": effect["concentration"],
                "scope": effect["scope"],
                "path": path,
            }
        )

    def _node_natures_sanctuary_move(
        self,
        ctx: _Context,
        node: dict[str, Any],
        path: str,
    ) -> None:
        position_node_id = self._natures_sanctuary_destination(ctx.params, node)
        effect = self._active_natures_sanctuary_effect(ctx.actor_id)
        if effect is None:
            raise AutomationError("Nature's Sanctuary requires an active Cube")
        scope = effect.setdefault("scope", {})
        if not isinstance(scope, dict):
            scope = {}
            effect["scope"] = scope
        metadata = effect.setdefault("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
            effect["metadata"] = metadata
        before = self._natures_sanctuary_effect_position(effect) or ""
        scope["position_node_id"] = position_node_id
        metadata["position_node_id"] = position_node_id
        metadata["last_moved_by_bonus_action"] = True
        ctx.result.state_changes.append(
            {
                "type": "natures_sanctuary_move",
                "actor_id": ctx.actor_id,
                "effect_id": effect.get("effect_id"),
                "from": before,
                "to": position_node_id,
                "path": path,
            }
        )

    def _node_max_hp_delta(self, ctx: _Context, node: dict[str, Any], path: str) -> None:
        increase_current = bool(node.get("increase_current", False))
        record_hp_max_reduction_marker = bool(node.get("record_hp_max_reduction_marker", False))
        for target_id in ctx.targets:
            amount = self._max_hp_delta_amount(ctx, node, target_id)
            target = self._entity(target_id)
            before_max = int(getattr(target, "hp_max"))
            before_current = int(getattr(target, "hp_current"))
            prevention_sources = (
                self._passive_hp_max_reduction_prevention_sources(target)
                if amount < 0
                else []
            )
            if prevention_sources:
                ctx.result.state_changes.append(
                    {
                        "type": "max_hp_delta",
                        "target_id": target_id,
                        "amount": amount,
                        "hp_max_before": before_max,
                        "hp_max_after": before_max,
                        "hp_current_before": before_current,
                        "hp_current_after": before_current,
                        "prevented": True,
                        "prevented_amount": abs(amount),
                        "prevention_sources": prevention_sources,
                        "path": path,
                    }
                )
                continue
            after_max = max(1, before_max + amount)
            after_current = before_current
            if increase_current and amount > 0:
                after_current = before_current + amount
            if after_current > after_max:
                after_current = after_max
            setattr(target, "hp_max", after_max)
            setattr(target, "hp_current", after_current)
            change = {
                "type": "max_hp_delta",
                "target_id": target_id,
                "amount": amount,
                "hp_max_before": before_max,
                "hp_max_after": after_max,
                "hp_current_before": before_current,
                "hp_current_after": after_current,
                "path": path,
            }
            actual_reduction = max(0, before_max - after_max)
            if record_hp_max_reduction_marker and actual_reduction:
                marker_effect_id = self._effect_id(target_id, f"{path}.hp_max_reduction")
                marker_effect = EffectInstance(
                    effect_id=marker_effect_id,
                    source_ref=ctx.action.source,
                    source_action_id=ctx.action.id,
                    target_id=target_id,
                    applied_by=ctx.actor_id,
                    audit={
                        "node_path": path,
                        "hp_max_reduction": actual_reduction,
                    },
                ).to_dict()
                marker_effect["effect_markers"] = ["hp_max_reduction"]
                marker_effect["metadata"] = {"hp_max_reduction": actual_reduction}
                getattr(target, "status_effects").append(marker_effect)
                change["hp_max_reduction_marker_effect_id"] = marker_effect_id
                change["hp_max_reduction"] = actual_reduction
            ctx.result.state_changes.append(change)

    def _max_hp_delta_amount(
        self,
        ctx: _Context,
        node: dict[str, Any],
        target_id: str,
    ) -> int:
        if "amount" in node:
            return int(node["amount"])
        amount_from = node.get("amount_from")
        if amount_from == "last_damage_taken":
            return ctx.last_damage_taken.get(target_id, 0)
        if amount_from == "-last_damage_taken":
            return -ctx.last_damage_taken.get(target_id, 0)
        raise AutomationError(f"unsupported max_hp_delta amount_from: {amount_from}")

    def _node_resource_delta(self, ctx: _Context, node: dict[str, Any], path: str) -> None:
        resource = str(node["resource"])
        if resource.startswith("budget."):
            economy_name = resource.removeprefix("budget.")
            try:
                if "set" in node:
                    before, after = self.economy.set(ctx.actor_id, economy_name, int(node["set"]))
                else:
                    delta = self._resource_delta_amount(ctx, node)
                    before, after = self.economy.add(ctx.actor_id, economy_name, delta)
            except ValueError as exc:
                raise AutomationError(f"budget {economy_name} cannot drop below zero") from exc
            ctx.result.state_changes.append(
                {
                    "type": "resource_delta",
                    "actor_id": ctx.actor_id,
                    "resource": resource,
                    "before": before,
                    "after": after,
                    "path": path,
                }
            )
            return
        if "set" in node:
            raise AutomationError("resource_delta set is supported only for budget resources")
        delta = self._resource_delta_amount(ctx, node)
        actor = self._resource_owner(ctx.actor_id)
        before = self._get_resource(actor, resource)
        after = before + delta
        if after < 0:
            raise AutomationError(f"resource {resource} cannot drop below zero")
        maximum = self._resource_delta_cap(ctx.actor_id, node)
        if maximum is not None and after > maximum:
            raise AutomationError(f"resource {resource} would exceed maximum {maximum}")
        self._set_resource(actor, resource, after)
        ctx.result.state_changes.append(
            {
                "type": "resource_delta",
                "actor_id": ctx.actor_id,
                "resource": resource,
                "before": before,
                "after": after,
                "path": path,
            }
        )

    def _node_heightened_focus_step_of_the_wind(
        self,
        ctx: _Context,
        node: dict[str, Any],
        path: str,
    ) -> None:
        companion_id = self._heightened_focus_companion_id(ctx.params)
        if companion_id is None:
            return
        plan = self._heightened_focus_companion_plan(ctx.actor_id, companion_id, ctx.params)
        actor = plan["actor"]
        assert isinstance(actor, Combatant)
        effect = EffectInstance(
            effect_id=self._effect_id(ctx.actor_id, path),
            source_ref=ctx.action.source,
            source_action_id=ctx.action.id,
            target_id=ctx.actor_id,
            applied_by=ctx.actor_id,
            condition=HEIGHTENED_FOCUS_COMPANION_CONDITION,
            passive_modifiers={
                "heightened_focus_step_of_the_wind": True,
                "companion_id": companion_id,
                "companion_no_opportunity_attacks": True,
            },
            duration=dict(node.get("duration", {"until": "end_of_current_turn"})),
            tick_on=node.get("tick_on", "self_turn_end"),
            stacking_policy="replace_condition",
            audit={"node_path": path},
        )
        effects = getattr(actor, "status_effects")
        effects[:] = [
            existing
            for existing in effects
            if existing.get("condition") != HEIGHTENED_FOCUS_COMPANION_CONDITION
        ]
        effects.append(effect.to_dict())
        ctx.result.state_changes.append(
            {
                "type": "heightened_focus_step_of_the_wind",
                "actor_id": ctx.actor_id,
                "companion_id": companion_id,
                "source_action_id": ctx.action.id,
                "distance_ft": plan["distance_ft"],
                "duration": effect.duration,
                "tick_on": effect.tick_on,
                "path": path,
            }
        )

    def _apply_tactical_mind_to_ability_check(
        self,
        ctx: _Context,
        total: int,
        dc: int,
        path: str,
    ) -> dict[str, Any] | None:
        if not bool(ctx.params.get("use_tactical_mind")) or total >= dc:
            return None
        actor = self._resource_owner(ctx.actor_id)
        if not isinstance(actor, Character):
            raise AutomationError("Tactical Mind requires a character")
        before_resource = int(actor.resources.get("srd.resource.second_wind", 0))
        roll = self.roll_service.roll("1d10")
        ctx.result.dice_rolls.append(roll.to_dict())
        after_total = total + roll.total
        success = after_total >= dc
        after_resource = before_resource
        if success:
            after_resource = before_resource - 1
            actor.resources["srd.resource.second_wind"] = after_resource
            ctx.result.state_changes.append(
                {
                    "type": "tactical_mind",
                    "actor_id": ctx.actor_id,
                    "resource": "srd.resource.second_wind",
                    "before": before_resource,
                    "after": after_resource,
                    "path": path,
                }
            )
        return {
            "resource": "srd.resource.second_wind",
            "resource_before": before_resource,
            "resource_after": after_resource,
            "roll_total": roll.total,
            "total_before": total,
            "total_after": after_total,
            "spent": success,
            "success": success,
        }

    def _apply_reliable_talent_to_ability_check(
        self,
        actor: Character | Monster | Combatant,
        roll: RollResult,
        total: int,
        proficiency_sources: list[str],
        dc: int,
    ) -> dict[str, Any] | None:
        if not isinstance(actor, Character):
            return None
        natural_d20 = self._kept_d20(roll)
        adjustment = reliable_talent_d20_adjustment(
            actor,
            proficiency_sources=proficiency_sources,
            natural_d20=natural_d20,
        )
        if adjustment <= 0:
            return None
        after_total = total + adjustment
        return {
            "source_action_id": RELIABLE_TALENT_ACTION_ID,
            "d20_before": natural_d20,
            "d20_after": RELIABLE_TALENT_D20_FLOOR,
            "adjustment": adjustment,
            "total_before": total,
            "total_after": after_total,
            "proficiency_sources": list(proficiency_sources),
            "success": after_total >= dc,
        }

    def _apply_charisma_check_minimum_d20_to_ability_check(
        self,
        actor: Character | Monster | Combatant,
        ability: str,
        roll: RollResult,
        total: int,
        dc: int,
        reliable_talent_result: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        natural_d20 = self._kept_d20(roll)
        current_d20 = natural_d20
        if reliable_talent_result is not None:
            d20_after = reliable_talent_result.get("d20_after")
            if isinstance(d20_after, int) and not isinstance(d20_after, bool):
                current_d20 = max(current_d20, d20_after)
        adjustment = charisma_check_minimum_d20_adjustment(
            status_effects=self._status_effects_for(actor),
            ability=ability,
            natural_d20=natural_d20,
            current_d20=current_d20,
        )
        if adjustment is None:
            return None
        after_total = total + int(adjustment["adjustment"])
        return {
            **adjustment,
            "total_before": total,
            "total_after": after_total,
            "success": after_total >= dc,
        }

    def _apply_indomitable_might_to_d20_test(
        self,
        actor: Character | Monster | Combatant,
        ability: str,
        total: int,
        dc: int,
    ) -> dict[str, Any] | None:
        if not isinstance(actor, Character):
            return None
        after_total = indomitable_might_total_floor(
            actor,
            ability=ability,
            total=total,
        )
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

    def _use_dark_ones_own_luck_for_save(self, ctx: _Context, target_id: str) -> bool:
        if not bool(ctx.params.get("use_dark_ones_own_luck")):
            return False
        explicit_target = ctx.params.get("dark_ones_own_luck_target_id")
        if explicit_target is not None:
            return str(explicit_target) == target_id
        return len(ctx.targets) == 1

    def _use_indomitable_for_save(self, ctx: _Context, target_id: str) -> bool:
        if not bool(ctx.params.get("use_indomitable")):
            return False
        explicit_target = ctx.params.get("indomitable_target_id")
        if explicit_target is not None:
            return str(explicit_target) == target_id
        return len(ctx.targets) == 1

    def _use_disciplined_survivor_for_save(self, ctx: _Context, target_id: str) -> bool:
        if not bool(ctx.params.get("use_disciplined_survivor")):
            return False
        explicit_target = ctx.params.get("disciplined_survivor_target_id")
        if explicit_target is not None:
            return str(explicit_target) == target_id
        return len(ctx.targets) == 1

    def _use_stroke_of_luck_for_target(self, ctx: _Context, target_id: str) -> bool:
        if not bool(ctx.params.get("use_stroke_of_luck")):
            return False
        explicit_target = ctx.params.get("stroke_of_luck_target_id")
        if explicit_target is not None:
            return str(explicit_target) == target_id
        return len(ctx.targets) == 1

    def _use_countercharm_for_save(self, ctx: _Context, target_id: str) -> bool:
        if not bool(ctx.params.get("use_countercharm")):
            return False
        explicit_target = ctx.params.get("countercharm_target_id")
        if explicit_target is not None:
            return str(explicit_target) == target_id
        return len(ctx.targets) == 1

    def _validate_stroke_of_luck_target_selection(self, ctx: _Context) -> None:
        explicit_target = ctx.params.get("stroke_of_luck_target_id")
        if explicit_target is None:
            if len(ctx.targets) > 1:
                raise AutomationError("Stroke of Luck requires an explicit target")
            return
        if str(explicit_target) not in ctx.targets:
            raise AutomationError("Stroke of Luck target must be one of the action targets")

    def _validate_countercharm_target_selection(self, ctx: _Context) -> None:
        target_id = self._countercharm_target_id(ctx.targets, ctx.params)
        if target_id not in ctx.targets:
            raise AutomationError("Countercharm target must be one of the action targets")

    def _validate_countercharm_preconditions(
        self,
        action: ActionDefinition,
        targets: list[str],
        params: dict[str, Any],
    ) -> None:
        if not bool(params.get("use_countercharm")):
            return
        self._validate_countercharm_save_node(action)
        target_id = self._countercharm_target_id(targets, params)
        if target_id not in targets:
            raise AutomationError("Countercharm target must be one of the action targets")
        target = self._entity(target_id)
        for node in self._countercharm_saving_throw_nodes(action):
            auto_fail_sources = self._saving_throw_auto_failure_sources(
                target,
                str(node["ability"]),
                node,
            )
            if auto_fail_sources:
                raise AutomationError("Countercharm requires a rolled failed saving throw")
        self._validate_countercharm_available_for_ids(params, target_id)

    def _validate_countercharm_save_node(self, action: ActionDefinition) -> None:
        if not self._countercharm_saving_throw_nodes(
            action
        ) or not self._action_applies_countercharm_condition(action):
            raise AutomationError("Countercharm requires a save against Charmed or Frightened")

    def _action_applies_countercharm_condition(self, action: ActionDefinition) -> bool:
        return any(
            node.get("type") == "condition"
            and str(node.get("condition", "")).lower() in COUNTERCHARM_CONDITIONS
            and node.get("requires_failed_save") is True
            for node in self._automation_nodes(action.automation)
        )

    def _countercharm_saving_throw_nodes(
        self,
        action: ActionDefinition,
    ) -> list[dict[str, Any]]:
        return [
            node
            for node in self._automation_nodes(action.automation)
            if node.get("type") == "saving_throw" and "ability" in node
        ]

    @staticmethod
    def _countercharm_target_id(targets: list[str], params: dict[str, Any]) -> str:
        explicit_target = params.get("countercharm_target_id")
        if explicit_target is not None:
            return str(explicit_target)
        if len(targets) == 1:
            return str(targets[0])
        raise AutomationError("Countercharm requires an explicit target")

    @staticmethod
    def _countercharm_bard_id(params: dict[str, Any]) -> str | None:
        explicit_bard = params.get("countercharm_bard_id")
        if explicit_bard is None:
            explicit_bard = params.get("countercharm_actor_id")
        if explicit_bard is None:
            return None
        return str(explicit_bard)

    def _countercharm_bard_character(self, bard_id: str) -> Character | None:
        try:
            bard_entity = self._entity(bard_id)
        except KeyError:
            return None
        if isinstance(bard_entity, Character):
            return bard_entity
        if isinstance(bard_entity, Combatant) and bard_entity.entity_id in self.state.characters:
            return self.state.characters[bard_entity.entity_id]
        return None

    def _validate_countercharm_available(self, ctx: _Context, target_id: str) -> None:
        self._validate_countercharm_available_for_ids(ctx.params, target_id)

    def _validate_countercharm_available_for_ids(
        self,
        params: dict[str, Any],
        target_id: str,
    ) -> None:
        bard_id = self._countercharm_bard_id(params)
        if bard_id is None:
            raise AutomationError("Countercharm requires an explicit Bard")
        character = self._countercharm_bard_character(bard_id)
        if character is None or int(character.class_levels.get("bard", 0)) < 7:
            raise AutomationError("Countercharm requires Bard level 7")
        try:
            bard_entity = self._entity(bard_id)
            target = self._entity(target_id)
        except KeyError as exc:
            raise AutomationError("Countercharm requires known Bard and target") from exc
        self._validate_condition_gate(bard_entity, "reaction")
        if not self._reaction_budget_available(bard_id, bard_entity):
            raise AutomationError("not enough reaction budget")
        if not self._countercharm_target_within_range(bard_id, bard_entity, target_id, target):
            raise AutomationError("Countercharm requires target within 30 feet")

    def _countercharm_target_within_range(
        self,
        bard_id: str,
        bard_entity: Character | Monster | Combatant,
        target_id: str,
        target: Character | Monster | Combatant,
    ) -> bool:
        if self._entity_ids_match(bard_id, target_id):
            return True
        bard_combatant = self._combatant_for(bard_entity)
        target_combatant = self._combatant_for(target)
        if bard_combatant is None or target_combatant is None:
            return False
        distance = self._combat_distance(bard_combatant, target_combatant)
        return distance is not None and distance <= COUNTERCHARM_RANGE_FT

    def _dark_ones_own_luck_character(
        self,
        entity: Character | Monster | Combatant,
    ) -> Character | None:
        if isinstance(entity, Character):
            return entity
        if isinstance(entity, Combatant):
            backing = self.state.characters.get(entity.entity_id)
            if backing is not None:
                return backing
        return None

    def _validate_dark_ones_own_luck_available(
        self,
        entity: Character | Monster | Combatant,
    ) -> None:
        character = self._dark_ones_own_luck_character(entity)
        if character is None or not has_warlock_fiend_feature(character, level=6):
            raise AutomationError("Dark One's Own Luck requires Fiend Patron Warlock level 6")
        if int(character.resources.get(DARK_ONES_OWN_LUCK_RESOURCE, 0)) <= 0:
            raise AutomationError("Dark One's Own Luck requires an available use")

    def _stroke_of_luck_character(
        self,
        entity: Character | Monster | Combatant,
    ) -> Character | None:
        if isinstance(entity, Character):
            return entity
        if isinstance(entity, Combatant):
            backing = self.state.characters.get(entity.entity_id)
            if backing is not None:
                return backing
        return None

    def _validate_stroke_of_luck_available(
        self,
        entity: Character | Monster | Combatant,
    ) -> None:
        character = self._stroke_of_luck_character(entity)
        if character is None or not rogue_stroke_of_luck_applies(character):
            raise AutomationError("Stroke of Luck requires Rogue level 20")
        if int(character.resources.get(STROKE_OF_LUCK_RESOURCE, 0)) <= 0:
            raise AutomationError("Stroke of Luck requires an available use")

    def _apply_stroke_of_luck_to_failed_d20_test(
        self,
        ctx: _Context,
        entity: Character | Monster | Combatant,
        roll: RollResult,
        total: int,
        path: str,
        *,
        use_stroke_of_luck: bool,
        failed: bool,
        d20_test_type: str,
    ) -> dict[str, Any] | None:
        if not use_stroke_of_luck or not failed:
            return None
        character = self._stroke_of_luck_character(entity)
        if character is None:
            raise AutomationError("Stroke of Luck requires a character")
        natural_d20 = self._kept_d20(roll)
        adjustment = STROKE_OF_LUCK_D20 - natural_d20
        if adjustment <= 0:
            return None
        before_resource = int(character.resources.get(STROKE_OF_LUCK_RESOURCE, 0))
        after_resource = before_resource - 1
        character.resources[STROKE_OF_LUCK_RESOURCE] = after_resource
        entity_id = str(getattr(entity, "id", character.id))
        after_total = total + adjustment
        ctx.result.state_changes.append(
            {
                "type": "stroke_of_luck",
                "actor_id": entity_id,
                "source_action_id": STROKE_OF_LUCK_ACTION_ID,
                "resource": STROKE_OF_LUCK_RESOURCE,
                "before": before_resource,
                "after": after_resource,
                "d20_test_type": d20_test_type,
                "path": path,
            }
        )
        return {
            "source_action_id": STROKE_OF_LUCK_ACTION_ID,
            "resource": STROKE_OF_LUCK_RESOURCE,
            "resource_before": before_resource,
            "resource_after": after_resource,
            "d20_test_type": d20_test_type,
            "d20_before": natural_d20,
            "d20_after": STROKE_OF_LUCK_D20,
            "adjustment": adjustment,
            "total_before": total,
            "total_after": after_total,
            "spent": True,
        }

    def _apply_dark_ones_own_luck_to_roll(
        self,
        ctx: _Context,
        entity: Character | Monster | Combatant,
        total: int,
        path: str,
        *,
        use_dark_ones_own_luck: bool,
    ) -> dict[str, Any] | None:
        if not use_dark_ones_own_luck:
            return None
        character = self._dark_ones_own_luck_character(entity)
        if character is None:
            raise AutomationError("Dark One's Own Luck requires a character")
        before_resource = int(character.resources.get(DARK_ONES_OWN_LUCK_RESOURCE, 0))
        roll = self.roll_service.roll("1d10")
        ctx.result.dice_rolls.append(roll.to_dict())
        after_total = total + roll.total
        after_resource = before_resource - 1
        character.resources[DARK_ONES_OWN_LUCK_RESOURCE] = after_resource
        entity_id = str(getattr(entity, "id", character.id))
        ctx.result.state_changes.append(
            {
                "type": "dark_ones_own_luck",
                "actor_id": entity_id,
                "source_action_id": DARK_ONES_OWN_LUCK_ACTION_ID,
                "resource": DARK_ONES_OWN_LUCK_RESOURCE,
                "before": before_resource,
                "after": after_resource,
                "path": path,
            }
        )
        return {
            "resource": DARK_ONES_OWN_LUCK_RESOURCE,
            "resource_before": before_resource,
            "resource_after": after_resource,
            "roll_total": roll.total,
            "total_before": total,
            "total_after": after_total,
            "spent": True,
        }

    def _indomitable_character(
        self,
        entity: Character | Monster | Combatant,
    ) -> Character | None:
        if isinstance(entity, Character):
            return entity
        if isinstance(entity, Combatant):
            backing = self.state.characters.get(entity.entity_id)
            if backing is not None:
                return backing
        return None

    def _validate_indomitable_available(
        self,
        entity: Character | Monster | Combatant,
    ) -> None:
        character = self._indomitable_character(entity)
        if character is None or not has_fighter_feature(character, level=9):
            raise AutomationError("Indomitable requires Fighter level 9")
        if int(character.resources.get(INDOMITABLE_RESOURCE, 0)) <= 0:
            raise AutomationError("Indomitable requires an available use")

    def _disciplined_survivor_character(
        self,
        entity: Character | Monster | Combatant,
    ) -> Character | None:
        if isinstance(entity, Character):
            return entity
        if isinstance(entity, Combatant):
            backing = self.state.characters.get(entity.entity_id)
            if backing is not None:
                return backing
        return None

    def _validate_disciplined_survivor_available(
        self,
        entity: Character | Monster | Combatant,
    ) -> None:
        character = self._disciplined_survivor_character(entity)
        if character is None or not monk_disciplined_survivor_applies(character):
            raise AutomationError("Disciplined Survivor requires Monk level 14")
        if int(character.resources.get(FOCUS_POINTS_RESOURCE, 0)) <= 0:
            raise AutomationError("Disciplined Survivor requires an available Focus Point")

    def _apply_indomitable_to_failed_save(
        self,
        ctx: _Context,
        entity: Character | Monster | Combatant,
        total: int,
        dc: int,
        bonus: int,
        passive_adjustment: int,
        advantage: str | None,
        path: str,
        *,
        use_indomitable: bool,
    ) -> dict[str, Any] | None:
        if not use_indomitable or total >= dc:
            return None
        character = self._indomitable_character(entity)
        if character is None:
            raise AutomationError("Indomitable requires a character")
        before_resource = int(character.resources.get(INDOMITABLE_RESOURCE, 0))
        fighter_level = int(character.class_levels.get("fighter", 0))
        reroll = self.roll_service.roll(d20_expression(bonus + fighter_level), advantage=advantage)
        ctx.result.dice_rolls.append(reroll.to_dict())
        after_total = reroll.total + passive_adjustment
        after_resource = before_resource - 1
        character.resources[INDOMITABLE_RESOURCE] = after_resource
        entity_id = str(getattr(entity, "id", character.id))
        success = after_total >= dc
        ctx.result.state_changes.append(
            {
                "type": "indomitable",
                "actor_id": entity_id,
                "source_action_id": INDOMITABLE_ACTION_ID,
                "resource": INDOMITABLE_RESOURCE,
                "before": before_resource,
                "after": after_resource,
                "path": path,
            }
        )
        return {
            "resource": INDOMITABLE_RESOURCE,
            "resource_before": before_resource,
            "resource_after": after_resource,
            "fighter_level_bonus": fighter_level,
            "total_before": total,
            "reroll_base_total": reroll.total,
            "passive_adjustment": passive_adjustment,
            "total_after": after_total,
            "spent": True,
            "success": success,
        }

    def _apply_disciplined_survivor_to_failed_save(
        self,
        ctx: _Context,
        entity: Character | Monster | Combatant,
        total: int,
        dc: int,
        bonus: int,
        passive_adjustment: int,
        advantage: str | None,
        path: str,
        *,
        use_disciplined_survivor: bool,
    ) -> dict[str, Any] | None:
        if not use_disciplined_survivor or total >= dc:
            return None
        character = self._disciplined_survivor_character(entity)
        if character is None:
            raise AutomationError("Disciplined Survivor requires a character")
        before_resource = int(character.resources.get(FOCUS_POINTS_RESOURCE, 0))
        reroll = self.roll_service.roll(d20_expression(bonus), advantage=advantage)
        ctx.result.dice_rolls.append(reroll.to_dict())
        after_total = reroll.total + passive_adjustment
        after_resource = before_resource - 1
        character.resources[FOCUS_POINTS_RESOURCE] = after_resource
        entity_id = str(getattr(entity, "id", character.id))
        success = after_total >= dc
        ctx.result.state_changes.append(
            {
                "type": "disciplined_survivor",
                "actor_id": entity_id,
                "source_action_id": DISCIPLINED_SURVIVOR_ACTION_ID,
                "resource": FOCUS_POINTS_RESOURCE,
                "before": before_resource,
                "after": after_resource,
                "path": path,
            }
        )
        return {
            "resource": FOCUS_POINTS_RESOURCE,
            "resource_before": before_resource,
            "resource_after": after_resource,
            "source_action_id": DISCIPLINED_SURVIVOR_ACTION_ID,
            "total_before": total,
            "reroll_base_total": reroll.total,
            "passive_adjustment": passive_adjustment,
            "total_after": after_total,
            "spent": True,
            "success": success,
        }

    def _apply_countercharm_to_failed_save(
        self,
        ctx: _Context,
        entity: Character | Monster | Combatant,
        total: int,
        dc: int,
        bonus: int,
        passive_adjustment: int,
        path: str,
        *,
        use_countercharm: bool,
    ) -> dict[str, Any] | None:
        if not use_countercharm or total >= dc:
            return None
        bard_id = self._countercharm_bard_id(ctx.params)
        if bard_id is None:
            raise AutomationError("Countercharm requires an explicit Bard")
        bard_entity = self._entity(bard_id)
        before = self.economy.budget_for(bard_id, self._effective_speed(bard_entity)).to_dict()
        reroll = self.roll_service.roll(d20_expression(bonus), advantage="advantage")
        ctx.result.dice_rolls.append(reroll.to_dict())
        after_total = reroll.total + passive_adjustment
        self.economy.spend(bard_id, "reaction", 1)
        after = self.economy.budget_for(bard_id).to_dict()
        target_id = str(getattr(entity, "id", ""))
        success = after_total >= dc
        ctx.result.state_changes.append(
            {
                "type": "countercharm",
                "actor_id": bard_id,
                "target_id": target_id,
                "source_action_id": COUNTERCHARM_ACTION_ID,
                "economy": "reaction",
                "amount": 1,
                "reaction_before": before,
                "reaction_after": after,
                "path": path,
            }
        )
        return {
            "source_action_id": COUNTERCHARM_ACTION_ID,
            "bard_id": bard_id,
            "target_id": target_id,
            "total_before": total,
            "reroll_base_total": reroll.total,
            "passive_adjustment": passive_adjustment,
            "total_after": after_total,
            "reaction_before": before,
            "reaction_after": after,
            "spent": True,
            "success": success,
        }

    def _node_pact_magic_recovery(self, ctx: _Context, path: str) -> None:
        actor = self._resource_owner(ctx.actor_id)
        if not isinstance(actor, Character):
            raise AutomationError("pact_magic_recovery requires a character")
        pact_slots = warlock_pact_slot_maxima_for_class_levels(actor.class_levels)
        recovered: dict[str, int] = {}
        before_slots: dict[str, int] = {}
        after_slots: dict[str, int] = {}
        recover_all = eldritch_master_applies(actor)
        for slot_level, maximum in sorted(pact_slots.items(), key=lambda item: int(item[0])):
            before = max(0, int(actor.spell_slots.get(slot_level, 0)))
            recover_limit = maximum if recover_all else (maximum + 1) // 2
            missing = max(0, maximum - before)
            amount = min(missing, recover_limit)
            after = before + amount
            actor.spell_slots[slot_level] = after
            actor.spell_slots_max[slot_level] = max(
                int(actor.spell_slots_max.get(slot_level, 0)),
                maximum,
            )
            before_slots[slot_level] = before
            after_slots[slot_level] = after
            recovered[slot_level] = amount
        ctx.result.state_changes.append(
            {
                "type": "pact_magic_recovery",
                "actor_id": ctx.actor_id,
                "before": before_slots,
                "after": after_slots,
                "recovered": recovered,
                "recover_limit": "all" if recover_all else "half_rounded_up",
                "source_action_id": "srd.eldritch_master" if recover_all else "srd.magical_cunning",
                "path": path,
            }
        )

    def _node_wild_resurgence_restore_wild_shape(self, ctx: _Context, path: str) -> None:
        actor = self._resource_owner(ctx.actor_id)
        if not isinstance(actor, Character):
            raise AutomationError("wild_resurgence_restore_wild_shape requires a character")
        maximum = self._wild_shape_maximum(actor)
        before = max(0, int(actor.resources.get("srd.resource.wild_shape", 0)))
        after = min(maximum, before + 1)
        actor.resources["srd.resource.wild_shape"] = after
        ctx.result.state_changes.append(
            {
                "type": "wild_resurgence_restore_wild_shape",
                "actor_id": ctx.actor_id,
                "resource": "srd.resource.wild_shape",
                "before": before,
                "after": after,
                "path": path,
            }
        )

    def _node_move(self, ctx: _Context, node: dict[str, Any]) -> None:
        destination = (
            node.get("to") or ctx.params.get("to_position_node_id") or ctx.params.get("to_zone_id")
        )
        if destination is None:
            raise AutomationError("move node requires a destination")
        actor = self._entity(ctx.actor_id)
        if isinstance(actor, Combatant):
            before = actor.position_node_id
            actor.position_node_id = str(destination)
            ctx.result.state_changes.append(
                {
                    "type": "move",
                    "actor_id": ctx.actor_id,
                    "from": before,
                    "to": actor.position_node_id,
                    "movement_cost": int(ctx.params.get("movement_cost", 0)),
                    "opportunity_attack_triggers": list(
                        ctx.params.get("opportunity_attack_triggers", [])
                    ),
                }
            )
            ctx.result.state_changes.extend(
                self._heightened_focus_step_companion_moves(ctx.actor_id, str(destination))
            )
        elif isinstance(actor, Character):
            before = actor.zone_id
            actor.zone_id = str(destination)
            if ctx.params.get("update_world_zone", True):
                self.state.world.current_zone_id = actor.zone_id or self.state.world.current_zone_id
            ctx.result.state_changes.append(
                {"type": "move", "actor_id": ctx.actor_id, "from": before, "to": actor.zone_id}
            )
        else:
            raise AutomationError("only characters and combatants can move")

    def _heightened_focus_step_companion_moves(
        self,
        actor_id: str,
        destination: str,
    ) -> list[dict[str, Any]]:
        if self.state.encounter is None:
            return []
        actor = self._entity(actor_id)
        if not isinstance(actor, Combatant):
            return []
        changes: list[dict[str, Any]] = []
        for effect in actor.status_effects:
            if effect.get("condition") != HEIGHTENED_FOCUS_COMPANION_CONDITION:
                continue
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            companion_id = modifiers.get("companion_id")
            if not isinstance(companion_id, str):
                continue
            companion = self.state.encounter.combatants.get(companion_id)
            if companion is None:
                continue
            before = companion.position_node_id
            companion.position_node_id = destination
            changes.append(
                {
                    "type": "heightened_focus_step_of_the_wind_companion_move",
                    "actor_id": actor_id,
                    "companion_id": companion_id,
                    "from": before,
                    "to": companion.position_node_id,
                    "movement_cost": 0,
                    "opportunity_attack_triggers": [],
                    "source_action_id": effect.get("source_action_id"),
                }
            )
        return changes

    def _node_tactical_shift_move(self, ctx: _Context, node: dict[str, Any], path: str) -> None:
        destination_param = str(node.get("destination_param", "tactical_shift_to_position_node_id"))
        destination = ctx.params.get(destination_param)
        if destination is None:
            return
        plan = self._tactical_shift_move_plan(ctx.actor_id, str(destination))
        actor = plan["actor"]
        assert isinstance(actor, Combatant)
        before_position = actor.position_node_id
        actor.position_node_id = str(destination)
        before_used, after_used = self.economy.add(
            ctx.actor_id,
            "movement_used",
            int(plan["movement_cost"]),
        )
        ctx.result.state_changes.append(
            {
                "type": "move",
                "actor_id": ctx.actor_id,
                "feature": "tactical_shift",
                "from": before_position,
                "to": actor.position_node_id,
                "movement_cost": int(plan["movement_cost"]),
                "movement_limit": int(plan["movement_limit"]),
                "movement_used_before": before_used,
                "movement_used_after": after_used,
                "opportunity_attack_triggers": [],
                "path": path,
            }
        )

    def _node_instinctive_pounce_move(
        self,
        ctx: _Context,
        node: dict[str, Any],
        path: str,
    ) -> None:
        destination_param = str(
            node.get("destination_param", "instinctive_pounce_to_position_node_id")
        )
        destination = ctx.params.get(destination_param)
        if destination is None:
            return
        plan = self._instinctive_pounce_move_plan(ctx.actor_id, str(destination))
        actor = plan["actor"]
        assert isinstance(actor, Combatant)
        before_position = actor.position_node_id
        actor.position_node_id = str(destination)
        before_used, after_used = self.economy.add(
            ctx.actor_id,
            "movement_used",
            int(plan["movement_cost"]),
        )
        ctx.result.state_changes.append(
            {
                "type": "move",
                "actor_id": ctx.actor_id,
                "feature": "instinctive_pounce",
                "source_action_id": INSTINCTIVE_POUNCE_ACTION_ID,
                "from": before_position,
                "to": actor.position_node_id,
                "movement_cost": int(plan["movement_cost"]),
                "movement_limit": int(plan["movement_limit"]),
                "movement_used_before": before_used,
                "movement_used_after": after_used,
                "opportunity_attack_triggers": self._opportunity_attack_triggers_for_move(
                    actor,
                    from_position=before_position,
                    to_position=actor.position_node_id,
                ),
                "path": path,
            }
        )

    def _branch_condition(self, ctx: _Context, node: dict[str, Any]) -> bool:
        condition = node.get("condition")
        if condition == "last_attack_hit":
            return any(ctx.attack_hits.values())
        if condition == "last_save_success":
            return any(ctx.save_successes.values())
        if condition == "ability_success":
            return bool(ctx.ability_success)
        if condition == "actor_class_level_min":
            class_name = node.get("class")
            level = node.get("level")
            if class_name is None or level is None:
                raise AutomationError("actor_class_level_min requires class and level")
            owner = self._resource_owner(ctx.actor_id)
            class_levels = getattr(owner, "class_levels", {})
            if not isinstance(class_levels, dict):
                return False
            return int(class_levels.get(str(class_name), 0)) >= int(level)
        raise AutomationError(f"unsupported branch condition: {condition}")

    def _execute_potent_cantrip_successful_save_damage(
        self,
        ctx: _Context,
        node: dict[str, Any],
        path: str,
        idempotency_key: str,
    ) -> None:
        if node.get("condition") != "last_save_success":
            return
        if not self._potent_cantrip_actor_applies(ctx):
            return
        if not any(success is True for success in ctx.save_successes.values()):
            return
        true_branch = node.get("if_true", [])
        if self._branch_has_state_changing_nodes(true_branch):
            return
        false_branch = node.get("if_false", [])
        if not isinstance(false_branch, list):
            return
        for index, child in enumerate(false_branch):
            if not isinstance(child, dict) or child.get("type") != "damage":
                continue
            damage_node = dict(child)
            damage_node["potent_cantrip_force_half"] = True
            self._execute_node(
                ctx,
                damage_node,
                f"{path}.potent_cantrip[{index}]",
                idempotency_key,
            )

    def _branch_has_state_changing_nodes(self, branch: Any) -> bool:
        if not isinstance(branch, list):
            return False
        for child in branch:
            if not isinstance(child, dict):
                continue
            node_type = child.get("type")
            if node_type in STATE_CHANGING_NODE_TYPES:
                return True
            if node_type == "branch":
                if self._branch_has_state_changing_nodes(child.get("if_true", [])):
                    return True
                if self._branch_has_state_changing_nodes(child.get("if_false", [])):
                    return True
        return False

    def _potent_cantrip_half_damage(
        self,
        ctx: _Context,
        node: dict[str, Any],
        target_id: str,
        *,
        require_hit: bool,
        force_half: bool,
    ) -> dict[str, Any] | None:
        if not self._potent_cantrip_actor_applies(ctx):
            return None
        if force_half:
            if ctx.save_successes.get(target_id) is not True:
                return None
            trigger = "successful_save"
        elif require_hit and ctx.attack_hits.get(target_id) is False:
            trigger = "missed_attack"
        else:
            return None
        return {
            "source_action_id": "srd.potent_cantrip",
            "trigger": trigger,
            "target_id": target_id,
            "action_id": ctx.action.id,
            "damage_node_type": node.get("type"),
        }

    def _potent_cantrip_actor_applies(self, ctx: _Context) -> bool:
        if not self._action_is_damaging_cantrip(ctx.action):
            return False
        owner = self._resource_owner(ctx.actor_id)
        return isinstance(owner, Character) and has_wizard_evocation_feature(owner, level=3)

    def _action_is_damaging_cantrip(self, action: ActionDefinition) -> bool:
        if action.action_type != "spell":
            return False
        try:
            spell_level = int(action.requirements.get("spell_level", -1))
        except (TypeError, ValueError):
            return False
        if spell_level != 0:
            return False
        return any(
            node.get("type") == "damage" for node in self._automation_nodes(action.automation)
        )

    def _roll_amount(self, ctx: _Context, node: dict[str, Any]) -> tuple[int, list[RollResult]]:
        if "amount" in node:
            return self._minimum_amount(
                int(node["amount"]) + self._amount_bonus(ctx, node),
                node,
            ), []
        if "amount_from" in node:
            return self._minimum_amount(
                self._param_amount(ctx, str(node["amount_from"])) + self._amount_bonus(ctx, node),
                node,
            ), []
        if "dice_from" in node:
            roll = self.roll_service.roll(self._dynamic_dice_expression(ctx, node))
            return self._minimum_amount(
                roll.total + self._amount_bonus(ctx, node),
                node,
            ), [roll]
        roll = self.roll_service.roll(self._scaled_dice_expression(ctx, node))
        return self._minimum_amount(roll.total + self._amount_bonus(ctx, node), node), [roll]

    def _healing_amount(
        self,
        ctx: _Context,
        node: dict[str, Any],
    ) -> tuple[int, list[RollResult], dict[str, Any] | None]:
        if not self._supreme_healing_applies(ctx):
            amount, rolls = self._roll_amount(ctx, node)
            return amount, rolls, None
        if "amount" in node or "amount_from" in node:
            amount, rolls = self._roll_amount(ctx, node)
            return amount, rolls, None
        expression = (
            self._dynamic_dice_expression(ctx, node)
            if "dice_from" in node
            else self._scaled_dice_expression(ctx, node)
        )
        maximum = self._maximum_dice_expression_total(expression)
        if maximum is None:
            amount, rolls = self._roll_amount(ctx, node)
            return amount, rolls, None
        amount = self._minimum_amount(maximum + self._amount_bonus(ctx, node), node)
        return amount, [], {
            "source_action_id": SUPREME_HEALING_ACTION_ID,
            "dice_expression": expression,
            "maximized_dice_total": maximum,
        }

    def _supreme_healing_applies(self, ctx: _Context) -> bool:
        owner = self._resource_owner(ctx.actor_id)
        if not isinstance(owner, Character) or not supreme_healing_applies(owner):
            return False
        if ctx.action.action_type == "spell":
            return True
        return int(ctx.action.cost.resources.get(CHANNEL_DIVINITY_RESOURCE_ID, 0)) > 0

    @staticmethod
    def _maximum_dice_expression_total(expression: str) -> int | None:
        cleaned = expression.replace(" ", "")
        if not cleaned:
            return None
        position = 0
        total = 0
        has_dice = False
        for match in re.finditer(r"([+-]?)(?:(\d*)d(\d+)|(\d+))", cleaned, re.IGNORECASE):
            if match.start() != position:
                raise AutomationError(f"unsupported dice expression for Supreme Healing: {expression}")
            sign = -1 if match.group(1) == "-" else 1
            if match.group(3) is not None:
                count = int(match.group(2) or "1")
                sides = int(match.group(3))
                value = count * sides
                has_dice = True
            else:
                value = int(match.group(4))
            total += sign * value
            position = match.end()
        if position != len(cleaned):
            raise AutomationError(f"unsupported dice expression for Supreme Healing: {expression}")
        return total if has_dice else None

    @staticmethod
    def _minimum_amount(amount: int, node: dict[str, Any]) -> int:
        minimum = node.get("minimum_amount")
        if minimum is None:
            return amount
        return max(int(minimum), amount)

    def _scaled_dice_expression(self, ctx: _Context, node: dict[str, Any]) -> str:
        base_expression = str(node["dice"])
        extra_dice = node.get("extra_dice_per_slot_above")
        if extra_dice is None:
            return base_expression
        if not isinstance(extra_dice, str):
            raise AutomationError("extra_dice_per_slot_above must be a dice string")
        base_slot_level = int(
            node.get("base_spell_slot_level", ctx.action.cost.spell_slot_level or 0)
        )
        slot_level = self._spell_slot_level_to_spend(ctx.action, ctx.params)
        extra_slots = max(0, slot_level - base_slot_level)
        if extra_slots == 0:
            return base_expression
        extra_match = re.fullmatch(r"([0-9]+)d([0-9]+)", extra_dice)
        if extra_match is None:
            raise AutomationError("extra_dice_per_slot_above must be a simple dice string")
        extra_count = int(extra_match.group(1)) * extra_slots
        extra_sides = extra_match.group(2)
        base_match = re.fullmatch(r"([0-9]+)d([0-9]+)", base_expression)
        if base_match is not None and base_match.group(2) == extra_sides:
            return f"{int(base_match.group(1)) + extra_count}d{extra_sides}"
        return f"{base_expression}+{extra_count}d{extra_sides}"

    def _dynamic_dice_expression(self, ctx: _Context, node: dict[str, Any]) -> str:
        dice_from = node.get("dice_from")
        if not isinstance(dice_from, dict):
            raise AutomationError("dice_from must be an object")
        class_feature = dice_from.get("class_feature")
        if class_feature == "monk_martial_arts_die":
            owner = self._resource_owner(ctx.actor_id)
            if not isinstance(owner, Character) or not has_monk_feature(owner, level=1):
                raise AutomationError("Monk Martial Arts die requires Monk level 1")
            dice_count = int(node.get("dice_count", 1))
            return f"{dice_count}{monk_martial_arts_die(owner)}"
        ability = dice_from.get("ability_modifier")
        die = dice_from.get("die")
        if ability is None or not isinstance(die, str) or not re.fullmatch(r"d[0-9]+", die):
            raise AutomationError("dice_from supports ability_modifier and die")
        count = self._ability_modifier(self._entity(ctx.actor_id), str(ability))
        minimum = int(dice_from.get("minimum", 0))
        return f"{max(minimum, count)}{die}"

    def _param_amount(self, ctx: _Context, amount_from: str) -> int:
        prefix = "param."
        if not amount_from.startswith(prefix):
            raise AutomationError(f"unsupported amount_from: {amount_from}")
        param_name = amount_from.removeprefix(prefix)
        return self._positive_param_int(ctx.params, param_name)

    def _amount_bonus(self, ctx: _Context, node: dict[str, Any]) -> int:
        bonus = self._slot_scaled_amount_bonus(ctx, node)
        bonus_from = node.get("bonus_from")
        if bonus_from is None:
            return bonus
        if not isinstance(bonus_from, dict):
            raise AutomationError("bonus_from must be an object")
        class_name = bonus_from.get("class_level")
        if class_name is not None:
            owner = self._resource_owner(ctx.actor_id)
            if not isinstance(owner, Character):
                return bonus
            return bonus + max(0, int(owner.class_levels.get(str(class_name), 0)))
        ability = bonus_from.get("ability_modifier")
        if ability is not None:
            return bonus + self._ability_modifier(self._entity(ctx.actor_id), str(ability))
        spellcasting_ability = bonus_from.get("spellcasting_ability_modifier")
        if spellcasting_ability is not None:
            if spellcasting_ability != "actor":
                raise AutomationError("spellcasting_ability_modifier supports only actor")
            return bonus + self._actor_spellcasting_ability_modifier(ctx)
        raise AutomationError("unsupported bonus_from")

    def _slot_scaled_amount_bonus(self, ctx: _Context, node: dict[str, Any]) -> int:
        per_slot = node.get("extra_amount_per_slot_above")
        if per_slot is None:
            return 0
        if not isinstance(per_slot, int) or isinstance(per_slot, bool):
            raise AutomationError("extra_amount_per_slot_above must be an integer")
        base_slot_level = int(
            node.get("base_spell_slot_level", ctx.action.cost.spell_slot_level or 0)
        )
        slot_level = self._spell_slot_level_to_spend(ctx.action, ctx.params)
        return max(0, slot_level - base_slot_level) * per_slot

    def _resolve_node_dc(self, ctx: _Context, node: dict[str, Any]) -> tuple[int, str]:
        dc_from = node.get("dc_from")
        if dc_from is not None:
            return self._resolve_dynamic_dc(ctx, dc_from)
        table = node.get("dc_table")
        if table is None:
            table = self.state.world.flags.get("dc_table", {})
        if not isinstance(table, dict):
            raise AutomationError("dc_table must be an object")
        try:
            return resolve_dc(
                difficulty_tier=node.get("difficulty_tier"),
                dc_ref=node.get("dc_ref"),
                dc_table={str(key): int(value) for key, value in table.items()},
            )
        except ValueError as exc:
            raise AutomationError(str(exc)) from exc

    def _resolve_dynamic_dc(self, ctx: _Context, dc_from: Any) -> tuple[int, str]:
        if not isinstance(dc_from, dict):
            raise AutomationError("dc_from must be an object")
        class_name = dc_from.get("spell_save_dc")
        if not isinstance(class_name, str):
            raise AutomationError("dc_from supports only spell_save_dc")
        class_name = class_name.lower()
        if class_name == "actor":
            return self._actor_spell_save_dc(ctx)
        return self._spell_save_dc_for_class(ctx, class_name)

    def _actor_spell_save_dc(self, ctx: _Context) -> tuple[int, str]:
        owner = self._resource_owner(ctx.actor_id)
        if not isinstance(owner, Character):
            raise AutomationError("spell_save_dc requires a character actor")
        class_levels = {
            str(class_name).lower(): int(level) for class_name, level in owner.class_levels.items()
        }
        candidate_classes = self._spell_save_dc_candidate_classes(ctx.action)
        matching_classes = [
            class_name for class_name in candidate_classes if class_levels.get(class_name, 0) > 0
        ]
        if not matching_classes:
            raise AutomationError("actor has no matching spellcasting class for this spell")
        return max(
            (self._spell_save_dc_for_class(ctx, class_name) for class_name in matching_classes),
            key=lambda item: (item[0], item[1]),
        )

    def _actor_spellcasting_ability_modifier(self, ctx: _Context) -> int:
        owner = self._resource_owner(ctx.actor_id)
        if not isinstance(owner, Character):
            raise AutomationError("spellcasting_ability_modifier requires a character actor")
        class_levels = {
            str(class_name).lower(): int(level) for class_name, level in owner.class_levels.items()
        }
        candidate_classes = self._spell_save_dc_candidate_classes(ctx.action)
        matching_classes = [
            class_name for class_name in candidate_classes if class_levels.get(class_name, 0) > 0
        ]
        if not matching_classes:
            raise AutomationError("actor has no matching spellcasting class for this spell")
        entity = self._entity(ctx.actor_id)
        return max(
            self._ability_modifier(entity, SPELLCASTING_ABILITIES[class_name])
            for class_name in matching_classes
        )

    def _spell_save_dc_candidate_classes(self, action: ActionDefinition) -> list[str]:
        raw_candidates = action.properties.get("spell_classes")
        if isinstance(raw_candidates, list) and raw_candidates:
            candidates = [str(item).lower() for item in raw_candidates]
        else:
            class_any = action.requirements.get("class_any")
            if isinstance(class_any, str):
                candidates = [class_any.lower()]
            elif isinstance(class_any, list):
                candidates = [str(item).lower() for item in class_any]
            else:
                candidates = list(SPELLCASTING_ABILITIES)
        return sorted(
            {class_name for class_name in candidates if class_name in SPELLCASTING_ABILITIES}
        )

    def _spell_save_dc_for_class(self, ctx: _Context, class_name: str) -> tuple[int, str]:
        ability = SPELLCASTING_ABILITIES.get(class_name)
        if ability is None:
            raise AutomationError(f"unsupported spell_save_dc class: {class_name}")
        owner = self._resource_owner(ctx.actor_id)
        if not isinstance(owner, Character):
            raise AutomationError("spell_save_dc requires a character actor")
        proficiency = int(getattr(owner, "proficiency_bonus", 2))
        dc = 8 + proficiency + self._ability_modifier(self._entity(ctx.actor_id), ability)
        passive_bonus = self._spell_save_dc_bonus(self._entity(ctx.actor_id), class_name)
        dc += passive_bonus
        source = f"spell_save_dc:{class_name}"
        if passive_bonus:
            source = f"{source}+{passive_bonus}"
        return dc, source

    def _passive_roll_adjustment(
        self,
        entity: Character | Monster | Combatant,
        *,
        bonus_key: str,
        penalty_key: str,
    ) -> tuple[int, list[RollResult], list[dict[str, Any]]]:
        adjustment = 0
        rolls: list[RollResult] = []
        sources: list[dict[str, Any]] = []
        if bonus_key == "saving_throw_bonus_dice":
            aura_bonus, aura_sources = self._aura_of_protection_saving_throw_adjustment(entity)
            adjustment += aura_bonus
            sources.extend(aura_sources)
        for effect in self._status_effects_for(entity):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            keyed_adjustments = [(bonus_key, 1), (penalty_key, -1)]
            if bonus_key.endswith("_bonus_dice"):
                keyed_adjustments.append((bonus_key.removesuffix("_dice"), 1))
            if penalty_key.endswith("_penalty_dice"):
                keyed_adjustments.append((penalty_key.removesuffix("_dice"), -1))
            for key, sign in keyed_adjustments:
                if key not in modifiers:
                    continue
                value = modifiers[key]
                if isinstance(value, str):
                    roll = self.roll_service.roll(value)
                    rolls.append(roll)
                    amount = sign * roll.total
                    adjustment += amount
                    sources.append(
                        {
                            "effect_id": effect.get("effect_id"),
                            "source_action_id": effect.get("source_action_id"),
                            "modifier": key,
                            "expression": value,
                            "amount": amount,
                        }
                    )
                elif isinstance(value, int) and not isinstance(value, bool):
                    amount = sign * value
                    adjustment += amount
                    sources.append(
                        {
                            "effect_id": effect.get("effect_id"),
                            "source_action_id": effect.get("source_action_id"),
                            "modifier": key,
                            "amount": amount,
                        }
                    )
        return adjustment, rolls, sources

    def _aura_of_protection_saving_throw_adjustment(
        self,
        entity: Character | Monster | Combatant,
    ) -> tuple[int, list[dict[str, Any]]]:
        candidates: list[dict[str, Any]] = []
        target_combatant = entity if isinstance(entity, Combatant) else self._combatant_for(entity)
        if self.state.encounter is not None and target_combatant is not None:
            for paladin in self.state.encounter.combatants.values():
                if paladin.entity_id not in self.state.characters:
                    continue
                if paladin.side != target_combatant.side:
                    continue
                source = self.state.characters[paladin.entity_id]
                bonus = aura_of_protection_saving_throw_bonus(source)
                if bonus <= 0:
                    continue
                radius_ft = aura_of_protection_radius_ft(source)
                if self._condition_sources(paladin, {"incapacitated"}):
                    continue
                distance = (
                    0
                    if paladin.id == target_combatant.id
                    else self._combat_distance(paladin, target_combatant)
                )
                if distance is None or distance > radius_ft:
                    continue
                candidates.append(
                    {
                        "source_action_id": AURA_OF_PROTECTION_ACTION_ID,
                        "modifier": "aura_of_protection",
                        "source_actor_id": paladin.id,
                        "target_id": target_combatant.id,
                        "distance_ft": distance,
                        "radius_ft": radius_ft,
                        "amount": bonus,
                    }
                )
        elif isinstance(entity, Character):
            bonus = aura_of_protection_saving_throw_bonus(entity)
            if bonus > 0 and not has_condition(entity.status_effects, "incapacitated"):
                candidates.append(
                    {
                        "source_action_id": AURA_OF_PROTECTION_ACTION_ID,
                        "modifier": "aura_of_protection",
                        "source_actor_id": entity.id,
                        "target_id": entity.id,
                        "amount": bonus,
                    }
                )
        if not candidates:
            return 0, []
        best_amount = max(int(candidate["amount"]) for candidate in candidates)
        best_sources = [
            candidate for candidate in candidates if int(candidate["amount"]) == best_amount
        ]
        return best_amount, best_sources

    def _combatant_for(
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
            if combatant.entity_id == entity_id or combatant.id == entity_id:
                return combatant
        return None

    def _sacred_weapon_attack_bonus(
        self,
        ctx: _Context,
        node: dict[str, Any],
    ) -> tuple[int, list[dict[str, Any]]]:
        effect = self._sacred_weapon_effect(ctx)
        if effect is None:
            return 0, []
        modifiers = effect.get("passive_modifiers", {})
        if not isinstance(modifiers, dict):
            return 0, []
        ability = modifiers.get("sacred_weapon_attack_bonus_ability")
        if not isinstance(ability, str):
            return 0, []
        minimum = int(modifiers.get("sacred_weapon_attack_bonus_minimum", 1))
        amount = max(
            minimum,
            self._ability_modifier(self._entity(ctx.actor_id), ability),
        )
        return amount, [
            {
                "effect_id": effect.get("effect_id"),
                "source_action_id": effect.get("source_action_id"),
                "modifier": "sacred_weapon_attack_bonus",
                "ability": ability,
                "minimum": minimum,
                "amount": amount,
                "selected_action_id": modifiers.get("sacred_weapon_action_id"),
            }
        ]

    def _sacred_weapon_damage_type(
        self,
        ctx: _Context,
        node: dict[str, Any],
        base_damage_type: str,
    ) -> str:
        requested = ctx.params.get("sacred_weapon_damage_type")
        if requested is None:
            return base_damage_type
        choice = str(requested).lower()
        if choice in {"normal", base_damage_type.lower()}:
            return base_damage_type
        if choice != "radiant":
            raise AutomationError("Sacred Weapon damage type must be normal or radiant")
        if self._sacred_weapon_effect(ctx) is None:
            return base_damage_type
        return "radiant"

    def _empowered_strikes_damage_type(
        self,
        ctx: _Context,
        node: dict[str, Any],
        base_damage_type: str,
    ) -> str:
        requested = ctx.params.get(
            "empowered_strikes_damage_type",
            ctx.params.get("unarmed_strike_damage_type"),
        )
        if requested is None:
            return base_damage_type
        choice = str(requested).casefold().strip()
        normal_types = {
            "normal",
            str(node.get("damage_type", "")).casefold(),
            base_damage_type.casefold(),
        }
        if choice in normal_types:
            return base_damage_type
        if choice != "force":
            raise AutomationError("empowered_strikes_damage_type must be normal or force")
        return "force"

    def _sacred_weapon_effect(self, ctx: _Context) -> dict[str, Any] | None:
        if not self._is_melee_weapon_attack_action(ctx.action):
            return None
        actor = self._entity(ctx.actor_id)
        for effect in self._status_effects_for(actor):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            if modifiers.get("sacred_weapon") is not True:
                continue
            if str(modifiers.get("sacred_weapon_action_id", "")) != ctx.action.id:
                continue
            return effect
        return None

    def _weapon_enhancement_bonus(self, ctx: _Context) -> tuple[int, list[dict[str, Any]]]:
        if ctx.action.action_type not in ATTACK_ACTION_TYPES:
            return 0, []
        best_amount = 0
        best_sources: list[dict[str, Any]] = []
        actor = self._entity(ctx.actor_id)
        for effect in self._status_effects_for(actor):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            selected_action_id = modifiers.get("weapon_bonus_action_id")
            if selected_action_id is not None and str(selected_action_id) != ctx.action.id:
                continue
            amount = self._optional_int(modifiers.get("weapon_enhancement_bonus"))
            if amount is None or amount <= 0:
                continue
            source = {
                "effect_id": effect.get("effect_id"),
                "source_action_id": effect.get("source_action_id"),
                "modifier": "weapon_enhancement_bonus",
                "amount": amount,
                "selected_action_id": selected_action_id,
            }
            if amount > best_amount:
                best_amount = amount
                best_sources = [source]
            elif amount == best_amount:
                best_sources.append(source)
        return best_amount, best_sources

    def _pact_weapon_attack_adjustment(
        self,
        ctx: _Context,
        node: dict[str, Any],
    ) -> tuple[int, list[dict[str, Any]]]:
        if ctx.params.get("use_pact_weapon_ability") is not True:
            return 0, []
        effect = self._pact_weapon_effect(ctx)
        if effect is None:
            raise AutomationError("Pact weapon ability requires the selected pact weapon")
        modifiers = effect.get("passive_modifiers", {})
        if not isinstance(modifiers, dict):
            return 0, []
        ability = str(modifiers.get("pact_weapon_attack_ability", "cha"))
        actor = self._entity(ctx.actor_id)
        desired = self._ability_modifier(actor, ability)
        current = self._current_attack_ability_modifier(actor, node)
        amount = desired - current
        return amount, [
            {
                "effect_id": effect.get("effect_id"),
                "source_action_id": effect.get("source_action_id"),
                "modifier": "pact_weapon_attack_ability",
                "ability": ability,
                "selected_action_id": modifiers.get("pact_weapon_action_id"),
                "amount": amount,
            }
        ]

    def _current_attack_ability_modifier(
        self,
        actor: Character | Monster | Combatant,
        node: dict[str, Any],
    ) -> int:
        if "attack_bonus" in node:
            proficiency = int(getattr(self._proficiency_source(actor), "proficiency_bonus", 2))
            return int(node["attack_bonus"]) - proficiency
        ability = str(node.get("ability", "str")).lower()
        return self._ability_modifier(actor, ability)

    def _ability_score_set_attack_adjustment(
        self,
        ctx: _Context,
        node: dict[str, Any],
        ability: str,
    ) -> tuple[int, list[dict[str, Any]]]:
        if ctx.action.action_type not in ATTACK_ACTION_TYPES:
            return 0, []
        if "attack_bonus" not in node:
            return 0, []
        actor = self._entity(ctx.actor_id)
        source = self._ability_source(actor)
        effects = self._ability_status_effects(actor, source)
        sources = ability_score_set_sources(source, ability, status_effects=effects)
        if not sources:
            return 0, []
        desired = self._ability_modifier(actor, ability)
        current = self._current_attack_ability_modifier(actor, node)
        amount = max(0, desired - current)
        if amount <= 0:
            return 0, []
        return amount, [{**source_entry, "amount": amount} for source_entry in sources]

    def _sundering_blow_attack_adjustment(
        self,
        ctx: _Context,
        target_id: str,
        path: str,
    ) -> tuple[int, list[dict[str, Any]], dict[str, Any] | None]:
        for owner_type, owner_id, effects in self._target_effect_lists(target_id):
            for index, effect in enumerate(list(effects)):
                modifiers = effect.get("passive_modifiers", {})
                if not isinstance(modifiers, dict):
                    continue
                amount = modifiers.get("sundering_blow_attack_bonus")
                if not isinstance(amount, int) or isinstance(amount, bool):
                    continue
                applied_by = effect.get("applied_by")
                if isinstance(applied_by, str) and self._entity_ids_match(
                    applied_by,
                    ctx.actor_id,
                ):
                    continue
                removed = {
                    "owner_type": owner_type,
                    "owner_id": owner_id,
                    "effect_id": effect.get("effect_id"),
                    "condition": effect.get("condition"),
                    "source_action_id": effect.get("source_action_id"),
                }
                del effects[index]
                source = {
                    "effect_id": effect.get("effect_id"),
                    "source_action_id": effect.get("source_action_id"),
                    "modifier": "sundering_blow_attack_bonus",
                    "amount": amount,
                    "applied_by": applied_by,
                }
                expired = {
                    "type": "effect_expired",
                    "target_id": target_id,
                    "trigger": "sundering_blow_attack_roll",
                    "removed": [removed],
                    "path": path,
                }
                return amount, [source], expired
        return 0, [], None

    def _pact_weapon_damage_type(self, ctx: _Context, base_damage_type: str) -> str:
        requested = ctx.params.get("pact_weapon_damage_type")
        if requested is None:
            return base_damage_type
        effect = self._pact_weapon_effect(ctx)
        if effect is None:
            raise AutomationError("Pact weapon damage type requires the selected pact weapon")
        modifiers = effect.get("passive_modifiers", {})
        allowed = modifiers.get("pact_weapon_damage_types", [])
        allowed_types = (
            {str(item).lower() for item in allowed} if isinstance(allowed, list) else set()
        )
        choice = str(requested).lower()
        if choice == "normal" or choice == base_damage_type.lower():
            return base_damage_type
        if choice not in allowed_types:
            raise AutomationError(
                "Pact weapon damage type must be normal, necrotic, psychic, or radiant"
            )
        return choice

    def _pact_weapon_damage_adjustment(
        self,
        ctx: _Context,
        node: dict[str, Any],
    ) -> tuple[int, list[dict[str, Any]]]:
        if ctx.params.get("use_pact_weapon_ability") is not True:
            return 0, []
        effect = self._pact_weapon_effect(ctx)
        if effect is None:
            raise AutomationError("Pact weapon ability requires the selected pact weapon")
        modifiers = effect.get("passive_modifiers", {})
        if not isinstance(modifiers, dict):
            return 0, []
        ability = str(modifiers.get("pact_weapon_damage_ability", "cha"))
        actor = self._entity(ctx.actor_id)
        desired = self._ability_modifier(actor, ability)
        current = self._current_damage_ability_modifier(node)
        amount = desired - current
        return amount, [
            {
                "effect_id": effect.get("effect_id"),
                "source_action_id": effect.get("source_action_id"),
                "modifier": "pact_weapon_damage_ability",
                "ability": ability,
                "selected_action_id": modifiers.get("pact_weapon_action_id"),
                "amount": amount,
            }
        ]

    @staticmethod
    def _current_damage_ability_modifier(node: dict[str, Any]) -> int:
        dice = node.get("dice")
        if not isinstance(dice, str):
            return 0
        match = re.fullmatch(r"\s*\d*d\d+(?:\s*([+-])\s*(\d+))?\s*", dice)
        if match is None or match.group(2) is None:
            return 0
        amount = int(match.group(2))
        return -amount if match.group(1) == "-" else amount

    def _pact_weapon_effect(self, ctx: _Context) -> dict[str, Any] | None:
        if not self._is_melee_weapon_attack_action(ctx.action):
            return None
        return self._active_pact_weapon_effect_for_action(ctx.actor_id, ctx.action.id)

    def _active_pact_weapon_effect_for_action(
        self,
        actor_id: str,
        action_id: str,
    ) -> dict[str, Any] | None:
        actor = self._entity(actor_id)
        for effect in self._status_effects_for(actor):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            if modifiers.get("pact_weapon") is not True:
                continue
            if str(modifiers.get("pact_weapon_action_id", "")) != action_id:
                continue
            return effect
        return None

    @staticmethod
    def _is_melee_weapon_attack_action(action: ActionDefinition) -> bool:
        if action.action_type != "weapon_attack":
            return False
        normal_range = action.range.get("normal_ft")
        if normal_range is None:
            return False
        return int(normal_range) <= 10

    def _passive_damage_bonus(
        self, ctx: _Context, node: dict[str, Any]
    ) -> tuple[int, list[dict[str, Any]]]:
        if ctx.action.action_type not in ATTACK_ACTION_TYPES | {"spell"}:
            return 0, []
        total = 0
        sources: list[dict[str, Any]] = []
        agonizing_blast_bonus = self._agonizing_blast_damage_bonus(ctx)
        if agonizing_blast_bonus:
            total += agonizing_blast_bonus
            sources.append(
                {
                    "source_action_id": "srd.agonizing_blast",
                    "modifier": "warlock_agonizing_blast",
                    "spell_id": ctx.action.properties.get("spell_definition_id"),
                    "amount": agonizing_blast_bonus,
                }
            )
        potent_spellcasting_bonus, potent_spellcasting_sources = (
            self._cleric_potent_spellcasting_damage_bonus(ctx)
        )
        total += potent_spellcasting_bonus
        sources.extend(potent_spellcasting_sources)
        elemental_affinity_bonus, elemental_affinity_sources = (
            self._draconic_elemental_affinity_damage_bonus(ctx, node)
        )
        total += elemental_affinity_bonus
        sources.extend(elemental_affinity_sources)
        if ctx.action.action_type not in ATTACK_ACTION_TYPES:
            return total, sources
        pact_weapon_bonus, pact_weapon_sources = self._pact_weapon_damage_adjustment(ctx, node)
        total += pact_weapon_bonus
        sources.extend(pact_weapon_sources)
        ability = node.get("ability")
        if not isinstance(ability, str):
            return total, sources
        ability = ability.lower()
        actor = self._entity(ctx.actor_id)
        enhancement_bonus, enhancement_sources = self._weapon_enhancement_bonus(ctx)
        total += enhancement_bonus
        sources.extend(enhancement_sources)
        score_set_bonus, score_set_sources = self._ability_score_set_damage_adjustment(
            actor,
            ability,
            node,
        )
        total += score_set_bonus
        sources.extend(score_set_sources)
        for effect in self._status_effects_for(actor):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            bonuses = modifiers.get("weapon_damage_bonus_by_ability", {})
            if not isinstance(bonuses, dict) or ability not in bonuses:
                continue
            amount = int(bonuses[ability])
            total += amount
            sources.append(
                {
                    "effect_id": effect.get("effect_id"),
                    "source_action_id": effect.get("source_action_id"),
                    "modifier": "weapon_damage_bonus_by_ability",
                    "ability": ability,
                    "amount": amount,
                }
            )
        return total, sources

    def _draconic_elemental_affinity_damage_bonus(
        self,
        ctx: _Context,
        node: dict[str, Any],
    ) -> tuple[int, list[dict[str, Any]]]:
        if ctx.action.action_type != "spell" or ctx.elemental_affinity_applied:
            return 0, []
        damage_type = str(node.get("damage_type", "")).lower()
        actor = self._resource_owner(ctx.actor_id)
        if not isinstance(actor, Character):
            return 0, []
        bonus = draconic_elemental_affinity_damage_bonus(actor, damage_type=damage_type)
        if bonus <= 0:
            return 0, []
        ctx.elemental_affinity_applied = True
        return bonus, [
            {
                "source_action_id": "srd.elemental_affinity",
                "modifier": "draconic_elemental_affinity",
                "damage_type": damage_type,
                "amount": bonus,
            }
        ]

    def _ability_score_set_damage_adjustment(
        self,
        actor: Character | Monster | Combatant,
        ability: str,
        node: dict[str, Any],
    ) -> tuple[int, list[dict[str, Any]]]:
        bonus_from = node.get("bonus_from")
        if (
            isinstance(bonus_from, dict)
            and str(bonus_from.get("ability_modifier", "")).lower() == ability
        ):
            return 0, []
        source = self._ability_source(actor)
        effects = self._ability_status_effects(actor, source)
        sources = ability_score_set_sources(source, ability, status_effects=effects)
        if not sources:
            return 0, []
        current = self._current_damage_ability_modifier(node)
        desired = self._ability_modifier(actor, ability)
        amount = max(0, desired - current)
        if amount <= 0:
            return 0, []
        return amount, [{**source_entry, "amount": amount} for source_entry in sources]

    def _enlarge_weapon_damage_bonus(
        self,
        ctx: _Context,
        target_id: str,
        damage_type: str,
    ) -> _ExtraDamageResult:
        if ctx.action.action_type not in {"weapon_attack", "unarmed_attack"}:
            return _ExtraDamageResult()
        if not ctx.attack_hits.get(target_id, False):
            return _ExtraDamageResult()
        actor = self._entity(ctx.actor_id)
        for effect in self._status_effects_for(actor):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict) or modifiers.get("size_change") != "enlarge":
                continue
            dice = modifiers.get("enlarge_weapon_damage_bonus")
            if not isinstance(dice, str) or not dice:
                continue
            roll = self.roll_service.roll(dice)
            rolls = [roll]
            amount = roll.total
            if ctx.attack_critical.get(target_id, False):
                critical_roll = self.roll_service.roll(dice)
                rolls.append(critical_roll)
                amount += critical_roll.total
            return _ExtraDamageResult(
                amount=amount,
                damage_type=damage_type,
                rolls=rolls,
                sources=[
                    {
                        "effect_id": effect.get("effect_id"),
                        "source_action_id": effect.get("source_action_id"),
                        "modifier": "enlarge_weapon_damage_bonus",
                        "dice": dice,
                        "damage_type": damage_type,
                    }
                ],
            )
        return _ExtraDamageResult()

    def _reduced_weapon_damage_penalty(
        self,
        ctx: _Context,
        node: dict[str, Any],
        target_id: str,
        amount: int,
    ) -> _DamageReductionResult | None:
        if ctx.action.action_type not in {"weapon_attack", "unarmed_attack"}:
            return None
        if not ctx.attack_hits.get(target_id, False):
            return None
        if node.get("requires_hit") is not True:
            return None
        actor = self._entity(ctx.actor_id)
        for effect in self._status_effects_for(actor):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict) or modifiers.get("size_change") != "reduce":
                continue
            dice = modifiers.get("reduce_weapon_damage_penalty")
            if not isinstance(dice, str) or not dice:
                continue
            roll = self.roll_service.roll(dice)
            amount_after = max(1, amount - roll.total)
            return _DamageReductionResult(
                amount_before=amount,
                amount_after=amount_after,
                reduction=amount - amount_after,
                rolls=[roll],
                sources=[
                    {
                        "effect_id": effect.get("effect_id"),
                        "source_action_id": effect.get("source_action_id"),
                        "modifier": "reduce_weapon_damage_penalty",
                        "dice": dice,
                        "roll_total": roll.total,
                    }
                ],
            )
        return None

    def _brutal_strike_attack_forgo_advantage(
        self,
        ctx: _Context,
        node: dict[str, Any],
        target_id: str,
        ability: str,
        *,
        node_advantage: str | None,
        status_advantage: str | None,
        status_sources: list[dict[str, Any]],
        advantage: str | None,
    ) -> dict[str, Any] | None:
        if not self._brutal_strike_requested(ctx.params):
            return None
        self._validate_brutal_strike_attack_context(
            ctx.action,
            ctx.actor_id,
            target_id,
            node,
            ability,
            params=ctx.params,
            node_advantage=node_advantage,
            status_advantage=status_advantage,
            status_sources=status_sources,
            advantage=advantage,
        )
        effects = self._brutal_strike_effects(ctx.params)
        if not effects:
            raise AutomationError("Brutal Strike requires an effect choice")
        forgone_sources = [source for source in status_sources if source.get("kind") == "advantage"]
        if node_advantage == "advantage":
            forgone_sources.append({"kind": "advantage", "modifier": "attack_node_advantage"})
        return {
            "source_action_id": BRUTAL_STRIKE_ACTION_ID,
            "effect": effects[0],
            "effects": effects,
            "forgone_advantage": True,
            "advantage_before_forgo": advantage,
            "forgone_advantage_sources": forgone_sources,
        }

    def _validate_brutal_strike_attack_context(
        self,
        action: ActionDefinition,
        actor_id: str,
        target_id: str,
        node: dict[str, Any],
        ability: str,
        *,
        params: dict[str, Any],
        node_advantage: str | None,
        status_advantage: str | None,
        status_sources: list[dict[str, Any]],
        advantage: str | None,
    ) -> None:
        if action.action_type not in {"weapon_attack", "unarmed_attack"}:
            raise AutomationError("Brutal Strike requires a weapon or Unarmed Strike attack")
        if str(ability).lower() != "str":
            raise AutomationError("Brutal Strike requires a Strength-based attack roll")
        actor_owner = self._resource_owner(actor_id)
        if not isinstance(actor_owner, Character) or not has_barbarian_feature(
            actor_owner,
            level=9,
        ):
            raise AutomationError("Brutal Strike requires Barbarian level 9")
        actor = self._entity(actor_id)
        if not has_condition(self._status_effects_for(actor), "reckless_attack"):
            raise AutomationError("Brutal Strike requires Reckless Attack")
        if self._has_brutal_strike_used(actor_id):
            raise AutomationError("Brutal Strike can be used on only one attack roll per turn")
        disadvantage_sources = [
            source for source in status_sources if source.get("kind") == "disadvantage"
        ]
        if (
            node_advantage == "disadvantage"
            or status_advantage == "disadvantage"
            or disadvantage_sources
        ):
            raise AutomationError(
                "Brutal Strike cannot be used on an attack roll with Disadvantage"
            )
        if advantage != "advantage":
            raise AutomationError("Brutal Strike requires Advantage to forgo")
        effects = self._brutal_strike_effects(params)
        if not effects:
            raise AutomationError("Brutal Strike requires an effect choice")
        for effect in effects:
            if effect in IMPROVED_BRUTAL_STRIKE_EFFECTS and not has_barbarian_feature(
                actor_owner,
                level=13,
            ):
                raise AutomationError("Improved Brutal Strike requires Barbarian level 13")
        if len(effects) > 1 and not has_barbarian_feature(actor_owner, level=17):
            raise AutomationError("Improved Brutal Strike requires Barbarian level 17")
        if target_id not in (self.state.encounter.combatants if self.state.encounter else {}):
            self._entity(target_id)

    def _brutal_strike_bonus(
        self,
        ctx: _Context,
        node: dict[str, Any],
        target_id: str,
        damage_type: str,
    ) -> _BrutalStrikeResult:
        effects = ctx.brutal_strike_effects.get(target_id, [])
        if not effects:
            return _BrutalStrikeResult()
        if ctx.action.action_type not in {"weapon_attack", "unarmed_attack"}:
            return _BrutalStrikeResult()
        if str(node.get("ability", "")).lower() != "str":
            return _BrutalStrikeResult()
        if not ctx.attack_hits.get(target_id, False):
            return _BrutalStrikeResult(effect=effects[0], effects=effects)
        actor_owner = self._resource_owner(ctx.actor_id)
        barbarian_level = (
            int(actor_owner.class_levels.get("barbarian", 0))
            if isinstance(actor_owner, Character)
            else 0
        )
        dice = "2d10" if barbarian_level >= 17 else "1d10"
        roll = self.roll_service.roll(dice)
        rolls = [roll]
        amount = roll.total
        if ctx.attack_critical.get(target_id, False):
            critical_roll = self.roll_service.roll(dice)
            rolls.append(critical_roll)
            amount += critical_roll.total
        return _BrutalStrikeResult(
            amount=amount,
            effect=effects[0],
            effects=effects,
            rolls=rolls,
            sources=[
                {
                    "feature": "brutal_strike",
                    "source_action_id": BRUTAL_STRIKE_ACTION_ID,
                    "barbarian_level": barbarian_level,
                    "dice": dice,
                    "damage_type": damage_type,
                    "effect": effects[0],
                    "effects": effects,
                    "forgone_advantage": True,
                }
            ],
        )

    def _apply_brutal_strike_effect(
        self,
        ctx: _Context,
        target_id: str,
        effect: str,
        path: str,
    ) -> None:
        base_change: dict[str, Any] = {
            "type": "brutal_strike",
            "actor_id": ctx.actor_id,
            "target_id": target_id,
            "effect": effect,
            "source_action_id": BRUTAL_STRIKE_ACTION_ID,
            "path": path,
        }
        if effect == "forceful_blow":
            destination = self._brutal_strike_forceful_destination(ctx.params, target_id=target_id)
            if destination is None:
                raise AutomationError("Brutal Strike Forceful Blow requires a destination position")
            base_change.update(
                self._apply_brutal_strike_forceful_push(ctx, target_id, destination, path)
            )
            follow_destination = self._brutal_strike_forceful_follow_destination(
                ctx.params,
                target_id=target_id,
            )
            if follow_destination is not None:
                base_change["follow_move"] = self._apply_brutal_strike_forceful_follow(
                    ctx,
                    target_id,
                    follow_destination,
                    path,
                )
            ctx.result.state_changes.append(base_change)
            return
        if effect == "hamstring_blow":
            ctx.result.state_changes.append(base_change)
            self._apply_brutal_strike_hamstring(ctx, target_id, path)
            return
        if effect == "staggering_blow":
            ctx.result.state_changes.append(base_change)
            self._apply_brutal_strike_staggering(ctx, target_id, path)
            return
        if effect == "sundering_blow":
            ctx.result.state_changes.append(base_change)
            self._apply_brutal_strike_sundering(ctx, target_id, path)
            return
        raise AutomationError(f"unsupported Brutal Strike effect: {effect}")

    def _apply_brutal_strike_forceful_push(
        self,
        ctx: _Context,
        target_id: str,
        destination: str,
        path: str,
    ) -> dict[str, Any]:
        plan = self._brutal_strike_forceful_plan(ctx.actor_id, target_id, destination)
        target = plan["target"]
        assert isinstance(target, Combatant)
        before_position = target.position_node_id
        target.position_node_id = destination
        return {
            "from": before_position,
            "to": target.position_node_id,
            "forced_movement_distance": int(plan["movement_distance"]),
            "distance_from_actor_before": plan["distance_from_actor_before"],
            "distance_from_actor_after": plan["distance_from_actor_after"],
            "path": f"{path}.brutal_strike",
        }

    def _apply_brutal_strike_forceful_follow(
        self,
        ctx: _Context,
        target_id: str,
        destination: str,
        path: str,
    ) -> dict[str, Any]:
        plan = self._brutal_strike_forceful_follow_plan(ctx.actor_id, target_id, destination)
        actor = plan["actor"]
        assert isinstance(actor, Combatant)
        before_position = actor.position_node_id
        actor.position_node_id = destination
        before_used, after_used = self.economy.add(
            ctx.actor_id,
            "movement_used",
            int(plan["movement_cost"]),
        )
        return {
            "actor_id": ctx.actor_id,
            "from": before_position,
            "to": actor.position_node_id,
            "movement_cost": int(plan["movement_cost"]),
            "movement_limit": int(plan["movement_limit"]),
            "movement_used_before": before_used,
            "movement_used_after": after_used,
            "distance_to_target_before": plan["distance_to_target_before"],
            "distance_to_target_after": plan["distance_to_target_after"],
            "opportunity_attack_triggers": [],
            "path": f"{path}.brutal_strike.follow",
        }

    def _apply_brutal_strike_hamstring(
        self,
        ctx: _Context,
        target_id: str,
        path: str,
    ) -> None:
        target = self._entity(target_id)
        effect = EffectInstance(
            effect_id=self._effect_id(target_id, "brutal_strike_hamstring"),
            source_ref="SRD 5.2.1 Barbarian Class Features: Level 9: Brutal Strike",
            source_action_id=BRUTAL_STRIKE_ACTION_ID,
            target_id=target_id,
            applied_by=ctx.actor_id,
            condition="hamstring_blow",
            duration={"until": "start_of_next_turn", "turn_owner_id": ctx.actor_id},
            tick_on="self_turn_start",
            stacking_policy="replace",
            passive_modifiers={"speed_bonus_ft": -15},
            audit={"node_path": path, "feature": "brutal_strike", "effect": "hamstring_blow"},
        )
        effects = getattr(target, "status_effects")
        effects[:] = [
            existing
            for existing in effects
            if existing.get("condition") != "hamstring_blow"
            or existing.get("source_action_id") != BRUTAL_STRIKE_ACTION_ID
        ]
        effects.append(effect.to_dict())
        ctx.result.state_changes.append(
            {
                "type": "condition",
                "target_id": target_id,
                "condition": effect.condition,
                "effect_id": effect.effect_id,
                "source_action_id": effect.source_action_id,
                "passive_modifiers": effect.passive_modifiers,
                "duration": effect.duration,
                "tick_on": effect.tick_on,
                "path": f"{path}.brutal_strike",
            }
        )

    def _apply_brutal_strike_staggering(
        self,
        ctx: _Context,
        target_id: str,
        path: str,
    ) -> None:
        self._apply_brutal_strike_condition(
            ctx,
            target_id,
            "staggering_blow_save_disadvantage",
            path,
            passive_modifiers={"next_saving_throw_disadvantage": True},
        )
        self._apply_brutal_strike_condition(
            ctx,
            target_id,
            "staggering_blow_no_opportunity_attacks",
            path,
            passive_modifiers={"cannot_make_opportunity_attacks": True},
        )

    def _apply_brutal_strike_sundering(
        self,
        ctx: _Context,
        target_id: str,
        path: str,
    ) -> None:
        self._apply_brutal_strike_condition(
            ctx,
            target_id,
            "sundering_blow",
            path,
            passive_modifiers={
                "sundering_blow_attack_bonus": 5,
                "sundering_blow_applied_by": ctx.actor_id,
            },
        )

    def _apply_brutal_strike_condition(
        self,
        ctx: _Context,
        target_id: str,
        condition: str,
        path: str,
        *,
        passive_modifiers: dict[str, Any],
    ) -> None:
        target = self._entity(target_id)
        effect = EffectInstance(
            effect_id=self._effect_id(target_id, f"brutal_strike_{condition}"),
            source_ref=("SRD 5.2.1 Barbarian Class Features: Level 13: Improved Brutal Strike"),
            source_action_id=BRUTAL_STRIKE_ACTION_ID,
            target_id=target_id,
            applied_by=ctx.actor_id,
            condition=condition,
            passive_modifiers=passive_modifiers,
            duration={"until": "start_of_next_turn", "turn_owner_id": ctx.actor_id},
            tick_on="self_turn_start",
            stacking_policy="replace",
            audit={"node_path": path, "feature": "brutal_strike", "effect": condition},
        )
        effects = getattr(target, "status_effects")
        effects[:] = [
            existing
            for existing in effects
            if existing.get("condition") != condition
            or existing.get("source_action_id") != BRUTAL_STRIKE_ACTION_ID
        ]
        effects.append(effect.to_dict())
        ctx.result.state_changes.append(
            {
                "type": "condition",
                "target_id": target_id,
                "condition": effect.condition,
                "effect_id": effect.effect_id,
                "source_action_id": effect.source_action_id,
                "passive_modifiers": effect.passive_modifiers,
                "duration": effect.duration,
                "tick_on": effect.tick_on,
                "path": f"{path}.brutal_strike",
            }
        )

    def _has_brutal_strike_used(self, actor_id: str) -> bool:
        actor = self._entity(actor_id)
        return any(
            effect.get("condition") == "brutal_strike_used"
            and effect.get("source_action_id") == BRUTAL_STRIKE_ACTION_ID
            for effect in self._status_effects_for(actor)
        )

    def _mark_brutal_strike_used(
        self,
        ctx: _Context,
        target_id: str,
        effects: list[str],
    ) -> None:
        actor = self._entity(ctx.actor_id)
        primary_effect = effects[0] if effects else None
        marker = EffectInstance(
            effect_id=self._effect_id(ctx.actor_id, "brutal_strike_used"),
            source_ref="SRD 5.2.1 Barbarian Class Features: Level 9: Brutal Strike",
            source_action_id=BRUTAL_STRIKE_ACTION_ID,
            target_id=ctx.actor_id,
            applied_by=ctx.actor_id,
            condition="brutal_strike_used",
            duration={"until": "start_of_next_turn"},
            tick_on="self_turn_start",
            stacking_policy="replace",
            audit={"target_id": target_id, "effect": primary_effect, "effects": effects},
        )
        getattr(actor, "status_effects").append(marker.to_dict())
        ctx.result.state_changes.append(
            {
                "type": "brutal_strike_used",
                "actor_id": ctx.actor_id,
                "target_id": target_id,
                "effect": primary_effect,
                "effects": effects,
                "effect_id": marker.effect_id,
                "source_action_id": marker.source_action_id,
            }
        )

    def _agonizing_blast_damage_bonus(self, ctx: _Context) -> int:
        if ctx.action.action_type != "spell":
            return 0
        owner = self._resource_owner(ctx.actor_id)
        if not isinstance(owner, Character):
            return 0
        spell_id = ctx.action.properties.get("spell_definition_id")
        return warlock_agonizing_blast_bonus(
            owner,
            spell_id=str(spell_id) if isinstance(spell_id, str) else None,
        )

    def _cleric_potent_spellcasting_damage_bonus(
        self,
        ctx: _Context,
    ) -> tuple[int, list[dict[str, Any]]]:
        if ctx.action.action_type != "spell":
            return 0, []
        owner = self._resource_owner(ctx.actor_id)
        if not isinstance(owner, Character):
            return 0, []
        bonus = cleric_potent_spellcasting_bonus(
            owner,
            spell_level=self._action_spell_level(ctx.action),
            spell_classes=self._action_spell_classes(ctx.action),
        )
        if bonus <= 0:
            return 0, []
        return bonus, [
            {
                "source_action_id": CLERIC_BLESSED_STRIKES_POTENT_SPELLCASTING_ACTION_ID,
                "modifier": "cleric_potent_spellcasting",
                "spell_id": ctx.action.properties.get("spell_definition_id"),
                "amount": bonus,
            }
        ]

    @staticmethod
    def _action_spell_level(action: ActionDefinition) -> int | None:
        raw = action.properties.get("spell_level", action.requirements.get("spell_level"))
        if not isinstance(raw, int | str):
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _action_spell_classes(action: ActionDefinition) -> list[str]:
        raw = action.properties.get("spell_classes", [])
        if isinstance(raw, str):
            return [raw.lower()]
        if isinstance(raw, list):
            return [str(item).lower() for item in raw if isinstance(item, str)]
        return []

    def _action_is_cleric_cantrip(self, action: ActionDefinition) -> bool:
        return self._action_spell_level(action) == 0 and "cleric" in self._action_spell_classes(
            action
        )

    def _frenzy_bonus(
        self,
        ctx: _Context,
        node: dict[str, Any],
        target_id: str,
        damage_type: str,
    ) -> _FrenzyResult:
        if ctx.action.action_type not in {"weapon_attack", "unarmed_attack"}:
            return _FrenzyResult()
        ability = node.get("ability")
        if not isinstance(ability, str) or ability.lower() != "str":
            return _FrenzyResult()
        actor_owner = self._resource_owner(ctx.actor_id)
        if not isinstance(actor_owner, Character):
            return _FrenzyResult()
        if not has_barbarian_berserker_feature(actor_owner, level=3):
            return _FrenzyResult()
        actor = self._entity(ctx.actor_id)
        effects = self._status_effects_for(actor)
        if not has_condition(effects, "raging") or not has_condition(effects, "reckless_attack"):
            return _FrenzyResult()
        if self._has_frenzy_used(ctx.actor_id):
            return _FrenzyResult()
        rage_damage_bonus = barbarian_rage_damage_bonus(actor_owner)
        if rage_damage_bonus <= 0:
            return _FrenzyResult()
        dice = f"{rage_damage_bonus}d6"
        roll = self.roll_service.roll(dice)
        rolls = [roll]
        amount = roll.total
        if ctx.attack_critical.get(target_id, False):
            critical_roll = self.roll_service.roll(dice)
            rolls.append(critical_roll)
            amount += critical_roll.total
        self._mark_frenzy_used(ctx, target_id)
        return _FrenzyResult(
            amount=amount,
            rolls=rolls,
            sources=[
                {
                    "feature": "frenzy",
                    "source_action_id": "srd.frenzy",
                    "barbarian_level": int(actor_owner.class_levels.get("barbarian", 0)),
                    "rage_damage_bonus": rage_damage_bonus,
                    "dice": dice,
                    "damage_type": damage_type,
                }
            ],
        )

    def _has_frenzy_used(self, actor_id: str) -> bool:
        actor = self._entity(actor_id)
        return any(
            effect.get("condition") == "frenzy_used"
            and effect.get("source_action_id") == "srd.frenzy"
            for effect in self._status_effects_for(actor)
        )

    def _mark_frenzy_used(self, ctx: _Context, target_id: str) -> None:
        actor = self._entity(ctx.actor_id)
        effect = EffectInstance(
            effect_id=self._effect_id(ctx.actor_id, "frenzy_used"),
            source_ref="SRD 5.2.1 Barbarian Subclass: Path of the Berserker, Level 3: Frenzy",
            source_action_id="srd.frenzy",
            target_id=ctx.actor_id,
            applied_by=ctx.actor_id,
            condition="frenzy_used",
            duration={"until": "start_of_next_turn"},
            tick_on="self_turn_start",
            stacking_policy="replace",
            audit={"target_id": target_id},
        )
        getattr(actor, "status_effects").append(effect.to_dict())
        ctx.result.state_changes.append(
            {
                "type": "frenzy",
                "target_id": target_id,
                "effect_id": effect.effect_id,
                "condition": effect.condition,
                "source_action_id": effect.source_action_id,
            }
        )

    def _colossus_slayer_bonus(
        self,
        ctx: _Context,
        target_id: str,
        damage_type: str,
    ) -> _ExtraDamageResult:
        if ctx.action.action_type != "weapon_attack":
            return _ExtraDamageResult()
        if not ctx.attack_hits.get(target_id, False):
            return _ExtraDamageResult()
        actor_owner = self._resource_owner(ctx.actor_id)
        if not isinstance(actor_owner, Character) or not has_colossus_slayer(actor_owner):
            return _ExtraDamageResult()
        target = self._entity(target_id)
        if int(getattr(target, "hp_current")) >= int(getattr(target, "hp_max")):
            return _ExtraDamageResult()
        if self._has_colossus_slayer_used(ctx.actor_id):
            return _ExtraDamageResult()
        dice = "1d8"
        roll = self.roll_service.roll(dice)
        rolls = [roll]
        amount = roll.total
        if ctx.attack_critical.get(target_id, False):
            critical_roll = self.roll_service.roll(dice)
            rolls.append(critical_roll)
            amount += critical_roll.total
        self._mark_colossus_slayer_used(ctx, target_id)
        return _ExtraDamageResult(
            amount=amount,
            damage_type=damage_type,
            rolls=rolls,
            sources=[
                {
                    "feature": "colossus_slayer",
                    "source_action_id": COLOSSUS_SLAYER_ACTION_ID,
                    "dice": dice,
                    "damage_type": damage_type,
                }
            ],
        )

    def _has_colossus_slayer_used(self, actor_id: str) -> bool:
        actor = self._entity(actor_id)
        return any(
            effect.get("condition") == "colossus_slayer_used"
            and effect.get("source_action_id") == COLOSSUS_SLAYER_ACTION_ID
            for effect in self._status_effects_for(actor)
        )

    def _mark_colossus_slayer_used(self, ctx: _Context, target_id: str) -> None:
        actor = self._entity(ctx.actor_id)
        effect = EffectInstance(
            effect_id=self._effect_id(ctx.actor_id, "colossus_slayer_used"),
            source_ref=(
                "SRD 5.2.1 Ranger Subclass: Hunter, Level 3: Hunter's Prey, Colossus Slayer"
            ),
            source_action_id=COLOSSUS_SLAYER_ACTION_ID,
            target_id=ctx.actor_id,
            applied_by=ctx.actor_id,
            condition="colossus_slayer_used",
            duration={"until": "start_of_next_turn"},
            tick_on="self_turn_start",
            stacking_policy="replace",
            audit={"target_id": target_id},
        )
        getattr(actor, "status_effects").append(effect.to_dict())
        ctx.result.state_changes.append(
            {
                "type": "colossus_slayer",
                "target_id": target_id,
                "effect_id": effect.effect_id,
                "condition": effect.condition,
                "source_action_id": effect.source_action_id,
            }
        )

    def _apply_horde_breaker_if_requested(
        self,
        ctx: _Context,
        damage_node: dict[str, Any],
        path: str,
    ) -> None:
        if ctx.horde_breaker_resolving or ctx.horde_breaker_applied:
            return
        if ctx.params.get("use_horde_breaker") is not True:
            return
        if ctx.action.action_type != "weapon_attack" or ctx.last_attack_node is None:
            return
        target_id = str(ctx.params.get("horde_breaker_target_id"))
        self._mark_horde_breaker_used(ctx, target_id)
        previous_targets = list(ctx.targets)
        try:
            ctx.horde_breaker_resolving = True
            ctx.horde_breaker_applied = True
            ctx.targets = [target_id]
            self._node_attack_roll(
                ctx,
                dict(ctx.last_attack_node),
                f"{path}.horde_breaker.attack_roll",
            )
            self._node_damage(ctx, damage_node, f"{path}.horde_breaker.damage")
        finally:
            ctx.targets = previous_targets
            ctx.horde_breaker_resolving = False

    def _mark_horde_breaker_used(self, ctx: _Context, target_id: str) -> None:
        actor = self._entity(ctx.actor_id)
        effect = EffectInstance(
            effect_id=self._effect_id(ctx.actor_id, HORDE_BREAKER_USED_CONDITION),
            source_ref=("SRD 5.2.1 Ranger Subclass: Hunter, Level 3: Hunter's Prey, Horde Breaker"),
            source_action_id=HORDE_BREAKER_ACTION_ID,
            target_id=ctx.actor_id,
            applied_by=ctx.actor_id,
            condition=HORDE_BREAKER_USED_CONDITION,
            duration={"until": "start_of_next_turn"},
            tick_on="self_turn_start",
            stacking_policy="replace",
            audit={"target_id": target_id},
        )
        getattr(actor, "status_effects").append(effect.to_dict())
        ctx.result.state_changes.append(
            {
                "type": "horde_breaker",
                "target_id": target_id,
                "effect_id": effect.effect_id,
                "condition": effect.condition,
                "source_action_id": effect.source_action_id,
            }
        )

    def _has_horde_breaker_used(self, actor_id: str) -> bool:
        actor = self._entity(actor_id)
        return any(
            effect.get("condition") == HORDE_BREAKER_USED_CONDITION
            and effect.get("source_action_id") == HORDE_BREAKER_ACTION_ID
            for effect in self._status_effects_for(actor)
        )

    @staticmethod
    def _superior_hunters_prey_target_id(params: dict[str, Any]) -> str | None:
        raw = params.get("superior_hunters_prey_target_id") or params.get(
            "superior_hunter_prey_target_id"
        )
        if raw in (None, "", False):
            return None
        return str(raw)

    def _validate_superior_hunters_prey_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        targets: list[str],
        params: dict[str, Any],
    ) -> None:
        target_id = self._superior_hunters_prey_target_id(params)
        if params.get("use_superior_hunters_prey") is not True and target_id is None:
            return
        if target_id is None:
            raise AutomationError("Superior Hunter's Prey requires superior_hunters_prey_target_id")
        actor_owner = self._resource_owner(actor_id)
        if not isinstance(actor_owner, Character) or not has_superior_hunters_prey(actor_owner):
            raise AutomationError("Superior Hunter's Prey requires Ranger Hunter level 11")
        if self._has_superior_hunters_prey_used(actor_id):
            raise AutomationError("Superior Hunter's Prey can be used only once per turn")
        if len(targets) != 1:
            raise AutomationError("Superior Hunter's Prey requires exactly one marked target")
        original_target_id = targets[0]
        if not self._target_marked_by_hunters_mark(actor_id, original_target_id):
            raise AutomationError(
                "Superior Hunter's Prey requires a target marked by your Hunter's Mark"
            )
        if target_id == original_target_id:
            raise AutomationError("Superior Hunter's Prey target must be a different creature")
        self._entity(target_id)
        self._validate_superior_hunters_prey_secondary_target(
            actor_id,
            original_target_id,
            target_id,
        )

    def _validate_superior_hunters_prey_secondary_target(
        self,
        actor_id: str,
        original_target_id: str,
        secondary_target_id: str,
    ) -> None:
        actor = self._entity(actor_id)
        original_target = self._entity(original_target_id)
        secondary_target = self._entity(secondary_target_id)
        if not (
            isinstance(actor, Combatant)
            and isinstance(original_target, Combatant)
            and isinstance(secondary_target, Combatant)
        ):
            raise AutomationError("Superior Hunter's Prey requires tactical combat targets")
        if (
            self.state.encounter is None
            or self.state.encounter.tactical_graph is None
            or actor.position_node_id is None
            or original_target.position_node_id is None
            or secondary_target.position_node_id is None
        ):
            raise AutomationError("Superior Hunter's Prey requires tactical positions")
        graph = TacticalGraph.from_dict(self.state.encounter.tactical_graph)
        distance = graph.shortest_distance(
            original_target.position_node_id,
            secondary_target.position_node_id,
        )
        if distance is None or int(distance) > 30:
            raise AutomationError(
                "Superior Hunter's Prey target must be within 30 feet of the marked target"
            )
        if not graph.has_line_of_sight(actor.position_node_id, secondary_target.position_node_id):
            raise AutomationError("Superior Hunter's Prey target must be visible")

    def _apply_superior_hunters_prey_if_requested(
        self,
        ctx: _Context,
        original_target_id: str,
        original_damage_taken: int,
        path: str,
    ) -> None:
        secondary_target_id = self._superior_hunters_prey_target_id(ctx.params)
        if ctx.params.get("use_superior_hunters_prey") is not True and secondary_target_id is None:
            return
        if secondary_target_id is None or ctx.superior_hunters_prey_applied:
            return
        if original_damage_taken <= 0:
            return
        actor_owner = self._resource_owner(ctx.actor_id)
        if not isinstance(actor_owner, Character) or not has_superior_hunters_prey(actor_owner):
            return
        if self._has_superior_hunters_prey_used(ctx.actor_id):
            return
        mark_effect = self._hunters_mark_effect(ctx.actor_id, original_target_id)
        if mark_effect is None:
            return
        modifiers = mark_effect.get("passive_modifiers", {})
        if not isinstance(modifiers, dict):
            return
        dice = modifiers.get("attacker_bonus_damage")
        if not isinstance(dice, str) or not dice:
            return
        dice, dice_source = self._effective_hunters_mark_damage_dice(ctx.actor_id, dice)
        damage_type = str(modifiers.get("damage_type", "force"))
        roll = self.roll_service.roll(dice)
        ctx.result.dice_rolls.append(roll.to_dict())
        amount = roll.total
        secondary_target = self._entity(secondary_target_id)
        damage_taken = self._mitigated_damage(secondary_target, amount, damage_type)
        applied = self._apply_damage(
            secondary_target_id,
            amount,
            damage_type,
            ctx=ctx,
            path=f"{path}.superior_hunters_prey",
        )
        ctx.last_damage_taken[secondary_target_id] = damage_taken
        ctx.superior_hunters_prey_applied = True
        self._mark_superior_hunters_prey_used(ctx, secondary_target_id)
        ctx.result.state_changes.append(
            {
                "type": "damage",
                "target_id": secondary_target_id,
                "amount": amount,
                "applied": applied,
                "damage_type": damage_type,
                "feature": "superior_hunters_prey",
                "source_action_id": SUPERIOR_HUNTERS_PREY_ACTION_ID,
                "original_target_id": original_target_id,
                "path": f"{path}.superior_hunters_prey",
                "sources": [
                    {
                        "feature": "superior_hunters_prey",
                        "source_action_id": SUPERIOR_HUNTERS_PREY_ACTION_ID,
                        "hunters_mark_source_action_id": mark_effect.get("source_action_id"),
                        "effect_id": mark_effect.get("effect_id"),
                        "dice": dice,
                        **dice_source,
                        "damage_type": damage_type,
                    }
                ],
            }
        )
        concentration = self._concentration_save_after_damage(
            secondary_target_id,
            damage_taken,
            f"{path}.superior_hunters_prey",
        )
        if concentration is not None:
            concentration_change, concentration_roll = concentration
            ctx.result.dice_rolls.append(concentration_roll.to_dict())
            ctx.result.state_changes.append(concentration_change)
        if damage_taken > 0:
            ctx.result.state_changes.extend(
                self._expire_target_effects_on_damage(
                    ctx,
                    secondary_target_id,
                    f"{path}.superior_hunters_prey",
                    damage_source_actor_id=ctx.actor_id,
                )
            )

    def _hunters_mark_effect(self, actor_id: str, target_id: str) -> dict[str, Any] | None:
        target = self._entity(target_id)
        for effect in self._status_effects_for(target):
            if effect.get("applied_by") != actor_id:
                continue
            modifiers = effect.get("passive_modifiers", {})
            if isinstance(modifiers, dict) and modifiers.get("hunters_mark") is True:
                return effect
        return None

    def _mark_superior_hunters_prey_used(self, ctx: _Context, target_id: str) -> None:
        actor = self._entity(ctx.actor_id)
        effect = EffectInstance(
            effect_id=self._effect_id(ctx.actor_id, SUPERIOR_HUNTERS_PREY_USED_CONDITION),
            source_ref=("SRD 5.2.1 Ranger Subclass: Hunter, Level 11: Superior Hunter's Prey"),
            source_action_id=SUPERIOR_HUNTERS_PREY_ACTION_ID,
            target_id=ctx.actor_id,
            applied_by=ctx.actor_id,
            condition=SUPERIOR_HUNTERS_PREY_USED_CONDITION,
            duration={"until": "start_of_next_turn"},
            tick_on="self_turn_start",
            stacking_policy="replace",
            audit={"target_id": target_id},
        )
        getattr(actor, "status_effects").append(effect.to_dict())
        ctx.result.state_changes.append(
            {
                "type": "superior_hunters_prey",
                "target_id": target_id,
                "effect_id": effect.effect_id,
                "condition": effect.condition,
                "source_action_id": effect.source_action_id,
            }
        )

    def _has_superior_hunters_prey_used(self, actor_id: str) -> bool:
        actor = self._entity(actor_id)
        return any(
            effect.get("condition") == SUPERIOR_HUNTERS_PREY_USED_CONDITION
            and effect.get("source_action_id") == SUPERIOR_HUNTERS_PREY_ACTION_ID
            for effect in self._status_effects_for(actor)
        )

    def _validate_action_surge_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
    ) -> None:
        if action.id != ACTION_SURGE_ACTION_ID:
            return
        if self._has_action_surge_used_this_turn(actor_id):
            raise AutomationError("Action Surge already used this turn")

    def _mark_action_surge_used(self, ctx: _Context) -> None:
        if ctx.action.id != ACTION_SURGE_ACTION_ID:
            return
        actor = self._entity(ctx.actor_id)
        effect = EffectInstance(
            effect_id=self._effect_id(ctx.actor_id, ACTION_SURGE_USED_CONDITION),
            source_ref="SRD 5.2.1 Fighter Class Features: Level 2: Action Surge",
            source_action_id=ACTION_SURGE_ACTION_ID,
            target_id=ctx.actor_id,
            applied_by=ctx.actor_id,
            condition=ACTION_SURGE_USED_CONDITION,
            duration={"until": "start_of_next_turn"},
            tick_on="self_turn_start",
            stacking_policy="replace",
        )
        effects = getattr(actor, "status_effects")
        effects[:] = [
            existing
            for existing in effects
            if existing.get("condition") != ACTION_SURGE_USED_CONDITION
            or existing.get("source_action_id") != ACTION_SURGE_ACTION_ID
        ]
        effects.append(effect.to_dict())
        ctx.result.state_changes.append(
            {
                "type": "action_surge_used",
                "effect_id": effect.effect_id,
                "condition": effect.condition,
                "source_action_id": effect.source_action_id,
            }
        )

    def _has_action_surge_used_this_turn(self, actor_id: str) -> bool:
        actor = self._entity(actor_id)
        return any(
            effect.get("condition") == ACTION_SURGE_USED_CONDITION
            and effect.get("source_action_id") == ACTION_SURGE_ACTION_ID
            for effect in self._status_effects_for(actor)
        )

    def _mark_weapon_attack_target_this_turn(self, ctx: _Context, target_id: str) -> None:
        actor_owner = self._resource_owner(ctx.actor_id)
        if not isinstance(actor_owner, Character) or not has_horde_breaker(actor_owner):
            return
        if self._has_attacked_target_this_turn(ctx.actor_id, target_id):
            return
        actor = self._entity(ctx.actor_id)
        effect = EffectInstance(
            effect_id=self._effect_id(
                ctx.actor_id,
                f"{WEAPON_ATTACK_TARGET_THIS_TURN_CONDITION}_{target_id}",
            ),
            source_ref=ctx.action.source,
            source_action_id=ctx.action.id,
            target_id=ctx.actor_id,
            applied_by=ctx.actor_id,
            condition=WEAPON_ATTACK_TARGET_THIS_TURN_CONDITION,
            duration={"until": "start_of_next_turn"},
            tick_on="self_turn_start",
            stacking_policy="append",
            audit={"attacked_target_id": target_id},
        )
        getattr(actor, "status_effects").append(effect.to_dict())
        ctx.result.state_changes.append(
            {
                "type": "weapon_attack_target_this_turn",
                "target_id": target_id,
                "effect_id": effect.effect_id,
                "condition": effect.condition,
            }
        )

    def _has_attacked_target_this_turn(self, actor_id: str, target_id: str) -> bool:
        actor = self._entity(actor_id)
        return any(
            effect.get("condition") == WEAPON_ATTACK_TARGET_THIS_TURN_CONDITION
            and effect.get("audit", {}).get("attacked_target_id") == target_id
            for effect in self._status_effects_for(actor)
        )

    def _mark_thirsting_blade_pact_weapon_attack_this_turn(
        self,
        ctx: _Context,
        target_id: str,
    ) -> None:
        actor_owner = self._resource_owner(ctx.actor_id)
        if not isinstance(actor_owner, Character) or not has_warlock_thirsting_blade(actor_owner):
            return
        if self._active_pact_weapon_effect_for_action(ctx.actor_id, ctx.action.id) is None:
            return
        if self._has_thirsting_blade_pact_weapon_attack_this_turn(ctx.actor_id, ctx.action.id):
            return
        actor = self._entity(ctx.actor_id)
        effect = EffectInstance(
            effect_id=self._effect_id(
                ctx.actor_id,
                f"{THIRSTING_BLADE_PACT_WEAPON_ATTACK_CONDITION}_{ctx.action.id}",
            ),
            source_ref=ctx.action.source,
            source_action_id=ctx.action.id,
            target_id=ctx.actor_id,
            applied_by=ctx.actor_id,
            condition=THIRSTING_BLADE_PACT_WEAPON_ATTACK_CONDITION,
            duration={"until": "start_of_next_turn"},
            tick_on="self_turn_start",
            stacking_policy="append",
            audit={"pact_weapon_action_id": ctx.action.id, "attacked_target_id": target_id},
        )
        getattr(actor, "status_effects").append(effect.to_dict())
        ctx.result.state_changes.append(
            {
                "type": "thirsting_blade_pact_weapon_attack_this_turn",
                "pact_weapon_action_id": ctx.action.id,
                "target_id": target_id,
                "effect_id": effect.effect_id,
                "condition": effect.condition,
            }
        )

    def _mark_thirsting_blade_extra_attack_used(
        self,
        ctx: _Context,
        target_id: str,
    ) -> None:
        if not self._thirsting_blade_extra_attack_requested(ctx.params):
            return
        if self._has_thirsting_blade_extra_attack_used(ctx.actor_id):
            return
        actor = self._entity(ctx.actor_id)
        effect = EffectInstance(
            effect_id=self._effect_id(ctx.actor_id, THIRSTING_BLADE_EXTRA_ATTACK_USED_CONDITION),
            source_ref=ctx.action.source,
            source_action_id=THIRSTING_BLADE_ACTION_ID,
            target_id=ctx.actor_id,
            applied_by=ctx.actor_id,
            condition=THIRSTING_BLADE_EXTRA_ATTACK_USED_CONDITION,
            duration={"until": "start_of_next_turn"},
            tick_on="self_turn_start",
            stacking_policy="append",
            audit={"pact_weapon_action_id": ctx.action.id, "attacked_target_id": target_id},
        )
        getattr(actor, "status_effects").append(effect.to_dict())
        ctx.result.state_changes.append(
            {
                "type": "thirsting_blade_extra_attack_used",
                "pact_weapon_action_id": ctx.action.id,
                "target_id": target_id,
                "effect_id": effect.effect_id,
                "condition": effect.condition,
            }
        )

    def _has_thirsting_blade_pact_weapon_attack_this_turn(
        self,
        actor_id: str,
        action_id: str,
    ) -> bool:
        actor = self._entity(actor_id)
        return any(
            effect.get("condition") == THIRSTING_BLADE_PACT_WEAPON_ATTACK_CONDITION
            and effect.get("audit", {}).get("pact_weapon_action_id") == action_id
            for effect in self._status_effects_for(actor)
        )

    def _has_thirsting_blade_extra_attack_used(self, actor_id: str) -> bool:
        actor = self._entity(actor_id)
        return any(
            effect.get("condition") == THIRSTING_BLADE_EXTRA_ATTACK_USED_CONDITION
            and effect.get("source_action_id") == THIRSTING_BLADE_ACTION_ID
            for effect in self._status_effects_for(actor)
        )

    def _eldritch_smite_bonus(
        self,
        ctx: _Context,
        target_id: str,
        path: str,
    ) -> _ExtraDamageResult:
        if not self._eldritch_smite_requested(ctx.params):
            return _ExtraDamageResult()
        if self._eldritch_smite_target_id(ctx.original_targets, ctx.params) != target_id:
            return _ExtraDamageResult()
        if not ctx.attack_hits.get(target_id, False):
            return _ExtraDamageResult()
        owner = self._resource_owner(ctx.actor_id)
        if not isinstance(owner, Character) or not has_warlock_eldritch_smite(owner):
            return _ExtraDamageResult()
        if self._active_pact_weapon_effect_for_action(ctx.actor_id, ctx.action.id) is None:
            return _ExtraDamageResult()
        if self._has_eldritch_smite_used(ctx.actor_id):
            return _ExtraDamageResult()
        slot_level = self._pact_magic_slot_level(owner)
        if slot_level is None:
            return _ExtraDamageResult()
        self._spend_eldritch_smite_slot(ctx, owner, slot_level, path)
        dice = f"{1 + slot_level}d8"
        roll = self.roll_service.roll(dice)
        rolls = [roll]
        amount = roll.total
        if ctx.attack_critical.get(target_id, False):
            critical_roll = self.roll_service.roll(dice)
            rolls.append(critical_roll)
            amount += critical_roll.total
        self._mark_eldritch_smite_used(ctx, target_id, slot_level)
        ctx.eldritch_smite_targets.add(target_id)
        return _ExtraDamageResult(
            amount=amount,
            damage_type="force",
            rolls=rolls,
            sources=[
                {
                    "feature": "eldritch_smite",
                    "source_action_id": ELDRITCH_SMITE_ACTION_ID,
                    "pact_spell_slot_level": slot_level,
                    "dice": dice,
                    "damage_type": "force",
                }
            ],
        )

    def _radiant_strikes_bonus(
        self,
        ctx: _Context,
        target_id: str,
    ) -> _ExtraDamageResult:
        if target_id in ctx.radiant_strikes_targets:
            return _ExtraDamageResult()
        if not self._action_is_melee_weapon_or_unarmed(ctx.action):
            return _ExtraDamageResult()
        if not ctx.attack_hits.get(target_id, False):
            return _ExtraDamageResult()
        owner = self._resource_owner(ctx.actor_id)
        if not isinstance(owner, Character) or not has_paladin_feature(owner, level=11):
            return _ExtraDamageResult()
        dice = "1d8"
        roll = self.roll_service.roll(dice)
        rolls = [roll]
        amount = roll.total
        if ctx.attack_critical.get(target_id, False):
            critical_roll = self.roll_service.roll(dice)
            rolls.append(critical_roll)
            amount += critical_roll.total
        ctx.radiant_strikes_targets.add(target_id)
        return _ExtraDamageResult(
            amount=amount,
            damage_type="radiant",
            rolls=rolls,
            sources=[
                {
                    "feature": "radiant_strikes",
                    "source_action_id": RADIANT_STRIKES_ACTION_ID,
                    "dice": dice,
                    "damage_type": "radiant",
                }
            ],
        )

    def _blessed_strikes_divine_strike_bonus(
        self,
        ctx: _Context,
        target_id: str,
    ) -> _ExtraDamageResult:
        if not self._blessed_strikes_divine_strike_requested(ctx.params):
            return _ExtraDamageResult()
        selected_target_id = self._blessed_strikes_divine_strike_target_id(
            ctx.original_targets,
            ctx.params,
        )
        if selected_target_id != target_id:
            return _ExtraDamageResult()
        if ctx.action.action_type != "weapon_attack":
            return _ExtraDamageResult()
        if not ctx.attack_hits.get(target_id, False):
            return _ExtraDamageResult()
        owner = self._resource_owner(ctx.actor_id)
        if not isinstance(owner, Character) or not has_cleric_blessed_strikes_divine_strike(owner):
            return _ExtraDamageResult()
        if self._has_blessed_strikes_divine_strike_used(ctx.actor_id):
            return _ExtraDamageResult()
        damage_type = self._blessed_strikes_divine_strike_damage_type(ctx.params)
        dice = "2d8" if has_cleric_improved_blessed_strikes(owner) else "1d8"
        roll = self.roll_service.roll(dice)
        rolls = [roll]
        amount = roll.total
        if ctx.attack_critical.get(target_id, False):
            critical_roll = self.roll_service.roll(dice)
            rolls.append(critical_roll)
            amount += critical_roll.total
        source = {
            "feature": "blessed_strikes_divine_strike",
            "source_action_id": CLERIC_BLESSED_STRIKES_DIVINE_STRIKE_ACTION_ID,
            "dice": dice,
            "damage_type": damage_type,
        }
        if dice == "2d8":
            source["improved_source_action_id"] = CLERIC_IMPROVED_BLESSED_STRIKES_ACTION_ID
        self._mark_blessed_strikes_divine_strike_used(ctx, target_id, damage_type)
        return _ExtraDamageResult(
            amount=amount,
            damage_type=damage_type,
            rolls=rolls,
            sources=[source],
        )

    def _conjure_minor_elementals_bonus(
        self,
        ctx: _Context,
        target_id: str,
    ) -> _ExtraDamageResult:
        effect = self._active_conjure_minor_elementals_effect(ctx.actor_id)
        if effect is None:
            return _ExtraDamageResult()
        if not ctx.attack_hits.get(target_id, False):
            return _ExtraDamageResult()
        if not self._conjure_minor_elementals_target_in_emanation(ctx.actor_id, target_id, effect):
            return _ExtraDamageResult()
        damage_type = self._conjure_minor_elementals_damage_type(ctx.params, required=True)
        metadata = effect.get("metadata", {})
        dice_count = 2
        if isinstance(metadata, dict):
            dice_count = max(1, int(metadata.get("extra_damage_dice_count", dice_count)))
        dice = f"{dice_count}d8"
        roll = self.roll_service.roll(dice)
        rolls = [roll]
        amount = roll.total
        if ctx.attack_critical.get(target_id, False):
            critical_roll = self.roll_service.roll(dice)
            rolls.append(critical_roll)
            amount += critical_roll.total
        return _ExtraDamageResult(
            amount=amount,
            damage_type=damage_type or "untyped",
            rolls=rolls,
            sources=[
                {
                    "spell": "conjure_minor_elementals",
                    "source_action_id": CONJURE_MINOR_ELEMENTALS_ACTION_ID,
                    "effect_type": CONJURE_MINOR_ELEMENTALS_EFFECT_TYPE,
                    "dice": dice,
                    "damage_type": damage_type,
                    "target_within_emanation_ft": CONJURE_MINOR_ELEMENTALS_RADIUS_FT,
                }
            ],
        )

    def _apply_improved_blessed_strikes_potent_spellcasting_temp_hp(
        self,
        ctx: _Context,
        damage_target_id: str,
        damage_taken: int,
        path: str,
    ) -> None:
        if ctx.improved_blessed_strikes_potent_spellcasting_applied or damage_taken <= 0:
            return
        beneficiary_id = self._improved_blessed_strikes_temp_hp_target_id(ctx.params)
        if beneficiary_id is None:
            return
        owner = self._resource_owner(ctx.actor_id)
        if not isinstance(owner, Character):
            return
        amount = cleric_improved_blessed_strikes_temp_hp(owner)
        if amount <= 0 or not self._action_is_cleric_cantrip(ctx.action):
            return
        beneficiary = self._entity(beneficiary_id)
        before = int(getattr(beneficiary, "temp_hp", 0))
        after = max(before, amount)
        setattr(beneficiary, "temp_hp", after)
        if after > before:
            self._clear_temp_hp_source(beneficiary_id, beneficiary)
        self._sync_hp_state_for_target(beneficiary)
        ctx.improved_blessed_strikes_potent_spellcasting_applied = True
        ctx.result.state_changes.append(
            {
                "type": "temp_hp",
                "target_id": beneficiary_id,
                "before": before,
                "after": after,
                "amount": amount,
                "applied": after - before,
                "path": f"{path}.improved_blessed_strikes",
                "source_action_id": CLERIC_IMPROVED_BLESSED_STRIKES_ACTION_ID,
                "source_feature": "improved_blessed_strikes_potent_spellcasting",
                "damage_target_id": damage_target_id,
            }
        )

    def _has_blessed_strikes_divine_strike_used(self, actor_id: str) -> bool:
        actor = self._entity(actor_id)
        return any(
            effect.get("condition") == CLERIC_BLESSED_STRIKES_DIVINE_STRIKE_USED_CONDITION
            and effect.get("source_action_id") == CLERIC_BLESSED_STRIKES_DIVINE_STRIKE_ACTION_ID
            for effect in self._status_effects_for(actor)
        )

    def _mark_blessed_strikes_divine_strike_used(
        self,
        ctx: _Context,
        target_id: str,
        damage_type: str,
    ) -> None:
        actor = self._entity(ctx.actor_id)
        effect = EffectInstance(
            effect_id=self._effect_id(
                ctx.actor_id,
                CLERIC_BLESSED_STRIKES_DIVINE_STRIKE_USED_CONDITION,
            ),
            source_ref=(
                "SRD 5.2.1 Cleric Class Features: Level 7: Blessed Strikes, Divine Strike"
            ),
            source_action_id=CLERIC_BLESSED_STRIKES_DIVINE_STRIKE_ACTION_ID,
            target_id=ctx.actor_id,
            applied_by=ctx.actor_id,
            condition=CLERIC_BLESSED_STRIKES_DIVINE_STRIKE_USED_CONDITION,
            duration={"until": "start_of_next_turn"},
            tick_on="self_turn_start",
            stacking_policy="replace",
            audit={"target_id": target_id, "damage_type": damage_type},
        )
        getattr(actor, "status_effects").append(effect.to_dict())
        ctx.result.state_changes.append(
            {
                "type": "blessed_strikes_divine_strike_used",
                "actor_id": ctx.actor_id,
                "target_id": target_id,
                "damage_type": damage_type,
                "effect_id": effect.effect_id,
                "source_action_id": effect.source_action_id,
            }
        )

    @staticmethod
    def _action_is_melee_weapon_or_unarmed(action: ActionDefinition) -> bool:
        if action.action_type == "unarmed_attack":
            return True
        if action.action_type != "weapon_attack":
            return False
        weapon_category = str(action.properties.get("weapon_category", "")).lower()
        if weapon_category:
            return weapon_category == "melee"
        normal_range = int(action.range.get("normal_ft", 0))
        return normal_range <= 5

    def _spend_eldritch_smite_slot(
        self,
        ctx: _Context,
        owner: Character,
        slot_level: int,
        path: str,
    ) -> None:
        key = str(slot_level)
        before = int(owner.spell_slots.get(key, 0))
        if before <= 0:
            raise AutomationError("insufficient Pact Magic spell slot")
        owner.spell_slots[key] = before - 1
        ctx.result.state_changes.append(
            {
                "type": "cost",
                "actor_id": ctx.actor_id,
                "resource": f"spell_slot_{key}",
                "before": before,
                "after": owner.spell_slots[key],
                "source_action_id": ELDRITCH_SMITE_ACTION_ID,
                "path": f"{path}.eldritch_smite",
            }
        )

    def _mark_eldritch_smite_used(
        self,
        ctx: _Context,
        target_id: str,
        slot_level: int,
    ) -> None:
        actor = self._entity(ctx.actor_id)
        effect = EffectInstance(
            effect_id=self._effect_id(ctx.actor_id, ELDRITCH_SMITE_USED_CONDITION),
            source_ref="SRD 5.2.1 Warlock Eldritch Invocation Options: Eldritch Smite",
            source_action_id=ELDRITCH_SMITE_ACTION_ID,
            target_id=ctx.actor_id,
            applied_by=ctx.actor_id,
            condition=ELDRITCH_SMITE_USED_CONDITION,
            duration={"until": "start_of_next_turn"},
            tick_on="self_turn_start",
            stacking_policy="append",
            audit={
                "pact_weapon_action_id": ctx.action.id,
                "target_id": target_id,
                "pact_spell_slot_level": slot_level,
            },
        )
        getattr(actor, "status_effects").append(effect.to_dict())
        ctx.result.state_changes.append(
            {
                "type": "eldritch_smite_used",
                "pact_weapon_action_id": ctx.action.id,
                "target_id": target_id,
                "pact_spell_slot_level": slot_level,
                "effect_id": effect.effect_id,
                "condition": effect.condition,
                "source_action_id": ELDRITCH_SMITE_ACTION_ID,
            }
        )

    def _has_eldritch_smite_used(self, actor_id: str) -> bool:
        actor = self._entity(actor_id)
        return any(
            effect.get("condition") == ELDRITCH_SMITE_USED_CONDITION
            and effect.get("source_action_id") == ELDRITCH_SMITE_ACTION_ID
            for effect in self._status_effects_for(actor)
        )

    def _marked_target_attack_damage_bonuses(
        self,
        ctx: _Context,
        target_id: str,
    ) -> list[_ExtraDamageResult]:
        if not ctx.attack_hits.get(target_id, False):
            return []
        bonuses: list[_ExtraDamageResult] = []
        target = self._entity(target_id)
        for effect in self._status_effects_for(target):
            if effect.get("applied_by") != ctx.actor_id:
                continue
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict) or modifiers.get("hunters_mark") is not True:
                continue
            dice = modifiers.get("attacker_bonus_damage")
            if not isinstance(dice, str) or not dice:
                continue
            source: dict[str, Any] = {
                "feature": "hunters_mark",
                "source_action_id": effect.get("source_action_id"),
                "effect_id": effect.get("effect_id"),
                "dice": dice,
            }
            dice, dice_source = self._effective_hunters_mark_damage_dice(ctx.actor_id, dice)
            source.update(dice_source)
            source["dice"] = dice
            damage_type = str(modifiers.get("damage_type", "force"))
            source["damage_type"] = damage_type
            roll = self.roll_service.roll(dice)
            rolls = [roll]
            amount = roll.total
            if ctx.attack_critical.get(target_id, False):
                critical_roll = self.roll_service.roll(dice)
                rolls.append(critical_roll)
                amount += critical_roll.total
            bonuses.append(
                _ExtraDamageResult(
                    amount=amount,
                    damage_type=damage_type,
                    rolls=rolls,
                    sources=[source],
                )
            )
        return bonuses

    def _effective_hunters_mark_damage_dice(
        self,
        actor_id: str,
        dice: str,
    ) -> tuple[str, dict[str, Any]]:
        actor_owner = self._resource_owner(actor_id)
        if not isinstance(actor_owner, Character) or dice != "1d6":
            return dice, {}
        upgraded_dice = ranger_hunters_mark_damage_dice(actor_owner)
        if upgraded_dice == dice:
            return dice, {}
        return upgraded_dice, {
            "base_dice": dice,
            "foe_slayer_source_action_id": FOE_SLAYER_ACTION_ID,
        }

    def _sneak_attack_bonus(
        self,
        ctx: _Context,
        node: dict[str, Any],
        target_id: str,
        damage_type: str,
    ) -> _SneakAttackResult:
        if ctx.params.get("use_sneak_attack") is not True:
            return _SneakAttackResult()
        if ctx.action.action_type != "weapon_attack":
            return _SneakAttackResult()
        if not self._action_qualifies_for_sneak_attack(ctx.action):
            return _SneakAttackResult()
        actor_owner = self._resource_owner(ctx.actor_id)
        if not isinstance(actor_owner, Character):
            return _SneakAttackResult()
        rogue_level = int(actor_owner.class_levels.get("rogue", 0))
        if rogue_level <= 0 or self._has_sneak_attack_used(ctx.actor_id):
            return _SneakAttackResult()
        advantage = ctx.attack_advantage.get(target_id)
        qualifies_by_advantage = advantage == "advantage"
        qualifies_by_ally = advantage != "disadvantage" and self._has_ally_within_5ft_of_target(
            ctx.actor_id,
            target_id,
        )
        if not (qualifies_by_advantage or qualifies_by_ally):
            return _SneakAttackResult()
        base_dice_count = (rogue_level + 1) // 2
        cunning_strike = self._cunning_strike_for_sneak_attack(
            ctx,
            target_id,
            rogue_level,
            base_dice_count,
        )
        dice_count = base_dice_count - (int(cunning_strike["die_cost"]) if cunning_strike else 0)
        dice = f"{dice_count}d6"
        roll = self.roll_service.roll(dice)
        rolls = [roll]
        amount = roll.total
        if ctx.attack_critical.get(target_id, False):
            critical_roll = self.roll_service.roll(dice)
            rolls.append(critical_roll)
            amount += critical_roll.total
        self._mark_sneak_attack_used(ctx, target_id)
        sources = [
            {
                "feature": "sneak_attack",
                "rogue_level": rogue_level,
                "dice": dice,
                "base_dice": f"{base_dice_count}d6",
                "damage_type": damage_type,
                "qualifies_by": "advantage" if qualifies_by_advantage else "ally_within_5ft",
            }
        ]
        if cunning_strike is not None:
            sources[0]["cunning_strike"] = self._cunning_strike_source(cunning_strike)
        return _SneakAttackResult(
            amount=amount,
            rolls=rolls,
            sources=sources,
            cunning_strike=cunning_strike,
        )

    def _cunning_strike_for_sneak_attack(
        self,
        ctx: _Context,
        target_id: str,
        rogue_level: int,
        base_dice_count: int,
    ) -> dict[str, Any] | None:
        effects = self._cunning_strike_choices(ctx.params)
        if not effects:
            return None
        die_cost = len(effects)
        if rogue_level < 5:
            raise AutomationError("Cunning Strike requires Rogue level 5")
        if len(effects) > 1 and rogue_level < 11:
            raise AutomationError("Improved Cunning Strike requires Rogue level 11")
        if base_dice_count <= die_cost:
            raise AutomationError("Cunning Strike requires enough Sneak Attack dice")
        dc = self._cunning_strike_dc(ctx.actor_id)
        dc_source = "cunning_strike:dex+proficiency"
        strikes: list[dict[str, Any]] = []
        for effect in effects:
            strike: dict[str, Any] = {
                "feature": "cunning_strike",
                "effect": effect,
                "die_cost": 1,
                "target_id": target_id,
                "dc": dc,
                "dc_source": dc_source,
            }
            destination = self._cunning_strike_withdraw_destination(ctx.params)
            if effect == "withdraw" and destination is not None:
                strike["to_position_node_id"] = destination
            strikes.append(strike)
        if len(strikes) == 1:
            return strikes[0]
        return {
            "feature": "improved_cunning_strike",
            "effects": strikes,
            "die_cost": die_cost,
            "target_id": target_id,
            "source_action_id": IMPROVED_CUNNING_STRIKE_ACTION_ID,
        }

    @staticmethod
    def _cunning_strike_effects(
        cunning_strike: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        if cunning_strike is None:
            return []
        effects = cunning_strike.get("effects")
        if isinstance(effects, list):
            return [effect for effect in effects if isinstance(effect, dict)]
        return [cunning_strike]

    @staticmethod
    def _cunning_strike_source(cunning_strike: dict[str, Any]) -> dict[str, Any]:
        effects = AutomationExecutor._cunning_strike_effects(cunning_strike)
        if len(effects) == 1:
            effect = effects[0]
            return {
                "effect": effect["effect"],
                "die_cost": effect["die_cost"],
                "forgone_dice": "1d6",
            }
        return {
            "source_action_id": IMPROVED_CUNNING_STRIKE_ACTION_ID,
            "effects": [
                {
                    "effect": effect["effect"],
                    "die_cost": effect["die_cost"],
                    "forgone_dice": "1d6",
                }
                for effect in effects
            ],
            "die_cost": int(cunning_strike["die_cost"]),
            "forgone_dice": f"{int(cunning_strike['die_cost'])}d6",
        }

    def _apply_cunning_strike_effect(
        self,
        ctx: _Context,
        target_id: str,
        cunning_strike: dict[str, Any],
        path: str,
    ) -> None:
        effect = str(cunning_strike["effect"])
        base_change = {
            "type": "cunning_strike",
            "actor_id": ctx.actor_id,
            "target_id": target_id,
            "effect": effect,
            "die_cost": int(cunning_strike["die_cost"]),
            "path": path,
        }
        if effect == "poison":
            success = self._roll_cunning_strike_save(
                ctx,
                target_id,
                "con",
                int(cunning_strike["dc"]),
                str(cunning_strike["dc_source"]),
                path,
                effect,
            )
            base_change["saving_throw_success"] = success
            ctx.result.state_changes.append(base_change)
            if not success:
                self._apply_cunning_strike_condition(
                    ctx,
                    target_id,
                    "poisoned",
                    path,
                    duration={
                        "until": "duration_1_minute",
                        "repeat_save": {
                            "ability": "con",
                            "dc": int(cunning_strike["dc"]),
                            "dc_source": str(cunning_strike["dc_source"]),
                            "end_on_success": True,
                        },
                    },
                    tick_on="target_turn_end",
                )
            return
        if effect == "trip":
            success = self._roll_cunning_strike_save(
                ctx,
                target_id,
                "dex",
                int(cunning_strike["dc"]),
                str(cunning_strike["dc_source"]),
                path,
                effect,
            )
            base_change["saving_throw_success"] = success
            ctx.result.state_changes.append(base_change)
            if not success:
                self._apply_cunning_strike_condition(
                    ctx,
                    target_id,
                    "prone",
                    path,
                    duration={"until": "stands_up"},
                    tick_on=None,
                )
            return
        if effect == "withdraw":
            move_change = self._apply_cunning_strike_withdraw(
                ctx,
                str(cunning_strike["to_position_node_id"]),
                path,
            )
            base_change.update(move_change)
            ctx.result.state_changes.append(base_change)
            return
        if effect == "stealth_attack":
            cover = self._cunning_strike_stealth_attack_cover(ctx.params)
            if cover is None:
                raise AutomationError(
                    "Supreme Sneak Stealth Attack requires end-turn cover of "
                    "Three-Quarters Cover or Total Cover"
                )
            base_change.update(
                {
                    "source_action_id": SUPREME_SNEAK_ACTION_ID,
                    "end_turn_cover": cover,
                    "preserved_condition_effects": self._hide_invisible_effect_entries(
                        ctx.actor_id
                    ),
                }
            )
            ctx.result.state_changes.append(base_change)
            return
        raise AutomationError(f"unsupported Cunning Strike effect: {effect}")

    def _roll_cunning_strike_save(
        self,
        ctx: _Context,
        target_id: str,
        ability: str,
        dc: int,
        dc_source: str,
        path: str,
        effect: str,
    ) -> bool:
        target = self._entity(target_id)
        base_bonus, proficient, _ = self._saving_throw_bonus(target, ability)
        target_exhaustion_level, exhaustion_penalty = self._exhaustion_details(target)
        bonus = base_bonus - exhaustion_penalty
        status_advantage, status_sources = self._saving_throw_status_advantage(target, ability)
        roll = self.roll_service.roll(d20_expression(bonus), advantage=status_advantage)
        adjustment, adjustment_rolls, adjustment_sources = self._passive_roll_adjustment(
            target,
            bonus_key="saving_throw_bonus_dice",
            penalty_key="saving_throw_penalty_dice",
        )
        ctx.result.dice_rolls.append(roll.to_dict())
        ctx.result.dice_rolls.extend(extra.to_dict() for extra in adjustment_rolls)
        total = roll.total + adjustment
        success = total >= dc
        result_path = f"{path}.cunning_strike.{effect}"
        ctx.result.node_results[result_path] = {
            "target_id": target_id,
            "effect": effect,
            "ability": ability,
            "dc": dc,
            "dc_source": dc_source,
            "bonus": bonus,
            "base_bonus": base_bonus,
            "proficient": proficient,
            "exhaustion_level": target_exhaustion_level,
            "d20_penalty": exhaustion_penalty,
            "base_total": roll.total,
            "passive_adjustment": adjustment,
            "passive_sources": adjustment_sources,
            "status_advantage": status_advantage,
            "status_sources": status_sources,
            "total": total,
            "success": success,
        }
        return success

    def _apply_cunning_strike_condition(
        self,
        ctx: _Context,
        target_id: str,
        condition: str,
        path: str,
        *,
        duration: dict[str, Any],
        tick_on: str | None,
    ) -> None:
        target = self._entity(target_id)
        immunity_sources = self._condition_immunity_sources(target, condition)
        if immunity_sources:
            ctx.result.state_changes.append(
                {
                    "type": "condition_immune",
                    "target_id": target_id,
                    "condition": condition,
                    "immunity_sources": immunity_sources,
                    "path": f"{path}.cunning_strike",
                }
            )
            return
        effect = EffectInstance(
            effect_id=self._effect_id(target_id, f"{path}-cunning-strike-{condition}"),
            source_ref="SRD 5.2.1 Rogue Class Features: Level 5: Cunning Strike",
            source_action_id="srd.cunning_strike",
            target_id=target_id,
            applied_by=ctx.actor_id,
            condition=condition,
            duration=duration,
            tick_on=tick_on,
            stacking_policy="replace",
            audit={"node_path": path, "feature": "cunning_strike"},
        )
        effects = getattr(target, "status_effects")
        effects[:] = [
            existing
            for existing in effects
            if existing.get("condition") != effect.condition
            or existing.get("source_action_id") != effect.source_action_id
        ]
        effects.append(effect.to_dict())
        ctx.result.state_changes.append(
            {
                "type": "condition",
                "target_id": target_id,
                "condition": condition,
                "effect_id": effect.effect_id,
                "source_action_id": effect.source_action_id,
                "path": f"{path}.cunning_strike",
            }
        )

    def _apply_cunning_strike_withdraw(
        self,
        ctx: _Context,
        destination: str,
        path: str,
    ) -> dict[str, Any]:
        plan = self._cunning_strike_withdraw_plan(ctx.actor_id, destination)
        actor = plan["actor"]
        assert isinstance(actor, Combatant)
        before_position = actor.position_node_id
        actor.position_node_id = destination
        before_used, after_used = self.economy.add(
            ctx.actor_id,
            "movement_used",
            int(plan["movement_cost"]),
        )
        return {
            "from": before_position,
            "to": actor.position_node_id,
            "movement_cost": int(plan["movement_cost"]),
            "movement_limit": int(plan["movement_limit"]),
            "movement_used_before": before_used,
            "movement_used_after": after_used,
            "opportunity_attack_triggers": [],
            "path": f"{path}.cunning_strike",
        }

    def _open_hand_damage_strike_index(
        self,
        ctx: _Context,
        node: dict[str, Any],
    ) -> int | None:
        if ctx.action.id != FLURRY_OF_BLOWS_ACTION_ID:
            return None
        if node.get("requires_hit") is not True:
            return None
        ctx.open_hand_strike_index += 1
        return ctx.open_hand_strike_index

    def _apply_open_hand_technique_if_requested(
        self,
        ctx: _Context,
        target_id: str,
        path: str,
        *,
        strike_index: int | None,
    ) -> None:
        if strike_index is None:
            return
        effect = self._open_hand_technique_choice(
            ctx.params,
            target_id=target_id,
            strike_index=strike_index,
        )
        if effect is None:
            return
        actor = self._resource_owner(ctx.actor_id)
        if not isinstance(actor, Character) or not has_monk_open_hand_feature(actor, level=3):
            raise AutomationError("Open Hand Technique requires Monk Open Hand level 3")
        base_change: dict[str, Any] = {
            "type": "open_hand_technique",
            "actor_id": ctx.actor_id,
            "target_id": target_id,
            "effect": effect,
            "strike_index": strike_index,
            "source_action_id": OPEN_HAND_TECHNIQUE_ACTION_ID,
            "path": path,
        }
        if effect == "addle":
            ctx.result.state_changes.append(base_change)
            self._apply_open_hand_condition(
                ctx,
                target_id,
                "open_hand_addled",
                path,
                duration={"until": "start_of_next_turn"},
                tick_on="target_turn_start",
                passive_modifiers={"cannot_make_opportunity_attacks": True},
            )
            return
        dc = self._monk_focus_save_dc(ctx.actor_id)
        dc_source = "monk_focus:wis+proficiency"
        if effect == "push":
            success = self._roll_open_hand_save(
                ctx,
                target_id,
                "str",
                dc,
                dc_source,
                path,
                effect,
            )
            base_change["saving_throw_success"] = success
            if not success:
                destination = self._open_hand_push_destination(
                    ctx.params,
                    target_id=target_id,
                    strike_index=strike_index,
                )
                if destination is None:
                    raise AutomationError(
                        "Open Hand Technique Push requires a destination position"
                    )
                base_change.update(self._apply_open_hand_push(ctx, target_id, destination, path))
            ctx.result.state_changes.append(base_change)
            return
        if effect == "topple":
            success = self._roll_open_hand_save(
                ctx,
                target_id,
                "dex",
                dc,
                dc_source,
                path,
                effect,
            )
            base_change["saving_throw_success"] = success
            ctx.result.state_changes.append(base_change)
            if not success:
                self._apply_open_hand_condition(
                    ctx,
                    target_id,
                    "prone",
                    path,
                    duration={"until": "stands_up"},
                    tick_on=None,
                )
            return
        raise AutomationError(f"unsupported Open Hand Technique effect: {effect}")

    def _roll_open_hand_save(
        self,
        ctx: _Context,
        target_id: str,
        ability: str,
        dc: int,
        dc_source: str,
        path: str,
        effect: str,
    ) -> bool:
        target = self._entity(target_id)
        base_bonus, proficient, _ = self._saving_throw_bonus(target, ability)
        target_exhaustion_level, exhaustion_penalty = self._exhaustion_details(target)
        bonus = base_bonus - exhaustion_penalty
        status_advantage, status_sources = self._saving_throw_status_advantage(target, ability)
        roll = self.roll_service.roll(d20_expression(bonus), advantage=status_advantage)
        adjustment, adjustment_rolls, adjustment_sources = self._passive_roll_adjustment(
            target,
            bonus_key="saving_throw_bonus_dice",
            penalty_key="saving_throw_penalty_dice",
        )
        ctx.result.dice_rolls.append(roll.to_dict())
        ctx.result.dice_rolls.extend(extra.to_dict() for extra in adjustment_rolls)
        total = roll.total + adjustment
        success = total >= dc
        ctx.result.node_results[f"{path}.open_hand_technique.{effect}"] = {
            "target_id": target_id,
            "effect": effect,
            "ability": ability,
            "dc": dc,
            "dc_source": dc_source,
            "bonus": bonus,
            "base_bonus": base_bonus,
            "proficient": proficient,
            "exhaustion_level": target_exhaustion_level,
            "d20_penalty": exhaustion_penalty,
            "base_total": roll.total,
            "passive_adjustment": adjustment,
            "passive_sources": adjustment_sources,
            "status_advantage": status_advantage,
            "status_sources": status_sources,
            "total": total,
            "success": success,
        }
        return success

    def _apply_open_hand_condition(
        self,
        ctx: _Context,
        target_id: str,
        condition: str,
        path: str,
        *,
        duration: dict[str, Any],
        tick_on: str | None,
        passive_modifiers: dict[str, Any] | None = None,
    ) -> None:
        target = self._entity(target_id)
        if condition != "open_hand_addled":
            immunity_sources = self._condition_immunity_sources(target, condition)
            if immunity_sources:
                ctx.result.state_changes.append(
                    {
                        "type": "condition_immune",
                        "target_id": target_id,
                        "condition": condition,
                        "immunity_sources": immunity_sources,
                        "path": f"{path}.open_hand_technique",
                    }
                )
                return
        effect = EffectInstance(
            effect_id=self._effect_id(target_id, f"{path}-open-hand-{condition}"),
            source_ref=(
                "SRD 5.2.1 Monk Subclass: Warrior of the Open Hand, Level 3: Open Hand Technique"
            ),
            source_action_id=OPEN_HAND_TECHNIQUE_ACTION_ID,
            target_id=target_id,
            applied_by=ctx.actor_id,
            condition=condition,
            passive_modifiers=passive_modifiers or {},
            duration=duration,
            tick_on=tick_on,
            stacking_policy="replace",
            audit={"node_path": path, "feature": "open_hand_technique"},
        )
        effects = getattr(target, "status_effects")
        effects[:] = [
            existing
            for existing in effects
            if existing.get("condition") != effect.condition
            or existing.get("source_action_id") != effect.source_action_id
        ]
        effects.append(effect.to_dict())
        change: dict[str, Any] = {
            "type": "condition",
            "target_id": target_id,
            "condition": condition,
            "effect_id": effect.effect_id,
            "source_action_id": effect.source_action_id,
            "path": f"{path}.open_hand_technique",
        }
        if passive_modifiers:
            change["passive_modifiers"] = passive_modifiers
        ctx.result.state_changes.append(change)

    def _apply_open_hand_push(
        self,
        ctx: _Context,
        target_id: str,
        destination: str,
        path: str,
    ) -> dict[str, Any]:
        plan = self._open_hand_push_plan(ctx.actor_id, target_id, destination)
        target = plan["target"]
        assert isinstance(target, Combatant)
        before_position = target.position_node_id
        target.position_node_id = destination
        return {
            "from": before_position,
            "to": target.position_node_id,
            "forced_movement_distance": int(plan["movement_distance"]),
            "distance_from_actor_before": plan["distance_from_actor_before"],
            "distance_from_actor_after": plan["distance_from_actor_after"],
            "path": f"{path}.open_hand_technique",
        }

    def _monk_focus_save_dc(self, actor_id: str) -> int:
        actor = self._resource_owner(actor_id)
        if not isinstance(actor, Character):
            raise AutomationError("Monk Focus save DC requires a character")
        return (
            8 + int(getattr(actor, "proficiency_bonus", 2)) + self._ability_modifier(actor, "wis")
        )

    def _validate_stunning_strike_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        targets: list[str],
        params: dict[str, Any],
    ) -> None:
        if not self._stunning_strike_requested(params):
            return
        actor_owner = self._resource_owner(actor_id)
        if not isinstance(actor_owner, Character) or not has_monk_feature(actor_owner, level=5):
            raise AutomationError("Stunning Strike requires Monk level 5")
        if not self._action_qualifies_for_stunning_strike(action):
            raise AutomationError("Stunning Strike requires a Monk weapon or Unarmed Strike")
        if self._has_stunning_strike_used(actor_id):
            raise AutomationError("Stunning Strike can be used only once per turn")
        declared_targets = self._declared_stunning_strike_targets(targets, params)
        target_id = self._stunning_strike_target_id(params, declared_targets)
        if target_id is None:
            raise AutomationError("Stunning Strike requires a single target")
        if target_id not in declared_targets:
            raise AutomationError("Stunning Strike target must be one of the attack targets")
        try:
            self._entity(target_id)
        except KeyError as exc:
            raise AutomationError(f"unknown target {target_id}") from exc
        action_focus_cost = int(action.cost.resources.get(FOCUS_RESOURCE_ID, 0))
        available = self._get_resource(actor_owner, FOCUS_RESOURCE_ID)
        if available < action_focus_cost + 1:
            raise AutomationError(f"resource {FOCUS_RESOURCE_ID} is insufficient")

    @staticmethod
    def _stunning_strike_requested(params: dict[str, Any]) -> bool:
        return params.get("use_stunning_strike") is True

    def _validate_empowered_strikes_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        params: dict[str, Any],
    ) -> None:
        raw = params.get(
            "empowered_strikes_damage_type",
            params.get("unarmed_strike_damage_type"),
        )
        if raw is None or raw == "":
            return
        if isinstance(raw, (dict, list)):
            raise AutomationError("empowered_strikes_damage_type must be a scalar")
        choice = str(raw).casefold().strip()
        if choice not in {"normal", "bludgeoning", "force"}:
            raise AutomationError("empowered_strikes_damage_type must be normal or force")
        if action.action_type != "unarmed_attack":
            raise AutomationError("Empowered Strikes requires an Unarmed Strike")
        actor_owner = self._resource_owner(actor_id)
        if not isinstance(actor_owner, Character) or not has_monk_feature(actor_owner, level=6):
            raise AutomationError("Empowered Strikes requires Monk level 6")
        params["empowered_strikes_damage_type"] = choice

    @classmethod
    def _stunning_strike_target_id(
        cls,
        params: dict[str, Any],
        declared_targets: set[str],
    ) -> str | None:
        selected = params.get("stunning_strike_target_id")
        if selected not in (None, "", False):
            if isinstance(selected, (dict, list)):
                raise AutomationError("parameter stunning_strike_target_id must be a scalar")
            return str(selected)
        if len(declared_targets) == 1:
            return next(iter(declared_targets))
        return None

    @staticmethod
    def _declared_stunning_strike_targets(
        targets: list[str],
        params: dict[str, Any],
    ) -> set[str]:
        declared = {str(target_id) for target_id in targets}
        for param_name in ("strike_1_target", "strike_2_target"):
            selected = params.get(param_name)
            if selected in (None, "", False):
                continue
            if isinstance(selected, list):
                declared.update(str(target_id) for target_id in selected)
            else:
                declared.add(str(selected))
        return declared

    @staticmethod
    def _action_qualifies_for_stunning_strike(action: ActionDefinition) -> bool:
        if action.action_type == "unarmed_attack":
            return True
        if action.action_type != "weapon_attack":
            return False
        properties = action.properties.get("weapon_properties", [])
        if isinstance(properties, str):
            properties = [properties]
        weapon_properties = {str(item).lower() for item in properties if isinstance(item, str)}
        normal_range = int(action.range.get("normal_ft", 0))
        return normal_range <= 5 and "light" in weapon_properties

    def _apply_stunning_strike_if_requested(
        self,
        ctx: _Context,
        target_id: str,
        path: str,
    ) -> None:
        if not self._stunning_strike_requested(ctx.params):
            return
        declared_targets = self._declared_stunning_strike_targets(
            ctx.original_targets,
            ctx.params,
        )
        selected_target_id = self._stunning_strike_target_id(ctx.params, declared_targets)
        if selected_target_id != target_id:
            return
        if not ctx.attack_hits.get(target_id, False):
            return
        if self._has_stunning_strike_used(ctx.actor_id):
            return
        actor_owner = self._resource_owner(ctx.actor_id)
        if not isinstance(actor_owner, Character) or not has_monk_feature(actor_owner, level=5):
            raise AutomationError("Stunning Strike requires Monk level 5")
        if not self._action_qualifies_for_stunning_strike(ctx.action):
            raise AutomationError("Stunning Strike requires a Monk weapon or Unarmed Strike")
        self._spend_stunning_strike_focus(ctx, path)
        self._mark_stunning_strike_used(ctx, target_id)
        dc = self._monk_focus_save_dc(ctx.actor_id)
        dc_source = "monk_focus:wis+proficiency"
        success = self._roll_stunning_strike_save(
            ctx,
            target_id,
            dc,
            dc_source,
            path,
        )
        ctx.result.state_changes.append(
            {
                "type": "stunning_strike",
                "actor_id": ctx.actor_id,
                "target_id": target_id,
                "source_action_id": STUNNING_STRIKE_ACTION_ID,
                "dc": dc,
                "dc_source": dc_source,
                "saving_throw_success": success,
                "path": f"{path}.stunning_strike",
            }
        )
        if success:
            self._apply_stunning_strike_condition(
                ctx,
                target_id,
                STUNNING_STRIKE_SLOWED_CONDITION,
                path,
                passive_modifiers={
                    "speed_multiplier": 0.5,
                    "incoming_attack_advantage": True,
                    "consume_on_incoming_attack": True,
                },
            )
            return
        self._apply_stunning_strike_condition(
            ctx,
            target_id,
            "stunned",
            path,
            passive_modifiers=None,
        )

    def _spend_stunning_strike_focus(self, ctx: _Context, path: str) -> None:
        actor = self._resource_owner(ctx.actor_id)
        before = self._get_resource(actor, FOCUS_RESOURCE_ID)
        if before <= 0:
            raise AutomationError(f"resource {FOCUS_RESOURCE_ID} is insufficient")
        self._set_resource(actor, FOCUS_RESOURCE_ID, before - 1)
        ctx.result.state_changes.append(
            {
                "type": "cost",
                "actor_id": ctx.actor_id,
                "resource": FOCUS_RESOURCE_ID,
                "before": before,
                "after": before - 1,
                "source_action_id": STUNNING_STRIKE_ACTION_ID,
                "path": f"{path}.stunning_strike",
            }
        )

    def _roll_stunning_strike_save(
        self,
        ctx: _Context,
        target_id: str,
        dc: int,
        dc_source: str,
        path: str,
    ) -> bool:
        target = self._entity(target_id)
        base_bonus, proficient, _ = self._saving_throw_bonus(target, "con")
        target_exhaustion_level, exhaustion_penalty = self._exhaustion_details(target)
        bonus = base_bonus - exhaustion_penalty
        status_advantage, status_sources = self._saving_throw_status_advantage(target, "con")
        roll = self.roll_service.roll(d20_expression(bonus), advantage=status_advantage)
        adjustment, adjustment_rolls, adjustment_sources = self._passive_roll_adjustment(
            target,
            bonus_key="saving_throw_bonus_dice",
            penalty_key="saving_throw_penalty_dice",
        )
        ctx.result.dice_rolls.append(roll.to_dict())
        ctx.result.dice_rolls.extend(extra.to_dict() for extra in adjustment_rolls)
        total = roll.total + adjustment
        success = total >= dc
        ctx.result.node_results[f"{path}.stunning_strike"] = {
            "target_id": target_id,
            "ability": "con",
            "dc": dc,
            "dc_source": dc_source,
            "bonus": bonus,
            "base_bonus": base_bonus,
            "proficient": proficient,
            "exhaustion_level": target_exhaustion_level,
            "d20_penalty": exhaustion_penalty,
            "base_total": roll.total,
            "passive_adjustment": adjustment,
            "passive_sources": adjustment_sources,
            "status_advantage": status_advantage,
            "status_sources": status_sources,
            "total": total,
            "success": success,
        }
        return success

    def _apply_stunning_strike_condition(
        self,
        ctx: _Context,
        target_id: str,
        condition: str,
        path: str,
        *,
        passive_modifiers: dict[str, Any] | None,
    ) -> None:
        target = self._entity(target_id)
        if condition != STUNNING_STRIKE_SLOWED_CONDITION:
            immunity_sources = self._condition_immunity_sources(target, condition)
            if immunity_sources:
                ctx.result.state_changes.append(
                    {
                        "type": "condition_immune",
                        "target_id": target_id,
                        "condition": condition,
                        "immunity_sources": immunity_sources,
                        "path": f"{path}.stunning_strike",
                    }
                )
                return
        effect = EffectInstance(
            effect_id=self._effect_id(target_id, f"{path}-stunning-strike-{condition}"),
            source_ref="SRD 5.2.1 Monk Class Features: Level 5: Stunning Strike",
            source_action_id=STUNNING_STRIKE_ACTION_ID,
            target_id=target_id,
            applied_by=ctx.actor_id,
            condition=condition,
            passive_modifiers=passive_modifiers or {},
            duration={"until": "start_of_next_turn"},
            tick_on="self_turn_start",
            stacking_policy="replace",
            audit={"node_path": path, "feature": "stunning_strike"},
        )
        effects = getattr(target, "status_effects")
        effects[:] = [
            existing
            for existing in effects
            if existing.get("condition") != effect.condition
            or existing.get("source_action_id") != effect.source_action_id
        ]
        effects.append(effect.to_dict())
        change: dict[str, Any] = {
            "type": "condition",
            "target_id": target_id,
            "condition": condition,
            "effect_id": effect.effect_id,
            "source_action_id": effect.source_action_id,
            "duration": effect.duration,
            "tick_on": effect.tick_on,
            "path": f"{path}.stunning_strike",
        }
        if passive_modifiers:
            change["passive_modifiers"] = passive_modifiers
        ctx.result.state_changes.append(change)

    @staticmethod
    def _quivering_palm_requested(params: dict[str, Any]) -> bool:
        return params.get("use_quivering_palm") is True

    @staticmethod
    def _quivering_palm_harmless_requested(params: dict[str, Any]) -> bool:
        return params.get("harmless") is True or params.get("end_harmlessly") is True

    def _quivering_palm_harmless_release_waives_action(
        self,
        action: ActionDefinition,
        params: dict[str, Any],
    ) -> bool:
        return (
            action.id == QUIVERING_PALM_RELEASE_ACTION_ID
            and self._quivering_palm_harmless_requested(params)
        )

    @staticmethod
    def _quivering_palm_same_plane(params: dict[str, Any]) -> bool:
        return params.get("same_plane") is True or params.get("target_same_plane") is True

    def _validate_quivering_palm_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        targets: list[str],
        params: dict[str, Any],
    ) -> None:
        if action.id == QUIVERING_PALM_RELEASE_ACTION_ID:
            actor_owner = self._resource_owner(actor_id)
            if not isinstance(actor_owner, Character) or not has_monk_open_hand_feature(
                actor_owner, level=17
            ):
                raise AutomationError("Quivering Palm requires Open Hand Monk level 17")
            if len(targets) != 1:
                raise AutomationError("Quivering Palm release requires a single target")
            release_target_id = str(targets[0])
            try:
                self._entity(release_target_id)
            except KeyError as exc:
                raise AutomationError(f"unknown target {release_target_id}") from exc
            if self._quivering_palm_effect(actor_id, release_target_id) is None:
                raise AutomationError("Quivering Palm release requires that target to be vibrating")
            if not self._quivering_palm_harmless_requested(
                params
            ) and not self._quivering_palm_same_plane(params):
                raise AutomationError("Quivering Palm release requires the target on same plane")
            return

        if not self._quivering_palm_requested(params):
            return
        actor_owner = self._resource_owner(actor_id)
        if not isinstance(actor_owner, Character) or not has_monk_open_hand_feature(
            actor_owner, level=17
        ):
            raise AutomationError("Quivering Palm requires Open Hand Monk level 17")
        if action.action_type != "unarmed_attack":
            raise AutomationError("Quivering Palm requires an Unarmed Strike")
        declared_targets = self._declared_quivering_palm_targets(targets, params)
        target_id = self._quivering_palm_target_id(params, declared_targets)
        if target_id is None:
            raise AutomationError("Quivering Palm requires a single target")
        if target_id not in declared_targets:
            raise AutomationError("Quivering Palm target must be one of the attack targets")
        try:
            self._entity(target_id)
        except KeyError as exc:
            raise AutomationError(f"unknown target {target_id}") from exc
        action_focus_cost = int(action.cost.resources.get(FOCUS_RESOURCE_ID, 0))
        available = self._get_resource(actor_owner, FOCUS_RESOURCE_ID)
        if available < action_focus_cost + 4:
            raise AutomationError(f"resource {FOCUS_RESOURCE_ID} is insufficient")

    @classmethod
    def _quivering_palm_target_id(
        cls,
        params: dict[str, Any],
        declared_targets: set[str],
    ) -> str | None:
        selected = params.get("quivering_palm_target_id")
        if selected not in (None, "", False):
            if isinstance(selected, (dict, list)):
                raise AutomationError("parameter quivering_palm_target_id must be a scalar")
            return str(selected)
        if len(declared_targets) == 1:
            return next(iter(declared_targets))
        return None

    @staticmethod
    def _declared_quivering_palm_targets(
        targets: list[str],
        params: dict[str, Any],
    ) -> set[str]:
        declared = {str(target_id) for target_id in targets}
        for param_name in ("strike_1_target", "strike_2_target", "strike_3_target"):
            selected = params.get(param_name)
            if selected in (None, "", False):
                continue
            if isinstance(selected, list):
                declared.update(str(target_id) for target_id in selected)
            else:
                declared.add(str(selected))
        return declared

    def _apply_quivering_palm_if_requested(
        self,
        ctx: _Context,
        target_id: str,
        path: str,
    ) -> None:
        if not self._quivering_palm_requested(ctx.params):
            return
        if ctx.quivering_palm_applied:
            return
        declared_targets = self._declared_quivering_palm_targets(ctx.original_targets, ctx.params)
        selected_target_id = self._quivering_palm_target_id(ctx.params, declared_targets)
        if selected_target_id != target_id:
            return
        if not ctx.attack_hits.get(target_id, False):
            return
        actor_owner = self._resource_owner(ctx.actor_id)
        if not isinstance(actor_owner, Character) or not has_monk_open_hand_feature(
            actor_owner, level=17
        ):
            raise AutomationError("Quivering Palm requires Open Hand Monk level 17")
        if ctx.action.action_type != "unarmed_attack":
            raise AutomationError("Quivering Palm requires an Unarmed Strike")
        before = self._get_resource(actor_owner, FOCUS_RESOURCE_ID)
        if before < 4:
            raise AutomationError(f"resource {FOCUS_RESOURCE_ID} is insufficient")
        self._set_resource(actor_owner, FOCUS_RESOURCE_ID, before - 4)
        replaced = self._clear_quivering_palm_effects_for_actor(ctx.actor_id)
        monk_level = int(actor_owner.class_levels.get("monk", 0))
        target = self._entity(target_id)
        effect = EffectInstance(
            effect_id=self._effect_id(target_id, f"{path}-quivering-palm"),
            source_ref="SRD 5.2.1 Monk Subclass: Warrior of the Open Hand, Level 17: Quivering Palm",
            source_action_id=QUIVERING_PALM_ACTION_ID,
            target_id=target_id,
            applied_by=ctx.actor_id,
            condition=QUIVERING_PALM_CONDITION,
            duration={"until": "duration_monk_level_days", "days": monk_level},
            tick_on=None,
            stacking_policy="replace",
            audit={
                "node_path": path,
                "feature": "quivering_palm",
                "monk_level": monk_level,
            },
        )
        getattr(target, "status_effects").append(effect.to_dict())
        ctx.quivering_palm_applied = True
        ctx.result.state_changes.append(
            {
                "type": "cost",
                "actor_id": ctx.actor_id,
                "resource": FOCUS_RESOURCE_ID,
                "before": before,
                "after": before - 4,
                "source_action_id": QUIVERING_PALM_ACTION_ID,
                "path": f"{path}.quivering_palm",
            }
        )
        ctx.result.state_changes.append(
            {
                "type": "quivering_palm",
                "actor_id": ctx.actor_id,
                "target_id": target_id,
                "source_action_id": QUIVERING_PALM_ACTION_ID,
                "effect_id": effect.effect_id,
                "condition": effect.condition,
                "duration": effect.duration,
                "replaced_effects": replaced,
                "path": f"{path}.quivering_palm",
            }
        )

    def _node_quivering_palm_release(
        self,
        ctx: _Context,
        node: dict[str, Any],
        path: str,
    ) -> None:
        del node
        if len(ctx.targets) != 1:
            raise AutomationError("Quivering Palm release requires a single target")
        target_id = ctx.targets[0]
        effect = self._quivering_palm_effect(ctx.actor_id, target_id)
        if effect is None:
            raise AutomationError("Quivering Palm release requires that target to be vibrating")
        harmless = self._quivering_palm_harmless_requested(ctx.params)
        if not harmless and not self._quivering_palm_same_plane(ctx.params):
            raise AutomationError("Quivering Palm release requires the target on same plane")
        removed = self._remove_quivering_palm_effect(ctx.actor_id, target_id)
        if harmless:
            ctx.result.state_changes.append(
                {
                    "type": "quivering_palm_release",
                    "actor_id": ctx.actor_id,
                    "target_id": target_id,
                    "source_action_id": QUIVERING_PALM_RELEASE_ACTION_ID,
                    "harmless": True,
                    "removed_effects": removed,
                    "path": path,
                }
            )
            return

        dc = self._monk_focus_save_dc(ctx.actor_id)
        dc_source = "monk_focus:wis+proficiency"
        save_result = self._roll_quivering_palm_save(ctx, target_id, dc, dc_source, path)
        damage_roll = self.roll_service.roll("10d12")
        ctx.result.dice_rolls.append(damage_roll.to_dict())
        amount_before_save = damage_roll.total
        amount = amount_before_save // 2 if save_result["success"] else amount_before_save
        target = self._entity(target_id)
        hp_before = int(getattr(target, "hp_current"))
        damage_taken = self._mitigated_damage(target, amount, "force")
        applied = self._apply_damage(target_id, amount, "force", ctx=ctx, path=path)
        hp_after = int(getattr(self._entity(target_id), "hp_current"))
        ctx.last_damage_taken[target_id] = damage_taken
        ctx.result.node_results[path] = {
            "target_id": target_id,
            "dc": dc,
            "dc_source": dc_source,
            "saving_throw": save_result,
            "damage_roll_total": damage_roll.total,
            "amount_before_save": amount_before_save,
            "amount": amount,
            "applied": applied,
            "damage_type": "force",
            "hp_before": hp_before,
            "hp_after": hp_after,
        }
        ctx.result.state_changes.append(
            {
                "type": "quivering_palm_release",
                "actor_id": ctx.actor_id,
                "target_id": target_id,
                "source_action_id": QUIVERING_PALM_RELEASE_ACTION_ID,
                "harmless": False,
                "removed_effects": removed,
                "dc": dc,
                "dc_source": dc_source,
                "saving_throw_success": save_result["success"],
                "damage_roll_total": damage_roll.total,
                "amount_before_save": amount_before_save,
                "amount": amount,
                "applied": applied,
                "damage_type": "force",
                "hp_before": hp_before,
                "hp_after": hp_after,
                "path": path,
            }
        )
        concentration = self._concentration_save_after_damage(target_id, damage_taken, path)
        if concentration is not None:
            concentration_change, concentration_roll = concentration
            ctx.result.dice_rolls.append(concentration_roll.to_dict())
            ctx.result.state_changes.append(concentration_change)
        if damage_taken > 0:
            ctx.result.state_changes.extend(
                self._expire_target_effects_on_damage(
                    ctx,
                    target_id,
                    path,
                    damage_source_actor_id=ctx.actor_id,
                )
            )
        if hp_before > 0 and hp_after == 0 and applied > 0:
            ctx.result.state_changes.extend(
                self._dark_ones_blessing_changes(
                    ctx.actor_id,
                    target_id,
                    path,
                )
            )

    def _roll_quivering_palm_save(
        self,
        ctx: _Context,
        target_id: str,
        dc: int,
        dc_source: str,
        path: str,
    ) -> dict[str, Any]:
        target = self._entity(target_id)
        base_bonus, proficient, _ = self._saving_throw_bonus(target, "con")
        target_exhaustion_level, exhaustion_penalty = self._exhaustion_details(target)
        bonus = base_bonus - exhaustion_penalty
        status_advantage, status_sources = self._saving_throw_status_advantage(target, "con")
        roll = self.roll_service.roll(d20_expression(bonus), advantage=status_advantage)
        adjustment, adjustment_rolls, adjustment_sources = self._passive_roll_adjustment(
            target,
            bonus_key="saving_throw_bonus_dice",
            penalty_key="saving_throw_penalty_dice",
        )
        ctx.result.dice_rolls.append(roll.to_dict())
        ctx.result.dice_rolls.extend(extra.to_dict() for extra in adjustment_rolls)
        total = roll.total + adjustment
        return {
            "target_id": target_id,
            "ability": "con",
            "dc": dc,
            "dc_source": dc_source,
            "bonus": bonus,
            "base_bonus": base_bonus,
            "proficient": proficient,
            "exhaustion_level": target_exhaustion_level,
            "d20_penalty": exhaustion_penalty,
            "base_total": roll.total,
            "passive_adjustment": adjustment,
            "passive_sources": adjustment_sources,
            "status_advantage": status_advantage,
            "status_sources": status_sources,
            "total": total,
            "success": total >= dc,
            "path": f"{path}.save",
        }

    def _quivering_palm_effect(
        self,
        actor_id: str,
        target_id: str,
    ) -> dict[str, Any] | None:
        for _, _, effects in self._target_effect_lists(target_id):
            for effect in effects:
                if self._is_quivering_palm_effect_for_actor(effect, actor_id):
                    return effect
        return None

    def _remove_quivering_palm_effect(
        self,
        actor_id: str,
        target_id: str,
    ) -> list[dict[str, Any]]:
        removed: list[dict[str, Any]] = []
        for owner_type, owner_id, effects in self._target_effect_lists(target_id):
            retained: list[dict[str, Any]] = []
            for effect in effects:
                if self._is_quivering_palm_effect_for_actor(effect, actor_id):
                    removed.append(
                        {
                            "owner_type": owner_type,
                            "owner_id": owner_id,
                            "effect_id": effect.get("effect_id"),
                            "target_id": effect.get("target_id"),
                            "source_action_id": effect.get("source_action_id"),
                        }
                    )
                else:
                    retained.append(effect)
            effects[:] = retained
        return removed

    def _clear_quivering_palm_effects_for_actor(self, actor_id: str) -> list[dict[str, Any]]:
        removed: list[dict[str, Any]] = []
        effect_lists: list[tuple[str, str, list[dict[str, Any]]]] = []
        effect_lists.extend(
            ("character", character_id, character.status_effects)
            for character_id, character in self.state.characters.items()
        )
        effect_lists.extend(
            ("monster", monster_id, monster.status_effects)
            for monster_id, monster in self.state.monsters.items()
        )
        if self.state.encounter is not None:
            effect_lists.extend(
                ("combatant", combatant_id, combatant.status_effects)
                for combatant_id, combatant in self.state.encounter.combatants.items()
            )
        for owner_type, owner_id, effects in effect_lists:
            retained: list[dict[str, Any]] = []
            for effect in effects:
                if self._is_quivering_palm_effect_for_actor(effect, actor_id):
                    removed.append(
                        {
                            "owner_type": owner_type,
                            "owner_id": owner_id,
                            "effect_id": effect.get("effect_id"),
                            "target_id": effect.get("target_id"),
                            "source_action_id": effect.get("source_action_id"),
                        }
                    )
                else:
                    retained.append(effect)
            effects[:] = retained
        return removed

    def _is_quivering_palm_effect_for_actor(
        self,
        effect: dict[str, Any],
        actor_id: str,
    ) -> bool:
        applied_by = effect.get("applied_by")
        return (
            effect.get("condition") == QUIVERING_PALM_CONDITION
            and effect.get("source_action_id") == QUIVERING_PALM_ACTION_ID
            and isinstance(applied_by, str)
            and self._entity_ids_match(applied_by, actor_id)
        )

    def _apply_eldritch_smite_prone_if_requested(
        self,
        ctx: _Context,
        target_id: str,
        path: str,
    ) -> None:
        if target_id not in ctx.eldritch_smite_targets:
            return
        if not self._eldritch_smite_prone_requested(ctx.params):
            return
        target = self._entity(target_id)
        immunity_sources = self._condition_immunity_sources(target, "prone")
        if immunity_sources:
            ctx.result.state_changes.append(
                {
                    "type": "condition_immune",
                    "target_id": target_id,
                    "condition": "prone",
                    "immunity_sources": immunity_sources,
                    "path": f"{path}.eldritch_smite",
                }
            )
            return
        effect = EffectInstance(
            effect_id=self._effect_id(target_id, f"{path}-eldritch-smite-prone"),
            source_ref="SRD 5.2.1 Warlock Eldritch Invocation Options: Eldritch Smite",
            source_action_id=ELDRITCH_SMITE_ACTION_ID,
            target_id=target_id,
            applied_by=ctx.actor_id,
            condition="prone",
            duration={"until": "stands_up"},
            tick_on=None,
            stacking_policy="replace",
            audit={"node_path": path, "feature": "eldritch_smite"},
        )
        effects = getattr(target, "status_effects")
        effects[:] = [
            existing
            for existing in effects
            if existing.get("condition") != effect.condition
            or existing.get("source_action_id") != effect.source_action_id
        ]
        effects.append(effect.to_dict())
        ctx.result.state_changes.append(
            {
                "type": "condition",
                "target_id": target_id,
                "condition": "prone",
                "effect_id": effect.effect_id,
                "source_action_id": effect.source_action_id,
                "duration": effect.duration,
                "tick_on": effect.tick_on,
                "path": f"{path}.eldritch_smite",
            }
        )

    def _has_stunning_strike_used(self, actor_id: str) -> bool:
        actor = self._entity(actor_id)
        return any(
            effect.get("condition") == "stunning_strike_used"
            and effect.get("source_action_id") == STUNNING_STRIKE_ACTION_ID
            for effect in self._status_effects_for(actor)
        )

    def _mark_stunning_strike_used(self, ctx: _Context, target_id: str) -> None:
        actor = self._entity(ctx.actor_id)
        effect = EffectInstance(
            effect_id=self._effect_id(ctx.actor_id, "stunning_strike_used"),
            source_ref="SRD 5.2.1 Monk Class Features: Level 5: Stunning Strike",
            source_action_id=STUNNING_STRIKE_ACTION_ID,
            target_id=ctx.actor_id,
            applied_by=ctx.actor_id,
            condition="stunning_strike_used",
            duration={"until": "start_of_next_turn"},
            tick_on="self_turn_start",
            stacking_policy="replace",
            audit={"target_id": target_id},
        )
        getattr(actor, "status_effects").append(effect.to_dict())
        ctx.result.state_changes.append(
            {
                "type": "stunning_strike_used",
                "target_id": target_id,
                "effect_id": effect.effect_id,
                "condition": effect.condition,
            }
        )

    @staticmethod
    def _normalize_open_hand_technique_effect(raw: Any) -> str | None:
        if raw in (None, "", False):
            return None
        effect = str(raw).casefold().strip().replace("-", "_").replace(" ", "_")
        if effect not in OPEN_HAND_TECHNIQUE_EFFECTS:
            raise AutomationError(f"unsupported Open Hand Technique effect: {effect}")
        return effect

    @classmethod
    def _open_hand_technique_choice(
        cls,
        params: dict[str, Any],
        *,
        target_id: str,
        strike_index: int,
    ) -> str | None:
        raw: Any = None
        by_strike = params.get("open_hand_technique_by_strike")
        if isinstance(by_strike, dict):
            raw = by_strike.get(str(strike_index), by_strike.get(strike_index))
        by_target = params.get("open_hand_technique_by_target")
        if raw in (None, "", False) and isinstance(by_target, dict):
            raw = by_target.get(target_id)
        if raw in (None, "", False):
            raw = params.get(
                "open_hand_technique",
                params.get("open_hand_technique_effect"),
            )
        return cls._normalize_open_hand_technique_effect(raw)

    @staticmethod
    def _open_hand_push_destination(
        params: dict[str, Any],
        *,
        target_id: str,
        strike_index: int,
    ) -> str | None:
        by_strike = params.get("open_hand_push_to_position_node_id_by_strike")
        if isinstance(by_strike, dict):
            selected = by_strike.get(str(strike_index), by_strike.get(strike_index))
            if selected not in (None, "", False):
                return str(selected)
        by_target = params.get("open_hand_push_to_position_node_id_by_target")
        if isinstance(by_target, dict):
            selected = by_target.get(target_id)
            if selected not in (None, "", False):
                return str(selected)
        selected = params.get("open_hand_push_to_position_node_id")
        if selected in (None, "", False):
            return None
        return str(selected)

    def _open_hand_push_plan(
        self,
        actor_id: str,
        target_id: str,
        destination: str,
    ) -> dict[str, Any]:
        actor = self._entity(actor_id)
        target = self._entity(target_id)
        if not isinstance(actor, Combatant) or not isinstance(target, Combatant):
            raise AutomationError("Open Hand Technique Push requires combatants")
        if self.state.encounter is None or self.state.encounter.tactical_graph is None:
            raise AutomationError("Open Hand Technique Push requires a combat tactical graph")
        if actor.position_node_id is None or target.position_node_id is None:
            raise AutomationError("Open Hand Technique Push requires current positions")
        graph = TacticalGraph.from_dict(self.state.encounter.tactical_graph)
        if destination not in graph.nodes:
            raise AutomationError("Open Hand Technique Push destination position does not exist")
        movement_distance = graph.shortest_distance(target.position_node_id, destination)
        if movement_distance is None:
            raise AutomationError("Open Hand Technique Push destination position is not reachable")
        if int(movement_distance) > 15:
            raise AutomationError("Open Hand Technique Push cannot exceed 15 feet")
        before_distance = graph.shortest_distance(actor.position_node_id, target.position_node_id)
        after_distance = graph.shortest_distance(actor.position_node_id, destination)
        if (
            before_distance is not None
            and after_distance is not None
            and after_distance <= before_distance
        ):
            raise AutomationError("Open Hand Technique Push destination must be away from the monk")
        return {
            "target": target,
            "movement_distance": int(movement_distance),
            "distance_from_actor_before": before_distance,
            "distance_from_actor_after": after_distance,
        }

    def _validate_repelling_blast_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        targets: list[str],
        params: dict[str, Any],
    ) -> None:
        if not self._repelling_blast_requested(params):
            return
        actor = self._resource_owner(actor_id)
        spell_id = action.properties.get("spell_definition_id")
        if not isinstance(actor, Character) or not has_warlock_repelling_blast(
            actor,
            spell_id=str(spell_id) if isinstance(spell_id, str) else None,
        ):
            raise AutomationError("Repelling Blast requires the selected Warlock invocation")
        if not self._action_qualifies_for_repelling_blast(action):
            raise AutomationError("Repelling Blast requires a Warlock cantrip attack roll")
        if not targets:
            raise AutomationError("Repelling Blast requires a target")
        for target_id in targets:
            if not self._target_large_or_smaller(target_id):
                raise AutomationError("Repelling Blast target must be Large or smaller")
            destination = self._repelling_blast_destination(params, target_id=target_id)
            if destination is None:
                raise AutomationError("Repelling Blast requires a destination position")
            self._repelling_blast_plan(actor_id, target_id, destination)

    @staticmethod
    def _repelling_blast_requested(params: dict[str, Any]) -> bool:
        return params.get("use_repelling_blast") is True

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

    def _action_qualifies_for_repelling_blast(self, action: ActionDefinition) -> bool:
        if action.action_type != "spell":
            return False
        nodes = self._automation_nodes(action.automation)
        return any(node.get("type") == "attack_roll" for node in nodes) and any(
            node.get("type") == "damage" and node.get("requires_hit") is True for node in nodes
        )

    def _apply_repelling_blast_if_requested(
        self,
        ctx: _Context,
        target_id: str,
        path: str,
    ) -> None:
        if not self._repelling_blast_requested(ctx.params):
            return
        if not ctx.attack_hits.get(target_id, False):
            return
        destination = self._repelling_blast_destination(ctx.params, target_id=target_id)
        if destination is None:
            raise AutomationError("Repelling Blast requires a destination position")
        plan = self._repelling_blast_plan(ctx.actor_id, target_id, destination)
        target = plan["target"]
        assert isinstance(target, Combatant)
        before_position = target.position_node_id
        target.position_node_id = destination
        ctx.result.state_changes.append(
            {
                "type": "repelling_blast",
                "actor_id": ctx.actor_id,
                "target_id": target_id,
                "source_action_id": REPELLING_BLAST_ACTION_ID,
                "from": before_position,
                "to": target.position_node_id,
                "forced_movement_distance": int(plan["movement_distance"]),
                "distance_from_actor_before": plan["distance_from_actor_before"],
                "distance_from_actor_after": plan["distance_from_actor_after"],
                "path": f"{path}.repelling_blast",
            }
        )

    def _repelling_blast_plan(
        self,
        actor_id: str,
        target_id: str,
        destination: str,
    ) -> dict[str, Any]:
        actor = self._entity(actor_id)
        target = self._entity(target_id)
        if not isinstance(actor, Combatant) or not isinstance(target, Combatant):
            raise AutomationError("Repelling Blast requires combatants")
        if self.state.encounter is None or self.state.encounter.tactical_graph is None:
            raise AutomationError("Repelling Blast requires a combat tactical graph")
        if actor.position_node_id is None or target.position_node_id is None:
            raise AutomationError("Repelling Blast requires current positions")
        graph = TacticalGraph.from_dict(self.state.encounter.tactical_graph)
        if destination not in graph.nodes:
            raise AutomationError("Repelling Blast destination position does not exist")
        movement_distance = graph.shortest_distance(target.position_node_id, destination)
        if movement_distance is None:
            raise AutomationError("Repelling Blast destination position is not reachable")
        if int(movement_distance) > 10:
            raise AutomationError("Repelling Blast cannot exceed 10 feet")
        before_distance = graph.shortest_distance(actor.position_node_id, target.position_node_id)
        after_distance = graph.shortest_distance(actor.position_node_id, destination)
        if (
            before_distance is not None
            and after_distance is not None
            and after_distance <= before_distance
        ):
            raise AutomationError("Repelling Blast destination must be away from the Warlock")
        return {
            "target": target,
            "movement_distance": int(movement_distance),
            "distance_from_actor_before": before_distance,
            "distance_from_actor_after": after_distance,
        }

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

    def _has_sneak_attack_used(self, actor_id: str) -> bool:
        actor = self._entity(actor_id)
        return any(
            effect.get("condition") == "sneak_attack_used"
            and effect.get("source_action_id") == "srd.sneak_attack"
            for effect in self._status_effects_for(actor)
        )

    def _has_ally_within_5ft_of_target(self, actor_id: str, target_id: str) -> bool:
        if self.state.encounter is None:
            return False
        actor = self._entity(actor_id)
        target = self._entity(target_id)
        if not isinstance(actor, Combatant) or not isinstance(target, Combatant):
            return False
        for ally_id, ally in self.state.encounter.combatants.items():
            if ally_id == actor_id or ally.side != actor.side:
                continue
            if any(
                effect.get("condition") == "incapacitated"
                for effect in self._status_effects_for(ally)
            ):
                continue
            distance = self._combat_distance(ally, target)
            if distance is not None and distance <= 5:
                return True
        return False

    def _mark_sneak_attack_used(self, ctx: _Context, target_id: str) -> None:
        actor = self._entity(ctx.actor_id)
        effect = EffectInstance(
            effect_id=self._effect_id(ctx.actor_id, "sneak_attack_used"),
            source_ref="SRD 5.2.1 Rogue Class Features: Level 1: Sneak Attack",
            source_action_id="srd.sneak_attack",
            target_id=ctx.actor_id,
            applied_by=ctx.actor_id,
            condition="sneak_attack_used",
            duration={"until": "start_of_next_turn"},
            tick_on="self_turn_start",
            stacking_policy="replace",
            audit={"target_id": target_id},
        )
        getattr(actor, "status_effects").append(effect.to_dict())
        ctx.result.state_changes.append(
            {
                "type": "sneak_attack",
                "target_id": target_id,
                "effect_id": effect.effect_id,
                "condition": effect.condition,
            }
        )

    def _passive_ability_advantage_sources(
        self,
        entity: Character | Monster | Combatant,
        *,
        modifier: str,
        ability: str,
    ) -> list[dict[str, Any]]:
        ability = ability.lower()
        sources: list[dict[str, Any]] = []
        for effect in self._status_effects_for(entity):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            abilities = modifiers.get(modifier, [])
            if isinstance(abilities, str):
                abilities = [abilities]
            if not isinstance(abilities, list):
                continue
            normalized = {str(entry).lower() for entry in abilities}
            if ability not in normalized:
                continue
            sources.append(
                {
                    "effect_id": effect.get("effect_id"),
                    "source_action_id": effect.get("source_action_id"),
                    "modifier": modifier,
                    "ability": ability,
                }
            )
        return sources

    def _passive_skill_advantage_sources(
        self,
        entity: Character | Monster | Combatant,
        *,
        ability: str,
        skill: str | None,
        contexts: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        if skill is None:
            return []
        contexts = contexts or set()
        sources: list[dict[str, Any]] = []
        for effect in self._status_effects_for(entity):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            entries = modifiers.get("ability_check_advantage_skills", [])
            if isinstance(entries, (str, dict)):
                entries = [entries]
            if not isinstance(entries, list):
                continue
            if not any(
                _skill_advantage_entry_matches(
                    entry,
                    ability=ability,
                    skill=skill,
                    contexts=contexts,
                )
                for entry in entries
            ):
                continue
            sources.append(
                {
                    "effect_id": effect.get("effect_id"),
                    "source_action_id": effect.get("source_action_id"),
                    "modifier": "ability_check_advantage_skills",
                    "ability": ability.lower(),
                    "skill": skill,
                    "contexts": sorted(contexts),
                }
            )
        return sources

    def _passive_damage_resistance_sources(
        self,
        target: Character | Monster | Combatant,
        damage_type: str,
    ) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        owner = target
        if isinstance(target, Combatant) and target.entity_id in self.state.characters:
            owner = self.state.characters[target.entity_id]
        if (
            isinstance(owner, Character)
            and draconic_elemental_affinity_damage_type(owner) == damage_type
        ):
            sources.append(
                {
                    "source_action_id": "srd.elemental_affinity",
                    "modifier": "draconic_elemental_affinity_resistance",
                    "damage_type": damage_type,
                }
            )
        if (
            isinstance(owner, Character)
            and druid_natures_ward_resistance_type(owner) == damage_type
        ):
            sources.append(
                {
                    "source_action_id": "srd.natures_ward",
                    "modifier": "druid_natures_ward_resistance",
                    "damage_type": damage_type,
                }
            )
        if (
            isinstance(owner, Character)
            and warlock_fiendish_resilience_damage_type(owner) == damage_type
        ):
            sources.append(
                {
                    "source_action_id": "srd.fiendish_resilience",
                    "modifier": "warlock_fiendish_resilience",
                    "damage_type": damage_type,
                }
            )
        for effect in self._status_effects_for(target):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            if modifiers.get("all_damage_resistance") is True:
                exceptions = _string_set(modifiers.get("all_damage_resistance_except"))
                if damage_type not in exceptions:
                    source = {
                        "effect_id": effect.get("effect_id"),
                        "source_action_id": effect.get("source_action_id"),
                        "modifier": "all_damage_resistance",
                    }
                    if exceptions:
                        source["except"] = sorted(exceptions)
                    sources.append(source)
                    continue
            resistances = modifiers.get("damage_resistances", [])
            if isinstance(resistances, str):
                resistances = [resistances]
            if not isinstance(resistances, list):
                continue
            if damage_type in {str(entry) for entry in resistances}:
                sources.append(
                    {
                        "effect_id": effect.get("effect_id"),
                        "source_action_id": effect.get("source_action_id"),
                        "modifier": "damage_resistances",
                        "damage_type": damage_type,
                    }
                )
        return sources

    def _passive_hp_max_reduction_prevention_sources(
        self,
        target: Character | Monster | Combatant,
    ) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        for effect in self._status_effects_for(target):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            if modifiers.get("prevents_hp_max_reduction") is True:
                sources.append(
                    {
                        "effect_id": effect.get("effect_id"),
                        "source_action_id": effect.get("source_action_id"),
                        "modifier": "prevents_hp_max_reduction",
                    }
                )
        return sources

    def _expire_effects_ended_by_condition(
        self,
        target_id: str,
        condition: str,
        path: str,
    ) -> list[dict[str, Any]]:
        expired: list[dict[str, Any]] = []
        for owner_type, owner_id, effects in self._target_effect_lists(target_id):
            retained: list[dict[str, Any]] = []
            for effect in effects:
                if self._effect_ends_if_condition(effect, condition):
                    expired.append(
                        {
                            "type": "effect_expired",
                            "target_id": target_id,
                            "owner_type": owner_type,
                            "owner_id": owner_id,
                            "effect_id": effect.get("effect_id"),
                            "source_action_id": effect.get("source_action_id"),
                            "condition": effect.get("condition"),
                            "ended_by_condition": condition,
                            "path": path,
                        }
                    )
                    continue
                retained.append(effect)
            effects[:] = retained
        return expired

    @staticmethod
    def _effect_ends_if_condition(effect: dict[str, Any], condition: str) -> bool:
        modifiers = effect.get("passive_modifiers", {})
        return isinstance(modifiers, dict) and modifiers.get("ends_if_condition") == condition

    def _status_effects_for(self, entity: Character | Monster | Combatant) -> list[dict[str, Any]]:
        effects = list(getattr(entity, "status_effects", []))
        if isinstance(entity, Combatant) and entity.entity_id in self.state.characters:
            effects.extend(self.state.characters[entity.entity_id].status_effects)
        if isinstance(entity, Combatant) and entity.entity_id in self.state.monsters:
            effects.extend(self.state.monsters[entity.entity_id].status_effects)
        return effects

    def _out_of_play_sources(self, entity: Character | Monster | Combatant) -> list[str]:
        sources: list[str] = []
        for effect in self._status_effects_for(entity):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict) or modifiers.get("out_of_play") is not True:
                continue
            source = effect.get("source_action_id") or effect.get("condition") or "effect"
            sources.append(str(source))
        return sources

    def _exhaustion_details(self, entity: Character | Monster | Combatant) -> tuple[int, int]:
        effects = self._status_effects_for(entity)
        level = exhaustion_level(effects)
        return level, exhaustion_d20_penalty(effects)

    def _effective_speed(self, entity: Character | Monster | Combatant) -> int:
        base_speed = self._speed_override(entity)
        if base_speed is None:
            base_speed = int(getattr(entity, "speed_ft", 30))
        base_speed += self._class_feature_speed_bonus(entity)
        return effective_speed(
            base_speed,
            self._status_effects_for(entity),
        )

    def _class_feature_speed_bonus(self, entity: Character | Monster | Combatant) -> int:
        owner = entity
        if isinstance(entity, Combatant) and entity.entity_id in self.state.characters:
            owner = self.state.characters[entity.entity_id]
        if isinstance(owner, Character):
            return class_feature_speed_bonus(owner)
        return 0

    def _speed_override(self, entity: Character | Monster | Combatant) -> int | None:
        speed_override: int | None = None
        for effect in self._status_effects_for(entity):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            speed = modifiers.get("speed_override_ft")
            if isinstance(speed, int) and not isinstance(speed, bool):
                speed_override = speed
        return speed_override

    def _persistent_condition_owner(
        self,
        target: Character | Monster | Combatant,
    ) -> Character | Monster | Combatant:
        if isinstance(target, Combatant) and target.entity_id in self.state.characters:
            return self.state.characters[target.entity_id]
        if isinstance(target, Combatant) and target.entity_id in self.state.monsters:
            return self.state.monsters[target.entity_id]
        return target

    def _food_drink_exhaustion_immunity_sources(
        self,
        target: Character | Monster | Combatant,
        action_id: str,
    ) -> list[dict[str, Any]]:
        if action_id not in FOOD_DRINK_EXHAUSTION_HAZARD_IDS:
            return []
        owner = target
        if isinstance(target, Combatant) and target.entity_id in self.state.characters:
            owner = self.state.characters[target.entity_id]
        if not isinstance(owner, Character):
            return []
        if not monk_forgoing_food_drink_exhaustion_immunity(owner):
            return []
        return [
            {
                "source_action_id": "srd.self_restoration",
                "modifier": "forgoing_food_and_drink_does_not_cause_exhaustion",
                "hazard_id": action_id,
            }
        ]

    def _exhaustion_death_change(
        self,
        target_id: str,
        target: Character | Monster | Combatant,
        owner: Character | Monster | Combatant,
        level: int,
        path: str,
    ) -> dict[str, Any] | None:
        if level < 6:
            return None
        death_ward = self._consume_death_ward(
            target_id,
            trigger="instant_death_without_damage",
            path=path,
        )
        if death_ward is not None:
            death_ward["negated_reason"] = "exhaustion"
            death_ward["exhaustion_level"] = level
            return death_ward
        changed: list[dict[str, Any]] = []
        seen: set[int] = set()
        for entity in (target, owner):
            entity_key = id(entity)
            if entity_key in seen:
                continue
            seen.add(entity_key)
            before_hp = int(getattr(entity, "hp_current", 0))
            before_dead = bool(getattr(entity, "dead", False))
            if hasattr(entity, "hp_current"):
                setattr(entity, "hp_current", 0)
            if hasattr(entity, "dead"):
                setattr(entity, "dead", True)
            if hasattr(entity, "stable"):
                setattr(entity, "stable", False)
            changed.append(
                {
                    "entity_id": getattr(entity, "id", target_id),
                    "hp_before": before_hp,
                    "hp_after": int(getattr(entity, "hp_current", 0)),
                    "dead_before": before_dead,
                    "dead_after": bool(getattr(entity, "dead", False)),
                }
            )
        return {
            "type": "death",
            "target_id": target_id,
            "reason": "exhaustion",
            "exhaustion_level": level,
            "entities": changed,
            "path": path,
        }

    @staticmethod
    def _is_death_ward_effect(effect: dict[str, Any]) -> bool:
        modifiers = effect.get("passive_modifiers", {})
        return isinstance(modifiers, dict) and modifiers.get("death_ward") is True

    def _consume_death_ward(
        self,
        target_id: str,
        *,
        trigger: str,
        path: str,
    ) -> dict[str, Any] | None:
        removed: list[dict[str, Any]] = []
        for owner_type, owner_id, effects in self._target_effect_lists(target_id):
            retained: list[dict[str, Any]] = []
            for effect in effects:
                if self._is_death_ward_effect(effect):
                    removed.append(
                        {
                            "owner_type": owner_type,
                            "owner_id": owner_id,
                            "effect_id": effect.get("effect_id"),
                            "source_action_id": effect.get("source_action_id"),
                        }
                    )
                    continue
                retained.append(effect)
            effects[:] = retained
        if not removed:
            return None
        return {
            "type": "death_ward",
            "target_id": target_id,
            "source_action_id": "srd.death_ward",
            "trigger": trigger,
            "removed_effects": removed,
            "path": path,
        }

    def _death_ward_after_drop_to_zero(
        self,
        target_id: str,
        *,
        hp_before: int,
        hp_after_without_death_ward: int,
        path: str,
    ) -> dict[str, Any] | None:
        if hp_before <= 0 or hp_after_without_death_ward != 0:
            return None
        death_ward = self._consume_death_ward(
            target_id,
            trigger="drop_to_0_hp",
            path=path,
        )
        if death_ward is None:
            return None
        self._set_hp_and_clear_death_state(target_id, 1)
        death_ward["hp_before"] = hp_before
        death_ward["hp_after_without_death_ward"] = hp_after_without_death_ward
        death_ward["hp_after"] = 1
        return death_ward

    def _attack_status_advantage(
        self,
        actor: Character | Monster | Combatant,
        target: Character | Monster | Combatant,
        distance_ft: int | None,
        *,
        actor_id: str,
        target_id: str,
        action: ActionDefinition,
        ability: str,
        node_advantage: str | None = None,
    ) -> tuple[str | None, list[dict[str, Any]]]:
        advantage_sources = self._condition_sources(actor, {"invisible"})
        advantage_sources.extend(
            self._condition_sources(
                target,
                {"blinded", "paralyzed", "petrified", "restrained", "stunned", "unconscious"},
            )
        )
        if distance_ft is not None and distance_ft <= 5:
            advantage_sources.extend(self._condition_sources(target, {"prone"}))
        advantage_sources.extend(self._spell_attack_advantage_sources(actor, action))
        advantage_sources.extend(
            self._attack_advantage_by_ability_sources(actor, action, ability=ability)
        )
        advantage_sources.extend(
            self._attack_roll_advantage_sources(actor, action, actor_id, target_id)
        )
        advantage_sources.extend(self._incoming_attack_advantage_sources(target))
        advantage_blocked_source = self._elusive_attack_advantage_block_source(
            target_id,
            target,
            node_advantage=node_advantage,
            advantage_sources=advantage_sources,
        )
        if advantage_blocked_source is not None:
            advantage_sources = []
        disadvantage_sources = self._condition_sources(
            actor,
            {"blinded", "frightened", "poisoned", "prone", "restrained"},
        )
        disadvantage_sources.extend(self._attack_roll_disadvantage_sources(actor, action))
        disadvantage_sources.extend(
            self._escape_the_horde_disadvantage_sources(
                action,
                target_id,
            )
        )
        disadvantage_sources.extend(
            self._multiattack_defense_disadvantage_sources(
                actor,
                target_id,
            )
        )
        disadvantage_sources.extend(self._grappled_non_grappler_sources(actor, target, target_id))
        disadvantage_sources.extend(self._condition_sources(target, {"invisible"}))
        if distance_ft is not None and distance_ft > 5:
            disadvantage_sources.extend(self._condition_sources(target, {"prone"}))
        disadvantage_sources.extend(self._strong_wind_ranged_weapon_sources(actor, action))
        return _merge_advantage(
            None,
            "advantage" if advantage_sources else None,
            "disadvantage" if disadvantage_sources else None,
        ), (
            (
                [{"kind": "advantage_blocked", **advantage_blocked_source}]
                if advantage_blocked_source is not None
                else []
            )
            + [{"kind": "advantage", **source} for source in advantage_sources]
            + [{"kind": "disadvantage", **source} for source in disadvantage_sources]
        )

    def _elusive_attack_advantage_block_source(
        self,
        target_id: str,
        target: Character | Monster | Combatant,
        *,
        node_advantage: str | None,
        advantage_sources: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        owner = self._resource_owner(target_id)
        if not isinstance(owner, Character) or not rogue_elusive_applies(owner):
            return None
        if self._condition_sources(target, {"incapacitated"}):
            return None
        if node_advantage is None and not advantage_sources:
            return None
        blocked_sources = list(advantage_sources)
        if node_advantage is not None:
            blocked_sources.append(
                {"modifier": "attack_node_advantage", "advantage": node_advantage}
            )
        return {
            "source_action_id": ELUSIVE_ACTION_ID,
            "modifier": "elusive_blocks_attack_advantage",
            "blocked_sources": blocked_sources,
        }

    def _attack_roll_advantage_sources(
        self,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
        actor_id: str,
        target_id: str,
    ) -> list[dict[str, Any]]:
        sources = self._studied_attacks_advantage_sources(actor, target_id)
        sources.extend(self._precise_hunter_advantage_sources(actor_id, target_id))
        if action.action_type not in ATTACK_ACTION_TYPES:
            return sources
        for effect in self._status_effects_for(actor):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            if modifiers.get("attack_roll_advantage") is not True:
                continue
            sources.append(
                {
                    "condition": effect.get("condition"),
                    "effect_id": effect.get("effect_id"),
                    "source_action_id": effect.get("source_action_id"),
                    "modifier": "attack_roll_advantage",
                }
            )
        return sources

    def _precise_hunter_advantage_sources(
        self,
        actor_id: str,
        target_id: str,
    ) -> list[dict[str, Any]]:
        actor_owner = self._resource_owner(actor_id)
        if not isinstance(actor_owner, Character) or not has_precise_hunter(actor_owner):
            return []
        if not self._target_marked_by_hunters_mark(actor_id, target_id):
            return []
        return [
            {
                "source_action_id": PRECISE_HUNTER_ACTION_ID,
                "modifier": "precise_hunter",
                "target_id": target_id,
            }
        ]

    def _studied_attacks_advantage_sources(
        self,
        actor: Character | Monster | Combatant,
        target_id: str,
    ) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        for effect in self._status_effects_for(actor):
            if effect.get("condition") != STUDIED_ATTACKS_CONDITION:
                continue
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            if modifiers.get("studied_attacks_advantage") is not True:
                continue
            studied_target_id = modifiers.get("studied_attacks_target_id")
            if studied_target_id is None or not self._entity_ids_match(
                str(studied_target_id),
                target_id,
            ):
                continue
            sources.append(
                {
                    "condition": effect.get("condition"),
                    "effect_id": effect.get("effect_id"),
                    "source_action_id": effect.get("source_action_id"),
                    "modifier": "studied_attacks_advantage",
                    "target_id": str(studied_target_id),
                }
            )
        return sources

    def _studied_attacks_effect_ids_for(
        self,
        actor: Character | Monster | Combatant,
        target_id: str,
    ) -> set[str]:
        effect_ids: set[str] = set()
        for effect in self._status_effects_for(actor):
            if effect.get("condition") != STUDIED_ATTACKS_CONDITION:
                continue
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            studied_target_id = modifiers.get("studied_attacks_target_id")
            effect_id = effect.get("effect_id")
            if (
                studied_target_id is None
                or effect_id is None
                or not self._entity_ids_match(str(studied_target_id), target_id)
            ):
                continue
            effect_ids.add(str(effect_id))
        return effect_ids

    def _expire_studied_attacks_effects_on_attack(
        self,
        ctx: _Context,
        target_id: str,
        effect_ids: set[str],
        path: str,
    ) -> None:
        if not effect_ids:
            return
        removed: list[dict[str, Any]] = []
        for owner_type, owner_id, effects in self._actor_effect_lists(ctx.actor_id):
            retained: list[dict[str, Any]] = []
            for effect in effects:
                effect_id = effect.get("effect_id")
                if effect_id is not None and str(effect_id) in effect_ids:
                    removed.append(
                        {
                            "owner_type": owner_type,
                            "owner_id": owner_id,
                            "effect_id": effect_id,
                            "condition": effect.get("condition"),
                            "source_action_id": effect.get("source_action_id"),
                        }
                    )
                else:
                    retained.append(effect)
            effects[:] = retained
        if removed:
            ctx.result.state_changes.append(
                {
                    "type": "effect_expired",
                    "actor_id": ctx.actor_id,
                    "target_id": target_id,
                    "trigger": "studied_attacks_attack",
                    "removed": removed,
                    "path": path,
                }
            )

    def _apply_studied_attacks_on_miss(
        self,
        ctx: _Context,
        target_id: str,
        path: str,
    ) -> None:
        if ctx.attack_hits.get(target_id) is not False:
            return
        if not self._actor_has_studied_attacks(ctx.actor_id):
            return
        actor = self._entity(ctx.actor_id)
        effect = EffectInstance(
            effect_id=f"{ctx.actor_id}:studied_attacks:{target_id}",
            source_ref="SRD 5.2.1 Fighter Class Features: Level 13: Studied Attacks",
            source_action_id=STUDIED_ATTACKS_ACTION_ID,
            target_id=ctx.actor_id,
            applied_by=ctx.actor_id,
            condition=STUDIED_ATTACKS_CONDITION,
            passive_modifiers={
                "studied_attacks_advantage": True,
                "studied_attacks_target_id": target_id,
            },
            duration={
                "until": "end_of_next_turn",
                "remaining_ticks": self._studied_attacks_remaining_ticks(ctx.actor_id),
            },
            tick_on="self_turn_end",
            audit={"node_path": path, "missed_target_id": target_id},
        )
        effects = getattr(actor, "status_effects")
        effects[:] = [
            existing
            for existing in effects
            if existing.get("condition") != STUDIED_ATTACKS_CONDITION
            or not self._studied_attacks_effect_targets(existing, target_id)
        ]
        effects.append(effect.to_dict())
        ctx.result.state_changes.append(
            {
                "type": "passive_effect",
                "target_id": ctx.actor_id,
                "effect_id": effect.effect_id,
                "condition": effect.condition,
                "passive_modifiers": effect.passive_modifiers,
                "duration": effect.duration,
                "tick_on": effect.tick_on,
                "path": path,
                "source_action_id": STUDIED_ATTACKS_ACTION_ID,
            }
        )

    def _actor_has_studied_attacks(self, actor_id: str) -> bool:
        owner = self._resource_owner(actor_id)
        return isinstance(owner, Character) and has_fighter_feature(owner, level=13)

    def _studied_attacks_remaining_ticks(self, actor_id: str) -> int:
        current_actor_id = (
            self.state.encounter.current_combatant_id if self.state.encounter is not None else None
        )
        if current_actor_id is not None and self._entity_ids_match(current_actor_id, actor_id):
            return 2
        return 1

    def _studied_attacks_effect_targets(self, effect: dict[str, Any], target_id: str) -> bool:
        modifiers = effect.get("passive_modifiers", {})
        if not isinstance(modifiers, dict):
            return False
        studied_target_id = modifiers.get("studied_attacks_target_id")
        return studied_target_id is not None and self._entity_ids_match(
            str(studied_target_id),
            target_id,
        )

    def _apply_multiattack_defense_on_hit(
        self,
        ctx: _Context,
        target_id: str,
        path: str,
    ) -> None:
        if ctx.attack_hits.get(target_id) is not True:
            return
        protected_owner = self._resource_owner(target_id)
        if not isinstance(protected_owner, Character) or not has_multiattack_defense(
            protected_owner
        ):
            return
        attacker = self._entity(ctx.actor_id)
        turn_owner_id = ctx.actor_id
        if self.state.encounter is not None and self.state.encounter.current_combatant_id:
            turn_owner_id = self.state.encounter.current_combatant_id
        effect = EffectInstance(
            effect_id=f"{ctx.actor_id}:multiattack_defense:{target_id}",
            source_ref=(
                "SRD 5.2.1 Ranger Subclass: Hunter, Level 7: Defensive Tactics, Multiattack Defense"
            ),
            source_action_id=MULTIATTACK_DEFENSE_ACTION_ID,
            target_id=ctx.actor_id,
            applied_by=target_id,
            condition="multiattack_defense",
            passive_modifiers={
                "attack_roll_disadvantage_against_target": True,
                "multiattack_defense_target_id": target_id,
            },
            duration={"until": "end_of_current_turn", "turn_owner_id": turn_owner_id},
            tick_on="self_turn_end",
            audit={"node_path": path, "protected_target_id": target_id},
        )
        effects = getattr(attacker, "status_effects")
        effects[:] = [
            existing
            for existing in effects
            if existing.get("condition") != "multiattack_defense"
            or not self._multiattack_defense_effect_targets(existing, target_id)
        ]
        effects.append(effect.to_dict())
        ctx.result.state_changes.append(
            {
                "type": "passive_effect",
                "target_id": ctx.actor_id,
                "effect_id": effect.effect_id,
                "condition": effect.condition,
                "passive_modifiers": effect.passive_modifiers,
                "duration": effect.duration,
                "tick_on": effect.tick_on,
                "path": path,
                "source_action_id": MULTIATTACK_DEFENSE_ACTION_ID,
                "protected_target_id": target_id,
            }
        )

    def _multiattack_defense_effect_targets(
        self,
        effect: dict[str, Any],
        target_id: str,
    ) -> bool:
        modifiers = effect.get("passive_modifiers", {})
        if not isinstance(modifiers, dict):
            return False
        protected_target_id = modifiers.get("multiattack_defense_target_id")
        return protected_target_id is not None and self._entity_ids_match(
            str(protected_target_id),
            target_id,
        )

    def _attack_roll_disadvantage_sources(
        self,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> list[dict[str, Any]]:
        if action.action_type not in ATTACK_ACTION_TYPES:
            return []
        sources: list[dict[str, Any]] = []
        for effect in self._status_effects_for(actor):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            if modifiers.get("attack_roll_disadvantage") is not True:
                continue
            sources.append(
                {
                    "condition": effect.get("condition"),
                    "effect_id": effect.get("effect_id"),
                    "source_action_id": effect.get("source_action_id"),
                    "modifier": "attack_roll_disadvantage",
                }
            )
        return sources

    def _escape_the_horde_disadvantage_sources(
        self,
        action: ActionDefinition,
        target_id: str,
    ) -> list[dict[str, Any]]:
        if action.id != "srd.opportunity_attack":
            return []
        owner = self._resource_owner(target_id)
        if not isinstance(owner, Character) or not has_escape_the_horde(owner):
            return []
        return [
            {
                "source_action_id": ESCAPE_THE_HORDE_ACTION_ID,
                "modifier": "escape_the_horde_opportunity_attack_disadvantage",
                "target_id": target_id,
            }
        ]

    def _multiattack_defense_disadvantage_sources(
        self,
        actor: Character | Monster | Combatant,
        target_id: str,
    ) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        for effect in self._status_effects_for(actor):
            if effect.get("condition") != "multiattack_defense":
                continue
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            if modifiers.get("attack_roll_disadvantage_against_target") is not True:
                continue
            protected_target_id = modifiers.get("multiattack_defense_target_id")
            if protected_target_id is None or not self._entity_ids_match(
                str(protected_target_id),
                target_id,
            ):
                continue
            sources.append(
                {
                    "condition": effect.get("condition"),
                    "effect_id": effect.get("effect_id"),
                    "source_action_id": effect.get("source_action_id"),
                    "modifier": "multiattack_defense",
                    "target_id": str(protected_target_id),
                }
            )
        return sources

    def _attack_advantage_by_ability_sources(
        self,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
        *,
        ability: str,
    ) -> list[dict[str, Any]]:
        if action.action_type not in ATTACK_ACTION_TYPES:
            return []
        ability = ability.lower()
        sources: list[dict[str, Any]] = []
        for effect in self._status_effects_for(actor):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            abilities = modifiers.get("weapon_attack_advantage_by_ability", [])
            if isinstance(abilities, str):
                abilities = [abilities]
            if not isinstance(abilities, list):
                continue
            normalized = {str(entry).lower() for entry in abilities}
            if ability not in normalized:
                continue
            sources.append(
                {
                    "condition": effect.get("condition"),
                    "effect_id": effect.get("effect_id"),
                    "source_action_id": effect.get("source_action_id"),
                    "modifier": "weapon_attack_advantage_by_ability",
                    "ability": ability,
                }
            )
        return sources

    def _incoming_attack_advantage_sources(
        self,
        target: Character | Monster | Combatant,
    ) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        for effect in self._status_effects_for(target):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            if modifiers.get("incoming_attack_advantage") is not True:
                continue
            sources.append(
                {
                    "condition": effect.get("condition"),
                    "effect_id": effect.get("effect_id"),
                    "source_action_id": effect.get("source_action_id"),
                    "modifier": "incoming_attack_advantage",
                }
            )
        return sources

    def _spell_save_dc_bonus(
        self,
        actor: Character | Monster | Combatant,
        class_name: str,
    ) -> int:
        bonus = 0
        for effect in self._status_effects_for(actor):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            bonuses = modifiers.get("spell_save_dc_bonus")
            if not isinstance(bonuses, dict):
                continue
            value = bonuses.get(class_name)
            if isinstance(value, int) and not isinstance(value, bool):
                bonus += value
        return bonus

    def _spell_attack_bonus(
        self,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> tuple[int, list[dict[str, Any]]]:
        if action.action_type != "spell":
            return 0, []
        actor_classes = set(self._class_levels_for_entity(actor))
        bonus = 0
        sources: list[dict[str, Any]] = []
        for effect in self._status_effects_for(actor):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            bonuses = modifiers.get("spell_attack_bonus")
            if isinstance(bonuses, int) and not isinstance(bonuses, bool):
                bonus += bonuses
                sources.append(
                    {
                        "kind": "passive",
                        "effect_id": effect.get("effect_id"),
                        "source_action_id": effect.get("source_action_id"),
                        "modifier": "spell_attack_bonus",
                        "amount": bonuses,
                    }
                )
                continue
            if not isinstance(bonuses, dict):
                continue
            matching: list[tuple[str, int]] = []
            for class_name, value in bonuses.items():
                class_key = str(class_name).lower()
                if class_key not in actor_classes:
                    continue
                if isinstance(value, int) and not isinstance(value, bool):
                    matching.append((class_key, value))
            if not matching:
                continue
            amount = max(value for _, value in matching)
            bonus += amount
            sources.append(
                {
                    "kind": "passive",
                    "effect_id": effect.get("effect_id"),
                    "source_action_id": effect.get("source_action_id"),
                    "modifier": "spell_attack_bonus",
                    "classes": sorted(class_name for class_name, _ in matching),
                    "amount": amount,
                }
            )
        return bonus, sources

    def _spell_attack_advantage_sources(
        self,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> list[dict[str, Any]]:
        if action.action_type != "spell":
            return []
        actor_classes = set(self._class_levels_for_entity(actor))
        sources: list[dict[str, Any]] = []
        for effect in self._status_effects_for(actor):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            classes = modifiers.get("spell_attack_advantage_classes", [])
            if isinstance(classes, str):
                classes = [classes]
            if not isinstance(classes, list):
                continue
            matching_classes = sorted(actor_classes & {str(item) for item in classes})
            if not matching_classes:
                continue
            sources.append(
                {
                    "condition": effect.get("condition"),
                    "effect_id": effect.get("effect_id"),
                    "source_action_id": effect.get("source_action_id"),
                    "modifier": "spell_attack_advantage_classes",
                    "classes": matching_classes,
                }
            )
        return sources

    def _strong_wind_ranged_weapon_sources(
        self,
        actor: Character | Monster | Combatant,
        action: ActionDefinition,
    ) -> list[dict[str, Any]]:
        if action.action_type not in ATTACK_ACTION_TYPES:
            return []
        try:
            normal_range = int(action.range.get("normal_ft", 0))
        except (TypeError, ValueError):
            normal_range = 0
        if normal_range <= 5:
            return []
        sources: list[dict[str, Any]] = []
        for effect in self._status_effects_for(actor):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            if modifiers.get("ranged_weapon_attack_disadvantage") is True:
                sources.append(
                    {
                        "condition": effect.get("condition"),
                        "effect_id": effect.get("effect_id"),
                        "source_action_id": effect.get("source_action_id"),
                        "modifier": "ranged_weapon_attack_disadvantage",
                    }
                )
        return sources

    def _grappled_non_grappler_sources(
        self,
        actor: Character | Monster | Combatant,
        target: Character | Monster | Combatant,
        target_id: str,
    ) -> list[dict[str, Any]]:
        target_aliases = {target_id}
        target_entity_id = getattr(target, "entity_id", None)
        if isinstance(target_entity_id, str):
            target_aliases.add(target_entity_id)
        target_base_id = getattr(target, "id", None)
        if isinstance(target_base_id, str):
            target_aliases.add(target_base_id)
        sources: list[dict[str, Any]] = []
        for effect in self._status_effects_for(actor):
            if effect.get("condition") != "grappled":
                continue
            grappler_id = effect.get("applied_by")
            if not isinstance(grappler_id, str) or grappler_id in target_aliases:
                continue
            sources.append(
                {
                    "condition": "grappled",
                    "effect_id": effect.get("effect_id"),
                    "source_action_id": effect.get("source_action_id"),
                    "grappler_id": grappler_id,
                }
            )
        return sources

    def _saving_throw_status_advantage(
        self,
        target: Character | Monster | Combatant,
        ability: str,
        *,
        contexts: set[str] | None = None,
    ) -> tuple[str | None, list[dict[str, Any]]]:
        contexts = contexts or set()
        advantage_sources = self._passive_ability_advantage_sources(
            target,
            modifier="saving_throw_advantage_abilities",
            ability=ability,
        )
        advantage_sources.extend(
            self._passive_saving_throw_context_advantage_sources(
                target,
                ability=ability,
                contexts=contexts,
            )
        )
        disadvantage_sources: list[dict[str, Any]] = []
        disadvantage_sources.extend(
            self._passive_ability_advantage_sources(
                target,
                modifier="saving_throw_disadvantage_abilities",
                ability=ability,
            )
        )
        disadvantage_sources.extend(self._next_saving_throw_disadvantage_sources(target))
        danger_sense_sources = self._danger_sense_sources(target, ability)
        advantage_sources.extend(danger_sense_sources)
        if ability.lower() == "dex":
            disadvantage_sources.extend(self._condition_sources(target, {"restrained"}))
        return (
            _merge_advantage(
                None,
                "advantage" if advantage_sources else None,
                "disadvantage" if disadvantage_sources else None,
            ),
            [{"kind": "advantage", **source} for source in advantage_sources]
            + [{"kind": "disadvantage", **source} for source in disadvantage_sources],
        )

    def _next_saving_throw_disadvantage_sources(
        self,
        target: Character | Monster | Combatant,
    ) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        for effect in self._status_effects_for(target):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            if modifiers.get("next_saving_throw_disadvantage") is not True:
                continue
            sources.append(
                {
                    "condition": effect.get("condition"),
                    "effect_id": effect.get("effect_id"),
                    "source_action_id": effect.get("source_action_id"),
                    "modifier": "next_saving_throw_disadvantage",
                }
            )
        return sources

    def _expire_next_saving_throw_disadvantage(
        self,
        target_id: str,
        path: str,
    ) -> dict[str, Any] | None:
        removed: list[dict[str, Any]] = []
        for owner_type, owner_id, effects in self._target_effect_lists(target_id):
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
        if not removed:
            return None
        return {
            "type": "effect_expired",
            "target_id": target_id,
            "trigger": "next_saving_throw",
            "removed": removed,
            "path": path,
        }

    def _passive_saving_throw_context_advantage_sources(
        self,
        target: Character | Monster | Combatant,
        *,
        ability: str,
        contexts: set[str],
    ) -> list[dict[str, Any]]:
        if not contexts:
            return []
        normalized_contexts = {context.lower() for context in contexts}
        sources: list[dict[str, Any]] = []
        for effect in self._status_effects_for(target):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            entries = modifiers.get("saving_throw_advantage_contexts", [])
            if isinstance(entries, str):
                entries = [entries]
            if not isinstance(entries, list):
                continue
            matched = sorted(normalized_contexts & {str(entry).lower() for entry in entries})
            if not matched:
                continue
            sources.append(
                {
                    "effect_id": effect.get("effect_id"),
                    "source_action_id": effect.get("source_action_id"),
                    "modifier": "saving_throw_advantage_contexts",
                    "ability": ability.lower(),
                    "contexts": matched,
                }
            )
        return sources

    def _danger_sense_sources(
        self,
        target: Character | Monster | Combatant,
        ability: str,
    ) -> list[dict[str, Any]]:
        if ability.lower() != "dex":
            return []
        source = self._proficiency_source(target)
        if not isinstance(source, Character):
            return []
        if int(source.class_levels.get("barbarian", 0)) < 2:
            return []
        if self._condition_sources(target, {"incapacitated"}):
            return []
        return [{"modifier": "danger_sense", "ability": "dex"}]

    def _saving_throw_auto_failure_sources(
        self,
        target: Character | Monster | Combatant,
        ability: str,
        node: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        if ability.lower() in {"str", "dex"}:
            sources.extend(
                self._condition_sources(
                    target,
                    {"paralyzed", "petrified", "stunned", "unconscious"},
                )
            )
        node = node or {}
        creature_types = node.get("auto_fail_creature_types", [])
        if isinstance(creature_types, list):
            allowed = {str(creature_type).lower() for creature_type in creature_types}
            target_creature_type = self._creature_type_for(target).lower()
            if target_creature_type in allowed:
                sources.append(
                    {
                        "modifier": "auto_fail_creature_types",
                        "creature_type": target_creature_type,
                    }
                )
        return sources

    def _evasion_adjustment(
        self,
        target_id: str,
        amount: int,
        *,
        save_success: bool | None,
        save_ability: str | None,
    ) -> dict[str, Any] | None:
        if save_success is None or str(save_ability).lower() != "dex":
            return None
        target = self._entity(target_id)
        owner = self._proficiency_source(target)
        if not isinstance(owner, Character) or not evasion_applies(owner):
            return None
        incapacitated_sources = self._condition_sources(
            target,
            {"incapacitated", "paralyzed", "petrified", "stunned", "unconscious"},
        )
        if incapacitated_sources:
            return None
        amount_after = 0 if save_success else int(amount) // 2
        return {
            "source_action_id": EVASION_ACTION_ID,
            "save_ability": "dex",
            "saving_throw_success": save_success,
            "amount_before_evasion": int(amount),
            "amount_after_evasion": amount_after,
        }

    def _ability_check_status_advantage(
        self,
        actor: Character | Monster | Combatant,
        ability: str,
        *,
        skill: str | None = None,
        contexts: set[str] | None = None,
    ) -> tuple[str | None, list[dict[str, Any]]]:
        contexts = contexts or set()
        advantage_sources = self._passive_ability_advantage_sources(
            actor,
            modifier="ability_check_advantage_abilities",
            ability=ability,
        )
        advantage_sources.extend(
            self._passive_skill_advantage_sources(
                actor,
                ability=ability,
                skill=skill,
                contexts=contexts,
            )
        )
        champion = self._proficiency_source(actor)
        if isinstance(champion, Character) and remarkable_athlete_applies_to_check(
            champion,
            ability=ability,
            skill=skill,
        ):
            advantage_sources.append(
                {
                    "source_action_id": "srd.remarkable_athlete",
                    "modifier": "remarkable_athlete",
                    "class": "fighter",
                    "subclass": "champion",
                    "ability": ability,
                    "skill": skill,
                }
            )
        disadvantage_sources = self._condition_sources(actor, {"frightened", "poisoned"})
        disadvantage_sources.extend(
            self._passive_ability_advantage_sources(
                actor,
                modifier="ability_check_disadvantage_abilities",
                ability=ability,
            )
        )
        return (
            _merge_advantage(
                None,
                "advantage" if advantage_sources else None,
                "disadvantage" if disadvantage_sources else None,
            ),
            [{"kind": "advantage", **source} for source in advantage_sources]
            + [{"kind": "disadvantage", **source} for source in disadvantage_sources],
        )

    @staticmethod
    def _node_check_contexts(node: dict[str, Any]) -> set[str]:
        contexts = node.get("contexts", [])
        if isinstance(contexts, str):
            return {contexts}
        if isinstance(contexts, list):
            return {str(context) for context in contexts}
        return set()

    def _condition_sources(
        self,
        entity: Character | Monster | Combatant,
        conditions: set[str],
    ) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        suppressed = {
            condition
            for condition in conditions
            if self._condition_immunity_sources(entity, condition)
        }
        for effect in self._status_effects_for(entity):
            condition = effect.get("condition")
            if (
                isinstance(condition, str)
                and condition in conditions
                and condition not in suppressed
            ):
                sources.append(
                    {
                        "condition": condition,
                        "effect_id": effect.get("effect_id"),
                        "source_action_id": effect.get("source_action_id"),
                    }
                )
        return sources

    def _target_auto_critical_sources(
        self, target: Character | Monster | Combatant, distance_ft: int | None
    ) -> list[dict[str, Any]]:
        if distance_ft is None or distance_ft > 5:
            return []
        return self._condition_sources(target, {"paralyzed", "unconscious"})

    def _critical_hit_threshold(
        self,
        actor_id: str,
        action: ActionDefinition,
    ) -> tuple[int, list[dict[str, Any]]]:
        if action.action_type not in {"weapon_attack", "unarmed_attack"}:
            return 20, []
        owner = self._resource_owner(actor_id)
        if not isinstance(owner, Character):
            return 20, []
        if has_fighter_champion_feature(owner, level=15):
            return 18, [
                {
                    "source_action_id": "srd.superior_critical",
                    "class": "fighter",
                    "subclass": "champion",
                    "feature": "Superior Critical",
                }
            ]
        if has_fighter_champion_feature(owner, level=3):
            return 19, [
                {
                    "source_action_id": "srd.improved_critical",
                    "class": "fighter",
                    "subclass": "champion",
                    "feature": "Improved Critical",
                }
            ]
        return 20, []

    def _combat_distance(
        self,
        actor: Character | Monster | Combatant,
        target: Character | Monster | Combatant,
    ) -> int | None:
        if not isinstance(actor, Combatant) or not isinstance(target, Combatant):
            return None
        if (
            self.state.encounter is None
            or self.state.encounter.tactical_graph is None
            or actor.position_node_id is None
            or target.position_node_id is None
        ):
            return None
        graph = TacticalGraph.from_dict(self.state.encounter.tactical_graph)
        return graph.shortest_distance(actor.position_node_id, target.position_node_id)

    def _active_conjure_minor_elementals_effect(self, actor_id: str) -> dict[str, Any] | None:
        for effect in reversed(self.state.world.active_effects):
            applied_by = effect.get("applied_by")
            if (
                effect.get("source_action_id") == CONJURE_MINOR_ELEMENTALS_ACTION_ID
                and effect.get("effect_type") == CONJURE_MINOR_ELEMENTALS_EFFECT_TYPE
                and isinstance(applied_by, str)
                and self._entity_ids_match(applied_by, actor_id)
            ):
                return effect
        return None

    def _conjure_minor_elementals_target_in_emanation(
        self,
        actor_id: str,
        target_id: str,
        effect: dict[str, Any],
    ) -> bool:
        distance = self._combat_distance(self._entity(actor_id), self._entity(target_id))
        if distance is None:
            return False
        radius = CONJURE_MINOR_ELEMENTALS_RADIUS_FT
        scope = effect.get("scope", {})
        if isinstance(scope, dict):
            radius = int(scope.get("radius_ft", radius))
        return distance <= radius

    def _clear_existing_concentration_if_needed(
        self, ctx: _Context, concentration: bool, path: str
    ) -> None:
        if not concentration or ctx.concentration_cleared:
            return
        removed = self._clear_existing_concentration(ctx.actor_id)
        ctx.concentration_cleared = True
        if removed:
            ctx.result.state_changes.append(
                {
                    "type": "concentration_cleared",
                    "actor_id": ctx.actor_id,
                    "removed": removed,
                    "path": path,
                }
            )

    def _resource_delta_amount(self, ctx: _Context, node: dict[str, Any]) -> int:
        if "delta" in node:
            return int(node["delta"])
        delta_from = node.get("delta_from")
        if delta_from == "speed":
            actor = self._entity(ctx.actor_id)
            return self._effective_speed(actor)
        raise AutomationError(f"unsupported resource_delta delta_from: {delta_from}")

    def _validate_resource_delta_caps(self, action: ActionDefinition, actor_id: str) -> None:
        for node in self._automation_nodes(action.automation):
            if node.get("type") != "resource_delta" or "max_from" not in node:
                continue
            delta = int(node.get("delta", 0))
            resource = str(node["resource"])
            actor = self._resource_owner(actor_id)
            before = self._get_resource(actor, resource)
            maximum = self._resource_delta_cap(actor_id, node)
            if maximum is not None and before + delta > maximum:
                raise AutomationError(f"resource {resource} would exceed maximum {maximum}")

    def _validate_cunning_strike_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        targets: list[str],
        params: dict[str, Any],
    ) -> None:
        effects = self._cunning_strike_choices(params)
        if not effects:
            return
        if params.get("use_sneak_attack") is not True:
            raise AutomationError("Cunning Strike requires Sneak Attack")
        if action.action_type != "weapon_attack" or not self._action_qualifies_for_sneak_attack(
            action
        ):
            raise AutomationError("Cunning Strike requires a Sneak Attack weapon attack")
        actor = self._resource_owner(actor_id)
        rogue_level = int(actor.class_levels.get("rogue", 0)) if isinstance(actor, Character) else 0
        if not isinstance(actor, Character) or rogue_level < 5:
            raise AutomationError("Cunning Strike requires Rogue level 5")
        if len(effects) > 1 and rogue_level < 11:
            raise AutomationError("Improved Cunning Strike requires Rogue level 11")
        if ((rogue_level + 1) // 2) <= len(effects):
            raise AutomationError("Cunning Strike requires enough Sneak Attack dice")
        if "poison" in effects and not self._has_item_on_person(actor, POISONERS_KIT_ITEM_ID):
            raise AutomationError("Cunning Strike Poison requires a Poisoner's Kit")
        if "trip" in effects:
            for target_id in targets:
                if not self._target_large_or_smaller(target_id):
                    raise AutomationError("Cunning Strike Trip requires a Large or smaller target")
        if "withdraw" in effects:
            destination = self._cunning_strike_withdraw_destination(params)
            if destination is None:
                raise AutomationError("Cunning Strike Withdraw requires a destination position")
            self._cunning_strike_withdraw_plan(actor_id, destination)
        if "stealth_attack" in effects:
            if not has_rogue_thief_feature(actor, level=9):
                raise AutomationError("Supreme Sneak Stealth Attack requires Rogue Thief level 9")
            if not self._hide_invisible_effect_entries(actor_id):
                raise AutomationError(
                    "Supreme Sneak Stealth Attack requires the Hide action's condition"
                )
            if self._cunning_strike_stealth_attack_cover(params) is None:
                raise AutomationError(
                    "Supreme Sneak Stealth Attack requires end-turn cover of "
                    "Three-Quarters Cover or Total Cover"
                )

    def _validate_brutal_strike_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        targets: list[str],
        params: dict[str, Any],
    ) -> None:
        if not self._brutal_strike_requested(params):
            return
        effects = self._brutal_strike_effects(params)
        if not effects:
            raise AutomationError("Brutal Strike requires an effect choice")
        if len(targets) != 1:
            raise AutomationError("Brutal Strike requires exactly one target")
        target_id = targets[0]
        attack_node = self._first_attack_roll_node(action)
        if attack_node is None:
            raise AutomationError("Brutal Strike requires an attack roll")
        ability = str(attack_node.get("ability", "str")).lower()
        actor = self._entity(actor_id)
        target = self._entity(target_id)
        distance_ft = self._combat_distance(actor, target)
        node_advantage = _advantage_value(attack_node.get("advantage"))
        status_advantage, status_sources = self._attack_status_advantage(
            actor,
            target,
            distance_ft,
            actor_id=actor_id,
            target_id=target_id,
            action=action,
            ability=ability,
            node_advantage=node_advantage,
        )
        effective_node_advantage = (
            None
            if any(source.get("kind") == "advantage_blocked" for source in status_sources)
            else node_advantage
        )
        advantage = _merge_advantage(effective_node_advantage, status_advantage)
        self._validate_brutal_strike_attack_context(
            action,
            actor_id,
            target_id,
            attack_node,
            ability,
            params=params,
            node_advantage=effective_node_advantage,
            status_advantage=status_advantage,
            status_sources=status_sources,
            advantage=advantage,
        )
        if "forceful_blow" in effects:
            destination = self._brutal_strike_forceful_destination(params, target_id=target_id)
            if destination is None:
                raise AutomationError("Brutal Strike Forceful Blow requires a destination position")
            self._brutal_strike_forceful_plan(actor_id, target_id, destination)
            follow_destination = self._brutal_strike_forceful_follow_destination(
                params,
                target_id=target_id,
            )
            if follow_destination is not None:
                self._brutal_strike_forceful_follow_plan(
                    actor_id,
                    target_id,
                    follow_destination,
                    target_position=destination,
                )

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
        effects = AutomationExecutor._brutal_strike_effects(params)
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
            if effect not in BRUTAL_STRIKE_EFFECTS:
                raise AutomationError(f"unsupported Brutal Strike effect: {effect}")
            if effect in effects:
                raise AutomationError(f"duplicate Brutal Strike effect: {effect}")
            effects.append(effect)
        if len(effects) > 2:
            raise AutomationError("Improved Brutal Strike allows at most two effects")
        return effects

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

    def _first_attack_roll_node(self, action: ActionDefinition) -> dict[str, Any] | None:
        return next(
            (
                node
                for node in self._automation_nodes(action.automation)
                if node.get("type") == "attack_roll"
            ),
            None,
        )

    def _brutal_strike_forceful_plan(
        self,
        actor_id: str,
        target_id: str,
        destination: str,
    ) -> dict[str, Any]:
        actor = self._entity(actor_id)
        target = self._entity(target_id)
        if not isinstance(actor, Combatant) or not isinstance(target, Combatant):
            raise AutomationError("Brutal Strike Forceful Blow requires combatants")
        if self.state.encounter is None or self.state.encounter.tactical_graph is None:
            raise AutomationError("Brutal Strike Forceful Blow requires a combat tactical graph")
        if actor.position_node_id is None or target.position_node_id is None:
            raise AutomationError("Brutal Strike Forceful Blow requires current positions")
        graph = TacticalGraph.from_dict(self.state.encounter.tactical_graph)
        if destination not in graph.nodes:
            raise AutomationError("Brutal Strike Forceful Blow destination position does not exist")
        movement_distance = graph.shortest_distance(target.position_node_id, destination)
        if movement_distance is None:
            raise AutomationError(
                "Brutal Strike Forceful Blow destination position is not reachable"
            )
        if int(movement_distance) > 15:
            raise AutomationError("Brutal Strike Forceful Blow cannot exceed 15 feet")
        before_distance = graph.shortest_distance(actor.position_node_id, target.position_node_id)
        after_distance = graph.shortest_distance(actor.position_node_id, destination)
        if (
            before_distance is not None
            and after_distance is not None
            and after_distance <= before_distance
        ):
            raise AutomationError(
                "Brutal Strike Forceful Blow destination must be away from the Barbarian"
            )
        return {
            "target": target,
            "movement_distance": int(movement_distance),
            "distance_from_actor_before": before_distance,
            "distance_from_actor_after": after_distance,
        }

    def _brutal_strike_forceful_follow_plan(
        self,
        actor_id: str,
        target_id: str,
        destination: str,
        *,
        target_position: str | None = None,
    ) -> dict[str, Any]:
        actor = self._entity(actor_id)
        target = self._entity(target_id)
        if not isinstance(actor, Combatant) or not isinstance(target, Combatant):
            raise AutomationError("Brutal Strike Forceful Blow follow movement requires combatants")
        if self.state.encounter is None or self.state.encounter.tactical_graph is None:
            raise AutomationError(
                "Brutal Strike Forceful Blow follow movement requires a combat tactical graph"
            )
        if actor.position_node_id is None or target.position_node_id is None:
            raise AutomationError("Brutal Strike Forceful Blow follow movement requires positions")
        graph = TacticalGraph.from_dict(self.state.encounter.tactical_graph)
        if destination not in graph.nodes:
            raise AutomationError(
                "Brutal Strike Forceful Blow follow destination position does not exist"
            )
        target_position = target_position or target.position_node_id
        movement_cost = graph.shortest_distance(
            actor.position_node_id,
            destination,
            movement_cost=True,
        )
        if movement_cost is None:
            raise AutomationError(
                "Brutal Strike Forceful Blow follow destination position is not reachable"
            )
        movement_limit = self._effective_speed(actor) // 2
        if int(movement_cost) > movement_limit:
            raise AutomationError(
                "Brutal Strike Forceful Blow follow movement cannot exceed half Speed"
            )
        before_distance = graph.shortest_distance(actor.position_node_id, target_position)
        after_distance = graph.shortest_distance(destination, target_position)
        if (
            before_distance is not None
            and after_distance is not None
            and after_distance >= before_distance
        ):
            raise AutomationError(
                "Brutal Strike Forceful Blow follow destination must be toward the target"
            )
        return {
            "actor": actor,
            "movement_cost": int(movement_cost),
            "movement_limit": int(movement_limit),
            "distance_to_target_before": before_distance,
            "distance_to_target_after": after_distance,
        }

    def _validate_fast_hands_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
    ) -> None:
        if action.id != FAST_HANDS_SLEIGHT_OF_HAND_ACTION_ID:
            return
        actor = self._resource_owner(actor_id)
        if not isinstance(actor, Character) or not has_rogue_thief_feature(actor, level=3):
            raise AutomationError("Fast Hands requires Rogue Thief level 3")
        tool_proficiencies = {str(tool_id) for tool_id in actor.tool_proficiencies}
        if not {THIEVES_TOOLS_ITEM_ID, THIEVES_TOOLS_ITEM_ID.removeprefix("srd.")} & (
            tool_proficiencies
        ):
            raise AutomationError("Fast Hands Sleight of Hand requires Thieves' Tools proficiency")

    @staticmethod
    def _validate_allowed_damage_type_param(
        action: ActionDefinition,
        params: dict[str, Any],
    ) -> None:
        allowed_raw = action.properties.get("allowed_damage_types")
        if not isinstance(allowed_raw, list) or not allowed_raw:
            return
        allowed = [str(damage_type) for damage_type in allowed_raw]
        param_name = str(action.properties.get("damage_type_param", "damage_type"))
        raw = params.get(param_name)
        if raw is None or raw == "":
            raise AutomationError(f"missing required parameter {param_name}")
        if isinstance(raw, (dict, list)):
            raise AutomationError(f"parameter {param_name} must be a scalar")
        normalized = str(raw).casefold().strip()
        if normalized not in allowed:
            raise AutomationError(f"{param_name} must be one of: {', '.join(allowed)}")
        params[param_name] = normalized

    def _validate_conjure_minor_elementals_damage_type(
        self,
        action: ActionDefinition,
        actor_id: str,
        targets: list[str],
        params: dict[str, Any],
    ) -> None:
        if self._first_attack_roll_node(action) is None:
            return
        effect = self._active_conjure_minor_elementals_effect(actor_id)
        if effect is None:
            self._conjure_minor_elementals_damage_type(params, required=False)
            return
        requires_choice = any(
            self._conjure_minor_elementals_target_in_emanation(actor_id, target_id, effect)
            for target_id in targets
        )
        self._conjure_minor_elementals_damage_type(params, required=requires_choice)

    @staticmethod
    def _conjure_minor_elementals_damage_type(
        params: dict[str, Any],
        *,
        required: bool,
    ) -> str | None:
        raw = params.get(CONJURE_MINOR_ELEMENTALS_DAMAGE_TYPE_PARAM)
        if raw in (None, ""):
            if required:
                raise AutomationError(
                    f"missing required parameter {CONJURE_MINOR_ELEMENTALS_DAMAGE_TYPE_PARAM}"
                )
            return None
        if isinstance(raw, (dict, list)):
            raise AutomationError(
                f"parameter {CONJURE_MINOR_ELEMENTALS_DAMAGE_TYPE_PARAM} must be a scalar"
            )
        normalized = str(raw).casefold().strip()
        if normalized not in CONJURE_MINOR_ELEMENTALS_DAMAGE_TYPES:
            expected = ", ".join(sorted(CONJURE_MINOR_ELEMENTALS_DAMAGE_TYPES))
            raise AutomationError(
                f"{CONJURE_MINOR_ELEMENTALS_DAMAGE_TYPE_PARAM} must be one of: {expected}"
            )
        params[CONJURE_MINOR_ELEMENTALS_DAMAGE_TYPE_PARAM] = normalized
        return normalized

    @staticmethod
    def _validate_allowed_creature_types_param(
        action: ActionDefinition,
        params: dict[str, Any],
    ) -> None:
        allowed_raw = action.properties.get("allowed_creature_types")
        if not isinstance(allowed_raw, list) or not allowed_raw:
            return
        allowed = [str(creature_type) for creature_type in allowed_raw]
        param_name = str(action.properties.get("creature_types_param", "creature_types"))
        raw = params.get(param_name)
        if raw is None or raw == "":
            raise AutomationError(f"missing required parameter {param_name}")
        if isinstance(raw, dict):
            raise AutomationError(f"parameter {param_name} must be a list")
        raw_values = raw if isinstance(raw, list) else [raw]
        if not raw_values:
            raise AutomationError(f"parameter {param_name} must not be empty")
        normalized_values: list[str] = []
        for value in raw_values:
            if isinstance(value, (dict, list)):
                raise AutomationError(f"parameter {param_name} entries must be scalars")
            normalized = str(value).casefold().strip()
            if normalized not in allowed:
                raise AutomationError(f"{param_name} must contain only: {', '.join(allowed)}")
            if normalized not in normalized_values:
                normalized_values.append(normalized)
        params[param_name] = normalized_values

    @staticmethod
    def _validate_allowed_list_params(
        action: ActionDefinition,
        params: dict[str, Any],
    ) -> None:
        specs = action.properties.get("allowed_list_params")
        if not isinstance(specs, dict):
            return
        required_counts = action.properties.get("required_list_param_counts")
        if not isinstance(required_counts, dict):
            required_counts = {}
        for param_name, allowed_raw in specs.items():
            param = str(param_name)
            if not isinstance(allowed_raw, list) or not allowed_raw:
                continue
            allowed = [str(value) for value in allowed_raw]
            raw = params.get(param)
            if raw is None or raw == "":
                raise AutomationError(f"missing required parameter {param}")
            if isinstance(raw, dict):
                raise AutomationError(f"parameter {param} must be a list")
            raw_values = raw if isinstance(raw, list) else [raw]
            if not raw_values:
                raise AutomationError(f"parameter {param} must not be empty")
            normalized_values: list[str] = []
            for value in raw_values:
                if isinstance(value, (dict, list)):
                    raise AutomationError(f"parameter {param} entries must be scalars")
                normalized = str(value).casefold().strip()
                if normalized not in allowed:
                    raise AutomationError(f"{param} must contain only: {', '.join(allowed)}")
                if normalized not in normalized_values:
                    normalized_values.append(normalized)
            expected_count = required_counts.get(param)
            if expected_count is not None and len(normalized_values) != int(expected_count):
                raise AutomationError(f"{param} must contain exactly {int(expected_count)} choices")
            params[param] = normalized_values

    @staticmethod
    def _validate_fire_shield_type_param(
        action: ActionDefinition,
        params: dict[str, Any],
    ) -> None:
        allowed_raw = action.properties.get("allowed_fire_shield_types")
        if not isinstance(allowed_raw, list) or not allowed_raw:
            return
        allowed = [str(shield_type).casefold().strip() for shield_type in allowed_raw]
        param_name = str(action.properties.get("fire_shield_type_param", "fire_shield_type"))
        raw = params.get(param_name)
        if raw is None or raw == "":
            raise AutomationError(f"missing required parameter {param_name}")
        if isinstance(raw, (dict, list)):
            raise AutomationError(f"parameter {param_name} must be a scalar")
        shield_type = str(raw).casefold().strip()
        if shield_type not in allowed:
            raise AutomationError(f"{param_name} must be one of: {', '.join(allowed)}")
        shield_type_effects = {
            "warm": {
                "resistance": "cold",
                "retaliation_damage_type": "fire",
            },
            "chill": {
                "resistance": "fire",
                "retaliation_damage_type": "cold",
            },
        }
        resolved = shield_type_effects.get(shield_type)
        if resolved is None:
            raise AutomationError(f"unsupported {param_name}: {shield_type}")
        params[param_name] = shield_type
        params["fire_shield_resistance_type"] = resolved["resistance"]
        params["fire_shield_retaliation_damage_type"] = resolved["retaliation_damage_type"]

    @staticmethod
    def _validate_greater_restoration_preconditions(
        action: ActionDefinition,
        params: dict[str, Any],
    ) -> None:
        for node in action.automation:
            if node.get("type") != "greater_restoration":
                continue
            choice_param = str(node.get("choice_param", "greater_restoration_choice"))
            if choice_param not in params:
                raise AutomationError(f"missing required parameter {choice_param}")
            choice = str(params[choice_param])
            allowed_choices = {str(item) for item in node.get("choices", [])}
            if choice not in allowed_choices or choice not in GREATER_RESTORATION_CHOICES:
                expected = ", ".join(sorted(allowed_choices & GREATER_RESTORATION_CHOICES))
                raise AutomationError(
                    f"unsupported Greater Restoration choice {choice}; choose {expected}"
                )

    def _validate_restoring_touch_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        targets: list[str],
        params: dict[str, Any],
    ) -> None:
        node = self._restoring_touch_node(action)
        if node is None:
            return
        self._restoring_touch_plan(action, actor_id, targets, params, node)

    def _restoring_touch_plan(
        self,
        action: ActionDefinition,
        actor_id: str,
        targets: list[str],
        params: dict[str, Any],
        node: dict[str, Any],
    ) -> tuple[list[str], int, int, int]:
        points_param = str(node.get("points_param", "lay_on_hands_points"))
        conditions_param = str(node.get("conditions_param", "restoring_touch_conditions"))
        total_points = self._positive_param_int(params, points_param)
        conditions = self._restoring_touch_conditions(node, params, conditions_param)
        point_cost = int(node.get("point_cost_per_condition", RESTORING_TOUCH_CONDITION_POINT_COST))
        condition_cost = point_cost * len(conditions)
        if total_points < condition_cost:
            raise AutomationError("Restoring Touch requires 5 Lay On Hands points per condition")
        if len(targets) != 1:
            raise AutomationError("Restoring Touch requires exactly one target")
        target_id = targets[0]
        try:
            self._entity(target_id)
        except KeyError as exc:
            raise AutomationError(f"unknown target {target_id}") from exc
        missing = [
            condition
            for condition in conditions
            if not self._target_has_condition(target_id, condition)
        ]
        if missing:
            raise AutomationError(
                "Restoring Touch target lacks condition(s): " + ", ".join(missing)
            )
        params[points_param] = total_points
        params[conditions_param] = conditions
        return conditions, total_points, condition_cost, total_points - condition_cost

    def _restoring_touch_conditions(
        self,
        node: dict[str, Any],
        params: dict[str, Any],
        param_name: str,
    ) -> list[str]:
        allowed_raw = node.get("allowed_conditions", sorted(RESTORING_TOUCH_ALLOWED_CONDITIONS))
        allowed = {
            str(condition).casefold().strip()
            for condition in allowed_raw
            if isinstance(condition, str)
        } & RESTORING_TOUCH_ALLOWED_CONDITIONS
        if not allowed:
            raise AutomationError("Restoring Touch has no supported conditions")
        raw = params.get(param_name)
        if raw is None:
            raise AutomationError(f"missing required parameter {param_name}")
        if isinstance(raw, str):
            raw_values: list[Any] = [
                value.strip() for value in re.split(r"[,\s]+", raw) if value.strip()
            ]
        elif isinstance(raw, list):
            raw_values = raw
        else:
            raise AutomationError(f"parameter {param_name} must be a list of conditions")
        if not raw_values:
            raise AutomationError(f"parameter {param_name} must include at least one condition")
        conditions: list[str] = []
        for value in raw_values:
            if isinstance(value, (bool, dict, list)):
                raise AutomationError(f"parameter {param_name} entries must be conditions")
            condition = str(value).casefold().strip()
            if condition not in allowed:
                expected = ", ".join(sorted(allowed))
                raise AutomationError(f"{param_name} must contain only: {expected}")
            if condition in conditions:
                raise AutomationError("Restoring Touch conditions must not repeat")
            conditions.append(condition)
        return conditions

    def _target_has_condition(self, target_id: str, condition: str) -> bool:
        return any(
            effect.get("condition") == condition
            for _, _, effects in self._target_effect_lists(target_id)
            for effect in effects
        )

    def _restoring_touch_node(self, action: ActionDefinition) -> dict[str, Any] | None:
        return next(
            (
                node
                for node in self._automation_nodes(action.automation)
                if node.get("type") == "restoring_touch"
            ),
            None,
        )

    def _validate_heightened_focus_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        targets: list[str],
        params: dict[str, Any],
    ) -> None:
        flurry_requested = action.id == FLURRY_OF_BLOWS_ACTION_ID and (
            self._heightened_flurry_requested(targets, params)
        )
        companion_id = self._heightened_focus_companion_id(params)
        if not flurry_requested and companion_id is None:
            return
        if companion_id is not None and action.id != STEP_OF_THE_WIND_FOCUS_ACTION_ID:
            raise AutomationError("Heightened Focus companion requires Step of the Wind: Focus")
        owner = self._resource_owner(actor_id)
        has_heightened_focus = isinstance(owner, Character) and has_monk_feature(owner, level=10)
        if flurry_requested and not has_heightened_focus:
            raise AutomationError("Heightened Focus requires Monk level 10")
        if action.id == STEP_OF_THE_WIND_FOCUS_ACTION_ID and companion_id is not None:
            if not has_heightened_focus:
                raise AutomationError("Heightened Focus requires Monk level 10")
            self._heightened_focus_companion_plan(actor_id, companion_id, params)

    @staticmethod
    def _heightened_flurry_requested(targets: list[str], params: dict[str, Any]) -> bool:
        if len(targets) > 2:
            return True
        selected = params.get("strike_3_target")
        return selected not in (None, "", False)

    @staticmethod
    def _heightened_focus_companion_id(params: dict[str, Any]) -> str | None:
        selected = params.get(
            "heightened_focus_companion_id",
            params.get("step_of_the_wind_companion_id"),
        )
        if selected in (None, "", False):
            return None
        return str(selected)

    def _heightened_focus_companion_plan(
        self,
        actor_id: str,
        companion_id: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        if self._entity_ids_match(actor_id, companion_id):
            raise AutomationError("Heightened Focus companion cannot be self")
        if not self._target_willing(params, companion_id):
            raise AutomationError("Heightened Focus companion must be willing")
        actor = self._entity(actor_id)
        companion = self._entity(companion_id)
        if not isinstance(actor, Combatant) or not isinstance(companion, Combatant):
            raise AutomationError("Heightened Focus companion requires combatants")
        if self.state.encounter is None or self.state.encounter.tactical_graph is None:
            raise AutomationError("Heightened Focus companion requires a combat tactical graph")
        if actor.position_node_id is None or companion.position_node_id is None:
            raise AutomationError("Heightened Focus companion requires current positions")
        if not self._target_large_or_smaller(companion_id):
            raise AutomationError("Heightened Focus companion must be Large or smaller")
        graph = TacticalGraph.from_dict(self.state.encounter.tactical_graph)
        distance = graph.shortest_distance(actor.position_node_id, companion.position_node_id)
        if distance is None or int(distance) > 5:
            raise AutomationError("Heightened Focus companion must be within 5 feet")
        return {"actor": actor, "companion": companion, "distance_ft": int(distance)}

    def _validate_fleet_step_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        params: dict[str, Any],
    ) -> None:
        if not self._fleet_step_requested(params):
            return
        if action.id not in STEP_OF_THE_WIND_ACTION_IDS:
            raise AutomationError("Fleet Step can only be used with Step of the Wind")
        owner = self._resource_owner(actor_id)
        if not isinstance(owner, Character) or not has_monk_open_hand_feature(owner, level=11):
            raise AutomationError("Fleet Step requires Open Hand Monk level 11")
        if self._current_fleet_step_window(actor_id) is None:
            raise AutomationError(
                "Fleet Step requires an immediately preceding non-Step Bonus Action"
            )

    @staticmethod
    def _fleet_step_requested(params: dict[str, Any]) -> bool:
        return params.get("use_fleet_step") is True or params.get("fleet_step") is True

    def _fleet_step_waives_bonus_action(
        self,
        action: ActionDefinition,
        actor_id: str,
        params: dict[str, Any],
    ) -> bool:
        return (
            action.action_economy == "bonus_action"
            and action.id in STEP_OF_THE_WIND_ACTION_IDS
            and self._fleet_step_requested(params)
            and self._current_fleet_step_window(actor_id) is not None
        )

    def _current_fleet_step_window(self, actor_id: str) -> dict[str, Any] | None:
        actor = self._entity(actor_id)
        for effect in self._status_effects_for(actor):
            if (
                effect.get("condition") == FLEET_STEP_CONDITION
                and effect.get("source_action_id") == FLEET_STEP_ACTION_ID
            ):
                return effect
        return None

    def _fleet_step_effect_containers(self, actor_id: str) -> list[list[dict[str, Any]]]:
        containers: list[list[dict[str, Any]]] = [getattr(self._entity(actor_id), "status_effects")]
        entity = self._entity(actor_id)
        if isinstance(entity, Combatant) and entity.entity_id in self.state.characters:
            containers.append(self.state.characters[entity.entity_id].status_effects)
        if isinstance(entity, Combatant) and entity.entity_id in self.state.monsters:
            containers.append(self.state.monsters[entity.entity_id].status_effects)
        return containers

    def _clear_fleet_step_window(self, actor_id: str) -> dict[str, Any] | None:
        removed: dict[str, Any] | None = None
        for effects in self._fleet_step_effect_containers(actor_id):
            kept: list[dict[str, Any]] = []
            for effect in effects:
                if (
                    effect.get("condition") == FLEET_STEP_CONDITION
                    and effect.get("source_action_id") == FLEET_STEP_ACTION_ID
                ):
                    if removed is None:
                        removed = effect
                    continue
                kept.append(effect)
            effects[:] = kept
        return removed

    def _record_fleet_step_window(self, ctx: _Context) -> None:
        try:
            owner = self._resource_owner(ctx.actor_id)
        except KeyError:
            return
        if not isinstance(owner, Character) or not has_monk_open_hand_feature(owner, level=11):
            return
        self._clear_fleet_step_window(ctx.actor_id)
        if ctx.action.action_economy != "bonus_action":
            return
        if ctx.action.id in STEP_OF_THE_WIND_ACTION_IDS:
            return
        actor = self._entity(ctx.actor_id)
        effect = EffectInstance(
            effect_id=self._effect_id(ctx.actor_id, FLEET_STEP_CONDITION),
            source_ref="SRD 5.2.1 Monk Subclass: Warrior of the Open Hand, Level 11: Fleet Step",
            source_action_id=FLEET_STEP_ACTION_ID,
            target_id=ctx.actor_id,
            applied_by=ctx.actor_id,
            condition=FLEET_STEP_CONDITION,
            duration={"until": "end_of_current_turn"},
            tick_on="self_turn_end",
            stacking_policy="replace",
            audit={"trigger_action_id": ctx.action.id},
        )
        getattr(actor, "status_effects").append(effect.to_dict())
        ctx.result.state_changes.append(
            {
                "type": "fleet_step_window",
                "actor_id": ctx.actor_id,
                "effect_id": effect.effect_id,
                "condition": effect.condition,
                "source_action_id": FLEET_STEP_ACTION_ID,
                "trigger_action_id": ctx.action.id,
                "duration": effect.duration,
                "tick_on": effect.tick_on,
            }
        )

    def _validate_open_hand_technique_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        targets: list[str],
        params: dict[str, Any],
    ) -> None:
        if not self._has_open_hand_technique_params(params):
            return
        if action.id != FLURRY_OF_BLOWS_ACTION_ID:
            raise AutomationError("Open Hand Technique requires Flurry of Blows")
        actor = self._resource_owner(actor_id)
        if not isinstance(actor, Character) or not has_monk_open_hand_feature(actor, level=3):
            raise AutomationError("Open Hand Technique requires Monk Open Hand level 3")
        max_strikes = self._flurry_strike_count(actor_id)
        targets_by_strike = self._flurry_targets_by_strike(
            targets,
            params,
            max_strikes=max_strikes,
        )
        valid_targets = {
            target_id
            for strike_targets in targets_by_strike.values()
            for target_id in strike_targets
        }
        self._validate_open_hand_param_keys(
            params,
            targets_by_strike,
            valid_targets,
            max_strikes=max_strikes,
        )
        for strike_index, strike_targets in targets_by_strike.items():
            for target_id in strike_targets:
                effect = self._open_hand_technique_choice(
                    params,
                    target_id=target_id,
                    strike_index=strike_index,
                )
                if effect != "push":
                    continue
                destination = self._open_hand_push_destination(
                    params,
                    target_id=target_id,
                    strike_index=strike_index,
                )
                if destination is None:
                    raise AutomationError(
                        "Open Hand Technique Push requires a destination position"
                    )
                self._open_hand_push_plan(actor_id, target_id, destination)

    @staticmethod
    def _has_open_hand_technique_params(params: dict[str, Any]) -> bool:
        return any(
            key in params
            for key in {
                "open_hand_technique",
                "open_hand_technique_effect",
                "open_hand_technique_by_target",
                "open_hand_technique_by_strike",
                "open_hand_push_to_position_node_id",
                "open_hand_push_to_position_node_id_by_target",
                "open_hand_push_to_position_node_id_by_strike",
            }
        )

    def _validate_open_hand_param_keys(
        self,
        params: dict[str, Any],
        targets_by_strike: dict[int, list[str]],
        valid_targets: set[str],
        *,
        max_strikes: int,
    ) -> None:
        by_target = params.get("open_hand_technique_by_target")
        if isinstance(by_target, dict):
            for target_id, raw_effect in by_target.items():
                if str(target_id) not in valid_targets:
                    raise AutomationError(
                        "Open Hand Technique target must be a Flurry of Blows target"
                    )
                self._normalize_open_hand_technique_effect(raw_effect)
        by_strike = params.get("open_hand_technique_by_strike")
        if isinstance(by_strike, dict):
            for raw_index, raw_effect in by_strike.items():
                strike_index = self._open_hand_strike_index(raw_index, max_strikes=max_strikes)
                if strike_index not in targets_by_strike:
                    raise AutomationError(self._open_hand_strike_error(max_strikes))
                self._normalize_open_hand_technique_effect(raw_effect)
        for param_name in (
            "open_hand_push_to_position_node_id_by_target",
            "open_hand_push_to_position_node_id_by_strike",
        ):
            if param_name in params and not isinstance(params[param_name], dict):
                raise AutomationError(f"parameter {param_name} must be a map")
        destinations_by_target = params.get("open_hand_push_to_position_node_id_by_target")
        if isinstance(destinations_by_target, dict):
            for target_id in destinations_by_target:
                if str(target_id) not in valid_targets:
                    raise AutomationError(
                        "Open Hand Technique Push target must be a Flurry of Blows target"
                    )
        destinations_by_strike = params.get("open_hand_push_to_position_node_id_by_strike")
        if isinstance(destinations_by_strike, dict):
            for raw_index in destinations_by_strike:
                strike_index = self._open_hand_strike_index(raw_index, max_strikes=max_strikes)
                if strike_index not in targets_by_strike:
                    raise AutomationError(
                        f"Open Hand Technique Push {self._open_hand_strike_error(max_strikes)}"
                    )
        self._normalize_open_hand_technique_effect(
            params.get(
                "open_hand_technique",
                params.get("open_hand_technique_effect"),
            )
        )

    @staticmethod
    def _open_hand_strike_index(raw_index: Any, *, max_strikes: int) -> int:
        if isinstance(raw_index, bool):
            raise AutomationError(AutomationExecutor._open_hand_strike_error(max_strikes))
        try:
            strike_index = int(raw_index)
        except (TypeError, ValueError) as exc:
            raise AutomationError(AutomationExecutor._open_hand_strike_error(max_strikes)) from exc
        if strike_index < 1 or strike_index > max_strikes:
            raise AutomationError(AutomationExecutor._open_hand_strike_error(max_strikes))
        return strike_index

    @staticmethod
    def _open_hand_strike_error(max_strikes: int) -> str:
        if max_strikes <= 2:
            return "Open Hand Technique strike must be 1 or 2"
        return "Open Hand Technique strike must be 1, 2, or 3"

    def _flurry_strike_count(self, actor_id: str) -> int:
        owner = self._resource_owner(actor_id)
        if isinstance(owner, Character) and has_monk_feature(owner, level=10):
            return 3
        return 2

    @staticmethod
    def _flurry_targets_by_strike(
        targets: list[str],
        params: dict[str, Any],
        *,
        max_strikes: int = 2,
    ) -> dict[int, list[str]]:
        return {
            strike_index: AutomationExecutor._flurry_strike_targets(
                params,
                f"strike_{strike_index}_target",
                targets,
                fallback_index=strike_index - 1,
            )
            for strike_index in range(1, max_strikes + 1)
        }

    @staticmethod
    def _flurry_strike_targets(
        params: dict[str, Any],
        param_name: str,
        fallback_targets: list[str],
        *,
        fallback_index: int = 0,
    ) -> list[str]:
        selected = params.get(param_name)
        if isinstance(selected, list):
            return [str(target_id) for target_id in selected]
        if selected not in (None, "", False):
            return [str(selected)]
        if not fallback_targets:
            return []
        if 0 <= fallback_index < len(fallback_targets):
            return [str(fallback_targets[fallback_index])]
        return [str(fallback_targets[0])]

    def _validate_deflect_attacks_preconditions(
        self,
        action: ActionDefinition,
        targets: list[str],
        params: dict[str, Any],
    ) -> None:
        target_id = self._deflect_attacks_target_id(targets, params)
        if target_id is None:
            return
        if params.get("use_uncanny_dodge") is True:
            raise AutomationError("Deflect Attacks cannot be combined with Uncanny Dodge")
        if target_id not in set(targets):
            raise AutomationError("Deflect Attacks target must be a target of the attack")
        target = self._entity(target_id)
        owner = self._resource_owner(target_id)
        if not isinstance(owner, Character) or not has_monk_feature(owner, level=3):
            raise AutomationError("Deflect Attacks requires Monk level 3")
        if not self._action_supports_deflect_attacks(action, owner):
            if has_monk_feature(owner, level=13):
                raise AutomationError("Deflect Attacks requires an attack roll with damage")
            raise AutomationError(
                "Deflect Attacks requires an attack roll with bludgeoning, piercing, or slashing damage"
            )
        if not self._reaction_budget_available(target_id, target):
            raise AutomationError("not enough reaction budget")
        redirect_target_id = self._deflect_attacks_redirect_target_id(params)
        if redirect_target_id is not None:
            if self._get_resource(owner, FOCUS_RESOURCE_ID) <= 0:
                raise AutomationError(f"resource {FOCUS_RESOURCE_ID} is insufficient")
            self._validate_deflect_attacks_redirect_target(
                action,
                deflector_id=target_id,
                redirect_target_id=redirect_target_id,
            )

    def _apply_deflect_attacks_if_requested(
        self,
        ctx: _Context,
        target_id: str,
        amount: int,
        damage_type: str,
        path: str,
    ) -> tuple[int, dict[str, Any] | None]:
        selected_target_id = self._deflect_attacks_target_id(ctx.original_targets, ctx.params)
        if selected_target_id != target_id:
            return amount, None
        owner = self._resource_owner(target_id)
        owner_character = owner if isinstance(owner, Character) else None
        if not self._action_supports_deflect_attacks(ctx.action, owner_character):
            return amount, None
        if not ctx.attack_hits.get(target_id, False):
            return amount, None
        if (
            target_id not in ctx.deflect_attacks_reduction_remaining
            and not self._deflect_attacks_accepts_damage_type(owner_character, damage_type)
        ):
            return amount, None
        reaction_spent = target_id not in ctx.deflect_attacks_reactions_spent
        reduction_roll: RollResult | None = None
        reduction_static_bonus = 0
        reduction_cap: int | None = None
        if reaction_spent:
            if owner_character is None or not has_monk_feature(owner_character, level=3):
                raise AutomationError("Deflect Attacks requires Monk level 3")
            monk_level = int(owner_character.class_levels.get("monk", 0))
            reduction_static_bonus = self._ability_modifier(owner_character, "dex") + monk_level
            reduction_roll = self.roll_service.roll("1d10")
            ctx.result.dice_rolls.append(reduction_roll.to_dict())
            reduction_cap = max(0, reduction_roll.total + reduction_static_bonus)
            ctx.deflect_attacks_reduction_remaining[target_id] = reduction_cap
        remaining = ctx.deflect_attacks_reduction_remaining.get(target_id, 0)
        reduction = min(amount, remaining)
        reduced_amount = max(0, amount - reduction)
        ctx.deflect_attacks_reduction_remaining[target_id] = max(0, remaining - reduction)
        change: dict[str, Any] = {
            "feature": "deflect_attacks",
            "source_action_id": DEFLECT_ATTACKS_ACTION_ID,
            "actor_id": target_id,
            "attacker_id": ctx.actor_id,
            "original_amount": amount,
            "damage_type": damage_type,
            "reduction": reduction,
            "reduced_amount": reduced_amount,
            "reduction_remaining": ctx.deflect_attacks_reduction_remaining[target_id],
            "reaction_spent": reaction_spent,
            "path": path,
        }
        if damage_type.lower() not in BASIC_WEAPON_DAMAGE_TYPES:
            change["deflect_energy"] = self._deflect_attacks_accepts_damage_type(
                owner_character,
                damage_type,
            )
        if reduction_roll is not None:
            change["reduction_roll_total"] = reduction_roll.total
            change["reduction_static_bonus"] = reduction_static_bonus
            change["reduction_cap"] = reduction_cap
        if reaction_spent:
            target = self._entity(target_id)
            before = self.economy.budget_for(target_id, self._effective_speed(target)).to_dict()
            self.economy.spend(target_id, "reaction", 1)
            after = self.economy.budget_for(target_id).to_dict()
            ctx.deflect_attacks_reactions_spent.add(target_id)
            economy_change = {
                "type": "action_economy",
                "actor_id": target_id,
                "economy": "reaction",
                "amount": 1,
                "before": before,
                "after": after,
                "source_action_id": DEFLECT_ATTACKS_ACTION_ID,
                "path": path,
            }
            ctx.result.state_changes.append(economy_change)
            change["reaction_before"] = before
            change["reaction_after"] = after
        redirect = self._apply_deflect_attacks_redirect_if_requested(
            ctx,
            deflector_id=target_id,
            damage_type=damage_type,
            reduced_amount=reduced_amount,
            path=path,
        )
        if redirect is not None:
            change["redirect"] = redirect
        ctx.result.state_changes.append({"type": "deflect_attacks", **change})
        return reduced_amount, change

    def _apply_deflect_attacks_redirect_if_requested(
        self,
        ctx: _Context,
        *,
        deflector_id: str,
        damage_type: str,
        reduced_amount: int,
        path: str,
    ) -> dict[str, Any] | None:
        redirect_target_id = self._deflect_attacks_redirect_target_id(ctx.params)
        if redirect_target_id is None or reduced_amount > 0:
            return None
        if deflector_id in ctx.deflect_attacks_redirect_applied:
            return None
        self._validate_deflect_attacks_redirect_target(
            ctx.action,
            deflector_id=deflector_id,
            redirect_target_id=redirect_target_id,
        )
        owner = self._resource_owner(deflector_id)
        if not isinstance(owner, Character):
            raise AutomationError("Deflect Attacks requires Monk level 3")
        self._spend_deflect_attacks_focus(ctx, deflector_id, path)
        dc = self._monk_focus_save_dc(deflector_id)
        dc_source = "monk_focus:wis+proficiency"
        success = self._roll_deflect_attacks_redirect_save(
            ctx,
            redirect_target_id,
            dc,
            dc_source,
            path,
        )
        change: dict[str, Any] = {
            "type": "deflect_attacks_redirect",
            "actor_id": deflector_id,
            "target_id": redirect_target_id,
            "source_action_id": DEFLECT_ATTACKS_ACTION_ID,
            "dc": dc,
            "dc_source": dc_source,
            "saving_throw_success": success,
            "damage_type": damage_type,
            "path": f"{path}.deflect_attacks.redirect",
        }
        if not success:
            die = monk_martial_arts_die(owner)
            first_roll = self.roll_service.roll(f"1{die}")
            second_roll = self.roll_service.roll(f"1{die}")
            ctx.result.dice_rolls.extend([first_roll.to_dict(), second_roll.to_dict()])
            dex_modifier = self._ability_modifier(owner, "dex")
            damage_amount = max(0, first_roll.total + second_roll.total + dex_modifier)
            target_before = self._entity(redirect_target_id)
            hp_before = int(getattr(target_before, "hp_current"))
            applied = self._apply_damage(
                redirect_target_id,
                damage_amount,
                damage_type,
                ctx=ctx,
                path=f"{path}.deflect_attacks.redirect",
            )
            hp_after = int(getattr(self._entity(redirect_target_id), "hp_current"))
            change.update(
                {
                    "martial_arts_die": die,
                    "damage_amount": damage_amount,
                    "damage_applied": applied,
                    "dex_modifier": dex_modifier,
                }
            )
            if hp_before > 0 and hp_after == 0 and applied > 0:
                ctx.result.state_changes.extend(
                    self._dark_ones_blessing_changes(
                        deflector_id,
                        redirect_target_id,
                        f"{path}.deflect_attacks.redirect",
                    )
                )
        ctx.deflect_attacks_redirect_applied.add(deflector_id)
        ctx.result.state_changes.append(change)
        return change

    def _spend_deflect_attacks_focus(
        self,
        ctx: _Context,
        deflector_id: str,
        path: str,
    ) -> None:
        owner = self._resource_owner(deflector_id)
        before = self._get_resource(owner, FOCUS_RESOURCE_ID)
        if before <= 0:
            raise AutomationError(f"resource {FOCUS_RESOURCE_ID} is insufficient")
        self._set_resource(owner, FOCUS_RESOURCE_ID, before - 1)
        ctx.result.state_changes.append(
            {
                "type": "cost",
                "actor_id": deflector_id,
                "resource": FOCUS_RESOURCE_ID,
                "before": before,
                "after": before - 1,
                "source_action_id": DEFLECT_ATTACKS_ACTION_ID,
                "path": f"{path}.deflect_attacks.redirect",
            }
        )

    def _roll_deflect_attacks_redirect_save(
        self,
        ctx: _Context,
        target_id: str,
        dc: int,
        dc_source: str,
        path: str,
    ) -> bool:
        target = self._entity(target_id)
        base_bonus, proficient, _ = self._saving_throw_bonus(target, "dex")
        target_exhaustion_level, exhaustion_penalty = self._exhaustion_details(target)
        bonus = base_bonus - exhaustion_penalty
        status_advantage, status_sources = self._saving_throw_status_advantage(target, "dex")
        roll = self.roll_service.roll(d20_expression(bonus), advantage=status_advantage)
        adjustment, adjustment_rolls, adjustment_sources = self._passive_roll_adjustment(
            target,
            bonus_key="saving_throw_bonus_dice",
            penalty_key="saving_throw_penalty_dice",
        )
        ctx.result.dice_rolls.append(roll.to_dict())
        ctx.result.dice_rolls.extend(extra.to_dict() for extra in adjustment_rolls)
        total = roll.total + adjustment
        success = total >= dc
        ctx.result.node_results[f"{path}.deflect_attacks.redirect"] = {
            "target_id": target_id,
            "ability": "dex",
            "dc": dc,
            "dc_source": dc_source,
            "bonus": bonus,
            "base_bonus": base_bonus,
            "proficient": proficient,
            "exhaustion_level": target_exhaustion_level,
            "d20_penalty": exhaustion_penalty,
            "base_total": roll.total,
            "passive_adjustment": adjustment,
            "passive_sources": adjustment_sources,
            "status_advantage": status_advantage,
            "status_sources": status_sources,
            "total": total,
            "success": success,
        }
        return success

    def _deflect_attacks_target_id(
        self,
        targets: list[str],
        params: dict[str, Any],
    ) -> str | None:
        if params.get("use_deflect_attacks") is not True:
            return None
        explicit = params.get("deflect_attacks_target_id")
        if explicit is not None:
            return str(explicit)
        if len(targets) == 1:
            return str(targets[0])
        raise AutomationError("Deflect Attacks requires a target id")

    @staticmethod
    def _deflect_attacks_redirect_target_id(params: dict[str, Any]) -> str | None:
        selected = params.get("deflect_attacks_redirect_target_id")
        if selected in (None, "", False):
            return None
        if isinstance(selected, (dict, list)):
            raise AutomationError("parameter deflect_attacks_redirect_target_id must be a scalar")
        return str(selected)

    def _validate_deflect_attacks_redirect_target(
        self,
        action: ActionDefinition,
        *,
        deflector_id: str,
        redirect_target_id: str,
    ) -> None:
        try:
            deflector = self._entity(deflector_id)
            redirect_target = self._entity(redirect_target_id)
        except KeyError as exc:
            raise AutomationError(f"unknown target {redirect_target_id}") from exc
        if (
            self.state.encounter is None
            or self.state.encounter.tactical_graph is None
            or not isinstance(deflector, Combatant)
            or not isinstance(redirect_target, Combatant)
            or deflector.position_node_id is None
            or redirect_target.position_node_id is None
        ):
            raise AutomationError("Deflect Attacks redirect requires tactical positions")
        graph = TacticalGraph.from_dict(self.state.encounter.tactical_graph)
        if not graph.has_line_of_sight(
            deflector.position_node_id, redirect_target.position_node_id
        ):
            raise AutomationError("Deflect Attacks redirect target must be visible")
        distance = graph.shortest_distance(
            deflector.position_node_id,
            redirect_target.position_node_id,
        )
        if distance is None:
            raise AutomationError("Deflect Attacks redirect target is out of range")
        if self._action_is_melee_attack(action):
            if int(distance) > 5:
                raise AutomationError("Deflect Attacks melee redirect target must be within 5 feet")
            return
        if int(distance) > 60:
            raise AutomationError("Deflect Attacks ranged redirect target must be within 60 feet")
        if (
            graph.cover_between(deflector.position_node_id, redirect_target.position_node_id)
            == "total"
        ):
            raise AutomationError("Deflect Attacks ranged redirect target is behind Total Cover")

    @staticmethod
    def _action_is_melee_attack(action: ActionDefinition) -> bool:
        normal_range = int(action.range.get("normal_ft", 0))
        return normal_range <= 5

    @staticmethod
    def _deflect_attacks_accepts_damage_type(
        owner: Character | None,
        damage_type: str,
    ) -> bool:
        if damage_type.lower() in BASIC_WEAPON_DAMAGE_TYPES:
            return True
        return owner is not None and has_monk_feature(owner, level=13)

    def _action_supports_deflect_attacks(
        self,
        action: ActionDefinition,
        owner: Character | None,
    ) -> bool:
        if action.action_type not in ATTACK_ACTION_TYPES:
            return False
        nodes = self._automation_nodes(action.automation)
        if not any(node.get("type") == "attack_roll" for node in nodes):
            return False
        damage_nodes = [
            node
            for node in nodes
            if node.get("type") == "damage" and node.get("requires_hit") is True
        ]
        if owner is not None and has_monk_feature(owner, level=13):
            return bool(damage_nodes)
        return any(
            str(node.get("damage_type", "")).lower() in BASIC_WEAPON_DAMAGE_TYPES
            for node in damage_nodes
        )

    def _validate_uncanny_dodge_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        targets: list[str],
        params: dict[str, Any],
    ) -> None:
        target_id = self._uncanny_dodge_target_id(targets, params)
        if target_id is None:
            return
        if target_id not in set(targets):
            raise AutomationError("Uncanny Dodge target must be a target of the attack")
        if not self._action_supports_uncanny_dodge(action):
            raise AutomationError("Uncanny Dodge requires a hit from an attack roll")
        target = self._entity(target_id)
        owner = self._resource_owner(target_id)
        if not isinstance(owner, Character) or int(owner.class_levels.get("rogue", 0)) < 5:
            raise AutomationError("Uncanny Dodge requires Rogue level 5")
        if not self._uncanny_dodge_attacker_visible(actor_id, target_id, params):
            raise AutomationError("Uncanny Dodge requires a visible attacker")
        if not self._reaction_budget_available(target_id, target):
            raise AutomationError("not enough reaction budget")

    def _validate_superior_hunters_defense_preconditions(
        self,
        action: ActionDefinition,
        targets: list[str],
        params: dict[str, Any],
    ) -> None:
        target_id = self._superior_hunters_defense_target_id(targets, params)
        if target_id is None:
            return
        if target_id not in set(targets):
            raise AutomationError("Superior Hunter's Defense target must be a target")
        if not self._action_supports_superior_hunters_defense(action):
            raise AutomationError("Superior Hunter's Defense requires damage")
        target = self._entity(target_id)
        owner = self._resource_owner(target_id)
        if not isinstance(owner, Character) or not has_superior_hunters_defense(owner):
            raise AutomationError("Superior Hunter's Defense requires Ranger Hunter level 15")
        self._superior_hunters_defense_damage_type(params)
        if not self._reaction_budget_available(target_id, target):
            raise AutomationError("not enough reaction budget")
        competing_reactions = {
            self._deflect_attacks_target_id(targets, params),
            self._uncanny_dodge_target_id(targets, params),
            self._slow_fall_target_id(targets, params),
        }
        if target_id in competing_reactions:
            raise AutomationError(
                "Superior Hunter's Defense cannot be combined with another reaction"
            )

    def _apply_superior_hunters_defense_if_requested(
        self,
        ctx: _Context,
        target_id: str,
        amount: int,
        damage_type: str,
        path: str,
    ) -> dict[str, Any] | None:
        selected_target_id = self._superior_hunters_defense_target_id(
            ctx.original_targets,
            ctx.params,
        )
        if selected_target_id != target_id:
            return None
        if target_id in ctx.superior_hunters_defense_reactions_spent:
            return None
        requested_damage_type = self._superior_hunters_defense_damage_type(ctx.params)
        if requested_damage_type is not None and requested_damage_type != damage_type:
            return None
        if amount <= 0:
            return None
        target = self._entity(target_id)
        if self._mitigated_damage(target, amount, damage_type) <= 0:
            return None
        owner = self._resource_owner(target_id)
        if not isinstance(owner, Character) or not has_superior_hunters_defense(owner):
            return None

        turn_owner_id = ctx.actor_id
        if self.state.encounter is not None and self.state.encounter.current_combatant_id:
            turn_owner_id = self.state.encounter.current_combatant_id
        effect = EffectInstance(
            effect_id=f"{target_id}:superior_hunters_defense:{damage_type}",
            source_ref=("SRD 5.2.1 Ranger Subclass: Hunter, Level 15: Superior Hunter's Defense"),
            source_action_id=SUPERIOR_HUNTERS_DEFENSE_ACTION_ID,
            target_id=target_id,
            applied_by=target_id,
            condition=SUPERIOR_HUNTERS_DEFENSE_CONDITION,
            passive_modifiers={
                "damage_resistances": [damage_type],
                "superior_hunters_defense": True,
            },
            duration={"until": "end_of_current_turn", "turn_owner_id": turn_owner_id},
            tick_on="self_turn_end",
            stacking_policy="replace_condition",
            audit={"damage_type": damage_type, "node_path": path},
        )
        effects = getattr(target, "status_effects")
        effects[:] = [
            existing
            for existing in effects
            if existing.get("condition") != SUPERIOR_HUNTERS_DEFENSE_CONDITION
        ]
        effects.append(effect.to_dict())

        before = self.economy.budget_for(target_id, self._effective_speed(target)).to_dict()
        self.economy.spend(target_id, "reaction", 1)
        after = self.economy.budget_for(target_id).to_dict()
        ctx.superior_hunters_defense_reactions_spent.add(target_id)
        ctx.result.state_changes.append(
            {
                "type": "action_economy",
                "actor_id": target_id,
                "economy": "reaction",
                "amount": 1,
                "before": before,
                "after": after,
                "source_action_id": SUPERIOR_HUNTERS_DEFENSE_ACTION_ID,
                "path": path,
            }
        )
        change = {
            "feature": "superior_hunters_defense",
            "source_action_id": SUPERIOR_HUNTERS_DEFENSE_ACTION_ID,
            "actor_id": target_id,
            "attacker_id": ctx.actor_id,
            "damage_type": damage_type,
            "effect_id": effect.effect_id,
            "duration": effect.duration,
            "tick_on": effect.tick_on,
            "reaction_before": before,
            "reaction_after": after,
            "path": path,
        }
        ctx.result.state_changes.append({"type": "superior_hunters_defense", **change})
        return change

    def _apply_uncanny_dodge_if_requested(
        self,
        ctx: _Context,
        target_id: str,
        amount: int,
        path: str,
    ) -> tuple[int, dict[str, Any] | None]:
        selected_target_id = self._uncanny_dodge_target_id(ctx.original_targets, ctx.params)
        if selected_target_id != target_id:
            return amount, None
        if not self._action_supports_uncanny_dodge(ctx.action):
            return amount, None
        reduced_amount = amount // 2
        reaction_spent = target_id not in ctx.uncanny_dodge_reactions_spent
        change: dict[str, Any] = {
            "feature": "uncanny_dodge",
            "source_action_id": UNCANNY_DODGE_ACTION_ID,
            "actor_id": target_id,
            "attacker_id": ctx.actor_id,
            "original_amount": amount,
            "halved_amount": reduced_amount,
            "reduction": amount - reduced_amount,
            "reaction_spent": reaction_spent,
            "path": path,
        }
        if reaction_spent:
            target = self._entity(target_id)
            before = self.economy.budget_for(target_id, self._effective_speed(target)).to_dict()
            self.economy.spend(target_id, "reaction", 1)
            after = self.economy.budget_for(target_id).to_dict()
            ctx.uncanny_dodge_reactions_spent.add(target_id)
            economy_change = {
                "type": "action_economy",
                "actor_id": target_id,
                "economy": "reaction",
                "amount": 1,
                "before": before,
                "after": after,
                "source_action_id": UNCANNY_DODGE_ACTION_ID,
                "path": path,
            }
            ctx.result.state_changes.append(economy_change)
            change["reaction_before"] = before
            change["reaction_after"] = after
        ctx.result.state_changes.append({"type": "uncanny_dodge", **change})
        return reduced_amount, change

    def _superior_hunters_defense_target_id(
        self,
        targets: list[str],
        params: dict[str, Any],
    ) -> str | None:
        if params.get("use_superior_hunters_defense") is not True:
            return None
        explicit = params.get("superior_hunters_defense_target_id")
        if explicit is not None:
            return str(explicit)
        if len(targets) == 1:
            return str(targets[0])
        raise AutomationError("Superior Hunter's Defense requires a target id")

    @staticmethod
    def _superior_hunters_defense_damage_type(params: dict[str, Any]) -> str | None:
        selected = params.get("superior_hunters_defense_damage_type")
        if selected in (None, "", False):
            return None
        if isinstance(selected, (dict, list)):
            raise AutomationError("parameter superior_hunters_defense_damage_type must be a scalar")
        return str(selected).lower()

    def _action_supports_superior_hunters_defense(self, action: ActionDefinition) -> bool:
        return any(
            node.get("type") == "damage" for node in self._automation_nodes(action.automation)
        )

    def _validate_slow_fall_preconditions(
        self,
        action: ActionDefinition,
        targets: list[str],
        params: dict[str, Any],
    ) -> None:
        target_id = self._slow_fall_target_id(targets, params)
        if target_id is None:
            return
        if action.id not in FALLING_HAZARD_ACTION_IDS:
            raise AutomationError("Slow Fall requires falling damage")
        if target_id not in set(targets):
            raise AutomationError("Slow Fall target must be a target of the fall")
        target = self._entity(target_id)
        owner = self._resource_owner(target_id)
        if not isinstance(owner, Character) or monk_slow_fall_damage_reduction(owner) <= 0:
            raise AutomationError("Slow Fall requires Monk level 4")
        if not self._reaction_budget_available(target_id, target):
            raise AutomationError("not enough reaction budget")

    def _apply_slow_fall_if_requested(
        self,
        ctx: _Context,
        target_id: str,
        amount: int,
        damage_type: str,
    ) -> tuple[int, dict[str, Any] | None]:
        selected_target_id = self._slow_fall_target_id(ctx.original_targets, ctx.params)
        if selected_target_id != target_id:
            return amount, None
        if ctx.action.id not in FALLING_HAZARD_ACTION_IDS or damage_type != "bludgeoning":
            return amount, None
        owner = self._resource_owner(target_id)
        if not isinstance(owner, Character):
            return amount, None
        reduction_cap = monk_slow_fall_damage_reduction(owner)
        if reduction_cap <= 0:
            return amount, None
        reduction = min(amount, reduction_cap)
        reduced_amount = max(0, amount - reduction)
        reaction_spent = target_id not in ctx.slow_fall_reactions_spent
        change: dict[str, Any] = {
            "feature": "slow_fall",
            "source_action_id": SLOW_FALL_ACTION_ID,
            "actor_id": target_id,
            "original_amount": amount,
            "reduction_cap": reduction_cap,
            "reduction": reduction,
            "reduced_amount": reduced_amount,
            "reaction_spent": reaction_spent,
        }
        if reaction_spent:
            target = self._entity(target_id)
            before = self.economy.budget_for(target_id, self._effective_speed(target)).to_dict()
            self.economy.spend(target_id, "reaction", 1)
            after = self.economy.budget_for(target_id).to_dict()
            ctx.slow_fall_reactions_spent.add(target_id)
            economy_change = {
                "type": "action_economy",
                "actor_id": target_id,
                "economy": "reaction",
                "amount": 1,
                "before": before,
                "after": after,
                "source_action_id": SLOW_FALL_ACTION_ID,
            }
            ctx.result.state_changes.append(economy_change)
            change["reaction_before"] = before
            change["reaction_after"] = after
        ctx.result.state_changes.append({"type": "slow_fall", **change})
        return reduced_amount, change

    def _slow_fall_target_id(
        self,
        targets: list[str],
        params: dict[str, Any],
    ) -> str | None:
        if params.get("use_slow_fall") is not True:
            return None
        explicit = params.get("slow_fall_target_id")
        if explicit is not None:
            return str(explicit)
        if len(targets) == 1:
            return str(targets[0])
        raise AutomationError("Slow Fall requires a target id")

    def _uncanny_dodge_target_id(
        self,
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
        raise AutomationError("Uncanny Dodge requires a target id")

    def _action_supports_uncanny_dodge(self, action: ActionDefinition) -> bool:
        if action.action_type not in ATTACK_ACTION_TYPES:
            return False
        nodes = self._automation_nodes(action.automation)
        return any(node.get("type") == "attack_roll" for node in nodes) and any(
            node.get("type") == "damage" and node.get("requires_hit") is True for node in nodes
        )

    def _reaction_budget_available(
        self,
        actor_id: str,
        actor: Character | Monster | Combatant,
    ) -> bool:
        if self.state.encounter is not None:
            budget_data = self.state.encounter.action_budgets.get(actor_id)
            if budget_data is None:
                return True
            return int(budget_data.get("reaction", 1)) >= 1
        return self.economy.budget_for(actor_id, self._effective_speed(actor)).can_spend("reaction")

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

    def _validate_remarkable_athlete_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        params: dict[str, Any],
    ) -> None:
        destination = self._remarkable_athlete_destination(params)
        if destination is None:
            return
        actor = self._resource_owner(actor_id)
        if not isinstance(actor, Character) or not has_fighter_champion_feature(actor, level=3):
            raise AutomationError("Remarkable Athlete requires Fighter Champion level 3")
        if not any(
            node.get("type") == "attack_roll" for node in self._automation_nodes(action.automation)
        ):
            raise AutomationError("Remarkable Athlete movement requires an attack roll")
        self._remarkable_athlete_move_plan(actor_id, destination)

    def _apply_remarkable_athlete_move_if_requested(
        self,
        ctx: _Context,
        path: str,
    ) -> None:
        if ctx.remarkable_athlete_moved:
            return
        destination = self._remarkable_athlete_destination(ctx.params)
        if destination is None:
            return
        plan = self._remarkable_athlete_move_plan(ctx.actor_id, destination)
        actor = plan["actor"]
        assert isinstance(actor, Combatant)
        before_position = actor.position_node_id
        actor.position_node_id = destination
        before_used, after_used = self.economy.add(
            ctx.actor_id,
            "movement_used",
            int(plan["movement_cost"]),
        )
        ctx.remarkable_athlete_moved = True
        ctx.result.state_changes.append(
            {
                "type": "move",
                "actor_id": ctx.actor_id,
                "feature": "remarkable_athlete",
                "source_action_id": "srd.remarkable_athlete",
                "from": before_position,
                "to": actor.position_node_id,
                "movement_cost": int(plan["movement_cost"]),
                "movement_limit": int(plan["movement_limit"]),
                "movement_used_before": before_used,
                "movement_used_after": after_used,
                "opportunity_attack_triggers": [],
                "path": f"{path}.remarkable_athlete",
            }
        )

    @staticmethod
    def _remarkable_athlete_destination(params: dict[str, Any]) -> str | None:
        destination = params.get("remarkable_athlete_to_position_node_id")
        if destination is None:
            return None
        return str(destination)

    def _remarkable_athlete_move_plan(self, actor_id: str, destination: str) -> dict[str, Any]:
        actor = self._entity(actor_id)
        if not isinstance(actor, Combatant):
            raise AutomationError("Remarkable Athlete movement requires a combatant")
        if self.state.encounter is None or self.state.encounter.tactical_graph is None:
            raise AutomationError("Remarkable Athlete movement requires a combat tactical graph")
        if actor.position_node_id is None:
            raise AutomationError("Remarkable Athlete movement requires a current position")
        graph = TacticalGraph.from_dict(self.state.encounter.tactical_graph)
        if destination not in graph.nodes:
            raise AutomationError("Remarkable Athlete destination position does not exist")
        movement_cost = graph.shortest_distance(
            actor.position_node_id,
            destination,
            movement_cost=True,
        )
        if movement_cost is None:
            raise AutomationError("Remarkable Athlete destination position is not reachable")
        movement_limit = self._effective_speed(actor) // 2
        if int(movement_cost) > movement_limit:
            raise AutomationError("Remarkable Athlete movement cannot exceed half Speed")
        return {
            "actor": actor,
            "movement_cost": int(movement_cost),
            "movement_limit": movement_limit,
        }

    @staticmethod
    def _cunning_strike_choice(params: dict[str, Any]) -> str | None:
        choices = AutomationExecutor._cunning_strike_choices(params)
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
            if effect not in CUNNING_STRIKE_EFFECTS:
                raise AutomationError(f"unsupported Cunning Strike effect: {effect}")
            if effect in effects:
                raise AutomationError(f"duplicate Cunning Strike effect: {effect}")
            effects.append(effect)
        if len(effects) > MAX_CUNNING_STRIKE_EFFECTS:
            raise AutomationError("Improved Cunning Strike allows at most two effects")
        return effects

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
        return SUPREME_SNEAK_COVER_ALIASES.get(cover)

    def _cunning_strike_dc(self, actor_id: str) -> int:
        actor = self._resource_owner(actor_id)
        if not isinstance(actor, Character):
            raise AutomationError("Cunning Strike requires a character")
        return (
            8
            + int(getattr(actor, "proficiency_bonus", 2))
            + self._ability_modifier(
                actor,
                "dex",
            )
        )

    @staticmethod
    def _has_item_on_person(actor: Character, item_id: str) -> bool:
        return item_id in actor.equipment or int(actor.inventory.get(item_id, 0)) > 0

    def _target_large_or_smaller(self, target_id: str) -> bool:
        size = str(getattr(self._entity(target_id), "size", "medium")).casefold()
        rank = CREATURE_SIZE_RANKS.get(size, CREATURE_SIZE_RANKS["medium"])
        return rank <= CREATURE_SIZE_RANKS["large"]

    def _target_huge_or_smaller(self, target_id: str) -> bool:
        size = str(getattr(self._entity(target_id), "size", "medium")).casefold()
        rank = CREATURE_SIZE_RANKS.get(size, CREATURE_SIZE_RANKS["medium"])
        return rank <= CREATURE_SIZE_RANKS["huge"]

    def _cunning_strike_withdraw_plan(self, actor_id: str, destination: str) -> dict[str, Any]:
        actor = self._entity(actor_id)
        if not isinstance(actor, Combatant):
            raise AutomationError("Cunning Strike Withdraw requires a combatant")
        if self.state.encounter is None or self.state.encounter.tactical_graph is None:
            raise AutomationError("Cunning Strike Withdraw requires a combat tactical graph")
        if actor.position_node_id is None:
            raise AutomationError("Cunning Strike Withdraw requires a current position")
        graph = TacticalGraph.from_dict(self.state.encounter.tactical_graph)
        if destination not in graph.nodes:
            raise AutomationError("Cunning Strike Withdraw destination position does not exist")
        movement_cost = graph.shortest_distance(
            actor.position_node_id,
            destination,
            movement_cost=True,
        )
        if movement_cost is None:
            raise AutomationError("Cunning Strike Withdraw destination position is not reachable")
        movement_limit = self._effective_speed(actor) // 2
        if int(movement_cost) > movement_limit:
            raise AutomationError("Cunning Strike Withdraw movement cannot exceed half Speed")
        return {
            "actor": actor,
            "movement_cost": int(movement_cost),
            "movement_limit": movement_limit,
        }

    def _validate_tactical_shift_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        params: dict[str, Any],
    ) -> None:
        for node in self._automation_nodes(action.automation):
            if node.get("type") != "tactical_shift_move":
                continue
            destination_param = str(
                node.get("destination_param", "tactical_shift_to_position_node_id")
            )
            destination = params.get(destination_param)
            if destination is None:
                continue
            owner = self._resource_owner(actor_id)
            class_levels = getattr(owner, "class_levels", {})
            if not isinstance(class_levels, dict) or int(class_levels.get("fighter", 0)) < 5:
                raise AutomationError("Tactical Shift requires Fighter level 5")
            self._tactical_shift_move_plan(actor_id, str(destination))

    def _validate_instinctive_pounce_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        params: dict[str, Any],
    ) -> None:
        for node in self._automation_nodes(action.automation):
            if node.get("type") != "instinctive_pounce_move":
                continue
            destination_param = str(
                node.get("destination_param", "instinctive_pounce_to_position_node_id")
            )
            destination = params.get(destination_param)
            if destination is None:
                continue
            owner = self._resource_owner(actor_id)
            class_levels = getattr(owner, "class_levels", {})
            if not isinstance(class_levels, dict) or int(class_levels.get("barbarian", 0)) < 7:
                raise AutomationError("Instinctive Pounce requires Barbarian level 7")
            self._instinctive_pounce_move_plan(actor_id, str(destination))

    def _instinctive_pounce_move_plan(self, actor_id: str, destination: str) -> dict[str, Any]:
        actor = self._entity(actor_id)
        if not isinstance(actor, Combatant):
            raise AutomationError("Instinctive Pounce requires a combatant")
        if self.state.encounter is None or self.state.encounter.tactical_graph is None:
            raise AutomationError("Instinctive Pounce requires a combat tactical graph")
        if actor.position_node_id is None:
            raise AutomationError("Instinctive Pounce requires a current position")
        graph = TacticalGraph.from_dict(self.state.encounter.tactical_graph)
        if destination not in graph.nodes:
            raise AutomationError("Instinctive Pounce destination position does not exist")
        movement_cost = graph.shortest_distance(
            actor.position_node_id,
            destination,
            movement_cost=True,
        )
        if movement_cost is None:
            raise AutomationError("Instinctive Pounce destination position is not reachable")
        movement_limit = self._effective_speed(actor) // 2
        if int(movement_cost) > movement_limit:
            raise AutomationError("Instinctive Pounce movement cannot exceed half Speed")
        return {
            "actor": actor,
            "movement_cost": int(movement_cost),
            "movement_limit": movement_limit,
        }

    def _opportunity_attack_triggers_for_move(
        self,
        actor: Combatant,
        *,
        from_position: str | None,
        to_position: str | None,
    ) -> list[str]:
        if (
            self.state.encounter is None
            or self.state.encounter.tactical_graph is None
            or from_position is None
            or to_position is None
        ):
            return []
        graph = TacticalGraph.from_dict(self.state.encounter.tactical_graph)
        enemy_positions: dict[str, str] = {}
        if not has_condition(actor.status_effects, "disengaged"):
            enemy_positions = {
                combatant_id: other.position_node_id
                for combatant_id, other in self.state.encounter.combatants.items()
                if other.side != actor.side
                and other.position_node_id is not None
                and not self._cannot_make_opportunity_attacks(other)
            }
        enemy_reach = {
            combatant_id: other.reach_ft
            for combatant_id, other in self.state.encounter.combatants.items()
        }
        return graph.opportunity_attack_triggers(
            actor_from=from_position,
            actor_to=to_position,
            enemy_positions=enemy_positions,
            enemy_reach_ft=enemy_reach,
        )

    @staticmethod
    def _cannot_make_opportunity_attacks(actor: Character | Monster | Combatant) -> bool:
        if has_condition(actor.status_effects, "open_hand_addled"):
            return True
        return any(
            bool(effect.get("passive_modifiers", {}).get("cannot_make_opportunity_attacks"))
            for effect in actor.status_effects
            if isinstance(effect.get("passive_modifiers", {}), dict)
        )

    def _tactical_shift_move_plan(self, actor_id: str, destination: str) -> dict[str, Any]:
        actor = self._entity(actor_id)
        if not isinstance(actor, Combatant):
            raise AutomationError("Tactical Shift requires a combatant")
        if self.state.encounter is None or self.state.encounter.tactical_graph is None:
            raise AutomationError("Tactical Shift requires a combat tactical graph")
        if actor.position_node_id is None:
            raise AutomationError("Tactical Shift requires a current position")
        graph = TacticalGraph.from_dict(self.state.encounter.tactical_graph)
        if destination not in graph.nodes:
            raise AutomationError("Tactical Shift destination position does not exist")
        movement_cost = graph.shortest_distance(
            actor.position_node_id,
            destination,
            movement_cost=True,
        )
        if movement_cost is None:
            raise AutomationError("Tactical Shift destination position is not reachable")
        movement_limit = self._effective_speed(actor) // 2
        if int(movement_cost) > movement_limit:
            raise AutomationError("Tactical Shift movement cannot exceed half Speed")
        return {
            "actor": actor,
            "movement_cost": int(movement_cost),
            "movement_limit": movement_limit,
        }

    def _validate_tactical_mind_available(self, actor_id: str) -> None:
        actor = self._resource_owner(actor_id)
        if not isinstance(actor, Character) or int(actor.class_levels.get("fighter", 0)) < 2:
            raise AutomationError("Tactical Mind requires Fighter level 2")
        if int(actor.resources.get("srd.resource.second_wind", 0)) <= 0:
            raise AutomationError("Tactical Mind requires an available Second Wind use")

    def _primal_knowledge_ability_check(
        self,
        actor_id: str,
        ability: str,
        skill: str | None,
        *,
        use_primal_knowledge: bool,
    ) -> dict[str, Any] | None:
        if not use_primal_knowledge:
            return None
        if skill not in PRIMAL_KNOWLEDGE_SKILLS:
            raise AutomationError("Primal Knowledge requires an eligible Barbarian skill")
        actor = self._resource_owner(actor_id)
        if not isinstance(actor, Character) or int(actor.class_levels.get("barbarian", 0)) < 3:
            raise AutomationError("Primal Knowledge requires Barbarian level 3")
        if not has_condition(self._status_effects_for(self._entity(actor_id)), "raging"):
            raise AutomationError("Primal Knowledge requires active Rage")
        return {
            "feature": "primal_knowledge",
            "skill": skill,
            "original_ability": ability,
            "ability": "str",
        }

    def _validate_wild_resurgence_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
    ) -> None:
        if not any(
            node.get("type") == "wild_resurgence_restore_wild_shape"
            for node in self._automation_nodes(action.automation)
        ):
            return
        actor = self._resource_owner(actor_id)
        if not isinstance(actor, Character):
            raise AutomationError("wild_resurgence_restore_wild_shape requires a character")
        if self._wild_shape_maximum(actor) <= 0:
            raise AutomationError("Wild Resurgence requires Wild Shape")
        if int(actor.resources.get("srd.resource.wild_shape", 0)) != 0:
            raise AutomationError("Wild Resurgence requires no Wild Shape uses remaining")

    @staticmethod
    def _wild_shape_maximum(actor: Character) -> int:
        return 2 if int(actor.class_levels.get("druid", 0)) >= 2 else 0

    def _resource_delta_cap(self, actor_id: str, node: dict[str, Any]) -> int | None:
        max_from = node.get("max_from")
        if max_from is None:
            return None
        if not isinstance(max_from, dict):
            raise AutomationError("max_from must be an object")
        class_name = max_from.get("class_level")
        if isinstance(class_name, str):
            owner = self._resource_owner(actor_id)
            class_levels = getattr(owner, "class_levels", {})
            if not isinstance(class_levels, dict):
                return 0
            return max(0, int(class_levels.get(class_name, 0)))
        class_resource = max_from.get("class_resource")
        if isinstance(class_resource, str):
            owner = self._resource_owner(actor_id)
            if not isinstance(owner, Character):
                return 0
            return max(0, int(resource_maxima(owner).get(class_resource, 0)))
        raise AutomationError("max_from supports only class_level or class_resource")

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

    def _clear_existing_concentration(self, actor_id: str) -> list[dict[str, Any]]:
        removed: list[dict[str, Any]] = []
        effect_lists: list[tuple[str, str, list[dict[str, Any]]]] = []
        effect_lists.extend(
            ("character", actor_id, actor.status_effects)
            for actor_id, actor in self.state.characters.items()
        )
        effect_lists.extend(
            ("monster", actor_id, actor.status_effects)
            for actor_id, actor in self.state.monsters.items()
        )
        if self.state.encounter is not None:
            effect_lists.extend(
                ("combatant", combatant_id, combatant.status_effects)
                for combatant_id, combatant in self.state.encounter.combatants.items()
            )
        for owner_type, owner_id, effects in effect_lists:
            retained: list[dict[str, Any]] = []
            for effect in effects:
                if self._effect_is_actor_concentration(effect, actor_id):
                    removed.append(
                        {
                            "owner_type": owner_type,
                            "owner_id": owner_id,
                            "effect_id": effect.get("effect_id"),
                            "source_action_id": effect.get("source_action_id"),
                        }
                    )
                else:
                    retained.append(effect)
            effects[:] = retained

        retained_world_effects: list[dict[str, Any]] = []
        for effect in self.state.world.active_effects:
            if self._effect_is_actor_concentration(effect, actor_id):
                removed.append(
                    {
                        "owner_type": "world",
                        "owner_id": "world",
                        "effect_id": effect.get("effect_id"),
                        "source_action_id": effect.get("source_action_id"),
                    }
                )
            else:
                retained_world_effects.append(effect)
        self.state.world.active_effects[:] = retained_world_effects
        return removed

    def _actor_effect_ids(self, actor_id: str) -> set[str]:
        return {
            str(effect.get("effect_id"))
            for _, _, effects in self._actor_effect_lists(actor_id)
            for effect in effects
            if effect.get("effect_id") is not None
        }

    def _target_effect_lists(self, target_id: str) -> list[tuple[str, str, list[dict[str, Any]]]]:
        effect_lists: list[tuple[str, str, list[dict[str, Any]]]] = []
        seen: set[int] = set()

        def add(owner_type: str, owner_id: str, effects: list[dict[str, Any]]) -> None:
            list_id = id(effects)
            if list_id in seen:
                return
            seen.add(list_id)
            effect_lists.append((owner_type, owner_id, effects))

        if target_id in self.state.characters:
            add("character", target_id, self.state.characters[target_id].status_effects)
        if target_id in self.state.monsters:
            add("monster", target_id, self.state.monsters[target_id].status_effects)
        if self.state.encounter is not None and target_id in self.state.encounter.combatants:
            combatant = self.state.encounter.combatants[target_id]
            add("combatant", target_id, combatant.status_effects)
            if combatant.entity_id in self.state.characters:
                add(
                    "character",
                    combatant.entity_id,
                    self.state.characters[combatant.entity_id].status_effects,
                )
            if combatant.entity_id in self.state.monsters:
                add(
                    "monster",
                    combatant.entity_id,
                    self.state.monsters[combatant.entity_id].status_effects,
                )
        return effect_lists

    def _actor_effect_lists(self, actor_id: str) -> list[tuple[str, str, list[dict[str, Any]]]]:
        effect_lists: list[tuple[str, str, list[dict[str, Any]]]] = []
        seen: set[int] = set()

        def add(owner_type: str, owner_id: str, effects: list[dict[str, Any]]) -> None:
            list_id = id(effects)
            if list_id in seen:
                return
            seen.add(list_id)
            effect_lists.append((owner_type, owner_id, effects))

        if actor_id in self.state.characters:
            add("character", actor_id, self.state.characters[actor_id].status_effects)
        if actor_id in self.state.monsters:
            add("monster", actor_id, self.state.monsters[actor_id].status_effects)
        if self.state.encounter is not None and actor_id in self.state.encounter.combatants:
            combatant = self.state.encounter.combatants[actor_id]
            add("combatant", actor_id, combatant.status_effects)
            if combatant.entity_id in self.state.characters:
                add(
                    "character",
                    combatant.entity_id,
                    self.state.characters[combatant.entity_id].status_effects,
                )
            if combatant.entity_id in self.state.monsters:
                add(
                    "monster",
                    combatant.entity_id,
                    self.state.monsters[combatant.entity_id].status_effects,
                )
        return effect_lists

    @staticmethod
    def _is_hide_invisible_effect(effect: dict[str, Any]) -> bool:
        return (
            effect.get("condition") in {"hidden", "invisible"}
            and effect.get("source_action_id") in HIDE_ACTION_IDS
        )

    def _hide_invisible_effect_entries(self, actor_id: str) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for owner_type, owner_id, effects in self._actor_effect_lists(actor_id):
            for effect in effects:
                if not self._is_hide_invisible_effect(effect):
                    continue
                effect_id = str(effect.get("effect_id"))
                key = (owner_type, owner_id, effect_id)
                if key in seen:
                    continue
                seen.add(key)
                entries.append(
                    {
                        "owner_type": owner_type,
                        "owner_id": owner_id,
                        "effect_id": effect.get("effect_id"),
                        "condition": effect.get("condition"),
                        "source_action_id": effect.get("source_action_id"),
                    }
                )
        return entries

    def _expire_actor_effects_after_action(
        self,
        ctx: _Context,
        preexisting_effect_ids: set[str],
    ) -> None:
        trigger = self._effect_break_trigger(ctx)
        if trigger is None:
            return
        removed: list[dict[str, Any]] = []
        for owner_type, owner_id, effects in self._actor_effect_lists(ctx.actor_id):
            retained: list[dict[str, Any]] = []
            for effect in effects:
                effect_id = effect.get("effect_id")
                if (
                    effect_id is not None
                    and str(effect_id) in preexisting_effect_ids
                    and self._effect_breaks_on_trigger(effect, trigger)
                    and not self._supreme_sneak_preserves_effect(ctx, effect, trigger)
                ):
                    removed.append(
                        {
                            "owner_type": owner_type,
                            "owner_id": owner_id,
                            "effect_id": effect_id,
                            "condition": effect.get("condition"),
                            "source_action_id": effect.get("source_action_id"),
                        }
                    )
                else:
                    retained.append(effect)
            effects[:] = retained
        if removed:
            ctx.result.state_changes.append(
                {
                    "type": "effect_expired",
                    "actor_id": ctx.actor_id,
                    "trigger": trigger,
                    "removed": removed,
                }
            )

    def _expire_target_effects_on_damage(
        self,
        ctx: _Context,
        target_id: str,
        path: str,
        *,
        damage_source_actor_id: str,
    ) -> list[dict[str, Any]]:
        changes: list[dict[str, Any]] = []
        removed: list[dict[str, Any]] = []
        repeat_save_removed: list[dict[str, Any]] = []
        consumed_next_save = False
        for owner_type, owner_id, effects in self._target_effect_lists(target_id):
            retained: list[dict[str, Any]] = []
            for effect in effects:
                repeat_save = self._effect_damage_repeat_save(effect)
                if repeat_save is not None:
                    repeat_save_entry, repeat_save_roll = self._roll_effect_repeat_save(
                        target_id,
                        effect,
                        repeat_save,
                    )
                    ctx.result.dice_rolls.append(repeat_save_roll.to_dict())
                    consumed_next_save = True
                    changes.append(
                        {
                            "type": "effect_repeat_save",
                            "target_id": target_id,
                            "trigger": "damage",
                            "owner_type": owner_type,
                            "owner_id": owner_id,
                            "effect_id": effect.get("effect_id"),
                            "condition": effect.get("condition"),
                            "source_action_id": effect.get("source_action_id"),
                            "repeat_save": repeat_save_entry,
                            "path": path,
                        }
                    )
                    if repeat_save_entry["success"] and bool(
                        repeat_save.get("end_on_success", True)
                    ):
                        repeat_save_removed.append(
                            {
                                "owner_type": owner_type,
                                "owner_id": owner_id,
                                "effect_id": effect.get("effect_id"),
                                "condition": effect.get("condition"),
                                "source_action_id": effect.get("source_action_id"),
                                "repeat_save": repeat_save_entry,
                            }
                        )
                        continue
                if self._effect_breaks_on_damage(
                    effect,
                    damage_source_actor_id=damage_source_actor_id,
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
                else:
                    retained.append(effect)
            effects[:] = retained
        if repeat_save_removed:
            changes.append(
                {
                    "type": "effect_expired",
                    "target_id": target_id,
                    "trigger": "damage",
                    "reason": "repeat_save_success",
                    "removed": repeat_save_removed,
                    "path": path,
                }
            )
        if removed:
            changes.append(
                {
                    "type": "effect_expired",
                    "target_id": target_id,
                    "trigger": "damage",
                    "removed": removed,
                    "path": path,
                }
            )
        if consumed_next_save:
            next_save_expiry = self._expire_next_saving_throw_disadvantage(target_id, path)
            if next_save_expiry is not None:
                changes.append(next_save_expiry)
        return changes

    def _expire_target_effects_on_incoming_attack(
        self,
        target_id: str,
        path: str,
    ) -> list[dict[str, Any]]:
        removed: list[dict[str, Any]] = []
        for owner_type, owner_id, effects in self._target_effect_lists(target_id):
            retained: list[dict[str, Any]] = []
            for effect in effects:
                modifiers = effect.get("passive_modifiers", {})
                if (
                    isinstance(modifiers, dict)
                    and modifiers.get("incoming_attack_advantage") is True
                    and modifiers.get("consume_on_incoming_attack") is True
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
                else:
                    retained.append(effect)
            effects[:] = retained
        if not removed:
            return []
        return [
            {
                "type": "effect_expired",
                "target_id": target_id,
                "trigger": "incoming_attack",
                "removed": removed,
                "path": path,
            }
        ]

    @staticmethod
    def _effect_break_trigger(ctx: _Context) -> str | None:
        if ctx.action.action_type in {"spell"}:
            return "spell"
        if ctx.action.action_type in ATTACK_ACTION_TYPES:
            return "attack"
        if any(
            change.get("type") == "damage" and int(change.get("applied", 0)) > 0
            for change in ctx.result.state_changes
        ):
            return "damage"
        return None

    def _supreme_sneak_preserves_effect(
        self,
        ctx: _Context,
        effect: dict[str, Any],
        trigger: str,
    ) -> bool:
        if trigger != "attack":
            return False
        cover = self._cunning_strike_stealth_attack_cover(ctx.params)
        if cover not in SUPREME_SNEAK_COVERS:
            return False
        if not self._is_hide_invisible_effect(effect):
            return False
        return any(
            change.get("type") == "cunning_strike" and change.get("effect") == "stealth_attack"
            for change in ctx.result.state_changes
        )

    @staticmethod
    def _effect_breaks_on_trigger(effect: dict[str, Any], trigger: str) -> bool:
        duration = effect.get("duration", {})
        until = str(duration.get("until", "")) if isinstance(duration, dict) else ""
        if not until:
            return False
        if "attack_damage_spell" in until or "attacks_or_deals_damage_or_casts" in until:
            return trigger in {"attack", "damage", "spell"}
        if "attacks_or_casts" in until:
            return trigger in {"attack", "spell"}
        return False

    def _effect_breaks_on_damage(
        self,
        effect: dict[str, Any],
        *,
        damage_source_actor_id: str,
    ) -> bool:
        duration = effect.get("duration", {})
        if not isinstance(duration, dict) or duration.get("break_on_damage") is not True:
            return False
        if duration.get("break_on_damage_by") != "applied_by_or_allies":
            return True
        applied_by = effect.get("applied_by")
        if not isinstance(applied_by, str):
            return False
        return self._same_side_or_same_actor(damage_source_actor_id, applied_by)

    @staticmethod
    def _effect_damage_repeat_save(effect: dict[str, Any]) -> dict[str, Any] | None:
        duration = effect.get("duration", {})
        if not isinstance(duration, dict):
            return None
        repeat_save = duration.get("repeat_save")
        if not isinstance(repeat_save, dict):
            return None
        if repeat_save.get("trigger", effect.get("tick_on")) != "damage":
            return None
        return repeat_save

    def _roll_effect_repeat_save(
        self,
        target_id: str,
        effect: dict[str, Any],
        repeat_save: dict[str, Any],
    ) -> tuple[dict[str, Any], RollResult]:
        save_target_id = str(effect.get("target_id") or target_id)
        target = self._entity(save_target_id)
        ability = str(repeat_save["ability"]).lower()
        base_bonus, proficient, proficiency_sources = self._saving_throw_bonus(target, ability)
        target_exhaustion_level, exhaustion_penalty = self._exhaustion_details(target)
        bonus = base_bonus - exhaustion_penalty
        status_advantage, status_sources = self._saving_throw_status_advantage(
            target,
            ability,
            contexts=set(),
        )
        roll = self.roll_service.roll(d20_expression(bonus), advantage=status_advantage)
        total = roll.total
        dc = int(repeat_save["dc"])
        indomitable_might = self._apply_indomitable_might_to_d20_test(
            self._proficiency_source(target),
            ability,
            total,
            dc,
        )
        if indomitable_might is not None:
            total = int(indomitable_might["total_after"])
        entry: dict[str, Any] = {
            "ability": ability,
            "dc": dc,
            "dc_source": repeat_save.get("dc_source"),
            "base_bonus": base_bonus,
            "bonus": bonus,
            "proficient": proficient,
            "proficiency_sources": proficiency_sources,
            "exhaustion_level": target_exhaustion_level,
            "d20_penalty": exhaustion_penalty,
            "status_advantage": status_advantage,
            "status_sources": status_sources,
            "roll": roll.to_dict(),
            "total": total,
            "success": total >= dc,
        }
        if indomitable_might is not None:
            entry["indomitable_might"] = indomitable_might
        return entry, roll

    def _same_side_or_same_actor(self, actor_id: str, other_actor_id: str) -> bool:
        if self._entity_aliases(actor_id) & self._entity_aliases(other_actor_id):
            return True
        if self.state.encounter is None:
            return False
        actor_combatant = self._combatant_for_aliases(self._entity_aliases(actor_id))
        other_combatant = self._combatant_for_aliases(self._entity_aliases(other_actor_id))
        if actor_combatant is None or other_combatant is None:
            return False
        return actor_combatant.side == other_combatant.side

    def _combatant_for_aliases(self, aliases: set[str]) -> Combatant | None:
        if self.state.encounter is None:
            return None
        for combatant_id, combatant in self.state.encounter.combatants.items():
            if combatant_id in aliases or combatant.entity_id in aliases:
                return combatant
        return None

    def _concentration_save_after_damage(
        self, actor_id: str, damage_taken: int, path: str
    ) -> tuple[dict[str, Any], RollResult] | None:
        if damage_taken <= 0 or not self._actor_has_active_concentration(actor_id):
            return None
        if self._relentless_hunter_protects_concentration(actor_id):
            return None
        actor = self._entity(actor_id)
        dc = max(10, damage_taken // 2)
        base_bonus, proficient, proficiency_sources = self._saving_throw_bonus(actor, "con")
        actor_exhaustion_level, exhaustion_penalty = self._exhaustion_details(actor)
        bonus = base_bonus - exhaustion_penalty
        advantage = None
        advantage_sources: list[dict[str, str]] = []
        owner = self._resource_owner(actor_id)
        if isinstance(owner, Character) and has_warlock_eldritch_mind(owner):
            advantage = "advantage"
            advantage_sources.append(
                {
                    "source_action_id": "srd.eldritch_mind",
                    "modifier": "concentration_save_advantage",
                }
            )
        roll = self.roll_service.roll(d20_expression(bonus), advantage=advantage)
        success = roll.total >= dc
        removed = [] if success else self._clear_existing_concentration(actor_id)
        return (
            {
                "type": "concentration_save",
                "actor_id": actor_id,
                "damage_taken": damage_taken,
                "dc": dc,
                "roll_id": roll.roll_id,
                "bonus": bonus,
                "base_bonus": base_bonus,
                "proficient": proficient,
                "proficiency_sources": proficiency_sources,
                "exhaustion_level": actor_exhaustion_level,
                "d20_penalty": exhaustion_penalty,
                "advantage": advantage,
                "advantage_sources": advantage_sources,
                "total": roll.total,
                "success": success,
                "removed": removed,
                "path": path,
            },
            roll,
        )

    def _relentless_rage_after_drop_to_zero(
        self,
        target_id: str,
        *,
        hp_before: int,
        hp_max: int,
        temp_hp_before: int,
        total_damage_taken: int,
        total_applied: int,
        path: str,
    ) -> tuple[dict[str, Any], list[RollResult]] | None:
        target = self._entity(target_id)
        owner = self._resource_owner(target_id)
        if hp_before <= 0 or int(getattr(target, "hp_current")) != 0 or total_applied <= 0:
            return None
        if bool(getattr(target, "dead", False)):
            return None
        if not isinstance(owner, Character) or not has_relentless_rage(owner):
            return None
        if not has_condition(self._status_effects_for(target), "raging"):
            return None
        hp_damage_after_temp = max(0, int(total_damage_taken) - max(0, int(temp_hp_before)))
        outright_death_threshold = int(hp_before) + int(hp_max)
        if hp_damage_after_temp >= outright_death_threshold:
            return None

        dc = relentless_rage_dc(owner)
        uses_before = max(
            0,
            int(owner.resources.get(RELENTLESS_RAGE_USES_SINCE_REST_RESOURCE, 0)),
        )
        base_bonus, proficient, proficiency_sources = self._saving_throw_bonus(target, "con")
        target_exhaustion_level, exhaustion_penalty = self._exhaustion_details(target)
        bonus = base_bonus - exhaustion_penalty
        status_advantage, status_sources = self._saving_throw_status_advantage(
            target,
            "con",
            contexts=set(),
        )
        roll = self.roll_service.roll(d20_expression(bonus), advantage=status_advantage)
        adjustment, adjustment_rolls, adjustment_sources = self._passive_roll_adjustment(
            target,
            bonus_key="saving_throw_bonus_dice",
            penalty_key="saving_throw_penalty_dice",
        )
        total = roll.total + adjustment
        success = total >= dc
        owner.resources[RELENTLESS_RAGE_USES_SINCE_REST_RESOURCE] = uses_before + 1
        hp_after = int(getattr(target, "hp_current"))
        if success:
            hp_after = relentless_rage_success_hp(owner)
            self._set_hp_and_clear_death_state(target_id, hp_after)
        else:
            self._sync_hp_state_for_target(target)
        return (
            {
                "type": "relentless_rage",
                "target_id": target_id,
                "character_id": owner.id,
                "source_action_id": RELENTLESS_RAGE_ACTION_ID,
                "trigger": "drop_to_0_hp_while_raging",
                "dc": dc,
                "roll_id": roll.roll_id,
                "bonus": bonus,
                "base_bonus": base_bonus,
                "proficient": proficient,
                "proficiency_sources": proficiency_sources,
                "exhaustion_level": target_exhaustion_level,
                "d20_penalty": exhaustion_penalty,
                "base_total": roll.total,
                "passive_adjustment": adjustment,
                "passive_sources": adjustment_sources,
                "status_advantage": status_advantage,
                "status_sources": status_sources,
                "total": total,
                "success": success,
                "hp_before": hp_before,
                "hp_after": hp_after,
                "success_hp": relentless_rage_success_hp(owner),
                "uses_since_rest_before": uses_before,
                "uses_since_rest_after": uses_before + 1,
                "next_dc": dc + 5,
                "path": path,
            },
            [roll, *adjustment_rolls],
        )

    def _set_hp_and_clear_death_state(self, target_id: str, hp_current: int) -> None:
        target = self._entity(target_id)
        if isinstance(target, (Character, Combatant)):
            self._set_death_recovery_state(target, hp_current)
        elif hasattr(target, "hp_current"):
            setattr(target, "hp_current", int(hp_current))
        else:
            return
        if isinstance(target, Combatant) and target.entity_id in self.state.characters:
            character = self.state.characters[target.entity_id]
            self._set_death_recovery_state(character, hp_current)
            self._sync_character_to_combatants(character)
        elif isinstance(target, Character):
            self._sync_character_to_combatants(target)

    def _sync_hp_state_for_target(self, target: Character | Monster | Combatant) -> None:
        if isinstance(target, Combatant) and target.entity_id in self.state.characters:
            self._sync_combatant_to_character(target, self.state.characters[target.entity_id])
        elif isinstance(target, Character):
            self._sync_character_to_combatants(target)

    def _sync_character_to_combatants(self, character: Character) -> None:
        if self.state.encounter is None:
            return
        for combatant in self.state.encounter.combatants.values():
            if combatant.entity_id != character.id:
                continue
            combatant.hp_current = character.hp_current
            combatant.hp_max = character.hp_max
            combatant.temp_hp = character.temp_hp
            combatant.temp_hp_source_effect_id = character.temp_hp_source_effect_id
            combatant.death_save_successes = character.death_save_successes
            combatant.death_save_failures = character.death_save_failures
            combatant.stable = character.stable
            combatant.dead = character.dead

    @staticmethod
    def _sync_combatant_to_character(combatant: Combatant, character: Character) -> None:
        character.hp_current = combatant.hp_current
        character.hp_max = combatant.hp_max
        character.temp_hp = combatant.temp_hp
        character.temp_hp_source_effect_id = combatant.temp_hp_source_effect_id
        character.death_save_successes = combatant.death_save_successes
        character.death_save_failures = combatant.death_save_failures
        character.stable = combatant.stable
        character.dead = combatant.dead

    @staticmethod
    def _set_death_recovery_state(entity: Character | Combatant, hp_current: int) -> None:
        entity.hp_current = int(hp_current)
        entity.death_save_successes = 0
        entity.death_save_failures = 0
        entity.stable = False
        entity.dead = False

    def _relentless_hunter_protects_concentration(self, actor_id: str) -> bool:
        owner = self._resource_owner(actor_id)
        if not isinstance(owner, Character) or not has_relentless_hunter(owner):
            return False
        effects = self._active_concentration_effects(actor_id)
        if not effects:
            return False
        return all(
            effect.get("source_action_id") == FAVORED_ENEMY_HUNTERS_MARK_ACTION_ID
            for effect in effects
        )

    def _active_concentration_effects(self, actor_id: str) -> list[dict[str, Any]]:
        effects: list[dict[str, Any]] = []
        for character in self.state.characters.values():
            effects.extend(
                effect
                for effect in character.status_effects
                if self._effect_is_actor_concentration(effect, actor_id)
            )
        for monster in self.state.monsters.values():
            effects.extend(
                effect
                for effect in monster.status_effects
                if self._effect_is_actor_concentration(effect, actor_id)
            )
        if self.state.encounter is not None:
            for combatant in self.state.encounter.combatants.values():
                effects.extend(
                    effect
                    for effect in combatant.status_effects
                    if self._effect_is_actor_concentration(effect, actor_id)
                )
        effects.extend(
            effect
            for effect in self.state.world.active_effects
            if self._effect_is_actor_concentration(effect, actor_id)
        )
        return effects

    def _actor_has_active_concentration(self, actor_id: str) -> bool:
        for character in self.state.characters.values():
            if any(
                self._effect_is_actor_concentration(effect, actor_id)
                for effect in character.status_effects
            ):
                return True
        for monster in self.state.monsters.values():
            if any(
                self._effect_is_actor_concentration(effect, actor_id)
                for effect in monster.status_effects
            ):
                return True
        if self.state.encounter is not None:
            for combatant in self.state.encounter.combatants.values():
                if any(
                    self._effect_is_actor_concentration(effect, actor_id)
                    for effect in combatant.status_effects
                ):
                    return True
        return any(
            self._effect_is_actor_concentration(effect, actor_id)
            for effect in self.state.world.active_effects
        )

    @staticmethod
    def _effect_is_actor_concentration(effect: dict[str, Any], actor_id: str) -> bool:
        metadata = effect.get("metadata", {})
        metadata_concentration = isinstance(metadata, dict) and bool(metadata.get("concentration"))
        duration = effect.get("duration", {})
        duration_until = duration.get("until") if isinstance(duration, dict) else None
        duration_concentration = isinstance(duration_until, str) and duration_until.startswith(
            "concentration_"
        )
        return effect.get("applied_by") == actor_id and bool(
            effect.get("concentration", metadata_concentration or duration_concentration)
        )

    @staticmethod
    def _node_requires_concentration(node: dict[str, Any]) -> bool:
        metadata = node.get("metadata", {})
        metadata_concentration = isinstance(metadata, dict) and bool(metadata.get("concentration"))
        duration = node.get("duration", {})
        duration_until = duration.get("until") if isinstance(duration, dict) else None
        duration_concentration = isinstance(duration_until, str) and duration_until.startswith(
            "concentration_"
        )
        return bool(node.get("concentration", metadata_concentration or duration_concentration))

    def _apply_damage(
        self,
        target_id: str,
        amount: int,
        damage_type: str,
        *,
        ctx: _Context,
        path: str,
    ) -> int:
        target = self._entity(target_id)
        adjusted = self._mitigated_damage(target, amount, damage_type)
        temp_hp = int(getattr(target, "temp_hp", 0))
        absorbed = min(temp_hp, adjusted)
        setattr(target, "temp_hp", temp_hp - absorbed)
        if int(getattr(target, "temp_hp", 0)) == 0:
            self._clear_temp_hp_source(target_id, target)
        remaining = adjusted - absorbed
        before = int(getattr(target, "hp_current"))
        setattr(target, "hp_current", max(0, before - remaining))
        death_ward = self._death_ward_after_drop_to_zero(
            target_id,
            hp_before=before,
            hp_after_without_death_ward=int(getattr(target, "hp_current")),
            path=path,
        )
        if death_ward is not None:
            ctx.result.state_changes.append(death_ward)
        return before - int(getattr(target, "hp_current"))

    def _set_temp_hp_source(
        self,
        target_id: str,
        target: Character | Monster | Combatant,
        effect_id: str,
    ) -> None:
        setattr(target, "temp_hp_source_effect_id", effect_id)
        if isinstance(target, Combatant) and target.entity_id in self.state.characters:
            self.state.characters[target.entity_id].temp_hp_source_effect_id = effect_id
        elif target_id in self.state.characters:
            self.state.characters[target_id].temp_hp_source_effect_id = effect_id

    def _clear_temp_hp_source(
        self,
        target_id: str,
        target: Character | Monster | Combatant,
    ) -> None:
        setattr(target, "temp_hp_source_effect_id", None)
        if isinstance(target, Combatant) and target.entity_id in self.state.characters:
            self.state.characters[target.entity_id].temp_hp_source_effect_id = None
        elif target_id in self.state.characters:
            self.state.characters[target_id].temp_hp_source_effect_id = None

    def _dark_ones_blessing_changes(
        self,
        reducer_id: str,
        target_id: str,
        path: str,
    ) -> list[dict[str, Any]]:
        changes: list[dict[str, Any]] = []
        for warlock_id in self._dark_ones_blessing_recipient_ids(reducer_id, target_id):
            owner = self._resource_owner(warlock_id)
            if not isinstance(owner, Character):
                continue
            amount = dark_ones_blessing_temp_hp(owner)
            if amount <= 0:
                continue
            before = int(getattr(owner, "temp_hp", 0))
            after = max(before, amount)
            owner.temp_hp = after
            if after > before:
                owner.temp_hp_source_effect_id = None
            if self.state.encounter is not None:
                for combatant in self.state.encounter.combatants.values():
                    if combatant.id == warlock_id or combatant.entity_id == owner.id:
                        combatant.temp_hp = after
                        if after > before:
                            combatant.temp_hp_source_effect_id = None
            changes.append(
                {
                    "type": "temp_hp",
                    "target_id": warlock_id,
                    "before": before,
                    "after": after,
                    "amount": amount,
                    "path": path,
                    "source_action_id": "srd.dark_ones_blessing",
                    "trigger": "enemy_reduced_to_0_hp",
                    "reducer_id": reducer_id,
                    "reduced_enemy_id": target_id,
                }
            )
        return changes

    def _dark_ones_blessing_recipient_ids(
        self,
        reducer_id: str,
        target_id: str,
    ) -> list[str]:
        if self.state.encounter is None:
            return [reducer_id] if self._is_fiend_warlock_actor(reducer_id) else []
        target = self.state.encounter.combatants.get(target_id)
        if target is None:
            return [reducer_id] if self._is_fiend_warlock_actor(reducer_id) else []
        recipients: list[str] = []
        for combatant_id, combatant in self.state.encounter.combatants.items():
            if combatant.hp_current <= 0:
                continue
            if not self._is_fiend_warlock_actor(combatant_id):
                continue
            if combatant.side == target.side:
                continue
            if self._actor_matches_combatant(reducer_id, combatant):
                recipients.append(combatant_id)
                continue
            distance = self._combat_distance(combatant, target)
            if distance is not None and distance <= 10:
                recipients.append(combatant_id)
        return sorted(set(recipients))

    def _is_fiend_warlock_actor(self, actor_id: str) -> bool:
        actor = self._resource_owner(actor_id)
        return isinstance(actor, Character) and dark_ones_blessing_temp_hp(actor) > 0

    @staticmethod
    def _actor_matches_combatant(actor_id: str, combatant: Combatant) -> bool:
        return actor_id == combatant.id or actor_id == combatant.entity_id

    def _mitigated_damage(
        self,
        target: Character | Monster | Combatant,
        amount: int,
        damage_type: str,
    ) -> int:
        if damage_type in getattr(
            target, "immunities", []
        ) or self._passive_damage_immunity_sources(
            target,
            damage_type,
        ):
            return 0
        if (
            damage_type in getattr(target, "resistances", [])
            or self._has_condition(target, "petrified")
            or self._passive_damage_resistance_sources(target, damage_type)
        ):
            return amount // 2
        if damage_type in getattr(target, "vulnerabilities", []):
            return amount * 2
        return amount

    def _passive_damage_immunity_sources(
        self,
        target: Character | Monster | Combatant,
        damage_type: str,
    ) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        for effect in self._status_effects_for(target):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            immunities = _string_set(modifiers.get("damage_immunities"))
            if damage_type in immunities:
                sources.append(
                    {
                        "effect_id": effect.get("effect_id"),
                        "source_action_id": effect.get("source_action_id"),
                        "modifier": "damage_immunities",
                        "damage_type": damage_type,
                    }
                )
        return sources

    def _has_condition(self, target: Character | Monster | Combatant, condition: str) -> bool:
        return any(
            effect.get("condition") == condition for effect in self._status_effects_for(target)
        )

    def _condition_immunity_sources(
        self,
        target: Character | Monster | Combatant,
        condition: str,
    ) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        if condition == "frightened":
            sources.extend(
                self._paladin_aura_condition_immunity_sources(
                    target,
                    condition="frightened",
                    source_action_id=AURA_OF_COURAGE_ACTION_ID,
                    modifier="aura_of_courage",
                )
            )
        if condition == "charmed":
            sources.extend(
                self._paladin_aura_condition_immunity_sources(
                    target,
                    condition="charmed",
                    source_action_id=AURA_OF_DEVOTION_ACTION_ID,
                    modifier="aura_of_devotion",
                )
            )
        if condition == "poisoned":
            sources.extend(self._condition_sources(target, {"petrified"}))
            owner = target
            if isinstance(target, Combatant) and target.entity_id in self.state.characters:
                owner = self.state.characters[target.entity_id]
            if isinstance(owner, Character) and has_druid_circle_of_the_land_feature(
                owner,
                level=10,
            ):
                sources.append(
                    {
                        "source_action_id": "srd.natures_ward",
                        "modifier": "druid_natures_ward_poisoned_immunity",
                        "immune_condition": condition,
                    }
                )
        for effect in self._status_effects_for(target):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            immunities = _string_set(modifiers.get("condition_immunities"))
            if condition in immunities:
                sources.append(
                    {
                        "condition": effect.get("condition"),
                        "effect_id": effect.get("effect_id"),
                        "source_action_id": effect.get("source_action_id"),
                        "modifier": "condition_immunities",
                        "immune_condition": condition,
                    }
                )
        return sources

    def _paladin_aura_condition_immunity_sources(
        self,
        target: Character | Monster | Combatant,
        *,
        condition: str,
        source_action_id: str,
        modifier: str,
    ) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        target_combatant = target if isinstance(target, Combatant) else self._combatant_for(target)
        if self.state.encounter is not None and target_combatant is not None:
            for paladin in self.state.encounter.combatants.values():
                if paladin.entity_id not in self.state.characters:
                    continue
                if paladin.side != target_combatant.side:
                    continue
                owner = self.state.characters[paladin.entity_id]
                if not self._paladin_aura_immunity_applies(
                    owner,
                    source_action_id=source_action_id,
                ):
                    continue
                radius_ft = aura_of_protection_radius_ft(owner)
                if self._condition_sources(paladin, {"incapacitated"}):
                    continue
                distance = (
                    0
                    if paladin.id == target_combatant.id
                    else self._combat_distance(paladin, target_combatant)
                )
                if distance is None or distance > radius_ft:
                    continue
                sources.append(
                    {
                        "source_action_id": source_action_id,
                        "modifier": modifier,
                        "source_actor_id": paladin.id,
                        "target_id": target_combatant.id,
                        "distance_ft": distance,
                        "radius_ft": radius_ft,
                        "immune_condition": condition,
                    }
                )
        elif (
            isinstance(target, Character)
            and self._paladin_aura_immunity_applies(
                target,
                source_action_id=source_action_id,
            )
            and not has_condition(target.status_effects, "incapacitated")
        ):
            sources.append(
                {
                    "source_action_id": source_action_id,
                    "modifier": modifier,
                    "source_actor_id": target.id,
                    "target_id": target.id,
                    "immune_condition": condition,
                }
            )
        return sources

    @staticmethod
    def _paladin_aura_immunity_applies(
        owner: Character,
        *,
        source_action_id: str,
    ) -> bool:
        if source_action_id == AURA_OF_COURAGE_ACTION_ID:
            return has_paladin_feature(owner, level=10)
        if source_action_id == AURA_OF_DEVOTION_ACTION_ID:
            return aura_of_devotion_applies(owner)
        return False

    def _apply_mindless_rage_if_available(
        self,
        ctx: _Context,
        node: dict[str, Any],
        target_id: str,
        passive_modifiers: dict[str, Any],
        path: str,
    ) -> dict[str, Any] | None:
        if ctx.action.id != RAGE_ACTION_ID or node.get("condition") != "raging":
            return None
        if target_id != ctx.actor_id:
            return None
        actor = self._resource_owner(ctx.actor_id)
        if not isinstance(actor, Character) or not has_barbarian_berserker_feature(
            actor,
            level=6,
        ):
            return None
        existing = _string_set(passive_modifiers.get("condition_immunities"))
        passive_modifiers["condition_immunities"] = sorted(
            existing | set(MINDLESS_RAGE_CONDITION_IMMUNITIES)
        )
        removed_conditions, removed_owners = self._remove_conditions_for_target(
            target_id,
            list(MINDLESS_RAGE_CONDITION_IMMUNITIES),
        )
        return {
            "type": "mindless_rage",
            "target_id": target_id,
            "source_action_id": MINDLESS_RAGE_ACTION_ID,
            "condition_immunities": list(MINDLESS_RAGE_CONDITION_IMMUNITIES),
            "removed": removed_conditions,
            "removed_owners": removed_owners,
            "path": path,
        }

    def _apply_persistent_rage_if_available(
        self,
        ctx: _Context,
        node: dict[str, Any],
        target_id: str,
        passive_modifiers: dict[str, Any],
        duration: dict[str, Any],
        path: str,
    ) -> dict[str, Any] | None:
        if ctx.action.id != RAGE_ACTION_ID or node.get("condition") != "raging":
            return None
        if target_id != ctx.actor_id:
            return None
        actor = self._resource_owner(ctx.actor_id)
        if not isinstance(actor, Character) or not persistent_rage_applies(actor):
            return None
        duration.clear()
        duration["until"] = "duration_10_minutes"
        passive_modifiers["ends_if_condition"] = "unconscious"
        passive_modifiers["ends_if_heavy_armor"] = True
        return {
            "type": "persistent_rage",
            "target_id": target_id,
            "source_action_id": PERSISTENT_RAGE_ACTION_ID,
            "rage_duration": "duration_10_minutes",
            "ends_if_condition": "unconscious",
            "ends_if_heavy_armor": True,
            "path": path,
        }

    def _apply_healing(self, target_id: str, amount: int) -> int:
        target = self._entity(target_id)
        before = int(getattr(target, "hp_current"))
        max_hp = int(getattr(target, "hp_max"))
        setattr(target, "hp_current", min(max_hp, before + amount))
        return int(getattr(target, "hp_current")) - before

    def _disciple_of_life_bonus(self, ctx: _Context) -> int:
        if ctx.action.action_type != "spell":
            return 0
        if ctx.action.cost.spell_slot_level is None:
            return 0
        actor = self._resource_owner(ctx.actor_id)
        if not isinstance(actor, Character):
            return 0
        return disciple_of_life_healing_bonus(
            actor,
            spell_slot_level=self._spell_slot_level_to_spend(ctx.action, ctx.params),
        )

    def _blessed_healer_bonus(self, ctx: _Context) -> int:
        if ctx.action.action_type != "spell":
            return 0
        if ctx.action.cost.spell_slot_level is None or bool(ctx.params.get("as_ritual", False)):
            return 0
        actor = self._resource_owner(ctx.actor_id)
        if not isinstance(actor, Character):
            return 0
        return blessed_healer_self_healing(
            actor,
            spell_slot_level=self._spell_slot_level_to_spend(ctx.action, ctx.params),
        )

    def _validate_hunters_lore_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        targets: list[str],
    ) -> None:
        if action.id != HUNTERS_LORE_ACTION_ID:
            return
        actor = self._resource_owner(actor_id)
        if not isinstance(actor, Character) or not has_ranger_hunter_feature(actor, level=3):
            raise AutomationError("Hunter's Lore requires Ranger Hunter level 3")
        for target_id in targets:
            if not self._target_marked_by_hunters_mark(actor_id, target_id):
                raise AutomationError(
                    "Hunter's Lore requires a target marked by your Hunter's Mark"
                )

    def _target_marked_by_hunters_mark(self, actor_id: str, target_id: str) -> bool:
        target = self._entity(target_id)
        for effect in self._status_effects_for(target):
            if effect.get("applied_by") != actor_id:
                continue
            modifiers = effect.get("passive_modifiers", {})
            if isinstance(modifiers, dict) and modifiers.get("hunters_mark") is True:
                return True
        return False

    def _validate_horde_breaker_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        targets: list[str],
        params: dict[str, Any],
    ) -> None:
        if params.get("use_horde_breaker") is not True:
            return
        if action.action_type != "weapon_attack":
            raise AutomationError("Horde Breaker requires a weapon attack")
        actor_owner = self._resource_owner(actor_id)
        if not isinstance(actor_owner, Character) or not has_horde_breaker(actor_owner):
            raise AutomationError("Horde Breaker requires the Ranger Hunter Horde Breaker option")
        if self._has_horde_breaker_used(actor_id):
            raise AutomationError("Horde Breaker can be used only once per turn")
        if len(targets) != 1:
            raise AutomationError("Horde Breaker requires exactly one original attack target")
        target_id = params.get("horde_breaker_target_id")
        if target_id is None:
            raise AutomationError("Horde Breaker requires horde_breaker_target_id")
        horde_target_id = str(target_id)
        original_target_id = targets[0]
        if horde_target_id == original_target_id:
            raise AutomationError("Horde Breaker target must be a different creature")
        self._entity(horde_target_id)
        if self._has_attacked_target_this_turn(actor_id, horde_target_id):
            raise AutomationError("Horde Breaker target was already attacked this turn")
        actor = self._entity(actor_id)
        original_target = self._entity(original_target_id)
        horde_target = self._entity(horde_target_id)
        if not (
            isinstance(actor, Combatant)
            and isinstance(original_target, Combatant)
            and isinstance(horde_target, Combatant)
        ):
            raise AutomationError("Horde Breaker requires tactical combat targets")
        target_distance = self._combat_distance(original_target, horde_target)
        if target_distance is None or target_distance > 5:
            raise AutomationError(
                "Horde Breaker target must be within 5 feet of the original target"
            )
        weapon_range = action.range.get("normal_ft")
        if weapon_range is None:
            raise AutomationError("Horde Breaker requires a weapon range")
        actor_distance = self._combat_distance(actor, horde_target)
        if actor_distance is None or actor_distance > int(weapon_range):
            raise AutomationError("Horde Breaker target must be within the weapon's range")

    def _validate_blessed_strikes_divine_strike_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        targets: list[str],
        params: dict[str, Any],
    ) -> None:
        if not self._blessed_strikes_divine_strike_requested(params):
            return
        actor_owner = self._resource_owner(actor_id)
        if not isinstance(actor_owner, Character) or not has_cleric_blessed_strikes_divine_strike(
            actor_owner
        ):
            raise AutomationError(
                "Blessed Strikes Divine Strike requires Cleric 7 with the Divine Strike option"
            )
        if action.action_type != "weapon_attack":
            raise AutomationError("Blessed Strikes Divine Strike requires a weapon attack")
        if self._has_blessed_strikes_divine_strike_used(actor_id):
            raise AutomationError("Blessed Strikes Divine Strike can be used only once per turn")
        target_id = self._blessed_strikes_divine_strike_target_id(targets, params)
        if target_id is None:
            raise AutomationError("Blessed Strikes Divine Strike requires a single attack target")
        if target_id not in {str(target) for target in targets}:
            raise AutomationError("Blessed Strikes Divine Strike target must be an attack target")
        self._entity(target_id)
        self._blessed_strikes_divine_strike_damage_type(params)

    def _validate_improved_blessed_strikes_potent_spellcasting_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        params: dict[str, Any],
    ) -> None:
        target_id = self._improved_blessed_strikes_temp_hp_target_id(params)
        if target_id is None:
            return
        actor_owner = self._resource_owner(actor_id)
        if not isinstance(actor_owner, Character):
            raise AutomationError(
                "Improved Blessed Strikes Potent Spellcasting requires Cleric 14"
            )
        if not (
            has_cleric_improved_blessed_strikes(actor_owner)
            and has_cleric_blessed_strikes_potent_spellcasting(actor_owner)
        ):
            raise AutomationError(
                "Improved Blessed Strikes Potent Spellcasting requires Cleric 14 with the Potent Spellcasting option"
            )
        if action.action_type != "spell" or not self._action_is_cleric_cantrip(action):
            raise AutomationError(
                "Improved Blessed Strikes Potent Spellcasting requires a Cleric cantrip"
            )
        self._entity(target_id)
        if not self._improved_blessed_strikes_temp_hp_target_in_range(actor_id, target_id):
            raise AutomationError(
                "Improved Blessed Strikes Potent Spellcasting target must be within 60 feet"
            )

    @staticmethod
    def _blessed_strikes_divine_strike_requested(params: dict[str, Any]) -> bool:
        return (
            params.get("use_blessed_strikes_divine_strike") is True
            or params.get("use_divine_strike") is True
        )

    @staticmethod
    def _blessed_strikes_divine_strike_target_id(
        targets: list[str],
        params: dict[str, Any],
    ) -> str | None:
        selected = params.get(
            "blessed_strikes_target_id",
            params.get("divine_strike_target_id"),
        )
        if selected not in (None, "", False):
            if isinstance(selected, (dict, list)):
                raise AutomationError("parameter divine_strike_target_id must be a scalar")
            return str(selected)
        if len(targets) == 1:
            return str(targets[0])
        return None

    @staticmethod
    def _blessed_strikes_divine_strike_damage_type(params: dict[str, Any]) -> str:
        raw = params.get(
            "divine_strike_damage_type",
            params.get("blessed_strikes_damage_type"),
        )
        if raw in (None, "", False):
            raise AutomationError(
                "Blessed Strikes Divine Strike requires divine_strike_damage_type radiant or necrotic"
            )
        if isinstance(raw, (dict, list)):
            raise AutomationError("divine_strike_damage_type must be a scalar")
        damage_type = str(raw).casefold().strip()
        if damage_type not in {"necrotic", "radiant"}:
            raise AutomationError("divine_strike_damage_type must be radiant or necrotic")
        return damage_type

    @staticmethod
    def _improved_blessed_strikes_temp_hp_target_id(params: dict[str, Any]) -> str | None:
        raw = params.get(
            "improved_blessed_strikes_temp_hp_target_id",
            params.get(
                "potent_spellcasting_temp_hp_target_id",
                params.get("blessed_strikes_temp_hp_target_id"),
            ),
        )
        if raw in (None, "", False):
            return None
        if isinstance(raw, (dict, list)):
            raise AutomationError("improved_blessed_strikes_temp_hp_target_id must be a scalar")
        return str(raw)

    def _improved_blessed_strikes_temp_hp_target_in_range(
        self,
        actor_id: str,
        target_id: str,
    ) -> bool:
        if self._entity_ids_match(actor_id, target_id):
            return True
        actor = self._combatant_for(self._entity(actor_id))
        target = self._combatant_for(self._entity(target_id))
        if actor is None or target is None:
            return False
        distance = self._combat_distance(actor, target)
        return distance is not None and distance <= 60

    def _validate_cutting_words_preconditions(
        self,
        action: ActionDefinition,
        params: dict[str, Any],
    ) -> None:
        if action.id != CUTTING_WORDS_ACTION_ID:
            return
        self._cutting_words_trigger(params)

    @staticmethod
    def _cutting_words_trigger(params: dict[str, Any]) -> dict[str, Any]:
        raw_roll_type = params.get("cutting_words_roll_type")
        roll_type = str(raw_roll_type).lower().strip() if raw_roll_type is not None else ""
        roll_type = {
            "damage": "damage_roll",
            "damage_roll": "damage_roll",
            "ability": "ability_check",
            "ability_check": "ability_check",
            "attack": "attack_roll",
            "attack_roll": "attack_roll",
        }.get(roll_type, "")
        if roll_type not in {"damage_roll", "ability_check", "attack_roll"}:
            raise AutomationError(
                "Cutting Words roll type must be damage_roll, ability_check, or attack_roll"
            )
        roll_total = AutomationExecutor._required_int_param(
            params,
            "cutting_words_roll_total",
        )
        if roll_type == "damage_roll":
            if roll_total <= 0:
                raise AutomationError("Cutting Words damage roll must be positive")
            return {"roll_type": roll_type, "roll_total": roll_total}
        original_success = params.get("cutting_words_original_success")
        if isinstance(original_success, bool):
            if not original_success:
                raise AutomationError("Cutting Words requires a successful roll")
            success_threshold = AutomationExecutor._optional_int_param(
                params,
                "cutting_words_success_threshold",
            )
            return {
                "roll_type": roll_type,
                "roll_total": roll_total,
                "success_threshold": success_threshold,
            }
        success_threshold = AutomationExecutor._cutting_words_success_threshold(
            params,
            roll_type,
        )
        if roll_total < success_threshold:
            raise AutomationError("Cutting Words requires a successful roll")
        return {
            "roll_type": roll_type,
            "roll_total": roll_total,
            "success_threshold": success_threshold,
        }

    @staticmethod
    def _cutting_words_success_threshold(
        params: dict[str, Any],
        roll_type: str,
    ) -> int:
        threshold = AutomationExecutor._optional_int_param(
            params,
            "cutting_words_success_threshold",
        )
        if threshold is not None:
            return threshold
        if roll_type == "ability_check":
            threshold = AutomationExecutor._optional_int_param(params, "cutting_words_dc")
        else:
            threshold = AutomationExecutor._optional_int_param(params, "cutting_words_target_ac")
        if threshold is None:
            raise AutomationError("Cutting Words requires a success threshold")
        return threshold

    @staticmethod
    def _required_int_param(params: dict[str, Any], param_name: str) -> int:
        value = AutomationExecutor._optional_int_param(params, param_name)
        if value is None:
            raise AutomationError(f"missing required parameter {param_name}")
        return value

    @staticmethod
    def _required_bool_param(params: dict[str, Any], param_name: str) -> bool:
        if param_name not in params:
            raise AutomationError(f"missing required parameter {param_name}")
        value = params[param_name]
        if not isinstance(value, bool):
            raise AutomationError(f"parameter {param_name} must be a boolean")
        return value

    @staticmethod
    def _optional_int_param(params: dict[str, Any], param_name: str) -> int | None:
        if param_name not in params:
            return None
        value = params[param_name]
        if isinstance(value, bool):
            raise AutomationError(f"parameter {param_name} must be an integer")
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise AutomationError(f"parameter {param_name} must be an integer") from exc

    def _bardic_inspiration_die(self, actor_id: str) -> str:
        owner = self._resource_owner(actor_id)
        class_levels = getattr(owner, "class_levels", {})
        bard_level = int(class_levels.get("bard", 0)) if isinstance(class_levels, dict) else 0
        if bard_level >= 15:
            return "d12"
        if bard_level >= 10:
            return "d10"
        if bard_level >= 5:
            return "d8"
        return "d6"

    def _validate_natures_sanctuary_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        params: dict[str, Any],
    ) -> None:
        sanctuary_nodes = [
            node
            for node in self._automation_nodes(action.automation)
            if node.get("type") in {"natures_sanctuary", "natures_sanctuary_move"}
        ]
        if not sanctuary_nodes:
            return
        actor = self._resource_owner(actor_id)
        if not isinstance(actor, Character):
            raise AutomationError("Nature's Sanctuary requires a character owner")
        for node in sanctuary_nodes:
            node_type = str(node.get("type"))
            destination = self._natures_sanctuary_destination(params, node)
            origin_position: str | None = None
            if node_type == "natures_sanctuary_move":
                effect = self._active_natures_sanctuary_effect(actor_id)
                if effect is None:
                    raise AutomationError("Nature's Sanctuary requires an active Cube")
                origin_position = self._natures_sanctuary_effect_position(effect)
                if origin_position is None:
                    raise AutomationError("Nature's Sanctuary active Cube has no position")
            self._validate_natures_sanctuary_tactical_position(
                actor_id=actor_id,
                node_type=node_type,
                destination=destination,
                origin_position=origin_position,
            )

    @staticmethod
    def _natures_sanctuary_destination(
        params: dict[str, Any],
        node: dict[str, Any],
    ) -> str:
        param_name = str(node.get("destination_param", "natures_sanctuary_position_node_id"))
        selected = params.get(param_name)
        if selected is None:
            raise AutomationError(f"missing required parameter {param_name}")
        if isinstance(selected, (dict, list, bool)):
            raise AutomationError(f"parameter {param_name} must be a scalar")
        destination = str(selected)
        if not destination:
            raise AutomationError(f"parameter {param_name} must be non-empty")
        return destination

    def _active_natures_sanctuary_effect(self, actor_id: str) -> dict[str, Any] | None:
        for effect in reversed(self.state.world.active_effects):
            if not isinstance(effect, dict):
                continue
            if effect.get("effect_type") != "natures_sanctuary":
                continue
            if effect.get("applied_by") != actor_id:
                continue
            return effect
        return None

    @staticmethod
    def _natures_sanctuary_effect_position(effect: dict[str, Any]) -> str | None:
        scope = effect.get("scope")
        if isinstance(scope, dict):
            position = scope.get("position_node_id")
            if isinstance(position, str) and position:
                return position
        metadata = effect.get("metadata")
        if isinstance(metadata, dict):
            position = metadata.get("position_node_id")
            if isinstance(position, str) and position:
                return position
        return None

    def _validate_natures_sanctuary_tactical_position(
        self,
        *,
        actor_id: str,
        node_type: str,
        destination: str,
        origin_position: str | None,
    ) -> None:
        if self.state.encounter is None or self.state.encounter.tactical_graph is None:
            return
        actor = self.state.encounter.combatants.get(actor_id)
        if actor is None or actor.position_node_id is None:
            return
        graph = TacticalGraph.from_dict(self.state.encounter.tactical_graph)
        if destination not in graph.nodes:
            raise AutomationError("Nature's Sanctuary destination position does not exist")
        actor_distance = graph.shortest_distance(actor.position_node_id, destination)
        if actor_distance is None or int(actor_distance) > 120:
            raise AutomationError(
                "Nature's Sanctuary destination must be within 120 feet of the Druid"
            )
        if node_type != "natures_sanctuary_move":
            return
        if origin_position is None:
            raise AutomationError("Nature's Sanctuary active Cube has no position")
        if origin_position not in graph.nodes:
            raise AutomationError("Nature's Sanctuary active Cube position does not exist")
        move_distance = graph.shortest_distance(origin_position, destination)
        if move_distance is None or int(move_distance) > 60:
            raise AutomationError("Nature's Sanctuary move cannot exceed 60 feet")

    @staticmethod
    def _validate_sacred_weapon_preconditions(
        action: ActionDefinition,
        params: dict[str, Any],
    ) -> None:
        if action.id != SACRED_WEAPON_ACTION_ID:
            return
        selected = params.get("sacred_weapon_action_id")
        if selected is None:
            raise AutomationError("missing required parameter sacred_weapon_action_id")
        if isinstance(selected, (dict, list)):
            raise AutomationError("parameter sacred_weapon_action_id must be a scalar")
        if not str(selected):
            raise AutomationError("parameter sacred_weapon_action_id must be non-empty")

    @staticmethod
    def _validate_oil_of_sharpness_preconditions(
        action: ActionDefinition,
        params: dict[str, Any],
    ) -> None:
        if action.id != OIL_OF_SHARPNESS_ACTION_ID:
            return
        selected = params.get("oil_of_sharpness_action_id")
        if selected is None:
            raise AutomationError("missing required parameter oil_of_sharpness_action_id")
        if isinstance(selected, (dict, list)):
            raise AutomationError("parameter oil_of_sharpness_action_id must be a scalar")
        selected_action_id = str(selected)
        if not selected_action_id:
            raise AutomationError("parameter oil_of_sharpness_action_id must be non-empty")
        allowed = action.properties.get("allowed_weapon_action_ids", [])
        allowed_ids = (
            {str(action_id) for action_id in allowed} if isinstance(allowed, list) else set()
        )
        if selected_action_id not in allowed_ids:
            raise AutomationError(
                "Oil of Sharpness requires an implemented nonmagical Slashing or Piercing melee weapon"
            )

    def _prepare_size_based_oil_vial_cost(
        self,
        action: ActionDefinition,
        targets: list[str],
        params: dict[str, Any],
    ) -> None:
        cost_param = {
            OIL_OF_ETHEREALNESS_ACTION_ID: "oil_of_etherealness_vials",
            APPLY_OIL_OF_SLIPPERINESS_ACTION_ID: "oil_of_slipperiness_vials",
        }.get(action.id)
        if cost_param is None:
            return
        if len(targets) != 1:
            raise AutomationError(f"{action.name} requires exactly one target")
        target = self._entity(targets[0])
        params[cost_param] = self._size_based_oil_vials_required(target)

    @staticmethod
    def _size_based_oil_vials_required(target: Character | Monster | Combatant) -> int:
        size = str(getattr(target, "size", "medium")).casefold()
        rank = CREATURE_SIZE_RANKS.get(size, CREATURE_SIZE_RANKS["medium"])
        return 1 + max(0, rank - CREATURE_SIZE_RANKS["medium"])

    def _validate_rod_of_absorption_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        params: dict[str, Any],
    ) -> None:
        if action.properties.get("rod_of_absorption_initialize") is True:
            actor = self._resource_owner(actor_id)
            if (
                isinstance(actor, Character)
                and int(actor.resources.get(ROD_OF_ABSORPTION_INITIALIZED_RESOURCE, 0)) > 0
            ):
                raise AutomationError("Rod of Absorption energy is already initialized")
            return
        if action.properties.get("rod_of_absorption_absorb_spell") is True:
            actor = self._resource_owner(actor_id)
            if not isinstance(actor, Character):
                raise AutomationError("Rod of Absorption requires a character owner")
            spell_level_param = str(
                action.properties.get("spell_level_param", "absorbed_spell_level")
            )
            spell_level = self._required_int_param(params, spell_level_param)
            if spell_level < 0 or spell_level > 9:
                raise AutomationError("Rod of Absorption absorbed spell level must be 0-9")
            self._validate_rod_of_absorption_spell_can_be_absorbed(
                actor,
                spell_level=spell_level,
                targeting_only_you=self._required_bool_param(
                    params,
                    str(action.properties.get("targeting_only_you_param", "targeting_only_you")),
                ),
                creates_area_of_effect=self._required_bool_param(
                    params,
                    str(
                        action.properties.get(
                            "creates_area_of_effect_param",
                            "creates_area_of_effect",
                        )
                    ),
                ),
            )

    @staticmethod
    def _validate_rod_of_absorption_spell_can_be_absorbed(
        actor: Character,
        *,
        spell_level: int,
        targeting_only_you: bool,
        creates_area_of_effect: bool,
    ) -> None:
        if not targeting_only_you:
            raise AutomationError("Rod of Absorption can absorb only a spell targeting only you")
        if creates_area_of_effect:
            raise AutomationError("Rod of Absorption cannot absorb an area-of-effect spell")
        lifetime_before = int(actor.resources.get(ROD_OF_ABSORPTION_LIFETIME_ABSORBED_RESOURCE, 0))
        if lifetime_before + spell_level > ROD_OF_ABSORPTION_LIFETIME_CAP:
            raise AutomationError("Rod of Absorption cannot store that spell level")

    def _validate_rod_of_alertness_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        targets: list[str],
    ) -> None:
        if action.properties.get("rod_of_alertness_protective_aura") is not True:
            return
        actor = self._resource_owner(actor_id)
        if not isinstance(actor, Character):
            raise AutomationError("Rod of Alertness requires a character owner")
        if int(actor.resources.get(ROD_OF_ALERTNESS_PROTECTIVE_AURA_USED_RESOURCE, 0)) > 0:
            raise AutomationError(
                "Rod of Alertness Protective Aura can't be used again until the next dawn"
            )
        if self.state.encounter is None:
            return
        actor_combatant = self.state.encounter.combatants.get(actor_id)
        if actor_combatant is None:
            return
        actor_aliases = self._entity_aliases(actor_id)
        for target_id in targets:
            if target_id in actor_aliases:
                continue
            target = self.state.encounter.combatants.get(target_id)
            if target is not None and target.side == actor_combatant.side:
                continue
            raise AutomationError(
                "Rod of Alertness Protective Aura affects only you and your allies"
            )

    def _validate_robe_of_useful_items_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        params: dict[str, Any],
    ) -> None:
        if action.properties.get("robe_of_useful_items_initialize") is True:
            actor = self._resource_owner(actor_id)
            if (
                isinstance(actor, Character)
                and int(actor.resources.get(ROBE_OF_USEFUL_ITEMS_INITIALIZED_RESOURCE, 0)) > 0
            ):
                raise AutomationError("Robe of Useful Items patches are already initialized")
            return
        if action.properties.get("robe_of_useful_items_detach_patch") is not True:
            return
        actor = self._resource_owner(actor_id)
        if not isinstance(actor, Character):
            raise AutomationError("Robe of Useful Items requires a character owner")
        patch_param = str(action.properties.get("patch_param", "robe_of_useful_items_patch"))
        selected = params.get(patch_param)
        if selected is None:
            raise AutomationError(f"missing required parameter {patch_param}")
        if isinstance(selected, (dict, list)):
            raise AutomationError(f"parameter {patch_param} must be a scalar")
        patch_key = str(selected).lower()
        allowed = action.properties.get("robe_of_useful_items_patch_keys", [])
        allowed_keys = {str(key) for key in allowed} if isinstance(allowed, list) else set()
        if patch_key not in allowed_keys:
            raise AutomationError("Robe of Useful Items patch is not in the SRD patch table")
        resource = self._robe_of_useful_items_patch_resource(patch_key)
        if int(actor.resources.get(resource, 0)) <= 0:
            raise AutomationError(f"Robe of Useful Items patch {patch_key} is unavailable")

    @staticmethod
    def _validate_pact_of_blade_weapon_preconditions(
        action: ActionDefinition,
        params: dict[str, Any],
    ) -> None:
        if action.id != PACT_OF_BLADE_WEAPON_ACTION_ID:
            return
        selected = params.get("pact_weapon_action_id")
        if selected is None:
            raise AutomationError("missing required parameter pact_weapon_action_id")
        if isinstance(selected, (dict, list)):
            raise AutomationError("parameter pact_weapon_action_id must be a scalar")
        selected_action_id = str(selected)
        if not selected_action_id:
            raise AutomationError("parameter pact_weapon_action_id must be non-empty")
        if selected_action_id not in WARLOCK_PACT_OF_BLADE_WEAPON_ACTION_IDS:
            raise AutomationError(
                "Pact of the Blade weapon must be an implemented SRD melee weapon"
            )

    def _validate_investment_of_chain_master_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        params: dict[str, Any],
    ) -> None:
        if action.id != PACT_OF_CHAIN_FIND_FAMILIAR_ACTION_ID:
            return
        owner = self._resource_owner(actor_id)
        if not isinstance(owner, Character) or not has_warlock_investment_of_chain_master(owner):
            return
        self._investment_familiar_speed_choice(params)

    def _investment_of_chain_master_familiar_metadata(
        self,
        ctx: _Context,
        node: dict[str, Any],
    ) -> dict[str, Any]:
        if ctx.action.id != PACT_OF_CHAIN_FIND_FAMILIAR_ACTION_ID:
            return {}
        if str(node.get("effect_type", "")) != "familiar_bound":
            return {}
        owner = self._resource_owner(ctx.actor_id)
        if not isinstance(owner, Character) or not has_warlock_investment_of_chain_master(owner):
            return {}
        speed_choice = self._investment_familiar_speed_choice(ctx.params)
        return {
            "investment_of_the_chain_master": True,
            "aerial_or_aquatic_speed": speed_choice,
            "aerial_or_aquatic_speed_ft": 40,
            "quick_attack_bonus_action_command": True,
            "can_convert_bludgeoning_piercing_slashing_to": ["necrotic", "radiant"],
            "uses_warlock_spell_save_dc": True,
            "warlock_reaction_can_grant_resistance": True,
        }

    @staticmethod
    def _investment_familiar_speed_choice(params: dict[str, Any]) -> str:
        raw = params.get(
            "investment_familiar_speed", params.get("investment_of_chain_master_speed")
        )
        choice = str(raw).casefold().strip() if raw not in (None, "", False) else ""
        normalized = {
            "fly": "fly",
            "flying": "fly",
            "飞行": "fly",
            "swim": "swim",
            "swimming": "swim",
            "游泳": "swim",
        }.get(choice)
        if normalized is None:
            raise AutomationError(
                "Investment of the Chain Master requires investment_familiar_speed fly or swim"
            )
        return normalized

    def _validate_thirsting_blade_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        params: dict[str, Any],
    ) -> None:
        if not self._thirsting_blade_extra_attack_requested(params):
            return
        owner = self._resource_owner(actor_id)
        if not isinstance(owner, Character) or not has_warlock_thirsting_blade(owner):
            raise AutomationError(
                "Thirsting Blade extra attack requires Warlock 5 with Pact of the Blade"
            )
        if action.action_type != "weapon_attack" or not self._is_melee_weapon_attack_action(action):
            raise AutomationError("Thirsting Blade extra attack requires a pact weapon attack")
        if self._active_pact_weapon_effect_for_action(actor_id, action.id) is None:
            raise AutomationError("Thirsting Blade extra attack requires the selected pact weapon")
        if not self._has_thirsting_blade_pact_weapon_attack_this_turn(actor_id, action.id):
            raise AutomationError(
                "Thirsting Blade extra attack requires a prior pact weapon attack this turn"
            )
        if self._has_thirsting_blade_extra_attack_used(actor_id):
            raise AutomationError("Thirsting Blade extra attack already used this turn")

    @staticmethod
    def _thirsting_blade_extra_attack_requested(params: dict[str, Any]) -> bool:
        return (
            params.get("use_thirsting_blade_extra_attack") is True
            or params.get("thirsting_blade_extra_attack") is True
        )

    def _validate_eldritch_smite_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        targets: list[str],
        params: dict[str, Any],
    ) -> None:
        if not self._eldritch_smite_requested(params):
            return
        owner = self._resource_owner(actor_id)
        if not isinstance(owner, Character) or not has_warlock_eldritch_smite(owner):
            raise AutomationError("Eldritch Smite requires Warlock 5 with Pact of the Blade")
        if action.action_type != "weapon_attack" or not self._is_melee_weapon_attack_action(action):
            raise AutomationError("Eldritch Smite requires a pact weapon attack")
        if self._active_pact_weapon_effect_for_action(actor_id, action.id) is None:
            raise AutomationError("Eldritch Smite requires the selected pact weapon")
        if self._has_eldritch_smite_used(actor_id):
            raise AutomationError("Eldritch Smite already used this turn")
        slot_level = self._pact_magic_slot_level(owner)
        if slot_level is None or int(owner.spell_slots.get(str(slot_level), 0)) <= 0:
            raise AutomationError("insufficient Pact Magic spell slot")
        target_id = self._eldritch_smite_target_id(targets, params)
        if self._eldritch_smite_prone_requested(params) and not self._target_huge_or_smaller(
            target_id
        ):
            raise AutomationError("Eldritch Smite Prone target must be Huge or smaller")

    @staticmethod
    def _eldritch_smite_requested(params: dict[str, Any]) -> bool:
        return params.get("use_eldritch_smite") is True or params.get("eldritch_smite") is True

    @staticmethod
    def _eldritch_smite_prone_requested(params: dict[str, Any]) -> bool:
        return (
            params.get("eldritch_smite_prone") is True
            or params.get("eldritch_smite_give_prone") is True
        )

    @staticmethod
    def _eldritch_smite_target_id(targets: list[str], params: dict[str, Any]) -> str:
        selected = params.get("eldritch_smite_target_id")
        if selected not in (None, "", False):
            return str(selected)
        if len(targets) == 1:
            return str(targets[0])
        raise AutomationError("Eldritch Smite requires a target")

    @staticmethod
    def _pact_magic_slot_level(actor: Character) -> int | None:
        pact_slots = warlock_pact_slot_maxima_for_class_levels(actor.class_levels)
        if not pact_slots:
            return None
        return max(int(level) for level in pact_slots)

    def _validate_preserve_life_preconditions(
        self,
        action: ActionDefinition,
        actor_id: str,
        targets: list[str],
        params: dict[str, Any],
    ) -> None:
        if self._preserve_life_node(action) is None:
            return
        self._preserve_life_allocations(action, actor_id, targets, params)

    def _preserve_life_allocations(
        self,
        action: ActionDefinition,
        actor_id: str,
        targets: list[str],
        params: dict[str, Any],
    ) -> dict[str, int]:
        node = self._preserve_life_node(action)
        if node is None:
            return {}
        param_name = str(node.get("points_param", "preserve_life_points"))
        raw_points = params.get(param_name)
        if raw_points is None:
            raise AutomationError(f"missing required parameter {param_name}")
        allocations = self._parse_preserve_life_points(raw_points, targets, param_name)
        owner = self._resource_owner(actor_id)
        if not isinstance(owner, Character):
            raise AutomationError("Preserve Life requires a character")
        pool = preserve_life_healing_pool(owner)
        total = sum(allocations.values())
        if pool <= 0:
            raise AutomationError("Preserve Life requires Cleric Life Domain level 3")
        if total > pool:
            raise AutomationError("Preserve Life points exceed available healing pool")
        max_range = int(action.range.get("normal_ft", 30))
        for target_id, amount in allocations.items():
            try:
                target = self._entity(target_id)
            except KeyError as exc:
                raise AutomationError(f"unknown target {target_id}") from exc
            hp_current = int(getattr(target, "hp_current"))
            hp_max = int(getattr(target, "hp_max"))
            cap = bloodied_hp_cap(hp_max)
            if not is_bloodied(hp_current=hp_current, hp_max=hp_max):
                raise AutomationError("Preserve Life target must be Bloodied")
            if amount > max(0, cap - hp_current):
                raise AutomationError("Preserve Life cannot heal a target above half HP")
            distance = self._combat_distance(self._entity(actor_id), target)
            if distance is not None and distance > max_range:
                raise AutomationError("Preserve Life target is out of range")
        return allocations

    def _parse_preserve_life_points(
        self,
        raw_points: Any,
        targets: list[str],
        param_name: str,
    ) -> dict[str, int]:
        if isinstance(raw_points, int) and not isinstance(raw_points, bool) and len(targets) == 1:
            allocations = {targets[0]: raw_points}
        elif isinstance(raw_points, dict):
            allocations = {
                str(target_id): self._positive_int(value, param_name)
                for target_id, value in raw_points.items()
            }
        else:
            raise AutomationError(f"parameter {param_name} must be a target-to-points map")
        target_set = set(targets)
        allocation_set = set(allocations)
        if allocation_set != target_set:
            raise AutomationError("Preserve Life points must be assigned to exactly the targets")
        for amount in allocations.values():
            if amount <= 0:
                raise AutomationError("Preserve Life points must be positive")
        return allocations

    def _validate_lands_aid_preconditions(
        self,
        action: ActionDefinition,
        targets: list[str],
        params: dict[str, Any],
    ) -> None:
        if action.id != LANDS_AID_ACTION_ID:
            return
        healing_target_id = self._lands_aid_healing_target_id(params)
        area_targets = self._lands_aid_area_targets(params)
        try:
            self._entity(healing_target_id)
        except KeyError as exc:
            raise AutomationError(f"unknown target {healing_target_id}") from exc
        if healing_target_id not in area_targets:
            raise AutomationError("Land's Aid healing target must be in the area")
        for target_id in targets:
            try:
                self._entity(target_id)
            except KeyError as exc:
                raise AutomationError(f"unknown target {target_id}") from exc
            if target_id not in area_targets:
                raise AutomationError("Land's Aid damage target must be in the area")

    @staticmethod
    def _lands_aid_healing_target_id(params: dict[str, Any]) -> str:
        param_name = "lands_aid_healing_target_id"
        selected = params.get(param_name)
        if selected is None:
            raise AutomationError(f"missing required parameter {param_name}")
        if isinstance(selected, (dict, list)):
            raise AutomationError(f"parameter {param_name} must identify one target")
        target_id = str(selected)
        if not target_id:
            raise AutomationError(f"parameter {param_name} must identify one target")
        return target_id

    @staticmethod
    def _lands_aid_area_targets(params: dict[str, Any]) -> set[str]:
        param_name = "lands_aid_area_target_ids"
        raw_area_targets = params.get(param_name)
        if raw_area_targets is None:
            param_name = "area_targets"
            raw_area_targets = params.get(param_name)
        if raw_area_targets is None:
            raise AutomationError("missing required parameter lands_aid_area_target_ids")
        if not isinstance(raw_area_targets, list):
            raise AutomationError(f"parameter {param_name} must be a target list")
        area_targets = {str(target_id) for target_id in raw_area_targets}
        if not area_targets:
            raise AutomationError(f"parameter {param_name} must include at least one target")
        return area_targets

    @staticmethod
    def _positive_int(value: Any, param_name: str) -> int:
        if isinstance(value, bool):
            raise AutomationError(f"parameter {param_name} must contain positive integers")
        try:
            amount = int(value)
        except (TypeError, ValueError) as exc:
            raise AutomationError(f"parameter {param_name} must contain positive integers") from exc
        if amount <= 0:
            raise AutomationError(f"parameter {param_name} must contain positive integers")
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

    def _validate_action_economy(
        self,
        action: ActionDefinition,
        actor_id: str,
        params: dict[str, Any],
    ) -> None:
        if action.action_economy == "none":
            return
        actor = self._entity(actor_id)
        self._validate_condition_gate(actor, action.action_economy)
        self._validate_blocked_action_economy(actor, action.action_economy)
        if self._fleet_step_waives_bonus_action(action, actor_id, params):
            return
        if self._quivering_palm_harmless_release_waives_action(action, params):
            return
        if (
            self._thirsting_blade_extra_attack_requested(params)
            and action.action_economy == "action"
        ):
            return
        amount = int(params.get("movement_cost", 1)) if action.action_economy == "movement" else 1
        budget = self.economy.budget_for(actor_id, self._effective_speed(actor))
        if not budget.can_spend(action.action_economy, amount):
            raise AutomationError(f"not enough {action.action_economy} budget")

    def _validate_charmed_targets(
        self,
        action: ActionDefinition,
        actor_id: str,
        targets: list[str],
        params: dict[str, Any],
    ) -> None:
        if self._quivering_palm_harmless_release_waives_action(action, params):
            return
        if not bool(action.target_policy.get("harmful", False)):
            return
        try:
            actor = self._entity(actor_id)
        except KeyError:
            return
        if self._condition_immunity_sources(actor, "charmed"):
            return
        charmer_ids = {
            str(effect.get("applied_by"))
            for effect in self._status_effects_for(actor)
            if effect.get("condition") == "charmed" and isinstance(effect.get("applied_by"), str)
        }
        if not charmer_ids:
            return
        target_ids = set(targets)
        if action.id != LANDS_AID_ACTION_ID:
            area_targets = params.get("area_targets", [])
            if isinstance(area_targets, list):
                target_ids.update(str(target_id) for target_id in area_targets)
        for target_id in target_ids:
            if charmer_ids & self._entity_aliases(target_id):
                raise AutomationError("actor cannot target the charmer while charmed")

    def _validate_target_policy(
        self,
        action: ActionDefinition,
        actor_id: str,
        targets: list[str],
        params: dict[str, Any],
    ) -> None:
        policy = action.target_policy
        min_targets = int(policy.get("min", 0))
        max_targets = self._effective_max_targets(action, params)
        if len(targets) < min_targets:
            raise AutomationError("not enough targets")
        if max_targets is not None and len(targets) > max_targets:
            raise AutomationError("too many targets")
        if bool(policy.get("exclude_self", False)):
            actor_aliases = self._entity_aliases(actor_id)
            if any(target_id in actor_aliases for target_id in targets):
                raise AutomationError("target cannot be self")
        creature_types = policy.get("creature_types")
        if isinstance(creature_types, list) and creature_types:
            allowed = {str(creature_type).lower() for creature_type in creature_types}
            for target_id in targets:
                target = self._entity(target_id)
                if self._creature_type_for(target).lower() not in allowed:
                    expected = ", ".join(sorted(allowed))
                    raise AutomationError(f"target must be {expected}")

    def _effective_max_targets(
        self,
        action: ActionDefinition,
        params: dict[str, Any],
    ) -> int | None:
        max_targets = action.target_policy.get("max")
        if max_targets is None:
            return None
        maximum = int(max_targets)
        per_slot = action.target_policy.get("max_targets_per_slot_above")
        if per_slot is None:
            return maximum
        if not isinstance(per_slot, int) or isinstance(per_slot, bool) or per_slot < 1:
            raise AutomationError("max_targets_per_slot_above must be a positive integer")
        base_slot = action.target_policy.get("base_spell_slot_level", action.cost.spell_slot_level)
        if not isinstance(base_slot, int) or isinstance(base_slot, bool) or base_slot < 1:
            raise AutomationError("base_spell_slot_level must be a positive integer")
        slot_level = self._spell_slot_level_to_spend(action, params)
        return maximum + max(0, slot_level - base_slot) * per_slot

    def _validate_self_only_targets(
        self,
        action: ActionDefinition,
        actor_id: str,
        targets: list[str],
    ) -> None:
        if action.properties.get("self_only") is not True:
            return
        actor_aliases = self._entity_aliases(actor_id)
        for target_id in targets:
            if not (actor_aliases & self._entity_aliases(target_id)):
                raise AutomationError("target must be self")

    def _validate_requires_self_target(
        self,
        action: ActionDefinition,
        actor_id: str,
        targets: list[str],
    ) -> None:
        if action.properties.get("requires_self_target") is not True:
            return
        actor_aliases = self._entity_aliases(actor_id)
        if not any(actor_aliases & self._entity_aliases(target_id) for target_id in targets):
            raise AutomationError("target list must include self")

    def _validate_actor_not_out_of_play(self, action: ActionDefinition, actor_id: str) -> None:
        if action.properties.get("can_be_used_out_of_play") is True:
            return
        try:
            actor = self._entity(actor_id)
        except KeyError:
            return
        sources = self._out_of_play_sources(actor)
        if sources:
            raise AutomationError(f"actor is out of play due to {sources[0]}")

    def _validate_targets_not_out_of_play(
        self,
        action: ActionDefinition,
        targets: list[str],
    ) -> None:
        if action.properties.get("can_target_out_of_play") is True:
            return
        for target_id in targets:
            sources = self._out_of_play_sources(self._entity(target_id))
            if sources:
                raise AutomationError(f"target is out of play due to {sources[0]}")

    def _validate_target_size_max(self, action: ActionDefinition, targets: list[str]) -> None:
        max_size = action.properties.get("target_size_max")
        if not isinstance(max_size, str):
            return
        normalized_max = max_size.casefold().strip()
        max_rank = CREATURE_SIZE_RANKS.get(normalized_max)
        if max_rank is None:
            raise AutomationError(f"unsupported target size max: {max_size}")
        for target_id in targets:
            target = self._entity(target_id)
            size = str(getattr(target, "size", "medium")).casefold().strip()
            rank = CREATURE_SIZE_RANKS.get(size, CREATURE_SIZE_RANKS["medium"])
            if rank > max_rank:
                raise AutomationError(f"target must be {normalized_max.title()} or smaller")

    def _validate_willing_targets(
        self,
        action: ActionDefinition,
        targets: list[str],
        params: dict[str, Any],
    ) -> None:
        if action.properties.get("requires_willing_target") is not True:
            return
        for target_id in targets:
            if not self._target_willing(params, target_id):
                raise AutomationError("target must be willing")

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

    def _validate_mage_armor_unarmored_targets(
        self,
        action: ActionDefinition,
        actor_id: str,
        targets: list[str],
    ) -> None:
        if action.properties.get("spell_definition_id") != "srd.spell.mage_armor":
            return
        target_ids = list(targets)
        if not target_ids and action.target_policy.get("self") is True:
            target_ids = [actor_id]
        for target_id in target_ids:
            target = self._entity(target_id)
            owner = self._resource_owner(target_id)
            if isinstance(owner, Character) and is_wearing_armor(owner):
                raise AutomationError("Mage Armor target must not be wearing armor")
            if isinstance(target, Character) and is_wearing_armor(target):
                raise AutomationError("Mage Armor target must not be wearing armor")

    def _validate_active_effect_requirement(
        self,
        action: ActionDefinition,
        actor_id: str,
    ) -> None:
        source_action_id = action.properties.get("requires_active_effect_source_action_id")
        if not isinstance(source_action_id, str) or not source_action_id:
            return
        if self._actor_has_active_effect_from_action(actor_id, source_action_id):
            return
        raise AutomationError(f"{action.id} requires active effect from {source_action_id}")

    def _actor_has_active_effect_from_action(
        self,
        actor_id: str,
        source_action_id: str,
    ) -> bool:
        def matches(effect: dict[str, Any]) -> bool:
            applied_by = effect.get("applied_by")
            return (
                effect.get("source_action_id") == source_action_id
                and isinstance(applied_by, str)
                and self._entity_ids_match(applied_by, actor_id)
            )

        return any(
            matches(effect)
            for _, _, effects in self._actor_effect_lists(actor_id)
            for effect in effects
        ) or any(matches(effect) for effect in self.state.world.active_effects)

    @staticmethod
    def _validate_one_with_shadows_lighting(
        action: ActionDefinition,
        params: dict[str, Any],
    ) -> None:
        if action.properties.get("requires_dim_light_or_darkness") is not True:
            return
        if params.get("in_dim_light_or_darkness") is True:
            return
        raise AutomationError("One with Shadows requires Dim Light or Darkness")

    def _validate_requirements(self, action: ActionDefinition, actor_id: str) -> None:
        requirements = action.requirements
        item_id = requirements.get("item")
        if isinstance(item_id, str) and item_id and not self._actor_has_item(actor_id, item_id):
            raise AutomationError(f"actor does not have item {item_id}")
        class_name = requirements.get("class")
        class_level_min = requirements.get("class_level_min")
        if class_name is not None or class_level_min is not None:
            owner = self._resource_owner(actor_id)
            class_levels = getattr(owner, "class_levels", None)
            if not isinstance(class_levels, dict):
                raise AutomationError("actor does not meet class requirements")
            if class_name is not None:
                required_level = int(class_level_min or 1)
                actual_level = int(class_levels.get(str(class_name), 0))
                if actual_level < required_level:
                    raise AutomationError(f"requires {class_name} level {required_level}")
            else:
                assert class_level_min is not None
                required_level = int(class_level_min)
                highest_class_level = max(
                    (int(level) for level in class_levels.values()), default=0
                )
                if highest_class_level < required_level:
                    raise AutomationError(f"requires class level {required_level}")
        class_any = requirements.get("class_any")
        if class_any is not None:
            if isinstance(class_any, str):
                required_classes = [class_any]
            elif isinstance(class_any, list):
                required_classes = [str(item) for item in class_any]
            else:
                raise AutomationError("class_any requirement must be a string or list")
            required_classes = [class_name.lower() for class_name in required_classes if class_name]
            owner = self._resource_owner(actor_id)
            class_levels = getattr(owner, "class_levels", None)
            if not isinstance(class_levels, dict):
                raise AutomationError("actor does not meet class requirements")
            required_level = int(requirements.get("class_any_level_min", 1))
            if not any(
                int(class_levels.get(class_name, 0)) >= required_level
                for class_name in required_classes
            ):
                raise AutomationError(f"requires one of {', '.join(required_classes)}")
        if requirements.get("no_movement_used") is True:
            actor = self._entity(actor_id)
            budget = self.economy.budget_for(actor_id, self._effective_speed(actor))
            if int(getattr(budget, "movement_used", 0)) > 0:
                raise AutomationError("requires no movement used this turn")
        subclass = requirements.get("subclass")
        if subclass is not None:
            if class_name is None:
                raise AutomationError("subclass requirement requires class")
            owner = self._resource_owner(actor_id)
            if not isinstance(owner, Character) or owner.subclasses.get(str(class_name)) != str(
                subclass
            ):
                raise AutomationError(f"requires {class_name} subclass {subclass}")

    def _validate_spellcasting_allowed(self, action: ActionDefinition, actor_id: str) -> None:
        if action.action_type != "spell":
            return
        actor = self._entity(actor_id)
        for effect in self._status_effects_for(actor):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            if modifiers.get("blocks_spellcasting") is True:
                source = effect.get("source_action_id") or effect.get("condition") or "effect"
                raise AutomationError(f"actor cannot cast spells while affected by {source}")

    def _validate_allowed_action_effects(self, action: ActionDefinition, actor_id: str) -> None:
        try:
            actor = self._entity(actor_id)
        except KeyError:
            return
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
                raise AutomationError(
                    f"actor can only take allowed actions ({allowed_text}) "
                    f"while affected by {source}"
                )

    def _validate_attacks_allowed(self, action: ActionDefinition, actor_id: str) -> None:
        if action.action_type not in ATTACK_ACTION_TYPES:
            return
        actor = self._entity(actor_id)
        for effect in self._status_effects_for(actor):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            if modifiers.get("blocks_attacks") is True:
                source = effect.get("source_action_id") or effect.get("condition") or "effect"
                raise AutomationError(f"actor cannot attack while affected by {source}")

    def _validate_ritual_casting(
        self,
        action: ActionDefinition,
        actor_id: str,
        params: dict[str, Any],
    ) -> None:
        if not bool(params.get("as_ritual", False)):
            return
        actor = self._resource_owner(actor_id)
        if not isinstance(actor, Character):
            raise AutomationError("ritual casting requires a character")
        eligibility = ritual_casting_eligibility(
            actor,
            action,
            requested_slot_level=self._optional_int(params.get("slot_level")),
        )
        if not eligibility.allowed:
            raise AutomationError(eligibility.reason)

    def _validate_condition_gate(
        self,
        actor: Character | Monster | Combatant,
        action_economy: str,
    ) -> None:
        conditions = self._condition_names(actor)
        if action_economy in {"action", "bonus_action", "reaction", "free"}:
            blocked_by = sorted(conditions & ACTION_BLOCKING_CONDITIONS)
            if blocked_by:
                raise AutomationError(f"actor cannot take {action_economy} while {blocked_by[0]}")
        if action_economy == "movement":
            blocked_by = sorted(conditions & MOVEMENT_BLOCKING_CONDITIONS)
            if blocked_by:
                raise AutomationError(f"actor cannot move while {blocked_by[0]}")

    def _validate_blocked_action_economy(
        self,
        actor: Character | Monster | Combatant,
        action_economy: str,
    ) -> None:
        if action_economy not in {"action", "bonus_action", "reaction", "movement", "free"}:
            return
        for effect in self._status_effects_for(actor):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            blocked = modifiers.get("blocked_action_economies")
            if isinstance(blocked, str):
                blocked_economies = {blocked}
            elif isinstance(blocked, list):
                blocked_economies = {str(item) for item in blocked}
            else:
                continue
            if action_economy not in blocked_economies:
                continue
            source = effect.get("source_action_id") or effect.get("condition") or "effect"
            raise AutomationError(
                f"actor cannot take {action_economy} while affected by {source}"
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

    def _entity_ids_match(self, left_id: str, right_id: str) -> bool:
        return bool(self._entity_aliases(left_id) & self._entity_aliases(right_id))

    def _creature_type_for(self, entity: Character | Monster | Combatant) -> str:
        if isinstance(entity, Combatant):
            if entity.entity_id in self.state.monsters:
                return str(self.state.monsters[entity.entity_id].creature_type)
            if entity.entity_id in self.state.characters:
                return "humanoid"
        if isinstance(entity, Character):
            return "humanoid"
        return str(getattr(entity, "creature_type", "humanoid"))

    def _spend_action_economy(
        self,
        action: ActionDefinition,
        actor_id: str,
        params: dict[str, Any],
        result: AutomationResult,
    ) -> None:
        if action.action_economy == "none":
            return
        if self._fleet_step_waives_bonus_action(action, actor_id, params):
            ticket = self._clear_fleet_step_window(actor_id) or {}
            actor = self._entity(actor_id)
            before = self.economy.budget_for(actor_id, self._effective_speed(actor)).to_dict()
            after = self.economy.budget_for(actor_id).to_dict()
            result.state_changes.append(
                {
                    "type": "fleet_step",
                    "actor_id": actor_id,
                    "source_action_id": FLEET_STEP_ACTION_ID,
                    "step_of_the_wind_action_id": action.id,
                    "trigger_action_id": ticket.get("audit", {}).get("trigger_action_id"),
                    "bonus_action_waived": True,
                    "bonus_action_before": before,
                    "bonus_action_after": after,
                }
            )
            return
        if self._quivering_palm_harmless_release_waives_action(action, params):
            return
        if (
            self._thirsting_blade_extra_attack_requested(params)
            and action.action_economy == "action"
        ):
            return
        amount = int(params.get("movement_cost", 1)) if action.action_economy == "movement" else 1
        actor = self._entity(actor_id)
        before = self.economy.budget_for(actor_id, self._effective_speed(actor)).to_dict()
        self.economy.spend(actor_id, action.action_economy, amount)
        after = self.economy.budget_for(actor_id).to_dict()
        result.state_changes.append(
            {
                "type": "action_economy",
                "actor_id": actor_id,
                "economy": action.action_economy,
                "amount": amount,
                "before": before,
                "after": after,
            }
        )

    @staticmethod
    def _uses_rod_of_absorption_spell_slot(params: dict[str, Any]) -> bool:
        return (
            params.get("use_rod_of_absorption") is True or params.get("rod_of_absorption") is True
        )

    def _validate_rod_of_absorption_spell_slot_replacement(
        self,
        action: ActionDefinition,
        actor_id: str,
        actor: Character,
        params: dict[str, Any],
    ) -> None:
        if not self._actor_has_item(actor_id, ROD_OF_ABSORPTION_ITEM_ID):
            raise AutomationError("Rod of Absorption requires holding the rod")
        slot_level = self._rod_of_absorption_created_spell_slot_level(action, params)
        highest_slot_level = self._highest_own_spell_slot_level(actor)
        if highest_slot_level <= 0:
            raise AutomationError("Rod of Absorption requires a spellcaster with spell slots")
        if slot_level > highest_slot_level:
            raise AutomationError(
                "Rod of Absorption cannot create a spell slot above your own spell slots"
            )
        if slot_level > ROD_OF_ABSORPTION_MAX_CREATED_SLOT_LEVEL:
            raise AutomationError("Rod of Absorption cannot create spell slots above level 5")
        stored = int(actor.resources.get(ROD_OF_ABSORPTION_STORED_LEVELS_RESOURCE, 0))
        if stored < slot_level:
            raise AutomationError("Rod of Absorption has insufficient stored spell energy")

    def _rod_of_absorption_created_spell_slot_level(
        self,
        action: ActionDefinition,
        params: dict[str, Any],
    ) -> int:
        base_slot_level = int(action.cost.spell_slot_level or 0)
        requested_slot_level = self._optional_int(params.get("slot_level"))
        slot_level = requested_slot_level if requested_slot_level is not None else base_slot_level
        if slot_level < base_slot_level:
            raise AutomationError(
                "Rod of Absorption cannot create a lower-level slot than the spell requires"
            )
        return slot_level

    def _spell_slot_level_to_spend(
        self,
        action: ActionDefinition,
        params: dict[str, Any],
    ) -> int:
        base_slot_level = int(action.cost.spell_slot_level or 0)
        requested_slot_level = self._optional_int(params.get("slot_level"))
        slot_level = requested_slot_level if requested_slot_level is not None else base_slot_level
        if slot_level < base_slot_level:
            raise AutomationError(f"spell requires level {base_slot_level} slot or higher")
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

    @staticmethod
    def _deplete_rod_of_absorption_if_nonmagical(
        actor: Character,
        actor_id: str,
    ) -> dict[str, Any] | None:
        stored = int(actor.resources.get(ROD_OF_ABSORPTION_STORED_LEVELS_RESOURCE, 0))
        lifetime = int(actor.resources.get(ROD_OF_ABSORPTION_LIFETIME_ABSORBED_RESOURCE, 0))
        if stored > 0 or lifetime < ROD_OF_ABSORPTION_LIFETIME_CAP:
            return None
        inventory_before = int(actor.inventory.get(ROD_OF_ABSORPTION_ITEM_ID, 0))
        equipment_before = list(actor.equipment)
        removed_from: str | None = None
        if inventory_before > 0:
            actor.inventory[ROD_OF_ABSORPTION_ITEM_ID] = inventory_before - 1
            removed_from = "inventory"
        elif ROD_OF_ABSORPTION_ITEM_ID in actor.equipment:
            actor.equipment.remove(ROD_OF_ABSORPTION_ITEM_ID)
            removed_from = "equipment"
        actor.resources[ROD_OF_ABSORPTION_INITIALIZED_RESOURCE] = 0
        return {
            "type": "rod_of_absorption_depleted",
            "actor_id": actor_id,
            "item_id": ROD_OF_ABSORPTION_ITEM_ID,
            "stored_levels": stored,
            "lifetime_absorbed_levels": lifetime,
            "removed_from": removed_from,
            "inventory_before": inventory_before,
            "inventory_after": int(actor.inventory.get(ROD_OF_ABSORPTION_ITEM_ID, 0)),
            "equipment_before": equipment_before,
            "equipment_after": list(actor.equipment),
        }

    def _validate_cost(
        self,
        action: ActionDefinition,
        actor_id: str,
        params: dict[str, Any],
    ) -> None:
        if (
            action.cost.spell_slot_level is None
            and not action.cost.resources
            and not action.cost.resource_params
            and not action.cost.items
            and action.cost.gold == 0
        ):
            return
        actor = self._resource_owner(actor_id)
        if action.cost.spell_slot_level is not None and not bool(params.get("as_ritual", False)):
            if not isinstance(actor, Character):
                raise AutomationError("only characters spend spell slots")
            if self._uses_rod_of_absorption_spell_slot(params):
                self._validate_rod_of_absorption_spell_slot_replacement(
                    action,
                    actor_id,
                    actor,
                    params,
                )
            else:
                key = str(self._spell_slot_level_to_spend(action, params))
                available = actor.spell_slots.get(key, 0)
                if available <= 0:
                    raise AutomationError(f"no spell slot level {key} available")
        for resource, amount in action.cost.resources.items():
            before = self._get_resource(actor, resource)
            if before < amount:
                raise AutomationError(f"resource {resource} is insufficient")
        for resource, param_name in action.cost.resource_params.items():
            amount = self._positive_param_int(params, param_name)
            before = self._get_resource(actor, resource)
            if before < amount:
                raise AutomationError(f"resource {resource} is insufficient")
        for item_id, amount in action.cost.items.items():
            before = self._get_resource(actor, item_id)
            if before < amount:
                raise AutomationError(f"item {item_id} is insufficient")
        if action.cost.gold:
            before = self._get_resource(actor, "gold")
            if before < action.cost.gold:
                raise AutomationError("gold is insufficient")

    def _apply_cost(
        self,
        action: ActionDefinition,
        actor_id: str,
        params: dict[str, Any],
        result: AutomationResult,
    ) -> None:
        if (
            action.cost.spell_slot_level is None
            and not action.cost.resources
            and not action.cost.resource_params
            and not action.cost.items
            and action.cost.gold == 0
        ):
            return
        actor = self._resource_owner(actor_id)
        if action.cost.spell_slot_level is not None:
            if not isinstance(actor, Character):
                raise AutomationError("only characters spend spell slots")
            if bool(params.get("as_ritual", False)):
                eligibility = ritual_casting_eligibility(
                    actor,
                    action,
                    requested_slot_level=self._optional_int(params.get("slot_level")),
                )
                result.state_changes.append(
                    {
                        "type": "ritual_casting",
                        "actor_id": actor_id,
                        "spell_id": action.properties.get("spell_definition_id", action.id),
                        "base_spell_slot_level": action.cost.spell_slot_level,
                        "spell_slot_expended": False,
                        "casting_time_extra_minutes": 10,
                        "source": eligibility.source,
                    }
                )
            elif self._uses_rod_of_absorption_spell_slot(params):
                slot_level = self._rod_of_absorption_created_spell_slot_level(action, params)
                before = int(actor.resources.get(ROD_OF_ABSORPTION_STORED_LEVELS_RESOURCE, 0))
                actor.resources[ROD_OF_ABSORPTION_STORED_LEVELS_RESOURCE] = before - slot_level
                result.state_changes.append(
                    {
                        "type": "cost",
                        "actor_id": actor_id,
                        "resource": ROD_OF_ABSORPTION_STORED_LEVELS_RESOURCE,
                        "before": before,
                        "after": before - slot_level,
                        "amount": slot_level,
                        "source": "rod_of_absorption",
                        "spell_id": action.properties.get("spell_definition_id", action.id),
                        "base_spell_slot_level": action.cost.spell_slot_level,
                        "created_spell_slot_level": slot_level,
                        "spell_slot_expended": False,
                    }
                )
                depleted = self._deplete_rod_of_absorption_if_nonmagical(actor, actor_id)
                if depleted is not None:
                    result.state_changes.append(depleted)
            else:
                slot_level = self._spell_slot_level_to_spend(action, params)
                key = str(slot_level)
                base_slot_level = int(action.cost.spell_slot_level)
                before = actor.spell_slots.get(key, 0)
                actor.spell_slots[key] = before - 1
                cost_change: dict[str, Any] = {
                    "type": "cost",
                    "actor_id": actor_id,
                    "resource": f"spell_slot_{key}",
                    "before": before,
                    "after": actor.spell_slots[key],
                }
                if slot_level != base_slot_level:
                    cost_change["base_spell_slot_level"] = base_slot_level
                    cost_change["spell_slot_level"] = slot_level
                result.state_changes.append(cost_change)
        for resource, amount in action.cost.resources.items():
            before = self._get_resource(actor, resource)
            self._set_resource(actor, resource, before - amount)
            result.state_changes.append(
                {
                    "type": "cost",
                    "actor_id": actor_id,
                    "resource": resource,
                    "before": before,
                    "after": before - amount,
                }
            )
        for resource, param_name in action.cost.resource_params.items():
            amount = self._positive_param_int(params, param_name)
            before = self._get_resource(actor, resource)
            self._set_resource(actor, resource, before - amount)
            result.state_changes.append(
                {
                    "type": "cost",
                    "actor_id": actor_id,
                    "resource": resource,
                    "before": before,
                    "after": before - amount,
                    "amount": amount,
                    "param": param_name,
                }
            )
        for item_id, amount in action.cost.items.items():
            before = self._get_resource(actor, item_id)
            self._set_resource(actor, item_id, before - amount)
            result.state_changes.append(
                {
                    "type": "cost",
                    "actor_id": actor_id,
                    "resource": item_id,
                    "before": before,
                    "after": before - amount,
                }
            )
        if action.cost.gold:
            before = self._get_resource(actor, "gold")
            self._set_resource(actor, "gold", before - action.cost.gold)
            result.state_changes.append(
                {
                    "type": "cost",
                    "actor_id": actor_id,
                    "resource": "gold",
                    "before": before,
                    "after": before - action.cost.gold,
                }
            )

    def _entity(self, actor_id: str) -> Character | Monster | Combatant:
        return self.state.entity_for_actor(actor_id)

    def _resource_owner(self, actor_id: str) -> Character | Monster | Combatant:
        actor = self._entity(actor_id)
        if isinstance(actor, Combatant) and actor.entity_id in self.state.characters:
            return self.state.characters[actor.entity_id]
        if isinstance(actor, Combatant) and actor.entity_id in self.state.monsters:
            return self.state.monsters[actor.entity_id]
        return actor

    def _actor_has_item(self, actor_id: str, item_id: str) -> bool:
        owner = self._resource_owner(actor_id)
        inventory = getattr(owner, "inventory", {})
        if isinstance(inventory, dict) and int(inventory.get(item_id, 0)) > 0:
            return True
        equipment = getattr(owner, "equipment", [])
        return isinstance(equipment, list) and item_id in {str(item) for item in equipment}

    @staticmethod
    def _positive_param_int(params: dict[str, Any], param_name: str) -> int:
        if param_name not in params:
            raise AutomationError(f"missing required parameter {param_name}")
        try:
            amount = int(params[param_name])
        except (TypeError, ValueError) as exc:
            raise AutomationError(f"parameter {param_name} must be an integer") from exc
        if amount <= 0:
            raise AutomationError(f"parameter {param_name} must be positive")
        return amount

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _condition_names(self, actor: Character | Monster | Combatant) -> set[str]:
        names: set[str] = set()
        for effect in self._status_effects_for(actor):
            condition = effect.get("condition")
            if isinstance(condition, str):
                names.add(condition)
        return names

    def _ability_source(
        self, actor: Character | Monster | Combatant
    ) -> Character | Monster | Combatant:
        if isinstance(actor, Combatant) and actor.abilities:
            return actor
        if isinstance(actor, Combatant) and actor.entity_id in self.state.characters:
            return self.state.characters[actor.entity_id]
        if isinstance(actor, Combatant) and actor.entity_id in self.state.monsters:
            return self.state.monsters[actor.entity_id]
        return actor

    def _class_levels_for_entity(self, actor: Character | Monster | Combatant) -> dict[str, int]:
        if isinstance(actor, Combatant) and actor.entity_id in self.state.characters:
            return self.state.characters[actor.entity_id].class_levels
        if isinstance(actor, Character):
            return actor.class_levels
        return {}

    def _effective_armor_class(
        self, target: Character | Monster | Combatant
    ) -> tuple[int, int, list[dict[str, Any]]]:
        base_ac = int(getattr(target, "armor_class"))
        ac = base_ac
        minimum_ac: int | None = None
        bonus = 0
        sources: list[dict[str, Any]] = []
        barbarian_unarmored_ac = self._barbarian_unarmored_defense_armor_class(target)
        if barbarian_unarmored_ac is not None:
            ac = max(ac, barbarian_unarmored_ac)
            sources.append(
                {
                    "modifier": "barbarian_unarmored_defense",
                    "source_action_id": "srd.barbarian_unarmored_defense",
                    "formula": "10+dex_modifier+con_modifier",
                    "value": barbarian_unarmored_ac,
                }
            )
        monk_unarmored_ac = self._monk_unarmored_defense_armor_class(target)
        if monk_unarmored_ac is not None:
            ac = max(ac, monk_unarmored_ac)
            sources.append(
                {
                    "modifier": "monk_unarmored_defense",
                    "source_action_id": "srd.monk_unarmored_defense",
                    "formula": "10+dex_modifier+wis_modifier",
                    "value": monk_unarmored_ac,
                }
            )
        draconic_ac = self._draconic_resilience_armor_class(target)
        if draconic_ac is not None:
            ac = max(ac, draconic_ac)
            sources.append(
                {
                    "modifier": "draconic_resilience",
                    "source_action_id": "srd.draconic_resilience",
                    "formula": "10+dex_modifier+cha_modifier",
                    "value": draconic_ac,
                }
            )
        for effect in self._status_effects_for(target):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            if modifiers.get("armor_class_requires_unarmored") is True and self._is_wearing_armor(
                target
            ):
                continue
            if modifiers.get("armor_class_requires_no_shield") is True and self._is_wielding_shield(
                target
            ):
                continue
            source = {
                "effect_id": effect.get("effect_id"),
                "source_action_id": effect.get("source_action_id"),
            }
            override = modifiers.get("armor_class_override")
            if isinstance(override, int) and not isinstance(override, bool):
                ac = override
                sources.append(
                    {
                        **source,
                        "modifier": "armor_class_override",
                        "value": override,
                    }
                )
            formula = modifiers.get("armor_class_formula")
            if formula in {"13+dex_modifier", "15+dex_modifier"}:
                base_value = 13 if formula == "13+dex_modifier" else 15
                formula_ac = base_value + self._ability_modifier(
                    self._ability_source(target), "dex"
                )
                ac = max(ac, formula_ac)
                sources.append(
                    {
                        **source,
                        "modifier": "armor_class_formula",
                        "formula": formula,
                        "value": formula_ac,
                    }
                )
            minimum = modifiers.get("armor_class_minimum")
            if isinstance(minimum, int) and not isinstance(minimum, bool):
                minimum_ac = max(minimum_ac or minimum, minimum)
                sources.append(
                    {
                        **source,
                        "modifier": "armor_class_minimum",
                        "minimum": minimum,
                    }
                )
            ac_bonus = modifiers.get("armor_class_bonus")
            if isinstance(ac_bonus, int) and not isinstance(ac_bonus, bool):
                bonus += ac_bonus
                sources.append(
                    {
                        **source,
                        "modifier": "armor_class_bonus",
                        "amount": ac_bonus,
                    }
                )
        if minimum_ac is not None:
            ac = max(ac, minimum_ac)
        return base_ac, ac + bonus, sources

    def _is_wearing_armor(self, target: Character | Monster | Combatant) -> bool:
        if isinstance(target, Character):
            return is_wearing_armor(target)
        if isinstance(target, Combatant) and target.entity_id in self.state.characters:
            return is_wearing_armor(self.state.characters[target.entity_id])
        return False

    def _is_wielding_shield(self, target: Character | Monster | Combatant) -> bool:
        if isinstance(target, Character):
            return is_wielding_shield(target)
        if isinstance(target, Combatant) and target.entity_id in self.state.characters:
            return is_wielding_shield(self.state.characters[target.entity_id])
        return False

    def _draconic_resilience_armor_class(
        self,
        target: Character | Monster | Combatant,
    ) -> int | None:
        if isinstance(target, Character):
            return draconic_resilience_armor_class(target)
        if isinstance(target, Combatant) and target.entity_id in self.state.characters:
            return draconic_resilience_armor_class(self.state.characters[target.entity_id])
        return None

    def _barbarian_unarmored_defense_armor_class(
        self,
        target: Character | Monster | Combatant,
    ) -> int | None:
        if isinstance(target, Character):
            return barbarian_unarmored_defense_armor_class(target)
        if isinstance(target, Combatant) and target.entity_id in self.state.characters:
            return barbarian_unarmored_defense_armor_class(self.state.characters[target.entity_id])
        return None

    def _monk_unarmored_defense_armor_class(
        self,
        target: Character | Monster | Combatant,
    ) -> int | None:
        if isinstance(target, Character):
            return monk_unarmored_defense_armor_class(target)
        if isinstance(target, Combatant) and target.entity_id in self.state.characters:
            return monk_unarmored_defense_armor_class(self.state.characters[target.entity_id])
        return None

    @staticmethod
    def _kept_d20(roll: RollResult) -> int:
        for die in roll.dice:
            if die.sides == 20 and die.kept:
                return die.value
        raise AutomationError("roll did not include a kept d20")

    def _ability_modifier(self, entity: Character | Monster | Combatant, ability: str) -> int:
        source = self._ability_source(entity)
        return effective_ability_modifier(
            source,
            ability,
            status_effects=self._ability_status_effects(entity, source),
        )

    def _ability_status_effects(
        self,
        entity: Character | Monster | Combatant,
        source: Character | Monster | Combatant,
    ) -> list[dict[str, Any]]:
        effects = self._status_effects_for(entity)
        if entity is not source or self.state.encounter is None:
            return effects
        source_id = getattr(source, "id", None)
        if source_id is None:
            return effects
        for combatant in self.state.encounter.combatants.values():
            if combatant.entity_id == source_id:
                effects.extend(combatant.status_effects)
        return effects

    def _saving_throw_bonus(
        self,
        target: Character | Monster | Combatant,
        ability: str,
    ) -> tuple[int, bool, list[dict[str, Any]]]:
        source = self._ability_source(target)
        proficiency_source = self._proficiency_source(target)
        proficiency_sources = saving_throw_proficiency_sources(proficiency_source, ability)
        proficient = bool(proficiency_sources)
        bonus = self._ability_modifier(source, ability)
        if proficient:
            bonus += int(getattr(proficiency_source, "proficiency_bonus", 2))
        return bonus, proficient, proficiency_sources

    def _ability_check_bonus(
        self,
        actor: Character | Monster | Combatant,
        ability: str,
        *,
        skill: str | None = None,
        tool: str | None = None,
    ) -> tuple[int, bool, list[str], str | None]:
        source = self._ability_source(actor)
        proficiency_source = self._proficiency_source(actor)
        skill_proficient = bool(
            skill
            and skill
            in {
                _proficiency_key(str(item))
                for item in getattr(proficiency_source, "skill_proficiencies", [])
            }
        )
        tool_proficient = bool(
            tool
            and tool
            in {
                _proficiency_key(str(item))
                for item in getattr(proficiency_source, "tool_proficiencies", [])
            }
        )
        sources: list[str] = []
        if skill_proficient and skill is not None:
            sources.append(f"skill:{skill}")
        if tool_proficient and tool is not None:
            sources.append(f"tool:{tool}")
        bonus = self._ability_modifier(source, ability)
        if sources:
            bonus += int(getattr(proficiency_source, "proficiency_bonus", 2))
        expertise_bonus = self._skill_expertise_bonus(
            proficiency_source,
            skill=skill,
        )
        if expertise_bonus:
            bonus += expertise_bonus
            sources.append(f"feature:expertise:{skill}")
        uses_proficiency = bool(sources)
        jack_bonus = self._jack_of_all_trades_bonus(
            proficiency_source,
            skill=skill,
            uses_proficiency=uses_proficiency,
        )
        if jack_bonus:
            bonus += jack_bonus
            sources.append("feature:jack_of_all_trades")
        thaumaturge_bonus = self._cleric_thaumaturge_bonus(
            proficiency_source,
            ability=ability,
            skill=skill,
        )
        if thaumaturge_bonus:
            bonus += thaumaturge_bonus
            sources.append("feature:divine_order_thaumaturge")
        magician_bonus = self._druid_magician_bonus(
            proficiency_source,
            ability=ability,
            skill=skill,
        )
        if magician_bonus:
            bonus += magician_bonus
            sources.append("feature:primal_order_magician")
        proficiency_advantage = "advantage" if skill_proficient and tool_proficient else None
        return bonus, uses_proficiency, sources, proficiency_advantage

    @staticmethod
    def _skill_expertise_bonus(
        actor: Character | Monster | Combatant,
        *,
        skill: str | None,
    ) -> int:
        if skill is None or not isinstance(actor, Character):
            return 0
        skill_proficiencies = {
            _proficiency_key(str(item)) for item in getattr(actor, "skill_proficiencies", [])
        }
        skill_expertise = {
            _proficiency_key(str(item)) for item in getattr(actor, "skill_expertise", [])
        }
        if skill not in skill_proficiencies or skill not in skill_expertise:
            return 0
        return int(actor.proficiency_bonus)

    @staticmethod
    def _jack_of_all_trades_bonus(
        actor: Character | Monster | Combatant,
        *,
        skill: str | None,
        uses_proficiency: bool,
    ) -> int:
        if skill is None or uses_proficiency or not isinstance(actor, Character):
            return 0
        if int(actor.class_levels.get("bard", 0)) < 2:
            return 0
        return int(actor.proficiency_bonus) // 2

    @staticmethod
    def _cleric_thaumaturge_bonus(
        actor: Character | Monster | Combatant,
        *,
        ability: str,
        skill: str | None,
    ) -> int:
        if not isinstance(actor, Character):
            return 0
        return cleric_thaumaturge_check_bonus(actor, ability=ability, skill=skill)

    @staticmethod
    def _druid_magician_bonus(
        actor: Character | Monster | Combatant,
        *,
        ability: str,
        skill: str | None,
    ) -> int:
        if not isinstance(actor, Character):
            return 0
        return druid_magician_check_bonus(actor, ability=ability, skill=skill)

    def _proficiency_source(
        self,
        target: Character | Monster | Combatant,
    ) -> Character | Monster | Combatant:
        if isinstance(target, Combatant) and target.entity_id in self.state.characters:
            return self.state.characters[target.entity_id]
        if isinstance(target, Combatant) and target.entity_id in self.state.monsters:
            return self.state.monsters[target.entity_id]
        return target

    @staticmethod
    def _get_resource(actor: Character | Monster | Combatant, resource: str) -> int:
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
    def _set_resource(actor: Character | Monster | Combatant, resource: str, value: int) -> None:
        if isinstance(actor, Character) and resource == "gold":
            actor.gold = value
            return
        if isinstance(actor, Character) and resource.startswith("spell_slot_"):
            actor.spell_slots[resource.removeprefix("spell_slot_")] = value
            return
        if isinstance(actor, Character) and (
            resource in actor.resources or resource.startswith("srd.resource.")
        ):
            actor.resources[resource] = value
            return
        if not hasattr(actor, "inventory"):
            raise AutomationError(f"actor has no resource store for {resource}")
        inventory = getattr(actor, "inventory")
        if not isinstance(inventory, dict):
            raise AutomationError(f"actor has invalid resource store for {resource}")
        inventory[resource] = value


def _string_set(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {str(item) for item in value}
    if isinstance(value, (tuple, set, frozenset)):
        return {str(item) for item in value}
    return set()

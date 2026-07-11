from __future__ import annotations

import re
from typing import Any

from .automation.definitions import ActionDefinition, SpellDefinition
from .automation.effects import EffectInstance
from .automation.executor import AutomationError, AutomationExecutor
from .compendium.loader import Compendium
from .compendium.validators import ALLOWED_DAMAGE_TYPES
from .dice import RollResult, RollService
from .economy import EconomyTracker
from .invariants import require_game_state_invariants
from .models import Character, Combatant, GameState, Monster
from .persistence import AuditLog
from .positioning import TacticalGraph
from .rules.auras import holy_aura_benefit_sources
from .rules.checks import (
    actor_ability_modifier,
    charisma_check_minimum_d20_adjustment,
    d20_expression,
    roll_check,
)
from .rules.class_features import (
    DARK_ONES_OWN_LUCK_RESOURCE,
    FOCUS_POINTS_RESOURCE,
    INDOMITABLE_MIGHT_ACTION_ID,
    INDOMITABLE_RESOURCE,
    PRIMAL_KNOWLEDGE_SKILLS,
    RELENTLESS_RAGE_ACTION_ID,
    RELENTLESS_RAGE_USES_SINCE_REST_RESOURCE,
    RELIABLE_TALENT_ACTION_ID,
    RELIABLE_TALENT_D20_FLOOR,
    STROKE_OF_LUCK_ACTION_ID,
    STROKE_OF_LUCK_D20,
    STROKE_OF_LUCK_RESOURCE,
    aura_of_protection_radius_ft,
    aura_of_protection_saving_throw_bonus,
    cleric_thaumaturge_check_bonus,
    draconic_elemental_affinity_damage_type,
    druid_magician_check_bonus,
    druid_natures_ward_resistance_type,
    has_condition,
    has_fighter_feature,
    has_relentless_rage,
    has_rogue_thief_feature,
    has_warlock_fiend_feature,
    indomitable_might_total_floor,
    monk_disciplined_survivor_applies,
    relentless_rage_dc,
    relentless_rage_success_hp,
    reliable_talent_d20_adjustment,
    remarkable_athlete_applies_to_check,
    rogue_stroke_of_luck_applies,
    saving_throw_proficiency_sources,
    warlock_fiendish_resilience_damage_type,
)
from .rules.combat import apply_healing as apply_healing_rule
from .rules.conditions import (
    apply_exhaustion,
    exhaustion_d20_penalty,
    exhaustion_level,
    passive_d20_test_penalty,
    passive_d20_test_penalty_sources,
)
from .rules.death import roll_death_save as roll_death_save_rule
from .rules.difficulty import resolve_dc
from .rules.rests import long_rest as long_rest_rule
from .rules.rests import short_rest as short_rest_rule


class EngineTools:
    def __init__(
        self,
        state: GameState,
        compendium: Compendium,
        audit_log: AuditLog,
        roll_service: RollService | None = None,
        economy: EconomyTracker | None = None,
    ):
        self.state = state
        self.compendium = compendium
        self.audit_log = audit_log
        self.roll_service = roll_service or RollService(state)
        self.economy = economy or EconomyTracker(
            state.encounter.action_budgets if state.encounter is not None else None
        )

    def roll_check(
        self,
        actor_id: str,
        ability: str,
        *,
        skill: str | None = None,
        tool: str | None = None,
        difficulty_tier: str | None = None,
        dc_ref: str | None = None,
        advantage: str | None = None,
        relies_on_sight: bool = False,
        examines_within_1_ft: bool = False,
        use_dark_ones_own_luck: bool = False,
        use_tactical_mind: bool = False,
        use_primal_knowledge: bool = False,
        use_stroke_of_luck: bool = False,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        idempotency_key = idempotency_key or f"roll_check:{self.state.event_counter}"
        cached = self._cached_result(idempotency_key)
        if cached is not None:
            return cached
        actor = self._ability_source(actor_id)
        proficiency_source = self._proficiency_source(actor_id)
        normalized_skill = _proficiency_key(skill) if skill else None
        normalized_tool = _proficiency_key(tool) if tool else None
        original_ability = ability.lower()
        effective_ability = original_ability
        primal_knowledge = self._primal_knowledge_ability_check(
            actor_id,
            original_ability,
            normalized_skill,
            proficiency_source,
            use_primal_knowledge=use_primal_knowledge,
        )
        if primal_knowledge is not None:
            effective_ability = str(primal_knowledge["ability"])
        proficient, proficiency_sources, proficiency_advantage = _check_proficiency(
            proficiency_source,
            skill=normalized_skill,
            tool=normalized_tool,
        )
        extra_bonus = _jack_of_all_trades_bonus(
            proficiency_source,
            skill=normalized_skill,
            uses_proficiency=proficient,
        )
        if extra_bonus:
            proficiency_sources = [*proficiency_sources, "feature:jack_of_all_trades"]
        expertise_bonus = _skill_expertise_bonus(
            proficiency_source,
            skill=normalized_skill,
        )
        if expertise_bonus:
            extra_bonus += expertise_bonus
            proficiency_sources = [
                *proficiency_sources,
                f"feature:expertise:{normalized_skill}",
            ]
        thaumaturge_bonus = _cleric_thaumaturge_bonus(
            proficiency_source,
            ability=effective_ability,
            skill=normalized_skill,
        )
        if thaumaturge_bonus:
            extra_bonus += thaumaturge_bonus
            proficiency_sources = [*proficiency_sources, "feature:divine_order_thaumaturge"]
        magician_bonus = _druid_magician_bonus(
            proficiency_source,
            ability=effective_ability,
            skill=normalized_skill,
        )
        if magician_bonus:
            extra_bonus += magician_bonus
            proficiency_sources = [*proficiency_sources, "feature:primal_order_magician"]
        passive_bonus, passive_bonus_sources = self._ability_check_passive_bonus(
            actor_id,
            effective_ability,
        )
        extra_bonus += passive_bonus
        if use_tactical_mind and use_stroke_of_luck:
            raise ValueError("choose only one failed ability check feature")
        if use_tactical_mind:
            self._validate_tactical_mind_available(proficiency_source)
        if use_dark_ones_own_luck:
            self._validate_dark_ones_own_luck_available(proficiency_source)
        if use_stroke_of_luck:
            self._validate_stroke_of_luck_available(proficiency_source)
        d20_penalty, d20_penalty_sources = self._exhaustion_penalty_for(actor_id)
        contexts: set[str] = set()
        if relies_on_sight:
            contexts.add("sight")
        if examines_within_1_ft:
            contexts.add("within_1_ft_examination")
        status_advantage, status_sources = self._ability_check_status_advantage(
            actor_id,
            effective_ability,
            normalized_skill,
            contexts=contexts,
        )
        merged_advantage = _merge_advantage(
            _merge_advantage(advantage, status_advantage),
            proficiency_advantage,
        )
        status_effects = self._status_effects_for_actor(actor_id)
        result = roll_check(
            actor_id=actor_id,
            actor=actor,
            ability=effective_ability,
            roll_service=self.roll_service,
            difficulty_tier=difficulty_tier,
            dc_ref=dc_ref,
            advantage=merged_advantage,
            proficiency=proficient,
            skill=normalized_skill,
            tool=normalized_tool,
            proficiency_sources=proficiency_sources,
            extra_bonus=extra_bonus,
            d20_penalty=d20_penalty,
            d20_penalty_sources=d20_penalty_sources,
            status_effects=status_effects,
        )
        payload: dict[str, Any] = result.to_dict()
        payload["original_ability"] = original_ability
        payload["status_advantage"] = status_advantage
        payload["status_sources"] = status_sources
        payload["passive_bonus"] = passive_bonus
        payload["passive_bonus_sources"] = passive_bonus_sources
        if primal_knowledge is not None:
            payload["primal_knowledge"] = primal_knowledge
        reliable_talent = _apply_reliable_talent_to_check_payload(
            proficiency_source,
            payload,
            result.roll,
            proficiency_sources,
        )
        if reliable_talent is not None:
            payload["reliable_talent"] = reliable_talent
        glibness = _apply_charisma_check_minimum_d20_to_check_payload(
            payload,
            result.roll,
            status_effects,
        )
        if glibness is not None:
            payload["glibness"] = glibness
        dice_rolls = [result.roll.to_dict()]
        dark_ones_own_luck = self._apply_dark_ones_own_luck_to_roll(
            actor_id,
            payload,
            proficiency_source,
            use_dark_ones_own_luck=use_dark_ones_own_luck,
        )
        if dark_ones_own_luck is not None:
            payload["dark_ones_own_luck"] = dark_ones_own_luck["result"]
            dice_rolls.append(dark_ones_own_luck["roll"])
        indomitable_might = _apply_indomitable_might_to_d20_payload(
            proficiency_source,
            payload,
            effective_ability,
        )
        if indomitable_might is not None:
            payload["indomitable_might"] = indomitable_might
        tactical_mind = self._apply_tactical_mind_to_check(
            actor_id,
            payload,
            proficiency_source,
            use_tactical_mind=use_tactical_mind,
        )
        if tactical_mind is not None:
            payload["tactical_mind"] = tactical_mind["result"]
            dice_rolls.append(tactical_mind["roll"])
        stroke_of_luck = self._apply_stroke_of_luck_to_failed_d20_test(
            actor_id,
            payload,
            proficiency_source,
            result.roll,
            use_stroke_of_luck=use_stroke_of_luck,
        )
        if stroke_of_luck is not None:
            payload["stroke_of_luck"] = stroke_of_luck
        self.audit_log.append(
            self.state,
            idempotency_key=idempotency_key,
            tool_name="roll_check",
            tool_args={
                "actor_id": actor_id,
                "ability": ability,
                "skill": normalized_skill,
                "tool": normalized_tool,
                "difficulty_tier": difficulty_tier,
                "dc_ref": dc_ref,
                "advantage": merged_advantage,
                "relies_on_sight": relies_on_sight,
                "examines_within_1_ft": examines_within_1_ft,
                "use_dark_ones_own_luck": use_dark_ones_own_luck,
                "use_tactical_mind": use_tactical_mind,
                "use_primal_knowledge": use_primal_knowledge,
                "use_stroke_of_luck": use_stroke_of_luck,
            },
            tool_result=payload,
            dice_rolls=dice_rolls,
        )
        require_game_state_invariants(self.state)
        return payload

    def roll_save(
        self,
        actor_id: str,
        ability: str,
        *,
        difficulty_tier: str | None = None,
        dc_ref: str | None = None,
        advantage: str | None = None,
        use_dark_ones_own_luck: bool = False,
        use_indomitable: bool = False,
        use_disciplined_survivor: bool = False,
        use_stroke_of_luck: bool = False,
        avoid_or_end_condition: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        idempotency_key = idempotency_key or f"roll_save:{self.state.event_counter}"
        cached = self._cached_result(idempotency_key)
        if cached is not None:
            return cached
        actor = self._ability_source(actor_id)
        proficiency_source = self._proficiency_source(actor_id)
        proficient, proficiency_sources = self._saving_throw_proficiency(
            proficiency_source,
            ability,
        )
        d20_penalty, d20_penalty_sources = self._exhaustion_penalty_for(actor_id)
        danger_sense_advantage = self._danger_sense_advantage(
            actor_id,
            ability,
            proficiency_source,
        )
        contexts: set[str] = set()
        if avoid_or_end_condition:
            contexts.add(f"avoid_or_end_condition:{avoid_or_end_condition.lower()}")
        status_advantage, status_sources = self._saving_throw_status_advantage(
            actor_id,
            ability,
            contexts=contexts,
        )
        passive_bonus, passive_bonus_sources = self._saving_throw_passive_bonus(actor_id, ability)
        if use_dark_ones_own_luck:
            self._validate_dark_ones_own_luck_available(proficiency_source)
        if use_indomitable:
            self._validate_indomitable_available(proficiency_source)
        if use_disciplined_survivor:
            self._validate_disciplined_survivor_available(proficiency_source)
        if use_stroke_of_luck:
            self._validate_stroke_of_luck_available(proficiency_source)
        if sum([use_indomitable, use_disciplined_survivor, use_stroke_of_luck]) > 1:
            raise ValueError("choose only one failed saving throw feature")
        auto_fail_sources = self._saving_throw_auto_failure_sources(actor_id, ability)
        if auto_fail_sources and (use_indomitable or use_disciplined_survivor):
            raise ValueError("failed saving throw reroll features require a rolled failed save")
        if auto_fail_sources and use_stroke_of_luck:
            raise ValueError("Stroke of Luck requires a rolled failed D20 Test")
        dc, dc_source = resolve_dc(difficulty_tier=difficulty_tier, dc_ref=dc_ref)
        bonus = (
            actor_ability_modifier(
                actor,
                ability,
                status_effects=self._status_effects_for_actor(actor_id),
            )
            + (int(getattr(proficiency_source, "proficiency_bonus", 2)) if proficient else 0)
            + passive_bonus
            - d20_penalty
        )
        if auto_fail_sources:
            auto_fail_payload: dict[str, Any] = {
                "actor_id": actor_id,
                "ability": ability,
                "skill": None,
                "dc": dc,
                "dc_source": dc_source,
                "roll": None,
                "success": False,
                "total": None,
                "bonus": bonus,
                "proficient": proficient,
                "d20_penalty": d20_penalty,
                "d20_penalty_sources": d20_penalty_sources,
                "tool": "roll_save",
                "status_advantage": status_advantage,
                "status_sources": [{"kind": "auto_fail", **source} for source in auto_fail_sources],
                "auto_failed": True,
                "passive_bonus": passive_bonus,
                "passive_bonus_sources": passive_bonus_sources,
                "proficiency_sources": proficiency_sources,
            }
            expiry = self._expire_next_saving_throw_disadvantage(actor_id, "roll_save")
            if expiry is not None:
                auto_fail_payload["effect_expired"] = expiry
            self.audit_log.append(
                self.state,
                idempotency_key=idempotency_key,
                tool_name="roll_save",
                tool_args={
                    "actor_id": actor_id,
                    "ability": ability,
                    "difficulty_tier": difficulty_tier,
                    "dc_ref": dc_ref,
                    "advantage": advantage,
                    "use_dark_ones_own_luck": use_dark_ones_own_luck,
                    "use_indomitable": use_indomitable,
                    "use_disciplined_survivor": use_disciplined_survivor,
                    "use_stroke_of_luck": use_stroke_of_luck,
                    "avoid_or_end_condition": avoid_or_end_condition,
                },
                tool_result=auto_fail_payload,
                dice_rolls=[],
            )
            require_game_state_invariants(self.state)
            return auto_fail_payload
        result = roll_check(
            actor_id=actor_id,
            actor=actor,
            ability=ability,
            roll_service=self.roll_service,
            difficulty_tier=difficulty_tier,
            dc_ref=dc_ref,
            advantage=_merge_advantage(
                _merge_advantage(advantage, danger_sense_advantage),
                status_advantage,
            ),
            proficiency=False,
            extra_bonus=(
                (int(getattr(proficiency_source, "proficiency_bonus", 2)) if proficient else 0)
                + passive_bonus
            ),
            d20_penalty=d20_penalty,
            d20_penalty_sources=d20_penalty_sources,
            status_effects=self._status_effects_for_actor(actor_id),
        )
        payload: dict[str, Any] = result.to_dict()
        payload["tool"] = "roll_save"
        payload["status_advantage"] = status_advantage
        payload["status_sources"] = status_sources
        payload["passive_bonus"] = passive_bonus
        payload["passive_bonus_sources"] = passive_bonus_sources
        payload["proficient"] = proficient
        payload["proficiency_sources"] = proficiency_sources
        dice_rolls = [result.roll.to_dict()]
        dark_ones_own_luck = self._apply_dark_ones_own_luck_to_roll(
            actor_id,
            payload,
            proficiency_source,
            use_dark_ones_own_luck=use_dark_ones_own_luck,
        )
        if dark_ones_own_luck is not None:
            payload["dark_ones_own_luck"] = dark_ones_own_luck["result"]
            dice_rolls.append(dark_ones_own_luck["roll"])
        indomitable_might = _apply_indomitable_might_to_d20_payload(
            proficiency_source,
            payload,
            ability,
        )
        if indomitable_might is not None:
            payload["indomitable_might"] = indomitable_might
        indomitable = self._apply_indomitable_to_save(
            payload,
            proficiency_source,
            use_indomitable=use_indomitable,
        )
        if indomitable is not None:
            payload["indomitable"] = indomitable["result"]
            dice_rolls.append(indomitable["roll"])
        disciplined_survivor = self._apply_disciplined_survivor_to_save(
            payload,
            proficiency_source,
            use_disciplined_survivor=use_disciplined_survivor,
        )
        if disciplined_survivor is not None:
            payload["disciplined_survivor"] = disciplined_survivor["result"]
            dice_rolls.append(disciplined_survivor["roll"])
        stroke_of_luck = self._apply_stroke_of_luck_to_failed_d20_test(
            actor_id,
            payload,
            proficiency_source,
            result.roll,
            use_stroke_of_luck=use_stroke_of_luck,
        )
        if stroke_of_luck is not None:
            payload["stroke_of_luck"] = stroke_of_luck
        expiry = self._expire_next_saving_throw_disadvantage(actor_id, "roll_save")
        if expiry is not None:
            payload["effect_expired"] = expiry
        self.audit_log.append(
            self.state,
            idempotency_key=idempotency_key,
            tool_name="roll_save",
            tool_args={
                "actor_id": actor_id,
                "ability": ability,
                "difficulty_tier": difficulty_tier,
                "dc_ref": dc_ref,
                "advantage": advantage,
                "use_dark_ones_own_luck": use_dark_ones_own_luck,
                "use_indomitable": use_indomitable,
                "use_disciplined_survivor": use_disciplined_survivor,
                "use_stroke_of_luck": use_stroke_of_luck,
                "avoid_or_end_condition": avoid_or_end_condition,
            },
            tool_result=payload,
            dice_rolls=dice_rolls,
        )
        require_game_state_invariants(self.state)
        return payload

    def attack(
        self,
        attacker_id: str,
        target_id: str,
        action_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        idempotency_key = idempotency_key or f"attack:{self.state.event_counter}"
        return self._execute_action(
            action_id=action_id,
            actor_id=attacker_id,
            targets=[target_id],
            idempotency_key=idempotency_key,
        )

    def cast_spell(
        self,
        caster_id: str,
        spell_id: str,
        targets: list[str],
        slot_level: int,
        *,
        as_ritual: bool = False,
        use_rod_of_absorption: bool = False,
        params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        idempotency_key = idempotency_key or f"cast_spell:{self.state.event_counter}"
        execution_params = dict(params or {})
        execution_params["slot_level"] = slot_level
        if as_ritual:
            execution_params["as_ritual"] = True
        if use_rod_of_absorption:
            execution_params["use_rod_of_absorption"] = True
        return self._execute_action(
            action_id=spell_id,
            actor_id=caster_id,
            targets=targets,
            params=execution_params,
            idempotency_key=idempotency_key,
        )

    def use_item(
        self,
        actor_id: str,
        item_id: str,
        targets: list[str] | None = None,
        action_id: str | None = None,
        params: dict[str, Any] | None = None,
        *,
        fast_hands: bool = False,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        idempotency_key = idempotency_key or f"use_item:{self.state.event_counter}"
        cached = self._cached_result(idempotency_key)
        if cached is not None:
            return cached
        if item_id in self.compendium.items:
            item = self.compendium.items[item_id]
            if not item.actions:
                raise ValueError(f"item has no executable actions: {item_id}")
            selected_action_id = action_id or item.actions[0]
            if selected_action_id not in item.actions:
                raise ValueError(f"action {selected_action_id} is not provided by item {item_id}")
        else:
            raise KeyError(f"unknown item: {item_id}")
        action = self.compendium.action(selected_action_id)
        if fast_hands:
            action = self._fast_hands_item_action(actor_id, item_id, action)
        return self._execute_definition(
            action,
            actor_id=actor_id,
            targets=[actor_id] if targets is None else targets,
            params=params,
            idempotency_key=idempotency_key,
        )

    def perform_action(
        self,
        actor_id: str,
        action_id: str,
        targets: list[str] | None = None,
        params: dict[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        idempotency_key = idempotency_key or f"perform_action:{self.state.event_counter}"
        return self._execute_action(
            action_id=action_id,
            actor_id=actor_id,
            targets=targets or [],
            params=params,
            idempotency_key=idempotency_key,
        )

    def move(
        self,
        actor_id: str,
        *,
        to_zone_id: str | None = None,
        to_position_node_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        idempotency_key = idempotency_key or f"move:{self.state.event_counter}"
        cached = self._cached_result(idempotency_key)
        if cached is not None:
            return cached
        action = ActionDefinition(
            id="core.move",
            name="Move",
            localization={"en": "Move", "zh": "移动", "aliases": []},
            source="core",
            rules_version=self.state.rules_data_version,
            action_type="base_action",
            action_economy="movement",
            range={"self": True},
            target_policy={"min": 0, "max": 0},
            automation=[{"type": "move"}],
            audit_label="Move",
        )
        params = self._validated_move_params(
            actor_id,
            to_zone_id=to_zone_id,
            to_position_node_id=to_position_node_id,
        )
        return self._execute_definition(
            action,
            actor_id=actor_id,
            targets=[],
            params=params,
            idempotency_key=idempotency_key,
        )

    def interact(
        self,
        actor_id: str,
        feature_id: str,
        intent: str,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        idempotency_key = (
            idempotency_key or f"interact:{actor_id}:{feature_id}:{self.state.event_counter}"
        )
        cached = self._cached_result(idempotency_key)
        if cached is not None:
            return cached
        self.audit_log.append(
            self.state,
            idempotency_key=idempotency_key,
            tool_name="interact",
            tool_args={"actor_id": actor_id, "feature_id": feature_id, "intent": intent},
            tool_result={"accepted": True},
        )
        return {"accepted": True, "feature_id": feature_id, "intent": intent}

    def trigger_event(
        self,
        event_id: str,
        actor_ids: list[str] | None = None,
        targets: list[str] | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if event_id not in self.compendium.events:
            raise KeyError(f"unknown event: {event_id}")
        event = self.compendium.events[event_id]
        action = ActionDefinition(
            id=event.id,
            name=event.name,
            localization={"en": event.name, "zh": event.name, "aliases": []},
            source=event.source,
            rules_version=event.rules_version,
            action_type="campaign_event",
            action_economy="none",
            range={},
            target_policy={"min": 0},
            automation=event.automation,
            audit_label=event.audit_label,
        )
        return self._execute_definition(
            action,
            actor_id=(actor_ids or ["system"])[0],
            targets=targets or actor_ids or [],
            idempotency_key=idempotency_key or f"event:{event_id}:{self.state.event_counter}",
        )

    def apply_hazard(
        self,
        target_ids: list[str],
        hazard_type: str,
        params: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        allowed_sources = {"map", "campaign_pack", "player_declaration", "rules_discrete"}
        if params.get("source") not in allowed_sources:
            raise ValueError("hazard params must include a traceable source")
        hazard = self.compendium.hazard(hazard_type)
        action = ActionDefinition(
            id=hazard.id,
            name=hazard.name,
            localization={"en": hazard.name, "zh": hazard.name, "aliases": []},
            source=hazard.source,
            rules_version=hazard.rules_version,
            action_type="hazard",
            action_economy="none",
            range={},
            target_policy={"min": 1, "harmful": True},
            automation=hazard.automation,
            audit_label=hazard.audit_label,
        )
        return self._execute_definition(
            action,
            actor_id="environment",
            targets=target_ids,
            params=params,
            idempotency_key=idempotency_key or f"hazard:{hazard_type}:{self.state.event_counter}",
        )

    def award(
        self,
        actor_ids: list[str],
        reward_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        idempotency_key = idempotency_key or f"award:{reward_id}:{self.state.event_counter}"
        cached = self._cached_result(idempotency_key)
        if cached is not None:
            return cached
        if not actor_ids:
            raise ValueError("award requires at least one recipient")
        if len(set(actor_ids)) != len(actor_ids):
            raise ValueError("award recipients must be unique")
        reward = self._parse_reward_id(reward_id)
        actors: dict[str, Character] = {}
        for actor_id in actor_ids:
            try:
                actors[actor_id] = self.state.get_character(actor_id)
            except KeyError as exc:
                raise ValueError(f"unknown award recipient: {actor_id}") from exc

        planned: dict[str, dict[str, Any]] = {}
        changes: list[dict[str, Any]] = []
        for actor_id, actor in actors.items():
            next_gold = actor.gold
            next_experience = actor.experience
            next_inventory = dict(actor.inventory)
            if reward["kind"] == "gold":
                before = next_gold
                next_gold += int(reward["amount"])
                changes.append(
                    {
                        "type": "gold",
                        "actor_id": actor_id,
                        "before": before,
                        "after": next_gold,
                    }
                )
            else:
                if reward["kind"] == "campaign_reward":
                    gold = int(reward.get("gold", 0))
                    if gold:
                        before_gold = next_gold
                        next_gold += gold
                        changes.append(
                            {
                                "type": "gold",
                                "actor_id": actor_id,
                                "before": before_gold,
                                "after": next_gold,
                            }
                        )
                    experience = int(reward.get("experience", 0))
                    if experience:
                        before_experience = next_experience
                        next_experience += experience
                        changes.append(
                            {
                                "type": "experience",
                                "actor_id": actor_id,
                                "before": before_experience,
                                "after": next_experience,
                            }
                        )
                    reward_items = list(reward.get("items", []))
                else:
                    reward_items = [
                        {
                            "item_id": str(reward["item_id"]),
                            "quantity": int(reward.get("quantity", 1)),
                        }
                    ]
                for reward_item in reward_items:
                    item_id = str(reward_item["item_id"])
                    quantity = int(reward_item.get("quantity", 1))
                    before = int(next_inventory.get(item_id, 0))
                    next_inventory[item_id] = before + quantity
                    changes.append(
                        {
                            "type": "item",
                            "actor_id": actor_id,
                            "item_id": item_id,
                            "quantity": quantity,
                            "before": before,
                            "after": next_inventory[item_id],
                        }
                    )
            planned[actor_id] = {
                "gold": next_gold,
                "experience": next_experience,
                "inventory": next_inventory,
            }

        snapshots = {
            actor_id: (actor.gold, actor.experience, dict(actor.inventory))
            for actor_id, actor in actors.items()
        }
        audit_length = len(self.audit_log.events)
        event_counter = self.state.event_counter
        try:
            for actor_id, actor in actors.items():
                actor.gold = int(planned[actor_id]["gold"])
                actor.experience = int(planned[actor_id]["experience"])
                actor.inventory = dict(planned[actor_id]["inventory"])
            require_game_state_invariants(self.state)
            self.audit_log.append(
                self.state,
                idempotency_key=idempotency_key,
                tool_name="award",
                tool_args={"actor_ids": actor_ids, "reward_id": reward_id},
                tool_result={"reward": reward, "changes": changes},
            )
        except Exception:
            for actor_id, actor in actors.items():
                gold, experience, inventory = snapshots[actor_id]
                actor.gold = gold
                actor.experience = experience
                actor.inventory = inventory
            del self.audit_log.events[audit_length:]
            self.state.event_counter = event_counter
            raise
        return {"reward": reward, "changes": changes}

    def short_rest(
        self,
        actor_id: str,
        hit_dice_to_spend: dict[str, int],
        *,
        arcane_recovery_slots: dict[str, int] | None = None,
        natural_recovery_slots: dict[str, int] | None = None,
        fiendish_resilience_damage_type: str | None = None,
        memorize_spell: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        idempotency_key = idempotency_key or f"short_rest:{actor_id}:{self.state.event_counter}"
        cached = self._cached_result(idempotency_key)
        if cached is not None:
            return cached
        character = self._character_for_actor(actor_id)
        memorize_spell_plan = (
            self._wizard_memorize_spell_plan(character, memorize_spell) if memorize_spell else None
        )
        character_snapshot = character.to_dict()
        combatant_snapshots = {
            combatant_id: combatant.to_dict()
            for combatant_id, combatant in (
                self.state.encounter.combatants.items() if self.state.encounter is not None else []
            )
            if combatant.entity_id == character.id
        }
        roll_counter = self.state.roll_counter
        event_counter = self.state.event_counter
        audit_length = len(self.audit_log.events)
        try:
            result = short_rest_rule(
                character,
                hit_dice_to_spend,
                self.roll_service,
                arcane_recovery_slots,
                natural_recovery_slots,
                fiendish_resilience_damage_type,
            )
            if memorize_spell_plan is not None:
                result["memorize_spell"] = self._apply_wizard_memorize_spell_plan(
                    character,
                    memorize_spell_plan,
                )
            result["actor_id"] = actor_id
            result["character_id"] = character.id
            self._sync_character_to_combatants(character)
            self.audit_log.append(
                self.state,
                idempotency_key=idempotency_key,
                tool_name="short_rest",
                tool_args={
                    "actor_id": actor_id,
                    "hit_dice_to_spend": hit_dice_to_spend,
                    "arcane_recovery_slots": arcane_recovery_slots or {},
                    "natural_recovery_slots": natural_recovery_slots or {},
                    "fiendish_resilience_damage_type": fiendish_resilience_damage_type,
                    "memorize_spell": memorize_spell or {},
                },
                tool_result=result,
                dice_rolls=list(result.get("dice_rolls", [])),
            )
            require_game_state_invariants(self.state)
        except Exception:
            restored_character = Character.from_dict(character_snapshot)
            character.__dict__.clear()
            character.__dict__.update(restored_character.__dict__)
            if self.state.encounter is not None:
                for combatant_id, snapshot in combatant_snapshots.items():
                    combatant = self.state.encounter.combatants.get(combatant_id)
                    if combatant is None:
                        continue
                    restored_combatant = Combatant.from_dict(snapshot)
                    combatant.__dict__.clear()
                    combatant.__dict__.update(restored_combatant.__dict__)
            self.state.roll_counter = roll_counter
            self.state.event_counter = event_counter
            del self.audit_log.events[audit_length:]
            raise
        return result

    def long_rest(
        self,
        actor_ids: list[str],
        *,
        fiendish_resilience_choices: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        idempotency_key = (
            idempotency_key or f"long_rest:{','.join(actor_ids)}:{self.state.event_counter}"
        )
        cached = self._cached_result(idempotency_key)
        if cached is not None:
            return cached
        results: dict[str, Any] = {}
        for actor_id in actor_ids:
            character = self._character_for_actor(actor_id)
            rest_result = long_rest_rule(
                character,
                (fiendish_resilience_choices or {}).get(actor_id),
            )
            rest_result["actor_id"] = actor_id
            rest_result["character_id"] = character.id
            results[actor_id] = rest_result
            self._sync_character_to_combatants(character)
        result = {"results": results}
        self.audit_log.append(
            self.state,
            idempotency_key=idempotency_key,
            tool_name="long_rest",
            tool_args={
                "actor_ids": actor_ids,
                "fiendish_resilience_choices": fiendish_resilience_choices or {},
            },
            tool_result=result,
        )
        require_game_state_invariants(self.state)
        return result

    def _wizard_memorize_spell_plan(
        self,
        character: Character,
        memorize_spell: dict[str, str],
    ) -> dict[str, Any]:
        if int(character.class_levels.get("wizard", 0)) < 5:
            raise ValueError("Memorize Spell requires Wizard level 5")
        old_ref = (
            memorize_spell.get("replace")
            or memorize_spell.get("old")
            or memorize_spell.get("from")
            or memorize_spell.get("prepared")
        )
        new_ref = (
            memorize_spell.get("with")
            or memorize_spell.get("new")
            or memorize_spell.get("to")
            or memorize_spell.get("spell")
        )
        if not old_ref or not new_ref:
            raise ValueError("Memorize Spell requires replace and with spell ids")
        old_spell = self._spell_definition_for_ref(old_ref)
        new_spell = self._spell_definition_for_ref(new_ref)
        if old_spell.id == new_spell.id:
            raise ValueError("Memorize Spell requires a different replacement spell")
        self._validate_memorizable_wizard_spell(old_spell, role="prepared")
        self._validate_memorizable_wizard_spell(new_spell, role="spellbook")
        prepared_spells = [str(spell_id) for spell_id in character.prepared_spells]
        prepared_refs = {_normalize_spell_ref(spell_id) for spell_id in prepared_spells}
        if old_spell.id not in prepared_refs:
            raise ValueError("Memorize Spell can replace only a prepared Wizard spell")
        if new_spell.id in prepared_refs:
            raise ValueError("Memorize Spell replacement is already prepared")
        known_refs = {_normalize_spell_ref(spell_id) for spell_id in character.known_spells}
        if new_spell.id not in known_refs:
            raise ValueError("Memorize Spell replacement must be in the Wizard spellbook")
        available_slot_levels = {
            int(level)
            for level, count in {**character.spell_slots_max, **character.spell_slots}.items()
            if int(count) > 0
        }
        if new_spell.level not in available_slot_levels:
            raise ValueError("Memorize Spell replacement must be of a level you can cast")

        before = list(prepared_spells)
        after: list[str] = []
        replaced = False
        for spell_id in prepared_spells:
            if not replaced and _normalize_spell_ref(spell_id) == old_spell.id:
                after.append(new_spell.id)
                replaced = True
            else:
                after.append(spell_id)
        return {
            "old_spell": old_spell,
            "new_spell": new_spell,
            "prepared_spells_before": before,
            "prepared_spells_after": after,
        }

    @staticmethod
    def _apply_wizard_memorize_spell_plan(
        character: Character,
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        old_spell = plan["old_spell"]
        new_spell = plan["new_spell"]
        after = [str(spell_id) for spell_id in plan["prepared_spells_after"]]
        character.prepared_spells = after
        return {
            "feature": "srd.memorize_spell",
            "replaced": old_spell.id,
            "with": new_spell.id,
            "prepared_spells_before": list(plan["prepared_spells_before"]),
            "prepared_spells_after": list(after),
        }

    def _spell_definition_for_ref(self, spell_ref: str) -> SpellDefinition:
        normalized = _normalize_spell_ref(str(spell_ref))
        if normalized in self.compendium.spells:
            return self.compendium.spell(normalized)
        if str(spell_ref) in self.compendium.actions:
            action = self.compendium.action(str(spell_ref))
            spell_definition_id = action.properties.get("spell_definition_id")
            if isinstance(spell_definition_id, str):
                return self.compendium.spell(spell_definition_id)
        raise KeyError(f"unknown spell: {spell_ref}")

    @staticmethod
    def _validate_memorizable_wizard_spell(spell: SpellDefinition, *, role: str) -> None:
        if spell.level <= 0:
            raise ValueError(f"Memorize Spell {role} spell must be level 1+")
        if "wizard" not in spell.classes:
            raise ValueError(f"Memorize Spell {role} spell must be a Wizard spell")

    def roll_death_save(
        self,
        actor_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        idempotency_key = idempotency_key or f"death_save:{actor_id}:{self.state.event_counter}"
        cached = self._cached_result(idempotency_key)
        if cached is not None:
            return cached
        entity = self.state.entity_for_actor(actor_id)
        if not isinstance(entity, (Character, Combatant)):
            raise ValueError("death saving throws require a character or combatant")
        feature_source = (
            self.state.characters.get(entity.entity_id) if isinstance(entity, Combatant) else entity
        )
        result = roll_death_save_rule(entity, self.roll_service, feature_source=feature_source)
        result["actor_id"] = actor_id
        if isinstance(entity, Combatant) and entity.entity_id in self.state.characters:
            character = self.state.characters[entity.entity_id]
            self._sync_combatant_to_character(entity, character)
            result["character_id"] = character.id
        elif isinstance(entity, Character):
            self._sync_character_to_combatants(entity)
            result["character_id"] = entity.id
        self.audit_log.append(
            self.state,
            idempotency_key=idempotency_key,
            tool_name="death_save",
            tool_args={"actor_id": actor_id},
            tool_result=result,
            dice_rolls=[result["roll"]],
        )
        require_game_state_invariants(self.state)
        return result

    def request_combat(
        self,
        participants: list[str],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        idempotency_key = idempotency_key or f"request_combat:{self.state.event_counter}"
        cached = self._cached_result(idempotency_key)
        if cached is not None:
            return cached
        self.audit_log.append(
            self.state,
            idempotency_key=idempotency_key,
            tool_name="request_combat",
            tool_args={"participants": participants},
            tool_result={"requested": True},
        )
        return {"requested": True, "participants": participants}

    def request_end_combat(
        self,
        *,
        recover_ammunition: bool = False,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        idempotency_key = idempotency_key or f"request_end_combat:{self.state.event_counter}"
        cached = self._cached_result(idempotency_key)
        if cached is not None:
            return cached
        self.audit_log.append(
            self.state,
            idempotency_key=idempotency_key,
            tool_name="request_end_combat",
            tool_args={"recover_ammunition": recover_ammunition},
            tool_result={
                "requested": True,
                "recover_ammunition": recover_ammunition,
            },
        )
        return {"requested": True, "recover_ammunition": recover_ammunition}

    def apply_damage(
        self,
        target_id: str,
        amount: int,
        damage_type: str,
        source_ref: str,
    ) -> dict[str, Any]:
        idempotency_key = f"gm:damage:{self.state.event_counter}"
        cached = self._cached_result(idempotency_key)
        if cached is not None:
            return cached
        if amount < 0:
            raise ValueError("damage amount cannot be negative")
        normalized_damage_type = damage_type.casefold()
        if normalized_damage_type not in ALLOWED_DAMAGE_TYPES:
            raise ValueError(f"unknown damage type: {damage_type}")
        target = self.state.entity_for_actor(target_id)
        hp_before = int(getattr(target, "hp_current"))
        hp_max_before = int(getattr(target, "hp_max"))
        temp_hp_before = int(getattr(target, "temp_hp", 0))
        damage_taken_before_hp_cap = self._gm_damage_taken_before_hp_cap(
            target_id,
            target,
            amount,
            normalized_damage_type,
        )
        applied = self._apply_gm_damage(target_id, target, amount, normalized_damage_type)
        death_ward = self._death_ward_after_drop_to_zero(
            target_id,
            hp_before=hp_before,
            hp_after_without_death_ward=int(
                getattr(self.state.entity_for_actor(target_id), "hp_current")
            ),
            trigger="gm.apply_damage",
        )
        if death_ward is not None:
            applied = hp_before - int(getattr(self.state.entity_for_actor(target_id), "hp_current"))
        result = {
            "target_id": target_id,
            "amount": amount,
            "damage_type": normalized_damage_type,
            "applied": applied,
        }
        if death_ward is not None:
            result["death_ward"] = death_ward
        relentless_rage = self._relentless_rage_after_gm_damage(
            target_id,
            hp_before=hp_before,
            hp_max=hp_max_before,
            temp_hp_before=temp_hp_before,
            damage_taken=damage_taken_before_hp_cap,
            applied=applied,
        )
        dice_rolls = []
        if relentless_rage is not None:
            result["relentless_rage"] = relentless_rage["result"]
            dice_rolls = relentless_rage["dice_rolls"]
        self.audit_log.append(
            self.state,
            idempotency_key=idempotency_key,
            tool_name="gm.apply_damage",
            tool_args={
                "target_id": target_id,
                "amount": amount,
                "damage_type": normalized_damage_type,
                "source_ref": source_ref,
            },
            tool_result=result,
            dice_rolls=dice_rolls,
        )
        require_game_state_invariants(self.state)
        return result

    def _relentless_rage_after_gm_damage(
        self,
        target_id: str,
        *,
        hp_before: int,
        hp_max: int,
        temp_hp_before: int,
        damage_taken: int,
        applied: int,
    ) -> dict[str, Any] | None:
        target = self.state.entity_for_actor(target_id)
        owner = self._proficiency_source(target_id)
        if hp_before <= 0 or int(getattr(target, "hp_current")) != 0 or applied <= 0:
            return None
        if bool(getattr(target, "dead", False)):
            return None
        if not isinstance(owner, Character) or not has_relentless_rage(owner):
            return None
        if not has_condition(self._status_effects_for_actor(target_id), "raging"):
            return None
        hp_damage_after_temp = max(0, int(damage_taken) - max(0, int(temp_hp_before)))
        if hp_damage_after_temp >= int(hp_before) + int(hp_max):
            return None

        dc = relentless_rage_dc(owner)
        uses_before = max(
            0,
            int(owner.resources.get(RELENTLESS_RAGE_USES_SINCE_REST_RESOURCE, 0)),
        )
        actor = self._ability_source(target_id)
        proficiency_source = self._proficiency_source(target_id)
        proficient, proficiency_sources = self._saving_throw_proficiency(
            proficiency_source,
            "con",
        )
        d20_penalty, d20_penalty_sources = self._exhaustion_penalty_for(target_id)
        status_advantage, status_sources = self._saving_throw_status_advantage(
            target_id,
            "con",
            contexts=set(),
        )
        passive_bonus, passive_sources = self._saving_throw_passive_bonus(target_id, "con")
        bonus = (
            actor_ability_modifier(
                actor,
                "con",
                status_effects=self._status_effects_for_actor(target_id),
            )
            + (int(getattr(proficiency_source, "proficiency_bonus", 2)) if proficient else 0)
            + passive_bonus
            - d20_penalty
        )
        roll = self.roll_service.roll(d20_expression(bonus), advantage=status_advantage)
        success = roll.total >= dc
        owner.resources[RELENTLESS_RAGE_USES_SINCE_REST_RESOURCE] = uses_before + 1
        hp_after = int(getattr(target, "hp_current"))
        if success:
            hp_after = relentless_rage_success_hp(owner)
            self._set_hp_and_clear_death_state(target_id, hp_after)
        else:
            self._sync_hp_state_for_target(target)
        return {
            "dice_rolls": [roll.to_dict()],
            "result": {
                "target_id": target_id,
                "character_id": owner.id,
                "source_action_id": RELENTLESS_RAGE_ACTION_ID,
                "trigger": "gm.apply_damage",
                "dc": dc,
                "roll": roll.to_dict(),
                "bonus": bonus,
                "proficient": proficient,
                "proficiency_sources": proficiency_sources,
                "d20_penalty": d20_penalty,
                "d20_penalty_sources": d20_penalty_sources,
                "passive_bonus": passive_bonus,
                "passive_sources": passive_sources,
                "status_advantage": status_advantage,
                "status_sources": status_sources,
                "total": roll.total,
                "success": success,
                "hp_before": hp_before,
                "hp_after": hp_after,
                "success_hp": relentless_rage_success_hp(owner),
                "uses_since_rest_before": uses_before,
                "uses_since_rest_after": uses_before + 1,
                "next_dc": dc + 5,
            },
        }

    @staticmethod
    def _is_death_ward_effect(effect: dict[str, Any]) -> bool:
        modifiers = effect.get("passive_modifiers", {})
        return isinstance(modifiers, dict) and modifiers.get("death_ward") is True

    def _consume_death_ward(self, target_id: str, *, trigger: str) -> dict[str, Any] | None:
        removed: list[dict[str, Any]] = []
        for owner_type, owner_id, effects in self._actor_effect_lists(target_id):
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
            "target_id": target_id,
            "source_action_id": "srd.death_ward",
            "trigger": trigger,
            "removed_effects": removed,
        }

    def _death_ward_after_drop_to_zero(
        self,
        target_id: str,
        *,
        hp_before: int,
        hp_after_without_death_ward: int,
        trigger: str,
    ) -> dict[str, Any] | None:
        if hp_before <= 0 or hp_after_without_death_ward != 0:
            return None
        death_ward = self._consume_death_ward(target_id, trigger=trigger)
        if death_ward is None:
            return None
        self._set_hp_and_clear_death_state(target_id, 1)
        death_ward["hp_before"] = hp_before
        death_ward["hp_after_without_death_ward"] = hp_after_without_death_ward
        death_ward["hp_after"] = 1
        return death_ward

    def _exhaustion_death_result(
        self,
        target_id: str,
        target: Character | Monster | Combatant,
        owner: Character | Monster | Combatant,
        level: int,
    ) -> dict[str, Any] | None:
        if level < 6:
            return None
        death_ward = self._consume_death_ward(
            target_id,
            trigger="instant_death_without_damage",
        )
        if death_ward is not None:
            death_ward["negated_reason"] = "exhaustion"
            death_ward["exhaustion_level"] = level
            return death_ward
        return _exhaustion_death_result(target_id, target, owner, level)

    def _apply_gm_damage(
        self,
        target_id: str,
        target: Character | Monster | Combatant,
        amount: int,
        damage_type: str,
    ) -> int:
        adjusted = self._gm_damage_taken_before_hp_cap(target_id, target, amount, damage_type)
        temp_hp = int(getattr(target, "temp_hp", 0))
        absorbed = min(temp_hp, adjusted)
        setattr(target, "temp_hp", temp_hp - absorbed)
        if int(getattr(target, "temp_hp", 0)) == 0:
            setattr(target, "temp_hp_source_effect_id", None)
        before = int(getattr(target, "hp_current"))
        setattr(target, "hp_current", max(0, before - (adjusted - absorbed)))
        self._sync_hp_state_for_target(target)
        return before - int(getattr(target, "hp_current"))

    def _gm_damage_taken_before_hp_cap(
        self,
        target_id: str,
        target: Character | Monster | Combatant,
        amount: int,
        damage_type: str,
    ) -> int:
        adjusted = int(amount)
        if damage_type in getattr(target, "immunities", []) or EngineTools._has_damage_immunity(
            target,
            damage_type,
        ):
            return 0
        if (
            damage_type in getattr(target, "resistances", [])
            or EngineTools._has_basic_condition(target, "petrified")
            or self._gm_passive_damage_resistance_sources(target_id, target, damage_type)
        ):
            adjusted //= 2
        elif damage_type in getattr(target, "vulnerabilities", []):
            adjusted *= 2
        return max(0, adjusted)

    def _gm_passive_damage_resistance_sources(
        self,
        target_id: str,
        target: Character | Monster | Combatant,
        damage_type: str,
    ) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        owner = self._character_owner_for_target(target_id, target)
        if owner is not None:
            if draconic_elemental_affinity_damage_type(owner) == damage_type:
                sources.append(
                    {
                        "source_action_id": "srd.elemental_affinity",
                        "modifier": "draconic_elemental_affinity_resistance",
                        "damage_type": damage_type,
                    }
                )
            if druid_natures_ward_resistance_type(owner) == damage_type:
                sources.append(
                    {
                        "source_action_id": "srd.natures_ward",
                        "modifier": "druid_natures_ward_resistance",
                        "damage_type": damage_type,
                    }
                )
            if warlock_fiendish_resilience_damage_type(owner) == damage_type:
                sources.append(
                    {
                        "source_action_id": "srd.fiendish_resilience",
                        "modifier": "warlock_fiendish_resilience",
                        "damage_type": damage_type,
                    }
                )
        for effect in getattr(target, "status_effects", []):
            if not isinstance(effect, dict):
                continue
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            resistances = modifiers.get("damage_resistances", [])
            if isinstance(resistances, str):
                resistances = [resistances]
            if isinstance(resistances, list) and damage_type in {str(item) for item in resistances}:
                sources.append(
                    {
                        "effect_id": effect.get("effect_id"),
                        "source_action_id": effect.get("source_action_id"),
                        "modifier": "damage_resistances",
                        "damage_type": damage_type,
                    }
                )
        return sources

    def _character_owner_for_target(
        self,
        target_id: str,
        target: Character | Monster | Combatant,
    ) -> Character | None:
        if isinstance(target, Character):
            return target
        if isinstance(target, Combatant) and target.entity_id in self.state.characters:
            return self.state.characters[target.entity_id]
        if target_id in self.state.characters:
            return self.state.characters[target_id]
        return None

    @staticmethod
    def _has_basic_condition(target: Character | Monster | Combatant, condition: str) -> bool:
        return any(
            effect.get("condition") == condition
            for effect in getattr(target, "status_effects", [])
            if isinstance(effect, dict)
        )

    @staticmethod
    def _has_damage_immunity(target: Character | Monster | Combatant, damage_type: str) -> bool:
        for effect in getattr(target, "status_effects", []):
            if not isinstance(effect, dict):
                continue
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            immunities = modifiers.get("damage_immunities", [])
            if isinstance(immunities, str):
                immunities = [immunities]
            if isinstance(immunities, list) and damage_type in {str(item) for item in immunities}:
                return True
        return False

    def apply_healing(self, target_id: str, amount: int, source_ref: str) -> dict[str, Any]:
        idempotency_key = f"gm:healing:{self.state.event_counter}"
        cached = self._cached_result(idempotency_key)
        if cached is not None:
            return cached
        if amount < 0:
            raise ValueError("healing amount cannot be negative")
        target = self.state.entity_for_actor(target_id)
        applied = apply_healing_rule(target, amount)
        result = {"target_id": target_id, "amount": amount, "applied": applied}
        self.audit_log.append(
            self.state,
            idempotency_key=idempotency_key,
            tool_name="gm.apply_healing",
            tool_args={"target_id": target_id, "amount": amount, "source_ref": source_ref},
            tool_result=result,
        )
        require_game_state_invariants(self.state)
        return result

    def apply_condition(
        self,
        target_id: str,
        condition: str,
        source_ref: str,
        *,
        applied_by: str = "gm",
        duration: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        idempotency_key = f"gm:condition:{self.state.event_counter}"
        cached = self._cached_result(idempotency_key)
        if cached is not None:
            return cached
        condition = condition.casefold()
        if condition not in self.compendium.conditions:
            raise ValueError(f"unknown condition: {condition}")
        target = self.state.entity_for_actor(target_id)
        if condition == "poisoned" and _target_has_condition(target, "petrified"):
            result = {
                "target_id": target_id,
                "condition": condition,
                "applied": False,
                "immune": True,
                "immunity_condition": "petrified",
            }
            self.audit_log.append(
                self.state,
                idempotency_key=idempotency_key,
                tool_name="gm.apply_condition",
                tool_args={
                    "target_id": target_id,
                    "condition": condition,
                    "source_ref": source_ref,
                    "applied_by": applied_by,
                    "duration": duration or {},
                },
                tool_result=result,
            )
            require_game_state_invariants(self.state)
            return result
        effect = EffectInstance(
            effect_id=f"effect-{self.state.event_counter}-{target_id}",
            source_ref=source_ref,
            source_action_id="gm.apply_condition",
            target_id=target_id,
            applied_by=applied_by,
            condition=condition,
            duration=duration or {},
            audit={"tool": "gm.apply_condition"},
        )
        if condition == "exhaustion":
            owner = self._persistent_condition_owner(target)
            before_level, after_level, applied_effect = apply_exhaustion(
                getattr(owner, "status_effects"),
                effect.to_dict(),
            )
            result = {
                "target_id": target_id,
                "condition": condition,
                "effect_id": applied_effect["effect_id"],
                "applied": True,
                "level_before": before_level,
                "level_after": after_level,
            }
            death_result = self._exhaustion_death_result(target_id, target, owner, after_level)
            if death_result is not None:
                result["death"] = death_result
            self.audit_log.append(
                self.state,
                idempotency_key=idempotency_key,
                tool_name="gm.apply_condition",
                tool_args={
                    "target_id": target_id,
                    "condition": condition,
                    "source_ref": source_ref,
                    "applied_by": applied_by,
                    "duration": duration or {},
                },
                tool_result=result,
            )
            require_game_state_invariants(self.state)
            return result
        target.status_effects.append(effect.to_dict())
        result = {
            "target_id": target_id,
            "condition": condition,
            "effect_id": effect.effect_id,
            "applied": True,
        }
        self.audit_log.append(
            self.state,
            idempotency_key=idempotency_key,
            tool_name="gm.apply_condition",
            tool_args={
                "target_id": target_id,
                "condition": condition,
                "source_ref": source_ref,
                "applied_by": applied_by,
                "duration": duration or {},
            },
            tool_result=result,
        )
        require_game_state_invariants(self.state)
        return result

    def gm_override(self, reason: str, patch: dict[str, Any]) -> dict[str, Any]:
        self.audit_log.append(
            self.state,
            idempotency_key=f"gm:override:{self.state.event_counter}",
            tool_name="gm_override",
            tool_args={"reason": reason, "patch": patch},
            tool_result={"recorded": True},
        )
        return {"recorded": True}

    def _execute_action(
        self,
        *,
        action_id: str,
        actor_id: str,
        targets: list[str],
        params: dict[str, Any] | None = None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        cached = self._cached_result(idempotency_key)
        if cached is not None:
            return cached
        return self._execute_definition(
            self.compendium.action(action_id),
            actor_id=actor_id,
            targets=targets,
            params=params,
            idempotency_key=idempotency_key,
        )

    def _execute_definition(
        self,
        action: ActionDefinition,
        *,
        actor_id: str,
        targets: list[str],
        params: dict[str, Any] | None = None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        cached = self._cached_result(idempotency_key)
        if cached is not None:
            return cached
        params = self._prepared_action_params(action, actor_id, params)
        executor = AutomationExecutor(self.state, self.roll_service, self.audit_log, self.economy)
        result = executor.execute(
            action,
            actor_id=actor_id,
            targets=targets,
            params=params,
            idempotency_key=idempotency_key,
        ).to_dict()
        require_game_state_invariants(self.state)
        return result

    def _prepared_action_params(
        self,
        action: ActionDefinition,
        actor_id: str,
        params: dict[str, Any] | None,
    ) -> dict[str, Any]:
        prepared = dict(params or {})
        for node in action.automation:
            if node.get("type") == "shapechange_form":
                self._prepare_shapechange_form_params(actor_id, node, prepared)
        return prepared

    def _prepare_shapechange_form_params(
        self,
        actor_id: str,
        node: dict[str, Any],
        params: dict[str, Any],
    ) -> None:
        form_param = str(node.get("form_param", "shapechange_form_id"))
        form_id = self._scalar_string_param(params, form_param)
        if form_id not in self.compendium.monsters:
            raise AutomationError("Shapechange form must be a loaded SRD monster")
        monster = self.compendium.monsters[form_id]
        prefix = str(node.get("resolved_param_prefix", "shapechange_form_"))
        params[f"{prefix}id"] = monster.id
        params[f"{prefix}name"] = monster.name
        params[f"{prefix}hit_points"] = monster.hit_points
        params[f"{prefix}cr"] = monster.cr
        params[f"{prefix}creature_type"] = monster.creature_type
        params[f"{prefix}armor_class"] = monster.armor_class
        params[f"{prefix}speed_ft"] = monster.speed_ft
        params[f"{prefix}size"] = monster.size
        params[f"{prefix}actions"] = list(monster.actions)
        params[f"{prefix}abilities"] = dict(monster.abilities)
        params["shapechange_actor_level_or_cr"] = self._shapechange_actor_level_or_cr(actor_id)

    @staticmethod
    def _scalar_string_param(params: dict[str, Any], param_name: str) -> str:
        value = params.get(param_name)
        if isinstance(value, list) and len(value) == 1:
            value = value[0]
        if not isinstance(value, str) or not value.strip():
            raise AutomationError(f"missing required parameter {param_name}")
        return value.strip()

    def _shapechange_actor_level_or_cr(self, actor_id: str) -> float:
        actor = self.state.entity_for_actor(actor_id)
        if isinstance(actor, Combatant) and actor.entity_id in self.state.characters:
            actor = self.state.characters[actor.entity_id]
        elif isinstance(actor, Combatant) and actor.entity_id in self.state.monsters:
            actor = self.state.monsters[actor.entity_id]
        if isinstance(actor, Character):
            return float(sum(max(0, int(level)) for level in actor.class_levels.values()))
        if isinstance(actor, Monster) and actor.id in self.compendium.monsters:
            return float(self.compendium.monsters[actor.id].cr)
        if isinstance(actor, Combatant) and actor.entity_id in self.compendium.monsters:
            return float(self.compendium.monsters[actor.entity_id].cr)
        raise AutomationError("Shapechange actor level or CR is unavailable")

    def _fast_hands_item_action(
        self,
        actor_id: str,
        item_id: str,
        action: ActionDefinition,
    ) -> ActionDefinition:
        actor = self._character_owner(actor_id)
        if not has_rogue_thief_feature(actor, level=3):
            raise ValueError("Fast Hands magic item use requires Rogue Thief level 3")
        if "srd.fast_hands_magic_item" not in actor.actions:
            raise ValueError("actor does not have Fast Hands magic item use")
        if action.action_type != "item" or action.action_economy != "action":
            raise ValueError("Fast Hands requires a magic item action that normally uses an action")
        if action.requirements.get("item") != item_id:
            raise ValueError(f"action {action.id} does not require item {item_id}")
        cloned = ActionDefinition.from_dict(action.to_dict())
        cloned.action_economy = "bonus_action"
        cloned.properties = {
            **cloned.properties,
            "fast_hands": True,
            "original_action_economy": action.action_economy,
        }
        return cloned

    def _character_owner(self, actor_id: str) -> Character:
        entity = self.state.entity_for_actor(actor_id)
        if isinstance(entity, Character):
            return entity
        if isinstance(entity, Combatant) and entity.entity_id in self.state.characters:
            return self.state.characters[entity.entity_id]
        raise ValueError("actor is not a character")

    def _validated_move_params(
        self,
        actor_id: str,
        *,
        to_zone_id: str | None,
        to_position_node_id: str | None,
    ) -> dict[str, Any]:
        if (to_zone_id is None) == (to_position_node_id is None):
            raise ValueError("move requires exactly one destination")
        if self.state.encounter is None:
            if to_position_node_id is not None:
                raise ValueError("exploration movement uses zone ids")
            actor = self.state.get_character(actor_id)
            current_zone = actor.zone_id or self.state.world.current_zone_id
            edges = self.state.world.zone_edges
            if edges and to_zone_id not in edges.get(current_zone, []):
                raise ValueError("destination zone is not connected")
            return {
                "to_zone_id": to_zone_id,
                "movement_cost": 0,
                "update_world_zone": True,
            }

        if to_zone_id is not None:
            raise ValueError("combat movement uses position node ids")
        actor_combatant = self.state.get_combatant(actor_id)
        if actor_combatant.position_node_id is None:
            raise ValueError("combatant has no current position")
        destination_node = to_position_node_id
        if destination_node is None:
            raise ValueError("combat movement requires a position node")
        graph_data = self.state.encounter.tactical_graph
        if graph_data is None:
            raise ValueError("encounter has no tactical graph")
        graph = TacticalGraph.from_dict(graph_data)
        if destination_node not in graph.nodes:
            raise ValueError("destination position node does not exist")
        movement_cost = graph.shortest_distance(
            actor_combatant.position_node_id,
            destination_node,
            movement_cost=True,
        )
        if movement_cost is None:
            raise ValueError("destination position node is not reachable")
        enemy_positions: dict[str, str] = {}
        if not has_condition(actor_combatant.status_effects, "disengaged"):
            enemy_positions = {
                combatant_id: other.position_node_id
                for combatant_id, other in self.state.encounter.combatants.items()
                if other.side != actor_combatant.side
                and other.position_node_id is not None
                and not self._cannot_make_opportunity_attacks(other)
            }
        enemy_reach = {
            combatant_id: other.reach_ft
            for combatant_id, other in self.state.encounter.combatants.items()
        }
        return {
            "to_position_node_id": destination_node,
            "movement_cost": movement_cost,
            "opportunity_attack_triggers": graph.opportunity_attack_triggers(
                actor_from=actor_combatant.position_node_id,
                actor_to=destination_node,
                enemy_positions=enemy_positions,
                enemy_reach_ft=enemy_reach,
            ),
        }

    @staticmethod
    def _cannot_make_opportunity_attacks(actor: Character | Monster | Combatant) -> bool:
        if has_condition(actor.status_effects, "open_hand_addled"):
            return True
        return any(
            bool(effect.get("passive_modifiers", {}).get("cannot_make_opportunity_attacks"))
            for effect in actor.status_effects
            if isinstance(effect.get("passive_modifiers", {}), dict)
        )

    def _cached_result(self, idempotency_key: str) -> dict[str, Any] | None:
        for event in reversed(self.audit_log.events):
            if event.idempotency_key == idempotency_key:
                return dict(event.tool_result)
        return None

    def _parse_reward_id(self, reward_id: str) -> dict[str, Any]:
        campaign_rewards = self.state.world.flags.get("campaign_rewards", {})
        if isinstance(campaign_rewards, dict) and reward_id in campaign_rewards:
            return self._parse_campaign_reward(reward_id, campaign_rewards[reward_id])
        if reward_id.startswith("gold:"):
            raise ValueError("gold rewards must be predefined campaign rewards")
        item_id = reward_id.removeprefix("item:") if reward_id.startswith("item:") else reward_id
        if item_id in self.compendium.items:
            return {"kind": "item", "item_id": item_id, "quantity": 1}
        raise ValueError(f"unknown reward id: {reward_id}")

    def _parse_campaign_reward(self, reward_id: str, payload: object) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError(f"campaign reward {reward_id} must be an object")
        try:
            gold = int(payload.get("gold", 0))
            experience = int(payload.get("experience", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"campaign reward {reward_id} has invalid numeric fields") from exc
        if gold < 0 or experience < 0:
            raise ValueError(f"campaign reward {reward_id} cannot be negative")
        items = payload.get("items", [])
        if not isinstance(items, list):
            raise ValueError(f"campaign reward {reward_id} items must be a list")
        normalized_items: list[dict[str, Any]] = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"campaign reward {reward_id} item {index} must be an object")
            item_id = str(item.get("item_id", ""))
            try:
                quantity = int(item.get("quantity", 1))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"campaign reward {reward_id} item {index} quantity must be an integer"
                ) from exc
            if quantity <= 0:
                raise ValueError(
                    f"campaign reward {reward_id} item {item_id} quantity must be positive"
                )
            if item_id not in self.compendium.items:
                raise ValueError(f"campaign reward {reward_id} has unknown item {item_id}")
            normalized_items.append({"item_id": item_id, "quantity": quantity})
        return {
            "kind": "campaign_reward",
            "reward_id": reward_id,
            "gold": gold,
            "experience": experience,
            "items": normalized_items,
        }

    def _character_for_actor(self, actor_id: str) -> Character:
        if actor_id in self.state.characters:
            return self.state.characters[actor_id]
        actor = self.state.entity_for_actor(actor_id)
        if isinstance(actor, Combatant) and actor.entity_id in self.state.characters:
            return self.state.characters[actor.entity_id]
        raise ValueError(f"actor {actor_id} is not backed by a character")

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

    def _set_hp_and_clear_death_state(self, target_id: str, hp_current: int) -> None:
        target = self.state.entity_for_actor(target_id)
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
        elif isinstance(target, Combatant) and target.entity_id in self.state.monsters:
            monster = self.state.monsters[target.entity_id]
            monster.hp_current = int(hp_current)
            self._sync_monster_to_combatants(monster)
        elif isinstance(target, Character):
            self._sync_character_to_combatants(target)
        elif isinstance(target, Monster):
            self._sync_monster_to_combatants(target)

    def _sync_hp_state_for_target(self, target: Character | Monster | Combatant) -> None:
        if isinstance(target, Combatant) and target.entity_id in self.state.characters:
            self._sync_combatant_to_character(target, self.state.characters[target.entity_id])
        elif isinstance(target, Combatant) and target.entity_id in self.state.monsters:
            self._sync_combatant_to_monster(target, self.state.monsters[target.entity_id])
        elif isinstance(target, Character):
            self._sync_character_to_combatants(target)
        elif isinstance(target, Monster):
            self._sync_monster_to_combatants(target)

    def _sync_monster_to_combatants(self, monster: Monster) -> None:
        if self.state.encounter is None:
            return
        for combatant in self.state.encounter.combatants.values():
            if combatant.entity_id != monster.id:
                continue
            combatant.hp_current = monster.hp_current
            combatant.hp_max = monster.hp_max
            combatant.temp_hp = monster.temp_hp
            combatant.temp_hp_source_effect_id = monster.temp_hp_source_effect_id

    @staticmethod
    def _sync_combatant_to_monster(combatant: Combatant, monster: Monster) -> None:
        monster.hp_current = combatant.hp_current
        monster.hp_max = combatant.hp_max
        monster.temp_hp = combatant.temp_hp
        monster.temp_hp_source_effect_id = combatant.temp_hp_source_effect_id

    @staticmethod
    def _set_death_recovery_state(entity: Character | Combatant, hp_current: int) -> None:
        entity.hp_current = int(hp_current)
        entity.death_save_successes = 0
        entity.death_save_failures = 0
        entity.stable = False
        entity.dead = False

    def _danger_sense_advantage(
        self,
        actor_id: str,
        ability: str,
        proficiency_source: Character | Monster | Combatant,
    ) -> str | None:
        if ability.lower() != "dex" or not isinstance(proficiency_source, Character):
            return None
        if int(proficiency_source.class_levels.get("barbarian", 0)) < 2:
            return None
        if any(
            effect.get("condition") == "incapacitated"
            for effect in self._status_effects_for_actor(actor_id)
        ):
            return None
        return "advantage"

    def _primal_knowledge_ability_check(
        self,
        actor_id: str,
        ability: str,
        skill: str | None,
        proficiency_source: Character | Monster | Combatant,
        *,
        use_primal_knowledge: bool,
    ) -> dict[str, Any] | None:
        if not use_primal_knowledge:
            return None
        if skill not in PRIMAL_KNOWLEDGE_SKILLS:
            raise ValueError("Primal Knowledge requires an eligible Barbarian skill")
        if (
            not isinstance(proficiency_source, Character)
            or int(proficiency_source.class_levels.get("barbarian", 0)) < 3
        ):
            raise ValueError("Primal Knowledge requires Barbarian level 3")
        if not has_condition(self._status_effects_for_actor(actor_id), "raging"):
            raise ValueError("Primal Knowledge requires active Rage")
        return {
            "feature": "primal_knowledge",
            "skill": skill,
            "original_ability": ability,
            "ability": "str",
        }

    def _ability_check_status_advantage(
        self,
        actor_id: str,
        ability: str,
        skill: str | None,
        *,
        contexts: set[str] | None = None,
    ) -> tuple[str | None, list[dict[str, Any]]]:
        advantage_sources: list[dict[str, Any]] = []
        disadvantage_sources: list[dict[str, Any]] = []
        contexts = contexts or set()
        proficiency_source = self._proficiency_source(actor_id)
        if isinstance(proficiency_source, Character) and remarkable_athlete_applies_to_check(
            proficiency_source,
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
        for effect in self._status_effects_for_actor(actor_id):
            modifiers = effect.get("passive_modifiers", {})
            if isinstance(modifiers, dict):
                abilities = modifiers.get("ability_check_advantage_abilities", [])
                if isinstance(abilities, str):
                    abilities = [abilities]
                if isinstance(abilities, list) and ability in {
                    str(entry).lower() for entry in abilities
                }:
                    advantage_sources.append(
                        {
                            "condition": effect.get("condition"),
                            "effect_id": effect.get("effect_id"),
                            "source_action_id": effect.get("source_action_id"),
                            "modifier": "ability_check_advantage_abilities",
                            "ability": ability,
                        }
                    )
                disadvantage_abilities = modifiers.get("ability_check_disadvantage_abilities", [])
                if isinstance(disadvantage_abilities, str):
                    disadvantage_abilities = [disadvantage_abilities]
                if isinstance(disadvantage_abilities, list) and ability in {
                    str(entry).lower() for entry in disadvantage_abilities
                }:
                    disadvantage_sources.append(
                        {
                            "condition": effect.get("condition"),
                            "effect_id": effect.get("effect_id"),
                            "source_action_id": effect.get("source_action_id"),
                            "modifier": "ability_check_disadvantage_abilities",
                            "ability": ability,
                        }
                    )
                skill_entries = modifiers.get("ability_check_advantage_skills", [])
                if isinstance(skill_entries, (str, dict)):
                    skill_entries = [skill_entries]
                if isinstance(skill_entries, list) and any(
                    _skill_advantage_entry_matches(
                        entry,
                        ability=ability,
                        skill=skill,
                        contexts=contexts,
                    )
                    for entry in skill_entries
                ):
                    advantage_sources.append(
                        {
                            "condition": effect.get("condition"),
                            "effect_id": effect.get("effect_id"),
                            "source_action_id": effect.get("source_action_id"),
                            "modifier": "ability_check_advantage_skills",
                            "ability": ability,
                            "skill": skill,
                            "contexts": sorted(contexts),
                        }
                    )
            condition = effect.get("condition")
            if isinstance(condition, str) and condition in {"frightened", "poisoned"}:
                disadvantage_sources.append(
                    {
                        "condition": condition,
                        "effect_id": effect.get("effect_id"),
                        "source_action_id": effect.get("source_action_id"),
                    }
                )
        return (
            _merge_advantage(
                "advantage" if advantage_sources else None,
                "disadvantage" if disadvantage_sources else None,
            ),
            [{"kind": "advantage", **source} for source in advantage_sources]
            + [{"kind": "disadvantage", **source} for source in disadvantage_sources],
        )

    def _saving_throw_status_advantage(
        self,
        actor_id: str,
        ability: str,
        *,
        contexts: set[str] | None = None,
    ) -> tuple[str | None, list[dict[str, Any]]]:
        ability = ability.lower()
        contexts = {context.lower() for context in (contexts or set())}
        advantage_sources: list[dict[str, Any]] = []
        disadvantage_sources: list[dict[str, Any]] = []
        for effect in self._status_effects_for_actor(actor_id):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            abilities = modifiers.get("saving_throw_advantage_abilities", [])
            if isinstance(abilities, str):
                abilities = [abilities]
            if isinstance(abilities, list) and ability in {
                str(entry).lower() for entry in abilities
            }:
                advantage_sources.append(
                    {
                        "condition": effect.get("condition"),
                        "effect_id": effect.get("effect_id"),
                        "source_action_id": effect.get("source_action_id"),
                        "modifier": "saving_throw_advantage_abilities",
                        "ability": ability,
                    }
                )
            context_entries = modifiers.get("saving_throw_advantage_contexts", [])
            if isinstance(context_entries, str):
                context_entries = [context_entries]
            if isinstance(context_entries, list) and contexts:
                matched = sorted(contexts & {str(entry).lower() for entry in context_entries})
                if matched:
                    advantage_sources.append(
                        {
                            "condition": effect.get("condition"),
                            "effect_id": effect.get("effect_id"),
                            "source_action_id": effect.get("source_action_id"),
                            "modifier": "saving_throw_advantage_contexts",
                            "ability": ability,
                            "contexts": matched,
                        }
                    )
            disadvantage_abilities = modifiers.get("saving_throw_disadvantage_abilities", [])
            if isinstance(disadvantage_abilities, str):
                disadvantage_abilities = [disadvantage_abilities]
            if isinstance(disadvantage_abilities, list) and ability in {
                str(entry).lower() for entry in disadvantage_abilities
            }:
                disadvantage_sources.append(
                    {
                        "condition": effect.get("condition"),
                        "effect_id": effect.get("effect_id"),
                        "source_action_id": effect.get("source_action_id"),
                        "modifier": "saving_throw_disadvantage_abilities",
                        "ability": ability,
                    }
                )
            if modifiers.get("next_saving_throw_disadvantage") is True:
                disadvantage_sources.append(
                    {
                        "condition": effect.get("condition"),
                        "effect_id": effect.get("effect_id"),
                        "source_action_id": effect.get("source_action_id"),
                        "modifier": "next_saving_throw_disadvantage",
                    }
                )
        advantage_sources.extend(
            {
                **source,
                "modifier": "holy_aura_saving_throw_advantage",
                "ability": ability,
            }
            for source in holy_aura_benefit_sources(self.state, actor_id)
        )
        return (
            _merge_advantage(
                "advantage" if advantage_sources else None,
                "disadvantage" if disadvantage_sources else None,
            ),
            [{"kind": "advantage", **source} for source in advantage_sources]
            + [{"kind": "disadvantage", **source} for source in disadvantage_sources],
        )

    def _saving_throw_passive_bonus(
        self,
        actor_id: str,
        ability: str,
    ) -> tuple[int, list[dict[str, Any]]]:
        ability = ability.lower()
        bonus, sources = self._aura_of_protection_saving_throw_bonus(actor_id)
        for effect in self._status_effects_for_actor(actor_id):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            amount = modifiers.get("saving_throw_bonus")
            if not isinstance(amount, int) or isinstance(amount, bool):
                continue
            bonus += amount
            sources.append(
                {
                    "condition": effect.get("condition"),
                    "effect_id": effect.get("effect_id"),
                    "source_action_id": effect.get("source_action_id"),
                    "modifier": "saving_throw_bonus",
                    "ability": ability,
                    "amount": amount,
                }
            )
        return bonus, sources

    def _ability_check_passive_bonus(
        self,
        actor_id: str,
        ability: str,
    ) -> tuple[int, list[dict[str, Any]]]:
        ability = ability.lower()
        bonus = 0
        sources: list[dict[str, Any]] = []
        for effect in self._status_effects_for_actor(actor_id):
            modifiers = effect.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                continue
            amount = modifiers.get("ability_check_bonus")
            if not isinstance(amount, int) or isinstance(amount, bool):
                continue
            bonus += amount
            sources.append(
                {
                    "condition": effect.get("condition"),
                    "effect_id": effect.get("effect_id"),
                    "source_action_id": effect.get("source_action_id"),
                    "modifier": "ability_check_bonus",
                    "ability": ability,
                    "amount": amount,
                }
            )
        return bonus, sources

    def _aura_of_protection_saving_throw_bonus(
        self,
        actor_id: str,
    ) -> tuple[int, list[dict[str, Any]]]:
        target = self.state.entity_for_actor(actor_id)
        target_combatant = target if isinstance(target, Combatant) else self._combatant_for(target)
        candidates: list[dict[str, Any]] = []
        if self.state.encounter is not None and target_combatant is not None:
            graph = (
                TacticalGraph.from_dict(self.state.encounter.tactical_graph)
                if self.state.encounter.tactical_graph is not None
                else None
            )
            for paladin in self.state.encounter.combatants.values():
                if paladin.entity_id not in self.state.characters:
                    continue
                if paladin.side != target_combatant.side:
                    continue
                owner = self.state.characters[paladin.entity_id]
                amount = aura_of_protection_saving_throw_bonus(owner)
                if amount <= 0:
                    continue
                radius_ft = aura_of_protection_radius_ft(owner)
                if has_condition(self._status_effects_for_actor(paladin.id), "incapacitated"):
                    continue
                distance: int | None
                if paladin.id == target_combatant.id:
                    distance = 0
                elif (
                    graph is None
                    or paladin.position_node_id is None
                    or target_combatant.position_node_id is None
                ):
                    continue
                else:
                    distance = graph.shortest_distance(
                        paladin.position_node_id,
                        target_combatant.position_node_id,
                    )
                if distance is None or distance > radius_ft:
                    continue
                candidates.append(
                    {
                        "source_action_id": "srd.aura_of_protection",
                        "modifier": "aura_of_protection",
                        "source_actor_id": paladin.id,
                        "target_id": target_combatant.id,
                        "distance_ft": distance,
                        "radius_ft": radius_ft,
                        "amount": amount,
                    }
                )
        elif isinstance(target, Character):
            amount = aura_of_protection_saving_throw_bonus(target)
            if amount > 0 and not has_condition(target.status_effects, "incapacitated"):
                candidates.append(
                    {
                        "source_action_id": "srd.aura_of_protection",
                        "modifier": "aura_of_protection",
                        "source_actor_id": target.id,
                        "target_id": target.id,
                        "amount": amount,
                    }
                )
        if not candidates:
            return 0, []
        best_amount = max(int(candidate["amount"]) for candidate in candidates)
        return best_amount, [
            candidate for candidate in candidates if int(candidate["amount"]) == best_amount
        ]

    def _combatant_for(self, actor: Character | Monster | Combatant) -> Combatant | None:
        if isinstance(actor, Combatant):
            return actor
        if self.state.encounter is None:
            return None
        actor_id = getattr(actor, "id", None)
        if actor_id is None:
            return None
        for combatant in self.state.encounter.combatants.values():
            if combatant.id == actor_id or combatant.entity_id == actor_id:
                return combatant
        return None

    def _ability_source(self, actor_id: str) -> Character | Monster | Combatant:
        actor = self.state.entity_for_actor(actor_id)
        if isinstance(actor, Combatant) and actor.abilities:
            return actor
        if isinstance(actor, Combatant) and actor.entity_id in self.state.characters:
            return self.state.characters[actor.entity_id]
        if isinstance(actor, Combatant) and actor.entity_id in self.state.monsters:
            return self.state.monsters[actor.entity_id]
        return actor

    def _proficiency_source(self, actor_id: str) -> Character | Monster | Combatant:
        actor = self.state.entity_for_actor(actor_id)
        if isinstance(actor, Combatant) and actor.entity_id in self.state.characters:
            return self.state.characters[actor.entity_id]
        if isinstance(actor, Combatant) and actor.entity_id in self.state.monsters:
            return self.state.monsters[actor.entity_id]
        return actor

    def _status_effects_for_actor(self, actor_id: str) -> list[dict[str, Any]]:
        actor = self.state.entity_for_actor(actor_id)
        effects = list(getattr(actor, "status_effects", []))
        if isinstance(actor, Combatant) and actor.entity_id in self.state.characters:
            effects.extend(self.state.characters[actor.entity_id].status_effects)
        if isinstance(actor, Combatant) and actor.entity_id in self.state.monsters:
            effects.extend(self.state.monsters[actor.entity_id].status_effects)
        return effects

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

    def _expire_next_saving_throw_disadvantage(
        self,
        actor_id: str,
        path: str,
    ) -> dict[str, Any] | None:
        removed: list[dict[str, Any]] = []
        for owner_type, owner_id, effects in self._actor_effect_lists(actor_id):
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
            "actor_id": actor_id,
            "trigger": "next_saving_throw",
            "removed": removed,
            "path": path,
        }

    def _exhaustion_penalty_for(self, actor_id: str) -> tuple[int, list[dict[str, Any]]]:
        effects = self._status_effects_for_actor(actor_id)
        level = exhaustion_level(effects)
        exhaustion_penalty = exhaustion_d20_penalty(effects)
        passive_penalty = passive_d20_test_penalty(effects)
        penalty = exhaustion_penalty + passive_penalty
        if penalty == 0:
            return 0, []
        sources: list[dict[str, Any]] = []
        if exhaustion_penalty:
            sources.append(
                {
                    "condition": "exhaustion",
                    "level": level,
                    "penalty": exhaustion_penalty,
                }
            )
        sources.extend(passive_d20_test_penalty_sources(effects))
        return penalty, sources

    @staticmethod
    def _validate_tactical_mind_available(actor: Character | Monster | Combatant) -> None:
        if not isinstance(actor, Character) or int(actor.class_levels.get("fighter", 0)) < 2:
            raise ValueError("Tactical Mind requires Fighter level 2")
        if int(actor.resources.get("srd.resource.second_wind", 0)) <= 0:
            raise ValueError("Tactical Mind requires an available Second Wind use")

    @staticmethod
    def _validate_dark_ones_own_luck_available(actor: Character | Monster | Combatant) -> None:
        if not isinstance(actor, Character) or not has_warlock_fiend_feature(actor, level=6):
            raise ValueError("Dark One's Own Luck requires Fiend Patron Warlock level 6")
        if int(actor.resources.get(DARK_ONES_OWN_LUCK_RESOURCE, 0)) <= 0:
            raise ValueError("Dark One's Own Luck requires an available use")

    @staticmethod
    def _validate_stroke_of_luck_available(actor: Character | Monster | Combatant) -> None:
        if not isinstance(actor, Character) or not rogue_stroke_of_luck_applies(actor):
            raise ValueError("Stroke of Luck requires Rogue level 20")
        if int(actor.resources.get(STROKE_OF_LUCK_RESOURCE, 0)) <= 0:
            raise ValueError("Stroke of Luck requires an available use")

    def _apply_stroke_of_luck_to_failed_d20_test(
        self,
        actor_id: str,
        payload: dict[str, Any],
        actor: Character | Monster | Combatant,
        roll: RollResult,
        *,
        use_stroke_of_luck: bool,
    ) -> dict[str, Any] | None:
        if not use_stroke_of_luck or bool(payload["success"]):
            return None
        if not isinstance(actor, Character):
            raise ValueError("Stroke of Luck requires a character")
        natural_d20 = _kept_d20(roll)
        adjustment = STROKE_OF_LUCK_D20 - natural_d20
        if adjustment <= 0:
            return None
        before_resource = int(actor.resources.get(STROKE_OF_LUCK_RESOURCE, 0))
        after_resource = before_resource - 1
        before_total = int(payload["total"])
        after_total = before_total + adjustment
        actor.resources[STROKE_OF_LUCK_RESOURCE] = after_resource
        payload["total"] = after_total
        payload["success"] = after_total >= int(payload["dc"])
        return {
            "source_action_id": STROKE_OF_LUCK_ACTION_ID,
            "resource": STROKE_OF_LUCK_RESOURCE,
            "resource_before": before_resource,
            "resource_after": after_resource,
            "actor_id": actor_id,
            "d20_before": natural_d20,
            "d20_after": STROKE_OF_LUCK_D20,
            "adjustment": adjustment,
            "total_before": before_total,
            "total_after": after_total,
            "spent": True,
            "success": payload["success"],
        }

    def _apply_dark_ones_own_luck_to_roll(
        self,
        actor_id: str,
        payload: dict[str, Any],
        actor: Character | Monster | Combatant,
        *,
        use_dark_ones_own_luck: bool,
    ) -> dict[str, Any] | None:
        if not use_dark_ones_own_luck:
            return None
        if not isinstance(actor, Character):
            raise ValueError("Dark One's Own Luck requires a character")
        before_resource = int(actor.resources.get(DARK_ONES_OWN_LUCK_RESOURCE, 0))
        roll = self.roll_service.roll("1d10")
        before_total = int(payload["total"])
        after_total = before_total + roll.total
        actor.resources[DARK_ONES_OWN_LUCK_RESOURCE] = before_resource - 1
        payload["total"] = after_total
        payload["success"] = after_total >= int(payload["dc"])
        return {
            "roll": roll.to_dict(),
            "result": {
                "resource": DARK_ONES_OWN_LUCK_RESOURCE,
                "resource_before": before_resource,
                "resource_after": actor.resources[DARK_ONES_OWN_LUCK_RESOURCE],
                "roll_total": roll.total,
                "total_before": before_total,
                "total_after": after_total,
                "spent": True,
                "success": payload["success"],
            },
        }

    @staticmethod
    def _validate_indomitable_available(actor: Character | Monster | Combatant) -> None:
        if not isinstance(actor, Character) or not has_fighter_feature(actor, level=9):
            raise ValueError("Indomitable requires Fighter level 9")
        if int(actor.resources.get(INDOMITABLE_RESOURCE, 0)) <= 0:
            raise ValueError("Indomitable requires an available use")

    def _apply_indomitable_to_save(
        self,
        payload: dict[str, Any],
        actor: Character | Monster | Combatant,
        *,
        use_indomitable: bool,
    ) -> dict[str, Any] | None:
        if not use_indomitable or bool(payload["success"]):
            return None
        if not isinstance(actor, Character):
            raise ValueError("Indomitable requires a character")
        before_resource = int(actor.resources.get(INDOMITABLE_RESOURCE, 0))
        fighter_level = int(actor.class_levels.get("fighter", 0))
        before_total = int(payload["total"])
        original_roll = dict(payload["roll"])
        reroll = self.roll_service.roll(
            d20_expression(int(payload["bonus"]) + fighter_level),
            advantage=original_roll.get("advantage"),
        )
        actor.resources[INDOMITABLE_RESOURCE] = before_resource - 1
        payload["roll"] = reroll.to_dict()
        payload["total"] = reroll.total
        payload["success"] = reroll.total >= int(payload["dc"])
        return {
            "roll": reroll.to_dict(),
            "result": {
                "resource": INDOMITABLE_RESOURCE,
                "resource_before": before_resource,
                "resource_after": actor.resources[INDOMITABLE_RESOURCE],
                "fighter_level_bonus": fighter_level,
                "original_roll": original_roll,
                "total_before": before_total,
                "reroll_total": reroll.total,
                "total_after": reroll.total,
                "spent": True,
                "success": payload["success"],
            },
        }

    @staticmethod
    def _saving_throw_proficiency(
        actor: Character | Monster | Combatant,
        ability: str,
    ) -> tuple[bool, list[dict[str, Any]]]:
        sources = saving_throw_proficiency_sources(actor, ability)
        return bool(sources), sources

    def _saving_throw_auto_failure_sources(
        self,
        actor_id: str,
        ability: str,
    ) -> list[dict[str, Any]]:
        if ability.lower() not in {"str", "dex"}:
            return []
        sources: list[dict[str, Any]] = []
        for effect in self._status_effects_for_actor(actor_id):
            condition = effect.get("condition")
            if condition in {"paralyzed", "petrified", "stunned", "unconscious"}:
                sources.append(
                    {
                        "condition": condition,
                        "effect_id": effect.get("effect_id"),
                        "source_action_id": effect.get("source_action_id"),
                    }
                )
        return sources

    @staticmethod
    def _validate_disciplined_survivor_available(
        actor: Character | Monster | Combatant,
    ) -> None:
        if not isinstance(actor, Character) or not monk_disciplined_survivor_applies(actor):
            raise ValueError("Disciplined Survivor requires Monk level 14")
        if int(actor.resources.get(FOCUS_POINTS_RESOURCE, 0)) <= 0:
            raise ValueError("Disciplined Survivor requires an available Focus Point")

    def _apply_disciplined_survivor_to_save(
        self,
        payload: dict[str, Any],
        actor: Character | Monster | Combatant,
        *,
        use_disciplined_survivor: bool,
    ) -> dict[str, Any] | None:
        if not use_disciplined_survivor or bool(payload["success"]):
            return None
        if not isinstance(actor, Character):
            raise ValueError("Disciplined Survivor requires a character")
        before_resource = int(actor.resources.get(FOCUS_POINTS_RESOURCE, 0))
        before_total = int(payload["total"])
        original_roll = dict(payload["roll"])
        reroll = self.roll_service.roll(
            d20_expression(int(payload["bonus"])),
            advantage=original_roll.get("advantage"),
        )
        actor.resources[FOCUS_POINTS_RESOURCE] = before_resource - 1
        payload["roll"] = reroll.to_dict()
        payload["total"] = reroll.total
        payload["success"] = reroll.total >= int(payload["dc"])
        return {
            "roll": reroll.to_dict(),
            "result": {
                "resource": FOCUS_POINTS_RESOURCE,
                "resource_before": before_resource,
                "resource_after": actor.resources[FOCUS_POINTS_RESOURCE],
                "source_action_id": "srd.disciplined_survivor",
                "original_roll": original_roll,
                "total_before": before_total,
                "reroll_total": reroll.total,
                "total_after": reroll.total,
                "spent": True,
                "success": payload["success"],
            },
        }

    def _apply_tactical_mind_to_check(
        self,
        actor_id: str,
        payload: dict[str, Any],
        actor: Character | Monster | Combatant,
        *,
        use_tactical_mind: bool,
    ) -> dict[str, Any] | None:
        if not use_tactical_mind or payload["success"]:
            return None
        if not isinstance(actor, Character):
            raise ValueError("Tactical Mind requires a character")
        before_resource = int(actor.resources.get("srd.resource.second_wind", 0))
        roll = self.roll_service.roll("1d10")
        before_total = int(payload["total"])
        after_total = before_total + roll.total
        success = after_total >= int(payload["dc"])
        if success:
            actor.resources["srd.resource.second_wind"] = before_resource - 1
        payload["total"] = after_total
        payload["success"] = success
        return {
            "roll": roll.to_dict(),
            "result": {
                "resource": "srd.resource.second_wind",
                "resource_before": before_resource,
                "resource_after": actor.resources.get("srd.resource.second_wind", before_resource),
                "roll_total": roll.total,
                "total_before": before_total,
                "total_after": after_total,
                "spent": success,
                "success": success,
            },
        }

    def _persistent_condition_owner(
        self,
        target: Character | Monster | Combatant,
    ) -> Character | Monster | Combatant:
        if isinstance(target, Combatant) and target.entity_id in self.state.characters:
            return self.state.characters[target.entity_id]
        if isinstance(target, Combatant) and target.entity_id in self.state.monsters:
            return self.state.monsters[target.entity_id]
        return target


def _kept_d20(roll: RollResult) -> int:
    for die in roll.dice:
        if die.sides == 20 and die.kept:
            return die.value
    raise ValueError("ability check roll did not include a kept d20")


def _apply_reliable_talent_to_check_payload(
    actor: Character | Monster | Combatant,
    payload: dict[str, Any],
    roll: RollResult,
    proficiency_sources: list[str],
) -> dict[str, Any] | None:
    if not isinstance(actor, Character):
        return None
    natural_d20 = _kept_d20(roll)
    adjustment = reliable_talent_d20_adjustment(
        actor,
        proficiency_sources=proficiency_sources,
        natural_d20=natural_d20,
    )
    if adjustment <= 0:
        return None
    before_total = int(payload["total"])
    after_total = before_total + adjustment
    payload["total"] = after_total
    payload["success"] = after_total >= int(payload["dc"])
    return {
        "source_action_id": RELIABLE_TALENT_ACTION_ID,
        "d20_before": natural_d20,
        "d20_after": RELIABLE_TALENT_D20_FLOOR,
        "adjustment": adjustment,
        "total_before": before_total,
        "total_after": after_total,
        "proficiency_sources": list(proficiency_sources),
        "success": payload["success"],
    }


def _apply_charisma_check_minimum_d20_to_check_payload(
    payload: dict[str, Any],
    roll: RollResult,
    status_effects: list[dict[str, Any]],
) -> dict[str, Any] | None:
    natural_d20 = _kept_d20(roll)
    current_d20 = natural_d20
    reliable_talent = payload.get("reliable_talent")
    if isinstance(reliable_talent, dict):
        d20_after = reliable_talent.get("d20_after")
        if isinstance(d20_after, int) and not isinstance(d20_after, bool):
            current_d20 = max(current_d20, d20_after)
    adjustment = charisma_check_minimum_d20_adjustment(
        status_effects=status_effects,
        ability=str(payload["ability"]),
        natural_d20=natural_d20,
        current_d20=current_d20,
    )
    if adjustment is None:
        return None
    before_total = int(payload["total"])
    after_total = before_total + int(adjustment["adjustment"])
    payload["total"] = after_total
    payload["success"] = after_total >= int(payload["dc"])
    return {
        **adjustment,
        "total_before": before_total,
        "total_after": after_total,
        "success": payload["success"],
    }


def _apply_indomitable_might_to_d20_payload(
    actor: Character | Monster | Combatant,
    payload: dict[str, Any],
    ability: str,
) -> dict[str, Any] | None:
    if not isinstance(actor, Character):
        return None
    before_total = int(payload["total"])
    after_total = indomitable_might_total_floor(
        actor,
        ability=ability,
        total=before_total,
    )
    if after_total is None:
        return None
    payload["total"] = after_total
    payload["success"] = after_total >= int(payload["dc"])
    return {
        "source_action_id": INDOMITABLE_MIGHT_ACTION_ID,
        "ability": ability.lower(),
        "strength_score": after_total,
        "total_before": before_total,
        "total_after": after_total,
        "success": payload["success"],
    }


def _check_proficiency(
    actor: Character | Monster | Combatant,
    *,
    skill: str | None = None,
    tool: str | None = None,
) -> tuple[bool, list[str], str | None]:
    sources: list[str] = []
    skill_proficient = bool(
        skill
        and skill
        in {_proficiency_key(str(item)) for item in getattr(actor, "skill_proficiencies", [])}
    )
    tool_proficient = bool(
        tool
        and tool
        in {_proficiency_key(str(item)) for item in getattr(actor, "tool_proficiencies", [])}
    )
    if skill_proficient and skill is not None:
        sources.append(f"skill:{skill}")
    if tool_proficient and tool is not None:
        sources.append(f"tool:{tool}")
    proficiency_advantage = "advantage" if skill_proficient and tool_proficient else None
    return bool(sources), sources, proficiency_advantage


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


def _cleric_thaumaturge_bonus(
    actor: Character | Monster | Combatant,
    *,
    ability: str,
    skill: str | None,
) -> int:
    if not isinstance(actor, Character):
        return 0
    return cleric_thaumaturge_check_bonus(actor, ability=ability, skill=skill)


def _druid_magician_bonus(
    actor: Character | Monster | Combatant,
    *,
    ability: str,
    skill: str | None,
) -> int:
    if not isinstance(actor, Character):
        return 0
    return druid_magician_check_bonus(actor, ability=ability, skill=skill)


def _merge_advantage(base: str | None, extra: str | None) -> str | None:
    if extra is None:
        return base
    if base is None or base == extra:
        return extra
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


def _normalize_spell_ref(value: str) -> str:
    if value.startswith("srd.spell."):
        return value
    if value.startswith("srd."):
        return "srd.spell." + value.removeprefix("srd.")
    return value


def _target_has_condition(target: Character | Monster | Combatant, condition: str) -> bool:
    return any(
        effect.get("condition") == condition
        for effect in getattr(target, "status_effects", [])
        if isinstance(effect, dict)
    )


def _exhaustion_death_result(
    target_id: str,
    target: Character | Monster | Combatant,
    owner: Character | Monster | Combatant,
    level: int,
) -> dict[str, Any] | None:
    if level < 6:
        return None
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
        "reason": "exhaustion",
        "exhaustion_level": level,
        "entities": changed,
    }

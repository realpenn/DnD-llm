from __future__ import annotations

import re
from typing import Any

from .automation.definitions import ActionDefinition, SpellDefinition
from .automation.effects import EffectInstance
from .automation.executor import AutomationExecutor
from .compendium.loader import Compendium
from .compendium.validators import ALLOWED_DAMAGE_TYPES
from .dice import RollService
from .economy import EconomyTracker
from .invariants import require_game_state_invariants
from .models import Character, Combatant, GameState, Monster
from .persistence import AuditLog
from .positioning import TacticalGraph
from .rules.checks import roll_check
from .rules.class_features import (
    PRIMAL_KNOWLEDGE_SKILLS,
    cleric_thaumaturge_check_bonus,
    druid_magician_check_bonus,
    has_condition,
    has_rogue_thief_feature,
    remarkable_athlete_applies_to_check,
)
from .rules.combat import apply_damage as apply_damage_rule
from .rules.combat import apply_healing as apply_healing_rule
from .rules.conditions import apply_exhaustion, exhaustion_d20_penalty, exhaustion_level
from .rules.death import roll_death_save as roll_death_save_rule
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
        use_tactical_mind: bool = False,
        use_primal_knowledge: bool = False,
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
        if use_tactical_mind:
            self._validate_tactical_mind_available(proficiency_source)
        d20_penalty, d20_penalty_sources = self._exhaustion_penalty_for(actor_id)
        status_advantage, status_sources = self._ability_check_status_advantage(
            actor_id,
            effective_ability,
            normalized_skill,
            contexts={"sight"} if relies_on_sight else set(),
        )
        merged_advantage = _merge_advantage(
            _merge_advantage(advantage, status_advantage),
            proficiency_advantage,
        )
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
            status_effects=self._status_effects_for_actor(actor_id),
        )
        payload = result.to_dict()
        payload["original_ability"] = original_ability
        payload["status_advantage"] = status_advantage
        payload["status_sources"] = status_sources
        if primal_knowledge is not None:
            payload["primal_knowledge"] = primal_knowledge
        dice_rolls = [result.roll.to_dict()]
        tactical_mind = self._apply_tactical_mind_to_check(
            actor_id,
            payload,
            proficiency_source,
            use_tactical_mind=use_tactical_mind,
        )
        if tactical_mind is not None:
            payload["tactical_mind"] = tactical_mind["result"]
            dice_rolls.append(tactical_mind["roll"])
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
                "use_tactical_mind": use_tactical_mind,
                "use_primal_knowledge": use_primal_knowledge,
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
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        idempotency_key = idempotency_key or f"roll_save:{self.state.event_counter}"
        cached = self._cached_result(idempotency_key)
        if cached is not None:
            return cached
        actor = self._ability_source(actor_id)
        proficiency_source = self._proficiency_source(actor_id)
        proficient = ability.lower() in {
            str(item).lower()
            for item in getattr(proficiency_source, "saving_throw_proficiencies", [])
        }
        d20_penalty, d20_penalty_sources = self._exhaustion_penalty_for(actor_id)
        danger_sense_advantage = self._danger_sense_advantage(
            actor_id,
            ability,
            proficiency_source,
        )
        status_advantage, status_sources = self._saving_throw_status_advantage(
            actor_id,
            ability,
        )
        passive_bonus, passive_bonus_sources = self._saving_throw_passive_bonus(actor_id, ability)
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
            proficiency=proficient,
            extra_bonus=passive_bonus,
            d20_penalty=d20_penalty,
            d20_penalty_sources=d20_penalty_sources,
            status_effects=self._status_effects_for_actor(actor_id),
        )
        payload = result.to_dict()
        payload["tool"] = "roll_save"
        payload["status_advantage"] = status_advantage
        payload["status_sources"] = status_sources
        payload["passive_bonus"] = passive_bonus
        payload["passive_bonus_sources"] = passive_bonus_sources
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
            },
            tool_result=payload,
            dice_rolls=[result.roll.to_dict()],
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
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        idempotency_key = idempotency_key or f"cast_spell:{self.state.event_counter}"
        params: dict[str, Any] = {"slot_level": slot_level}
        if as_ritual:
            params["as_ritual"] = True
        if use_rod_of_absorption:
            params["use_rod_of_absorption"] = True
        return self._execute_action(
            action_id=spell_id,
            actor_id=caster_id,
            targets=targets,
            params=params,
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
        reward = self._parse_reward_id(reward_id)
        changes = []
        for actor_id in actor_ids:
            actor = self.state.get_character(actor_id)
            if reward["kind"] == "gold":
                before = actor.gold
                actor.gold += int(reward["amount"])
                changes.append(
                    {
                        "type": "gold",
                        "actor_id": actor_id,
                        "before": before,
                        "after": actor.gold,
                    }
                )
            else:
                if reward["kind"] == "campaign_reward":
                    gold = int(reward.get("gold", 0))
                    if gold:
                        before_gold = actor.gold
                        actor.gold += gold
                        changes.append(
                            {
                                "type": "gold",
                                "actor_id": actor_id,
                                "before": before_gold,
                                "after": actor.gold,
                            }
                        )
                    experience = int(reward.get("experience", 0))
                    if experience:
                        before_experience = actor.experience
                        actor.experience += experience
                        changes.append(
                            {
                                "type": "experience",
                                "actor_id": actor_id,
                                "before": before_experience,
                                "after": actor.experience,
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
                    before = int(actor.inventory.get(item_id, 0))
                    actor.inventory[item_id] = before + quantity
                    changes.append(
                        {
                            "type": "item",
                            "actor_id": actor_id,
                            "item_id": item_id,
                            "quantity": quantity,
                            "before": before,
                            "after": actor.inventory[item_id],
                        }
                    )
        self.audit_log.append(
            self.state,
            idempotency_key=idempotency_key,
            tool_name="award",
            tool_args={"actor_ids": actor_ids, "reward_id": reward_id},
            tool_result={"reward": reward, "changes": changes},
        )
        require_game_state_invariants(self.state)
        return {"reward": reward, "changes": changes}

    def short_rest(
        self,
        actor_id: str,
        hit_dice_to_spend: dict[str, int],
        *,
        arcane_recovery_slots: dict[str, int] | None = None,
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
        result = short_rest_rule(
            character,
            hit_dice_to_spend,
            self.roll_service,
            arcane_recovery_slots,
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
                "memorize_spell": memorize_spell or {},
            },
            tool_result=result,
            dice_rolls=list(result.get("dice_rolls", [])),
        )
        require_game_state_invariants(self.state)
        return result

    def long_rest(
        self,
        actor_ids: list[str],
        *,
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
            rest_result = long_rest_rule(character)
            rest_result["actor_id"] = actor_id
            rest_result["character_id"] = character.id
            results[actor_id] = rest_result
            self._sync_character_to_combatants(character)
        result = {"results": results}
        self.audit_log.append(
            self.state,
            idempotency_key=idempotency_key,
            tool_name="long_rest",
            tool_args={"actor_ids": actor_ids},
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
        result = roll_death_save_rule(entity, self.roll_service)
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

    def request_end_combat(self, *, idempotency_key: str | None = None) -> dict[str, Any]:
        idempotency_key = idempotency_key or f"request_end_combat:{self.state.event_counter}"
        cached = self._cached_result(idempotency_key)
        if cached is not None:
            return cached
        self.audit_log.append(
            self.state,
            idempotency_key=idempotency_key,
            tool_name="request_end_combat",
            tool_result={"requested": True},
        )
        return {"requested": True}

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
        applied = apply_damage_rule(target, amount, normalized_damage_type)
        result = {
            "target_id": target_id,
            "amount": amount,
            "damage_type": normalized_damage_type,
            "applied": applied,
        }
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
        )
        require_game_state_invariants(self.state)
        return result

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
            death_result = _exhaustion_death_result(target_id, target, owner, after_level)
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
            try:
                amount = int(reward_id.removeprefix("gold:"))
            except ValueError as exc:
                raise ValueError(f"invalid gold reward: {reward_id}") from exc
            if amount <= 0:
                raise ValueError("gold reward must be positive")
            return {"kind": "gold", "amount": amount}
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
    ) -> tuple[str | None, list[dict[str, Any]]]:
        ability = ability.lower()
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
        bonus = 0
        sources: list[dict[str, Any]] = []
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

    def _exhaustion_penalty_for(self, actor_id: str) -> tuple[int, list[dict[str, Any]]]:
        effects = self._status_effects_for_actor(actor_id)
        level = exhaustion_level(effects)
        penalty = exhaustion_d20_penalty(effects)
        if penalty == 0:
            return 0, []
        return penalty, [{"condition": "exhaustion", "level": level, "penalty": penalty}]

    @staticmethod
    def _validate_tactical_mind_available(actor: Character | Monster | Combatant) -> None:
        if not isinstance(actor, Character) or int(actor.class_levels.get("fighter", 0)) < 2:
            raise ValueError("Tactical Mind requires Fighter level 2")
        if int(actor.resources.get("srd.resource.second_wind", 0)) <= 0:
            raise ValueError("Tactical Mind requires an available Second Wind use")

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

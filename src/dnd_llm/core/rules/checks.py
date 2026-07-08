from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..dice import RollResult, RollService
from ..models import Character, Combatant, Monster
from .conditions import effective_ability_modifier
from .difficulty import resolve_dc

CHARISMA_CHECK_MINIMUM_D20_MODIFIER = "charisma_check_minimum_d20"
GLIBNESS_ACTION_ID = "srd.glibness"


def ability_modifier(score: int) -> int:
    return (score - 10) // 2


def actor_ability_modifier(
    actor: Character | Monster | Combatant,
    ability: str,
    *,
    status_effects: list[dict[str, Any]] | None = None,
) -> int:
    return effective_ability_modifier(actor, ability, status_effects=status_effects)


@dataclass
class CheckResult:
    actor_id: str
    ability: str
    dc: int
    dc_source: str
    roll: RollResult
    success: bool
    bonus: int
    proficient: bool = False
    skill: str | None = None
    tool: str | None = None
    proficiency_sources: list[str] | None = None
    d20_penalty: int = 0
    d20_penalty_sources: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "ability": self.ability,
            "skill": self.skill,
            "tool": self.tool,
            "dc": self.dc,
            "dc_source": self.dc_source,
            "roll": self.roll.to_dict(),
            "success": self.success,
            "total": self.roll.total,
            "bonus": self.bonus,
            "proficient": self.proficient,
            "proficiency_sources": self.proficiency_sources or [],
            "d20_penalty": self.d20_penalty,
            "d20_penalty_sources": self.d20_penalty_sources or [],
        }


def roll_check(
    *,
    actor_id: str,
    actor: Character | Monster | Combatant,
    ability: str,
    roll_service: RollService,
    difficulty_tier: str | None = None,
    dc_ref: str | None = None,
    dc_table: dict[str, int] | None = None,
    advantage: str | None = None,
    proficiency: bool = False,
    skill: str | None = None,
    tool: str | None = None,
    proficiency_sources: list[str] | None = None,
    extra_bonus: int = 0,
    d20_penalty: int = 0,
    d20_penalty_sources: list[dict[str, Any]] | None = None,
    status_effects: list[dict[str, Any]] | None = None,
) -> CheckResult:
    dc, dc_source = resolve_dc(
        difficulty_tier=difficulty_tier,
        dc_ref=dc_ref,
        dc_table=dc_table,
    )
    proficiency_bonus = int(getattr(actor, "proficiency_bonus", 2)) if proficiency else 0
    bonus = (
        actor_ability_modifier(actor, ability, status_effects=status_effects)
        + proficiency_bonus
        + extra_bonus
        - d20_penalty
    )
    roll = roll_service.roll(d20_expression(bonus), advantage=advantage)
    return CheckResult(
        actor_id=actor_id,
        ability=ability,
        dc=dc,
        dc_source=dc_source,
        roll=roll,
        success=roll.total >= dc,
        bonus=bonus,
        proficient=proficiency,
        skill=skill,
        tool=tool,
        proficiency_sources=proficiency_sources,
        d20_penalty=d20_penalty,
        d20_penalty_sources=d20_penalty_sources,
    )


def d20_expression(bonus: int) -> str:
    if bonus < 0:
        return f"1d20{bonus}"
    return f"1d20+{bonus}"


def charisma_check_minimum_d20_adjustment(
    *,
    status_effects: list[dict[str, Any]],
    ability: str,
    natural_d20: int,
    current_d20: int | None = None,
) -> dict[str, Any] | None:
    if ability.lower() != "cha":
        return None
    effective_d20 = natural_d20 if current_d20 is None else current_d20
    best_floor = effective_d20
    best_effect: dict[str, Any] | None = None
    for effect in status_effects:
        modifiers = effect.get("passive_modifiers", {})
        if not isinstance(modifiers, dict):
            continue
        floor = modifiers.get(CHARISMA_CHECK_MINIMUM_D20_MODIFIER)
        if not isinstance(floor, int) or isinstance(floor, bool):
            continue
        if floor <= best_floor:
            continue
        best_floor = floor
        best_effect = effect
    if best_effect is None:
        return None
    return {
        "source_action_id": best_effect.get("source_action_id") or GLIBNESS_ACTION_ID,
        "effect_id": best_effect.get("effect_id"),
        "modifier": CHARISMA_CHECK_MINIMUM_D20_MODIFIER,
        "ability": "cha",
        "original_d20": natural_d20,
        "d20_before": effective_d20,
        "d20_after": best_floor,
        "adjustment": best_floor - effective_d20,
    }

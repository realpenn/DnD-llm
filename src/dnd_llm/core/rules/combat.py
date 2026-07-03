from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..dice import RollResult, RollService
from ..models import Character, Combatant, Monster
from .checks import actor_ability_modifier, d20_expression
from .conditions import exhaustion_d20_penalty


@dataclass
class AttackResult:
    attacker_id: str
    target_id: str
    roll: RollResult
    armor_class: int
    hit: bool
    critical: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "attacker_id": self.attacker_id,
            "target_id": self.target_id,
            "roll": self.roll.to_dict(),
            "armor_class": self.armor_class,
            "hit": self.hit,
            "critical": self.critical,
        }


def attack_roll(
    *,
    attacker_id: str,
    attacker: Character | Monster | Combatant,
    target_id: str,
    target: Character | Monster | Combatant,
    roll_service: RollService,
    ability: str = "str",
    proficiency: bool = True,
    bonus: int = 0,
    advantage: str | None = None,
) -> AttackResult:
    prof = getattr(attacker, "proficiency_bonus", 2) if proficiency else 0
    attack_bonus = (
        actor_ability_modifier(
            attacker,
            ability,
            status_effects=getattr(attacker, "status_effects", []),
        )
        + int(prof)
        + bonus
        - exhaustion_d20_penalty(getattr(attacker, "status_effects", []))
    )
    roll = roll_service.roll(d20_expression(attack_bonus), advantage=advantage)
    natural = next(die.value for die in roll.dice if die.sides == 20 and die.kept)
    armor_class = int(getattr(target, "armor_class"))
    hit = natural == 20 or (natural != 1 and roll.total >= armor_class)
    return AttackResult(
        attacker_id=attacker_id,
        target_id=target_id,
        roll=roll,
        armor_class=armor_class,
        hit=hit,
        critical=natural == 20,
    )


def apply_damage(
    target: Character | Monster | Combatant,
    amount: int,
    damage_type: str = "untyped",
) -> int:
    adjusted = amount
    if damage_type in getattr(target, "immunities", []):
        adjusted = 0
    elif damage_type in getattr(target, "resistances", []) or _has_condition(target, "petrified"):
        adjusted //= 2
    elif damage_type in getattr(target, "vulnerabilities", []):
        adjusted *= 2
    temp_hp = int(getattr(target, "temp_hp", 0))
    absorbed = min(temp_hp, adjusted)
    setattr(target, "temp_hp", temp_hp - absorbed)
    if int(getattr(target, "temp_hp", 0)) == 0:
        setattr(target, "temp_hp_source_effect_id", None)
    before = int(getattr(target, "hp_current"))
    setattr(target, "hp_current", max(0, before - (adjusted - absorbed)))
    return before - int(getattr(target, "hp_current"))


def apply_healing(target: Character | Monster | Combatant, amount: int) -> int:
    before = int(getattr(target, "hp_current"))
    max_hp = int(getattr(target, "hp_max"))
    setattr(target, "hp_current", min(max_hp, before + amount))
    return int(getattr(target, "hp_current")) - before


def _has_condition(target: Character | Monster | Combatant, condition: str) -> bool:
    return any(
        effect.get("condition") == condition
        for effect in getattr(target, "status_effects", [])
        if isinstance(effect, dict)
    )

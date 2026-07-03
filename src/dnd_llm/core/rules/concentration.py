from __future__ import annotations

from ..dice import RollService
from ..models import Character, Combatant
from .checks import actor_ability_modifier, d20_expression
from .conditions import exhaustion_d20_penalty


def clear_other_concentration(
    actor: Character | Combatant, keep_effect_id: str | None = None
) -> list[str]:
    removed: list[str] = []
    effects = getattr(actor, "status_effects")
    retained: list[dict[str, object]] = []
    for effect in effects:
        if effect.get("concentration") and effect.get("effect_id") != keep_effect_id:
            removed.append(str(effect.get("effect_id")))
        else:
            retained.append(effect)
    effects[:] = retained
    return removed


def concentration_save(
    actor: Character | Combatant,
    damage_taken: int,
    roll_service: RollService,
) -> tuple[bool, dict[str, object]]:
    dc = max(10, damage_taken // 2)
    bonus = actor_ability_modifier(actor, "con") - exhaustion_d20_penalty(
        getattr(actor, "status_effects", [])
    )
    roll = roll_service.roll(d20_expression(bonus))
    return roll.total >= dc, {"dc": dc, "roll": roll.to_dict()}

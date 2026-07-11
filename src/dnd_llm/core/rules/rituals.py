from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..automation.definitions import ActionDefinition
from ..models import Character

RITUAL_ADEPT_ACTION_ID = "srd.ritual_adept"


@dataclass(frozen=True)
class RitualEligibility:
    allowed: bool
    reason: str
    source: str | None = None


def ritual_casting_eligibility(
    character: Character,
    action: ActionDefinition,
    *,
    requested_slot_level: int | None,
) -> RitualEligibility:
    if action.action_type != "spell":
        return RitualEligibility(False, "ritual casting requires a spell")
    if not bool(action.properties.get("ritual", False)):
        return RitualEligibility(False, "spell does not have the Ritual tag")
    base_slot_level = action.cost.spell_slot_level
    if base_slot_level is None or base_slot_level <= 0:
        return RitualEligibility(False, "ritual casting requires a level 1+ spell")
    if requested_slot_level is not None and requested_slot_level > base_slot_level:
        return RitualEligibility(False, "ritual spells cannot be cast at a higher level")

    spell_refs = spell_reference_ids(action)
    if _has_any_spell_ref(character.prepared_spells, spell_refs):
        return RitualEligibility(True, "prepared ritual spell", "prepared_spell")
    if int(character.class_levels.get("wizard", 0)) >= 1 and _has_any_spell_ref(
        character.known_spells,
        spell_refs,
    ):
        return RitualEligibility(True, "Wizard Ritual Adept spellbook entry", "wizard_spellbook")
    return RitualEligibility(
        False,
        "ritual casting requires a prepared ritual spell or a Wizard spellbook entry",
    )


def spell_reference_ids(action: ActionDefinition) -> set[str]:
    refs = {_normalize_spell_ref(action.id)}
    properties: dict[str, Any] = action.properties if isinstance(action.properties, dict) else {}
    for key in ("spell_definition_id", "spell_id"):
        value = properties.get(key)
        if isinstance(value, str) and value:
            refs.add(_normalize_spell_ref(value))
    return refs


def _has_any_spell_ref(values: list[str], spell_refs: set[str]) -> bool:
    normalized_values = {_normalize_spell_ref(str(value)) for value in values}
    return bool(normalized_values & spell_refs)


def _normalize_spell_ref(value: str) -> str:
    if value.startswith("srd.spell."):
        return value
    if value.startswith("srd."):
        return "srd.spell." + value.removeprefix("srd.")
    return value

from __future__ import annotations

from ..core.models import Character

STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]


def default_fighter(character_id: str, name: str) -> Character:
    return Character(
        id=character_id,
        name=name,
        abilities={"str": 15, "dex": 13, "con": 14, "int": 10, "wis": 12, "cha": 8},
        class_levels={"fighter": 1},
        proficiency_bonus=2,
        hp_current=12,
        hp_max=12,
        hit_dice={"d10": 1},
        armor_class=16,
        speed_ft=30,
        saving_throw_proficiencies=["str", "con"],
        equipment=["srd.chain_mail", "srd.shield", "srd.longsword"],
        resources={"srd.resource.second_wind": 2},
        actions=["srd.longsword_attack", "srd.second_wind", "srd.move"],
        zone_id="start",
    )


def validate_standard_array(abilities: dict[str, int]) -> bool:
    return sorted(abilities.values(), reverse=True) == STANDARD_ARRAY

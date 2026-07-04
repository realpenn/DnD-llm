from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ..models import Character
from .checks import ability_modifier

HEAVY_ARMOR_ITEM_IDS = frozenset({"srd.chain_mail"})
ARMOR_ITEM_IDS = frozenset({"srd.leather_armor", "srd.chain_mail"})
SHIELD_ITEM_IDS = frozenset({"srd.shield"})
HUNTERS_PREY_CHOICE_KEY = "ranger.hunter.hunters_prey"
HUNTERS_PREY_COLOSSUS_SLAYER = "colossus_slayer"
HUNTERS_PREY_HORDE_BREAKER = "horde_breaker"
HUNTER_DEFENSIVE_TACTICS_CHOICE_KEY = "ranger.hunter.defensive_tactics"
HUNTER_DEFENSIVE_TACTICS_ESCAPE_THE_HORDE = "escape_the_horde"
HUNTER_DEFENSIVE_TACTICS_MULTIATTACK_DEFENSE = "multiattack_defense"
DIVINE_ORDER_CHOICE_KEY = "cleric.divine_order"
DIVINE_ORDER_PROTECTOR = "protector"
DIVINE_ORDER_THAUMATURGE = "thaumaturge"
DRUID_PRIMAL_ORDER_CHOICE_KEY = "druid.primal_order"
DRUID_PRIMAL_ORDER_MAGICIAN = "magician"
DRUID_PRIMAL_ORDER_WARDEN = "warden"
DRUID_CIRCLE_LAND_CHOICE_KEY = "druid.land.current_land"
DRUID_CIRCLE_LAND_TYPES = frozenset({"arid", "polar", "temperate", "tropical"})
DRUID_NATURES_WARD_RESISTANCE_BY_LAND = {
    "arid": "fire",
    "polar": "cold",
    "temperate": "lightning",
    "tropical": "poison",
}
DRACONIC_ELEMENTAL_AFFINITY_CHOICE_KEY = "sorcerer.draconic.elemental_affinity"
DRACONIC_ELEMENTAL_AFFINITY_DAMAGE_TYPES = frozenset(
    {"acid", "cold", "fire", "lightning", "poison"}
)
WARLOCK_ELDRITCH_INVOCATION_CHOICE_KEY = "warlock.eldritch_invocation"
WARLOCK_DEVILS_SIGHT_CHOICE_KEY = "warlock.eldritch_invocation.devils_sight"
WARLOCK_DEVILS_SIGHT_SELECTED = "selected"
WARLOCK_AGONIZING_BLAST_CANTRIP_KEY = "warlock.eldritch_invocation.agonizing_blast.cantrip"
WARLOCK_AGONIZING_BLAST_ELDRITCH_BLAST = "srd.spell.eldritch_blast"
WARLOCK_ELDRITCH_SPEAR_CANTRIP_KEY = "warlock.eldritch_invocation.eldritch_spear.cantrip"
WARLOCK_ELDRITCH_SPEAR_ELDRITCH_BLAST = "srd.spell.eldritch_blast"
WARLOCK_REPELLING_BLAST_CANTRIP_KEY = "warlock.eldritch_invocation.repelling_blast.cantrip"
WARLOCK_REPELLING_BLAST_ELDRITCH_BLAST = "srd.spell.eldritch_blast"
WARLOCK_ASCENDANT_STEP_CHOICE_KEY = "warlock.eldritch_invocation.ascendant_step"
WARLOCK_ASCENDANT_STEP_SELECTED = "selected"
WARLOCK_ARMOR_OF_SHADOWS_CHOICE_KEY = "warlock.eldritch_invocation.armor_of_shadows"
WARLOCK_ARMOR_OF_SHADOWS_SELECTED = "selected"
WARLOCK_FIENDISH_VIGOR_CHOICE_KEY = "warlock.eldritch_invocation.fiendish_vigor"
WARLOCK_FIENDISH_VIGOR_SELECTED = "selected"
WARLOCK_MASK_OF_MANY_FACES_CHOICE_KEY = "warlock.eldritch_invocation.mask_of_many_faces"
WARLOCK_MASK_OF_MANY_FACES_SELECTED = "selected"
WARLOCK_MISTY_VISIONS_CHOICE_KEY = "warlock.eldritch_invocation.misty_visions"
WARLOCK_MISTY_VISIONS_SELECTED = "selected"
WARLOCK_ONE_WITH_SHADOWS_CHOICE_KEY = "warlock.eldritch_invocation.one_with_shadows"
WARLOCK_ONE_WITH_SHADOWS_SELECTED = "selected"
WARLOCK_OTHERWORLDLY_LEAP_CHOICE_KEY = "warlock.eldritch_invocation.otherworldly_leap"
WARLOCK_OTHERWORLDLY_LEAP_SELECTED = "selected"
WARLOCK_MASTER_OF_MYRIAD_FORMS_CHOICE_KEY = "warlock.eldritch_invocation.master_of_myriad_forms"
WARLOCK_MASTER_OF_MYRIAD_FORMS_SELECTED = "selected"
WARLOCK_GIFT_OF_DEPTHS_CHOICE_KEY = "warlock.eldritch_invocation.gift_of_the_depths"
WARLOCK_GIFT_OF_DEPTHS_SELECTED = "selected"
WARLOCK_GAZE_OF_TWO_MINDS_CHOICE_KEY = "warlock.eldritch_invocation.gaze_of_two_minds"
WARLOCK_GAZE_OF_TWO_MINDS_SELECTED = "selected"
WARLOCK_INVESTMENT_OF_CHAIN_MASTER_CHOICE_KEY = (
    "warlock.eldritch_invocation.investment_of_the_chain_master"
)
WARLOCK_INVESTMENT_OF_CHAIN_MASTER_SELECTED = "selected"
WARLOCK_LESSONS_OF_FIRST_ONES_CHOICE_PREFIX = (
    "warlock.eldritch_invocation.lessons_of_the_first_ones"
)
WARLOCK_LESSONS_OF_FIRST_ONES_SELECTED = "selected"
WARLOCK_LESSONS_OF_FIRST_ONES_ORIGIN_FEATS = frozenset({"alert", "skilled"})
WARLOCK_PACT_OF_BLADE_CHOICE_KEY = "warlock.eldritch_invocation.pact_of_the_blade"
WARLOCK_PACT_OF_BLADE_SELECTED = "selected"
WARLOCK_PACT_OF_BLADE_WEAPON_ACTION_IDS = frozenset(
    {"srd.longsword_attack", "srd.shortsword_attack"}
)
WARLOCK_PACT_OF_CHAIN_CHOICE_KEY = "warlock.eldritch_invocation.pact_of_the_chain"
WARLOCK_PACT_OF_CHAIN_SELECTED = "selected"
WARLOCK_PACT_OF_TOME_CHOICE_KEY = "warlock.eldritch_invocation.pact_of_the_tome"
WARLOCK_PACT_OF_TOME_SELECTED = "selected"
WARLOCK_PACT_OF_TOME_CANTRIP_COUNT = 3
WARLOCK_PACT_OF_TOME_RITUAL_COUNT = 2
WARLOCK_THIRSTING_BLADE_CHOICE_KEY = "warlock.eldritch_invocation.thirsting_blade"
WARLOCK_THIRSTING_BLADE_SELECTED = "selected"
WARLOCK_ELDRITCH_SMITE_CHOICE_KEY = "warlock.eldritch_invocation.eldritch_smite"
WARLOCK_ELDRITCH_SMITE_SELECTED = "selected"
WARLOCK_ELDRITCH_MIND = "eldritch_mind"
UNCANNY_METABOLISM_RESOURCE = "srd.resource.uncanny_metabolism"
WHOLENESS_OF_BODY_RESOURCE = "srd.resource.wholeness_of_body"
FOCUS_POINTS_RESOURCE = "srd.resource.focus_points"
GIFT_OF_DEPTHS_RESOURCE = "srd.resource.gift_of_the_depths"
DARK_ONES_OWN_LUCK_RESOURCE = "srd.resource.dark_ones_own_luck"
INDOMITABLE_RESOURCE = "srd.resource.indomitable"
STROKE_OF_LUCK_RESOURCE = "srd.resource.stroke_of_luck"
HEROIC_INSPIRATION_RESOURCE = "srd.resource.heroic_inspiration"
NATURAL_RECOVERY_SPELL_SLOTS_RESOURCE = "srd.resource.natural_recovery_spell_slots"
NATURAL_RECOVERY_CIRCLE_SPELL_RESOURCE = "srd.resource.natural_recovery_circle_spell"
TIRELESS_RESOURCE = "srd.resource.tireless"
SAVING_THROW_ABILITIES = frozenset({"str", "dex", "con", "int", "wis", "cha"})
DISCIPLINED_SURVIVOR_ACTION_ID = "srd.disciplined_survivor"
RELIABLE_TALENT_ACTION_ID = "srd.reliable_talent"
RELIABLE_TALENT_D20_FLOOR = 10
RELIABLE_TALENT_MAX_NATURAL = 9
SLIPPERY_MIND_ACTION_ID = "srd.slippery_mind"
SLIPPERY_MIND_SAVING_THROWS = frozenset({"wis", "cha"})
ELUSIVE_ACTION_ID = "srd.elusive"
STROKE_OF_LUCK_ACTION_ID = "srd.stroke_of_luck"
STROKE_OF_LUCK_D20 = 20

PRIMAL_KNOWLEDGE_SKILLS = frozenset(
    {
        "acrobatics",
        "intimidation",
        "perception",
        "stealth",
        "survival",
    }
)


def barbarian_fast_movement_bonus(character: Character) -> int:
    if int(character.class_levels.get("barbarian", 0)) < 5:
        return 0
    if is_wearing_heavy_armor(character):
        return 0
    return 10


def ranger_roving_speed_bonus(character: Character) -> int:
    if int(character.class_levels.get("ranger", 0)) < 6:
        return 0
    if is_wearing_heavy_armor(character):
        return 0
    return 10


def ranger_tireless_uses(character: Character) -> int:
    if int(character.class_levels.get("ranger", 0)) < 10:
        return 0
    wisdom = int(character.abilities.get("wis", character.abilities.get("WIS", 10)))
    return max(1, ability_modifier(wisdom))


def monk_unarmored_movement_bonus(character: Character) -> int:
    monk_level = int(character.class_levels.get("monk", 0))
    if monk_level < 2:
        return 0
    if is_wearing_armor(character) or is_wielding_shield(character):
        return 0
    if monk_level >= 18:
        return 30
    if monk_level >= 14:
        return 25
    if monk_level >= 10:
        return 20
    if monk_level >= 6:
        return 15
    return 10


def class_feature_speed_bonus(character: Character) -> int:
    return (
        barbarian_fast_movement_bonus(character)
        + ranger_roving_speed_bonus(character)
        + monk_unarmored_movement_bonus(character)
    )


def monk_martial_arts_die(character: Character) -> str:
    monk_level = int(character.class_levels.get("monk", 0))
    if monk_level >= 17:
        return "d12"
    if monk_level >= 11:
        return "d10"
    if monk_level >= 5:
        return "d8"
    return "d6"


def has_barbarian_feature(character: Character, *, level: int) -> bool:
    return int(character.class_levels.get("barbarian", 0)) >= level


def has_barbarian_berserker_feature(character: Character, *, level: int) -> bool:
    return has_barbarian_feature(character, level=level) and (
        character.subclasses.get("barbarian") == "berserker"
    )


def barbarian_rage_damage_bonus(character: Character) -> int:
    barbarian_level = int(character.class_levels.get("barbarian", 0))
    if barbarian_level <= 0:
        return 0
    if barbarian_level >= 16:
        return 4
    if barbarian_level >= 9:
        return 3
    return 2


def has_monk_feature(character: Character, *, level: int) -> bool:
    return int(character.class_levels.get("monk", 0)) >= level


def monk_evasion_applies(character: Character) -> bool:
    return has_monk_feature(character, level=7)


def rogue_evasion_applies(character: Character) -> bool:
    return int(character.class_levels.get("rogue", 0)) >= 7


def evasion_applies(character: Character) -> bool:
    return monk_evasion_applies(character) or rogue_evasion_applies(character)


def reliable_talent_applies(character: Character) -> bool:
    return int(character.class_levels.get("rogue", 0)) >= 7


def rogue_slippery_mind_applies(character: Character) -> bool:
    return int(character.class_levels.get("rogue", 0)) >= 15


def rogue_elusive_applies(character: Character) -> bool:
    return int(character.class_levels.get("rogue", 0)) >= 18


def rogue_stroke_of_luck_applies(character: Character) -> bool:
    return int(character.class_levels.get("rogue", 0)) >= 20


def reliable_talent_d20_adjustment(
    character: Character,
    *,
    proficiency_sources: Iterable[str],
    natural_d20: int,
) -> int:
    if not reliable_talent_applies(character):
        return 0
    if not any(
        source.startswith("skill:") or source.startswith("tool:") for source in proficiency_sources
    ):
        return 0
    if natural_d20 > RELIABLE_TALENT_MAX_NATURAL:
        return 0
    return RELIABLE_TALENT_D20_FLOOR - natural_d20


def monk_acrobatic_movement_applies(character: Character) -> bool:
    return (
        has_monk_feature(character, level=9)
        and not is_wearing_armor(character)
        and not is_wielding_shield(character)
    )


def monk_can_move_along_vertical_surfaces(character: Character) -> bool:
    return monk_acrobatic_movement_applies(character)


def monk_can_move_across_liquids(character: Character) -> bool:
    return monk_acrobatic_movement_applies(character)


def monk_self_restoration_applies(character: Character) -> bool:
    return has_monk_feature(character, level=10)


def monk_heightened_focus_applies(character: Character) -> bool:
    return has_monk_feature(character, level=10)


def monk_deflect_energy_applies(character: Character) -> bool:
    return has_monk_feature(character, level=13)


def monk_disciplined_survivor_applies(character: Character) -> bool:
    return has_monk_feature(character, level=14)


def monk_perfect_focus_applies(character: Character) -> bool:
    return has_monk_feature(character, level=15)


def monk_superior_defense_applies(character: Character) -> bool:
    return has_monk_feature(character, level=18)


def saving_throw_proficiency_sources(actor: Any, ability: str) -> list[dict[str, Any]]:
    ability_key = ability.lower()
    sources: list[dict[str, Any]] = []
    if ability_key in {
        str(item).lower() for item in getattr(actor, "saving_throw_proficiencies", [])
    }:
        sources.append({"kind": "saving_throw_proficiency", "ability": ability_key})
    if (
        isinstance(actor, Character)
        and ability_key in SAVING_THROW_ABILITIES
        and monk_disciplined_survivor_applies(actor)
    ):
        sources.append(
            {
                "kind": "disciplined_survivor",
                "source_action_id": DISCIPLINED_SURVIVOR_ACTION_ID,
                "ability": ability_key,
            }
        )
    if (
        isinstance(actor, Character)
        and ability_key in SLIPPERY_MIND_SAVING_THROWS
        and rogue_slippery_mind_applies(actor)
    ):
        sources.append(
            {
                "kind": "slippery_mind",
                "source_action_id": SLIPPERY_MIND_ACTION_ID,
                "ability": ability_key,
            }
        )
    return sources


def monk_forgoing_food_drink_exhaustion_immunity(character: Character) -> bool:
    return monk_self_restoration_applies(character)


def monk_slow_fall_damage_reduction(character: Character) -> int:
    monk_level = int(character.class_levels.get("monk", 0))
    if monk_level < 4:
        return 0
    return monk_level * 5


def has_monk_open_hand_feature(character: Character, *, level: int) -> bool:
    return has_monk_feature(character, level=level) and (
        character.subclasses.get("monk") == "open_hand"
    )


def monk_open_hand_fleet_step_applies(character: Character) -> bool:
    return has_monk_open_hand_feature(character, level=11)


def monk_open_hand_quivering_palm_applies(character: Character) -> bool:
    return has_monk_open_hand_feature(character, level=17)


def has_paladin_feature(character: Character, *, level: int) -> bool:
    return int(character.class_levels.get("paladin", 0)) >= level


def has_fighter_champion_feature(character: Character, *, level: int) -> bool:
    return (
        int(character.class_levels.get("fighter", 0)) >= level
        and character.subclasses.get("fighter") == "champion"
    )


def has_fighter_feature(character: Character, *, level: int) -> bool:
    return int(character.class_levels.get("fighter", 0)) >= level


def fighter_indomitable_uses(character: Character) -> int:
    fighter_level = int(character.class_levels.get("fighter", 0))
    if fighter_level >= 17:
        return 3
    if fighter_level >= 13:
        return 2
    if fighter_level >= 9:
        return 1
    return 0


def has_cleric_life_domain_feature(character: Character, *, level: int) -> bool:
    return (
        int(character.class_levels.get("cleric", 0)) >= level
        and character.subclasses.get("cleric") == "life"
    )


def cleric_divine_order_choice(character: Character) -> str | None:
    if int(character.class_levels.get("cleric", 0)) < 1:
        return None
    choice = character.feature_choices.get(DIVINE_ORDER_CHOICE_KEY)
    if choice in {DIVINE_ORDER_PROTECTOR, DIVINE_ORDER_THAUMATURGE}:
        return choice
    return None


def has_cleric_divine_order(character: Character, choice: str) -> bool:
    return cleric_divine_order_choice(character) == choice


def cleric_thaumaturge_check_bonus(
    character: Character,
    *,
    ability: str,
    skill: str | None,
) -> int:
    if not has_cleric_divine_order(character, DIVINE_ORDER_THAUMATURGE):
        return 0
    if ability.lower() != "int" or skill not in {"arcana", "religion"}:
        return 0
    wisdom = int(character.abilities.get("wis", character.abilities.get("WIS", 10)))
    return max(1, ability_modifier(wisdom))


def druid_primal_order_choice(character: Character) -> str | None:
    if int(character.class_levels.get("druid", 0)) < 1:
        return None
    choice = character.feature_choices.get(DRUID_PRIMAL_ORDER_CHOICE_KEY)
    if choice in {DRUID_PRIMAL_ORDER_MAGICIAN, DRUID_PRIMAL_ORDER_WARDEN}:
        return choice
    return None


def has_druid_primal_order(character: Character, choice: str) -> bool:
    return druid_primal_order_choice(character) == choice


def druid_magician_check_bonus(
    character: Character,
    *,
    ability: str,
    skill: str | None,
) -> int:
    if not has_druid_primal_order(character, DRUID_PRIMAL_ORDER_MAGICIAN):
        return 0
    if ability.lower() != "int" or skill not in {"arcana", "nature"}:
        return 0
    wisdom = int(character.abilities.get("wis", character.abilities.get("WIS", 10)))
    return max(1, ability_modifier(wisdom))


def has_druid_circle_of_the_land_feature(character: Character, *, level: int) -> bool:
    return (
        int(character.class_levels.get("druid", 0)) >= level
        and character.subclasses.get("druid") == "land"
    )


def druid_natures_ward_resistance_type(character: Character) -> str | None:
    if not has_druid_circle_of_the_land_feature(character, level=10):
        return None
    choice = character.feature_choices.get(DRUID_CIRCLE_LAND_CHOICE_KEY)
    if choice not in DRUID_CIRCLE_LAND_TYPES:
        return None
    return DRUID_NATURES_WARD_RESISTANCE_BY_LAND[choice]


def has_warlock_fiend_feature(character: Character, *, level: int) -> bool:
    return (
        int(character.class_levels.get("warlock", 0)) >= level
        and character.subclasses.get("warlock") == "fiend"
    )


def dark_ones_own_luck_uses(character: Character) -> int:
    if not has_warlock_fiend_feature(character, level=6):
        return 0
    charisma = int(character.abilities.get("cha", character.abilities.get("CHA", 10)))
    return max(1, ability_modifier(charisma))


def has_warlock_eldritch_mind(character: Character) -> bool:
    return (
        int(character.class_levels.get("warlock", 0)) >= 1
        and character.feature_choices.get(WARLOCK_ELDRITCH_INVOCATION_CHOICE_KEY)
        == WARLOCK_ELDRITCH_MIND
        and "srd.eldritch_mind" in character.actions
    )


def has_warlock_devils_sight(character: Character) -> bool:
    return (
        int(character.class_levels.get("warlock", 0)) >= 2
        and character.feature_choices.get(WARLOCK_DEVILS_SIGHT_CHOICE_KEY)
        == WARLOCK_DEVILS_SIGHT_SELECTED
        and "srd.devils_sight" in character.actions
    )


def warlock_devils_sight_range_ft(character: Character) -> int:
    return 120 if has_warlock_devils_sight(character) else 0


def warlock_lessons_of_first_ones_choice_key(feat_id: str) -> str:
    return f"{WARLOCK_LESSONS_OF_FIRST_ONES_CHOICE_PREFIX}.{feat_id}"


def warlock_lessons_of_first_ones_origin_feats(character: Character) -> list[str]:
    if int(character.class_levels.get("warlock", 0)) < 2:
        return []
    feats: list[str] = []
    for feat_id in sorted(WARLOCK_LESSONS_OF_FIRST_ONES_ORIGIN_FEATS):
        if (
            character.feature_choices.get(warlock_lessons_of_first_ones_choice_key(feat_id))
            == WARLOCK_LESSONS_OF_FIRST_ONES_SELECTED
        ):
            feats.append(feat_id)
    return feats


def has_warlock_lessons_of_first_ones(character: Character) -> bool:
    return bool(warlock_lessons_of_first_ones_origin_feats(character)) and (
        "srd.lessons_of_the_first_ones" in character.actions
    )


def has_warlock_pact_of_chain(character: Character) -> bool:
    return (
        int(character.class_levels.get("warlock", 0)) >= 1
        and character.feature_choices.get(WARLOCK_PACT_OF_CHAIN_CHOICE_KEY)
        == WARLOCK_PACT_OF_CHAIN_SELECTED
        and "srd.pact_of_the_chain" in character.actions
    )


def has_warlock_pact_of_blade(character: Character) -> bool:
    return (
        int(character.class_levels.get("warlock", 0)) >= 1
        and character.feature_choices.get(WARLOCK_PACT_OF_BLADE_CHOICE_KEY)
        == WARLOCK_PACT_OF_BLADE_SELECTED
        and "srd.pact_of_the_blade" in character.actions
    )


def warlock_pact_of_tome_cantrip_choice_key(index: int) -> str:
    return f"{WARLOCK_PACT_OF_TOME_CHOICE_KEY}.cantrip.{index}"


def warlock_pact_of_tome_ritual_choice_key(index: int) -> str:
    return f"{WARLOCK_PACT_OF_TOME_CHOICE_KEY}.ritual.{index}"


def has_warlock_pact_of_tome(character: Character) -> bool:
    return (
        int(character.class_levels.get("warlock", 0)) >= 1
        and character.feature_choices.get(WARLOCK_PACT_OF_TOME_CHOICE_KEY)
        == WARLOCK_PACT_OF_TOME_SELECTED
        and "srd.pact_of_the_tome" in character.actions
    )


def has_warlock_thirsting_blade(character: Character) -> bool:
    return (
        int(character.class_levels.get("warlock", 0)) >= 5
        and has_warlock_pact_of_blade(character)
        and character.feature_choices.get(WARLOCK_THIRSTING_BLADE_CHOICE_KEY)
        == WARLOCK_THIRSTING_BLADE_SELECTED
        and "srd.thirsting_blade" in character.actions
    )


def has_warlock_eldritch_smite(character: Character) -> bool:
    return (
        int(character.class_levels.get("warlock", 0)) >= 5
        and has_warlock_pact_of_blade(character)
        and character.feature_choices.get(WARLOCK_ELDRITCH_SMITE_CHOICE_KEY)
        == WARLOCK_ELDRITCH_SMITE_SELECTED
        and "srd.eldritch_smite" in character.actions
    )


def warlock_agonizing_blast_bonus(character: Character, *, spell_id: str | None) -> int:
    if int(character.class_levels.get("warlock", 0)) < 2:
        return 0
    if "srd.agonizing_blast" not in character.actions:
        return 0
    if spell_id is None:
        return 0
    if character.feature_choices.get(WARLOCK_AGONIZING_BLAST_CANTRIP_KEY) != spell_id:
        return 0
    charisma = int(character.abilities.get("cha", character.abilities.get("CHA", 10)))
    return max(0, ability_modifier(charisma))


def warlock_eldritch_spear_range_bonus(character: Character, *, spell_id: str | None) -> int:
    warlock_level = int(character.class_levels.get("warlock", 0))
    if warlock_level < 2:
        return 0
    if "srd.eldritch_spear" not in character.actions:
        return 0
    if spell_id is None:
        return 0
    if character.feature_choices.get(WARLOCK_ELDRITCH_SPEAR_CANTRIP_KEY) != spell_id:
        return 0
    return 30 * warlock_level


def has_warlock_repelling_blast(character: Character, *, spell_id: str | None) -> bool:
    if int(character.class_levels.get("warlock", 0)) < 2:
        return False
    if "srd.repelling_blast" not in character.actions:
        return False
    if spell_id is None:
        return False
    return character.feature_choices.get(WARLOCK_REPELLING_BLAST_CANTRIP_KEY) == spell_id


def has_warlock_armor_of_shadows(character: Character) -> bool:
    return (
        int(character.class_levels.get("warlock", 0)) >= 1
        and character.feature_choices.get(WARLOCK_ARMOR_OF_SHADOWS_CHOICE_KEY)
        == WARLOCK_ARMOR_OF_SHADOWS_SELECTED
        and "srd.armor_of_shadows" in character.actions
    )


def has_warlock_ascendant_step(character: Character) -> bool:
    return (
        int(character.class_levels.get("warlock", 0)) >= 5
        and character.feature_choices.get(WARLOCK_ASCENDANT_STEP_CHOICE_KEY)
        == WARLOCK_ASCENDANT_STEP_SELECTED
        and "srd.ascendant_step" in character.actions
    )


def has_warlock_fiendish_vigor(character: Character) -> bool:
    return (
        int(character.class_levels.get("warlock", 0)) >= 2
        and character.feature_choices.get(WARLOCK_FIENDISH_VIGOR_CHOICE_KEY)
        == WARLOCK_FIENDISH_VIGOR_SELECTED
        and "srd.fiendish_vigor" in character.actions
    )


def has_warlock_mask_of_many_faces(character: Character) -> bool:
    return (
        int(character.class_levels.get("warlock", 0)) >= 2
        and character.feature_choices.get(WARLOCK_MASK_OF_MANY_FACES_CHOICE_KEY)
        == WARLOCK_MASK_OF_MANY_FACES_SELECTED
        and "srd.mask_of_many_faces" in character.actions
    )


def has_warlock_misty_visions(character: Character) -> bool:
    return (
        int(character.class_levels.get("warlock", 0)) >= 2
        and character.feature_choices.get(WARLOCK_MISTY_VISIONS_CHOICE_KEY)
        == WARLOCK_MISTY_VISIONS_SELECTED
        and "srd.misty_visions" in character.actions
    )


def has_warlock_one_with_shadows(character: Character) -> bool:
    return (
        int(character.class_levels.get("warlock", 0)) >= 5
        and character.feature_choices.get(WARLOCK_ONE_WITH_SHADOWS_CHOICE_KEY)
        == WARLOCK_ONE_WITH_SHADOWS_SELECTED
        and "srd.one_with_shadows" in character.actions
    )


def has_warlock_otherworldly_leap(character: Character) -> bool:
    return (
        int(character.class_levels.get("warlock", 0)) >= 2
        and character.feature_choices.get(WARLOCK_OTHERWORLDLY_LEAP_CHOICE_KEY)
        == WARLOCK_OTHERWORLDLY_LEAP_SELECTED
        and "srd.otherworldly_leap" in character.actions
    )


def has_warlock_master_of_myriad_forms(character: Character) -> bool:
    return (
        int(character.class_levels.get("warlock", 0)) >= 5
        and character.feature_choices.get(WARLOCK_MASTER_OF_MYRIAD_FORMS_CHOICE_KEY)
        == WARLOCK_MASTER_OF_MYRIAD_FORMS_SELECTED
        and "srd.master_of_myriad_forms" in character.actions
    )


def has_warlock_gift_of_depths(character: Character) -> bool:
    return (
        int(character.class_levels.get("warlock", 0)) >= 5
        and character.feature_choices.get(WARLOCK_GIFT_OF_DEPTHS_CHOICE_KEY)
        == WARLOCK_GIFT_OF_DEPTHS_SELECTED
        and "srd.gift_of_the_depths" in character.actions
    )


def has_warlock_gaze_of_two_minds(character: Character) -> bool:
    return (
        int(character.class_levels.get("warlock", 0)) >= 5
        and character.feature_choices.get(WARLOCK_GAZE_OF_TWO_MINDS_CHOICE_KEY)
        == WARLOCK_GAZE_OF_TWO_MINDS_SELECTED
        and "srd.gaze_of_two_minds" in character.actions
    )


def has_warlock_investment_of_chain_master(character: Character) -> bool:
    return (
        int(character.class_levels.get("warlock", 0)) >= 5
        and has_warlock_pact_of_chain(character)
        and character.feature_choices.get(WARLOCK_INVESTMENT_OF_CHAIN_MASTER_CHOICE_KEY)
        == WARLOCK_INVESTMENT_OF_CHAIN_MASTER_SELECTED
        and "srd.investment_of_the_chain_master" in character.actions
    )


def warlock_gift_of_depths_swim_speed_ft(character: Character) -> int:
    if not has_warlock_gift_of_depths(character):
        return 0
    return int(character.speed_ft) + class_feature_speed_bonus(character)


def has_sorcerer_draconic_feature(character: Character, *, level: int) -> bool:
    return (
        int(character.class_levels.get("sorcerer", 0)) >= level
        and character.subclasses.get("sorcerer") == "draconic"
    )


def has_wizard_evocation_feature(character: Character, *, level: int) -> bool:
    return (
        int(character.class_levels.get("wizard", 0)) >= level
        and character.subclasses.get("wizard") == "evocation"
    )


def has_rogue_thief_feature(character: Character, *, level: int) -> bool:
    return (
        int(character.class_levels.get("rogue", 0)) >= level
        and character.subclasses.get("rogue") == "thief"
    )


def has_ranger_hunter_feature(character: Character, *, level: int) -> bool:
    return (
        int(character.class_levels.get("ranger", 0)) >= level
        and character.subclasses.get("ranger") == "hunter"
    )


def ranger_roving_climb_speed_ft(character: Character) -> int | None:
    if ranger_roving_speed_bonus(character) <= 0:
        return None
    return int(character.speed_ft) + class_feature_speed_bonus(character)


def ranger_roving_swim_speed_ft(character: Character) -> int | None:
    if ranger_roving_speed_bonus(character) <= 0:
        return None
    return int(character.speed_ft) + class_feature_speed_bonus(character)


def ranger_hunters_prey_choice(character: Character) -> str | None:
    if not has_ranger_hunter_feature(character, level=3):
        return None
    choice = character.feature_choices.get(HUNTERS_PREY_CHOICE_KEY)
    if choice:
        return choice
    return HUNTERS_PREY_COLOSSUS_SLAYER


def has_colossus_slayer(character: Character) -> bool:
    return ranger_hunters_prey_choice(character) == HUNTERS_PREY_COLOSSUS_SLAYER


def has_horde_breaker(character: Character) -> bool:
    return ranger_hunters_prey_choice(character) == HUNTERS_PREY_HORDE_BREAKER


def ranger_hunter_defensive_tactics_choice(character: Character) -> str | None:
    if not has_ranger_hunter_feature(character, level=7):
        return None
    choice = character.feature_choices.get(HUNTER_DEFENSIVE_TACTICS_CHOICE_KEY)
    if choice in {
        HUNTER_DEFENSIVE_TACTICS_ESCAPE_THE_HORDE,
        HUNTER_DEFENSIVE_TACTICS_MULTIATTACK_DEFENSE,
    }:
        return choice
    return HUNTER_DEFENSIVE_TACTICS_ESCAPE_THE_HORDE


def has_escape_the_horde(character: Character) -> bool:
    return (
        ranger_hunter_defensive_tactics_choice(character)
        == HUNTER_DEFENSIVE_TACTICS_ESCAPE_THE_HORDE
    )


def has_multiattack_defense(character: Character) -> bool:
    return (
        ranger_hunter_defensive_tactics_choice(character)
        == HUNTER_DEFENSIVE_TACTICS_MULTIATTACK_DEFENSE
    )


def second_story_work_climb_speed(character: Character) -> int | None:
    if not has_rogue_thief_feature(character, level=3):
        return None
    return int(character.speed_ft)


def second_story_work_jump_ability(character: Character) -> str | None:
    if not has_rogue_thief_feature(character, level=3):
        return None
    return "dex"


def draconic_resilience_hp_bonus(character: Character) -> int:
    if not has_sorcerer_draconic_feature(character, level=3):
        return 0
    return int(character.class_levels.get("sorcerer", 0))


def draconic_resilience_armor_class(character: Character) -> int | None:
    if not has_sorcerer_draconic_feature(character, level=3):
        return None
    if is_wearing_armor(character):
        return None
    dexterity = int(character.abilities.get("dex", character.abilities.get("DEX", 10)))
    charisma = int(character.abilities.get("cha", character.abilities.get("CHA", 10)))
    return 10 + ability_modifier(dexterity) + ability_modifier(charisma)


def draconic_elemental_affinity_damage_type(character: Character) -> str | None:
    if not has_sorcerer_draconic_feature(character, level=6):
        return None
    choice = character.feature_choices.get(DRACONIC_ELEMENTAL_AFFINITY_CHOICE_KEY)
    if choice in DRACONIC_ELEMENTAL_AFFINITY_DAMAGE_TYPES:
        return choice
    return None


def draconic_elemental_affinity_damage_bonus(
    character: Character,
    *,
    damage_type: str,
) -> int:
    if draconic_elemental_affinity_damage_type(character) != damage_type:
        return 0
    charisma = int(character.abilities.get("cha", character.abilities.get("CHA", 10)))
    return max(0, ability_modifier(charisma))


def aura_of_protection_saving_throw_bonus(character: Character) -> int:
    if not has_paladin_feature(character, level=6):
        return 0
    charisma = int(character.abilities.get("cha", character.abilities.get("CHA", 10)))
    return max(1, ability_modifier(charisma))


def aura_of_courage_applies(character: Character) -> bool:
    return has_paladin_feature(character, level=10)


def barbarian_unarmored_defense_armor_class(character: Character) -> int | None:
    if not has_barbarian_feature(character, level=1):
        return None
    if is_wearing_armor(character):
        return None
    dexterity = int(character.abilities.get("dex", character.abilities.get("DEX", 10)))
    constitution = int(character.abilities.get("con", character.abilities.get("CON", 10)))
    return 10 + ability_modifier(dexterity) + ability_modifier(constitution)


def monk_unarmored_defense_armor_class(character: Character) -> int | None:
    if not has_monk_feature(character, level=1):
        return None
    if is_wearing_armor(character) or is_wielding_shield(character):
        return None
    dexterity = int(character.abilities.get("dex", character.abilities.get("DEX", 10)))
    wisdom = int(character.abilities.get("wis", character.abilities.get("WIS", 10)))
    return 10 + ability_modifier(dexterity) + ability_modifier(wisdom)


def dark_ones_blessing_temp_hp(character: Character) -> int:
    if not has_warlock_fiend_feature(character, level=3):
        return 0
    charisma = int(character.abilities.get("cha", character.abilities.get("CHA", 10)))
    warlock_level = int(character.class_levels.get("warlock", 0))
    return max(1, ability_modifier(charisma) + warlock_level)


def disciple_of_life_healing_bonus(
    character: Character,
    *,
    spell_slot_level: int,
) -> int:
    if not has_cleric_life_domain_feature(character, level=3):
        return 0
    if spell_slot_level <= 0:
        return 0
    return 2 + spell_slot_level


def blessed_healer_self_healing(
    character: Character,
    *,
    spell_slot_level: int,
) -> int:
    if not has_cleric_life_domain_feature(character, level=6):
        return 0
    if spell_slot_level <= 0:
        return 0
    return 2 + spell_slot_level


def preserve_life_healing_pool(character: Character) -> int:
    if not has_cleric_life_domain_feature(character, level=3):
        return 0
    return int(character.class_levels.get("cleric", 0)) * 5


def champion_heroic_warrior_can_grant_inspiration(character: Character) -> bool:
    return (
        has_fighter_champion_feature(character, level=10)
        and int(character.resources.get(HEROIC_INSPIRATION_RESOURCE, 0)) <= 0
    )


def champion_survivor_death_save_advantage(character: Character) -> bool:
    return has_fighter_champion_feature(character, level=18)


def champion_survivor_death_save_counts_as_20(
    character: Character,
    *,
    natural: int,
) -> bool:
    return has_fighter_champion_feature(character, level=18) and int(natural) in {18, 19}


def champion_survivor_heroic_rally_healing(
    character: Character,
    *,
    hp_current: int,
    hp_max: int,
) -> int:
    if not has_fighter_champion_feature(character, level=18):
        return 0
    if int(hp_current) < 1:
        return 0
    if not is_bloodied(hp_current=hp_current, hp_max=hp_max):
        return 0
    constitution = int(character.abilities.get("con", character.abilities.get("CON", 10)))
    return max(0, 5 + ability_modifier(constitution))


def bloodied_hp_cap(hp_max: int) -> int:
    return max(0, int(hp_max) // 2)


def is_bloodied(*, hp_current: int, hp_max: int) -> bool:
    return int(hp_current) <= bloodied_hp_cap(hp_max)


def remarkable_athlete_applies_to_check(
    character: Character,
    *,
    ability: str,
    skill: str | None,
) -> bool:
    return (
        has_fighter_champion_feature(character, level=3)
        and ability.lower() == "str"
        and skill == "athletics"
    )


def has_condition(status_effects: list[dict[str, Any]], condition: str) -> bool:
    return any(effect.get("condition") == condition for effect in status_effects)


def is_wearing_heavy_armor(character: Character) -> bool:
    return any(item_id in HEAVY_ARMOR_ITEM_IDS for item_id in character.equipment)


def is_wearing_armor(character: Character) -> bool:
    return any(item_id in ARMOR_ITEM_IDS for item_id in character.equipment)


def is_wielding_shield(character: Character) -> bool:
    return any(item_id in SHIELD_ITEM_IDS for item_id in character.equipment)

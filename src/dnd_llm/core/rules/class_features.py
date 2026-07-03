from __future__ import annotations

from typing import Any

from ..models import Character
from .checks import ability_modifier

HEAVY_ARMOR_ITEM_IDS = frozenset({"srd.chain_mail"})
ARMOR_ITEM_IDS = frozenset({"srd.leather_armor", "srd.chain_mail"})
SHIELD_ITEM_IDS = frozenset({"srd.shield"})
HUNTERS_PREY_CHOICE_KEY = "ranger.hunter.hunters_prey"
HUNTERS_PREY_COLOSSUS_SLAYER = "colossus_slayer"
HUNTERS_PREY_HORDE_BREAKER = "horde_breaker"
DIVINE_ORDER_CHOICE_KEY = "cleric.divine_order"
DIVINE_ORDER_PROTECTOR = "protector"
DIVINE_ORDER_THAUMATURGE = "thaumaturge"
DRUID_PRIMAL_ORDER_CHOICE_KEY = "druid.primal_order"
DRUID_PRIMAL_ORDER_MAGICIAN = "magician"
DRUID_PRIMAL_ORDER_WARDEN = "warden"
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
GIFT_OF_DEPTHS_RESOURCE = "srd.resource.gift_of_the_depths"
DARK_ONES_OWN_LUCK_RESOURCE = "srd.resource.dark_ones_own_luck"

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
    return barbarian_fast_movement_bonus(character) + monk_unarmored_movement_bonus(character)


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


def monk_slow_fall_damage_reduction(character: Character) -> int:
    monk_level = int(character.class_levels.get("monk", 0))
    if monk_level < 4:
        return 0
    return monk_level * 5


def has_monk_open_hand_feature(character: Character, *, level: int) -> bool:
    return has_monk_feature(character, level=level) and (
        character.subclasses.get("monk") == "open_hand"
    )


def has_paladin_feature(character: Character, *, level: int) -> bool:
    return int(character.class_levels.get("paladin", 0)) >= level


def has_fighter_champion_feature(character: Character, *, level: int) -> bool:
    return (
        int(character.class_levels.get("fighter", 0)) >= level
        and character.subclasses.get("fighter") == "champion"
    )


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

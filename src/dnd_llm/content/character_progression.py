from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from dnd_llm.core.models import Character
from dnd_llm.core.rules.class_features import (
    DARK_ONES_OWN_LUCK_RESOURCE,
    DIVINE_ORDER_CHOICE_KEY,
    DIVINE_ORDER_PROTECTOR,
    DIVINE_ORDER_THAUMATURGE,
    DRUID_CIRCLE_LAND_CHOICE_KEY,
    DRUID_CIRCLE_LAND_TYPES,
    DRUID_PRIMAL_ORDER_CHOICE_KEY,
    DRUID_PRIMAL_ORDER_MAGICIAN,
    DRUID_PRIMAL_ORDER_WARDEN,
    GIFT_OF_DEPTHS_RESOURCE,
    HUNTER_DEFENSIVE_TACTICS_CHOICE_KEY,
    HUNTER_DEFENSIVE_TACTICS_ESCAPE_THE_HORDE,
    HUNTER_DEFENSIVE_TACTICS_MULTIATTACK_DEFENSE,
    HUNTERS_PREY_CHOICE_KEY,
    HUNTERS_PREY_COLOSSUS_SLAYER,
    HUNTERS_PREY_HORDE_BREAKER,
    NATURAL_RECOVERY_CIRCLE_SPELL_RESOURCE,
    NATURAL_RECOVERY_SPELL_SLOTS_RESOURCE,
    NATURES_VEIL_RESOURCE,
    PERSISTENT_RAGE_INITIATIVE_RESTORE_RESOURCE,
    STROKE_OF_LUCK_RESOURCE,
    TIRELESS_RESOURCE,
    UNCANNY_METABOLISM_RESOURCE,
    WARLOCK_AGONIZING_BLAST_CANTRIP_KEY,
    WARLOCK_AGONIZING_BLAST_ELDRITCH_BLAST,
    WARLOCK_ARMOR_OF_SHADOWS_CHOICE_KEY,
    WARLOCK_ARMOR_OF_SHADOWS_SELECTED,
    WARLOCK_ASCENDANT_STEP_CHOICE_KEY,
    WARLOCK_ASCENDANT_STEP_SELECTED,
    WARLOCK_DEVILS_SIGHT_CHOICE_KEY,
    WARLOCK_DEVILS_SIGHT_SELECTED,
    WARLOCK_ELDRITCH_INVOCATION_CHOICE_KEY,
    WARLOCK_ELDRITCH_MIND,
    WARLOCK_ELDRITCH_SMITE_CHOICE_KEY,
    WARLOCK_ELDRITCH_SMITE_SELECTED,
    WARLOCK_ELDRITCH_SPEAR_CANTRIP_KEY,
    WARLOCK_ELDRITCH_SPEAR_ELDRITCH_BLAST,
    WARLOCK_FIENDISH_VIGOR_CHOICE_KEY,
    WARLOCK_FIENDISH_VIGOR_SELECTED,
    WARLOCK_GAZE_OF_TWO_MINDS_CHOICE_KEY,
    WARLOCK_GAZE_OF_TWO_MINDS_SELECTED,
    WARLOCK_GIFT_OF_DEPTHS_CHOICE_KEY,
    WARLOCK_GIFT_OF_DEPTHS_SELECTED,
    WARLOCK_INVESTMENT_OF_CHAIN_MASTER_CHOICE_KEY,
    WARLOCK_INVESTMENT_OF_CHAIN_MASTER_SELECTED,
    WARLOCK_LESSONS_OF_FIRST_ONES_ORIGIN_FEATS,
    WARLOCK_LESSONS_OF_FIRST_ONES_SELECTED,
    WARLOCK_MASK_OF_MANY_FACES_CHOICE_KEY,
    WARLOCK_MASK_OF_MANY_FACES_SELECTED,
    WARLOCK_MASTER_OF_MYRIAD_FORMS_CHOICE_KEY,
    WARLOCK_MASTER_OF_MYRIAD_FORMS_SELECTED,
    WARLOCK_MISTY_VISIONS_CHOICE_KEY,
    WARLOCK_MISTY_VISIONS_SELECTED,
    WARLOCK_ONE_WITH_SHADOWS_CHOICE_KEY,
    WARLOCK_ONE_WITH_SHADOWS_SELECTED,
    WARLOCK_OTHERWORLDLY_LEAP_CHOICE_KEY,
    WARLOCK_OTHERWORLDLY_LEAP_SELECTED,
    WARLOCK_PACT_OF_BLADE_CHOICE_KEY,
    WARLOCK_PACT_OF_BLADE_SELECTED,
    WARLOCK_PACT_OF_CHAIN_CHOICE_KEY,
    WARLOCK_PACT_OF_CHAIN_SELECTED,
    WARLOCK_PACT_OF_TOME_CANTRIP_COUNT,
    WARLOCK_PACT_OF_TOME_CHOICE_KEY,
    WARLOCK_PACT_OF_TOME_RITUAL_COUNT,
    WARLOCK_PACT_OF_TOME_SELECTED,
    WARLOCK_REPELLING_BLAST_CANTRIP_KEY,
    WARLOCK_REPELLING_BLAST_ELDRITCH_BLAST,
    WARLOCK_THIRSTING_BLADE_CHOICE_KEY,
    WARLOCK_THIRSTING_BLADE_SELECTED,
    WHOLENESS_OF_BODY_RESOURCE,
    draconic_resilience_hp_bonus,
    warlock_lessons_of_first_ones_choice_key,
    warlock_lessons_of_first_ones_origin_feats,
    warlock_pact_of_tome_cantrip_choice_key,
    warlock_pact_of_tome_ritual_choice_key,
)
from dnd_llm.core.rules.spell_slots import spell_slot_maxima_for_class_levels


def _choice_key(raw: str) -> str:
    return re.sub(r"[\s_'’().-]+", "", raw.casefold())


CLASS_ALIASES = {
    "barbarian": "barbarian",
    "bard": "bard",
    "cleric": "cleric",
    "druid": "druid",
    "fighter": "fighter",
    "monk": "monk",
    "paladin": "paladin",
    "ranger": "ranger",
    "rogue": "rogue",
    "sorcerer": "sorcerer",
    "warlock": "warlock",
    "wizard": "wizard",
    "战士": "fighter",
    "牧师": "cleric",
    "游荡者": "rogue",
    "盗贼": "rogue",
    "法师": "wizard",
    "巫师": "wizard",
    "野蛮人": "barbarian",
    "吟游诗人": "bard",
    "诗人": "bard",
    "德鲁伊": "druid",
    "武僧": "monk",
    "圣武士": "paladin",
    "圣骑士": "paladin",
    "游侠": "ranger",
    "术士": "warlock",
    "邪术师": "warlock",
    "契术师": "warlock",
    "术法师": "sorcerer",
}

CLASS_HIT_DICE = {
    "barbarian": "d12",
    "bard": "d8",
    "cleric": "d8",
    "druid": "d8",
    "fighter": "d10",
    "monk": "d8",
    "paladin": "d10",
    "ranger": "d10",
    "rogue": "d8",
    "sorcerer": "d6",
    "warlock": "d8",
    "wizard": "d6",
}

CLASS_SAVES = {
    "barbarian": ["str", "con"],
    "bard": ["dex", "cha"],
    "cleric": ["wis", "cha"],
    "druid": ["int", "wis"],
    "fighter": ["str", "con"],
    "monk": ["str", "dex"],
    "paladin": ["wis", "cha"],
    "ranger": ["str", "dex"],
    "rogue": ["dex", "int"],
    "sorcerer": ["con", "cha"],
    "warlock": ["wis", "cha"],
    "wizard": ["int", "wis"],
}

CLASS_TOOL_PROFICIENCIES = {
    "rogue": ["thieves_tools"],
}

CLASS_LANGUAGES = {
    "druid": ["druidic"],
    "rogue": ["thieves_cant"],
}

CLASS_BASE_ACTIONS = {
    "bard": ["srd.cure_wounds"],
    "cleric": ["srd.cure_wounds"],
    "druid": ["srd.cure_wounds"],
    "fighter": ["srd.longsword_attack"],
    "monk": ["srd.shortsword_attack"],
    "wizard": ["srd.fire_bolt", "srd.ritual_adept", "srd.arcane_recovery"],
    "warlock": ["srd.eldritch_blast"],
    "paladin": ["srd.shortsword_attack"],
    "ranger": ["srd.shortsword_attack"],
    "rogue": ["srd.shortsword_attack", "srd.hide", "srd.sneak_attack"],
    "sorcerer": ["srd.fire_bolt", "srd.innate_sorcery"],
}

CLASS_LEVEL_ACTIONS = {
    "bard": {
        1: ["srd.bardic_inspiration"],
        2: ["srd.bard_expertise", "srd.jack_of_all_trades"],
        5: [
            "srd.font_of_inspiration_restore_bardic_inspiration_slot_1",
            "srd.font_of_inspiration_restore_bardic_inspiration_slot_2",
            "srd.font_of_inspiration_restore_bardic_inspiration_slot_3",
        ],
        7: ["srd.countercharm"],
        9: ["srd.bard_expertise"],
    },
    "cleric": {
        1: ["srd.divine_order"],
        2: [
            "srd.divine_spark_heal",
            "srd.divine_spark_radiant",
            "srd.divine_spark_necrotic",
            "srd.turn_undead",
        ],
    },
    "druid": {
        1: ["srd.druidic", "srd.primal_order", "srd.speak_with_animals"],
        2: [
            "srd.wild_shape_wolf",
            "srd.wild_shape_giant_rat",
            "srd.wild_companion_wild_shape",
            "srd.wild_companion_spell_slot",
        ],
        5: [
            "srd.wild_resurgence_restore_wild_shape_slot_1",
            "srd.wild_resurgence_restore_wild_shape_slot_2",
            "srd.wild_resurgence_restore_wild_shape_slot_3",
            "srd.wild_resurgence_create_spell_slot",
        ],
    },
    "fighter": {
        1: ["srd.second_wind"],
        2: ["srd.action_surge", "srd.tactical_mind"],
        5: ["srd.extra_attack"],
        9: ["srd.indomitable", "srd.tactical_master"],
        11: ["srd.two_extra_attacks"],
        13: ["srd.studied_attacks"],
        20: ["srd.three_extra_attacks"],
    },
    "barbarian": {
        1: ["srd.rage", "srd.barbarian_unarmored_defense"],
        2: ["srd.danger_sense", "srd.reckless_attack"],
        3: ["srd.primal_knowledge"],
        5: ["srd.extra_attack"],
        7: ["srd.feral_instinct", "srd.instinctive_pounce"],
        9: ["srd.brutal_strike"],
        11: ["srd.relentless_rage"],
        13: ["srd.improved_brutal_strike"],
        15: ["srd.persistent_rage"],
        18: ["srd.indomitable_might"],
        20: ["srd.primal_champion"],
    },
    "monk": {
        1: [
            "srd.monk_unarmed_strike",
            "srd.martial_arts_bonus_unarmed_strike",
            "srd.monk_unarmored_defense",
        ],
        2: [
            "srd.uncanny_metabolism",
            "srd.monk_unarmored_movement",
            "srd.flurry_of_blows",
            "srd.patient_defense",
            "srd.patient_defense_focus",
            "srd.step_of_the_wind",
            "srd.step_of_the_wind_focus",
        ],
        3: ["srd.deflect_attacks"],
        4: ["srd.slow_fall"],
        5: ["srd.stunning_strike", "srd.extra_attack"],
        6: ["srd.empowered_strikes"],
        7: ["srd.evasion"],
        9: ["srd.acrobatic_movement"],
        10: ["srd.heightened_focus", "srd.self_restoration"],
        13: ["srd.deflect_energy"],
        14: ["srd.disciplined_survivor"],
        15: ["srd.perfect_focus"],
        18: ["srd.superior_defense"],
    },
    "paladin": {
        1: ["srd.lay_on_hands", "srd.lay_on_hands_remove_poisoned", "srd.cure_wounds"],
        2: ["srd.divine_smite", "srd.paladins_smite_divine_smite"],
        3: ["srd.divine_sense"],
        5: [
            "srd.extra_attack",
            "srd.faithful_steed",
            "srd.find_steed",
            "srd.faithful_steed_find_steed",
        ],
        6: ["srd.aura_of_protection"],
        10: ["srd.aura_of_courage"],
        11: ["srd.radiant_strikes"],
        14: ["srd.restoring_touch"],
    },
    "ranger": {
        1: ["srd.favored_enemy_hunters_mark"],
        2: ["srd.cure_wounds", "srd.deft_explorer"],
        5: ["srd.extra_attack"],
        6: ["srd.roving"],
        9: ["srd.ranger_expertise"],
        10: ["srd.tireless"],
        13: ["srd.relentless_hunter"],
        14: ["srd.natures_veil"],
        17: ["srd.precise_hunter"],
        18: ["srd.feral_senses"],
        20: ["srd.foe_slayer"],
    },
    "rogue": {
        1: ["srd.rogue_expertise", "srd.thieves_cant"],
        2: [
            "srd.cunning_action_dash",
            "srd.cunning_action_disengage",
            "srd.cunning_action_hide",
        ],
        3: ["srd.steady_aim"],
        5: ["srd.cunning_strike", "srd.uncanny_dodge"],
        6: ["srd.rogue_expertise"],
        7: ["srd.evasion", "srd.reliable_talent"],
        11: ["srd.improved_cunning_strike"],
        15: ["srd.slippery_mind"],
        18: ["srd.elusive"],
        20: ["srd.stroke_of_luck"],
    },
    "sorcerer": {
        2: ["srd.font_of_magic_convert_slot_1", "srd.font_of_magic_create_slot_1"],
        3: ["srd.font_of_magic_convert_slot_2", "srd.font_of_magic_create_slot_2"],
        5: [
            "srd.font_of_magic_convert_slot_3",
            "srd.font_of_magic_create_slot_3",
            "srd.sorcerous_restoration",
        ],
    },
    "warlock": {1: ["srd.eldritch_invocations"], 2: ["srd.magical_cunning"]},
    "wizard": {1: ["srd.ritual_adept"], 2: ["srd.scholar"], 5: ["srd.memorize_spell"]},
}

SUBCLASS_ALIASES = {
    "barbarian": {"berserker": "berserker"},
    "bard": {"lore": "lore"},
    "cleric": {"life": "life"},
    "druid": {"land": "land"},
    "fighter": {"champion": "champion", "冠军": "champion"},
    "monk": {"openhand": "open_hand", "open_hand": "open_hand"},
    "paladin": {"devotion": "devotion"},
    "ranger": {"hunter": "hunter"},
    "rogue": {"thief": "thief"},
    "sorcerer": {"draconic": "draconic"},
    "warlock": {"fiend": "fiend"},
    "wizard": {"evocation": "evocation", "evoker": "evocation"},
}

SUBCLASS_LEVELS = {
    class_name: {subclass_id: 3 for subclass_id in aliases.values()}
    for class_name, aliases in SUBCLASS_ALIASES.items()
}

SUBCLASS_ACTIONS = {
    "barbarian": {
        "berserker": {3: ["srd.frenzy"]},
    },
    "bard": {
        "lore": {3: ["srd.cutting_words"]},
    },
    "cleric": {
        "life": {3: ["srd.disciple_of_life", "srd.preserve_life"]},
    },
    "druid": {
        "land": {
            3: ["srd.lands_aid"],
            6: ["srd.natural_recovery"],
            10: ["srd.natures_ward"],
            14: ["srd.natures_sanctuary", "srd.natures_sanctuary_move"],
        },
    },
    "fighter": {
        "champion": {
            3: ["srd.improved_critical", "srd.remarkable_athlete"],
            7: ["srd.additional_fighting_style"],
            10: ["srd.heroic_warrior"],
            15: ["srd.superior_critical"],
            18: ["srd.survivor"],
        },
    },
    "monk": {
        "open_hand": {
            3: ["srd.open_hand_technique"],
            6: ["srd.wholeness_of_body"],
            11: ["srd.fleet_step"],
            17: ["srd.quivering_palm", "srd.quivering_palm_release"],
        },
    },
    "paladin": {
        "devotion": {3: ["srd.sacred_weapon"]},
    },
    "ranger": {
        "hunter": {
            3: ["srd.hunters_lore"],
            7: ["srd.defensive_tactics"],
            11: ["srd.superior_hunters_prey"],
            15: ["srd.superior_hunters_defense"],
        },
    },
    "rogue": {
        "thief": {
            3: [
                "srd.fast_hands_sleight_of_hand",
                "srd.fast_hands_utilize",
                "srd.fast_hands_magic_item",
                "srd.second_story_work",
            ],
            9: ["srd.supreme_sneak"],
            17: ["srd.thiefs_reflexes"],
        },
    },
    "sorcerer": {
        "draconic": {3: ["srd.draconic_resilience"]},
    },
    "warlock": {
        "fiend": {3: ["srd.dark_ones_blessing"], 6: ["srd.dark_ones_own_luck"]},
    },
    "wizard": {
        "evocation": {3: ["srd.potent_cantrip"]},
    },
}

COMMON_FEAT_LEVELS = (4, 8, 12, 16, 19)
EXTRA_FEAT_LEVELS = {
    "fighter": (6, 14),
    "rogue": (10,),
}

FEAT_ALIASES = {
    "tough": "tough",
    "强韧": "tough",
    "坚韧": "tough",
    "skilled": "skilled",
    "熟练": "skilled",
    "alert": "alert",
    "警觉": "alert",
}

FEAT_IDS = {"tough", "skilled", "alert"}
REPEATABLE_FEATS = {"skilled"}
HUNTERS_PREY_CHOICES = {HUNTERS_PREY_COLOSSUS_SLAYER, HUNTERS_PREY_HORDE_BREAKER}
HUNTERS_PREY_ALIASES = {
    "colossusslayer": HUNTERS_PREY_COLOSSUS_SLAYER,
    "巨像杀手": HUNTERS_PREY_COLOSSUS_SLAYER,
    "hordebreaker": HUNTERS_PREY_HORDE_BREAKER,
    "破群者": HUNTERS_PREY_HORDE_BREAKER,
}
HUNTER_DEFENSIVE_TACTICS_CHOICES = {
    HUNTER_DEFENSIVE_TACTICS_ESCAPE_THE_HORDE,
    HUNTER_DEFENSIVE_TACTICS_MULTIATTACK_DEFENSE,
}
HUNTER_DEFENSIVE_TACTICS_ALIASES = {
    "escapethehorde": HUNTER_DEFENSIVE_TACTICS_ESCAPE_THE_HORDE,
    "逃离部落": HUNTER_DEFENSIVE_TACTICS_ESCAPE_THE_HORDE,
    "逃脱群敌": HUNTER_DEFENSIVE_TACTICS_ESCAPE_THE_HORDE,
    "避开群敌": HUNTER_DEFENSIVE_TACTICS_ESCAPE_THE_HORDE,
    "multiattackdefense": HUNTER_DEFENSIVE_TACTICS_MULTIATTACK_DEFENSE,
    "多重攻击防御": HUNTER_DEFENSIVE_TACTICS_MULTIATTACK_DEFENSE,
    "多攻防御": HUNTER_DEFENSIVE_TACTICS_MULTIATTACK_DEFENSE,
}
DIVINE_ORDER_CHOICES = {DIVINE_ORDER_PROTECTOR, DIVINE_ORDER_THAUMATURGE}
DIVINE_ORDER_ALIASES = {
    "protector": DIVINE_ORDER_PROTECTOR,
    "护卫": DIVINE_ORDER_PROTECTOR,
    "守护者": DIVINE_ORDER_PROTECTOR,
    "守护": DIVINE_ORDER_PROTECTOR,
    "thaumaturge": DIVINE_ORDER_THAUMATURGE,
    "奇术师": DIVINE_ORDER_THAUMATURGE,
    "神术师": DIVINE_ORDER_THAUMATURGE,
    "神奇术士": DIVINE_ORDER_THAUMATURGE,
}
DRUID_PRIMAL_ORDER_CHOICES = {DRUID_PRIMAL_ORDER_MAGICIAN, DRUID_PRIMAL_ORDER_WARDEN}
DRUID_PRIMAL_ORDER_ALIASES = {
    "magician": DRUID_PRIMAL_ORDER_MAGICIAN,
    "自然术士": DRUID_PRIMAL_ORDER_MAGICIAN,
    "魔法师": DRUID_PRIMAL_ORDER_MAGICIAN,
    "法术师": DRUID_PRIMAL_ORDER_MAGICIAN,
    "warden": DRUID_PRIMAL_ORDER_WARDEN,
    "守望者": DRUID_PRIMAL_ORDER_WARDEN,
    "守卫": DRUID_PRIMAL_ORDER_WARDEN,
    "守护者": DRUID_PRIMAL_ORDER_WARDEN,
}
DRUID_CIRCLE_LAND_ALIASES = {
    "arid": "arid",
    "dry": "arid",
    "desert": "arid",
    "沙漠": "arid",
    "干旱": "arid",
    "polar": "polar",
    "arctic": "polar",
    "寒地": "polar",
    "极地": "polar",
    "temperate": "temperate",
    "温带": "temperate",
    "tropical": "tropical",
    "热带": "tropical",
}
WARLOCK_ELDRITCH_INVOCATION_CHOICES = {WARLOCK_ELDRITCH_MIND}
WARLOCK_ELDRITCH_INVOCATION_ALIASES = {
    "eldritchmind": WARLOCK_ELDRITCH_MIND,
    "魔能心智": WARLOCK_ELDRITCH_MIND,
    "异界心智": WARLOCK_ELDRITCH_MIND,
    "专注优势": WARLOCK_ELDRITCH_MIND,
}
WARLOCK_DEVILS_SIGHT_ALIASES = {
    "devilssight": WARLOCK_DEVILS_SIGHT_SELECTED,
    "devilsight": WARLOCK_DEVILS_SIGHT_SELECTED,
    "魔鬼视界": WARLOCK_DEVILS_SIGHT_SELECTED,
    "魔鬼视觉": WARLOCK_DEVILS_SIGHT_SELECTED,
    "恶魔视界": WARLOCK_DEVILS_SIGHT_SELECTED,
}
WARLOCK_AGONIZING_BLAST_CANTRIP_ALIASES = {
    "eldritchblast": WARLOCK_AGONIZING_BLAST_ELDRITCH_BLAST,
    "魔能爆": WARLOCK_AGONIZING_BLAST_ELDRITCH_BLAST,
    "邪能冲击": WARLOCK_AGONIZING_BLAST_ELDRITCH_BLAST,
}
WARLOCK_ELDRITCH_SPEAR_CANTRIP_ALIASES = {
    "eldritchblast": WARLOCK_ELDRITCH_SPEAR_ELDRITCH_BLAST,
    "魔能爆": WARLOCK_ELDRITCH_SPEAR_ELDRITCH_BLAST,
    "邪能冲击": WARLOCK_ELDRITCH_SPEAR_ELDRITCH_BLAST,
}
WARLOCK_REPELLING_BLAST_CANTRIP_ALIASES = {
    "eldritchblast": WARLOCK_REPELLING_BLAST_ELDRITCH_BLAST,
    "魔能爆": WARLOCK_REPELLING_BLAST_ELDRITCH_BLAST,
    "邪能冲击": WARLOCK_REPELLING_BLAST_ELDRITCH_BLAST,
}
WARLOCK_ASCENDANT_STEP_ALIASES = {
    "ascendantstep": WARLOCK_ASCENDANT_STEP_SELECTED,
    "升腾步伐": WARLOCK_ASCENDANT_STEP_SELECTED,
    "升阶步伐": WARLOCK_ASCENDANT_STEP_SELECTED,
    "飞升步伐": WARLOCK_ASCENDANT_STEP_SELECTED,
}
WARLOCK_ARMOR_OF_SHADOWS_ALIASES = {
    "armorofshadows": WARLOCK_ARMOR_OF_SHADOWS_SELECTED,
    "影之护甲": WARLOCK_ARMOR_OF_SHADOWS_SELECTED,
    "阴影护甲": WARLOCK_ARMOR_OF_SHADOWS_SELECTED,
    "暗影护甲": WARLOCK_ARMOR_OF_SHADOWS_SELECTED,
}
WARLOCK_FIENDISH_VIGOR_ALIASES = {
    "fiendishvigor": WARLOCK_FIENDISH_VIGOR_SELECTED,
    "邪魔活力": WARLOCK_FIENDISH_VIGOR_SELECTED,
    "魔鬼活力": WARLOCK_FIENDISH_VIGOR_SELECTED,
    "恶魔活力": WARLOCK_FIENDISH_VIGOR_SELECTED,
}
WARLOCK_MASK_OF_MANY_FACES_ALIASES = {
    "maskofmanyfaces": WARLOCK_MASK_OF_MANY_FACES_SELECTED,
    "千面面具": WARLOCK_MASK_OF_MANY_FACES_SELECTED,
    "众面假面": WARLOCK_MASK_OF_MANY_FACES_SELECTED,
}
WARLOCK_MISTY_VISIONS_ALIASES = {
    "mistyvisions": WARLOCK_MISTY_VISIONS_SELECTED,
    "迷雾幻象": WARLOCK_MISTY_VISIONS_SELECTED,
    "雾影幻象": WARLOCK_MISTY_VISIONS_SELECTED,
}
WARLOCK_ONE_WITH_SHADOWS_ALIASES = {
    "onewithshadows": WARLOCK_ONE_WITH_SHADOWS_SELECTED,
    "影中合一": WARLOCK_ONE_WITH_SHADOWS_SELECTED,
    "与影合一": WARLOCK_ONE_WITH_SHADOWS_SELECTED,
    "融入阴影": WARLOCK_ONE_WITH_SHADOWS_SELECTED,
}
WARLOCK_OTHERWORLDLY_LEAP_ALIASES = {
    "otherworldlyleap": WARLOCK_OTHERWORLDLY_LEAP_SELECTED,
    "异界跃动": WARLOCK_OTHERWORLDLY_LEAP_SELECTED,
    "异界跳跃": WARLOCK_OTHERWORLDLY_LEAP_SELECTED,
}
WARLOCK_MASTER_OF_MYRIAD_FORMS_ALIASES = {
    "masterofmyriadforms": WARLOCK_MASTER_OF_MYRIAD_FORMS_SELECTED,
    "万形大师": WARLOCK_MASTER_OF_MYRIAD_FORMS_SELECTED,
    "千形大师": WARLOCK_MASTER_OF_MYRIAD_FORMS_SELECTED,
    "百变大师": WARLOCK_MASTER_OF_MYRIAD_FORMS_SELECTED,
}
WARLOCK_GIFT_OF_DEPTHS_ALIASES = {
    "giftofthedepths": WARLOCK_GIFT_OF_DEPTHS_SELECTED,
    "深海馈赠": WARLOCK_GIFT_OF_DEPTHS_SELECTED,
    "深渊馈赠": WARLOCK_GIFT_OF_DEPTHS_SELECTED,
    "深海赠礼": WARLOCK_GIFT_OF_DEPTHS_SELECTED,
}
WARLOCK_GAZE_OF_TWO_MINDS_ALIASES = {
    "gazeoftwominds": WARLOCK_GAZE_OF_TWO_MINDS_SELECTED,
    "双心凝视": WARLOCK_GAZE_OF_TWO_MINDS_SELECTED,
    "双重心灵凝视": WARLOCK_GAZE_OF_TWO_MINDS_SELECTED,
    "双心视界": WARLOCK_GAZE_OF_TWO_MINDS_SELECTED,
}
WARLOCK_INVESTMENT_OF_CHAIN_MASTER_ALIASES = {
    "investmentofthechainmaster": WARLOCK_INVESTMENT_OF_CHAIN_MASTER_SELECTED,
    "锁链大师投资": WARLOCK_INVESTMENT_OF_CHAIN_MASTER_SELECTED,
    "链主投资": WARLOCK_INVESTMENT_OF_CHAIN_MASTER_SELECTED,
    "链契大师投资": WARLOCK_INVESTMENT_OF_CHAIN_MASTER_SELECTED,
}
WARLOCK_LESSONS_OF_FIRST_ONES_ORIGIN_FEAT_ALIASES = {
    "alert": "alert",
    "警觉": "alert",
    "skilled": "skilled",
    "熟练": "skilled",
    "magicinitiate": "magic_initiate",
    "魔法学徒": "magic_initiate",
    "savageattacker": "savage_attacker",
    "凶蛮攻击者": "savage_attacker",
}
WARLOCK_PACT_OF_BLADE_ALIASES = {
    "pactoftheblade": WARLOCK_PACT_OF_BLADE_SELECTED,
    "pactofblade": WARLOCK_PACT_OF_BLADE_SELECTED,
    "刃契": WARLOCK_PACT_OF_BLADE_SELECTED,
    "刀锋契约": WARLOCK_PACT_OF_BLADE_SELECTED,
    "刃之契约": WARLOCK_PACT_OF_BLADE_SELECTED,
}
WARLOCK_PACT_OF_CHAIN_ALIASES = {
    "pactofthechain": WARLOCK_PACT_OF_CHAIN_SELECTED,
    "pactofchain": WARLOCK_PACT_OF_CHAIN_SELECTED,
    "链契": WARLOCK_PACT_OF_CHAIN_SELECTED,
    "锁链契约": WARLOCK_PACT_OF_CHAIN_SELECTED,
    "链之契约": WARLOCK_PACT_OF_CHAIN_SELECTED,
}
WARLOCK_PACT_OF_TOME_ALIASES = {
    "pactofthetome": WARLOCK_PACT_OF_TOME_SELECTED,
    "pactoftome": WARLOCK_PACT_OF_TOME_SELECTED,
    "书契": WARLOCK_PACT_OF_TOME_SELECTED,
    "魔典契约": WARLOCK_PACT_OF_TOME_SELECTED,
    "书之契约": WARLOCK_PACT_OF_TOME_SELECTED,
    "影书契约": WARLOCK_PACT_OF_TOME_SELECTED,
}
WARLOCK_PACT_OF_TOME_CANTRIP_ACTIONS = {
    "srd.spell.acid_splash": "srd.acid_splash",
    "srd.spell.chill_touch": "srd.chill_touch",
    "srd.spell.dancing_lights": "srd.dancing_lights",
    "srd.spell.druidcraft": "srd.druidcraft",
    "srd.spell.eldritch_blast": "srd.eldritch_blast",
    "srd.spell.elementalism": "srd.elementalism",
    "srd.spell.fire_bolt": "srd.fire_bolt",
    "srd.spell.guidance": "srd.guidance",
    "srd.spell.light": "srd.light",
    "srd.spell.mage_hand": "srd.mage_hand",
    "srd.spell.mending": "srd.mending",
    "srd.spell.message": "srd.message",
    "srd.spell.minor_illusion": "srd.minor_illusion",
    "srd.spell.poison_spray": "srd.poison_spray",
    "srd.spell.prestidigitation": "srd.prestidigitation",
    "srd.spell.produce_flame": "srd.produce_flame",
    "srd.spell.ray_of_frost": "srd.ray_of_frost",
    "srd.spell.resistance": "srd.resistance",
    "srd.spell.sacred_flame": "srd.sacred_flame",
    "srd.spell.shillelagh": "srd.shillelagh",
    "srd.spell.shocking_grasp": "srd.shocking_grasp",
    "srd.spell.sorcerous_burst": "srd.sorcerous_burst",
    "srd.spell.spare_the_dying": "srd.spare_the_dying",
    "srd.spell.starry_wisp": "srd.starry_wisp",
    "srd.spell.thaumaturgy": "srd.thaumaturgy",
    "srd.spell.true_strike": "srd.true_strike",
    "srd.spell.vicious_mockery": "srd.vicious_mockery",
}
WARLOCK_PACT_OF_TOME_RITUAL_ACTIONS = {
    "srd.spell.alarm": "srd.alarm",
    "srd.spell.comprehend_languages": "srd.comprehend_languages",
    "srd.spell.detect_magic": "srd.detect_magic",
    "srd.spell.detect_poison_and_disease": "srd.detect_poison_and_disease",
    "srd.spell.find_familiar": "srd.find_familiar",
    "srd.spell.floating_disk": "srd.floating_disk",
    "srd.spell.identify": "srd.identify",
    "srd.spell.illusory_script": "srd.illusory_script",
    "srd.spell.purify_food_and_drink": "srd.purify_food_and_drink",
    "srd.spell.speak_with_animals": "srd.speak_with_animals",
    "srd.spell.unseen_servant": "srd.unseen_servant",
}
WARLOCK_PACT_OF_TOME_CANTRIP_ALIASES = {
    **{_choice_key(spell_id): spell_id for spell_id in WARLOCK_PACT_OF_TOME_CANTRIP_ACTIONS},
    **{
        _choice_key(spell_id.removeprefix("srd.spell.")): spell_id
        for spell_id in WARLOCK_PACT_OF_TOME_CANTRIP_ACTIONS
    },
    "acidsplash": "srd.spell.acid_splash",
    "chilltouch": "srd.spell.chill_touch",
    "dancinglights": "srd.spell.dancing_lights",
    "druidcraft": "srd.spell.druidcraft",
    "eldritchblast": "srd.spell.eldritch_blast",
    "elementalism": "srd.spell.elementalism",
    "firebolt": "srd.spell.fire_bolt",
    "guidance": "srd.spell.guidance",
    "light": "srd.spell.light",
    "magehand": "srd.spell.mage_hand",
    "mending": "srd.spell.mending",
    "message": "srd.spell.message",
    "minorillusion": "srd.spell.minor_illusion",
    "poisonspray": "srd.spell.poison_spray",
    "prestidigitation": "srd.spell.prestidigitation",
    "produceflame": "srd.spell.produce_flame",
    "rayoffrost": "srd.spell.ray_of_frost",
    "resistance": "srd.spell.resistance",
    "sacredflame": "srd.spell.sacred_flame",
    "shillelagh": "srd.spell.shillelagh",
    "shockinggrasp": "srd.spell.shocking_grasp",
    "sorcerousburst": "srd.spell.sorcerous_burst",
    "sparethedying": "srd.spell.spare_the_dying",
    "starrywisp": "srd.spell.starry_wisp",
    "thaumaturgy": "srd.spell.thaumaturgy",
    "truestrike": "srd.spell.true_strike",
    "viciousmockery": "srd.spell.vicious_mockery",
    "魔能爆": "srd.spell.eldritch_blast",
    "火焰箭": "srd.spell.fire_bolt",
    "法师之手": "srd.spell.mage_hand",
    "小幻象": "srd.spell.minor_illusion",
    "圣火术": "srd.spell.sacred_flame",
    "神导术": "srd.spell.guidance",
}
WARLOCK_PACT_OF_TOME_RITUAL_ALIASES = {
    **{_choice_key(spell_id): spell_id for spell_id in WARLOCK_PACT_OF_TOME_RITUAL_ACTIONS},
    **{
        _choice_key(spell_id.removeprefix("srd.spell.")): spell_id
        for spell_id in WARLOCK_PACT_OF_TOME_RITUAL_ACTIONS
    },
    "alarm": "srd.spell.alarm",
    "comprehendlanguages": "srd.spell.comprehend_languages",
    "detectmagic": "srd.spell.detect_magic",
    "detectpoisonanddisease": "srd.spell.detect_poison_and_disease",
    "findfamiliar": "srd.spell.find_familiar",
    "floatingdisk": "srd.spell.floating_disk",
    "identify": "srd.spell.identify",
    "illusoryscript": "srd.spell.illusory_script",
    "purifyfoodanddrink": "srd.spell.purify_food_and_drink",
    "speakwithanimals": "srd.spell.speak_with_animals",
    "unseenservant": "srd.spell.unseen_servant",
    "警报术": "srd.spell.alarm",
    "通晓语言": "srd.spell.comprehend_languages",
    "侦测魔法": "srd.spell.detect_magic",
    "寻找魔宠": "srd.spell.find_familiar",
    "鉴定术": "srd.spell.identify",
    "动物交谈": "srd.spell.speak_with_animals",
    "隐形仆役": "srd.spell.unseen_servant",
}
WARLOCK_THIRSTING_BLADE_ALIASES = {
    "thirstingblade": WARLOCK_THIRSTING_BLADE_SELECTED,
    "渴饮魔刃": WARLOCK_THIRSTING_BLADE_SELECTED,
    "渴血之刃": WARLOCK_THIRSTING_BLADE_SELECTED,
    "饥渴之刃": WARLOCK_THIRSTING_BLADE_SELECTED,
}
WARLOCK_ELDRITCH_SMITE_ALIASES = {
    "eldritchsmite": WARLOCK_ELDRITCH_SMITE_SELECTED,
    "魔能斩击": WARLOCK_ELDRITCH_SMITE_SELECTED,
    "魔能重击": WARLOCK_ELDRITCH_SMITE_SELECTED,
    "异界斩击": WARLOCK_ELDRITCH_SMITE_SELECTED,
}
WIZARD_SCHOLAR_SKILLS = frozenset(
    {"arcana", "history", "investigation", "medicine", "nature", "religion"}
)
FEATURE_CHOICE_ACTIONS = {
    HUNTERS_PREY_CHOICE_KEY: {
        HUNTERS_PREY_COLOSSUS_SLAYER: ["srd.hunters_prey_colossus_slayer"],
        HUNTERS_PREY_HORDE_BREAKER: ["srd.hunters_prey_horde_breaker"],
    },
    HUNTER_DEFENSIVE_TACTICS_CHOICE_KEY: {
        HUNTER_DEFENSIVE_TACTICS_ESCAPE_THE_HORDE: ["srd.escape_the_horde"],
        HUNTER_DEFENSIVE_TACTICS_MULTIATTACK_DEFENSE: ["srd.multiattack_defense"],
    },
    WARLOCK_ELDRITCH_INVOCATION_CHOICE_KEY: {
        WARLOCK_ELDRITCH_MIND: ["srd.eldritch_mind"],
    },
    WARLOCK_DEVILS_SIGHT_CHOICE_KEY: {
        WARLOCK_DEVILS_SIGHT_SELECTED: ["srd.devils_sight"],
    },
    WARLOCK_AGONIZING_BLAST_CANTRIP_KEY: {
        WARLOCK_AGONIZING_BLAST_ELDRITCH_BLAST: ["srd.agonizing_blast"],
    },
    WARLOCK_ELDRITCH_SPEAR_CANTRIP_KEY: {
        WARLOCK_ELDRITCH_SPEAR_ELDRITCH_BLAST: ["srd.eldritch_spear"],
    },
    WARLOCK_REPELLING_BLAST_CANTRIP_KEY: {
        WARLOCK_REPELLING_BLAST_ELDRITCH_BLAST: ["srd.repelling_blast"],
    },
    WARLOCK_ASCENDANT_STEP_CHOICE_KEY: {
        WARLOCK_ASCENDANT_STEP_SELECTED: [
            "srd.ascendant_step",
            "srd.ascendant_step_levitate",
        ],
    },
    WARLOCK_ARMOR_OF_SHADOWS_CHOICE_KEY: {
        WARLOCK_ARMOR_OF_SHADOWS_SELECTED: [
            "srd.armor_of_shadows",
            "srd.armor_of_shadows_mage_armor",
        ],
    },
    WARLOCK_FIENDISH_VIGOR_CHOICE_KEY: {
        WARLOCK_FIENDISH_VIGOR_SELECTED: [
            "srd.fiendish_vigor",
            "srd.fiendish_vigor_false_life",
        ],
    },
    WARLOCK_MASK_OF_MANY_FACES_CHOICE_KEY: {
        WARLOCK_MASK_OF_MANY_FACES_SELECTED: [
            "srd.mask_of_many_faces",
            "srd.mask_of_many_faces_disguise_self",
        ],
    },
    WARLOCK_MISTY_VISIONS_CHOICE_KEY: {
        WARLOCK_MISTY_VISIONS_SELECTED: [
            "srd.misty_visions",
            "srd.misty_visions_silent_image",
        ],
    },
    WARLOCK_ONE_WITH_SHADOWS_CHOICE_KEY: {
        WARLOCK_ONE_WITH_SHADOWS_SELECTED: [
            "srd.one_with_shadows",
            "srd.one_with_shadows_invisibility",
        ],
    },
    WARLOCK_OTHERWORLDLY_LEAP_CHOICE_KEY: {
        WARLOCK_OTHERWORLDLY_LEAP_SELECTED: [
            "srd.otherworldly_leap",
            "srd.otherworldly_leap_jump",
        ],
    },
    WARLOCK_MASTER_OF_MYRIAD_FORMS_CHOICE_KEY: {
        WARLOCK_MASTER_OF_MYRIAD_FORMS_SELECTED: [
            "srd.master_of_myriad_forms",
            "srd.master_of_myriad_forms_alter_self",
        ],
    },
    WARLOCK_GIFT_OF_DEPTHS_CHOICE_KEY: {
        WARLOCK_GIFT_OF_DEPTHS_SELECTED: [
            "srd.gift_of_the_depths",
            "srd.gift_of_the_depths_water_breathing",
        ],
    },
    WARLOCK_GAZE_OF_TWO_MINDS_CHOICE_KEY: {
        WARLOCK_GAZE_OF_TWO_MINDS_SELECTED: [
            "srd.gaze_of_two_minds",
            "srd.gaze_of_two_minds_touch",
        ],
    },
    WARLOCK_INVESTMENT_OF_CHAIN_MASTER_CHOICE_KEY: {
        WARLOCK_INVESTMENT_OF_CHAIN_MASTER_SELECTED: ["srd.investment_of_the_chain_master"],
    },
    WARLOCK_PACT_OF_BLADE_CHOICE_KEY: {
        WARLOCK_PACT_OF_BLADE_SELECTED: [
            "srd.pact_of_the_blade",
            "srd.pact_of_the_blade_weapon",
        ],
    },
    WARLOCK_PACT_OF_CHAIN_CHOICE_KEY: {
        WARLOCK_PACT_OF_CHAIN_SELECTED: [
            "srd.pact_of_the_chain",
            "srd.pact_of_the_chain_find_familiar",
        ],
    },
    WARLOCK_PACT_OF_TOME_CHOICE_KEY: {
        WARLOCK_PACT_OF_TOME_SELECTED: [
            "srd.pact_of_the_tome",
        ],
    },
    WARLOCK_THIRSTING_BLADE_CHOICE_KEY: {
        WARLOCK_THIRSTING_BLADE_SELECTED: ["srd.thirsting_blade"],
    },
    WARLOCK_ELDRITCH_SMITE_CHOICE_KEY: {
        WARLOCK_ELDRITCH_SMITE_SELECTED: ["srd.eldritch_smite"],
    },
}

SRD_SKILL_ALIASES = {
    "acrobatics": ("acrobatics", "杂技"),
    "animal_handling": ("animal handling", "animal_handling", "驯兽", "驯养动物", "动物驯养"),
    "arcana": ("arcana", "奥秘", "奥术"),
    "athletics": ("athletics", "运动"),
    "deception": ("deception", "欺瞒"),
    "history": ("history", "历史"),
    "insight": ("insight", "洞悉"),
    "intimidation": ("intimidation", "威吓"),
    "investigation": ("investigation", "调查"),
    "medicine": ("medicine", "医药", "医疗"),
    "nature": ("nature", "自然"),
    "perception": ("perception", "察觉"),
    "performance": ("performance", "表演"),
    "persuasion": ("persuasion", "游说", "说服"),
    "religion": ("religion", "宗教"),
    "sleight_of_hand": ("sleight of hand", "sleight_of_hand", "巧手"),
    "stealth": ("stealth", "潜行"),
    "survival": ("survival", "生存"),
}

SRD_TOOL_ALIASES = {
    "alchemists_supplies": ("alchemist's supplies", "alchemists supplies", "炼金用品"),
    "brewers_supplies": ("brewer's supplies", "brewers supplies", "酿酒用品"),
    "calligraphers_supplies": ("calligrapher's supplies", "calligraphers supplies", "书法用品"),
    "carpenters_tools": ("carpenter's tools", "carpenters tools", "木匠工具"),
    "cartographers_tools": ("cartographer's tools", "cartographers tools", "制图工具"),
    "cobblers_tools": ("cobbler's tools", "cobblers tools", "鞋匠工具"),
    "cooks_utensils": ("cook's utensils", "cooks utensils", "厨师用具"),
    "glassblowers_tools": ("glassblower's tools", "glassblowers tools", "玻璃匠工具"),
    "jewelers_tools": ("jeweler's tools", "jewelers tools", "珠宝匠工具"),
    "leatherworkers_tools": ("leatherworker's tools", "leatherworkers tools", "皮匠工具"),
    "masons_tools": ("mason's tools", "masons tools", "石匠工具"),
    "painters_supplies": ("painter's supplies", "painters supplies", "画家用品"),
    "potters_tools": ("potter's tools", "potters tools", "陶匠工具"),
    "smiths_tools": ("smith's tools", "smiths tools", "铁匠工具"),
    "tinkers_tools": ("tinker's tools", "tinkers tools", "修补匠工具"),
    "weavers_tools": ("weaver's tools", "weavers tools", "织工工具"),
    "woodcarvers_tools": ("woodcarver's tools", "woodcarvers tools", "木雕工具"),
    "disguise_kit": ("disguise kit", "易容工具"),
    "forgery_kit": ("forgery kit", "伪造工具"),
    "dice": ("dice", "骰子"),
    "dragonchess": ("dragonchess", "龙棋"),
    "playing_cards": ("playing cards", "纸牌"),
    "three_dragon_ante": ("three-dragon ante", "three dragon ante", "三龙牌"),
    "herbalism_kit": ("herbalism kit", "草药工具"),
    "bagpipes": ("bagpipes", "风笛"),
    "drum": ("drum", "鼓"),
    "dulcimer": ("dulcimer", "扬琴"),
    "flute": ("flute", "长笛"),
    "horn": ("horn", "号角"),
    "lute": ("lute", "鲁特琴"),
    "lyre": ("lyre", "里拉琴"),
    "pan_flute": ("pan flute", "排箫"),
    "shawm": ("shawm", "肖姆管"),
    "viol": ("viol", "维奥尔琴"),
    "navigators_tools": ("navigator's tools", "navigators tools", "导航工具"),
    "poisoners_kit": ("poisoner's kit", "poisoners kit", "制毒工具"),
    "thieves_tools": ("thieves' tools", "thieves tools", "盗贼工具", "开锁工具"),
}

_SKILL_LOOKUP = {
    _choice_key(alias): skill_id
    for skill_id, aliases in SRD_SKILL_ALIASES.items()
    for alias in aliases
}
_TOOL_LOOKUP = {
    _choice_key(alias): tool_id
    for tool_id, aliases in SRD_TOOL_ALIASES.items()
    for alias in aliases
}


@dataclass(frozen=True)
class ProgressionResult:
    errors: list[str]
    hp_delta: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors


def normalize_class_name(raw: str) -> str | None:
    return CLASS_ALIASES.get(raw.strip().casefold())


def normalize_subclass_name(raw: str, class_name: str | None = None) -> tuple[str, str] | None:
    key = _choice_key(raw)
    if class_name is not None:
        subclass_id = SUBCLASS_ALIASES.get(class_name, {}).get(key)
        if subclass_id is None:
            return None
        return class_name, subclass_id
    matches = [
        (candidate_class, subclass_id)
        for candidate_class, aliases in SUBCLASS_ALIASES.items()
        for alias, subclass_id in aliases.items()
        if alias == key
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def normalize_feat_name(raw: str) -> str | None:
    return FEAT_ALIASES.get(raw.strip().casefold())


def normalize_hunters_prey_choice(raw: str) -> str | None:
    return HUNTERS_PREY_ALIASES.get(_choice_key(raw))


def normalize_hunter_defensive_tactics_choice(raw: str) -> str | None:
    return HUNTER_DEFENSIVE_TACTICS_ALIASES.get(_choice_key(raw))


def normalize_divine_order_choice(raw: str) -> str | None:
    return DIVINE_ORDER_ALIASES.get(_choice_key(raw))


def normalize_druid_primal_order_choice(raw: str) -> str | None:
    return DRUID_PRIMAL_ORDER_ALIASES.get(_choice_key(raw))


def normalize_druid_circle_land_choice(raw: str) -> str | None:
    return DRUID_CIRCLE_LAND_ALIASES.get(_choice_key(raw))


def normalize_warlock_eldritch_invocation_choice(raw: str) -> str | None:
    return WARLOCK_ELDRITCH_INVOCATION_ALIASES.get(_choice_key(raw))


def normalize_warlock_devils_sight_choice(raw: str) -> str | None:
    return WARLOCK_DEVILS_SIGHT_ALIASES.get(_choice_key(raw))


def normalize_warlock_agonizing_blast_cantrip(raw: str) -> str | None:
    return WARLOCK_AGONIZING_BLAST_CANTRIP_ALIASES.get(_choice_key(raw))


def normalize_warlock_eldritch_spear_cantrip(raw: str) -> str | None:
    return WARLOCK_ELDRITCH_SPEAR_CANTRIP_ALIASES.get(_choice_key(raw))


def normalize_warlock_repelling_blast_cantrip(raw: str) -> str | None:
    return WARLOCK_REPELLING_BLAST_CANTRIP_ALIASES.get(_choice_key(raw))


def normalize_warlock_ascendant_step_choice(raw: str) -> str | None:
    return WARLOCK_ASCENDANT_STEP_ALIASES.get(_choice_key(raw))


def normalize_warlock_armor_of_shadows_choice(raw: str) -> str | None:
    return WARLOCK_ARMOR_OF_SHADOWS_ALIASES.get(_choice_key(raw))


def normalize_warlock_fiendish_vigor_choice(raw: str) -> str | None:
    return WARLOCK_FIENDISH_VIGOR_ALIASES.get(_choice_key(raw))


def normalize_warlock_mask_of_many_faces_choice(raw: str) -> str | None:
    return WARLOCK_MASK_OF_MANY_FACES_ALIASES.get(_choice_key(raw))


def normalize_warlock_misty_visions_choice(raw: str) -> str | None:
    return WARLOCK_MISTY_VISIONS_ALIASES.get(_choice_key(raw))


def normalize_warlock_one_with_shadows_choice(raw: str) -> str | None:
    return WARLOCK_ONE_WITH_SHADOWS_ALIASES.get(_choice_key(raw))


def normalize_warlock_otherworldly_leap_choice(raw: str) -> str | None:
    return WARLOCK_OTHERWORLDLY_LEAP_ALIASES.get(_choice_key(raw))


def normalize_warlock_master_of_myriad_forms_choice(raw: str) -> str | None:
    return WARLOCK_MASTER_OF_MYRIAD_FORMS_ALIASES.get(_choice_key(raw))


def normalize_warlock_gift_of_depths_choice(raw: str) -> str | None:
    return WARLOCK_GIFT_OF_DEPTHS_ALIASES.get(_choice_key(raw))


def normalize_warlock_gaze_of_two_minds_choice(raw: str) -> str | None:
    return WARLOCK_GAZE_OF_TWO_MINDS_ALIASES.get(_choice_key(raw))


def normalize_warlock_investment_of_chain_master_choice(raw: str) -> str | None:
    return WARLOCK_INVESTMENT_OF_CHAIN_MASTER_ALIASES.get(_choice_key(raw))


def normalize_warlock_lessons_origin_feat(raw: str) -> str | None:
    return WARLOCK_LESSONS_OF_FIRST_ONES_ORIGIN_FEAT_ALIASES.get(_choice_key(raw))


def normalize_warlock_pact_of_blade_choice(raw: str) -> str | None:
    return WARLOCK_PACT_OF_BLADE_ALIASES.get(_choice_key(raw))


def normalize_warlock_pact_of_chain_choice(raw: str) -> str | None:
    return WARLOCK_PACT_OF_CHAIN_ALIASES.get(_choice_key(raw))


def normalize_warlock_pact_of_tome_choice(raw: str) -> str | None:
    return WARLOCK_PACT_OF_TOME_ALIASES.get(_choice_key(raw))


def normalize_warlock_pact_of_tome_cantrip(raw: str) -> str | None:
    return WARLOCK_PACT_OF_TOME_CANTRIP_ALIASES.get(_choice_key(raw))


def normalize_warlock_pact_of_tome_ritual(raw: str) -> str | None:
    return WARLOCK_PACT_OF_TOME_RITUAL_ALIASES.get(_choice_key(raw))


def normalize_warlock_thirsting_blade_choice(raw: str) -> str | None:
    return WARLOCK_THIRSTING_BLADE_ALIASES.get(_choice_key(raw))


def normalize_warlock_eldritch_smite_choice(raw: str) -> str | None:
    return WARLOCK_ELDRITCH_SMITE_ALIASES.get(_choice_key(raw))


def replace_class(character: Character, class_name: str, *, level: int = 1) -> ProgressionResult:
    errors = _validate_class_level(class_name, level)
    if errors:
        return ProgressionResult(errors)
    character.class_levels = {class_name: level}
    character.subclasses = {}
    character.feature_choices = {}
    character.saving_throw_proficiencies = list(CLASS_SAVES[class_name])
    character.tool_proficiencies = list(CLASS_TOOL_PROFICIENCIES.get(class_name, []))
    character.feats = []
    character.known_spells = []
    character.prepared_spells = []
    character.hp_max = _fixed_hp_for_single_class(character, class_name, level)
    character.hp_current = character.hp_max
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[], hp_delta=0)


def set_multiclass_level(
    character: Character,
    class_name: str,
    *,
    level: int = 1,
) -> ProgressionResult:
    errors = _validate_class_level(class_name, level)
    if errors:
        return ProgressionResult(errors)
    previous_level = int(character.class_levels.get(class_name, 0))
    if level < previous_level:
        return ProgressionResult([f"{class_name}: 多职业等级不能降低"])
    projected_total = total_level(character) - previous_level + level
    if projected_total > 20:
        return ProgressionResult(["角色总等级不能超过 SRD 角色等级上限 20"])
    previous_subclass_hp_bonus = _subclass_hp_bonus(character)
    previous_con_modifier = _effective_con_modifier_for_levels(
        character,
        character.class_levels,
    )
    previous_total_level = total_level(character)
    character.class_levels[class_name] = level
    _append_fixed_class_tool_proficiencies(character, class_name)
    delta = level - previous_level
    hp_delta = _fixed_hp_gain(character, class_name) * delta if delta > 0 else 0
    new_con_modifier = _effective_con_modifier_for_levels(character, character.class_levels)
    if new_con_modifier != previous_con_modifier:
        hp_delta += (new_con_modifier - previous_con_modifier) * previous_total_level
    subclass_hp_delta = _subclass_hp_bonus(character) - previous_subclass_hp_bonus
    hp_delta += subclass_hp_delta
    if hp_delta:
        character.hp_max += hp_delta
        character.hp_current += hp_delta
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[], hp_delta=hp_delta)


def set_subclass(
    character: Character,
    class_name: str,
    subclass_id: str,
) -> ProgressionResult:
    if class_name not in CLASS_HIT_DICE:
        return ProgressionResult([f"不支持的 SRD 基础职业：{class_name}"])
    subclass_levels = SUBCLASS_LEVELS.get(class_name, {})
    required_level = subclass_levels.get(subclass_id)
    if required_level is None:
        return ProgressionResult([f"{class_name}: 不支持的 SRD 子职：{subclass_id}"])
    class_level = int(character.class_levels.get(class_name, 0))
    if class_level < required_level:
        return ProgressionResult([f"{class_name}: 子职需要职业等级至少 {required_level}"])
    previous_hp_bonus = _subclass_hp_bonus(character)
    character.subclasses[class_name] = subclass_id
    _sync_feature_choices(character)
    hp_delta = _subclass_hp_bonus(character) - previous_hp_bonus
    if hp_delta:
        character.hp_max += hp_delta
        character.hp_current += hp_delta
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[], hp_delta=hp_delta)


def set_hunters_prey_choice(character: Character, choice: str) -> ProgressionResult:
    normalized = normalize_hunters_prey_choice(choice)
    if normalized is None:
        return ProgressionResult([f"Hunter's Prey 不支持的 SRD 选项：{choice}"])
    if (
        character.subclasses.get("ranger") != "hunter"
        or int(character.class_levels.get("ranger", 0)) < 3
    ):
        return ProgressionResult(["Hunter's Prey 选项需要 Ranger/Hunter 3"])
    choices = dict(getattr(character, "feature_choices", {}))
    choices[HUNTERS_PREY_CHOICE_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def set_hunter_defensive_tactics_choice(character: Character, choice: str) -> ProgressionResult:
    normalized = normalize_hunter_defensive_tactics_choice(choice)
    if normalized is None:
        return ProgressionResult([f"Defensive Tactics 不支持的 SRD 选项：{choice}"])
    if (
        character.subclasses.get("ranger") != "hunter"
        or int(character.class_levels.get("ranger", 0)) < 7
    ):
        return ProgressionResult(["Defensive Tactics 选项需要 Ranger/Hunter 7"])
    choices = dict(getattr(character, "feature_choices", {}))
    choices[HUNTER_DEFENSIVE_TACTICS_CHOICE_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def set_divine_order_choice(character: Character, choice: str) -> ProgressionResult:
    normalized = normalize_divine_order_choice(choice)
    if normalized is None:
        return ProgressionResult([f"Divine Order 不支持的 SRD 选项：{choice}"])
    if int(character.class_levels.get("cleric", 0)) < 1:
        return ProgressionResult(["Divine Order 选项需要 Cleric 1"])
    choices = dict(getattr(character, "feature_choices", {}))
    choices[DIVINE_ORDER_CHOICE_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def set_druid_primal_order_choice(character: Character, choice: str) -> ProgressionResult:
    normalized = normalize_druid_primal_order_choice(choice)
    if normalized is None:
        return ProgressionResult([f"Primal Order 不支持的 SRD 选项：{choice}"])
    if int(character.class_levels.get("druid", 0)) < 1:
        return ProgressionResult(["Primal Order 选项需要 Druid 1"])
    choices = dict(getattr(character, "feature_choices", {}))
    choices[DRUID_PRIMAL_ORDER_CHOICE_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def set_druid_circle_land_choice(character: Character, choice: str) -> ProgressionResult:
    normalized = normalize_druid_circle_land_choice(choice)
    if normalized is None:
        return ProgressionResult([f"Circle of the Land 不支持的 SRD 地形：{choice}"])
    if (
        character.subclasses.get("druid") != "land"
        or int(character.class_levels.get("druid", 0)) < 3
    ):
        return ProgressionResult(["Circle of the Land 地形选择需要 Druid/Land 3"])
    choices = dict(getattr(character, "feature_choices", {}))
    choices[DRUID_CIRCLE_LAND_CHOICE_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def set_warlock_eldritch_invocation_choice(
    character: Character,
    choice: str,
) -> ProgressionResult:
    normalized = normalize_warlock_eldritch_invocation_choice(choice)
    if normalized is None:
        return ProgressionResult([f"Eldritch Invocation 不支持的 SRD 选项：{choice}"])
    if int(character.class_levels.get("warlock", 0)) < 1:
        return ProgressionResult(["Eldritch Invocation 选项需要 Warlock 1"])
    choices = dict(getattr(character, "feature_choices", {}))
    choices[WARLOCK_ELDRITCH_INVOCATION_CHOICE_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def set_warlock_devils_sight_choice(
    character: Character,
    choice: str,
) -> ProgressionResult:
    normalized = normalize_warlock_devils_sight_choice(choice)
    if normalized is None:
        return ProgressionResult([f"Devil's Sight 不支持的 SRD 选项：{choice}"])
    if int(character.class_levels.get("warlock", 0)) < 2:
        return ProgressionResult(["Devil's Sight 需要 Warlock 2"])
    choices = dict(getattr(character, "feature_choices", {}))
    choices[WARLOCK_DEVILS_SIGHT_CHOICE_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def set_warlock_agonizing_blast_choice(
    character: Character,
    cantrip: str,
) -> ProgressionResult:
    normalized = normalize_warlock_agonizing_blast_cantrip(cantrip)
    if normalized is None:
        return ProgressionResult([f"Agonizing Blast 不支持的 SRD 戏法选择：{cantrip}"])
    if int(character.class_levels.get("warlock", 0)) < 2:
        return ProgressionResult(["Agonizing Blast 需要 Warlock 2"])
    if normalized == WARLOCK_AGONIZING_BLAST_ELDRITCH_BLAST and "srd.eldritch_blast" not in set(
        character.actions
    ):
        return ProgressionResult(["Agonizing Blast 需要已知 Eldritch Blast"])
    choices = dict(getattr(character, "feature_choices", {}))
    choices[WARLOCK_AGONIZING_BLAST_CANTRIP_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def set_warlock_eldritch_spear_choice(
    character: Character,
    cantrip: str,
) -> ProgressionResult:
    normalized = normalize_warlock_eldritch_spear_cantrip(cantrip)
    if normalized is None:
        return ProgressionResult([f"Eldritch Spear 不支持的 SRD 戏法选择：{cantrip}"])
    if int(character.class_levels.get("warlock", 0)) < 2:
        return ProgressionResult(["Eldritch Spear 需要 Warlock 2"])
    if normalized == WARLOCK_ELDRITCH_SPEAR_ELDRITCH_BLAST and "srd.eldritch_blast" not in set(
        character.actions
    ):
        return ProgressionResult(["Eldritch Spear 需要已知 Eldritch Blast"])
    choices = dict(getattr(character, "feature_choices", {}))
    choices[WARLOCK_ELDRITCH_SPEAR_CANTRIP_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def set_warlock_repelling_blast_choice(
    character: Character,
    cantrip: str,
) -> ProgressionResult:
    normalized = normalize_warlock_repelling_blast_cantrip(cantrip)
    if normalized is None:
        return ProgressionResult([f"Repelling Blast 不支持的 SRD 戏法选择：{cantrip}"])
    if int(character.class_levels.get("warlock", 0)) < 2:
        return ProgressionResult(["Repelling Blast 需要 Warlock 2"])
    if normalized == WARLOCK_REPELLING_BLAST_ELDRITCH_BLAST and "srd.eldritch_blast" not in set(
        character.actions
    ):
        return ProgressionResult(["Repelling Blast 需要已知 Eldritch Blast"])
    choices = dict(getattr(character, "feature_choices", {}))
    choices[WARLOCK_REPELLING_BLAST_CANTRIP_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def set_warlock_ascendant_step_choice(
    character: Character,
    choice: str,
) -> ProgressionResult:
    normalized = normalize_warlock_ascendant_step_choice(choice)
    if normalized is None:
        return ProgressionResult([f"Ascendant Step 不支持的 SRD 选项：{choice}"])
    if int(character.class_levels.get("warlock", 0)) < 5:
        return ProgressionResult(["Ascendant Step 需要 Warlock 5"])
    choices = dict(getattr(character, "feature_choices", {}))
    choices[WARLOCK_ASCENDANT_STEP_CHOICE_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def set_warlock_armor_of_shadows_choice(
    character: Character,
    choice: str,
) -> ProgressionResult:
    normalized = normalize_warlock_armor_of_shadows_choice(choice)
    if normalized is None:
        return ProgressionResult([f"Armor of Shadows 不支持的 SRD 选项：{choice}"])
    if int(character.class_levels.get("warlock", 0)) < 1:
        return ProgressionResult(["Armor of Shadows 需要 Warlock 1"])
    choices = dict(getattr(character, "feature_choices", {}))
    choices[WARLOCK_ARMOR_OF_SHADOWS_CHOICE_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def set_warlock_fiendish_vigor_choice(
    character: Character,
    choice: str,
) -> ProgressionResult:
    normalized = normalize_warlock_fiendish_vigor_choice(choice)
    if normalized is None:
        return ProgressionResult([f"Fiendish Vigor 不支持的 SRD 选项：{choice}"])
    if int(character.class_levels.get("warlock", 0)) < 2:
        return ProgressionResult(["Fiendish Vigor 需要 Warlock 2"])
    choices = dict(getattr(character, "feature_choices", {}))
    choices[WARLOCK_FIENDISH_VIGOR_CHOICE_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def set_warlock_mask_of_many_faces_choice(
    character: Character,
    choice: str,
) -> ProgressionResult:
    normalized = normalize_warlock_mask_of_many_faces_choice(choice)
    if normalized is None:
        return ProgressionResult([f"Mask of Many Faces 不支持的 SRD 选项：{choice}"])
    if int(character.class_levels.get("warlock", 0)) < 2:
        return ProgressionResult(["Mask of Many Faces 需要 Warlock 2"])
    choices = dict(getattr(character, "feature_choices", {}))
    choices[WARLOCK_MASK_OF_MANY_FACES_CHOICE_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def set_warlock_misty_visions_choice(
    character: Character,
    choice: str,
) -> ProgressionResult:
    normalized = normalize_warlock_misty_visions_choice(choice)
    if normalized is None:
        return ProgressionResult([f"Misty Visions 不支持的 SRD 选项：{choice}"])
    if int(character.class_levels.get("warlock", 0)) < 2:
        return ProgressionResult(["Misty Visions 需要 Warlock 2"])
    choices = dict(getattr(character, "feature_choices", {}))
    choices[WARLOCK_MISTY_VISIONS_CHOICE_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def set_warlock_one_with_shadows_choice(
    character: Character,
    choice: str,
) -> ProgressionResult:
    normalized = normalize_warlock_one_with_shadows_choice(choice)
    if normalized is None:
        return ProgressionResult([f"One with Shadows 不支持的 SRD 选项：{choice}"])
    if int(character.class_levels.get("warlock", 0)) < 5:
        return ProgressionResult(["One with Shadows 需要 Warlock 5"])
    choices = dict(getattr(character, "feature_choices", {}))
    choices[WARLOCK_ONE_WITH_SHADOWS_CHOICE_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def set_warlock_otherworldly_leap_choice(
    character: Character,
    choice: str,
) -> ProgressionResult:
    normalized = normalize_warlock_otherworldly_leap_choice(choice)
    if normalized is None:
        return ProgressionResult([f"Otherworldly Leap 不支持的 SRD 选项：{choice}"])
    if int(character.class_levels.get("warlock", 0)) < 2:
        return ProgressionResult(["Otherworldly Leap 需要 Warlock 2"])
    choices = dict(getattr(character, "feature_choices", {}))
    choices[WARLOCK_OTHERWORLDLY_LEAP_CHOICE_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def set_warlock_master_of_myriad_forms_choice(
    character: Character,
    choice: str,
) -> ProgressionResult:
    normalized = normalize_warlock_master_of_myriad_forms_choice(choice)
    if normalized is None:
        return ProgressionResult([f"Master of Myriad Forms 不支持的 SRD 选项：{choice}"])
    if int(character.class_levels.get("warlock", 0)) < 5:
        return ProgressionResult(["Master of Myriad Forms 需要 Warlock 5"])
    choices = dict(getattr(character, "feature_choices", {}))
    choices[WARLOCK_MASTER_OF_MYRIAD_FORMS_CHOICE_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def set_warlock_gift_of_depths_choice(
    character: Character,
    choice: str,
) -> ProgressionResult:
    normalized = normalize_warlock_gift_of_depths_choice(choice)
    if normalized is None:
        return ProgressionResult([f"Gift of the Depths 不支持的 SRD 选项：{choice}"])
    if int(character.class_levels.get("warlock", 0)) < 5:
        return ProgressionResult(["Gift of the Depths 需要 Warlock 5"])
    choices = dict(getattr(character, "feature_choices", {}))
    choices[WARLOCK_GIFT_OF_DEPTHS_CHOICE_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def set_warlock_gaze_of_two_minds_choice(
    character: Character,
    choice: str,
) -> ProgressionResult:
    normalized = normalize_warlock_gaze_of_two_minds_choice(choice)
    if normalized is None:
        return ProgressionResult([f"Gaze of Two Minds 不支持的 SRD 选项：{choice}"])
    if int(character.class_levels.get("warlock", 0)) < 5:
        return ProgressionResult(["Gaze of Two Minds 需要 Warlock 5"])
    choices = dict(getattr(character, "feature_choices", {}))
    choices[WARLOCK_GAZE_OF_TWO_MINDS_CHOICE_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def set_warlock_investment_of_chain_master_choice(
    character: Character,
    choice: str,
) -> ProgressionResult:
    normalized = normalize_warlock_investment_of_chain_master_choice(choice)
    if normalized is None:
        return ProgressionResult([f"Investment of the Chain Master 不支持的 SRD 选项：{choice}"])
    if int(character.class_levels.get("warlock", 0)) < 5:
        return ProgressionResult(["Investment of the Chain Master 需要 Warlock 5"])
    if (
        character.feature_choices.get(WARLOCK_PACT_OF_CHAIN_CHOICE_KEY)
        != WARLOCK_PACT_OF_CHAIN_SELECTED
    ):
        return ProgressionResult(
            ["Investment of the Chain Master 需要 Pact of the Chain invocation"]
        )
    choices = dict(getattr(character, "feature_choices", {}))
    choices[WARLOCK_INVESTMENT_OF_CHAIN_MASTER_CHOICE_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def grant_warlock_lessons_of_first_ones_origin_feat(
    character: Character,
    feat: str,
    *,
    choices: Sequence[str] | None = None,
) -> ProgressionResult:
    normalized = normalize_warlock_lessons_origin_feat(feat)
    if normalized is None:
        return ProgressionResult([f"Lessons of the First Ones 不支持的 SRD Origin feat：{feat}"])
    if int(character.class_levels.get("warlock", 0)) < 2:
        return ProgressionResult(["Lessons of the First Ones 需要 Warlock 2"])
    if normalized not in WARLOCK_LESSONS_OF_FIRST_ONES_ORIGIN_FEATS:
        return ProgressionResult([f"Lessons of the First Ones 尚未接入该 SRD Origin feat：{feat}"])
    key = warlock_lessons_of_first_ones_choice_key(normalized)
    if character.feature_choices.get(key) == WARLOCK_LESSONS_OF_FIRST_ONES_SELECTED:
        return ProgressionResult([f"Lessons of the First Ones 已经选择该 Origin feat：{feat}"])
    result = grant_feat(character, normalized, choices=choices, consume_slot=False)
    if result.errors:
        return result
    feature_choices = dict(getattr(character, "feature_choices", {}))
    feature_choices[key] = WARLOCK_LESSONS_OF_FIRST_ONES_SELECTED
    character.feature_choices = feature_choices
    _recalculate_progression_fields(character)
    return result


def set_warlock_pact_of_blade_choice(
    character: Character,
    choice: str,
) -> ProgressionResult:
    normalized = normalize_warlock_pact_of_blade_choice(choice)
    if normalized is None:
        return ProgressionResult([f"Pact of the Blade 不支持的 SRD 选项：{choice}"])
    if int(character.class_levels.get("warlock", 0)) < 1:
        return ProgressionResult(["Pact of the Blade 需要 Warlock 1"])
    choices = dict(getattr(character, "feature_choices", {}))
    choices[WARLOCK_PACT_OF_BLADE_CHOICE_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def set_warlock_pact_of_chain_choice(
    character: Character,
    choice: str,
) -> ProgressionResult:
    normalized = normalize_warlock_pact_of_chain_choice(choice)
    if normalized is None:
        return ProgressionResult([f"Pact of the Chain 不支持的 SRD 选项：{choice}"])
    if int(character.class_levels.get("warlock", 0)) < 1:
        return ProgressionResult(["Pact of the Chain 需要 Warlock 1"])
    choices = dict(getattr(character, "feature_choices", {}))
    choices[WARLOCK_PACT_OF_CHAIN_CHOICE_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def set_warlock_pact_of_tome_choice(
    character: Character,
    choice: str,
    *,
    cantrips: Sequence[str],
    rituals: Sequence[str],
) -> ProgressionResult:
    normalized = normalize_warlock_pact_of_tome_choice(choice)
    if normalized is None:
        return ProgressionResult([f"Pact of the Tome 不支持的 SRD 选项：{choice}"])
    if int(character.class_levels.get("warlock", 0)) < 1:
        return ProgressionResult(["Pact of the Tome 需要 Warlock 1"])
    if len(cantrips) != WARLOCK_PACT_OF_TOME_CANTRIP_COUNT:
        return ProgressionResult(["Pact of the Tome 必须明确选择 3 个已实现 SRD cantrip"])
    if len(rituals) != WARLOCK_PACT_OF_TOME_RITUAL_COUNT:
        return ProgressionResult(["Pact of the Tome 必须明确选择 2 个已实现 SRD 1 环 Ritual"])

    normalized_cantrips: list[str] = []
    normalized_rituals: list[str] = []
    errors: list[str] = []
    seen_cantrips: set[str] = set()
    seen_rituals: set[str] = set()
    for cantrip in cantrips:
        spell_id = normalize_warlock_pact_of_tome_cantrip(cantrip)
        if spell_id is None:
            errors.append(f"Pact of the Tome 不支持的 SRD cantrip：{cantrip}")
            continue
        if spell_id in seen_cantrips:
            errors.append(f"Pact of the Tome cantrip 选择重复：{cantrip}")
            continue
        seen_cantrips.add(spell_id)
        normalized_cantrips.append(spell_id)
    for ritual in rituals:
        spell_id = normalize_warlock_pact_of_tome_ritual(ritual)
        if spell_id is None:
            errors.append(f"Pact of the Tome 不支持的 SRD 1 环 Ritual：{ritual}")
            continue
        if spell_id in seen_rituals:
            errors.append(f"Pact of the Tome Ritual 选择重复：{ritual}")
            continue
        seen_rituals.add(spell_id)
        normalized_rituals.append(spell_id)
    if errors:
        return ProgressionResult(errors)

    previous_tome_spells = set(_warlock_pact_of_tome_selected_spell_ids(character.feature_choices))
    prepared_spells = {
        str(spell_id)
        for spell_id in getattr(character, "prepared_spells", [])
        if str(spell_id) not in previous_tome_spells
    }
    already_prepared = [
        spell_id
        for spell_id in [*normalized_cantrips, *normalized_rituals]
        if spell_id in prepared_spells
    ]
    if already_prepared:
        return ProgressionResult(
            [f"Pact of the Tome 不能选择已经 prepared 的 spell：{already_prepared[0]}"]
        )

    choices = dict(getattr(character, "feature_choices", {}))
    choices[WARLOCK_PACT_OF_TOME_CHOICE_KEY] = normalized
    for index, spell_id in enumerate(normalized_cantrips, start=1):
        choices[warlock_pact_of_tome_cantrip_choice_key(index)] = spell_id
    for index, spell_id in enumerate(normalized_rituals, start=1):
        choices[warlock_pact_of_tome_ritual_choice_key(index)] = spell_id
    character.prepared_spells = [
        str(spell_id)
        for spell_id in getattr(character, "prepared_spells", [])
        if str(spell_id) not in previous_tome_spells
    ]
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def set_warlock_thirsting_blade_choice(
    character: Character,
    choice: str,
) -> ProgressionResult:
    normalized = normalize_warlock_thirsting_blade_choice(choice)
    if normalized is None:
        return ProgressionResult([f"Thirsting Blade 不支持的 SRD 选项：{choice}"])
    if int(character.class_levels.get("warlock", 0)) < 5:
        return ProgressionResult(["Thirsting Blade 需要 Warlock 5"])
    if (
        character.feature_choices.get(WARLOCK_PACT_OF_BLADE_CHOICE_KEY)
        != WARLOCK_PACT_OF_BLADE_SELECTED
    ):
        return ProgressionResult(["Thirsting Blade 需要 Pact of the Blade invocation"])
    choices = dict(getattr(character, "feature_choices", {}))
    choices[WARLOCK_THIRSTING_BLADE_CHOICE_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def set_warlock_eldritch_smite_choice(
    character: Character,
    choice: str,
) -> ProgressionResult:
    normalized = normalize_warlock_eldritch_smite_choice(choice)
    if normalized is None:
        return ProgressionResult([f"Eldritch Smite 不支持的 SRD 选项：{choice}"])
    if int(character.class_levels.get("warlock", 0)) < 5:
        return ProgressionResult(["Eldritch Smite 需要 Warlock 5"])
    if (
        character.feature_choices.get(WARLOCK_PACT_OF_BLADE_CHOICE_KEY)
        != WARLOCK_PACT_OF_BLADE_SELECTED
    ):
        return ProgressionResult(["Eldritch Smite 需要 Pact of the Blade invocation"])
    choices = dict(getattr(character, "feature_choices", {}))
    choices[WARLOCK_ELDRITCH_SMITE_CHOICE_KEY] = normalized
    character.feature_choices = choices
    _recalculate_progression_fields(character)
    return ProgressionResult(errors=[])


def grant_feat(
    character: Character,
    feat_id: str,
    *,
    choices: Sequence[str] | None = None,
    consume_slot: bool = True,
) -> ProgressionResult:
    if feat_id not in FEAT_IDS:
        return ProgressionResult([f"不支持的专长：{feat_id}"])
    feats = list(getattr(character, "feats", []))
    if feat_id in feats and feat_id not in REPEATABLE_FEATS:
        return ProgressionResult([f"已经拥有专长：{feat_id}"])
    if consume_slot and _ordinary_feat_count(character) >= available_feat_slots(character):
        return ProgressionResult(
            ["没有可用专长槽位；通常需要职业 4 级的 Ability Score Improvement"]
        )
    if feat_id == "skilled":
        errors = _grant_skilled_choices(character, choices or [])
        if errors:
            return ProgressionResult(errors)
    hp_delta = 0
    if feat_id == "tough":
        hp_delta = 2 * total_level(character)
        character.hp_max += hp_delta
        character.hp_current += hp_delta
    feats.append(feat_id)
    character.feats = feats
    return ProgressionResult(errors=[], hp_delta=hp_delta)


def grant_skill_expertise(
    character: Character,
    choices: Sequence[str],
) -> ProgressionResult:
    if not choices:
        return ProgressionResult(["Expertise 必须明确选择至少一项已熟练的 SRD 技能"])
    skill_proficiencies = {
        _choice_key(str(skill_id)) for skill_id in getattr(character, "skill_proficiencies", [])
    }
    existing = [
        skill_id
        for skill_id in getattr(character, "skill_expertise", [])
        if _choice_key(str(skill_id)) in skill_proficiencies
    ]
    normalized: list[tuple[str, str]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for choice in choices:
        skill_id = normalize_skill_choice(choice)
        if skill_id is None:
            errors.append(f"Expertise 不能选择非 SRD 技能：{choice}")
            continue
        if skill_id in seen:
            errors.append(f"Expertise 选择重复：{choice}")
            continue
        seen.add(skill_id)
        if _choice_key(skill_id) not in skill_proficiencies:
            errors.append(f"Expertise 只能选择已熟练技能：{choice}")
            continue
        if skill_id in existing:
            errors.append(f"已经拥有该技能 Expertise：{choice}")
            continue
        normalized.append((skill_id, choice))
    if errors:
        return ProgressionResult(errors)
    proposed = [*existing, *(skill_id for skill_id, _ in normalized)]
    if not _skill_expertise_choices_assignable(proposed, character.class_levels):
        return ProgressionResult(
            ["没有可用 Expertise 槽位，或该技能不符合 Wizard Scholar 的 SRD 限制"]
        )
    character.skill_expertise = proposed
    return ProgressionResult(errors=[])


def total_level(character: Character) -> int:
    return sum(max(0, int(level)) for level in character.class_levels.values())


def proficiency_bonus_for_level(level: int) -> int:
    level = max(1, level)
    return 2 + (level - 1) // 4


def normalize_skilled_choice(raw: str) -> tuple[str, str] | None:
    key = _choice_key(raw)
    skill_id = _SKILL_LOOKUP.get(key)
    if skill_id is not None:
        return ("skill", skill_id)
    tool_id = _TOOL_LOOKUP.get(key)
    if tool_id is not None:
        return ("tool", tool_id)
    return None


def normalize_skill_choice(raw: str) -> str | None:
    return _SKILL_LOOKUP.get(_choice_key(raw))


def available_feat_slots(character: Character) -> int:
    slots = 0
    for class_name, level in character.class_levels.items():
        class_level = max(0, int(level))
        slots += sum(1 for feat_level in COMMON_FEAT_LEVELS if class_level >= feat_level)
        slots += sum(
            1 for feat_level in EXTRA_FEAT_LEVELS.get(class_name, ()) if class_level >= feat_level
        )
    return slots


def _ordinary_feat_count(character: Character) -> int:
    lesson_counts: dict[str, int] = {}
    for feat_id in warlock_lessons_of_first_ones_origin_feats(character):
        lesson_counts[feat_id] = lesson_counts.get(feat_id, 0) + 1
    count = 0
    for feat_id in getattr(character, "feats", []):
        feat_key = str(feat_id)
        if lesson_counts.get(feat_key, 0) > 0:
            lesson_counts[feat_key] -= 1
            continue
        count += 1
    return count


def _warlock_pact_of_tome_cantrip_keys() -> list[str]:
    return [
        warlock_pact_of_tome_cantrip_choice_key(index)
        for index in range(1, WARLOCK_PACT_OF_TOME_CANTRIP_COUNT + 1)
    ]


def _warlock_pact_of_tome_ritual_keys() -> list[str]:
    return [
        warlock_pact_of_tome_ritual_choice_key(index)
        for index in range(1, WARLOCK_PACT_OF_TOME_RITUAL_COUNT + 1)
    ]


def _clear_warlock_pact_of_tome_choices(choices: dict[str, str]) -> None:
    choices.pop(WARLOCK_PACT_OF_TOME_CHOICE_KEY, None)
    for key in [*_warlock_pact_of_tome_cantrip_keys(), *_warlock_pact_of_tome_ritual_keys()]:
        choices.pop(key, None)


def _warlock_pact_of_tome_selected_spell_ids(feature_choices: dict[str, str]) -> list[str]:
    spell_ids: list[str] = []
    for key in _warlock_pact_of_tome_cantrip_keys():
        spell_id = feature_choices.get(key)
        if spell_id in WARLOCK_PACT_OF_TOME_CANTRIP_ACTIONS:
            spell_ids.append(spell_id)
    for key in _warlock_pact_of_tome_ritual_keys():
        spell_id = feature_choices.get(key)
        if spell_id in WARLOCK_PACT_OF_TOME_RITUAL_ACTIONS:
            spell_ids.append(spell_id)
    return spell_ids


def _warlock_pact_of_tome_choice_valid(feature_choices: dict[str, str]) -> bool:
    if feature_choices.get(WARLOCK_PACT_OF_TOME_CHOICE_KEY) != WARLOCK_PACT_OF_TOME_SELECTED:
        return False
    cantrips = [feature_choices.get(key) for key in _warlock_pact_of_tome_cantrip_keys()]
    rituals = [feature_choices.get(key) for key in _warlock_pact_of_tome_ritual_keys()]
    if any(spell_id not in WARLOCK_PACT_OF_TOME_CANTRIP_ACTIONS for spell_id in cantrips):
        return False
    if any(spell_id not in WARLOCK_PACT_OF_TOME_RITUAL_ACTIONS for spell_id in rituals):
        return False
    return len(set(cantrips)) == len(cantrips) and len(set(rituals)) == len(rituals)


def _warlock_pact_of_tome_action_ids(feature_choices: dict[str, str]) -> list[str]:
    if not _warlock_pact_of_tome_choice_valid(feature_choices):
        return []
    action_ids: list[str] = []
    for spell_id in _warlock_pact_of_tome_selected_spell_ids(feature_choices):
        action_id = WARLOCK_PACT_OF_TOME_CANTRIP_ACTIONS.get(
            spell_id
        ) or WARLOCK_PACT_OF_TOME_RITUAL_ACTIONS.get(spell_id)
        if action_id is not None:
            action_ids.append(action_id)
    return action_ids


def _recalculate_progression_fields(character: Character) -> None:
    character.proficiency_bonus = proficiency_bonus_for_level(total_level(character))
    character.hit_dice = _hit_dice_for_levels(character.class_levels)
    character.subclasses = {
        class_name: subclass_id
        for class_name, subclass_id in character.subclasses.items()
        if int(character.class_levels.get(class_name, 0))
        >= SUBCLASS_LEVELS.get(class_name, {}).get(subclass_id, 10**9)
    }
    _sync_feature_choices(character)
    character.actions = _actions_for_levels(
        character.class_levels,
        character.subclasses,
        character.feature_choices,
    )
    character.resources = _resources_for_levels(
        character.class_levels,
        character.subclasses,
        character.feature_choices,
        character.resources,
        character.abilities,
    )
    spell_slots = spell_slot_maxima_for_class_levels(character.class_levels)
    character.spell_slots = dict(spell_slots)
    character.spell_slots_max = dict(spell_slots)
    _sync_class_languages(character)
    _sync_always_prepared_spells(character)
    _sync_class_known_spells(character)
    _sync_skill_expertise(character)


def _sync_feature_choices(character: Character) -> None:
    choices = dict(getattr(character, "feature_choices", {}))
    if (
        character.subclasses.get("ranger") == "hunter"
        and int(character.class_levels.get("ranger", 0)) >= 3
    ):
        if choices.get(HUNTERS_PREY_CHOICE_KEY) not in HUNTERS_PREY_CHOICES:
            choices[HUNTERS_PREY_CHOICE_KEY] = HUNTERS_PREY_COLOSSUS_SLAYER
    else:
        choices.pop(HUNTERS_PREY_CHOICE_KEY, None)
    if (
        character.subclasses.get("ranger") == "hunter"
        and int(character.class_levels.get("ranger", 0)) >= 7
    ):
        if choices.get(HUNTER_DEFENSIVE_TACTICS_CHOICE_KEY) not in HUNTER_DEFENSIVE_TACTICS_CHOICES:
            choices[HUNTER_DEFENSIVE_TACTICS_CHOICE_KEY] = HUNTER_DEFENSIVE_TACTICS_ESCAPE_THE_HORDE
    else:
        choices.pop(HUNTER_DEFENSIVE_TACTICS_CHOICE_KEY, None)
    if int(character.class_levels.get("cleric", 0)) >= 1:
        if choices.get(DIVINE_ORDER_CHOICE_KEY) not in DIVINE_ORDER_CHOICES:
            choices.pop(DIVINE_ORDER_CHOICE_KEY, None)
    else:
        choices.pop(DIVINE_ORDER_CHOICE_KEY, None)
    if int(character.class_levels.get("druid", 0)) >= 1:
        if choices.get(DRUID_PRIMAL_ORDER_CHOICE_KEY) not in DRUID_PRIMAL_ORDER_CHOICES:
            choices.pop(DRUID_PRIMAL_ORDER_CHOICE_KEY, None)
    else:
        choices.pop(DRUID_PRIMAL_ORDER_CHOICE_KEY, None)
    if (
        character.subclasses.get("druid") == "land"
        and int(character.class_levels.get("druid", 0)) >= 3
    ):
        if choices.get(DRUID_CIRCLE_LAND_CHOICE_KEY) not in DRUID_CIRCLE_LAND_TYPES:
            choices.pop(DRUID_CIRCLE_LAND_CHOICE_KEY, None)
    else:
        choices.pop(DRUID_CIRCLE_LAND_CHOICE_KEY, None)
    if int(character.class_levels.get("warlock", 0)) >= 1:
        if (
            choices.get(WARLOCK_ELDRITCH_INVOCATION_CHOICE_KEY)
            not in WARLOCK_ELDRITCH_INVOCATION_CHOICES
        ):
            choices.pop(WARLOCK_ELDRITCH_INVOCATION_CHOICE_KEY, None)
        if (
            choices.get(WARLOCK_ARMOR_OF_SHADOWS_CHOICE_KEY)
            not in WARLOCK_ARMOR_OF_SHADOWS_ALIASES.values()
        ):
            choices.pop(WARLOCK_ARMOR_OF_SHADOWS_CHOICE_KEY, None)
        if (
            choices.get(WARLOCK_PACT_OF_CHAIN_CHOICE_KEY)
            not in WARLOCK_PACT_OF_CHAIN_ALIASES.values()
        ):
            choices.pop(WARLOCK_PACT_OF_CHAIN_CHOICE_KEY, None)
        if (
            choices.get(WARLOCK_PACT_OF_BLADE_CHOICE_KEY)
            not in WARLOCK_PACT_OF_BLADE_ALIASES.values()
        ):
            choices.pop(WARLOCK_PACT_OF_BLADE_CHOICE_KEY, None)
        if not _warlock_pact_of_tome_choice_valid(choices):
            _clear_warlock_pact_of_tome_choices(choices)
    else:
        choices.pop(WARLOCK_ELDRITCH_INVOCATION_CHOICE_KEY, None)
        choices.pop(WARLOCK_ARMOR_OF_SHADOWS_CHOICE_KEY, None)
        choices.pop(WARLOCK_PACT_OF_CHAIN_CHOICE_KEY, None)
        choices.pop(WARLOCK_PACT_OF_BLADE_CHOICE_KEY, None)
        _clear_warlock_pact_of_tome_choices(choices)
    if int(character.class_levels.get("warlock", 0)) >= 2:
        if (
            choices.get(WARLOCK_DEVILS_SIGHT_CHOICE_KEY)
            not in WARLOCK_DEVILS_SIGHT_ALIASES.values()
        ):
            choices.pop(WARLOCK_DEVILS_SIGHT_CHOICE_KEY, None)
        if (
            choices.get(WARLOCK_AGONIZING_BLAST_CANTRIP_KEY)
            not in WARLOCK_AGONIZING_BLAST_CANTRIP_ALIASES.values()
        ):
            choices.pop(WARLOCK_AGONIZING_BLAST_CANTRIP_KEY, None)
        if (
            choices.get(WARLOCK_ELDRITCH_SPEAR_CANTRIP_KEY)
            not in WARLOCK_ELDRITCH_SPEAR_CANTRIP_ALIASES.values()
        ):
            choices.pop(WARLOCK_ELDRITCH_SPEAR_CANTRIP_KEY, None)
        if (
            choices.get(WARLOCK_REPELLING_BLAST_CANTRIP_KEY)
            not in WARLOCK_REPELLING_BLAST_CANTRIP_ALIASES.values()
        ):
            choices.pop(WARLOCK_REPELLING_BLAST_CANTRIP_KEY, None)
        if (
            choices.get(WARLOCK_FIENDISH_VIGOR_CHOICE_KEY)
            not in WARLOCK_FIENDISH_VIGOR_ALIASES.values()
        ):
            choices.pop(WARLOCK_FIENDISH_VIGOR_CHOICE_KEY, None)
        if (
            choices.get(WARLOCK_MASK_OF_MANY_FACES_CHOICE_KEY)
            not in WARLOCK_MASK_OF_MANY_FACES_ALIASES.values()
        ):
            choices.pop(WARLOCK_MASK_OF_MANY_FACES_CHOICE_KEY, None)
        if (
            choices.get(WARLOCK_MISTY_VISIONS_CHOICE_KEY)
            not in WARLOCK_MISTY_VISIONS_ALIASES.values()
        ):
            choices.pop(WARLOCK_MISTY_VISIONS_CHOICE_KEY, None)
        if (
            choices.get(WARLOCK_OTHERWORLDLY_LEAP_CHOICE_KEY)
            not in WARLOCK_OTHERWORLDLY_LEAP_ALIASES.values()
        ):
            choices.pop(WARLOCK_OTHERWORLDLY_LEAP_CHOICE_KEY, None)
        for feat_id in WARLOCK_LESSONS_OF_FIRST_ONES_ORIGIN_FEATS:
            key = warlock_lessons_of_first_ones_choice_key(feat_id)
            if choices.get(key) != WARLOCK_LESSONS_OF_FIRST_ONES_SELECTED:
                choices.pop(key, None)
    else:
        choices.pop(WARLOCK_DEVILS_SIGHT_CHOICE_KEY, None)
        choices.pop(WARLOCK_AGONIZING_BLAST_CANTRIP_KEY, None)
        choices.pop(WARLOCK_ELDRITCH_SPEAR_CANTRIP_KEY, None)
        choices.pop(WARLOCK_REPELLING_BLAST_CANTRIP_KEY, None)
        choices.pop(WARLOCK_FIENDISH_VIGOR_CHOICE_KEY, None)
        choices.pop(WARLOCK_MASK_OF_MANY_FACES_CHOICE_KEY, None)
        choices.pop(WARLOCK_MISTY_VISIONS_CHOICE_KEY, None)
        choices.pop(WARLOCK_OTHERWORLDLY_LEAP_CHOICE_KEY, None)
        for feat_id in WARLOCK_LESSONS_OF_FIRST_ONES_ORIGIN_FEATS:
            choices.pop(warlock_lessons_of_first_ones_choice_key(feat_id), None)
    if int(character.class_levels.get("warlock", 0)) >= 5:
        if (
            choices.get(WARLOCK_ASCENDANT_STEP_CHOICE_KEY)
            not in WARLOCK_ASCENDANT_STEP_ALIASES.values()
        ):
            choices.pop(WARLOCK_ASCENDANT_STEP_CHOICE_KEY, None)
        if (
            choices.get(WARLOCK_ONE_WITH_SHADOWS_CHOICE_KEY)
            not in WARLOCK_ONE_WITH_SHADOWS_ALIASES.values()
        ):
            choices.pop(WARLOCK_ONE_WITH_SHADOWS_CHOICE_KEY, None)
        if (
            choices.get(WARLOCK_MASTER_OF_MYRIAD_FORMS_CHOICE_KEY)
            not in WARLOCK_MASTER_OF_MYRIAD_FORMS_ALIASES.values()
        ):
            choices.pop(WARLOCK_MASTER_OF_MYRIAD_FORMS_CHOICE_KEY, None)
        if (
            choices.get(WARLOCK_GIFT_OF_DEPTHS_CHOICE_KEY)
            not in WARLOCK_GIFT_OF_DEPTHS_ALIASES.values()
        ):
            choices.pop(WARLOCK_GIFT_OF_DEPTHS_CHOICE_KEY, None)
        if (
            choices.get(WARLOCK_GAZE_OF_TWO_MINDS_CHOICE_KEY)
            not in WARLOCK_GAZE_OF_TWO_MINDS_ALIASES.values()
        ):
            choices.pop(WARLOCK_GAZE_OF_TWO_MINDS_CHOICE_KEY, None)
        if (
            choices.get(WARLOCK_INVESTMENT_OF_CHAIN_MASTER_CHOICE_KEY)
            not in WARLOCK_INVESTMENT_OF_CHAIN_MASTER_ALIASES.values()
            or choices.get(WARLOCK_PACT_OF_CHAIN_CHOICE_KEY) != WARLOCK_PACT_OF_CHAIN_SELECTED
        ):
            choices.pop(WARLOCK_INVESTMENT_OF_CHAIN_MASTER_CHOICE_KEY, None)
        if (
            choices.get(WARLOCK_THIRSTING_BLADE_CHOICE_KEY)
            not in WARLOCK_THIRSTING_BLADE_ALIASES.values()
            or choices.get(WARLOCK_PACT_OF_BLADE_CHOICE_KEY) != WARLOCK_PACT_OF_BLADE_SELECTED
        ):
            choices.pop(WARLOCK_THIRSTING_BLADE_CHOICE_KEY, None)
        if (
            choices.get(WARLOCK_ELDRITCH_SMITE_CHOICE_KEY)
            not in WARLOCK_ELDRITCH_SMITE_ALIASES.values()
            or choices.get(WARLOCK_PACT_OF_BLADE_CHOICE_KEY) != WARLOCK_PACT_OF_BLADE_SELECTED
        ):
            choices.pop(WARLOCK_ELDRITCH_SMITE_CHOICE_KEY, None)
    else:
        choices.pop(WARLOCK_ASCENDANT_STEP_CHOICE_KEY, None)
        choices.pop(WARLOCK_ONE_WITH_SHADOWS_CHOICE_KEY, None)
        choices.pop(WARLOCK_MASTER_OF_MYRIAD_FORMS_CHOICE_KEY, None)
        choices.pop(WARLOCK_GIFT_OF_DEPTHS_CHOICE_KEY, None)
        choices.pop(WARLOCK_GAZE_OF_TWO_MINDS_CHOICE_KEY, None)
        choices.pop(WARLOCK_INVESTMENT_OF_CHAIN_MASTER_CHOICE_KEY, None)
        choices.pop(WARLOCK_THIRSTING_BLADE_CHOICE_KEY, None)
        choices.pop(WARLOCK_ELDRITCH_SMITE_CHOICE_KEY, None)
    character.feature_choices = choices


def _append_fixed_class_tool_proficiencies(character: Character, class_name: str) -> None:
    proficiencies = list(getattr(character, "tool_proficiencies", []))
    for tool_id in CLASS_TOOL_PROFICIENCIES.get(class_name, []):
        if tool_id not in proficiencies:
            proficiencies.append(tool_id)
    character.tool_proficiencies = proficiencies


def _sync_class_languages(character: Character) -> None:
    class_language_ids = {
        language_id for languages in CLASS_LANGUAGES.values() for language_id in languages
    }
    languages = [
        str(language_id)
        for language_id in getattr(character, "languages", [])
        if str(language_id) not in class_language_ids
    ]
    for class_name, language_ids in CLASS_LANGUAGES.items():
        if int(character.class_levels.get(class_name, 0)) < 1:
            continue
        for language_id in language_ids:
            if language_id not in languages:
                languages.append(language_id)
    character.languages = languages


def _sync_always_prepared_spells(character: Character) -> None:
    always_prepared = {
        "druid": [(1, "srd.spell.speak_with_animals")],
        "paladin": [(5, "srd.spell.find_steed")],
    }
    class_spell_ids = {
        spell_id for spell_entries in always_prepared.values() for _, spell_id in spell_entries
    }
    selected_pact_tome_spells = (
        set(_warlock_pact_of_tome_selected_spell_ids(character.feature_choices))
        if _warlock_pact_of_tome_choice_valid(character.feature_choices)
        else set()
    )
    prepared_spells = [
        str(spell_id)
        for spell_id in getattr(character, "prepared_spells", [])
        if str(spell_id) not in class_spell_ids and str(spell_id) not in selected_pact_tome_spells
    ]
    for class_name, spell_entries in always_prepared.items():
        class_level = int(character.class_levels.get(class_name, 0))
        for required_level, spell_id in spell_entries:
            if class_level < required_level:
                continue
            if spell_id not in prepared_spells:
                prepared_spells.append(spell_id)
    for spell_id in _warlock_pact_of_tome_selected_spell_ids(character.feature_choices):
        if spell_id in selected_pact_tome_spells and spell_id not in prepared_spells:
            prepared_spells.append(spell_id)
    character.prepared_spells = prepared_spells


def _sync_class_known_spells(character: Character) -> None:
    known_spells = [str(spell_id) for spell_id in getattr(character, "known_spells", [])]
    has_pact_of_chain = (
        int(character.class_levels.get("warlock", 0)) >= 1
        and character.feature_choices.get(WARLOCK_PACT_OF_CHAIN_CHOICE_KEY)
        == WARLOCK_PACT_OF_CHAIN_SELECTED
    )
    if has_pact_of_chain:
        if "srd.spell.find_familiar" not in known_spells:
            known_spells.append("srd.spell.find_familiar")
    elif int(character.class_levels.get("wizard", 0)) <= 0:
        known_spells = [
            spell_id for spell_id in known_spells if spell_id != "srd.spell.find_familiar"
        ]
    character.known_spells = known_spells


def _sync_skill_expertise(character: Character) -> None:
    skill_proficiencies = {
        _choice_key(str(skill_id)) for skill_id in getattr(character, "skill_proficiencies", [])
    }
    synced: list[str] = []
    for raw_skill in getattr(character, "skill_expertise", []):
        skill_id = normalize_skill_choice(str(raw_skill))
        if skill_id is None or _choice_key(skill_id) not in skill_proficiencies:
            continue
        if skill_id in synced:
            continue
        proposed = [*synced, skill_id]
        if _skill_expertise_choices_assignable(proposed, character.class_levels):
            synced.append(skill_id)
    character.skill_expertise = synced


def _skill_expertise_choices_assignable(
    skill_ids: Sequence[str],
    class_levels: dict[str, int],
) -> bool:
    if len(set(skill_ids)) != len(skill_ids):
        return False
    slots = _skill_expertise_slots(class_levels)
    if len(skill_ids) > len(slots):
        return False
    ordered_skills = sorted(
        skill_ids,
        key=lambda skill_id: sum(1 for allowed in slots if allowed is None or skill_id in allowed),
    )

    def assign(index: int, used_slots: set[int]) -> bool:
        if index >= len(ordered_skills):
            return True
        skill_id = ordered_skills[index]
        for slot_index, allowed in enumerate(slots):
            if slot_index in used_slots:
                continue
            if allowed is not None and skill_id not in allowed:
                continue
            if assign(index + 1, used_slots | {slot_index}):
                return True
        return False

    return assign(0, set())


def _skill_expertise_slots(class_levels: dict[str, int]) -> list[frozenset[str] | None]:
    slots: list[frozenset[str] | None] = []
    rogue_level = int(class_levels.get("rogue", 0))
    if rogue_level >= 1:
        slots.extend([None, None])
    if rogue_level >= 6:
        slots.extend([None, None])
    bard_level = int(class_levels.get("bard", 0))
    if bard_level >= 2:
        slots.extend([None, None])
    if bard_level >= 9:
        slots.extend([None, None])
    ranger_level = int(class_levels.get("ranger", 0))
    if ranger_level >= 2:
        slots.append(None)
    if ranger_level >= 9:
        slots.extend([None, None])
    if int(class_levels.get("wizard", 0)) >= 2:
        slots.append(WIZARD_SCHOLAR_SKILLS)
    return slots


def _grant_skilled_choices(character: Character, choices: Sequence[str]) -> list[str]:
    normalized: list[tuple[str, str, str]] = []
    errors: list[str] = []
    if len(choices) != 3:
        return ["Skilled 专长必须明确选择任意三项 SRD 技能或工具熟练"]
    seen: set[tuple[str, str]] = set()
    for choice in choices:
        parsed = normalize_skilled_choice(choice)
        if parsed is None:
            errors.append(f"Skilled 不能选择非 SRD 技能或工具：{choice}")
            continue
        key = parsed
        if key in seen:
            errors.append(f"Skilled 选择重复：{choice}")
            continue
        seen.add(key)
        normalized.append((parsed[0], parsed[1], choice))
    skill_proficiencies = list(getattr(character, "skill_proficiencies", []))
    tool_proficiencies = list(getattr(character, "tool_proficiencies", []))
    for kind, value, raw in normalized:
        if kind == "skill" and value in skill_proficiencies:
            errors.append(f"已经拥有技能熟练：{raw}")
        if kind == "tool" and value in tool_proficiencies:
            errors.append(f"已经拥有工具熟练：{raw}")
    if errors:
        return errors
    for kind, value, _raw in normalized:
        if kind == "skill":
            skill_proficiencies.append(value)
        else:
            tool_proficiencies.append(value)
    character.skill_proficiencies = skill_proficiencies
    character.tool_proficiencies = tool_proficiencies
    return []


def _validate_class_level(class_name: str, level: int) -> list[str]:
    errors: list[str] = []
    if class_name not in CLASS_HIT_DICE:
        errors.append(f"不支持的 SRD 基础职业：{class_name}")
    if level < 1:
        errors.append("职业等级必须至少为 1")
    if level > 20:
        errors.append("职业等级不能超过 SRD 角色等级上限 20")
    return errors


def _hit_dice_for_levels(class_levels: dict[str, int]) -> dict[str, int]:
    hit_dice: dict[str, int] = {}
    for class_name, level in class_levels.items():
        hit_die = CLASS_HIT_DICE.get(class_name)
        if hit_die is None:
            continue
        hit_dice[hit_die] = hit_dice.get(hit_die, 0) + max(0, int(level))
    return hit_dice


def _actions_for_levels(
    class_levels: dict[str, int],
    subclasses: dict[str, str],
    feature_choices: dict[str, str],
) -> list[str]:
    actions: list[str] = []
    for class_name, level in class_levels.items():
        for action_id in CLASS_BASE_ACTIONS.get(class_name, ["srd.shortsword_attack"]):
            _append_unique(actions, action_id)
        for required_level, action_ids in sorted(CLASS_LEVEL_ACTIONS.get(class_name, {}).items()):
            if int(level) >= required_level:
                for action_id in action_ids:
                    _append_unique(actions, action_id)
        if class_name == "warlock" and int(level) >= 1:
            choice = feature_choices.get(WARLOCK_ELDRITCH_INVOCATION_CHOICE_KEY)
            for action_id in FEATURE_CHOICE_ACTIONS.get(
                WARLOCK_ELDRITCH_INVOCATION_CHOICE_KEY,
                {},
            ).get(str(choice), []):
                _append_unique(actions, action_id)
            armor_of_shadows = feature_choices.get(WARLOCK_ARMOR_OF_SHADOWS_CHOICE_KEY)
            for action_id in FEATURE_CHOICE_ACTIONS.get(
                WARLOCK_ARMOR_OF_SHADOWS_CHOICE_KEY,
                {},
            ).get(str(armor_of_shadows), []):
                _append_unique(actions, action_id)
            pact_of_chain = feature_choices.get(WARLOCK_PACT_OF_CHAIN_CHOICE_KEY)
            for action_id in FEATURE_CHOICE_ACTIONS.get(
                WARLOCK_PACT_OF_CHAIN_CHOICE_KEY,
                {},
            ).get(str(pact_of_chain), []):
                _append_unique(actions, action_id)
            pact_of_tome = feature_choices.get(WARLOCK_PACT_OF_TOME_CHOICE_KEY)
            for action_id in FEATURE_CHOICE_ACTIONS.get(
                WARLOCK_PACT_OF_TOME_CHOICE_KEY,
                {},
            ).get(str(pact_of_tome), []):
                _append_unique(actions, action_id)
            for action_id in _warlock_pact_of_tome_action_ids(feature_choices):
                _append_unique(actions, action_id)
            pact_of_blade = feature_choices.get(WARLOCK_PACT_OF_BLADE_CHOICE_KEY)
            for action_id in FEATURE_CHOICE_ACTIONS.get(
                WARLOCK_PACT_OF_BLADE_CHOICE_KEY,
                {},
            ).get(str(pact_of_blade), []):
                _append_unique(actions, action_id)
            agonizing_blast_cantrip = feature_choices.get(WARLOCK_AGONIZING_BLAST_CANTRIP_KEY)
            for action_id in FEATURE_CHOICE_ACTIONS.get(
                WARLOCK_AGONIZING_BLAST_CANTRIP_KEY,
                {},
            ).get(str(agonizing_blast_cantrip), []):
                _append_unique(actions, action_id)
            eldritch_spear_cantrip = feature_choices.get(WARLOCK_ELDRITCH_SPEAR_CANTRIP_KEY)
            for action_id in FEATURE_CHOICE_ACTIONS.get(
                WARLOCK_ELDRITCH_SPEAR_CANTRIP_KEY,
                {},
            ).get(str(eldritch_spear_cantrip), []):
                _append_unique(actions, action_id)
            repelling_blast_cantrip = feature_choices.get(WARLOCK_REPELLING_BLAST_CANTRIP_KEY)
            for action_id in FEATURE_CHOICE_ACTIONS.get(
                WARLOCK_REPELLING_BLAST_CANTRIP_KEY,
                {},
            ).get(str(repelling_blast_cantrip), []):
                _append_unique(actions, action_id)
            devils_sight = feature_choices.get(WARLOCK_DEVILS_SIGHT_CHOICE_KEY)
            for action_id in FEATURE_CHOICE_ACTIONS.get(
                WARLOCK_DEVILS_SIGHT_CHOICE_KEY,
                {},
            ).get(str(devils_sight), []):
                _append_unique(actions, action_id)
            fiendish_vigor = feature_choices.get(WARLOCK_FIENDISH_VIGOR_CHOICE_KEY)
            for action_id in FEATURE_CHOICE_ACTIONS.get(
                WARLOCK_FIENDISH_VIGOR_CHOICE_KEY,
                {},
            ).get(str(fiendish_vigor), []):
                _append_unique(actions, action_id)
            mask_of_many_faces = feature_choices.get(WARLOCK_MASK_OF_MANY_FACES_CHOICE_KEY)
            for action_id in FEATURE_CHOICE_ACTIONS.get(
                WARLOCK_MASK_OF_MANY_FACES_CHOICE_KEY,
                {},
            ).get(str(mask_of_many_faces), []):
                _append_unique(actions, action_id)
            misty_visions = feature_choices.get(WARLOCK_MISTY_VISIONS_CHOICE_KEY)
            for action_id in FEATURE_CHOICE_ACTIONS.get(
                WARLOCK_MISTY_VISIONS_CHOICE_KEY,
                {},
            ).get(str(misty_visions), []):
                _append_unique(actions, action_id)
            one_with_shadows = feature_choices.get(WARLOCK_ONE_WITH_SHADOWS_CHOICE_KEY)
            for action_id in FEATURE_CHOICE_ACTIONS.get(
                WARLOCK_ONE_WITH_SHADOWS_CHOICE_KEY,
                {},
            ).get(str(one_with_shadows), []):
                _append_unique(actions, action_id)
            otherworldly_leap = feature_choices.get(WARLOCK_OTHERWORLDLY_LEAP_CHOICE_KEY)
            for action_id in FEATURE_CHOICE_ACTIONS.get(
                WARLOCK_OTHERWORLDLY_LEAP_CHOICE_KEY,
                {},
            ).get(str(otherworldly_leap), []):
                _append_unique(actions, action_id)
            ascendant_step = feature_choices.get(WARLOCK_ASCENDANT_STEP_CHOICE_KEY)
            for action_id in FEATURE_CHOICE_ACTIONS.get(
                WARLOCK_ASCENDANT_STEP_CHOICE_KEY,
                {},
            ).get(str(ascendant_step), []):
                _append_unique(actions, action_id)
            master_of_myriad_forms = feature_choices.get(WARLOCK_MASTER_OF_MYRIAD_FORMS_CHOICE_KEY)
            for action_id in FEATURE_CHOICE_ACTIONS.get(
                WARLOCK_MASTER_OF_MYRIAD_FORMS_CHOICE_KEY,
                {},
            ).get(str(master_of_myriad_forms), []):
                _append_unique(actions, action_id)
            gift_of_depths = feature_choices.get(WARLOCK_GIFT_OF_DEPTHS_CHOICE_KEY)
            for action_id in FEATURE_CHOICE_ACTIONS.get(
                WARLOCK_GIFT_OF_DEPTHS_CHOICE_KEY,
                {},
            ).get(str(gift_of_depths), []):
                _append_unique(actions, action_id)
            gaze_of_two_minds = feature_choices.get(WARLOCK_GAZE_OF_TWO_MINDS_CHOICE_KEY)
            for action_id in FEATURE_CHOICE_ACTIONS.get(
                WARLOCK_GAZE_OF_TWO_MINDS_CHOICE_KEY,
                {},
            ).get(str(gaze_of_two_minds), []):
                _append_unique(actions, action_id)
            investment_of_chain_master = feature_choices.get(
                WARLOCK_INVESTMENT_OF_CHAIN_MASTER_CHOICE_KEY
            )
            for action_id in FEATURE_CHOICE_ACTIONS.get(
                WARLOCK_INVESTMENT_OF_CHAIN_MASTER_CHOICE_KEY,
                {},
            ).get(str(investment_of_chain_master), []):
                _append_unique(actions, action_id)
            thirsting_blade = feature_choices.get(WARLOCK_THIRSTING_BLADE_CHOICE_KEY)
            for action_id in FEATURE_CHOICE_ACTIONS.get(
                WARLOCK_THIRSTING_BLADE_CHOICE_KEY,
                {},
            ).get(str(thirsting_blade), []):
                _append_unique(actions, action_id)
            eldritch_smite = feature_choices.get(WARLOCK_ELDRITCH_SMITE_CHOICE_KEY)
            for action_id in FEATURE_CHOICE_ACTIONS.get(
                WARLOCK_ELDRITCH_SMITE_CHOICE_KEY,
                {},
            ).get(str(eldritch_smite), []):
                _append_unique(actions, action_id)
            if int(level) >= 2:
                for feat_id in WARLOCK_LESSONS_OF_FIRST_ONES_ORIGIN_FEATS:
                    if (
                        feature_choices.get(warlock_lessons_of_first_ones_choice_key(feat_id))
                        == WARLOCK_LESSONS_OF_FIRST_ONES_SELECTED
                    ):
                        _append_unique(actions, "srd.lessons_of_the_first_ones")
        subclass_id = subclasses.get(class_name)
        if subclass_id is None:
            continue
        for required_level, action_ids in sorted(
            SUBCLASS_ACTIONS.get(class_name, {}).get(subclass_id, {}).items()
        ):
            if int(level) >= required_level:
                for action_id in action_ids:
                    _append_unique(actions, action_id)
        if subclass_id == "hunter" and class_name == "ranger" and int(level) >= 3:
            choice = feature_choices.get(HUNTERS_PREY_CHOICE_KEY)
            for action_id in FEATURE_CHOICE_ACTIONS.get(HUNTERS_PREY_CHOICE_KEY, {}).get(
                str(choice),
                [],
            ):
                _append_unique(actions, action_id)
        if subclass_id == "hunter" and class_name == "ranger" and int(level) >= 7:
            choice = feature_choices.get(HUNTER_DEFENSIVE_TACTICS_CHOICE_KEY)
            for action_id in FEATURE_CHOICE_ACTIONS.get(
                HUNTER_DEFENSIVE_TACTICS_CHOICE_KEY,
                {},
            ).get(str(choice), []):
                _append_unique(actions, action_id)
    return actions


def _resources_for_levels(
    class_levels: dict[str, int],
    subclasses: dict[str, str],
    feature_choices: dict[str, str],
    current: dict[str, int],
    abilities: dict[str, int],
) -> dict[str, int]:
    resources = {
        resource: amount
        for resource, amount in current.items()
        if not resource.startswith("srd.resource.")
    }
    fighter_level = int(class_levels.get("fighter", 0))
    if fighter_level > 0:
        if fighter_level >= 10:
            second_wind_uses = 4
        elif fighter_level >= 4:
            second_wind_uses = 3
        else:
            second_wind_uses = 2
        resources["srd.resource.second_wind"] = second_wind_uses
    if fighter_level >= 2:
        resources["srd.resource.action_surge"] = 2 if fighter_level >= 17 else 1
    if fighter_level >= 9:
        if fighter_level >= 17:
            indomitable_uses = 3
        elif fighter_level >= 13:
            indomitable_uses = 2
        else:
            indomitable_uses = 1
        resources["srd.resource.indomitable"] = indomitable_uses
    barbarian_level = int(class_levels.get("barbarian", 0))
    if barbarian_level > 0:
        if barbarian_level >= 17:
            rage_uses = 6
        elif barbarian_level >= 12:
            rage_uses = 5
        elif barbarian_level >= 6:
            rage_uses = 4
        elif barbarian_level >= 3:
            rage_uses = 3
        else:
            rage_uses = 2
        resources["srd.resource.rage"] = rage_uses
        if barbarian_level >= 15:
            resources[PERSISTENT_RAGE_INITIATIVE_RESTORE_RESOURCE] = 1
    paladin_level = int(class_levels.get("paladin", 0))
    if paladin_level > 0:
        resources["srd.resource.lay_on_hands"] = paladin_level * 5
    if paladin_level >= 2:
        resources["srd.resource.paladins_smite"] = 1
    if paladin_level >= 5:
        resources["srd.resource.faithful_steed"] = 1
    monk_level = int(class_levels.get("monk", 0))
    if monk_level >= 2:
        resources["srd.resource.focus_points"] = monk_level
        resources[UNCANNY_METABOLISM_RESOURCE] = 1
    if monk_level >= 6 and subclasses.get("monk") == "open_hand":
        resources[WHOLENESS_OF_BODY_RESOURCE] = max(
            1,
            _ability_modifier_from_scores(abilities, "wis"),
        )
    bard_level = int(class_levels.get("bard", 0))
    if bard_level > 0:
        resources["srd.resource.bardic_inspiration"] = max(
            1,
            _ability_modifier_from_scores(abilities, "cha"),
        )
    ranger_level = int(class_levels.get("ranger", 0))
    if ranger_level > 0:
        resources["srd.resource.favored_enemy_hunters_mark"] = 3 if ranger_level >= 5 else 2
    if ranger_level >= 10:
        resources[TIRELESS_RESOURCE] = max(1, _ability_modifier_from_scores(abilities, "wis"))
    if ranger_level >= 14:
        resources[NATURES_VEIL_RESOURCE] = max(1, _ability_modifier_from_scores(abilities, "wis"))
    cleric_level = int(class_levels.get("cleric", 0))
    if cleric_level >= 2:
        resources["srd.resource.channel_divinity"] = 2
    if paladin_level >= 3:
        resources["srd.resource.channel_divinity"] = max(
            resources.get("srd.resource.channel_divinity", 0),
            2,
        )
    druid_level = int(class_levels.get("druid", 0))
    if druid_level >= 2:
        resources["srd.resource.wild_shape"] = 2
    if druid_level >= 5:
        resources["srd.resource.wild_resurgence_spell_slot"] = 1
    if druid_level >= 6 and subclasses.get("druid") == "land":
        resources[NATURAL_RECOVERY_SPELL_SLOTS_RESOURCE] = 1
        resources[NATURAL_RECOVERY_CIRCLE_SPELL_RESOURCE] = 1
    sorcerer_level = int(class_levels.get("sorcerer", 0))
    if sorcerer_level >= 1:
        resources["srd.resource.innate_sorcery"] = 2
    if sorcerer_level >= 2:
        resources["srd.resource.sorcery_points"] = sorcerer_level
    if sorcerer_level >= 5:
        resources["srd.resource.sorcerous_restoration"] = 1
    warlock_level = int(class_levels.get("warlock", 0))
    if warlock_level >= 2:
        resources["srd.resource.magical_cunning"] = 1
    if warlock_level >= 6 and subclasses.get("warlock") == "fiend":
        resources[DARK_ONES_OWN_LUCK_RESOURCE] = max(
            1,
            _ability_modifier_from_scores(abilities, "cha"),
        )
    if int(class_levels.get("rogue", 0)) >= 20:
        resources[STROKE_OF_LUCK_RESOURCE] = 1
    if (
        warlock_level >= 5
        and feature_choices.get(WARLOCK_GIFT_OF_DEPTHS_CHOICE_KEY)
        == WARLOCK_GIFT_OF_DEPTHS_SELECTED
    ):
        resources[GIFT_OF_DEPTHS_RESOURCE] = 1
    wizard_level = int(class_levels.get("wizard", 0))
    if wizard_level >= 1:
        resources["srd.resource.arcane_recovery"] = 1
    return resources


def _fixed_hp_gain(character: Character, class_name: str) -> int:
    die = int(CLASS_HIT_DICE[class_name].removeprefix("d"))
    average = die // 2 + 1
    con_modifier = _effective_con_modifier_for_levels(character, character.class_levels)
    return max(1, average + con_modifier)


def _fixed_hp_for_single_class(character: Character, class_name: str, level: int) -> int:
    die = int(CLASS_HIT_DICE[class_name].removeprefix("d"))
    con_modifier = _effective_con_modifier_for_levels(character, {class_name: level})
    first_level = max(1, die + con_modifier)
    later_levels = max(0, level - 1) * _fixed_hp_gain(character, class_name)
    return first_level + later_levels


def _subclass_hp_bonus(character: Character) -> int:
    return draconic_resilience_hp_bonus(character)


def _effective_con_modifier_for_levels(character: Character, class_levels: dict[str, int]) -> int:
    con_score = int(character.abilities.get("con", 10))
    if int(class_levels.get("barbarian", 0)) >= 20:
        con_score = min(con_score + 4, 25)
    return (con_score - 10) // 2


def _ability_modifier_from_scores(abilities: dict[str, int], ability: str) -> int:
    return (int(abilities.get(ability, 10)) - 10) // 2


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)

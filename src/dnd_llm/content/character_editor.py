from __future__ import annotations

import re
from dataclasses import dataclass

from dnd_llm.core.models import Character

from .character_gen import STANDARD_ARRAY
from .character_progression import (
    grant_feat,
    grant_skill_expertise,
    grant_warlock_lessons_of_first_ones_origin_feat,
    normalize_class_name,
    normalize_feat_name,
    normalize_skill_choice,
    normalize_skilled_choice,
    normalize_subclass_name,
    replace_class,
    set_divine_order_choice,
    set_druid_circle_land_choice,
    set_druid_primal_order_choice,
    set_hunters_prey_choice,
    set_multiclass_level,
    set_subclass,
    set_warlock_agonizing_blast_choice,
    set_warlock_armor_of_shadows_choice,
    set_warlock_ascendant_step_choice,
    set_warlock_devils_sight_choice,
    set_warlock_eldritch_invocation_choice,
    set_warlock_eldritch_smite_choice,
    set_warlock_eldritch_spear_choice,
    set_warlock_fiendish_vigor_choice,
    set_warlock_gaze_of_two_minds_choice,
    set_warlock_gift_of_depths_choice,
    set_warlock_investment_of_chain_master_choice,
    set_warlock_mask_of_many_faces_choice,
    set_warlock_master_of_myriad_forms_choice,
    set_warlock_misty_visions_choice,
    set_warlock_one_with_shadows_choice,
    set_warlock_otherworldly_leap_choice,
    set_warlock_pact_of_blade_choice,
    set_warlock_pact_of_chain_choice,
    set_warlock_pact_of_tome_choice,
    set_warlock_repelling_blast_choice,
    set_warlock_thirsting_blade_choice,
)

ABILITY_ALIASES = {
    "str": "str",
    "strength": "str",
    "力量": "str",
    "dex": "dex",
    "dexterity": "dex",
    "敏捷": "dex",
    "con": "con",
    "constitution": "con",
    "体质": "con",
    "int": "int",
    "intelligence": "int",
    "智力": "int",
    "wis": "wis",
    "wisdom": "wis",
    "感知": "wis",
    "cha": "cha",
    "charisma": "cha",
    "魅力": "cha",
}

ABILITY_RE = re.compile(
    r"(str|strength|力量|dex|dexterity|敏捷|con|constitution|体质|int|intelligence|智力|wis|wisdom|感知|cha|charisma|魅力)\s*[:=：]?\s*(\d{1,2})",
    re.IGNORECASE,
)
CLASS_RE = re.compile(
    r"(?:class|(?<!多)职业)\s*[:=：]?\s*([A-Za-z]+|[\u4e00-\u9fff]+)\s*(\d{1,2})?",
    re.IGNORECASE,
)
MULTICLASS_RE = re.compile(
    r"(?:multiclass|多职业|兼职)\s*[:=：]?\s*([A-Za-z]+|[\u4e00-\u9fff]+)\s*(\d{1,2})?",
    re.IGNORECASE,
)
FEAT_RE = re.compile(
    r"(?:feat|专长)\s*[:=：]?\s*([A-Za-z_-]+|[\u4e00-\u9fff]+)",
    re.IGNORECASE,
)
SUBCLASS_RE = re.compile(
    r"(?:subclass|子职|子职业)\s*[:=：]?\s*([A-Za-z_-]+|[\u4e00-\u9fff]+)",
    re.IGNORECASE,
)
HUNTERS_PREY_RE = re.compile(
    r"(?:hunter['’]?s\s+prey|猎人猎物)\s*[:=：]?\s*(colossus\s+slayer|horde\s+breaker|[A-Za-z_-]+|[\u4e00-\u9fff]+)",
    re.IGNORECASE,
)
DIVINE_ORDER_RE = re.compile(
    r"(?:divine\s+order|神圣职责|神圣秩序)\s*[:=：]?\s*(protector|thaumaturge|[A-Za-z_-]+|[\u4e00-\u9fff]+)",
    re.IGNORECASE,
)
DRUID_PRIMAL_ORDER_RE = re.compile(
    r"(?:primal\s+order|原初职责|原初秩序|自然职责)\s*[:=：]?\s*(magician|warden|[A-Za-z_-]+|[\u4e00-\u9fff]+)",
    re.IGNORECASE,
)
DRUID_CIRCLE_LAND_RE = re.compile(
    r"(?:circle\s+of\s+the\s+land\s+choice|land\s+choice|land\s+type|大地地形|结社地形|地形选择)\s*[:=：]?\s*"
    r"(arid|polar|temperate|tropical|desert|dry|arctic|[A-Za-z_-]+|[\u4e00-\u9fff]+)",
    re.IGNORECASE,
)
WARLOCK_ELDRITCH_INVOCATION_RE = re.compile(
    r"(?:eldritch\s+invocation|魔能祈唤|魔能祷唤|异界祈唤)\s*[:=：]?\s*(eldritch\s+mind|魔能心智|异界心智|专注优势)",
    re.IGNORECASE,
)
WARLOCK_DEVILS_SIGHT_RE = re.compile(
    r"(?:eldritch\s+invocation|魔能祈唤|魔能祷唤|异界祈唤)\s*[:=：]?\s*(devil['’]?s\s+sight|devils?\s+sight|魔鬼视界|魔鬼视觉|恶魔视界)",
    re.IGNORECASE,
)
WARLOCK_AGONIZING_BLAST_RE = re.compile(
    r"(?:(?:eldritch\s+invocation|魔能祈唤|魔能祷唤|异界祈唤)\s*[:=：]?\s*)?(?:agonizing\s+blast|苦痛魔爆|痛苦魔爆)\s*(?:[:=：]|\s+)(eldritch\s+blast|魔能爆|邪能冲击)",
    re.IGNORECASE,
)
WARLOCK_ELDRITCH_SPEAR_RE = re.compile(
    r"(?:(?:eldritch\s+invocation|魔能祈唤|魔能祷唤|异界祈唤)\s*[:=：]?\s*)?(?:eldritch\s+spear|魔能长矛|异界长矛)\s*(?:[:=：]|\s+)(eldritch\s+blast|魔能爆|邪能冲击)",
    re.IGNORECASE,
)
WARLOCK_REPELLING_BLAST_RE = re.compile(
    r"(?:(?:eldritch\s+invocation|魔能祈唤|魔能祷唤|异界祈唤)\s*[:=：]?\s*)?(?:repelling\s+blast|斥退魔爆|推斥魔爆)\s*(?:[:=：]|\s+)(eldritch\s+blast|魔能爆|邪能冲击)",
    re.IGNORECASE,
)
WARLOCK_ASCENDANT_STEP_RE = re.compile(
    r"(?:eldritch\s+invocation|魔能祈唤|魔能祷唤|异界祈唤)\s*[:=：]?\s*"
    r"(ascendant\s+step|升腾步伐|升阶步伐|飞升步伐)",
    re.IGNORECASE,
)
WARLOCK_ARMOR_OF_SHADOWS_RE = re.compile(
    r"(?:eldritch\s+invocation|魔能祈唤|魔能祷唤|异界祈唤)\s*[:=：]?\s*(armor\s+of\s+shadows|影之护甲|阴影护甲|暗影护甲)",
    re.IGNORECASE,
)
WARLOCK_FIENDISH_VIGOR_RE = re.compile(
    r"(?:eldritch\s+invocation|魔能祈唤|魔能祷唤|异界祈唤)\s*[:=：]?\s*(fiendish\s+vigor|邪魔活力|魔鬼活力|恶魔活力)",
    re.IGNORECASE,
)
WARLOCK_MASK_OF_MANY_FACES_RE = re.compile(
    r"(?:eldritch\s+invocation|魔能祈唤|魔能祷唤|异界祈唤)\s*[:=：]?\s*(mask\s+of\s+many\s+faces|千面面具|众面假面)",
    re.IGNORECASE,
)
WARLOCK_MISTY_VISIONS_RE = re.compile(
    r"(?:eldritch\s+invocation|魔能祈唤|魔能祷唤|异界祈唤)\s*[:=：]?\s*(misty\s+visions|迷雾幻象|雾影幻象)",
    re.IGNORECASE,
)
WARLOCK_ONE_WITH_SHADOWS_RE = re.compile(
    r"(?:eldritch\s+invocation|魔能祈唤|魔能祷唤|异界祈唤)\s*[:=：]?\s*"
    r"(one\s+with\s+shadows|影中合一|与影合一|融入阴影)",
    re.IGNORECASE,
)
WARLOCK_OTHERWORLDLY_LEAP_RE = re.compile(
    r"(?:eldritch\s+invocation|魔能祈唤|魔能祷唤|异界祈唤)\s*[:=：]?\s*(otherworldly\s+leap|异界跃动|异界跳跃)",
    re.IGNORECASE,
)
WARLOCK_MASTER_OF_MYRIAD_FORMS_RE = re.compile(
    r"(?:eldritch\s+invocation|魔能祈唤|魔能祷唤|异界祈唤)\s*[:=：]?\s*"
    r"(master\s+of\s+myriad\s+forms|万形大师|千形大师|百变大师)",
    re.IGNORECASE,
)
WARLOCK_GIFT_OF_DEPTHS_RE = re.compile(
    r"(?:eldritch\s+invocation|魔能祈唤|魔能祷唤|异界祈唤)\s*[:=：]?\s*"
    r"(gift\s+of\s+the\s+depths|深海馈赠|深渊馈赠|深海赠礼)",
    re.IGNORECASE,
)
WARLOCK_GAZE_OF_TWO_MINDS_RE = re.compile(
    r"(?:eldritch\s+invocation|魔能祈唤|魔能祷唤|异界祈唤)\s*[:=：]?\s*"
    r"(gaze\s+of\s+two\s+minds|双心凝视|双重心灵凝视|双心视界)",
    re.IGNORECASE,
)
WARLOCK_INVESTMENT_OF_CHAIN_MASTER_RE = re.compile(
    r"(?:eldritch\s+invocation|魔能祈唤|魔能祷唤|异界祈唤)\s*[:=：]?\s*"
    r"(investment\s+of\s+the\s+chain\s+master|锁链大师投资|链主投资|链契大师投资)",
    re.IGNORECASE,
)
WARLOCK_LESSONS_OF_FIRST_ONES_RE = re.compile(
    r"(?:eldritch\s+invocation|魔能祈唤|魔能祷唤|异界祈唤)\s*[:=：]?\s*"
    r"(?:lessons\s+of\s+the\s+first\s+ones|初民训诲|初民教诲|始源训诲)"
    r"\s*(?:[:=：]|\s+)"
    r"(alert|skilled|magic\s+initiate|savage\s+attacker|警觉|熟练|魔法学徒|凶蛮攻击者)",
    re.IGNORECASE,
)
WARLOCK_PACT_OF_CHAIN_RE = re.compile(
    r"(?:eldritch\s+invocation|魔能祈唤|魔能祷唤|异界祈唤)\s*[:=：]?\s*"
    r"(pact\s+of\s+the\s+chain|pact\s+of\s+chain|链契|锁链契约|链之契约)",
    re.IGNORECASE,
)
WARLOCK_PACT_OF_BLADE_RE = re.compile(
    r"(?:eldritch\s+invocation|魔能祈唤|魔能祷唤|异界祈唤)\s*[:=：]?\s*"
    r"(pact\s+of\s+the\s+blade|pact\s+of\s+blade|刃契|刀锋契约|刃之契约)",
    re.IGNORECASE,
)
WARLOCK_PACT_OF_TOME_RE = re.compile(
    r"(?:eldritch\s+invocation|魔能祈唤|魔能祷唤|异界祈唤)\s*[:=：]?\s*"
    r"(pact\s+of\s+the\s+tome|pact\s+of\s+tome|书契|魔典契约|书之契约|影书契约)",
    re.IGNORECASE,
)
WARLOCK_THIRSTING_BLADE_RE = re.compile(
    r"(?:eldritch\s+invocation|魔能祈唤|魔能祷唤|异界祈唤)\s*[:=：]?\s*"
    r"(thirsting\s+blade|渴饮魔刃|渴血之刃|饥渴之刃)",
    re.IGNORECASE,
)
WARLOCK_ELDRITCH_SMITE_RE = re.compile(
    r"(?:eldritch\s+invocation|魔能祈唤|魔能祷唤|异界祈唤)\s*[:=：]?\s*"
    r"(eldritch\s+smite|魔能斩击|魔能重击|异界斩击)",
    re.IGNORECASE,
)
EXPERTISE_RE = re.compile(
    r"(?:\bexpertise\b|技能专精|专精)\s*[:=：]?",
    re.IGNORECASE,
)
EDIT_MARKER_RE = re.compile(
    r"(?:\bfeat\b|专长|\bclass\b|(?<!多)职业|\bmulticlass\b|多职业|兼职|\bsubclass\b|子职|子职业|hunter['’]?s\s+prey|猎人猎物|divine\s+order|神圣职责|神圣秩序|primal\s+order|原初职责|原初秩序|自然职责|circle\s+of\s+the\s+land\s+choice|land\s+choice|land\s+type|大地地形|结社地形|地形选择|eldritch\s+invocation|魔能祈唤|魔能祷唤|异界祈唤|lessons\s+of\s+the\s+first\s+ones|初民训诲|初民教诲|始源训诲|pact\s+of\s+the\s+chain|pact\s+of\s+chain|链契|锁链契约|链之契约|pact\s+of\s+the\s+blade|pact\s+of\s+blade|刃契|刀锋契约|刃之契约|pact\s+of\s+the\s+tome|pact\s+of\s+tome|书契|魔典契约|书之契约|影书契约|investment\s+of\s+the\s+chain\s+master|锁链大师投资|链主投资|链契大师投资|thirsting\s+blade|渴饮魔刃|渴血之刃|饥渴之刃|eldritch\s+smite|魔能斩击|魔能重击|异界斩击|ascendant\s+step|升腾步伐|升阶步伐|飞升步伐|one\s+with\s+shadows|影中合一|与影合一|融入阴影|master\s+of\s+myriad\s+forms|万形大师|千形大师|百变大师|gift\s+of\s+the\s+depths|深海馈赠|深渊馈赠|深海赠礼|gaze\s+of\s+two\s+minds|双心凝视|双重心灵凝视|双心视界|\bexpertise\b|技能专精|专精)",
    re.IGNORECASE,
)
SKILLED_CHOICE_IGNORE = {
    "skill",
    "skills",
    "tool",
    "tools",
    "技能",
    "工具",
    "选择",
    "任选",
    "任意",
    "choose",
}


@dataclass
class CharacterEditResult:
    accepted: bool
    character: Character | None = None
    errors: list[str] | None = None


def apply_natural_language_character_edit(
    character: Character,
    text: str,
) -> CharacterEditResult:
    edited = Character.from_dict(character.to_dict())
    errors: list[str] = []
    ability_updates = _parse_abilities(text)
    if ability_updates:
        candidate = dict(edited.abilities)
        candidate.update(ability_updates)
        if sorted(candidate.values(), reverse=True) != STANDARD_ARRAY:
            errors.append("属性必须使用标准数组 15/14/13/12/10/8")
        else:
            edited.abilities = candidate

    class_match = CLASS_RE.search(text)
    if class_match:
        normalized = normalize_class_name(class_match.group(1))
        if normalized is None:
            errors.append(f"不支持的 SRD 基础职业：{class_match.group(1)}")
        else:
            result = replace_class(edited, normalized, level=_level_from_match(class_match))
            errors.extend(result.errors)

    for multiclass_match in MULTICLASS_RE.finditer(text):
        normalized = normalize_class_name(multiclass_match.group(1))
        if normalized is None:
            errors.append(f"不支持的 SRD 基础职业：{multiclass_match.group(1)}")
            continue
        result = set_multiclass_level(
            edited,
            normalized,
            level=_level_from_match(multiclass_match),
        )
        errors.extend(result.errors)

    for subclass_match in SUBCLASS_RE.finditer(text):
        subclass_selection = normalize_subclass_name(subclass_match.group(1))
        if subclass_selection is None:
            errors.append(f"不支持的 SRD 子职：{subclass_match.group(1)}")
            continue
        class_name, subclass_id = subclass_selection
        result = set_subclass(edited, class_name, subclass_id)
        errors.extend(result.errors)

    for hunters_prey_match in HUNTERS_PREY_RE.finditer(text):
        result = set_hunters_prey_choice(edited, hunters_prey_match.group(1).strip())
        errors.extend(result.errors)

    for divine_order_match in DIVINE_ORDER_RE.finditer(text):
        result = set_divine_order_choice(edited, divine_order_match.group(1).strip())
        errors.extend(result.errors)

    for druid_primal_order_match in DRUID_PRIMAL_ORDER_RE.finditer(text):
        result = set_druid_primal_order_choice(
            edited,
            druid_primal_order_match.group(1).strip(),
        )
        errors.extend(result.errors)

    for druid_circle_land_match in DRUID_CIRCLE_LAND_RE.finditer(text):
        result = set_druid_circle_land_choice(
            edited,
            druid_circle_land_match.group(1).strip(),
        )
        errors.extend(result.errors)

    for devils_sight_match in WARLOCK_DEVILS_SIGHT_RE.finditer(text):
        result = set_warlock_devils_sight_choice(
            edited,
            devils_sight_match.group(1).strip(),
        )
        errors.extend(result.errors)

    for agonizing_blast_match in WARLOCK_AGONIZING_BLAST_RE.finditer(text):
        result = set_warlock_agonizing_blast_choice(
            edited,
            agonizing_blast_match.group(1).strip(),
        )
        errors.extend(result.errors)

    for eldritch_spear_match in WARLOCK_ELDRITCH_SPEAR_RE.finditer(text):
        result = set_warlock_eldritch_spear_choice(
            edited,
            eldritch_spear_match.group(1).strip(),
        )
        errors.extend(result.errors)

    for repelling_blast_match in WARLOCK_REPELLING_BLAST_RE.finditer(text):
        result = set_warlock_repelling_blast_choice(
            edited,
            repelling_blast_match.group(1).strip(),
        )
        errors.extend(result.errors)

    for ascendant_step_match in WARLOCK_ASCENDANT_STEP_RE.finditer(text):
        result = set_warlock_ascendant_step_choice(
            edited,
            ascendant_step_match.group(1).strip(),
        )
        errors.extend(result.errors)

    for armor_of_shadows_match in WARLOCK_ARMOR_OF_SHADOWS_RE.finditer(text):
        result = set_warlock_armor_of_shadows_choice(
            edited,
            armor_of_shadows_match.group(1).strip(),
        )
        errors.extend(result.errors)

    for fiendish_vigor_match in WARLOCK_FIENDISH_VIGOR_RE.finditer(text):
        result = set_warlock_fiendish_vigor_choice(
            edited,
            fiendish_vigor_match.group(1).strip(),
        )
        errors.extend(result.errors)

    for mask_of_many_faces_match in WARLOCK_MASK_OF_MANY_FACES_RE.finditer(text):
        result = set_warlock_mask_of_many_faces_choice(
            edited,
            mask_of_many_faces_match.group(1).strip(),
        )
        errors.extend(result.errors)

    for misty_visions_match in WARLOCK_MISTY_VISIONS_RE.finditer(text):
        result = set_warlock_misty_visions_choice(
            edited,
            misty_visions_match.group(1).strip(),
        )
        errors.extend(result.errors)

    for one_with_shadows_match in WARLOCK_ONE_WITH_SHADOWS_RE.finditer(text):
        result = set_warlock_one_with_shadows_choice(
            edited,
            one_with_shadows_match.group(1).strip(),
        )
        errors.extend(result.errors)

    for otherworldly_leap_match in WARLOCK_OTHERWORLDLY_LEAP_RE.finditer(text):
        result = set_warlock_otherworldly_leap_choice(
            edited,
            otherworldly_leap_match.group(1).strip(),
        )
        errors.extend(result.errors)

    for master_of_myriad_forms_match in WARLOCK_MASTER_OF_MYRIAD_FORMS_RE.finditer(text):
        result = set_warlock_master_of_myriad_forms_choice(
            edited,
            master_of_myriad_forms_match.group(1).strip(),
        )
        errors.extend(result.errors)

    for gift_of_depths_match in WARLOCK_GIFT_OF_DEPTHS_RE.finditer(text):
        result = set_warlock_gift_of_depths_choice(
            edited,
            gift_of_depths_match.group(1).strip(),
        )
        errors.extend(result.errors)

    for gaze_of_two_minds_match in WARLOCK_GAZE_OF_TWO_MINDS_RE.finditer(text):
        result = set_warlock_gaze_of_two_minds_choice(
            edited,
            gaze_of_two_minds_match.group(1).strip(),
        )
        errors.extend(result.errors)

    for lessons_match in WARLOCK_LESSONS_OF_FIRST_ONES_RE.finditer(text):
        choices = _skilled_choices_from_segment(_segment_after_match(text, lessons_match))
        result = grant_warlock_lessons_of_first_ones_origin_feat(
            edited,
            lessons_match.group(1).strip(),
            choices=choices,
        )
        errors.extend(result.errors)

    for pact_of_chain_match in WARLOCK_PACT_OF_CHAIN_RE.finditer(text):
        result = set_warlock_pact_of_chain_choice(
            edited,
            pact_of_chain_match.group(1).strip(),
        )
        errors.extend(result.errors)

    for investment_match in WARLOCK_INVESTMENT_OF_CHAIN_MASTER_RE.finditer(text):
        result = set_warlock_investment_of_chain_master_choice(
            edited,
            investment_match.group(1).strip(),
        )
        errors.extend(result.errors)

    for pact_of_blade_match in WARLOCK_PACT_OF_BLADE_RE.finditer(text):
        result = set_warlock_pact_of_blade_choice(
            edited,
            pact_of_blade_match.group(1).strip(),
        )
        errors.extend(result.errors)

    for eldritch_smite_match in WARLOCK_ELDRITCH_SMITE_RE.finditer(text):
        result = set_warlock_eldritch_smite_choice(
            edited,
            eldritch_smite_match.group(1).strip(),
        )
        errors.extend(result.errors)

    for thirsting_blade_match in WARLOCK_THIRSTING_BLADE_RE.finditer(text):
        result = set_warlock_thirsting_blade_choice(
            edited,
            thirsting_blade_match.group(1).strip(),
        )
        errors.extend(result.errors)

    for pact_of_tome_match in WARLOCK_PACT_OF_TOME_RE.finditer(text):
        cantrips, rituals = _pact_tome_choices_from_segment(
            _segment_after_match(text, pact_of_tome_match)
        )
        result = set_warlock_pact_of_tome_choice(
            edited,
            pact_of_tome_match.group(1).strip(),
            cantrips=cantrips,
            rituals=rituals,
        )
        errors.extend(result.errors)

    for invocation_match in WARLOCK_ELDRITCH_INVOCATION_RE.finditer(text):
        result = set_warlock_eldritch_invocation_choice(
            edited,
            invocation_match.group(1).strip(),
        )
        errors.extend(result.errors)

    for feat_match in FEAT_RE.finditer(text):
        feat_id = normalize_feat_name(feat_match.group(1))
        if feat_id is None:
            errors.append(f"不支持的专长：{feat_match.group(1)}")
            continue
        choices = _skilled_choices_from_segment(_segment_after_match(text, feat_match))
        result = grant_feat(edited, feat_id, choices=choices)
        errors.extend(result.errors)

    for expertise_match in EXPERTISE_RE.finditer(text):
        choices = _expertise_choices_from_segment(_segment_after_match(text, expertise_match))
        result = grant_skill_expertise(edited, choices)
        errors.extend(result.errors)

    if errors:
        return CharacterEditResult(accepted=False, errors=errors)
    return CharacterEditResult(accepted=True, character=edited, errors=[])


def _parse_abilities(text: str) -> dict[str, int]:
    updates: dict[str, int] = {}
    for match in ABILITY_RE.finditer(text):
        alias = match.group(1).casefold()
        ability = ABILITY_ALIASES[alias]
        updates[ability] = int(match.group(2))
    return updates


def _level_from_match(match: re.Match[str]) -> int:
    raw_level = match.group(2) if len(match.groups()) >= 2 else None
    return int(raw_level) if raw_level is not None else 1


def _segment_after_match(text: str, match: re.Match[str]) -> str:
    next_match = EDIT_MARKER_RE.search(text, match.end())
    if next_match is None:
        return text[match.end() :]
    return text[match.end() : next_match.start()]


def _skilled_choices_from_segment(segment: str) -> list[str]:
    choices: list[str] = []
    for chunk in re.split(r"[、,，;；/:：]+", segment):
        stripped = chunk.strip(" \t\r\n()（）[]【】")
        if not stripped:
            continue
        if normalize_skilled_choice(stripped) is not None:
            choices.append(stripped)
            continue
        for token in re.split(r"\s+", stripped):
            token = token.strip(" \t\r\n()（）[]【】")
            if not token or token.casefold() in SKILLED_CHOICE_IGNORE:
                continue
            choices.append(token)
    return choices


def _expertise_choices_from_segment(segment: str) -> list[str]:
    choices: list[str] = []
    for chunk in re.split(r"[、,，;；/:：]+", segment):
        stripped = chunk.strip(" \t\r\n()（）[]【】")
        if not stripped:
            continue
        if normalize_skill_choice(stripped) is not None:
            choices.append(stripped)
            continue
        for token in re.split(r"\s+", stripped):
            token = token.strip(" \t\r\n()（）[]【】")
            if not token or token.casefold() in SKILLED_CHOICE_IGNORE:
                continue
            choices.append(token)
    return choices


def _pact_tome_choices_from_segment(segment: str) -> tuple[list[str], list[str]]:
    cantrips = _labeled_spell_choices(
        segment,
        r"(?:cantrips?|戏法)",
        r"(?:ritual\s+spells?|rituals?|1\s*环\s*ritual|1\s*环\s*仪式|仪式)",
    )
    rituals = _labeled_spell_choices(
        segment,
        r"(?:ritual\s+spells?|rituals?|1\s*环\s*ritual|1\s*环\s*仪式|仪式)",
        r"(?:cantrips?|戏法)",
    )
    return cantrips, rituals


def _labeled_spell_choices(segment: str, label_pattern: str, stop_pattern: str) -> list[str]:
    match = re.search(
        rf"{label_pattern}\s*[:=：]?\s*(.*?)(?={stop_pattern}\s*[:=：]?|$)",
        segment,
        re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        return []
    choices: list[str] = []
    for chunk in re.split(r"[、,，;；/]+", match.group(1)):
        stripped = chunk.strip(" \t\r\n()（）[]【】")
        if stripped:
            choices.append(stripped)
    return choices

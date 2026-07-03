from __future__ import annotations

from dnd_llm.content.character_editor import apply_natural_language_character_edit
from dnd_llm.content.character_gen import default_fighter
from dnd_llm.core.rules.class_features import (
    has_warlock_eldritch_smite,
    has_warlock_gaze_of_two_minds,
    has_warlock_investment_of_chain_master,
    has_warlock_pact_of_blade,
    has_warlock_pact_of_tome,
    has_warlock_thirsting_blade,
    ranger_roving_climb_speed_ft,
    ranger_roving_speed_bonus,
    ranger_roving_swim_speed_ft,
    warlock_devils_sight_range_ft,
    warlock_gift_of_depths_swim_speed_ft,
)


def test_default_fighter_equipment_uses_srd_item_ids() -> None:
    character = default_fighter("pc1", "Penn")

    assert character.equipment == ["srd.chain_mail", "srd.shield", "srd.longsword"]
    assert character.actions == ["srd.longsword_attack", "srd.second_wind", "srd.move"]
    assert character.resources == {"srd.resource.second_wind": 2}


def test_natural_language_character_edit_accepts_standard_array_and_class() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 牧师 力量 12 敏捷 14 体质 13 智力 10 感知 15 魅力 8",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"cleric": 1}
    assert result.character.abilities["wis"] == 15
    assert "srd.cure_wounds" in result.character.actions
    assert "srd.divine_order" in result.character.actions
    assert result.character.feature_choices == {}
    assert character.class_levels == {"fighter": 1}


def test_natural_language_character_edit_assigns_cleric_divine_order_choice() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 牧师 divine order thaumaturge",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"cleric": 1}
    assert result.character.actions == ["srd.cure_wounds", "srd.divine_order"]
    assert result.character.feature_choices == {"cleric.divine_order": "thaumaturge"}


def test_natural_language_character_edit_rejects_cleric_divine_order_without_cleric() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "神圣职责 奇术师")

    assert result.accepted is False
    assert result.character is None
    assert result.errors is not None
    assert "Divine Order 选项需要 Cleric 1" in result.errors


def test_natural_language_character_edit_rejects_invalid_numbers_and_class() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 超级英雄 力量 18 敏捷 18",
    )

    assert result.accepted is False
    assert result.character is None
    assert result.errors is not None
    assert any("标准数组" in error for error in result.errors)
    assert any("不支持" in error for error in result.errors)


def test_natural_language_character_edit_assigns_caster_starting_action() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 法师")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"wizard": 1}
    assert result.character.actions == [
        "srd.fire_bolt",
        "srd.ritual_adept",
        "srd.arcane_recovery",
    ]
    assert result.character.known_spells == []
    assert result.character.prepared_spells == []
    assert result.character.resources["srd.resource.arcane_recovery"] == 1


def test_natural_language_character_edit_assigns_warlock_cantrip() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 邪术师3")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 3}
    assert result.character.actions == [
        "srd.eldritch_blast",
        "srd.eldritch_invocations",
        "srd.magical_cunning",
    ]
    assert "srd.eldritch_mind" not in result.character.actions
    assert result.character.resources["srd.resource.magical_cunning"] == 1
    assert result.character.spell_slots == {"2": 2}
    assert result.character.spell_slots_max == {"2": 2}


def test_natural_language_character_edit_assigns_explicit_eldritch_mind_invocation() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock1 eldritch invocation eldritch mind",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 1}
    assert result.character.feature_choices == {"warlock.eldritch_invocation": "eldritch_mind"}
    assert "srd.eldritch_invocations" in result.character.actions
    assert "srd.eldritch_mind" in result.character.actions


def test_natural_language_character_edit_assigns_explicit_devils_sight_invocation() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock2 eldritch invocation devil's sight",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 2}
    assert result.character.feature_choices == {
        "warlock.eldritch_invocation.devils_sight": "selected"
    }
    assert "srd.eldritch_invocations" in result.character.actions
    assert "srd.devils_sight" in result.character.actions
    assert warlock_devils_sight_range_ft(result.character) == 120


def test_natural_language_character_edit_rejects_devils_sight_before_warlock_2() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock1 eldritch invocation devil's sight",
    )

    assert result.accepted is False
    assert result.errors == ["Devil's Sight 需要 Warlock 2"]


def test_natural_language_character_edit_assigns_lessons_origin_alert_invocation() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock2 eldritch invocation lessons of the first ones alert",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 2}
    assert result.character.feature_choices == {
        "warlock.eldritch_invocation.lessons_of_the_first_ones.alert": "selected"
    }
    assert result.character.feats == ["alert"]
    assert "srd.lessons_of_the_first_ones" in result.character.actions


def test_lessons_origin_feat_does_not_consume_ordinary_feat_slot() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        (
            "职业 warlock4 eldritch invocation lessons of the first ones alert "
            "feat skilled stealth, perception, thieves tools"
        ),
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.feats == ["alert", "skilled"]
    assert result.character.skill_proficiencies == ["stealth", "perception"]
    assert result.character.tool_proficiencies == ["thieves_tools"]


def test_natural_language_character_edit_assigns_lessons_origin_skilled_invocation() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        (
            "职业 warlock2 eldritch invocation lessons of the first ones skilled "
            "stealth, perception, thieves tools"
        ),
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.feature_choices == {
        "warlock.eldritch_invocation.lessons_of_the_first_ones.skilled": "selected"
    }
    assert result.character.feats == ["skilled"]
    assert result.character.skill_proficiencies == ["stealth", "perception"]
    assert result.character.tool_proficiencies == ["thieves_tools"]
    assert "srd.lessons_of_the_first_ones" in result.character.actions


def test_natural_language_character_edit_rejects_lessons_before_warlock_2() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock1 eldritch invocation lessons of the first ones alert",
    )

    assert result.accepted is False
    assert result.errors == ["Lessons of the First Ones 需要 Warlock 2"]


def test_natural_language_character_edit_rejects_unimplemented_lessons_origin_feat() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock2 eldritch invocation lessons of the first ones magic initiate",
    )

    assert result.accepted is False
    assert result.errors == ["Lessons of the First Ones 尚未接入该 SRD Origin feat：magic initiate"]


def test_natural_language_character_edit_assigns_pact_of_the_chain_invocation() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock1 eldritch invocation pact of the chain",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 1}
    assert result.character.feature_choices == {
        "warlock.eldritch_invocation.pact_of_the_chain": "selected"
    }
    assert "srd.pact_of_the_chain" in result.character.actions
    assert "srd.pact_of_the_chain_find_familiar" in result.character.actions
    assert result.character.known_spells == ["srd.spell.find_familiar"]


def test_natural_language_character_edit_rejects_pact_of_the_chain_without_warlock() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "eldritch invocation pact of the chain",
    )

    assert result.accepted is False
    assert result.errors == ["Pact of the Chain 需要 Warlock 1"]


def test_natural_language_character_edit_assigns_investment_of_chain_master_invocation() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock5 eldritch invocation pact of the chain "
        "eldritch invocation investment of the chain master",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 5}
    assert result.character.feature_choices == {
        "warlock.eldritch_invocation.pact_of_the_chain": "selected",
        "warlock.eldritch_invocation.investment_of_the_chain_master": "selected",
    }
    assert "srd.pact_of_the_chain" in result.character.actions
    assert "srd.pact_of_the_chain_find_familiar" in result.character.actions
    assert "srd.investment_of_the_chain_master" in result.character.actions
    assert has_warlock_investment_of_chain_master(result.character) is True


def test_natural_language_character_edit_rejects_investment_before_warlock_5() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock4 eldritch invocation pact of the chain "
        "eldritch invocation investment of the chain master",
    )

    assert result.accepted is False
    assert result.errors == ["Investment of the Chain Master 需要 Warlock 5"]


def test_natural_language_character_edit_rejects_investment_without_pact_chain() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock5 eldritch invocation investment of the chain master",
    )

    assert result.accepted is False
    assert result.errors == ["Investment of the Chain Master 需要 Pact of the Chain invocation"]


def test_natural_language_character_edit_removes_investment_when_level_drops() -> None:
    character = default_fighter("pc1", "Penn")
    warlock_result = apply_natural_language_character_edit(
        character,
        "职业 warlock5 eldritch invocation pact of the chain "
        "eldritch invocation investment of the chain master",
    )
    assert warlock_result.accepted is True
    assert warlock_result.character is not None

    lower_level_result = apply_natural_language_character_edit(
        warlock_result.character,
        "职业 warlock4",
    )

    assert lower_level_result.accepted is True
    assert lower_level_result.character is not None
    assert "srd.investment_of_the_chain_master" not in lower_level_result.character.actions
    assert (
        "warlock.eldritch_invocation.investment_of_the_chain_master"
        not in lower_level_result.character.feature_choices
    )
    assert has_warlock_investment_of_chain_master(lower_level_result.character) is False


def test_natural_language_character_edit_assigns_pact_of_the_blade_invocation() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock1 eldritch invocation pact of the blade",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 1}
    assert result.character.feature_choices == {
        "warlock.eldritch_invocation.pact_of_the_blade": "selected"
    }
    assert "srd.pact_of_the_blade" in result.character.actions
    assert "srd.pact_of_the_blade_weapon" in result.character.actions
    assert "srd.longsword_attack" not in result.character.actions
    assert has_warlock_pact_of_blade(result.character) is True


def test_natural_language_character_edit_rejects_pact_of_the_blade_without_warlock() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "eldritch invocation pact of the blade",
    )

    assert result.accepted is False
    assert result.errors == ["Pact of the Blade 需要 Warlock 1"]


def test_natural_language_character_edit_removes_pact_of_the_blade_when_class_changes() -> None:
    character = default_fighter("pc1", "Penn")
    warlock_result = apply_natural_language_character_edit(
        character,
        "职业 warlock1 eldritch invocation pact of the blade",
    )
    assert warlock_result.accepted is True
    assert warlock_result.character is not None

    fighter_result = apply_natural_language_character_edit(
        warlock_result.character, "职业 fighter1"
    )

    assert fighter_result.accepted is True
    assert fighter_result.character is not None
    assert "srd.pact_of_the_blade" not in fighter_result.character.actions
    assert "srd.pact_of_the_blade_weapon" not in fighter_result.character.actions
    assert (
        "warlock.eldritch_invocation.pact_of_the_blade"
        not in fighter_result.character.feature_choices
    )
    assert has_warlock_pact_of_blade(fighter_result.character) is False


def test_natural_language_character_edit_assigns_thirsting_blade_invocation() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock5 eldritch invocation pact of the blade eldritch invocation thirsting blade",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 5}
    assert result.character.feature_choices == {
        "warlock.eldritch_invocation.pact_of_the_blade": "selected",
        "warlock.eldritch_invocation.thirsting_blade": "selected",
    }
    assert "srd.pact_of_the_blade" in result.character.actions
    assert "srd.pact_of_the_blade_weapon" in result.character.actions
    assert "srd.thirsting_blade" in result.character.actions
    assert has_warlock_thirsting_blade(result.character) is True


def test_natural_language_character_edit_rejects_thirsting_blade_before_warlock_5() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock4 eldritch invocation pact of the blade eldritch invocation thirsting blade",
    )

    assert result.accepted is False
    assert result.errors == ["Thirsting Blade 需要 Warlock 5"]


def test_natural_language_character_edit_rejects_thirsting_blade_without_pact_blade() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock5 eldritch invocation thirsting blade",
    )

    assert result.accepted is False
    assert result.errors == ["Thirsting Blade 需要 Pact of the Blade invocation"]


def test_natural_language_character_edit_removes_thirsting_blade_when_pact_blade_missing() -> None:
    character = default_fighter("pc1", "Penn")
    warlock_result = apply_natural_language_character_edit(
        character,
        "职业 warlock5 eldritch invocation pact of the blade eldritch invocation thirsting blade",
    )
    assert warlock_result.accepted is True
    assert warlock_result.character is not None

    lower_level_result = apply_natural_language_character_edit(
        warlock_result.character,
        "职业 warlock4",
    )

    assert lower_level_result.accepted is True
    assert lower_level_result.character is not None
    assert "srd.thirsting_blade" not in lower_level_result.character.actions
    assert (
        "warlock.eldritch_invocation.thirsting_blade"
        not in lower_level_result.character.feature_choices
    )
    assert has_warlock_thirsting_blade(lower_level_result.character) is False


def test_natural_language_character_edit_assigns_eldritch_smite_invocation() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock5 eldritch invocation pact of the blade eldritch invocation eldritch smite",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 5}
    assert result.character.feature_choices == {
        "warlock.eldritch_invocation.pact_of_the_blade": "selected",
        "warlock.eldritch_invocation.eldritch_smite": "selected",
    }
    assert "srd.pact_of_the_blade" in result.character.actions
    assert "srd.pact_of_the_blade_weapon" in result.character.actions
    assert "srd.eldritch_smite" in result.character.actions
    assert has_warlock_eldritch_smite(result.character) is True


def test_natural_language_character_edit_rejects_eldritch_smite_before_warlock_5() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock4 eldritch invocation pact of the blade eldritch invocation eldritch smite",
    )

    assert result.accepted is False
    assert result.errors == ["Eldritch Smite 需要 Warlock 5"]


def test_natural_language_character_edit_rejects_eldritch_smite_without_pact_blade() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock5 eldritch invocation eldritch smite",
    )

    assert result.accepted is False
    assert result.errors == ["Eldritch Smite 需要 Pact of the Blade invocation"]


def test_natural_language_character_edit_removes_eldritch_smite_when_pact_blade_missing() -> None:
    character = default_fighter("pc1", "Penn")
    warlock_result = apply_natural_language_character_edit(
        character,
        "职业 warlock5 eldritch invocation pact of the blade eldritch invocation eldritch smite",
    )
    assert warlock_result.accepted is True
    assert warlock_result.character is not None

    lower_level_result = apply_natural_language_character_edit(
        warlock_result.character,
        "职业 warlock4",
    )

    assert lower_level_result.accepted is True
    assert lower_level_result.character is not None
    assert "srd.eldritch_smite" not in lower_level_result.character.actions
    assert (
        "warlock.eldritch_invocation.eldritch_smite"
        not in lower_level_result.character.feature_choices
    )
    assert has_warlock_eldritch_smite(lower_level_result.character) is False


def test_natural_language_character_edit_assigns_pact_of_the_tome_invocation() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock1 eldritch invocation pact of the tome "
        "cantrips fire bolt, guidance, mage hand "
        "rituals detect magic, speak with animals",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 1}
    assert result.character.feature_choices == {
        "warlock.eldritch_invocation.pact_of_the_tome": "selected",
        "warlock.eldritch_invocation.pact_of_the_tome.cantrip.1": "srd.spell.fire_bolt",
        "warlock.eldritch_invocation.pact_of_the_tome.cantrip.2": "srd.spell.guidance",
        "warlock.eldritch_invocation.pact_of_the_tome.cantrip.3": "srd.spell.mage_hand",
        "warlock.eldritch_invocation.pact_of_the_tome.ritual.1": "srd.spell.detect_magic",
        "warlock.eldritch_invocation.pact_of_the_tome.ritual.2": "srd.spell.speak_with_animals",
    }
    assert "srd.pact_of_the_tome" in result.character.actions
    assert "srd.fire_bolt" in result.character.actions
    assert "srd.guidance" in result.character.actions
    assert "srd.mage_hand" in result.character.actions
    assert "srd.detect_magic" in result.character.actions
    assert "srd.speak_with_animals" in result.character.actions
    assert result.character.prepared_spells == [
        "srd.spell.fire_bolt",
        "srd.spell.guidance",
        "srd.spell.mage_hand",
        "srd.spell.detect_magic",
        "srd.spell.speak_with_animals",
    ]
    assert result.character.known_spells == []
    assert has_warlock_pact_of_tome(result.character) is True


def test_natural_language_character_edit_rejects_pact_of_the_tome_without_warlock() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "eldritch invocation pact of the tome "
        "cantrips fire bolt, guidance, mage hand rituals detect magic, speak with animals",
    )

    assert result.accepted is False
    assert result.errors == ["Pact of the Tome 需要 Warlock 1"]


def test_natural_language_character_edit_rejects_pact_of_the_tome_invalid_spell() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock1 eldritch invocation pact of the tome "
        "cantrips fire bolt, guidance, imaginary bolt rituals detect magic, speak with animals",
    )

    assert result.accepted is False
    assert result.errors == ["Pact of the Tome 不支持的 SRD cantrip：imaginary bolt"]


def test_natural_language_character_edit_rejects_pact_of_the_tome_prepared_spell() -> None:
    character = default_fighter("pc1", "Penn")
    character.class_levels = {"warlock": 1}
    character.prepared_spells = ["srd.spell.detect_magic"]

    result = apply_natural_language_character_edit(
        character,
        "eldritch invocation pact of the tome "
        "cantrips fire bolt, guidance, mage hand rituals detect magic, speak with animals",
    )

    assert result.accepted is False
    assert result.errors == [
        "Pact of the Tome 不能选择已经 prepared 的 spell：srd.spell.detect_magic"
    ]


def test_natural_language_character_edit_removes_pact_of_the_tome_when_class_changes() -> None:
    character = default_fighter("pc1", "Penn")
    warlock_result = apply_natural_language_character_edit(
        character,
        "职业 warlock1 eldritch invocation pact of the tome "
        "cantrips fire bolt, guidance, mage hand rituals detect magic, speak with animals",
    )
    assert warlock_result.accepted is True
    assert warlock_result.character is not None

    fighter_result = apply_natural_language_character_edit(
        warlock_result.character, "职业 fighter1"
    )

    assert fighter_result.accepted is True
    assert fighter_result.character is not None
    assert "srd.pact_of_the_tome" not in fighter_result.character.actions
    assert "srd.detect_magic" not in fighter_result.character.actions
    assert fighter_result.character.prepared_spells == []
    assert (
        "warlock.eldritch_invocation.pact_of_the_tome"
        not in fighter_result.character.feature_choices
    )
    assert has_warlock_pact_of_tome(fighter_result.character) is False


def test_natural_language_character_edit_assigns_master_of_myriad_forms_invocation() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock5 eldritch invocation master of myriad forms",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 5}
    assert result.character.feature_choices == {
        "warlock.eldritch_invocation.master_of_myriad_forms": "selected"
    }
    assert "srd.master_of_myriad_forms" in result.character.actions
    assert "srd.master_of_myriad_forms_alter_self" in result.character.actions


def test_natural_language_character_edit_rejects_master_of_myriad_forms_before_warlock_5() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock4 eldritch invocation master of myriad forms",
    )

    assert result.accepted is False
    assert result.errors == ["Master of Myriad Forms 需要 Warlock 5"]


def test_natural_language_character_edit_assigns_ascendant_step_invocation() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock5 eldritch invocation ascendant step",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 5}
    assert result.character.feature_choices == {
        "warlock.eldritch_invocation.ascendant_step": "selected"
    }
    assert "srd.ascendant_step" in result.character.actions
    assert "srd.ascendant_step_levitate" in result.character.actions


def test_natural_language_character_edit_rejects_ascendant_step_before_warlock_5() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock4 eldritch invocation ascendant step",
    )

    assert result.accepted is False
    assert result.errors == ["Ascendant Step 需要 Warlock 5"]


def test_natural_language_character_edit_removes_ascendant_step_when_level_drops() -> None:
    character = default_fighter("pc1", "Penn")
    warlock_result = apply_natural_language_character_edit(
        character,
        "职业 warlock5 eldritch invocation ascendant step",
    )
    assert warlock_result.accepted is True
    assert warlock_result.character is not None

    lower_level_result = apply_natural_language_character_edit(
        warlock_result.character, "职业 warlock4"
    )

    assert lower_level_result.accepted is True
    assert lower_level_result.character is not None
    assert lower_level_result.character.class_levels == {"warlock": 4}
    assert "srd.ascendant_step" not in lower_level_result.character.actions
    assert "srd.ascendant_step_levitate" not in lower_level_result.character.actions


def test_natural_language_character_edit_assigns_one_with_shadows_invocation() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock5 eldritch invocation one with shadows",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 5}
    assert result.character.feature_choices == {
        "warlock.eldritch_invocation.one_with_shadows": "selected"
    }
    assert "srd.one_with_shadows" in result.character.actions
    assert "srd.one_with_shadows_invisibility" in result.character.actions


def test_natural_language_character_edit_rejects_one_with_shadows_before_warlock_5() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock4 eldritch invocation one with shadows",
    )

    assert result.accepted is False
    assert result.errors == ["One with Shadows 需要 Warlock 5"]


def test_natural_language_character_edit_removes_one_with_shadows_when_level_drops() -> None:
    character = default_fighter("pc1", "Penn")
    warlock_result = apply_natural_language_character_edit(
        character,
        "职业 warlock5 eldritch invocation one with shadows",
    )
    assert warlock_result.accepted is True
    assert warlock_result.character is not None

    lower_level_result = apply_natural_language_character_edit(
        warlock_result.character, "职业 warlock4"
    )

    assert lower_level_result.accepted is True
    assert lower_level_result.character is not None
    assert lower_level_result.character.class_levels == {"warlock": 4}
    assert "srd.one_with_shadows" not in lower_level_result.character.actions
    assert "srd.one_with_shadows_invisibility" not in lower_level_result.character.actions


def test_natural_language_character_edit_assigns_gift_of_the_depths_invocation() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock5 eldritch invocation gift of the depths",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 5}
    assert result.character.feature_choices == {
        "warlock.eldritch_invocation.gift_of_the_depths": "selected"
    }
    assert "srd.gift_of_the_depths" in result.character.actions
    assert "srd.gift_of_the_depths_water_breathing" in result.character.actions
    assert result.character.resources["srd.resource.gift_of_the_depths"] == 1
    assert warlock_gift_of_depths_swim_speed_ft(result.character) == 30


def test_natural_language_character_edit_rejects_gift_of_the_depths_before_warlock_5() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock4 eldritch invocation gift of the depths",
    )

    assert result.accepted is False
    assert result.errors == ["Gift of the Depths 需要 Warlock 5"]


def test_natural_language_character_edit_removes_gift_of_the_depths_when_level_drops() -> None:
    character = default_fighter("pc1", "Penn")
    warlock_result = apply_natural_language_character_edit(
        character,
        "职业 warlock5 eldritch invocation gift of the depths",
    )
    assert warlock_result.accepted is True
    assert warlock_result.character is not None

    lower_level_result = apply_natural_language_character_edit(
        warlock_result.character, "职业 warlock4"
    )

    assert lower_level_result.accepted is True
    assert lower_level_result.character is not None
    assert lower_level_result.character.class_levels == {"warlock": 4}
    assert "srd.gift_of_the_depths" not in lower_level_result.character.actions
    assert "srd.gift_of_the_depths_water_breathing" not in lower_level_result.character.actions
    assert "srd.resource.gift_of_the_depths" not in lower_level_result.character.resources
    assert warlock_gift_of_depths_swim_speed_ft(lower_level_result.character) == 0


def test_natural_language_character_edit_assigns_gaze_of_two_minds_invocation() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock5 eldritch invocation gaze of two minds",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 5}
    assert result.character.feature_choices == {
        "warlock.eldritch_invocation.gaze_of_two_minds": "selected"
    }
    assert "srd.gaze_of_two_minds" in result.character.actions
    assert "srd.gaze_of_two_minds_touch" in result.character.actions
    assert has_warlock_gaze_of_two_minds(result.character) is True


def test_natural_language_character_edit_rejects_gaze_of_two_minds_before_warlock_5() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock4 eldritch invocation gaze of two minds",
    )

    assert result.accepted is False
    assert result.errors == ["Gaze of Two Minds 需要 Warlock 5"]


def test_natural_language_character_edit_removes_gaze_of_two_minds_when_level_drops() -> None:
    character = default_fighter("pc1", "Penn")
    warlock_result = apply_natural_language_character_edit(
        character,
        "职业 warlock5 eldritch invocation gaze of two minds",
    )
    assert warlock_result.accepted is True
    assert warlock_result.character is not None

    lower_level_result = apply_natural_language_character_edit(
        warlock_result.character, "职业 warlock4"
    )

    assert lower_level_result.accepted is True
    assert lower_level_result.character is not None
    assert lower_level_result.character.class_levels == {"warlock": 4}
    assert "srd.gaze_of_two_minds" not in lower_level_result.character.actions
    assert "srd.gaze_of_two_minds_touch" not in lower_level_result.character.actions
    assert (
        "warlock.eldritch_invocation.gaze_of_two_minds"
        not in lower_level_result.character.feature_choices
    )
    assert has_warlock_gaze_of_two_minds(lower_level_result.character) is False


def test_natural_language_character_edit_assigns_explicit_armor_of_shadows_invocation() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock1 eldritch invocation armor of shadows",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 1}
    assert result.character.feature_choices == {
        "warlock.eldritch_invocation.armor_of_shadows": "selected"
    }
    assert "srd.eldritch_invocations" in result.character.actions
    assert "srd.armor_of_shadows" in result.character.actions
    assert "srd.armor_of_shadows_mage_armor" in result.character.actions


def test_natural_language_character_edit_rejects_armor_of_shadows_without_warlock() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "eldritch invocation armor of shadows",
    )

    assert result.accepted is False
    assert result.errors == ["Armor of Shadows 需要 Warlock 1"]


def test_natural_language_character_edit_assigns_explicit_fiendish_vigor_invocation() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock2 eldritch invocation fiendish vigor",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 2}
    assert result.character.feature_choices == {
        "warlock.eldritch_invocation.fiendish_vigor": "selected"
    }
    assert "srd.eldritch_invocations" in result.character.actions
    assert "srd.fiendish_vigor" in result.character.actions
    assert "srd.fiendish_vigor_false_life" in result.character.actions


def test_natural_language_character_edit_rejects_fiendish_vigor_before_warlock_2() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock1 eldritch invocation fiendish vigor",
    )

    assert result.accepted is False
    assert result.errors == ["Fiendish Vigor 需要 Warlock 2"]


def test_natural_language_character_edit_assigns_explicit_mask_of_many_faces_invocation() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock2 eldritch invocation mask of many faces",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 2}
    assert result.character.feature_choices == {
        "warlock.eldritch_invocation.mask_of_many_faces": "selected"
    }
    assert "srd.eldritch_invocations" in result.character.actions
    assert "srd.mask_of_many_faces" in result.character.actions
    assert "srd.mask_of_many_faces_disguise_self" in result.character.actions


def test_natural_language_character_edit_rejects_mask_of_many_faces_before_warlock_2() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock1 eldritch invocation mask of many faces",
    )

    assert result.accepted is False
    assert result.errors == ["Mask of Many Faces 需要 Warlock 2"]


def test_natural_language_character_edit_assigns_explicit_misty_visions_invocation() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock2 eldritch invocation misty visions",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 2}
    assert result.character.feature_choices == {
        "warlock.eldritch_invocation.misty_visions": "selected"
    }
    assert "srd.eldritch_invocations" in result.character.actions
    assert "srd.misty_visions" in result.character.actions
    assert "srd.misty_visions_silent_image" in result.character.actions


def test_natural_language_character_edit_rejects_misty_visions_before_warlock_2() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock1 eldritch invocation misty visions",
    )

    assert result.accepted is False
    assert result.errors == ["Misty Visions 需要 Warlock 2"]


def test_natural_language_character_edit_assigns_explicit_otherworldly_leap_invocation() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock2 eldritch invocation otherworldly leap",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 2}
    assert result.character.feature_choices == {
        "warlock.eldritch_invocation.otherworldly_leap": "selected"
    }
    assert "srd.eldritch_invocations" in result.character.actions
    assert "srd.otherworldly_leap" in result.character.actions
    assert "srd.otherworldly_leap_jump" in result.character.actions


def test_natural_language_character_edit_rejects_otherworldly_leap_before_warlock_2() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock1 eldritch invocation otherworldly leap",
    )

    assert result.accepted is False
    assert result.errors == ["Otherworldly Leap 需要 Warlock 2"]


def test_natural_language_character_edit_assigns_explicit_agonizing_blast_invocation() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock2 eldritch invocation agonizing blast eldritch blast",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 2}
    assert result.character.feature_choices == {
        "warlock.eldritch_invocation.agonizing_blast.cantrip": "srd.spell.eldritch_blast"
    }
    assert "srd.eldritch_invocations" in result.character.actions
    assert "srd.agonizing_blast" in result.character.actions


def test_natural_language_character_edit_rejects_agonizing_blast_before_warlock_2() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock1 eldritch invocation agonizing blast eldritch blast",
    )

    assert result.accepted is False
    assert result.errors == ["Agonizing Blast 需要 Warlock 2"]


def test_natural_language_character_edit_assigns_explicit_eldritch_spear_invocation() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock2 eldritch invocation eldritch spear eldritch blast",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 2}
    assert result.character.feature_choices == {
        "warlock.eldritch_invocation.eldritch_spear.cantrip": "srd.spell.eldritch_blast"
    }
    assert "srd.eldritch_invocations" in result.character.actions
    assert "srd.eldritch_spear" in result.character.actions


def test_natural_language_character_edit_rejects_eldritch_spear_before_warlock_2() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock1 eldritch invocation eldritch spear eldritch blast",
    )

    assert result.accepted is False
    assert result.errors == ["Eldritch Spear 需要 Warlock 2"]


def test_natural_language_character_edit_assigns_explicit_repelling_blast_invocation() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock2 eldritch invocation repelling blast eldritch blast",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 2}
    assert result.character.feature_choices == {
        "warlock.eldritch_invocation.repelling_blast.cantrip": "srd.spell.eldritch_blast"
    }
    assert "srd.eldritch_invocations" in result.character.actions
    assert "srd.repelling_blast" in result.character.actions


def test_natural_language_character_edit_rejects_repelling_blast_before_warlock_2() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 warlock1 eldritch invocation repelling blast eldritch blast",
    )

    assert result.accepted is False
    assert result.errors == ["Repelling Blast 需要 Warlock 2"]


def test_natural_language_character_edit_removes_eldritch_mind_when_class_replaced() -> None:
    character = default_fighter("pc1", "Penn")
    warlock_result = apply_natural_language_character_edit(
        character,
        "职业 warlock1 eldritch invocation eldritch mind",
    )
    assert warlock_result.accepted is True
    assert warlock_result.character is not None

    fighter_result = apply_natural_language_character_edit(
        warlock_result.character, "职业 fighter1"
    )

    assert fighter_result.accepted is True
    assert fighter_result.character is not None
    assert fighter_result.character.class_levels == {"fighter": 1}
    assert "srd.eldritch_invocations" not in fighter_result.character.actions
    assert "srd.eldritch_mind" not in fighter_result.character.actions
    assert fighter_result.character.feature_choices == {}


def test_natural_language_character_edit_assigns_explicit_evoker_subclass() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 wizard3 子职 evoker")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"wizard": 3}
    assert result.character.subclasses == {"wizard": "evocation"}
    assert "srd.ritual_adept" in result.character.actions
    assert "srd.arcane_recovery" in result.character.actions
    assert "srd.potent_cantrip" in result.character.actions


def test_natural_language_character_edit_does_not_assign_evoker_by_default() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 wizard3")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"wizard": 3}
    assert result.character.subclasses == {}
    assert "srd.ritual_adept" in result.character.actions
    assert "srd.arcane_recovery" in result.character.actions
    assert "srd.potent_cantrip" not in result.character.actions


def test_natural_language_character_edit_assigns_wizard_memorize_spell_at_level_5() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 wizard5")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"wizard": 5}
    assert "srd.ritual_adept" in result.character.actions
    assert "srd.arcane_recovery" in result.character.actions
    assert "srd.scholar" in result.character.actions
    assert "srd.memorize_spell" in result.character.actions


def test_natural_language_character_edit_assigns_sorcerer_innate_sorcery() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 术法师 魅力 15 敏捷 14 体质 13 力量 8 智力 10 感知 12",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"sorcerer": 1}
    assert result.character.actions == ["srd.fire_bolt", "srd.innate_sorcery"]
    assert result.character.resources["srd.resource.innate_sorcery"] == 2


def test_natural_language_character_edit_assigns_sorcerer_font_of_magic() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 术法师5")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"sorcerer": 5}
    assert {
        "srd.font_of_magic_convert_slot_1",
        "srd.font_of_magic_convert_slot_2",
        "srd.font_of_magic_convert_slot_3",
        "srd.font_of_magic_create_slot_1",
        "srd.font_of_magic_create_slot_2",
        "srd.font_of_magic_create_slot_3",
        "srd.sorcerous_restoration",
    } <= set(result.character.actions)
    assert result.character.resources["srd.resource.sorcery_points"] == 5
    assert result.character.resources["srd.resource.sorcerous_restoration"] == 1


def test_natural_language_character_edit_assigns_druid_wild_shape_resource() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 德鲁伊2")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"druid": 2}
    assert "srd.druidic" in result.character.actions
    assert "srd.primal_order" in result.character.actions
    assert "srd.speak_with_animals" in result.character.actions
    assert "srd.wild_shape_wolf" in result.character.actions
    assert "srd.wild_shape_giant_rat" in result.character.actions
    assert "srd.wild_companion_wild_shape" in result.character.actions
    assert "srd.wild_companion_spell_slot" in result.character.actions
    assert result.character.languages == ["druidic"]
    assert result.character.prepared_spells == ["srd.spell.speak_with_animals"]
    assert result.character.feature_choices == {}
    assert result.character.resources["srd.resource.wild_shape"] == 2


def test_natural_language_character_edit_removes_druidic_when_replacing_class() -> None:
    character = default_fighter("pc1", "Penn")
    druid_result = apply_natural_language_character_edit(character, "职业 德鲁伊")
    assert druid_result.accepted is True
    assert druid_result.character is not None
    assert druid_result.character.languages == ["druidic"]
    assert druid_result.character.prepared_spells == ["srd.spell.speak_with_animals"]

    fighter_result = apply_natural_language_character_edit(druid_result.character, "职业 战士")

    assert fighter_result.accepted is True
    assert fighter_result.character is not None
    assert fighter_result.character.class_levels == {"fighter": 1}
    assert "srd.druidic" not in fighter_result.character.actions
    assert "srd.speak_with_animals" not in fighter_result.character.actions
    assert fighter_result.character.languages == []
    assert fighter_result.character.prepared_spells == []


def test_natural_language_character_edit_assigns_druid_primal_order_choice() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 德鲁伊 primal order magician",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"druid": 1}
    assert result.character.actions == [
        "srd.cure_wounds",
        "srd.druidic",
        "srd.primal_order",
        "srd.speak_with_animals",
    ]
    assert result.character.feature_choices == {"druid.primal_order": "magician"}


def test_natural_language_character_edit_rejects_druid_primal_order_without_druid() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "原初职责 自然术士")

    assert result.accepted is False
    assert result.character is None
    assert result.errors is not None
    assert "Primal Order 选项需要 Druid 1" in result.errors


def test_natural_language_character_edit_assigns_explicit_land_subclass() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 德鲁伊3 子职 land")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"druid": 3}
    assert result.character.subclasses == {"druid": "land"}
    assert "srd.lands_aid" in result.character.actions


def test_natural_language_character_edit_assigns_land_natural_recovery_at_level_6() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 德鲁伊6 子职 land")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"druid": 6}
    assert result.character.subclasses == {"druid": "land"}
    assert "srd.natural_recovery" in result.character.actions
    assert result.character.resources["srd.resource.natural_recovery_spell_slots"] == 1
    assert result.character.resources["srd.resource.natural_recovery_circle_spell"] == 1


def test_natural_language_character_edit_assigns_land_choice_for_circle_of_land() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 德鲁伊10 子职 land land choice polar",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"druid": 10}
    assert result.character.subclasses == {"druid": "land"}
    assert result.character.feature_choices == {"druid.land.current_land": "polar"}
    assert "srd.natures_ward" in result.character.actions


def test_natural_language_character_edit_rejects_land_choice_without_circle_of_land() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 德鲁伊10 land choice polar")

    assert result.accepted is False
    assert result.character is None
    assert result.errors is not None
    assert "Circle of the Land 地形选择需要 Druid/Land 3" in result.errors


def test_natural_language_character_edit_does_not_assign_land_by_default() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 德鲁伊3")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"druid": 3}
    assert result.character.subclasses == {}
    assert "srd.lands_aid" not in result.character.actions


def test_natural_language_character_edit_assigns_druid_wild_resurgence() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 德鲁伊5")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"druid": 5}
    assert {
        "srd.wild_resurgence_restore_wild_shape_slot_1",
        "srd.wild_resurgence_restore_wild_shape_slot_2",
        "srd.wild_resurgence_restore_wild_shape_slot_3",
        "srd.wild_resurgence_create_spell_slot",
    } <= set(result.character.actions)
    assert result.character.resources["srd.resource.wild_shape"] == 2
    assert result.character.resources["srd.resource.wild_resurgence_spell_slot"] == 1


def test_natural_language_character_edit_assigns_bardic_inspiration_resource() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 吟游诗人 力量 8 敏捷 14 体质 13 智力 10 感知 12 魅力 15",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"bard": 1}
    assert "srd.bardic_inspiration" in result.character.actions
    assert result.character.resources["srd.resource.bardic_inspiration"] == 2


def test_natural_language_character_edit_assigns_bard_jack_of_all_trades() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 bard2")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"bard": 2}
    assert "srd.jack_of_all_trades" in result.character.actions


def test_natural_language_character_edit_assigns_explicit_lore_subclass() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 bard3 子职 lore")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"bard": 3}
    assert result.character.subclasses == {"bard": "lore"}
    assert "srd.jack_of_all_trades" in result.character.actions
    assert "srd.cutting_words" in result.character.actions


def test_natural_language_character_edit_does_not_assign_lore_by_default() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 bard3")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"bard": 3}
    assert result.character.subclasses == {}
    assert "srd.jack_of_all_trades" in result.character.actions
    assert "srd.cutting_words" not in result.character.actions


def test_natural_language_character_edit_assigns_cleric_channel_divinity_resource() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 牧师2")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"cleric": 2}
    assert "srd.divine_spark_heal" in result.character.actions
    assert "srd.divine_spark_radiant" in result.character.actions
    assert "srd.divine_spark_necrotic" in result.character.actions
    assert "srd.turn_undead" in result.character.actions
    assert result.character.resources["srd.resource.channel_divinity"] == 2


def test_natural_language_character_edit_assigns_barbarian_rage_resource() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 野蛮人3")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"barbarian": 3}
    assert "srd.rage" in result.character.actions
    assert "srd.barbarian_unarmored_defense" in result.character.actions
    assert "srd.danger_sense" in result.character.actions
    assert "srd.primal_knowledge" in result.character.actions
    assert "srd.reckless_attack" in result.character.actions
    assert "srd.frenzy" not in result.character.actions
    assert result.character.resources == {"srd.resource.rage": 3}


def test_natural_language_character_edit_assigns_explicit_berserker_subclass() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 barbarian3 子职 berserker")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"barbarian": 3}
    assert result.character.subclasses == {"barbarian": "berserker"}
    assert "srd.frenzy" in result.character.actions


def test_natural_language_character_edit_assigns_paladin_lay_on_hands_pool() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 圣武士2")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"paladin": 2}
    assert "srd.lay_on_hands" in result.character.actions
    assert "srd.lay_on_hands_remove_poisoned" in result.character.actions
    assert "srd.divine_smite" in result.character.actions
    assert "srd.paladins_smite_divine_smite" in result.character.actions
    assert result.character.resources["srd.resource.lay_on_hands"] == 10
    assert result.character.resources["srd.resource.paladins_smite"] == 1


def test_natural_language_character_edit_assigns_paladin_channel_divinity() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 圣武士3")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"paladin": 3}
    assert "srd.divine_sense" in result.character.actions
    assert result.character.resources["srd.resource.channel_divinity"] == 2


def test_natural_language_character_edit_assigns_paladin_faithful_steed() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 圣武士5")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"paladin": 5}
    assert "srd.faithful_steed" in result.character.actions
    assert "srd.find_steed" in result.character.actions
    assert "srd.faithful_steed_find_steed" in result.character.actions
    assert result.character.prepared_spells == ["srd.spell.find_steed"]
    assert result.character.resources["srd.resource.faithful_steed"] == 1


def test_natural_language_character_edit_assigns_paladin_aura_of_protection() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 圣武士6")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"paladin": 6}
    assert "srd.aura_of_protection" in result.character.actions
    assert result.character.resources["srd.resource.faithful_steed"] == 1


def test_natural_language_character_edit_removes_faithful_steed_when_level_drops() -> None:
    character = default_fighter("pc1", "Penn")
    paladin_result = apply_natural_language_character_edit(character, "职业 圣武士5")
    assert paladin_result.accepted is True
    assert paladin_result.character is not None

    lower_level_result = apply_natural_language_character_edit(
        paladin_result.character, "职业 圣武士4"
    )

    assert lower_level_result.accepted is True
    assert lower_level_result.character is not None
    assert lower_level_result.character.class_levels == {"paladin": 4}
    assert "srd.faithful_steed" not in lower_level_result.character.actions
    assert "srd.find_steed" not in lower_level_result.character.actions
    assert "srd.faithful_steed_find_steed" not in lower_level_result.character.actions
    assert lower_level_result.character.prepared_spells == []
    assert "srd.resource.faithful_steed" not in lower_level_result.character.resources


def test_natural_language_character_edit_assigns_explicit_devotion_subclass() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 paladin3 子职 devotion")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"paladin": 3}
    assert result.character.subclasses == {"paladin": "devotion"}
    assert "srd.sacred_weapon" in result.character.actions


def test_natural_language_character_edit_does_not_assign_devotion_by_default() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 paladin3")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"paladin": 3}
    assert result.character.subclasses == {}
    assert "srd.sacred_weapon" not in result.character.actions


def test_natural_language_character_edit_assigns_monk_focus_points() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 武僧2")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"monk": 2}
    assert "srd.monk_unarmed_strike" in result.character.actions
    assert "srd.martial_arts_bonus_unarmed_strike" in result.character.actions
    assert "srd.monk_unarmored_defense" in result.character.actions
    assert "srd.monk_unarmored_movement" in result.character.actions
    assert "srd.uncanny_metabolism" in result.character.actions
    assert "srd.flurry_of_blows" in result.character.actions
    assert "srd.patient_defense" in result.character.actions
    assert "srd.patient_defense_focus" in result.character.actions
    assert "srd.step_of_the_wind" in result.character.actions
    assert "srd.step_of_the_wind_focus" in result.character.actions
    assert result.character.resources["srd.resource.focus_points"] == 2
    assert result.character.resources["srd.resource.uncanny_metabolism"] == 1


def test_natural_language_character_edit_assigns_open_hand_subclass_action() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 monk3 子职 open_hand")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"monk": 3}
    assert result.character.subclasses == {"monk": "open_hand"}
    assert "srd.deflect_attacks" in result.character.actions
    assert "srd.open_hand_technique" in result.character.actions


def test_natural_language_character_edit_does_not_assign_open_hand_by_default() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 monk3")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"monk": 3}
    assert result.character.subclasses == {}
    assert "srd.deflect_attacks" in result.character.actions
    assert "srd.open_hand_technique" not in result.character.actions


def test_natural_language_character_edit_assigns_monk_slow_fall() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 monk4")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"monk": 4}
    assert "srd.slow_fall" in result.character.actions
    assert result.character.resources["srd.resource.focus_points"] == 4


def test_natural_language_character_edit_assigns_monk_stunning_strike() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 monk5")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"monk": 5}
    assert "srd.stunning_strike" in result.character.actions
    assert "srd.extra_attack" in result.character.actions
    assert result.character.resources["srd.resource.focus_points"] == 5


def test_natural_language_character_edit_assigns_monk_empowered_strikes() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 monk6")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"monk": 6}
    assert "srd.empowered_strikes" in result.character.actions
    assert "srd.wholeness_of_body" not in result.character.actions
    assert "srd.resource.wholeness_of_body" not in result.character.resources


def test_natural_language_character_edit_assigns_open_hand_wholeness_of_body() -> None:
    character = default_fighter("pc1", "Penn")
    character.abilities["wis"] = 16

    result = apply_natural_language_character_edit(character, "职业 monk6 子职 open_hand")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"monk": 6}
    assert result.character.subclasses == {"monk": "open_hand"}
    assert "srd.empowered_strikes" in result.character.actions
    assert "srd.wholeness_of_body" in result.character.actions
    assert result.character.resources["srd.resource.wholeness_of_body"] == 3


def test_natural_language_character_edit_assigns_ranger_favored_enemy_uses() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 游侠5")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"ranger": 5}
    assert "srd.favored_enemy_hunters_mark" in result.character.actions
    assert "srd.extra_attack" in result.character.actions
    assert result.character.resources["srd.resource.favored_enemy_hunters_mark"] == 3


def test_natural_language_character_edit_assigns_ranger_roving_at_level_6() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 ranger6")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"ranger": 6}
    assert "srd.roving" in result.character.actions

    result.character.equipment = []
    assert ranger_roving_speed_bonus(result.character) == 10
    assert ranger_roving_climb_speed_ft(result.character) == 40
    assert ranger_roving_swim_speed_ft(result.character) == 40

    result.character.equipment = ["srd.chain_mail"]
    assert ranger_roving_speed_bonus(result.character) == 0
    assert ranger_roving_climb_speed_ft(result.character) is None
    assert ranger_roving_swim_speed_ft(result.character) is None


def test_natural_language_character_edit_assigns_hunter_subclass_default_prey() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 ranger3 子职 hunter")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"ranger": 3}
    assert result.character.subclasses == {"ranger": "hunter"}
    assert result.character.feature_choices == {"ranger.hunter.hunters_prey": "colossus_slayer"}
    assert "srd.hunters_lore" in result.character.actions
    assert "srd.hunters_prey_colossus_slayer" in result.character.actions
    assert "srd.hunters_prey_horde_breaker" not in result.character.actions


def test_natural_language_character_edit_does_not_grant_hunter_actions_by_default() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 ranger3")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.subclasses == {}
    assert result.character.feature_choices == {}
    assert "srd.hunters_lore" not in result.character.actions
    assert "srd.hunters_prey_colossus_slayer" not in result.character.actions
    assert "srd.hunters_prey_horde_breaker" not in result.character.actions


def test_natural_language_character_edit_assigns_hunter_horde_breaker_choice() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 ranger3 子职 hunter Hunter's Prey Horde Breaker",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.subclasses == {"ranger": "hunter"}
    assert result.character.feature_choices == {"ranger.hunter.hunters_prey": "horde_breaker"}
    assert "srd.hunters_lore" in result.character.actions
    assert "srd.hunters_prey_horde_breaker" in result.character.actions
    assert "srd.hunters_prey_colossus_slayer" not in result.character.actions


def test_natural_language_character_edit_assigns_rogue_cunning_action() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 盗贼2")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"rogue": 2}
    assert result.character.actions == [
        "srd.shortsword_attack",
        "srd.hide",
        "srd.sneak_attack",
        "srd.rogue_expertise",
        "srd.thieves_cant",
        "srd.cunning_action_dash",
        "srd.cunning_action_disengage",
        "srd.cunning_action_hide",
    ]
    assert result.character.languages == ["thieves_cant"]


def test_natural_language_character_edit_removes_thieves_cant_when_replacing_class() -> None:
    character = default_fighter("pc1", "Penn")
    rogue_result = apply_natural_language_character_edit(character, "职业 盗贼1")
    assert rogue_result.accepted is True
    assert rogue_result.character is not None
    assert rogue_result.character.languages == ["thieves_cant"]

    fighter_result = apply_natural_language_character_edit(rogue_result.character, "职业 战士")

    assert fighter_result.accepted is True
    assert fighter_result.character is not None
    assert fighter_result.character.class_levels == {"fighter": 1}
    assert "srd.thieves_cant" not in fighter_result.character.actions
    assert fighter_result.character.languages == []


def test_natural_language_character_edit_assigns_rogue_steady_aim() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 盗贼3")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"rogue": 3}
    assert "srd.steady_aim" in result.character.actions
    assert "srd.thieves_cant" in result.character.actions
    assert result.character.languages == ["thieves_cant"]
    assert result.character.tool_proficiencies == ["thieves_tools"]
    assert "srd.fast_hands_sleight_of_hand" not in result.character.actions


def test_natural_language_character_edit_assigns_thief_subclass_actions() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 rogue3 子职 thief")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"rogue": 3}
    assert result.character.subclasses == {"rogue": "thief"}
    assert {
        "srd.fast_hands_sleight_of_hand",
        "srd.fast_hands_utilize",
        "srd.fast_hands_magic_item",
        "srd.second_story_work",
    } <= set(result.character.actions)


def test_natural_language_character_edit_assigns_rogue_cunning_strike() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 盗贼5")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"rogue": 5}
    assert "srd.cunning_strike" in result.character.actions
    assert "srd.uncanny_dodge" in result.character.actions
    assert "srd.thieves_cant" in result.character.actions


def test_natural_language_character_edit_assigns_bard_font_of_inspiration_actions() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 吟游诗人5")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"bard": 5}
    assert "srd.jack_of_all_trades" in result.character.actions
    assert {
        "srd.font_of_inspiration_restore_bardic_inspiration_slot_1",
        "srd.font_of_inspiration_restore_bardic_inspiration_slot_2",
        "srd.font_of_inspiration_restore_bardic_inspiration_slot_3",
    } <= set(result.character.actions)


def test_natural_language_character_edit_supports_multiclass_progression() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "多职业 牧师 1")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"fighter": 1, "cleric": 1}
    assert result.character.proficiency_bonus == 2
    assert result.character.hit_dice == {"d10": 1, "d8": 1}
    assert "srd.longsword_attack" in result.character.actions
    assert "srd.cure_wounds" in result.character.actions
    assert result.character.hp_max > character.hp_max
    assert character.class_levels == {"fighter": 1}


def test_natural_language_character_edit_accepts_feat_with_available_asi_slot() -> None:
    character = default_fighter("pc1", "Penn")
    character.class_levels = {"fighter": 4}
    character.hit_dice = {"d10": 4}
    character.hp_max = 36
    character.hp_current = 36

    result = apply_natural_language_character_edit(character, "专长 强韧")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.feats == ["tough"]
    assert result.character.hp_max == 44
    assert result.character.hp_current == 44


def test_natural_language_character_edit_can_set_level_and_take_feat_in_one_request() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 战士4 专长 强韧")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"fighter": 4}
    assert result.character.proficiency_bonus == 2
    assert result.character.hit_dice == {"d10": 4}
    assert "srd.action_surge" in result.character.actions
    assert "srd.tactical_mind" in result.character.actions
    assert result.character.resources["srd.resource.action_surge"] == 1
    assert result.character.resources["srd.resource.second_wind"] == 3
    assert result.character.feats == ["tough"]
    assert result.character.hp_max == 44


def test_natural_language_character_edit_assigns_explicit_champion_subclass() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 战士3 子职 champion")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"fighter": 3}
    assert result.character.subclasses == {"fighter": "champion"}
    assert "srd.improved_critical" in result.character.actions
    assert "srd.remarkable_athlete" in result.character.actions


def test_natural_language_character_edit_does_not_assign_champion_by_default() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 战士3")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"fighter": 3}
    assert result.character.subclasses == {}
    assert "srd.improved_critical" not in result.character.actions
    assert "srd.remarkable_athlete" not in result.character.actions


def test_natural_language_character_edit_assigns_explicit_life_domain_subclass() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 牧师3 子职 life")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"cleric": 3}
    assert result.character.subclasses == {"cleric": "life"}
    assert "srd.disciple_of_life" in result.character.actions
    assert "srd.preserve_life" in result.character.actions


def test_natural_language_character_edit_does_not_assign_life_domain_by_default() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 牧师3")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"cleric": 3}
    assert result.character.subclasses == {}
    assert "srd.disciple_of_life" not in result.character.actions
    assert "srd.preserve_life" not in result.character.actions


def test_natural_language_character_edit_assigns_explicit_fiend_patron_subclass() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 warlock3 子职 fiend")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 3}
    assert result.character.subclasses == {"warlock": "fiend"}
    assert "srd.dark_ones_blessing" in result.character.actions


def test_natural_language_character_edit_assigns_fiend_patron_level_6_luck() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 warlock6 子职 fiend")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 6}
    assert result.character.subclasses == {"warlock": "fiend"}
    assert "srd.dark_ones_blessing" in result.character.actions
    assert "srd.dark_ones_own_luck" in result.character.actions
    assert result.character.resources["srd.resource.dark_ones_own_luck"] == 1


def test_natural_language_character_edit_does_not_assign_fiend_patron_by_default() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 warlock3")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"warlock": 3}
    assert result.character.subclasses == {}
    assert "srd.dark_ones_blessing" not in result.character.actions
    assert "srd.dark_ones_own_luck" not in result.character.actions


def test_natural_language_character_edit_assigns_draconic_resilience_hp_bonus() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 sorcerer5 子职 draconic")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"sorcerer": 5}
    assert result.character.subclasses == {"sorcerer": "draconic"}
    assert result.character.hp_max == 37
    assert result.character.hp_current == 37
    assert "srd.draconic_resilience" in result.character.actions


def test_natural_language_character_edit_does_not_assign_draconic_by_default() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 sorcerer5")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"sorcerer": 5}
    assert result.character.subclasses == {}
    assert result.character.hp_max == 32
    assert "srd.draconic_resilience" not in result.character.actions


def test_natural_language_character_edit_rejects_feat_without_slot_and_duplicate() -> None:
    character = default_fighter("pc1", "Penn")

    no_slot = apply_natural_language_character_edit(character, "专长 强韧")

    assert no_slot.accepted is False
    assert no_slot.errors is not None
    assert any("没有可用专长槽位" in error for error in no_slot.errors)

    character.class_levels = {"fighter": 4}
    character.feats = ["tough"]
    duplicate = apply_natural_language_character_edit(character, "专长 tough")

    assert duplicate.accepted is False
    assert duplicate.errors is not None
    assert any("已经拥有专长" in error for error in duplicate.errors)


def test_natural_language_character_edit_accepts_level_six_plus_progression() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "职业 战士6 专长 强韧")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"fighter": 6}
    assert result.character.proficiency_bonus == 3
    assert result.character.hit_dice == {"d10": 6}
    assert result.character.feats == ["tough"]
    assert result.character.hp_max > character.hp_max


def test_natural_language_character_edit_applies_skilled_srd_choices() -> None:
    character = default_fighter("pc1", "Penn")
    character.class_levels = {"fighter": 4}
    character.hit_dice = {"d10": 4}

    result = apply_natural_language_character_edit(
        character,
        "专长 熟练 技能 察觉 潜行 工具 盗贼工具",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.feats == ["skilled"]
    assert result.character.skill_proficiencies == ["perception", "stealth"]
    assert result.character.tool_proficiencies == ["thieves_tools"]
    assert character.skill_proficiencies == []
    assert character.tool_proficiencies == []


def test_natural_language_character_edit_allows_repeatable_skilled_with_new_choices() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(
        character,
        "职业 战士6 专长 熟练 察觉 潜行 盗贼工具 专长 熟练 奥秘 历史 鲁特琴",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.feats == ["skilled", "skilled"]
    assert result.character.skill_proficiencies == [
        "perception",
        "stealth",
        "arcana",
        "history",
    ]
    assert result.character.tool_proficiencies == ["thieves_tools", "lute"]


def test_natural_language_character_edit_assigns_skill_expertise_choices() -> None:
    character = default_fighter("pc1", "Penn")
    character.skill_proficiencies = ["stealth", "perception"]

    result = apply_natural_language_character_edit(character, "职业 盗贼1 专精 潜行 察觉")

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"rogue": 1}
    assert result.character.skill_expertise == ["stealth", "perception"]
    assert "srd.rogue_expertise" in result.character.actions
    assert character.skill_expertise == []


def test_natural_language_character_edit_assigns_rogue_level_6_expertise_slots() -> None:
    character = default_fighter("pc1", "Penn")
    character.skill_proficiencies = ["stealth", "perception", "arcana", "history"]

    result = apply_natural_language_character_edit(
        character,
        "职业 rogue6 专精 潜行 察觉 奥秘 历史",
    )

    assert result.accepted is True
    assert result.character is not None
    assert result.character.class_levels == {"rogue": 6}
    assert result.character.skill_expertise == ["stealth", "perception", "arcana", "history"]
    assert "srd.rogue_expertise" in result.character.actions


def test_natural_language_character_edit_rejects_rogue_level_5_extra_expertise_slots() -> None:
    character = default_fighter("pc1", "Penn")
    character.skill_proficiencies = ["stealth", "perception", "arcana", "history"]

    result = apply_natural_language_character_edit(
        character,
        "职业 rogue5 专精 潜行 察觉 奥秘 历史",
    )

    assert result.accepted is False
    assert result.errors is not None
    assert any("Expertise 槽位" in error for error in result.errors)


def test_natural_language_character_edit_enforces_scholar_expertise_skill_list() -> None:
    character = default_fighter("pc1", "Penn")
    character.skill_proficiencies = ["arcana", "stealth"]

    accepted = apply_natural_language_character_edit(character, "职业 wizard2 专精 奥秘")
    rejected = apply_natural_language_character_edit(character, "职业 wizard2 专精 潜行")

    assert accepted.accepted is True
    assert accepted.character is not None
    assert accepted.character.skill_expertise == ["arcana"]
    assert "srd.scholar" in accepted.character.actions
    assert rejected.accepted is False
    assert rejected.errors is not None
    assert any("Scholar" in error for error in rejected.errors)


def test_natural_language_character_edit_rejects_skilled_without_three_srd_choices() -> None:
    character = default_fighter("pc1", "Penn")
    character.class_levels = {"fighter": 4}

    missing = apply_natural_language_character_edit(character, "专长 熟练")
    invented = apply_natural_language_character_edit(
        character,
        "专长 熟练 察觉 潜行 光剑工具",
    )

    assert missing.accepted is False
    assert missing.errors is not None
    assert any("必须明确选择任意三项" in error for error in missing.errors)
    assert invented.accepted is False
    assert invented.errors is not None
    assert any("非 SRD 技能或工具" in error for error in invented.errors)


def test_natural_language_character_edit_rejects_above_srd_level_cap_and_feat() -> None:
    character = default_fighter("pc1", "Penn")

    result = apply_natural_language_character_edit(character, "多职业 牧师 21 专长 飞天")

    assert result.accepted is False
    assert result.errors is not None
    assert any("等级上限 20" in error for error in result.errors)
    assert any("不支持的专长" in error for error in result.errors)


def test_natural_language_character_edit_rejects_multiclass_total_above_level_cap() -> None:
    character = default_fighter("pc1", "Penn")
    character.class_levels = {"fighter": 19}
    character.hit_dice = {"d10": 19}

    result = apply_natural_language_character_edit(character, "多职业 牧师 2")

    assert result.accepted is False
    assert result.errors is not None
    assert any("总等级不能超过" in error for error in result.errors)
    assert character.class_levels == {"fighter": 19}

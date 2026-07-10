from dnd_llm.core.rules.spell_slots import (
    spell_slot_maxima_for_class_levels,
    warlock_pact_slot_maxima_for_class_levels,
)


def test_spell_slot_maxima_keeps_pact_magic_out_of_normal_slots() -> None:
    class_levels = {"wizard": 1, "warlock": 1}

    assert spell_slot_maxima_for_class_levels(class_levels) == {"1": 2}
    assert warlock_pact_slot_maxima_for_class_levels(class_levels) == {"1": 1}


def test_paladin_and_ranger_multiclass_levels_round_up_for_spellcasting() -> None:
    assert spell_slot_maxima_for_class_levels({"wizard": 1, "paladin": 1}) == {"1": 3}
    assert spell_slot_maxima_for_class_levels({"wizard": 1, "ranger": 1}) == {"1": 3}
    assert spell_slot_maxima_for_class_levels({"paladin": 1}) == {"1": 2}


def test_paladin_and_ranger_levels_add_before_using_the_slot_table() -> None:
    assert spell_slot_maxima_for_class_levels({"paladin": 3, "ranger": 3}) == {
        "1": 4,
        "2": 3,
    }

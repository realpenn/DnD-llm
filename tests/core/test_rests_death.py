from __future__ import annotations

import pytest

from dnd_llm.core.compendium.loader import CompendiumLoader
from dnd_llm.core.persistence import AuditLog
from dnd_llm.core.tools import EngineTools


def test_short_rest_spends_hit_dice_heals_and_is_idempotent(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"fighter": 2}
    state.characters["pc1"].resources["srd.resource.second_wind"] = 0
    state.characters["pc1"].resources["srd.resource.action_surge"] = 0
    state.characters["pc1"].hp_current = 1
    state.encounter.combatants["pc1"].hp_current = 1
    compendium = CompendiumLoader("rules_data").load()
    audit = AuditLog()
    tools = EngineTools(state, compendium, audit)

    result = tools.short_rest("pc1", {"d10": 1}, idempotency_key="rest-1")
    roll_counter = state.roll_counter
    repeated = tools.short_rest("pc1", {"d10": 1}, idempotency_key="rest-1")

    assert repeated == result
    assert state.roll_counter == roll_counter
    assert result["hp_before"] == 1
    assert result["hp_after"] == 12
    assert result["healing_rolls"][0]["roll_total"] == 10
    assert result["healing_rolls"][0]["con_modifier"] == 2
    assert state.characters["pc1"].hit_dice["d10"] == 0
    assert result["restored_resources"] == {
        "srd.resource.action_surge": 1,
        "srd.resource.second_wind": 1,
    }
    assert state.characters["pc1"].resources["srd.resource.second_wind"] == 1
    assert state.characters["pc1"].resources["srd.resource.action_surge"] == 1
    assert state.encounter.combatants["pc1"].hp_current == 12
    assert audit.events[-1].tool_name == "short_rest"
    assert audit.events[-1].dice_rolls[0]["expression"] == "1d10"


def test_short_rest_decreases_exhaustion_only_with_ranger_tireless(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.status_effects.append(
        {"effect_id": "fighter-exhaustion", "condition": "exhaustion", "level": 2}
    )
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    fighter_rest = tools.short_rest("pc1", {}, idempotency_key="fighter-short-exhaustion")

    assert fighter_rest["exhaustion_before"] == 2
    assert fighter_rest["exhaustion_after"] == 2
    assert character.status_effects[-1]["level"] == 2

    character.class_levels = {"ranger": 10}
    ranger_rest = tools.short_rest("pc1", {}, idempotency_key="ranger-tireless-short")

    assert ranger_rest["exhaustion_before"] == 2
    assert ranger_rest["exhaustion_after"] == 1
    assert character.status_effects[-1]["level"] == 1


def test_long_rest_restores_ranger_tireless_uses(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"ranger": 10}
    character.abilities["wis"] = 16
    character.resources["srd.resource.tireless"] = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.long_rest(["pc1"], idempotency_key="ranger-tireless-long")

    pc1_result = result["results"]["pc1"]
    assert pc1_result["restored_resources"]["srd.resource.tireless"] == 3
    assert character.resources["srd.resource.tireless"] == 3


def test_rest_restores_barbarian_rage_by_srd_rule(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"barbarian": 3}
    character.resources["srd.resource.rage"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    short = tools.short_rest("pc1", {}, idempotency_key="rage-short-rest")

    assert short["restored_resources"] == {"srd.resource.rage": 1}
    assert character.resources["srd.resource.rage"] == 2

    character.resources["srd.resource.rage"] = 0
    long = tools.long_rest(["pc1"], idempotency_key="rage-long-rest")

    assert long["results"]["pc1"]["restored_resources"] == {"srd.resource.rage": 3}
    assert character.resources["srd.resource.rage"] == 3


def test_persistent_rage_initiative_restore_resets_on_long_rest_only(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"barbarian": 15}
    character.resources["srd.resource.rage"] = 4
    character.resources["srd.resource.persistent_rage_initiative_restore"] = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    short = tools.short_rest("pc1", {}, idempotency_key="persistent-rage-short-rest")

    assert short["restored_resources"] == {"srd.resource.rage": 1}
    assert character.resources["srd.resource.rage"] == 5
    assert character.resources["srd.resource.persistent_rage_initiative_restore"] == 0

    long = tools.long_rest(["pc1"], idempotency_key="persistent-rage-long-rest")

    restored = long["results"]["pc1"]["restored_resources"]
    assert restored["srd.resource.persistent_rage_initiative_restore"] == 1
    assert character.resources["srd.resource.persistent_rage_initiative_restore"] == 1


def test_rest_resets_barbarian_relentless_rage_dc_counter(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"barbarian": 11}
    character.resources["srd.resource.relentless_rage_uses_since_rest"] = 2
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    short = tools.short_rest("pc1", {}, idempotency_key="relentless-rage-short-rest")

    assert short["reset_resources"] == {"srd.resource.relentless_rage_uses_since_rest": 2}
    assert character.resources["srd.resource.relentless_rage_uses_since_rest"] == 0

    character.resources["srd.resource.relentless_rage_uses_since_rest"] = 3
    long = tools.long_rest(["pc1"], idempotency_key="relentless-rage-long-rest")

    assert long["results"]["pc1"]["reset_resources"] == {
        "srd.resource.relentless_rage_uses_since_rest": 3
    }
    assert character.resources["srd.resource.relentless_rage_uses_since_rest"] == 0


def test_short_rest_restores_monk_focus_points(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"monk": 3}
    character.resources["srd.resource.focus_points"] = 1
    character.resources["srd.resource.uncanny_metabolism"] = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    short = tools.short_rest("pc1", {}, idempotency_key="focus-short-rest")

    assert short["restored_resources"] == {"srd.resource.focus_points": 2}
    assert character.resources["srd.resource.focus_points"] == 3
    assert character.resources["srd.resource.uncanny_metabolism"] == 0

    character.resources["srd.resource.focus_points"] = 0
    long = tools.long_rest(["pc1"], idempotency_key="focus-long-rest")

    assert long["results"]["pc1"]["restored_resources"] == {
        "srd.resource.focus_points": 3,
        "srd.resource.uncanny_metabolism": 1,
    }
    assert character.resources["srd.resource.focus_points"] == 3
    assert character.resources["srd.resource.uncanny_metabolism"] == 1


def test_long_rest_restores_open_hand_wholeness_of_body(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"monk": 6}
    character.subclasses = {"monk": "open_hand"}
    character.abilities["wis"] = 16
    character.resources["srd.resource.wholeness_of_body"] = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    short = tools.short_rest("pc1", {}, idempotency_key="wholeness-short-rest")

    assert "srd.resource.wholeness_of_body" not in short["restored_resources"]
    assert character.resources["srd.resource.wholeness_of_body"] == 0

    long = tools.long_rest(["pc1"], idempotency_key="wholeness-long-rest")

    assert long["results"]["pc1"]["restored_resources"]["srd.resource.wholeness_of_body"] == 3
    assert character.resources["srd.resource.wholeness_of_body"] == 3


def test_wild_shape_restoration_follows_srd_uses(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"druid": 2}
    character.resources["srd.resource.wild_shape"] = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    short = tools.short_rest("pc1", {}, idempotency_key="wild-shape-short-rest")

    assert short["restored_resources"] == {"srd.resource.wild_shape": 1}
    assert character.resources["srd.resource.wild_shape"] == 1

    character.resources["srd.resource.wild_shape"] = 0
    long = tools.long_rest(["pc1"], idempotency_key="wild-shape-long-rest")

    assert long["results"]["pc1"]["restored_resources"] == {"srd.resource.wild_shape": 2}
    assert character.resources["srd.resource.wild_shape"] == 2


def test_long_rest_restores_sorcerer_srd_resources(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"sorcerer": 2}
    character.resources["srd.resource.innate_sorcery"] = 0
    character.resources["srd.resource.sorcery_points"] = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    short = tools.short_rest("pc1", {}, idempotency_key="sorcerer-short-rest")

    assert short["restored_resources"] == {}
    assert character.resources["srd.resource.innate_sorcery"] == 0
    assert character.resources["srd.resource.sorcery_points"] == 0

    long = tools.long_rest(["pc1"], idempotency_key="sorcerer-long-rest")

    assert long["results"]["pc1"]["restored_resources"] == {
        "srd.resource.innate_sorcery": 2,
        "srd.resource.sorcery_points": 2,
    }
    assert character.resources["srd.resource.innate_sorcery"] == 2
    assert character.resources["srd.resource.sorcery_points"] == 2


def test_sorcerous_restoration_recovers_sorcery_points_once_per_long_rest(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"sorcerer": 5}
    character.resources["srd.resource.innate_sorcery"] = 2
    character.resources["srd.resource.sorcery_points"] = 1
    character.resources["srd.resource.sorcerous_restoration"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    short = tools.short_rest("pc1", {}, idempotency_key="sorcerous-restoration-short")

    assert short["restored_resources"] == {"srd.resource.sorcery_points": 2}
    assert short["spent_resources"] == {"srd.resource.sorcerous_restoration": 1}
    assert character.resources["srd.resource.sorcery_points"] == 3
    assert character.resources["srd.resource.sorcerous_restoration"] == 0

    character.resources["srd.resource.sorcery_points"] = 0
    repeated = tools.short_rest("pc1", {}, idempotency_key="sorcerous-restoration-spent")

    assert "srd.resource.sorcery_points" not in repeated["restored_resources"]
    assert repeated["spent_resources"] == {}
    assert character.resources["srd.resource.sorcery_points"] == 0

    long = tools.long_rest(["pc1"], idempotency_key="sorcerous-restoration-long")

    assert long["results"]["pc1"]["restored_resources"]["srd.resource.sorcery_points"] == 5
    assert long["results"]["pc1"]["restored_resources"]["srd.resource.sorcerous_restoration"] == 1
    assert character.resources["srd.resource.sorcery_points"] == 5
    assert character.resources["srd.resource.sorcerous_restoration"] == 1


def test_arcane_recovery_restores_chosen_spell_slots_once_per_long_rest(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"wizard": 4}
    character.resources["srd.resource.arcane_recovery"] = 1
    character.spell_slots = {"1": 0, "2": 0}
    character.spell_slots_max = {"1": 4, "2": 3}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    short = tools.short_rest(
        "pc1",
        {},
        arcane_recovery_slots={"2": 1},
        idempotency_key="arcane-recovery-short",
    )

    assert short["restored_spell_slots"] == {"2": 1}
    assert short["spent_resources"] == {"srd.resource.arcane_recovery": 1}
    assert character.spell_slots == {"1": 0, "2": 1}
    assert character.resources["srd.resource.arcane_recovery"] == 0

    try:
        tools.short_rest(
            "pc1",
            {},
            arcane_recovery_slots={"1": 1},
            idempotency_key="arcane-recovery-spent",
        )
    except ValueError as exc:
        assert str(exc) == "Arcane Recovery has already been used"
    else:  # pragma: no cover - defensive assertion for the test itself.
        raise AssertionError("Arcane Recovery should be limited to once per Long Rest")

    long = tools.long_rest(["pc1"], idempotency_key="arcane-recovery-long")

    assert long["results"]["pc1"]["restored_resources"]["srd.resource.arcane_recovery"] == 1
    assert character.resources["srd.resource.arcane_recovery"] == 1


def test_natural_recovery_restores_chosen_spell_slots_once_per_long_rest(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"druid": 6}
    character.subclasses = {"druid": "land"}
    character.resources["srd.resource.natural_recovery_spell_slots"] = 1
    character.resources["srd.resource.natural_recovery_circle_spell"] = 0
    character.spell_slots = {"1": 0, "2": 0, "3": 0}
    character.spell_slots_max = {"1": 4, "2": 3, "3": 3}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    short = tools.short_rest(
        "pc1",
        {},
        natural_recovery_slots={"1": 1, "2": 1},
        idempotency_key="natural-recovery-short",
    )

    assert short["restored_spell_slots"] == {"1": 1, "2": 1}
    assert short["spent_resources"] == {"srd.resource.natural_recovery_spell_slots": 1}
    assert character.spell_slots == {"1": 1, "2": 1, "3": 0}
    assert character.resources["srd.resource.natural_recovery_spell_slots"] == 0

    with pytest.raises(ValueError, match="Natural Recovery has already been used"):
        tools.short_rest(
            "pc1",
            {},
            natural_recovery_slots={"1": 1},
            idempotency_key="natural-recovery-spent",
        )

    long = tools.long_rest(["pc1"], idempotency_key="natural-recovery-long")

    assert (
        long["results"]["pc1"]["restored_resources"]["srd.resource.natural_recovery_spell_slots"]
        == 1
    )
    assert (
        long["results"]["pc1"]["restored_resources"]["srd.resource.natural_recovery_circle_spell"]
        == 1
    )
    assert character.resources["srd.resource.natural_recovery_spell_slots"] == 1
    assert character.resources["srd.resource.natural_recovery_circle_spell"] == 1


def test_natural_recovery_rejects_over_cap_and_level_6_slots_before_spending(
    make_state,
) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"druid": 6}
    character.subclasses = {"druid": "land"}
    character.resources["srd.resource.natural_recovery_spell_slots"] = 1
    character.spell_slots = {"3": 0, "6": 0}
    character.spell_slots_max = {"3": 3, "6": 1}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(
        ValueError,
        match="Natural Recovery cannot recover more than 3 spell levels",
    ):
        tools.short_rest(
            "pc1",
            {},
            natural_recovery_slots={"3": 2},
            idempotency_key="natural-recovery-over-cap",
        )

    assert character.spell_slots == {"3": 0, "6": 0}
    assert character.resources["srd.resource.natural_recovery_spell_slots"] == 1

    with pytest.raises(
        ValueError,
        match="Natural Recovery cannot recover level 6 or higher spell slots",
    ):
        tools.short_rest(
            "pc1",
            {},
            natural_recovery_slots={"6": 1},
            idempotency_key="natural-recovery-level-6",
        )

    assert character.spell_slots == {"3": 0, "6": 0}
    assert character.resources["srd.resource.natural_recovery_spell_slots"] == 1


def test_wizard_memorize_spell_replaces_prepared_spell_on_short_rest(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"wizard": 5}
    character.actions = ["srd.memorize_spell"]
    character.known_spells = [
        "srd.spell.detect_magic",
        "srd.spell.magic_missile",
        "srd.spell.fireball",
    ]
    character.prepared_spells = ["srd.spell.detect_magic", "srd.spell.magic_missile"]
    character.spell_slots = {"1": 4, "2": 3, "3": 2}
    character.spell_slots_max = {"1": 4, "2": 3, "3": 2}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.short_rest(
        "pc1",
        {},
        memorize_spell={"replace": "srd.detect_magic", "with": "srd.fireball"},
        idempotency_key="wizard-memorize-short",
    )

    assert character.prepared_spells == ["srd.spell.fireball", "srd.spell.magic_missile"]
    assert result["memorize_spell"] == {
        "feature": "srd.memorize_spell",
        "replaced": "srd.spell.detect_magic",
        "with": "srd.spell.fireball",
        "prepared_spells_before": ["srd.spell.detect_magic", "srd.spell.magic_missile"],
        "prepared_spells_after": ["srd.spell.fireball", "srd.spell.magic_missile"],
    }


def test_wizard_memorize_spell_rejects_invalid_short_rest_replacements(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"wizard": 4}
    character.known_spells = ["srd.spell.detect_magic", "srd.spell.magic_missile"]
    character.prepared_spells = ["srd.spell.detect_magic"]
    character.spell_slots = {"1": 4}
    character.spell_slots_max = {"1": 4}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    with pytest.raises(ValueError, match="Wizard level 5"):
        tools.short_rest(
            "pc1",
            {},
            memorize_spell={"replace": "srd.detect_magic", "with": "srd.magic_missile"},
            idempotency_key="wizard-memorize-level",
        )

    character.class_levels = {"wizard": 5}
    with pytest.raises(ValueError, match="spellbook"):
        tools.short_rest(
            "pc1",
            {},
            memorize_spell={"replace": "srd.detect_magic", "with": "srd.fireball"},
            idempotency_key="wizard-memorize-spellbook",
        )

    character.known_spells.append("srd.spell.fire_bolt")
    with pytest.raises(ValueError, match="level 1"):
        tools.short_rest(
            "pc1",
            {},
            memorize_spell={"replace": "srd.detect_magic", "with": "srd.fire_bolt"},
            idempotency_key="wizard-memorize-cantrip",
        )

    character.known_spells.append("srd.spell.cure_wounds")
    with pytest.raises(ValueError, match="Wizard spell"):
        tools.short_rest(
            "pc1",
            {},
            memorize_spell={"replace": "srd.detect_magic", "with": "srd.cure_wounds"},
            idempotency_key="wizard-memorize-non-wizard",
        )


def test_short_and_long_rest_restore_warlock_pact_magic_slots(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 3}
    character.resources["srd.resource.magical_cunning"] = 0
    character.spell_slots = {"2": 0}
    character.spell_slots_max = {}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    short = tools.short_rest("pc1", {}, idempotency_key="warlock-pact-short-rest")

    assert short["spell_slots_before"] == {"2": 0}
    assert short["restored_spell_slots"] == {"2": 2}
    assert short["spell_slots_after"] == {"2": 2}
    assert character.spell_slots == {"2": 2}
    assert character.spell_slots_max == {"2": 2}
    assert character.resources["srd.resource.magical_cunning"] == 0

    character.class_levels = {"warlock": 5}
    character.spell_slots = {"3": 0}
    character.spell_slots_max = {}
    long = tools.long_rest(["pc1"], idempotency_key="warlock-pact-long-rest")

    assert long["results"]["pc1"]["spell_slots_after"] == {"3": 2}
    assert long["results"]["pc1"]["restored_resources"] == {"srd.resource.magical_cunning": 1}
    assert character.spell_slots_max == {"3": 2}
    assert character.resources["srd.resource.magical_cunning"] == 1


def test_bardic_inspiration_restoration_uses_font_of_inspiration_rule(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"bard": 4}
    character.abilities["cha"] = 16
    character.resources["srd.resource.bardic_inspiration"] = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    short_before_font = tools.short_rest("pc1", {}, idempotency_key="bard-short-level-4")

    assert "srd.resource.bardic_inspiration" not in short_before_font["restored_resources"]
    assert character.resources["srd.resource.bardic_inspiration"] == 0

    long_before_font = tools.long_rest(["pc1"], idempotency_key="bard-long-level-4")

    assert long_before_font["results"]["pc1"]["restored_resources"] == {
        "srd.resource.bardic_inspiration": 3
    }
    assert character.resources["srd.resource.bardic_inspiration"] == 3

    character.class_levels = {"bard": 5}
    character.resources["srd.resource.bardic_inspiration"] = 1
    short_after_font = tools.short_rest("pc1", {}, idempotency_key="bard-short-level-5")

    assert short_after_font["restored_resources"] == {"srd.resource.bardic_inspiration": 2}
    assert character.resources["srd.resource.bardic_inspiration"] == 3


def test_channel_divinity_restores_one_on_short_rest_and_all_on_long_rest(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"cleric": 2}
    character.resources["srd.resource.channel_divinity"] = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    short = tools.short_rest("pc1", {}, idempotency_key="channel-divinity-short-rest")

    assert short["restored_resources"] == {"srd.resource.channel_divinity": 1}
    assert character.resources["srd.resource.channel_divinity"] == 1

    character.resources["srd.resource.channel_divinity"] = 0
    long = tools.long_rest(["pc1"], idempotency_key="channel-divinity-long-rest")

    assert long["results"]["pc1"]["restored_resources"] == {"srd.resource.channel_divinity": 2}
    assert character.resources["srd.resource.channel_divinity"] == 2

    character.class_levels = {"paladin": 3}
    character.resources["srd.resource.channel_divinity"] = 0
    paladin_short = tools.short_rest("pc1", {}, idempotency_key="paladin-channel-short-rest")

    assert paladin_short["restored_resources"] == {"srd.resource.channel_divinity": 1}
    assert character.resources["srd.resource.channel_divinity"] == 1


def test_long_rest_restores_favored_enemy_hunters_mark_uses(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"ranger": 5}
    character.resources["srd.resource.favored_enemy_hunters_mark"] = 1
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    short = tools.short_rest("pc1", {}, idempotency_key="favored-enemy-short-rest")

    assert "srd.resource.favored_enemy_hunters_mark" not in short["restored_resources"]
    assert character.resources["srd.resource.favored_enemy_hunters_mark"] == 1

    long = tools.long_rest(["pc1"], idempotency_key="favored-enemy-long-rest")

    assert long["results"]["pc1"]["restored_resources"] == {
        "srd.resource.favored_enemy_hunters_mark": 2
    }
    assert character.resources["srd.resource.favored_enemy_hunters_mark"] == 3


def test_long_rest_restores_lay_on_hands_pool(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"paladin": 2}
    character.resources["srd.resource.lay_on_hands"] = 2
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    short = tools.short_rest("pc1", {}, idempotency_key="lay-on-hands-short-rest")

    assert "srd.resource.lay_on_hands" not in short["restored_resources"]
    assert character.resources["srd.resource.lay_on_hands"] == 2

    long = tools.long_rest(["pc1"], idempotency_key="lay-on-hands-long-rest")

    restored = long["results"]["pc1"]["restored_resources"]
    assert restored["srd.resource.lay_on_hands"] == 8
    assert restored["srd.resource.paladins_smite"] == 0
    assert character.resources["srd.resource.lay_on_hands"] == 10


def test_long_rest_restores_faithful_steed_uses(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"paladin": 5}
    character.resources["srd.resource.faithful_steed"] = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    short = tools.short_rest("pc1", {}, idempotency_key="faithful-steed-short-rest")

    assert "srd.resource.faithful_steed" not in short["restored_resources"]
    assert character.resources["srd.resource.faithful_steed"] == 0

    long = tools.long_rest(["pc1"], idempotency_key="faithful-steed-long-rest")

    assert long["results"]["pc1"]["restored_resources"]["srd.resource.faithful_steed"] == 1
    assert character.resources["srd.resource.faithful_steed"] == 1


def test_long_rest_restores_gift_of_depths_uses(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 5}
    character.feature_choices = {"warlock.eldritch_invocation.gift_of_the_depths": "selected"}
    character.actions.extend(["srd.gift_of_the_depths", "srd.gift_of_the_depths_water_breathing"])
    character.resources["srd.resource.gift_of_the_depths"] = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    short = tools.short_rest("pc1", {}, idempotency_key="gift-depths-short-rest")

    assert "srd.resource.gift_of_the_depths" not in short["restored_resources"]
    assert character.resources["srd.resource.gift_of_the_depths"] == 0

    long = tools.long_rest(["pc1"], idempotency_key="gift-depths-long-rest")

    assert long["results"]["pc1"]["restored_resources"]["srd.resource.gift_of_the_depths"] == 1
    assert character.resources["srd.resource.gift_of_the_depths"] == 1


def test_long_rest_restores_hp_spell_slots_hit_dice_and_death_state(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc2"]
    combatant = state.encounter.combatants["pc2"]
    character.hp_current = 0
    character.temp_hp = 3
    character.spell_slots = {"1": 0}
    character.hit_dice = {"d8": 0}
    character.status_effects.append(
        {"effect_id": "exhaustion-test", "condition": "exhaustion", "level": 2}
    )
    character.death_save_successes = 2
    character.stable = True
    combatant.hp_current = 0
    combatant.temp_hp = 3
    combatant.death_save_successes = 2
    combatant.stable = True
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.long_rest(["pc2"], idempotency_key="long-rest")

    pc2_result = result["results"]["pc2"]
    assert pc2_result["hp_after"] == 8
    assert pc2_result["spell_slots_after"] == {"1": 2}
    assert pc2_result["hit_dice_after"] == {"d8": 1}
    assert pc2_result["exhaustion_before"] == 2
    assert pc2_result["exhaustion_after"] == 1
    assert character.hp_current == 8
    assert character.temp_hp == 0
    assert character.death_save_successes == 0
    assert character.stable is False
    assert combatant.hp_current == 8
    assert combatant.temp_hp == 0
    assert combatant.death_save_successes == 0
    assert combatant.stable is False
    assert character.status_effects[-1]["level"] == 1


def test_long_rest_restores_second_wind_to_srd_maximum(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"fighter": 2}
    character.resources["srd.resource.second_wind"] = 0
    character.resources["srd.resource.action_surge"] = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.long_rest(["pc1"], idempotency_key="second-wind-long-rest")

    pc1_result = result["results"]["pc1"]
    assert pc1_result["restored_resources"] == {
        "srd.resource.action_surge": 1,
        "srd.resource.second_wind": 2,
    }
    assert character.resources["srd.resource.second_wind"] == 2
    assert character.resources["srd.resource.action_surge"] == 1


def test_long_rest_restores_fighter_action_surge_two_uses_at_level_17(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"fighter": 17}
    character.resources["srd.resource.action_surge"] = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.long_rest(["pc1"], idempotency_key="action-surge-level-17-long-rest")

    assert result["results"]["pc1"]["restored_resources"]["srd.resource.action_surge"] == 2
    assert character.resources["srd.resource.action_surge"] == 2


def test_long_rest_restores_fighter_indomitable_uses_by_level(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"fighter": 13}
    character.resources["srd.resource.indomitable"] = 0
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    level_13 = tools.long_rest(["pc1"], idempotency_key="indomitable-level-13-long-rest")

    assert level_13["results"]["pc1"]["restored_resources"]["srd.resource.indomitable"] == 2
    assert character.resources["srd.resource.indomitable"] == 2

    character.class_levels = {"fighter": 17}
    character.resources["srd.resource.indomitable"] = 1
    level_17 = tools.long_rest(["pc1"], idempotency_key="indomitable-level-17-long-rest")

    assert level_17["results"]["pc1"]["restored_resources"]["srd.resource.indomitable"] == 2
    assert character.resources["srd.resource.indomitable"] == 3


def test_long_rest_restores_srd_high_level_spell_slots(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"wizard": 17}
    character.spell_slots = {str(level): 0 for level in range(1, 10)}
    character.spell_slots_max = {}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.long_rest(["pc1"], idempotency_key="high-level-long-rest")

    pc1_result = result["results"]["pc1"]
    assert pc1_result["spell_slots_after"] == {
        "1": 4,
        "2": 3,
        "3": 3,
        "4": 3,
        "5": 2,
        "6": 1,
        "7": 1,
        "8": 1,
        "9": 1,
    }


def test_long_rest_recomputes_spell_slots_after_level_change(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"wizard": 5}
    character.spell_slots = {"1": 0}
    character.spell_slots_max = {"1": 2}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.long_rest(["pc1"], idempotency_key="stale-slot-max-long-rest")

    assert result["results"]["pc1"]["spell_slots_after"] == {"1": 4, "2": 3, "3": 2}
    assert character.spell_slots_max == {"1": 4, "2": 3, "3": 2}


def test_long_rest_uses_multiclass_spellcaster_level(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"wizard": 5, "paladin": 5}
    character.spell_slots = {str(level): 0 for level in range(1, 5)}
    character.spell_slots_max = {}
    compendium = CompendiumLoader("rules_data").load()
    tools = EngineTools(state, compendium, AuditLog())

    result = tools.long_rest(["pc1"], idempotency_key="multiclass-slot-long-rest")

    assert result["results"]["pc1"]["spell_slots_after"] == {
        "1": 4,
        "2": 3,
        "3": 3,
        "4": 1,
    }


def test_death_save_rolls_deterministically_audits_and_syncs_character(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].hp_current = 0
    state.encounter.combatants["pc1"].hp_current = 0
    compendium = CompendiumLoader("rules_data").load()
    audit = AuditLog()
    tools = EngineTools(state, compendium, audit)

    result = tools.roll_death_save("pc1", idempotency_key="death-1")
    roll_counter = state.roll_counter
    repeated = tools.roll_death_save("pc1", idempotency_key="death-1")

    assert repeated == result
    assert state.roll_counter == roll_counter
    assert result["natural"] == 16
    assert result["after"]["successes"] == 1
    assert result["dead"] is False
    assert state.encounter.combatants["pc1"].death_save_successes == 1
    assert state.characters["pc1"].death_save_successes == 1
    assert audit.events[-1].tool_name == "death_save"
    assert audit.events[-1].dice_rolls[0]["expression"] == "1d20"


def test_champion_survivor_defy_death_advantage_and_18_to_20(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.rng_seed = 21
    state.characters["pc1"].class_levels = {"fighter": 18}
    state.characters["pc1"].subclasses = {"fighter": "champion"}
    state.characters["pc1"].hp_current = 0
    state.characters["pc1"].death_save_failures = 2
    state.encounter.combatants["pc1"].hp_current = 0
    state.encounter.combatants["pc1"].death_save_failures = 2
    compendium = CompendiumLoader("rules_data").load()
    audit = AuditLog()
    tools = EngineTools(state, compendium, audit)

    result = tools.roll_death_save("pc1", idempotency_key="champion-survivor-death")

    assert result["roll"]["advantage"] == "advantage"
    assert result["natural"] == 19
    assert result["effective_natural"] == 20
    assert result["advantage_sources"] == ["srd.survivor"]
    assert result["defy_death_counts_as_20"] is True
    assert result["hp_after"] == 1
    assert result["after"]["failures"] == 0
    assert state.encounter.combatants["pc1"].hp_current == 1
    assert state.characters["pc1"].hp_current == 1
    assert audit.events[-1].dice_rolls[0]["advantage"] == "advantage"

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from dnd_llm.core.compendium.loader import CompendiumLoader

SPELL_METADATA = {
    # SRD 5.2.1 spell entries, pp. 107-173.
    "srd.spell.aid": ("abjuration", {"bard", "cleric", "druid", "paladin", "ranger"}),
    "srd.spell.augury": ("divination", {"cleric", "druid", "wizard"}),
    "srd.spell.bane": ("enchantment", {"bard", "cleric", "warlock"}),
    "srd.spell.beacon_of_hope": ("abjuration", {"cleric"}),
    "srd.spell.color_spray": ("illusion", {"bard", "sorcerer", "wizard"}),
    "srd.spell.command": ("enchantment", {"bard", "cleric", "paladin"}),
    "srd.spell.cure_wounds": ("abjuration", {"bard", "cleric", "druid", "paladin", "ranger"}),
    "srd.spell.detect_magic": (
        "divination",
        {"bard", "cleric", "druid", "paladin", "ranger", "sorcerer", "warlock", "wizard"},
    ),
    "srd.spell.dispel_magic": (
        "abjuration",
        {"bard", "cleric", "druid", "paladin", "ranger", "sorcerer", "warlock", "wizard"},
    ),
    "srd.spell.enhance_ability": (
        "transmutation",
        {"bard", "cleric", "druid", "ranger", "sorcerer", "wizard"},
    ),
    "srd.spell.enlarge_reduce": (
        "transmutation",
        {"bard", "druid", "sorcerer", "wizard"},
    ),
    "srd.spell.flame_blade": ("evocation", {"druid", "sorcerer"}),
    "srd.spell.flaming_sphere": ("conjuration", {"druid", "sorcerer", "wizard"}),
    "srd.spell.gentle_repose": ("necromancy", {"cleric", "paladin", "wizard"}),
    "srd.spell.gust_of_wind": ("evocation", {"druid", "ranger", "sorcerer", "wizard"}),
    "srd.spell.hideous_laughter": ("enchantment", {"bard", "warlock", "wizard"}),
    "srd.spell.meld_into_stone": ("transmutation", {"cleric", "druid", "ranger"}),
    "srd.spell.message": ("transmutation", {"bard", "druid", "sorcerer", "wizard"}),
    "srd.spell.mirror_image": ("illusion", {"bard", "sorcerer", "warlock", "wizard"}),
    "srd.spell.protection_from_evil_and_good": (
        "abjuration",
        {"cleric", "druid", "paladin", "warlock", "wizard"},
    ),
    "srd.spell.revivify": ("necromancy", {"cleric", "druid", "paladin", "ranger"}),
    "srd.spell.sending": ("divination", {"bard", "cleric", "wizard"}),
    "srd.spell.slow": ("transmutation", {"bard", "sorcerer", "wizard"}),
    "srd.spell.speak_with_animals": ("divination", {"bard", "druid", "ranger", "warlock"}),
    "srd.spell.speak_with_dead": ("necromancy", {"bard", "cleric", "wizard"}),
    "srd.spell.vampiric_touch": ("necromancy", {"sorcerer", "warlock", "wizard"}),
    "srd.spell.warding_bond": ("abjuration", {"cleric", "paladin"}),
    "srd.spell.water_walk": ("transmutation", {"cleric", "druid", "ranger", "sorcerer"}),
}


WEAPON_ACTIONS = {
    "srd.dagger": {"srd.dagger_attack", "srd.dagger_throw"},
    "srd.shortbow": {"srd.shortbow_attack"},
    "srd.light_crossbow": {"srd.light_crossbow_attack"},
    "srd.quarterstaff": {"srd.quarterstaff_attack"},
    "srd.mace": {"srd.mace_attack"},
    "srd.spear": {"srd.spear_attack", "srd.spear_throw"},
    "srd.handaxe": {"srd.handaxe_attack", "srd.handaxe_throw"},
}


def test_corrected_spell_metadata_matches_srd_entries() -> None:
    compendium = CompendiumLoader("rules_data").load()

    for spell_id, (school, classes) in SPELL_METADATA.items():
        spell = compendium.spells[spell_id]
        assert spell.school == school, spell_id
        assert set(spell.classes) == classes, spell_id

    assert compendium.action("srd.flaming_sphere").action_economy == "action"
    assert compendium.action("srd.slow").range == {
        "normal_ft": 120,
        "shape": "cube",
        "size_ft": 40,
    }
    assert compendium.action("srd.bane").target_policy["max_targets_per_slot_above"] == 1
    assert compendium.action("srd.command").target_policy["max_targets_per_slot_above"] == 1


def test_starter_weapons_reference_executable_srd_attacks() -> None:
    compendium = CompendiumLoader("rules_data").load()

    for item_id, action_ids in WEAPON_ACTIONS.items():
        item = compendium.items[item_id]
        assert set(item.actions) == action_ids
        assert all(action_id in compendium.actions for action_id in item.actions)

    dagger = compendium.action("srd.dagger_throw")
    assert dagger.range == {"normal_ft": 20, "long_ft": 60}
    assert dagger.properties["weapon_mastery_property"] == "Nick"
    assert dagger.properties["damage_dice"] == "1d4"

    shortbow = compendium.action("srd.shortbow_attack")
    assert shortbow.range == {"normal_ft": 80, "long_ft": 320}
    assert shortbow.properties["weapon_mastery_property"] == "Vex"

    light_crossbow = compendium.action("srd.light_crossbow_attack")
    assert light_crossbow.properties["weapon_properties"] == [
        "ammunition",
        "loading",
        "two-handed",
    ]
    assert light_crossbow.properties["weapon_mastery_property"] == "Slow"

    quarterstaff = compendium.action("srd.quarterstaff_attack")
    assert quarterstaff.properties["versatile_damage_dice"] == "1d8"
    assert quarterstaff.properties["weapon_mastery_property"] == "Topple"
    assert compendium.action("srd.mace_attack").properties["weapon_mastery_property"] == "Sap"
    assert compendium.action("srd.spear_throw").range == {"normal_ft": 20, "long_ft": 60}
    assert compendium.action("srd.handaxe_throw").properties["weapon_mastery_property"] == "Vex"


def test_monster_stat_blocks_include_srd_multiattack_parry_and_pack_tactics() -> None:
    compendium = CompendiumLoader("rules_data").load()
    captain = compendium.monsters["srd.bandit_captain"]
    infantry = compendium.monsters["srd.warrior_infantry"]

    assert {"srd.bandit_captain_multiattack", "srd.bandit_captain_parry"} <= set(captain.actions)
    multiattack = compendium.action("srd.bandit_captain_multiattack")
    assert multiattack.properties["multiattack_count"] == 2
    assert multiattack.properties["allowed_attack_action_ids"] == [
        "srd.bandit_captain_scimitar",
        "srd.bandit_captain_pistol",
    ]
    assert sum(node["type"] == "attack_roll" for node in multiattack.automation) == 2

    parry = compendium.action("srd.bandit_captain_parry")
    assert parry.action_economy == "reaction"
    assert parry.properties["armor_class_bonus_against_triggering_attack"] == 2

    assert "srd.warrior_infantry_pack_tactics" in infantry.actions
    pack_tactics = compendium.action("srd.warrior_infantry_pack_tactics")
    assert pack_tactics.properties == {
        "grants_attack_roll_advantage": True,
        "requires_ally_within_target_ft": 5,
        "ally_must_not_be_incapacitated": True,
    }


def test_srd_json_ids_are_unique_within_each_definition_namespace() -> None:
    ids_by_namespace: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for path in sorted(Path("rules_data/srd").glob("**/*.json")):
        namespace = path.parent.name
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in data.get("items", []):
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            ids_by_namespace[namespace][item["id"]].append(str(path))
            if namespace == "spells" and isinstance(item.get("action"), dict):
                action_id = item["action"].get("id")
                if isinstance(action_id, str):
                    ids_by_namespace["actions"][action_id].append(str(path))

    duplicates = {
        namespace: {item_id: paths for item_id, paths in ids.items() if len(paths) > 1}
        for namespace, ids in ids_by_namespace.items()
    }
    assert {namespace: values for namespace, values in duplicates.items() if values} == {}

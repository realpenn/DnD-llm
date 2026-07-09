from __future__ import annotations

import json
from pathlib import Path

from dnd_llm.core.compendium.coverage import build_coverage_report
from dnd_llm.core.compendium.loader import CompendiumLoader


def test_compendium_coverage_report_is_explicit_about_phase1_gaps() -> None:
    compendium = CompendiumLoader("rules_data").load()
    report = build_coverage_report(compendium)
    sections = {section.name: section for section in report.sections}

    assert sections["base_classes"].complete is True
    assert sections["core_conditions"].complete is True
    assert sections["spells_0_to_3"].expected_count == 183
    assert sections["spells_0_to_3"].loaded_count == 183
    assert sections["spells_0_to_3"].complete is True
    assert sections["spells_0_to_3"].missing == []
    assert sections["actions"].expected_count == 229
    assert sections["actions"].complete is True
    assert sections["actions"].missing == []
    assert sections["monsters"].expected_count == 9
    assert sections["monsters"].complete is True
    assert sections["monsters"].missing == []
    assert sections["items"].expected_count == 22
    assert sections["items"].complete is True
    assert sections["items"].missing == []
    assert sections["hazards"].expected_count == 11
    assert sections["hazards"].loaded_count == 11
    assert sections["hazards"].complete is True
    assert sections["hazards"].missing == []
    assert report.fully_complete is True
    assert report.to_dict()["sections"]


def test_srd_definitions_do_not_use_sample_labels() -> None:
    sample_labels: list[str] = []
    for path in sorted(Path("rules_data/srd").glob("**/*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in data.get("items", []):
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("id", ""))
            if "sample" in item_id:
                sample_labels.append(f"{path}:{item_id}")
            source = str(item.get("source", ""))
            if "sample" in source.casefold():
                sample_labels.append(f"{path}:{item_id}:source={source}")
            action = item.get("action")
            if isinstance(action, dict):
                action_id = str(action.get("id", ""))
                if "sample" in action_id:
                    sample_labels.append(f"{path}:{action_id}")
                action_source = str(action.get("source", ""))
                if "sample" in action_source.casefold():
                    sample_labels.append(f"{path}:{action_id}:source={action_source}")

    assert sample_labels == []


def test_tier1_srd_monsters_do_not_use_generic_monster_attack() -> None:
    compendium = CompendiumLoader("rules_data").load()
    generic_users = [
        monster_id
        for monster_id, monster in sorted(compendium.monsters.items())
        if "srd.monster_melee_attack" in monster.actions
    ]

    assert generic_users == []

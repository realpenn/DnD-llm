from __future__ import annotations

from dnd_llm.core.compendium.loader import CompendiumLoader
from dnd_llm.core.compendium.simulator import CompendiumSimulator


def test_every_loaded_action_can_be_simulated_and_serialized() -> None:
    compendium = CompendiumLoader("rules_data").load()
    reports = CompendiumSimulator(compendium).simulate_all_actions()

    failures = {report.action_id: report.error for report in reports if not report.ok}
    assert failures == {}
    assert {report.action_id for report in reports} == set(compendium.actions)
    assert all(report.serialized_state for report in reports)
    assert all(report.audit_events for report in reports)


def test_dash_simulation_adds_movement_budget() -> None:
    compendium = CompendiumLoader("rules_data").load()
    report = CompendiumSimulator(compendium).simulate_action("srd.dash")

    assert report.ok is True
    assert report.serialized_state is not None
    budget = report.serialized_state["encounter"]["action_budgets"]["pc_actor"]
    assert budget["action"] == 0
    assert budget["movement"] == 60


def test_prismatic_spray_simulation_resolves_automated_ray_subset() -> None:
    compendium = CompendiumLoader("rules_data").load()
    report = CompendiumSimulator(compendium).simulate_action("srd.prismatic_spray")

    assert report.ok is True
    assert report.result is not None
    spray_results = next(
        value for value in report.result["node_results"].values() if isinstance(value, list)
    )
    assert len(spray_results) == 1
    assert spray_results[0]["target_id"] == "npc_enemy"
    assert spray_results[0]["color_roll"] in range(1, 9)
    if spray_results[0]["color_roll"] in range(1, 6):
        assert spray_results[0]["automated"] is True
        assert spray_results[0]["damage_type"] in {
            "fire",
            "acid",
            "lightning",
            "poison",
            "cold",
        }
    else:
        assert spray_results[0]["automation_status"] == "not_automated"


def test_extra_attack_marker_does_not_spend_action_budget() -> None:
    compendium = CompendiumLoader("rules_data").load()
    report = CompendiumSimulator(compendium).simulate_action("srd.extra_attack")

    assert report.ok is True
    assert report.result is not None
    assert not [
        change for change in report.result["state_changes"] if change["type"] == "action_economy"
    ]


def test_class_any_level_min_simulation_uses_required_level() -> None:
    compendium = CompendiumLoader("rules_data").load()
    report = CompendiumSimulator(compendium).simulate_action("srd.evasion")

    assert report.ok is True
    assert report.serialized_state is not None
    actor = report.serialized_state["characters"]["pc_actor"]
    assert actor["class_levels"]["monk"] == 7


def test_every_loaded_hazard_can_be_simulated_and_serialized() -> None:
    compendium = CompendiumLoader("rules_data").load()
    reports = CompendiumSimulator(compendium).simulate_all_hazards()

    failures = {report.action_id: report.error for report in reports if not report.ok}
    assert failures == {}
    assert {report.action_id for report in reports} == set(compendium.hazards)
    assert all(report.serialized_state for report in reports)
    assert all(report.audit_events for report in reports)

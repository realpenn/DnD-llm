from __future__ import annotations

from pathlib import Path

from dnd_llm.core.dice import ReplayRollService, RollService
from dnd_llm.core.models import Character
from dnd_llm.core.persistence import AuditLog, load_game, save_game


def test_roll_service_save_load_continues_deterministically(tmp_path: Path, make_state) -> None:
    state = make_state()
    audit = AuditLog()
    first = RollService(state).roll("1d20+3", advantage="advantage")
    audit.append(
        state,
        idempotency_key="roll:first",
        tool_name="test.roll",
        tool_result={"total": first.total},
        dice_rolls=[first.to_dict()],
    )

    save_game(tmp_path / "slot", state, audit)
    loaded_state, loaded_audit = load_game(tmp_path / "slot")
    continued = RollService(loaded_state).roll("1d20+3", advantage="advantage")

    control = make_state()
    control_service = RollService(control)
    control_service.roll("1d20+3", advantage="advantage")
    expected_second = control_service.roll("1d20+3", advantage="advantage")

    assert loaded_state.roll_counter == 2
    assert continued.to_dict() == expected_second.to_dict()
    assert loaded_audit.events[0].to_dict()["dice_rolls"][0]["roll_id"] == "roll-00000000"


def test_world_effects_round_trip_in_save_file(tmp_path: Path, make_state) -> None:
    state = make_state()
    state.world.active_effects.append(
        {
            "effect_id": "world-effect-test",
            "source_action_id": "srd.detect_magic",
            "effect_type": "detect_magic",
        }
    )

    save_game(tmp_path / "slot", state, AuditLog())
    loaded_state, _ = load_game(tmp_path / "slot")

    assert loaded_state.world.active_effects == state.world.active_effects


def test_model_usage_round_trips_in_audit_log(tmp_path: Path, make_state) -> None:
    state = make_state()
    audit = AuditLog()
    audit.append(
        state,
        idempotency_key="model:first",
        tool_name="dm.model_draft",
        tool_result={"draft": {}},
        model_id="fake-dm",
        prompt_version="test-v1",
        model_usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    )

    save_game(tmp_path / "slot", state, audit)
    _, loaded_audit = load_game(tmp_path / "slot")

    assert loaded_audit.events[0].model_usage == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }
    assert loaded_audit.model_usage_totals()["total_tokens"] == 15


def test_character_resources_round_trip_in_save_file(tmp_path: Path, make_state) -> None:
    state = make_state()
    state.characters["pc1"].resources["srd.resource.second_wind"] = 1

    save_game(tmp_path / "slot", state, AuditLog())
    loaded_state, _ = load_game(tmp_path / "slot")

    assert loaded_state.characters["pc1"].resources == {"srd.resource.second_wind": 1}


def test_character_from_legacy_dict_defaults_languages() -> None:
    character = Character.from_dict(
        {
            "id": "pc-legacy",
            "name": "Legacy",
            "abilities": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
            "class_levels": {"fighter": 1},
            "proficiency_bonus": 2,
            "hp_current": 10,
            "hp_max": 10,
            "armor_class": 16,
        }
    )

    assert character.languages == []


def test_replay_roll_service_uses_audited_faces(make_state) -> None:
    state = make_state()
    roll = RollService(state).roll("2d6+1")
    replayed = ReplayRollService([roll.to_dict()]).roll("2d6+1")

    assert replayed.total == roll.total
    assert replayed.replayed is True

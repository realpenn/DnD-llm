from __future__ import annotations

from pathlib import Path

from dnd_llm.core.compendium.loader import CompendiumLoader
from dnd_llm.core.dice import RollService
from dnd_llm.core.effect_lifecycle import tick_effects
from dnd_llm.core.persistence import AuditLog, load_game, save_game
from dnd_llm.core.resolver import PlayerActionDraft
from dnd_llm.orchestrator.session import GameSession, SessionResult


def test_dodge_expires_on_next_self_turn_start(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "goblin1"]
    state.encounter.turn_index = 0
    state.characters["pc1"].actions.append("srd.dodge")
    session = GameSession(state, CompendiumLoader("rules_data").load(), AuditLog())

    action = session.submit_player_action(
        PlayerActionDraft(
            actor_id="pc1",
            verb="闪避",
            candidate_action_id="srd.dodge",
            raw_text="DD 闪避",
        ),
        "dodge-action",
    )

    assert isinstance(action, SessionResult)
    assert action.accepted is True
    assert state.encounter.current_combatant_id == "goblin1"
    assert any(
        effect.get("condition") == "dodging"
        for effect in state.encounter.combatants["pc1"].status_effects
    )

    advanced = session.advance_turn("advance-back-to-pc1")

    assert isinstance(advanced, SessionResult)
    assert advanced.accepted is True
    assert state.encounter.current_combatant_id == "pc1"
    assert state.encounter.combatants["pc1"].status_effects == []
    lifecycle = advanced.payload["effect_lifecycle"]
    assert lifecycle[0]["trigger"] == "self_turn_start"
    assert lifecycle[0]["expired"][0]["condition"] == "dodging"


def test_disengage_expires_on_current_self_turn_end(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "goblin1"]
    state.encounter.turn_index = 0
    state.characters["pc1"].actions.append("srd.disengage")
    audit = AuditLog()
    session = GameSession(state, CompendiumLoader("rules_data").load(), audit)

    action = session.submit_player_action(
        PlayerActionDraft(
            actor_id="pc1",
            verb="撤离",
            candidate_action_id="srd.disengage",
            raw_text="DD 撤离",
        ),
        "disengage-action",
    )

    assert isinstance(action, SessionResult)
    assert action.accepted is True
    assert state.encounter.current_combatant_id == "goblin1"
    assert state.encounter.combatants["pc1"].status_effects == []
    advance_event = next(
        event for event in audit.events if event.idempotency_key == "disengage-action:advance"
    )
    lifecycle = advance_event.tool_result["effect_lifecycle"]
    assert lifecycle[0]["trigger"] == "self_turn_end"
    assert lifecycle[0]["expired"][0]["condition"] == "disengaged"


def test_rage_expires_at_end_of_next_self_turn(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "goblin1"]
    state.encounter.turn_index = 0
    state.characters["pc1"].class_levels = {"barbarian": 1}
    state.characters["pc1"].actions.append("srd.rage")
    state.characters["pc1"].resources["srd.resource.rage"] = 1
    session = GameSession(state, CompendiumLoader("rules_data").load(), AuditLog())

    action = session.submit_player_action(
        PlayerActionDraft(
            actor_id="pc1",
            verb="狂暴",
            candidate_action_id="srd.rage",
            raw_text="DD 狂暴",
        ),
        "rage-action",
    )

    assert isinstance(action, SessionResult)
    assert action.accepted is True
    rage_effect = state.encounter.combatants["pc1"].status_effects[0]
    assert rage_effect["condition"] == "raging"
    assert rage_effect["duration"]["remaining_ticks"] == 1

    advanced_to_pc = session.advance_turn("advance-back-to-raging-pc")

    assert isinstance(advanced_to_pc, SessionResult)
    assert state.encounter.current_combatant_id == "pc1"
    assert state.encounter.combatants["pc1"].status_effects[0]["condition"] == "raging"

    expired = session.advance_turn("advance-rage-expiry")

    assert isinstance(expired, SessionResult)
    assert state.encounter.combatants["pc1"].status_effects == []
    lifecycle = expired.payload["effect_lifecycle"]
    assert lifecycle[0]["trigger"] == "self_turn_end"
    assert lifecycle[0]["expired"][0]["condition"] == "raging"


def test_longer_duration_ticks_and_round_trips(tmp_path: Path, make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["goblin1", "pc1"]
    state.encounter.turn_index = 0
    state.encounter.combatants["pc1"].status_effects.append(
        {
            "effect_id": "effect-long",
            "source_ref": "test",
            "source_action_id": "test.duration",
            "target_id": "pc1",
            "applied_by": "pc1",
            "condition": "blessed",
            "duration": {"until": "duration_1_minute"},
            "tick_on": "self_turn_start",
        }
    )
    audit = AuditLog()
    session = GameSession(state, CompendiumLoader("rules_data").load(), audit)

    advanced = session.advance_turn("advance-to-duration-owner")

    assert isinstance(advanced, SessionResult)
    assert advanced.accepted is True
    effect = state.encounter.combatants["pc1"].status_effects[0]
    assert effect["duration"]["remaining_ticks"] == 9
    assert advanced.payload["effect_lifecycle"][0]["ticked"][0]["remaining_ticks_after"] == 9

    save_game(tmp_path / "slot", state, audit)
    loaded_state, loaded_audit = load_game(tmp_path / "slot")

    assert loaded_state.to_dict() == state.to_dict()
    assert len(loaded_audit.events) == len(audit.events)


def test_eight_hour_duration_ticks_from_inferred_remaining_ticks(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["pc1"].status_effects.append(
        {
            "effect_id": "effect-eight-hours",
            "source_ref": "test",
            "source_action_id": "test.duration_8_hours",
            "target_id": "pc1",
            "applied_by": "pc1",
            "condition": None,
            "duration": {"until": "duration_8_hours"},
            "tick_on": "self_turn_start",
        }
    )

    result = tick_effects(state, trigger="self_turn_start", actor_id="pc1")

    assert result.changed is True
    assert (
        state.encounter.combatants["pc1"].status_effects[0]["duration"]["remaining_ticks"] == 4799
    )
    assert result.ticked[0]["remaining_ticks_before"] == 4800
    assert result.ticked[0]["remaining_ticks_after"] == 4799


def test_repeat_save_effect_ends_on_success_with_roll_service(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    target = state.encounter.combatants["goblin1"]
    target.abilities = {"str": 10, "dex": 10, "con": 30, "int": 10, "wis": 10, "cha": 10}
    target.status_effects.append(
        {
            "effect_id": "poison-repeat",
            "source_ref": "test",
            "source_action_id": "srd.cunning_strike",
            "target_id": "goblin1",
            "applied_by": "pc1",
            "condition": "poisoned",
            "duration": {
                "until": "duration_1_minute",
                "repeat_save": {
                    "ability": "con",
                    "dc": 1,
                    "dc_source": "cunning_strike:dex+proficiency",
                    "end_on_success": True,
                },
            },
            "tick_on": "target_turn_end",
        }
    )

    result = tick_effects(
        state,
        trigger="target_turn_end",
        actor_id="goblin1",
        roll_service=RollService(state),
    )

    assert result.changed is True
    assert target.status_effects == []
    assert result.expired[0]["condition"] == "poisoned"
    assert result.expired[0]["repeat_save"]["success"] is True
    assert result.expired[0]["repeat_save"]["roll"]["expression"] == "1d20+10"

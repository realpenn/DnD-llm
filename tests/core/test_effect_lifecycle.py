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


def test_turn_owner_self_turn_effect_waits_for_owner_turn_start(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin1"].status_effects.append(
        {
            "effect_id": "hamstring-test",
            "source_action_id": "srd.brutal_strike",
            "target_id": "goblin1",
            "applied_by": "pc1",
            "condition": "hamstring_blow",
            "duration": {"until": "start_of_next_turn", "turn_owner_id": "pc1"},
            "tick_on": "self_turn_start",
            "passive_modifiers": {"speed_bonus_ft": -15},
        }
    )

    target_turn = tick_effects(state, trigger="self_turn_start", actor_id="goblin1")
    owner_turn = tick_effects(state, trigger="self_turn_start", actor_id="pc1")

    assert target_turn.changed is False
    assert owner_turn.expired[0]["condition"] == "hamstring_blow"
    assert state.encounter.combatants["goblin1"].status_effects == []


def test_staggering_blow_consumes_next_saving_throw_on_repeat_save(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    target = state.encounter.combatants["goblin1"]
    target.status_effects.extend(
        [
            {
                "effect_id": "staggering-repeat",
                "source_ref": "test",
                "source_action_id": "srd.brutal_strike",
                "target_id": "goblin1",
                "applied_by": "pc1",
                "condition": "staggering_blow_save_disadvantage",
                "duration": {"until": "start_of_next_turn", "turn_owner_id": "pc1"},
                "tick_on": "self_turn_start",
                "passive_modifiers": {"next_saving_throw_disadvantage": True},
            },
            {
                "effect_id": "repeat-save-staggered",
                "source_ref": "test",
                "source_action_id": "test.repeat_save",
                "target_id": "goblin1",
                "applied_by": "pc1",
                "condition": "poisoned",
                "duration": {
                    "until": "duration_1_minute",
                    "repeat_save": {
                        "ability": "wis",
                        "dc": 99,
                        "dc_source": "test",
                        "end_on_success": True,
                    },
                },
                "tick_on": "target_turn_end",
            },
        ]
    )

    result = tick_effects(
        state,
        trigger="target_turn_end",
        actor_id="goblin1",
        roll_service=RollService(state),
    )

    repeat_save = result.ticked[0]["repeat_save"]
    assert repeat_save["status_advantage"] == "disadvantage"
    assert repeat_save["status_sources"][0]["modifier"] == "next_saving_throw_disadvantage"
    assert repeat_save["consumed_effects"][0]["condition"] == ("staggering_blow_save_disadvantage")
    assert [effect["condition"] for effect in target.status_effects] == ["poisoned"]


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


def test_effect_with_ends_if_condition_expires_when_condition_present(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["pc1"].status_effects.extend(
        [
            {
                "effect_id": "superior-defense-test",
                "source_ref": "test",
                "source_action_id": "srd.superior_defense",
                "target_id": "pc1",
                "applied_by": "pc1",
                "condition": "superior_defense",
                "passive_modifiers": {"ends_if_condition": "incapacitated"},
                "duration": {"until": "duration_1_minute"},
                "tick_on": "self_turn_start",
            },
            {
                "effect_id": "incapacitated-test",
                "source_ref": "test",
                "source_action_id": "test.incapacitated",
                "target_id": "pc1",
                "applied_by": "goblin1",
                "condition": "incapacitated",
                "duration": {"until": "duration_1_minute"},
                "tick_on": "self_turn_start",
            },
        ]
    )

    result = tick_effects(state, trigger="self_turn_start", actor_id="pc1")

    assert result.expired[0]["source_action_id"] == "srd.superior_defense"
    assert result.expired[0]["ended_by_condition"] == "incapacitated"
    assert result.ticked[0]["source_action_id"] == "test.incapacitated"
    assert [
        effect["source_action_id"] for effect in state.encounter.combatants["pc1"].status_effects
    ] == ["test.incapacitated"]


def test_multi_day_duration_variants_tick_from_inferred_remaining_ticks(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    durations = [
        ("effect-ten-days", "duration_10_days_or_harmed", 144000),
        ("effect-thirty-days", "duration_30_days_or_harmed", 432000),
        ("effect-year-and-day", "duration_366_days_or_harmed", 5270400),
    ]
    for effect_id, until, _ticks in durations:
        state.encounter.combatants["pc1"].status_effects.append(
            {
                "effect_id": effect_id,
                "source_ref": "test",
                "source_action_id": "test.multi_day_duration",
                "target_id": "pc1",
                "applied_by": "pc1",
                "condition": None,
                "duration": {"until": until},
                "tick_on": "self_turn_start",
            }
        )

    result = tick_effects(state, trigger="self_turn_start", actor_id="pc1")

    assert result.changed is True
    assert [entry["remaining_ticks_before"] for entry in result.ticked] == [
        ticks for _effect_id, _until, ticks in durations
    ]
    assert [entry["remaining_ticks_after"] for entry in result.ticked] == [
        ticks - 1 for _effect_id, _until, ticks in durations
    ]
    assert [
        effect["duration"]["remaining_ticks"]
        for effect in state.encounter.combatants["pc1"].status_effects
    ] == [ticks - 1 for _effect_id, _until, ticks in durations]
    assert result.expired == []


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


def test_disciplined_survivor_grants_proficiency_on_repeat_save(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    monk = state.characters["pc1"]
    monk.class_levels = {"monk": 14}
    monk.proficiency_bonus = 5
    monk.abilities["wis"] = 10
    monk.resources["srd.resource.focus_points"] = 1
    target = state.encounter.combatants["pc1"]
    target.status_effects.append(
        {
            "effect_id": "repeat-save-test",
            "source_ref": "test",
            "source_action_id": "test.repeat_save",
            "target_id": "pc1",
            "applied_by": "goblin1",
            "condition": "frightened",
            "duration": {
                "until": "duration_1_minute",
                "repeat_save": {
                    "ability": "wis",
                    "dc": 1,
                    "dc_source": "test",
                    "end_on_success": True,
                },
            },
            "tick_on": "self_turn_end",
        }
    )

    result = tick_effects(
        state,
        trigger="self_turn_end",
        actor_id="pc1",
        roll_service=RollService(state),
    )

    repeat_save = result.expired[0]["repeat_save"]
    assert repeat_save["base_bonus"] == 5
    assert repeat_save["bonus"] == 5
    assert repeat_save["proficient"] is True
    assert repeat_save["proficiency_sources"] == [
        {
            "kind": "disciplined_survivor",
            "source_action_id": "srd.disciplined_survivor",
            "ability": "wis",
        }
    ]
    assert repeat_save["roll"]["expression"] == "1d20+5"
    assert monk.resources["srd.resource.focus_points"] == 1
    assert "disciplined_survivor" not in repeat_save


def test_slippery_mind_grants_proficiency_on_repeat_save(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    rogue = state.characters["pc1"]
    rogue.class_levels = {"rogue": 15}
    rogue.proficiency_bonus = 5
    rogue.saving_throw_proficiencies = ["dex", "int"]
    rogue.abilities["cha"] = 10
    target = state.encounter.combatants["pc1"]
    target.status_effects.append(
        {
            "effect_id": "repeat-save-test",
            "source_ref": "test",
            "source_action_id": "test.repeat_save",
            "target_id": "pc1",
            "applied_by": "goblin1",
            "condition": "frightened",
            "duration": {
                "until": "duration_1_minute",
                "repeat_save": {
                    "ability": "cha",
                    "dc": 1,
                    "dc_source": "test",
                    "end_on_success": True,
                },
            },
            "tick_on": "self_turn_end",
        }
    )

    result = tick_effects(
        state,
        trigger="self_turn_end",
        actor_id="pc1",
        roll_service=RollService(state),
    )

    repeat_save = result.expired[0]["repeat_save"]
    assert repeat_save["base_bonus"] == 5
    assert repeat_save["bonus"] == 5
    assert repeat_save["proficient"] is True
    assert repeat_save["proficiency_sources"] == [
        {
            "kind": "slippery_mind",
            "source_action_id": "srd.slippery_mind",
            "ability": "cha",
        }
    ]
    assert repeat_save["roll"]["expression"] == "1d20+5"


def test_monk_self_restoration_removes_single_eligible_condition(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"monk": 10}
    state.encounter.combatants["pc1"].status_effects.append(
        {"effect_id": "combat-poison", "condition": "poisoned"}
    )
    state.characters["pc1"].status_effects.append(
        {"effect_id": "character-poison", "condition": "poisoned"}
    )

    result = tick_effects(state, trigger="self_turn_end", actor_id="pc1")

    assert result.changed is True
    assert state.encounter.combatants["pc1"].status_effects == []
    assert state.characters["pc1"].status_effects == []
    assert result.removed == [
        {
            "type": "self_restoration",
            "action_id": "srd.self_restoration",
            "actor_id": "pc1",
            "removed": {"poisoned": 2},
            "removed_owners": [
                {
                    "owner_type": "character",
                    "owner_id": "pc1",
                    "condition": "poisoned",
                    "count": 1,
                },
                {
                    "owner_type": "combatant",
                    "owner_id": "pc1",
                    "condition": "poisoned",
                    "count": 1,
                },
            ],
        }
    ]


def test_monk_self_restoration_requires_choice_for_multiple_conditions(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"monk": 10}
    state.encounter.combatants["pc1"].status_effects.extend(
        [
            {"effect_id": "combat-charm", "condition": "charmed"},
            {"effect_id": "combat-poison", "condition": "poisoned"},
        ]
    )

    result = tick_effects(state, trigger="self_turn_end", actor_id="pc1")

    assert result.changed is True
    assert [effect["condition"] for effect in state.encounter.combatants["pc1"].status_effects] == [
        "charmed",
        "poisoned",
    ]
    assert result.removed == []
    assert result.choice_required == [
        {
            "type": "self_restoration",
            "action_id": "srd.self_restoration",
            "actor_id": "pc1",
            "conditions": ["charmed", "poisoned"],
            "reason": "multiple_eligible_conditions",
        }
    ]


def test_monk_self_restoration_does_not_apply_before_level_ten(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"monk": 9}
    state.encounter.combatants["pc1"].status_effects.append(
        {"effect_id": "combat-fright", "condition": "frightened"}
    )

    result = tick_effects(state, trigger="self_turn_end", actor_id="pc1")

    assert result.changed is False
    assert state.encounter.combatants["pc1"].status_effects == [
        {"effect_id": "combat-fright", "condition": "frightened"}
    ]

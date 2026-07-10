from __future__ import annotations

from dnd_llm.core.compendium.loader import CompendiumLoader
from dnd_llm.core.dice import RollService
from dnd_llm.core.models import GameState
from dnd_llm.core.persistence import AuditLog, load_game, save_game
from dnd_llm.core.resolver import PlayerActionDraft
from dnd_llm.orchestrator.reactions import ReactionManager
from dnd_llm.orchestrator.session import GameSession, SessionResult
from dnd_llm.orchestrator.tactics import MonsterTacticProfile, MonsterTacticsLibrary, TacticOption
from dnd_llm.orchestrator.timeout import TimeoutController, TimeoutPolicy


def _session_for_state(state: GameState) -> GameSession:
    return GameSession(state, CompendiumLoader("rules_data").load(), AuditLog())


def test_monster_tactics_are_seeded_and_repeatable(make_state) -> None:
    state_a = make_state()
    state_b = make_state()
    for state in (state_a, state_b):
        assert state.encounter is not None
        state.encounter.initiative_order = ["goblin1", "pc1"]
        state.encounter.turn_index = 0
        state.encounter.combatants["goblin1"].position_node_id = "front"
        state.encounter.combatants["pc1"].position_node_id = "front"

    result_a = _session_for_state(state_a).run_current_monster_turn("monster-turn")
    result_b = _session_for_state(state_b).run_current_monster_turn("monster-turn")

    assert isinstance(result_a, SessionResult)
    assert isinstance(result_b, SessionResult)
    assert result_a.accepted is True
    assert result_a.payload["action_id"] == result_b.payload["action_id"]
    assert state_a.to_dict() == state_b.to_dict()


def test_srd_monster_tactic_profiles_use_loaded_actions() -> None:
    compendium = CompendiumLoader("rules_data").load()
    library = MonsterTacticsLibrary()

    for monster_name in (
        "bandit",
        "cultist",
        "giant rat",
        "kobold warrior",
        "warrior infantry",
        "skeleton",
        "wolf",
        "zombie",
    ):
        profile = library.profiles[monster_name]
        assert len(profile.options) >= 2
        assert all(option.action_id in compendium.actions for option in profile.options)
        assert not profile.use_llm

    bandit_captain = library.profiles["bandit captain"]
    assert bandit_captain.use_llm is True
    assert all(option.action_id in compendium.actions for option in bandit_captain.options)


def test_monster_tactics_filter_conditions_and_count_choice_roll(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["goblin1", "pc1"]
    state.encounter.turn_index = 0
    actor = state.encounter.combatants["goblin1"]
    actor.name = "Skeleton"
    actor.hp_current = actor.hp_max
    actor.actions = ["srd.skeleton_shortbow"]
    state.encounter.combatants["pc1"].position_node_id = "front"
    state.encounter.combatants["pc2"].position_node_id = "back"
    state.encounter.combatants["pc2"].hp_current = 1
    compendium = CompendiumLoader("rules_data").load()
    library = MonsterTacticsLibrary(
        {
            "skeleton": MonsterTacticProfile(
                monster_name="Skeleton",
                options=[
                    TacticOption(
                        "srd.dodge",
                        weight=99,
                        target="self",
                        when={"hp_ratio_lte": 0.1},
                    ),
                    TacticOption("srd.skeleton_shortbow", weight=1, target="lowest_hp_enemy"),
                ],
            )
        }
    )

    draft = library.draft_for_current_turn(
        state=state,
        actions=compendium.actions,
        roll_service=RollService(state),
    )

    assert state.roll_counter == 1
    assert draft.candidate_action_id == "srd.skeleton_shortbow"
    assert draft.target_ids == ["pc2"]


def test_monster_tactics_fall_back_to_combatant_stat_block_actions(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["goblin1", "pc1"]
    state.encounter.turn_index = 0
    state.encounter.combatants["goblin1"].position_node_id = "front"
    state.encounter.combatants["goblin1"].actions = ["srd.kobold_dagger"]
    state.encounter.combatants["pc1"].position_node_id = "front"

    result = _session_for_state(state).run_current_monster_turn("monster-stat-block-turn")

    assert isinstance(result, SessionResult)
    assert result.accepted is True
    assert result.payload["action_id"] == "srd.kobold_dagger"


def test_leader_monster_turn_prefers_planner_draft(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["goblin1", "pc1"]
    state.encounter.turn_index = 0
    leader = state.encounter.combatants["goblin1"]
    leader.name = "Bandit Captain"
    leader.actions = ["srd.bandit_captain_scimitar", "srd.bandit_captain_pistol"]
    leader.position_node_id = "front"
    state.encounter.combatants["pc1"].position_node_id = "front"
    audit = AuditLog()

    def planner(actor_id: str, now: int, idempotency_key: str) -> PlayerActionDraft:
        assert actor_id == "goblin1"
        assert idempotency_key == "leader-turn"
        return PlayerActionDraft(
            actor_id=actor_id,
            verb="scimitar",
            candidate_action_id="srd.bandit_captain_scimitar",
            target_ids=["pc1"],
            raw_text="[monster turn] LLM chooses the captain's scimitar",
        )

    session = GameSession(
        state,
        CompendiumLoader("rules_data").load(),
        audit,
        monster_turn_planner=planner,
    )

    result = session.run_current_monster_turn("leader-turn")

    assert isinstance(result, SessionResult)
    assert result.accepted is True
    assert result.payload["action_id"] == "srd.bandit_captain_scimitar"
    assert state.encounter.current_combatant_id == "pc1"
    event = next(event for event in audit.events if event.tool_name == "orchestrator.monster_turn")
    assert event.tool_result["source"] == "llm"


def test_regular_monster_turn_uses_tactics_without_planner(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["goblin1", "pc1"]
    state.encounter.turn_index = 0
    bandit = state.encounter.combatants["goblin1"]
    bandit.name = "Bandit"
    bandit.actions = ["srd.bandit_scimitar"]
    bandit.position_node_id = "front"
    state.encounter.combatants["pc1"].position_node_id = "front"
    audit = AuditLog()

    def planner(actor_id: str, now: int, idempotency_key: str) -> PlayerActionDraft:
        raise AssertionError("regular SRD monsters must use deterministic tactics")

    session = GameSession(
        state,
        CompendiumLoader("rules_data").load(),
        audit,
        monster_turn_planner=planner,
    )

    result = session.run_current_monster_turn("regular-monster-turn")

    assert isinstance(result, SessionResult)
    assert result.accepted is True
    assert result.payload["action_id"] == "srd.bandit_scimitar"
    event = next(event for event in audit.events if event.tool_name == "orchestrator.monster_turn")
    assert event.tool_result["source"] == "deterministic_tactics"


def test_movement_triggers_auto_opportunity_attack_reaction(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "goblin1"]
    state.encounter.turn_index = 0
    state.encounter.combatants["pc1"].speed_ft = 60
    session = GameSession(state, CompendiumLoader("rules_data").load(), AuditLog())

    result = session.submit_player_action(
        PlayerActionDraft(
            actor_id="pc1",
            verb="移动",
            candidate_action_id="srd.move",
            params={"to_position_node_id": "back"},
            raw_text="DD 我退到后排",
        ),
        "move-with-reaction",
    )

    assert isinstance(result, SessionResult)
    assert result.accepted is True
    assert result.payload["reactions"]
    assert "reaction_windows" not in result.payload
    assert result.payload["reactions"][0]["action_id"] == "srd.opportunity_attack"
    assert state.encounter.action_budgets["goblin1"]["reaction"] == 0
    assert state.encounter.pending_reactions == {}


def test_movement_opens_interactive_reaction_window_and_pauses_turn(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["goblin1", "pc1"]
    state.encounter.turn_index = 0
    state.encounter.combatants["goblin1"].position_node_id = "front"
    state.encounter.combatants["goblin1"].speed_ft = 60
    state.encounter.combatants["pc2"].position_node_id = "back"
    audit = AuditLog()
    session = GameSession(
        state,
        CompendiumLoader("rules_data").load(),
        audit,
        reactions=ReactionManager(mode="interactive"),
    )

    result = session.submit_player_action(
        PlayerActionDraft(
            actor_id="goblin1",
            verb="移动",
            candidate_action_id="srd.move",
            params={"to_position_node_id": "back"},
            raw_text="[monster] goblin withdraws",
        ),
        "move-with-window",
    )

    assert isinstance(result, SessionResult)
    assert result.accepted is True
    assert result.payload["reactions"] == []
    assert result.payload["reaction_windows"]
    assert result.payload["reaction_windows"][0]["actor_id"] == "pc1"
    assert state.encounter.current_combatant_id == "goblin1"
    assert state.encounter.action_budgets["pc1"]["reaction"] == 1
    assert state.encounter.pending_reactions
    assert any(event.tool_name == "orchestrator.reaction_window.open" for event in audit.events)


def test_confirmed_reaction_executes_before_turn_advances(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["goblin1", "pc1"]
    state.encounter.turn_index = 0
    state.encounter.combatants["goblin1"].position_node_id = "front"
    state.encounter.combatants["goblin1"].speed_ft = 60
    state.encounter.combatants["pc2"].position_node_id = "back"
    session = GameSession(
        state,
        CompendiumLoader("rules_data").load(),
        AuditLog(),
        reactions=ReactionManager(mode="interactive"),
    )

    move = session.submit_player_action(
        PlayerActionDraft(
            actor_id="goblin1",
            verb="移动",
            candidate_action_id="srd.move",
            params={"to_position_node_id": "back"},
            raw_text="[monster] goblin withdraws",
        ),
        "move-confirm-reaction",
    )
    assert isinstance(move, SessionResult)
    reaction_id = move.payload["reaction_windows"][0]["reaction_id"]

    confirmed = session.resolve_reaction(
        reaction_id=reaction_id,
        accept=True,
        now=move.payload["reaction_windows"][0]["opened_at"] + 1,
        idempotency_key="confirm-reaction",
    )

    assert isinstance(confirmed, SessionResult)
    assert confirmed.accepted is True
    assert confirmed.payload["status"] == "accepted"
    assert confirmed.payload["reaction"]["action_id"] == "srd.opportunity_attack"
    assert state.encounter.pending_reactions == {}
    assert state.encounter.action_budgets["pc1"]["reaction"] == 0
    assert state.encounter.current_combatant_id == "pc1"


def test_reaction_timeout_defaults_to_decline_and_advances_turn(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["goblin1", "pc1"]
    state.encounter.turn_index = 0
    state.encounter.combatants["goblin1"].position_node_id = "front"
    state.encounter.combatants["goblin1"].speed_ft = 60
    state.encounter.combatants["pc2"].position_node_id = "back"
    session = GameSession(
        state,
        CompendiumLoader("rules_data").load(),
        AuditLog(),
        reactions=ReactionManager(mode="interactive"),
    )

    move = session.submit_player_action(
        PlayerActionDraft(
            actor_id="goblin1",
            verb="移动",
            candidate_action_id="srd.move",
            params={"to_position_node_id": "back"},
            raw_text="[monster] goblin withdraws",
        ),
        "move-expire-reaction",
    )
    assert isinstance(move, SessionResult)
    timeout_at = move.payload["reaction_windows"][0]["timeout_at"]

    expired = session.expire_reactions(now=timeout_at, idempotency_key="expire-reaction")

    assert isinstance(expired, SessionResult)
    assert expired.accepted is True
    assert expired.payload["status"] == "expired"
    assert state.encounter.pending_reactions == {}
    assert state.encounter.action_budgets["pc1"]["reaction"] == 1
    assert state.encounter.current_combatant_id == "pc1"


def test_pending_reaction_window_round_trips_through_save(tmp_path, make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["goblin1", "pc1"]
    state.encounter.turn_index = 0
    state.encounter.combatants["goblin1"].position_node_id = "front"
    state.encounter.combatants["goblin1"].speed_ft = 60
    state.encounter.combatants["pc2"].position_node_id = "back"
    audit = AuditLog()
    session = GameSession(
        state,
        CompendiumLoader("rules_data").load(),
        audit,
        reactions=ReactionManager(mode="interactive"),
    )

    result = session.submit_player_action(
        PlayerActionDraft(
            actor_id="goblin1",
            verb="移动",
            candidate_action_id="srd.move",
            params={"to_position_node_id": "back"},
        ),
        "move-save-reaction",
    )
    assert isinstance(result, SessionResult)

    save_game(tmp_path / "slot", state, audit)
    loaded_state, _ = load_game(tmp_path / "slot")

    assert loaded_state.encounter is not None
    assert loaded_state.encounter.pending_reactions == state.encounter.pending_reactions


def test_session_advance_turn_idempotency_survives_save_load(tmp_path, make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "goblin1"]
    state.encounter.turn_index = 0
    audit = AuditLog()
    session = GameSession(state, CompendiumLoader("rules_data").load(), audit)
    session.set_current_time(100)

    first = session.advance_turn("restart-advance")
    assert isinstance(first, SessionResult)
    assert first.accepted is True
    save_game(tmp_path / "slot", state, audit)

    loaded_state, loaded_audit = load_game(tmp_path / "slot")
    restarted = GameSession(
        loaded_state,
        CompendiumLoader("rules_data").load(),
        loaded_audit,
    )
    current_before_retry = loaded_state.encounter.current_combatant_id
    event_count_before_retry = len(loaded_audit.events)

    repeated = restarted.advance_turn("restart-advance")

    assert repeated == first
    assert loaded_state.encounter.current_combatant_id == current_before_retry
    assert len(loaded_audit.events) == event_count_before_retry


def test_session_player_action_idempotency_survives_save_load(tmp_path, make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "goblin1"]
    state.encounter.turn_index = 0
    audit = AuditLog()
    session = GameSession(state, CompendiumLoader("rules_data").load(), audit)
    session.set_current_time(100)
    draft = PlayerActionDraft(
        actor_id="pc1",
        verb="短剑",
        candidate_action_id="srd.shortsword_attack",
        target_ids=["goblin1"],
    )

    first = session.submit_player_action(draft, "restart-action")
    assert isinstance(first, SessionResult)
    assert first.accepted is True
    save_game(tmp_path / "slot", state, audit)

    loaded_state, loaded_audit = load_game(tmp_path / "slot")
    restarted = GameSession(
        loaded_state,
        CompendiumLoader("rules_data").load(),
        loaded_audit,
    )
    current_before_retry = loaded_state.encounter.current_combatant_id
    roll_counter_before_retry = loaded_state.roll_counter
    event_count_before_retry = len(loaded_audit.events)

    repeated = restarted.submit_player_action(draft, "restart-action")

    assert repeated == first
    assert loaded_state.encounter.current_combatant_id == current_before_retry
    assert loaded_state.roll_counter == roll_counter_before_retry
    assert len(loaded_audit.events) == event_count_before_retry


def test_player_action_records_timeout_start_for_next_turn(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "goblin1"]
    state.encounter.turn_index = 0
    session = GameSession(state, CompendiumLoader("rules_data").load(), AuditLog())
    session.set_current_time(123)

    result = session.submit_player_action(
        PlayerActionDraft(
            actor_id="pc1",
            verb="短剑",
            candidate_action_id="srd.shortsword_attack",
            target_ids=["goblin1"],
        ),
        "records-timeout-start",
    )

    assert isinstance(result, SessionResult)
    assert result.accepted is True
    assert session.timeout.turn_started_at["goblin1"] == 123


def test_timeout_takeover_uses_character_tactic_and_advances_turn(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "goblin1"]
    state.encounter.turn_index = 0
    state.encounter.combatants["pc1"].position_node_id = "front"
    state.encounter.combatants["goblin1"].position_node_id = "front"
    state.characters["pc1"].actions = ["srd.longsword_attack", "srd.move"]
    session = GameSession(
        state,
        CompendiumLoader("rules_data").load(),
        AuditLog(),
        timeout=TimeoutController(TimeoutPolicy(timeout_seconds=10)),
    )
    session.mark_current_turn_started(now=100)

    result = session.run_timeout_takeover(now=111, idempotency_key="timeout-1")

    assert isinstance(result, SessionResult)
    assert result.accepted is True
    assert result.payload["action_id"] == "srd.longsword_attack"
    assert state.encounter.current_combatant_id == "goblin1"


def test_timeout_takeover_prefers_planner_draft(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "goblin1"]
    state.encounter.turn_index = 0
    state.encounter.combatants["pc1"].position_node_id = "front"
    state.encounter.combatants["goblin1"].position_node_id = "front"
    audit = AuditLog()

    def planner(actor_id: str, now: int, idempotency_key: str) -> PlayerActionDraft:
        assert actor_id == "pc1"
        assert now == 111
        assert idempotency_key == "timeout-planner"
        return PlayerActionDraft(
            actor_id=actor_id,
            verb="shortsword",
            candidate_action_id="srd.shortsword_attack",
            target_ids=["goblin1"],
            raw_text="[timeout takeover] LLM chooses a direct attack",
        )

    session = GameSession(
        state,
        CompendiumLoader("rules_data").load(),
        audit,
        timeout=TimeoutController(TimeoutPolicy(timeout_seconds=10)),
        timeout_takeover_planner=planner,
    )
    session.mark_current_turn_started(now=100)

    result = session.run_timeout_takeover(now=111, idempotency_key="timeout-planner")

    assert isinstance(result, SessionResult)
    assert result.accepted is True
    assert result.payload["action_id"] == "srd.shortsword_attack"
    assert state.encounter.current_combatant_id == "goblin1"
    timeout_event = next(
        event for event in audit.events if event.tool_name == "orchestrator.timeout_takeover"
    )
    assert timeout_event.tool_result["source"] == "llm"


def test_timeout_takeover_helps_nearby_ally_when_no_enemy_is_active(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "pc2"]
    state.encounter.turn_index = 0
    state.encounter.combatants["pc1"].position_node_id = "front"
    state.encounter.combatants["pc2"].position_node_id = "front"
    state.encounter.combatants["goblin1"].hp_current = 0
    session = GameSession(
        state,
        CompendiumLoader("rules_data").load(),
        AuditLog(),
        timeout=TimeoutController(TimeoutPolicy(timeout_seconds=10)),
    )
    session.mark_current_turn_started(now=100)

    result = session.run_timeout_takeover(now=111, idempotency_key="timeout-help")

    assert isinstance(result, SessionResult)
    assert result.accepted is True
    assert result.payload["action_id"] == "srd.help"
    assert state.encounter.combatants["pc2"].status_effects[-1]["condition"] == "helping"


def test_timeout_takeover_prefers_rogue_cunning_action_fallback(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "pc2", "goblin1"]
    state.encounter.turn_index = 0
    state.encounter.combatants["pc1"].position_node_id = "front"
    state.encounter.combatants["pc2"].hp_current = 0
    state.encounter.combatants["goblin1"].hp_current = 0
    state.characters["pc1"].class_levels = {"rogue": 2}
    state.characters["pc1"].actions = [
        "srd.shortsword_attack",
        "srd.hide",
        "srd.cunning_action_dash",
        "srd.cunning_action_disengage",
        "srd.cunning_action_hide",
    ]
    session = GameSession(
        state,
        CompendiumLoader("rules_data").load(),
        AuditLog(),
        timeout=TimeoutController(TimeoutPolicy(timeout_seconds=10)),
    )
    session.mark_current_turn_started(now=100)

    result = session.run_timeout_takeover(now=111, idempotency_key="timeout-cunning")

    assert isinstance(result, SessionResult)
    assert result.accepted is True
    assert result.payload["action_id"] == "srd.cunning_action_hide"
    assert state.encounter.action_budgets["pc1"]["action"] == 1
    assert state.encounter.action_budgets["pc1"]["bonus_action"] == 0

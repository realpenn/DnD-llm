from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from dnd_llm.content.campaign_pack import CampaignPackLoader
from dnd_llm.content.runtime import apply_campaign_pack
from dnd_llm.core.compendium.loader import CompendiumLoader
from dnd_llm.core.models import Combatant, GameState, Monster
from dnd_llm.core.persistence import AuditLog, load_game, save_game
from dnd_llm.core.positioning import TacticalGraph
from dnd_llm.core.resolver import PlayerActionDraft
from dnd_llm.orchestrator.session import GameSession, SessionResult
from dnd_llm.orchestrator.turn import roll_initiative


def test_session_starts_combat_prompts_turn_and_dedupes_player_action(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    combatants: dict[str, Combatant] = state.encounter.combatants
    graph = TacticalGraph.from_dict(state.encounter.tactical_graph or {})
    state.encounter = None
    compendium = CompendiumLoader("rules_data").load()
    session = GameSession(state, compendium, AuditLog())

    started = session.start_combat(
        encounter_id="scripted",
        combatants=combatants,
        tactical_graph=graph,
        idempotency_key="start-1",
    )

    assert isinstance(started, SessionResult)
    assert started.accepted is True
    assert state.encounter is not None
    assert state.encounter.current_combatant_id is not None
    assert session.current_turn_prompt()

    while state.encounter.current_combatant_id != "pc1":
        session.advance_turn(f"advance-to-pc1-{state.encounter.turn_index}")

    draft = PlayerActionDraft(
        actor_id="pc1",
        verb="短剑",
        target_ids=["goblin1"],
        candidate_action_id="srd.shortsword_attack",
        raw_text="DD 我用短剑攻击",
    )
    first = session.submit_player_action(draft, "player-action-1")
    roll_counter_after_first = state.roll_counter
    repeated = session.submit_player_action(draft, "player-action-1")

    assert isinstance(first, SessionResult)
    assert first.accepted is True
    assert repeated == first
    assert state.roll_counter == roll_counter_after_first
    assert state.encounter.current_combatant_id != "pc1"


def test_session_queue_dedupes_concurrent_player_action_resource_spend(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "pc2", "goblin1"]
    state.encounter.turn_index = 0
    state.characters["pc1"].hp_current = 6
    state.encounter.combatants["pc1"].hp_current = 6
    state.characters["pc1"].spell_slots = {"1": 1}
    session = GameSession(state, CompendiumLoader("rules_data").load(), AuditLog())
    draft = PlayerActionDraft(
        actor_id="pc1",
        verb="治疗术",
        target_ids=["pc1"],
        candidate_action_id="srd.cure_wounds",
        raw_text="DD 我治疗自己",
    )

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(
            executor.map(
                lambda _: session.submit_player_action(draft, "concurrent-cure-wounds"),
                range(4),
            )
        )

    assert all(isinstance(result, SessionResult) for result in results)
    assert all(result.accepted for result in results if isinstance(result, SessionResult))
    assert results == [results[0]] * 4
    assert state.characters["pc1"].spell_slots["1"] == 0
    assert state.encounter.combatants["pc1"].hp_current > 6
    assert state.encounter.current_combatant_id == "pc2"
    assert state.roll_counter == 1


def test_session_pauses_auto_advance_for_open_hand_fleet_step(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "pc2", "goblin1"]
    state.encounter.turn_index = 0
    character = state.characters["pc1"]
    character.class_levels = {"monk": 11}
    character.subclasses = {"monk": "open_hand"}
    character.actions.extend(["srd.patient_defense", "srd.step_of_the_wind", "srd.fleet_step"])
    session = GameSession(state, CompendiumLoader("rules_data").load(), AuditLog())

    trigger = session.submit_player_action(
        PlayerActionDraft(
            actor_id="pc1",
            verb="patient defense",
            candidate_action_id="srd.patient_defense",
            raw_text="DD 我用忍耐防御",
        ),
        "fleet-step-session-trigger",
    )

    assert trigger.accepted is True
    assert trigger.payload["fleet_step_available"] is True
    assert trigger.payload["next_combatant_id"] == "pc1"
    assert state.encounter.current_combatant_id == "pc1"

    step = session.submit_player_action(
        PlayerActionDraft(
            actor_id="pc1",
            verb="step of the wind",
            candidate_action_id="srd.step_of_the_wind",
            params={"use_fleet_step": True},
            raw_text="DD 我立刻风步",
        ),
        "fleet-step-session-step",
    )

    assert step.accepted is True
    assert step.payload["next_combatant_id"] == "pc2"
    assert state.encounter.current_combatant_id == "pc2"


def test_start_combat_initial_budget_uses_exhaustion_adjusted_speed(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    combatants: dict[str, Combatant] = state.encounter.combatants
    graph = TacticalGraph.from_dict(state.encounter.tactical_graph or {})
    for combatant in combatants.values():
        combatant.speed_ft = 40
    for character in state.characters.values():
        character.status_effects.append(
            {"effect_id": f"exhaustion-{character.id}", "condition": "exhaustion", "level": 2}
        )
    state.encounter = None
    session = GameSession(state, CompendiumLoader("rules_data").load(), AuditLog())

    started = session.start_combat(
        encounter_id="scripted",
        combatants=combatants,
        tactical_graph=graph,
        idempotency_key="start-exhaustion",
    )

    assert isinstance(started, SessionResult)
    assert started.accepted is True
    assert state.encounter is not None
    current = state.encounter.current_combatant_id
    assert current is not None
    expected_movement = 30 if current in state.characters else 40
    assert state.encounter.action_budgets[current]["movement"] == expected_movement


def test_start_combat_loads_tactical_graph_from_campaign_zone(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    combatants: dict[str, Combatant] = state.encounter.combatants
    state.encounter = None
    compendium = CompendiumLoader("rules_data").load()
    pack = CampaignPackLoader().load("rules_data/campaigns/starter/pack.json")
    apply_campaign_pack(state, pack)
    state.world.current_zone_id = "ruins"
    session = GameSession(state, compendium, AuditLog(), campaign_pack=pack)

    started = session.start_combat(
        encounter_id="scripted",
        combatants=combatants,
        zone_id="ruins",
        idempotency_key="start-zone-graph",
    )

    assert isinstance(started, SessionResult)
    assert started.accepted is True
    assert state.encounter is not None
    assert state.encounter.tactical_graph == pack.zones["ruins"]["tactical_graph"]
    assert started.payload["zone_id"] == "ruins"
    assert started.payload["tactical_graph_source"] == "campaign_pack"
    assert "generated_tactical_graphs" not in state.world.flags


def test_start_combat_generates_and_persists_missing_zone_tactical_graph(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    combatants: dict[str, Combatant] = state.encounter.combatants
    state.encounter = None
    compendium = CompendiumLoader("rules_data").load()
    pack = CampaignPackLoader().load("rules_data/campaigns/starter/pack.json")
    apply_campaign_pack(state, pack)
    state.world.current_zone_id = "vault"
    session = GameSession(state, compendium, AuditLog(), campaign_pack=pack)

    first = session.start_combat(
        encounter_id="scripted",
        combatants=combatants,
        zone_id="vault",
        idempotency_key="start-generated-graph-1",
    )

    assert isinstance(first, SessionResult)
    assert first.accepted is True
    assert state.encounter is not None
    generated = state.world.flags["generated_tactical_graphs"]["vault"]
    assert state.encounter.tactical_graph == generated
    assert first.payload["tactical_graph_source"] == "generated_template"

    first_graph = state.encounter.tactical_graph
    state.encounter = None
    second = session.start_combat(
        encounter_id="scripted",
        combatants=combatants,
        zone_id="vault",
        idempotency_key="start-generated-graph-2",
    )

    assert isinstance(second, SessionResult)
    assert second.accepted is True
    assert state.encounter is not None
    assert state.encounter.tactical_graph == first_graph
    assert state.world.flags["generated_tactical_graphs"]["vault"] == first_graph


def test_session_state_machine_transitions_are_queued_and_audited(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    combatants: dict[str, Combatant] = state.encounter.combatants
    graph = TacticalGraph.from_dict(state.encounter.tactical_graph or {})
    state.encounter = None
    state.session_mode = "exploration"
    audit = AuditLog()
    session = GameSession(state, CompendiumLoader("rules_data").load(), audit)

    cutscene = session.enter_cutscene(
        idempotency_key="scene-cutscene",
        reason="chapter transition",
    )
    event_counter_after_cutscene = state.event_counter
    repeated_cutscene = session.enter_cutscene(
        idempotency_key="scene-cutscene",
        reason="chapter transition",
    )
    exit_cutscene = session.exit_cutscene("scene-exploration")
    started = session.start_combat(
        encounter_id="scripted",
        combatants=combatants,
        tactical_graph=graph,
        idempotency_key="scene-combat",
    )
    blocked_cutscene = session.enter_cutscene(idempotency_key="scene-blocked")
    ended = session.end_combat("scene-end-combat")

    assert isinstance(cutscene, SessionResult)
    assert cutscene.accepted is True
    assert repeated_cutscene == cutscene
    assert state.event_counter == event_counter_after_cutscene + 4
    assert isinstance(exit_cutscene, SessionResult)
    assert exit_cutscene.payload["session_mode"] == "exploration"
    assert isinstance(started, SessionResult)
    assert started.accepted is True
    assert state.session_mode == "exploration"
    assert isinstance(blocked_cutscene, SessionResult)
    assert blocked_cutscene.accepted is False
    assert isinstance(ended, SessionResult)
    assert ended.accepted is True
    assert state.encounter is None
    assert [event.tool_name for event in audit.events if event.tool_name is not None] == [
        "orchestrator.enter_cutscene",
        "orchestrator.exit_cutscene",
        "orchestrator.roll_initiative",
        "orchestrator.start_combat",
        "orchestrator.end_combat",
    ]


def test_advance_turn_budget_uses_monk_unarmored_movement(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"monk": 2}
    state.characters["pc1"].equipment = []
    state.encounter.initiative_order = ["goblin1", "pc1"]
    state.encounter.turn_index = 0
    session = GameSession(state, CompendiumLoader("rules_data").load(), AuditLog())

    advanced = session.advance_turn("advance-to-unarmored-monk")

    assert isinstance(advanced, SessionResult)
    assert advanced.accepted is True
    assert state.encounter.current_combatant_id == "pc1"
    assert state.encounter.action_budgets["pc1"]["movement"] == 40


def test_advance_turn_budget_uses_ranger_roving_when_not_in_heavy_armor(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"ranger": 6}
    state.characters["pc1"].equipment = []
    state.encounter.initiative_order = ["goblin1", "pc1"]
    state.encounter.turn_index = 0
    session = GameSession(state, CompendiumLoader("rules_data").load(), AuditLog())

    advanced = session.advance_turn("advance-to-roving-ranger")

    assert isinstance(advanced, SessionResult)
    assert advanced.accepted is True
    assert state.encounter.current_combatant_id == "pc1"
    assert state.encounter.action_budgets["pc1"]["movement"] == 40


def test_champion_survivor_heroic_rally_heals_on_turn_start(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    combatant = state.encounter.combatants["pc1"]
    character.class_levels = {"fighter": 18}
    character.subclasses = {"fighter": "champion"}
    character.abilities["con"] = 14
    character.hp_max = 20
    character.hp_current = 9
    combatant.hp_max = 20
    combatant.hp_current = 9
    state.encounter.initiative_order = ["goblin1", "pc1"]
    state.encounter.turn_index = 0
    audit = AuditLog()
    session = GameSession(state, CompendiumLoader("rules_data").load(), audit)

    advanced = session.advance_turn("advance-to-survivor")

    assert isinstance(advanced, SessionResult)
    assert advanced.accepted is True
    assert state.encounter.current_combatant_id == "pc1"
    assert combatant.hp_current == 16
    assert character.hp_current == 16
    assert advanced.payload["heroic_rally"] == {
        "combatant_id": "pc1",
        "character_id": "pc1",
        "source_action_id": "srd.survivor",
        "healing": 7,
        "applied": 7,
        "combatant_hp_before": 9,
        "combatant_hp_after": 16,
        "character_hp_before": 9,
        "character_hp_after": 16,
    }
    assert audit.events[-1].tool_result["heroic_rally"]["source_action_id"] == "srd.survivor"


def test_champion_heroic_warrior_grants_heroic_inspiration_on_turn_start(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"fighter": 10}
    character.subclasses = {"fighter": "champion"}
    state.encounter.initiative_order = ["goblin1", "pc1"]
    state.encounter.turn_index = 0
    audit = AuditLog()
    session = GameSession(state, CompendiumLoader("rules_data").load(), audit)

    advanced = session.advance_turn("advance-to-heroic-warrior")

    assert isinstance(advanced, SessionResult)
    assert advanced.accepted is True
    assert character.resources["srd.resource.heroic_inspiration"] == 1
    assert advanced.payload["heroic_inspiration"] == {
        "combatant_id": "pc1",
        "character_id": "pc1",
        "source_action_id": "srd.heroic_warrior",
        "resource": "srd.resource.heroic_inspiration",
        "before": 0,
        "after": 1,
    }
    assert audit.events[-1].tool_result["heroic_inspiration"]["source_action_id"] == (
        "srd.heroic_warrior"
    )


def test_champion_heroic_warrior_does_not_grant_when_already_inspired(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"fighter": 10}
    character.subclasses = {"fighter": "champion"}
    character.resources["srd.resource.heroic_inspiration"] = 1
    state.encounter.initiative_order = ["goblin1", "pc1"]
    state.encounter.turn_index = 0
    session = GameSession(state, CompendiumLoader("rules_data").load(), AuditLog())

    advanced = session.advance_turn("advance-to-already-inspired-heroic-warrior")

    assert isinstance(advanced, SessionResult)
    assert advanced.accepted is True
    assert character.resources["srd.resource.heroic_inspiration"] == 1
    assert "heroic_inspiration" not in advanced.payload


def test_session_rejects_out_of_turn_action(make_state) -> None:
    state = make_state()
    compendium = CompendiumLoader("rules_data").load()
    session = GameSession(state, compendium, AuditLog())
    assert state.encounter is not None
    state.encounter.initiative_order = ["goblin1", "pc1"]
    state.encounter.turn_index = 0

    result = session.submit_player_action(
        PlayerActionDraft(
            actor_id="pc1",
            verb="短剑",
            target_ids=["goblin1"],
            candidate_action_id="srd.shortsword_attack",
        ),
        "out-of-turn",
    )

    assert isinstance(result, SessionResult)
    assert result.accepted is False
    assert result.payload["reason"] == "not actor turn"


def test_session_rejects_movement_without_destination_instead_of_raising(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "pc2", "goblin1"]
    state.encounter.turn_index = 0
    state.characters["pc1"].actions.append("srd.move")
    session = GameSession(state, CompendiumLoader("rules_data").load(), AuditLog())

    result = session.submit_player_action(
        PlayerActionDraft(
            actor_id="pc1",
            verb="移动",
            candidate_action_id="srd.move",
            raw_text="DD 移动到遗迹入口",
        ),
        "move-without-destination",
    )

    assert isinstance(result, SessionResult)
    assert result.accepted is False
    assert result.payload["status"] == "rejected"
    assert result.payload["reason"] == "move requires exactly one destination"
    assert state.encounter.current_combatant_id == "pc1"


def test_end_combat_preserves_character_and_monster_status_effects(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.monsters["goblin1"] = Monster(
        id="goblin1",
        name="Goblin",
        abilities={"str": 8, "dex": 14, "con": 10, "int": 10, "wis": 8, "cha": 8},
        hp_current=7,
        hp_max=7,
        armor_class=12,
    )
    character_effect = {
        "effect_id": "character-poison",
        "source_action_id": "test.poison",
        "target_id": "pc2",
        "applied_by": "goblin1",
        "condition": "poisoned",
        "duration": {"until": "duration_1_hour"},
        "tick_on": "self_turn_start",
    }
    monster_effect = {
        "effect_id": "monster-poison",
        "source_action_id": "test.poison",
        "target_id": "goblin1",
        "applied_by": "pc1",
        "condition": "poisoned",
        "duration": {"until": "duration_1_hour"},
        "tick_on": "self_turn_start",
    }
    state.encounter.combatants["pc2"].status_effects.append(character_effect)
    state.encounter.combatants["goblin1"].status_effects.append(monster_effect)
    session = GameSession(state, CompendiumLoader("rules_data").load(), AuditLog())

    ended = session.end_combat("preserve-cross-combat-effects")

    assert isinstance(ended, SessionResult)
    assert ended.accepted is True
    assert state.encounter is None
    assert state.characters["pc2"].status_effects == [character_effect]
    assert state.monsters["goblin1"].status_effects == [monster_effect]


def test_end_combat_does_not_restore_effect_removed_from_combatant(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    stale_effect = {
        "effect_id": "expired-poison",
        "source_action_id": "test.poison",
        "target_id": "pc2",
        "applied_by": "goblin1",
        "condition": "poisoned",
    }
    state.characters["pc2"].status_effects = [stale_effect]
    state.encounter.combatants["pc2"].status_effects = []
    state.encounter.status_effect_baselines["pc2"] = [stale_effect]
    session = GameSession(state, CompendiumLoader("rules_data").load(), AuditLog())

    ended = session.end_combat("remove-expired-cross-combat-effect")

    assert isinstance(ended, SessionResult)
    assert ended.accepted is True
    assert state.characters["pc2"].status_effects == []


def test_end_combat_preserves_long_term_effect_added_directly_to_character(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.status_effect_baselines["pc1"] = []
    session = GameSession(state, CompendiumLoader("rules_data").load(), AuditLog())

    result = session.tools.apply_hazard(
        ["pc1"],
        "srd.dehydration",
        {"source": "rules_discrete"},
        idempotency_key="dehydration-during-combat",
    )
    ended = session.end_combat("preserve-dehydration-after-combat")

    assert result["success"] is True
    assert isinstance(ended, SessionResult)
    assert ended.accepted is True
    exhaustion = next(
        effect
        for effect in state.characters["pc1"].status_effects
        if effect.get("condition") == "exhaustion"
    )
    assert exhaustion["level"] == 1


def test_end_combat_recovers_half_spent_ammunition_only_after_one_minute_search(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].inventory["srd.arrow"] = 5
    state.encounter.ammunition_inventory_baselines = {"pc1": {"srd.arrow": 10}}
    session = GameSession(state, CompendiumLoader("rules_data").load(), AuditLog())

    result = session.end_combat("recover-ammunition", recover_ammunition=True)

    assert isinstance(result, SessionResult)
    assert result.accepted is True
    assert state.characters["pc1"].inventory["srd.arrow"] == 7
    assert result.payload["ammunition_recovered"] == {"pc1": {"srd.arrow": 2}}


def test_end_combat_does_not_recover_ammunition_without_search(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].inventory["srd.arrow"] = 5
    state.encounter.ammunition_inventory_baselines = {"pc1": {"srd.arrow": 10}}
    session = GameSession(state, CompendiumLoader("rules_data").load(), AuditLog())

    result = session.end_combat("do-not-recover-ammunition")

    assert isinstance(result, SessionResult)
    assert state.characters["pc1"].inventory["srd.arrow"] == 5
    assert result.payload["ammunition_recovered"] == {}


def test_legacy_encounter_status_baselines_migrate_and_round_trip(
    tmp_path,
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    baseline_effect = {
        "effect_id": "legacy-poison",
        "source_action_id": "test.poison",
        "target_id": "pc2",
        "applied_by": "goblin1",
        "condition": "poisoned",
    }
    state.characters["pc2"].status_effects = [baseline_effect]
    state.encounter.combatants["pc2"].status_effects = [baseline_effect]
    legacy_payload = state.to_dict()
    assert legacy_payload["encounter"] is not None
    legacy_payload["encounter"].pop("status_effect_baselines")

    migrated_state = GameState.from_dict(legacy_payload)

    assert migrated_state.encounter is not None
    assert migrated_state.encounter.status_effect_baselines["pc2"] == [baseline_effect]
    save_game(tmp_path / "slot", migrated_state, AuditLog())
    loaded_state, loaded_audit = load_game(tmp_path / "slot")

    assert loaded_state.encounter is not None
    assert loaded_state.encounter.status_effect_baselines["pc2"] == [baseline_effect]
    loaded_state.encounter.combatants["pc2"].status_effects = []
    long_term_effect = {
        "effect_id": "legacy-dehydration",
        "source_action_id": "srd.dehydration",
        "target_id": "pc2",
        "applied_by": "environment",
        "condition": "exhaustion",
        "level": 1,
    }
    loaded_state.characters["pc2"].status_effects.append(long_term_effect)
    session = GameSession(
        loaded_state,
        CompendiumLoader("rules_data").load(),
        loaded_audit,
    )

    ended = session.end_combat("end-legacy-encounter")

    assert isinstance(ended, SessionResult)
    assert ended.accepted is True
    assert loaded_state.characters["pc2"].status_effects == [long_term_effect]


def test_roll_initiative_groups_same_named_monsters(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["goblin2"] = Combatant(
        id="goblin2",
        entity_id="goblin2",
        name="Goblin",
        side="monsters",
        hp_current=7,
        hp_max=7,
        armor_class=12,
        position_node_id="cover",
    )
    audit = AuditLog()

    order = roll_initiative(state, audit)

    assert state.roll_counter == 3
    assert set(order) == {"pc1", "pc2", "goblin1", "goblin2"}
    goblin_positions = sorted(order.index(combatant_id) for combatant_id in ("goblin1", "goblin2"))
    assert goblin_positions[1] == goblin_positions[0] + 1
    assert audit.events[-1].tool_result["groups"]
    assert len(audit.events[-1].dice_rolls) == 3


def test_roll_initiative_uses_dexterity_and_alert_feat(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].feats = ["alert"]
    audit = AuditLog()

    roll_initiative(state, audit)

    groups = {group["group_key"]: group for group in audit.events[-1].tool_result["groups"]}
    assert groups["combatant:pc1"]["initiative_modifier"] == 4
    assert groups["combatant:pc1"]["initiative_modifier_sources"] == ["dex:2", "alert:2"]
    assert groups["combatant:pc2"]["initiative_modifier"] == 0


def test_roll_initiative_applies_champion_remarkable_athlete_advantage(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"fighter": 3}
    state.characters["pc1"].subclasses = {"fighter": "champion"}
    audit = AuditLog()

    roll_initiative(state, audit)

    groups = {group["group_key"]: group for group in audit.events[-1].tool_result["groups"]}
    assert groups["combatant:pc1"]["initiative_advantage_sources"] == ["remarkable_athlete"]
    assert any(roll["advantage"] == "advantage" for roll in audit.events[-1].dice_rolls)


def test_roll_initiative_applies_barbarian_feral_instinct_advantage(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"barbarian": 7}
    audit = AuditLog()

    roll_initiative(state, audit)

    groups = {group["group_key"]: group for group in audit.events[-1].tool_result["groups"]}
    assert groups["combatant:pc1"]["initiative_advantage_sources"] == ["feral_instinct"]
    assert any(roll["advantage"] == "advantage" for roll in audit.events[-1].dice_rolls)


def test_roll_initiative_applies_foresight_d20_test_advantage(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.combatants["pc1"].status_effects.append(
        {
            "effect_id": "foresight-test",
            "source_action_id": "srd.foresight",
            "condition": None,
            "passive_modifiers": {
                "initiative_advantage": True,
                "initiative_advantage_source": "srd.foresight",
            },
        }
    )
    audit = AuditLog()

    roll_initiative(state, audit)

    groups = {group["group_key"]: group for group in audit.events[-1].tool_result["groups"]}
    assert groups["combatant:pc1"]["initiative_advantage_sources"] == ["srd.foresight"]
    assert any(roll["advantage"] == "advantage" for roll in audit.events[-1].dice_rolls)


def test_roll_initiative_adds_thief_reflexes_second_first_round_turn(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"rogue": 17}
    character.subclasses = {"rogue": "thief"}
    audit = AuditLog()

    order = roll_initiative(state, audit)

    pc1_turns = [index for index, combatant_id in enumerate(order) if combatant_id == "pc1"]
    groups = {group["group_key"]: group for group in audit.events[-1].tool_result["groups"]}
    thiefs_reflexes = audit.events[-1].tool_result["thiefs_reflexes"]

    assert pc1_turns[1] > pc1_turns[0]
    assert len(pc1_turns) == 2
    assert thiefs_reflexes == [
        {
            "combatant_id": "pc1",
            "character_id": "pc1",
            "source_action_id": "srd.thiefs_reflexes",
            "normal_initiative": groups["combatant:pc1"]["initiative"],
            "second_turn_initiative": groups["combatant:pc1"]["initiative"] - 10,
            "initiative_penalty": -10,
            "round": 1,
        }
    ]


def test_thief_reflexes_extra_turn_is_removed_after_first_round(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"rogue": 17}
    character.subclasses = {"rogue": "thief"}
    roll_initiative(state, AuditLog())
    assert state.encounter.initiative_order.count("pc1") == 2
    session = GameSession(state, CompendiumLoader("rules_data").load(), AuditLog())

    advances = 0
    while state.encounter.round_number == 1:
        session.advance_turn(f"advance-thiefs-reflexes-{advances}")
        advances += 1
        assert advances <= 10

    assert state.encounter.round_number == 2
    assert state.encounter.initiative_order.count("pc1") == 1
    assert state.encounter.turn_index == 0
    assert state.encounter.current_combatant_id == state.encounter.initiative_order[0]


def test_roll_initiative_applies_monk_uncanny_metabolism_when_beneficial(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"monk": 5}
    character.resources["srd.resource.focus_points"] = 1
    character.resources["srd.resource.uncanny_metabolism"] = 1
    character.hp_current = 10
    character.hp_max = 30
    state.encounter.combatants["pc1"].hp_current = 10
    state.encounter.combatants["pc1"].hp_max = 30
    audit = AuditLog()

    roll_initiative(state, audit)

    result = audit.events[-1].tool_result["uncanny_metabolism"][0]
    healing_roll = audit.events[-1].dice_rolls[-1]
    expected_healing = 5 + int(healing_roll["total"])
    assert result["source_action_id"] == "srd.uncanny_metabolism"
    assert result["martial_arts_die"] == "d8"
    assert healing_roll["expression"] == "1d8"
    assert result["focus_before"] == 1
    assert result["focus_after"] == 5
    assert character.resources["srd.resource.focus_points"] == 5
    assert character.resources["srd.resource.uncanny_metabolism"] == 0
    assert character.hp_current == 10 + expected_healing
    assert state.encounter.combatants["pc1"].hp_current == 10 + expected_healing


def test_roll_initiative_does_not_spend_uncanny_metabolism_without_benefit(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"monk": 2}
    character.resources["srd.resource.focus_points"] = 2
    character.resources["srd.resource.uncanny_metabolism"] = 1
    character.hp_current = character.hp_max
    state.encounter.combatants["pc1"].hp_current = state.encounter.combatants["pc1"].hp_max
    audit = AuditLog()

    roll_initiative(state, audit)

    assert audit.events[-1].tool_result["uncanny_metabolism"] == []
    assert character.resources["srd.resource.focus_points"] == 2
    assert character.resources["srd.resource.uncanny_metabolism"] == 1


def test_roll_initiative_applies_monk_perfect_focus_when_uncanny_metabolism_unused(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"monk": 15}
    character.resources["srd.resource.focus_points"] = 3
    character.resources["srd.resource.uncanny_metabolism"] = 0
    character.hp_current = character.hp_max
    state.encounter.combatants["pc1"].hp_current = state.encounter.combatants["pc1"].hp_max
    audit = AuditLog()

    roll_initiative(state, audit)

    assert audit.events[-1].tool_result["uncanny_metabolism"] == []
    result = audit.events[-1].tool_result["perfect_focus"][0]
    assert result == {
        "combatant_id": "pc1",
        "character_id": "pc1",
        "source_action_id": "srd.perfect_focus",
        "resource": "srd.resource.focus_points",
        "resource_before": 3,
        "resource_after": 4,
        "requires_uncanny_metabolism_not_used": True,
    }
    assert character.resources["srd.resource.focus_points"] == 4


def test_roll_initiative_monk_perfect_focus_does_not_stack_with_uncanny_metabolism(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"monk": 15}
    character.resources["srd.resource.focus_points"] = 3
    character.resources["srd.resource.uncanny_metabolism"] = 1
    character.hp_current = character.hp_max
    state.encounter.combatants["pc1"].hp_current = state.encounter.combatants["pc1"].hp_max
    audit = AuditLog()

    roll_initiative(state, audit)

    uncanny_metabolism = audit.events[-1].tool_result["uncanny_metabolism"][0]
    assert uncanny_metabolism["source_action_id"] == "srd.uncanny_metabolism"
    assert uncanny_metabolism["focus_before"] == 3
    assert uncanny_metabolism["focus_after"] == 15
    assert audit.events[-1].tool_result["perfect_focus"] == []
    assert character.resources["srd.resource.focus_points"] == 15
    assert character.resources["srd.resource.uncanny_metabolism"] == 0


def test_roll_initiative_applies_barbarian_persistent_rage_once_per_long_rest(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"barbarian": 15}
    character.actions.extend(["srd.rage", "srd.persistent_rage"])
    character.resources["srd.resource.rage"] = 2
    character.resources["srd.resource.persistent_rage_initiative_restore"] = 1
    audit = AuditLog()

    roll_initiative(state, audit)

    result = audit.events[-1].tool_result["persistent_rage"][0]
    assert result == {
        "combatant_id": "pc1",
        "character_id": "pc1",
        "source_action_id": "srd.persistent_rage",
        "resource": "srd.resource.rage",
        "resource_before": 2,
        "resource_after": 5,
        "restore_resource": "srd.resource.persistent_rage_initiative_restore",
        "restore_resource_before": 1,
        "restore_resource_after": 0,
    }
    assert character.resources["srd.resource.rage"] == 5
    assert character.resources["srd.resource.persistent_rage_initiative_restore"] == 0

    character.resources["srd.resource.rage"] = 1
    roll_initiative(state, audit)

    assert audit.events[-1].tool_result["persistent_rage"] == []
    assert character.resources["srd.resource.rage"] == 1
    assert character.resources["srd.resource.persistent_rage_initiative_restore"] == 0


def test_roll_initiative_persistent_rage_does_not_spend_restore_when_rage_full(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"barbarian": 15}
    character.resources["srd.resource.rage"] = 5
    character.resources["srd.resource.persistent_rage_initiative_restore"] = 1
    audit = AuditLog()

    roll_initiative(state, audit)

    assert audit.events[-1].tool_result["persistent_rage"] == []
    assert character.resources["srd.resource.rage"] == 5
    assert character.resources["srd.resource.persistent_rage_initiative_restore"] == 1


def test_roll_initiative_applies_bard_superior_inspiration_until_two(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"bard": 18}
    character.abilities["cha"] = 16
    character.resources["srd.resource.bardic_inspiration"] = 0
    audit = AuditLog()

    roll_initiative(state, audit)

    result = audit.events[-1].tool_result["superior_inspiration"][0]
    assert result == {
        "combatant_id": "pc1",
        "character_id": "pc1",
        "source_action_id": "srd.superior_inspiration",
        "resource": "srd.resource.bardic_inspiration",
        "resource_before": 0,
        "resource_after": 2,
        "resource_max": 3,
        "minimum_after": 2,
    }
    assert character.resources["srd.resource.bardic_inspiration"] == 2


def test_roll_initiative_bard_superior_inspiration_respects_level_and_current_uses(
    make_state,
) -> None:
    low_state = make_state()
    assert low_state.encounter is not None
    low_character = low_state.characters["pc1"]
    low_character.class_levels = {"bard": 17}
    low_character.abilities["cha"] = 16
    low_character.resources["srd.resource.bardic_inspiration"] = 0
    low_audit = AuditLog()

    roll_initiative(low_state, low_audit)

    assert low_audit.events[-1].tool_result["superior_inspiration"] == []
    assert low_character.resources["srd.resource.bardic_inspiration"] == 0

    full_state = make_state()
    assert full_state.encounter is not None
    full_character = full_state.characters["pc1"]
    full_character.class_levels = {"bard": 18}
    full_character.abilities["cha"] = 16
    full_character.resources["srd.resource.bardic_inspiration"] = 2
    full_audit = AuditLog()

    roll_initiative(full_state, full_audit)

    assert full_audit.events[-1].tool_result["superior_inspiration"] == []
    assert full_character.resources["srd.resource.bardic_inspiration"] == 2

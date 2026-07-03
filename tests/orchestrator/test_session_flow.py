from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from dnd_llm.content.campaign_pack import CampaignPackLoader
from dnd_llm.content.runtime import apply_campaign_pack
from dnd_llm.core.compendium.loader import CompendiumLoader
from dnd_llm.core.models import Combatant
from dnd_llm.core.persistence import AuditLog
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

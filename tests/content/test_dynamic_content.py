from __future__ import annotations

from pathlib import Path

from dnd_llm.content.campaign_pack import CampaignPackLoader
from dnd_llm.content.character_gen import default_fighter
from dnd_llm.content.dynamic import dynamic_zones_for_state
from dnd_llm.content.runtime import (
    apply_campaign_pack,
    tactical_graph_for_state_zone,
    zone_definition_for_state,
)
from dnd_llm.core.compendium.loader import CompendiumLoader
from dnd_llm.core.models import GameState
from dnd_llm.core.persistence import AuditLog, load_game, save_game
from dnd_llm.core.tools import EngineTools
from dnd_llm.orchestrator.session import GameSession, SessionResult


def _session_state() -> tuple[GameState, AuditLog, GameSession]:
    character = default_fighter("pc1", "Penn")
    state = GameState(campaign_id="blank", rng_seed=20260629, characters={"pc1": character})
    pack = CampaignPackLoader().load("rules_data/campaigns/starter/pack.json")
    apply_campaign_pack(state, pack)
    audit = AuditLog()
    session = GameSession(state, CompendiumLoader("rules_data").load(), audit)
    return state, audit, session


def test_dynamic_zone_expansion_updates_runtime_graph_and_moves_actor(
    tmp_path: Path,
) -> None:
    state, audit, session = _session_state()
    pack = CampaignPackLoader().load("rules_data/campaigns/starter/pack.json")

    expanded = session.expand_dynamic_zone(
        parent_zone_id="start",
        theme="Moonlit smuggler quay",
        name="月光走私码头",
        idempotency_key="dynamic-zone-1",
    )

    assert isinstance(expanded, SessionResult)
    assert expanded.accepted is True
    zone_id = str(expanded.payload["zone_id"])
    assert zone_id in dynamic_zones_for_state(state)
    assert zone_id in state.world.zone_edges["start"]
    assert state.world.zone_edges[zone_id] == ["start"]
    assert any(event.tool_name == "orchestrator.content.expand_zone" for event in audit.events)

    zone = zone_definition_for_state(state, pack, zone_id)
    assert zone["name"] == "月光走私码头"
    graph = tactical_graph_for_state_zone(state, pack, zone_id)
    start_node = next(iter(graph.nodes))
    assert graph.reachable(start_node, 10_000) == set(graph.nodes)

    moved = EngineTools(state, CompendiumLoader("rules_data").load(), audit).move(
        "pc1",
        to_zone_id=zone_id,
        idempotency_key="move-to-dynamic-zone",
    )
    assert moved["success"] is True
    assert state.world.current_zone_id == zone_id

    save_game(tmp_path / "slot", state, audit)
    loaded_state, loaded_audit = load_game(tmp_path / "slot")
    assert loaded_state.to_dict() == state.to_dict()
    assert len(loaded_audit.events) == len(audit.events)
    assert tactical_graph_for_state_zone(loaded_state, pack, zone_id).to_dict() == graph.to_dict()


def test_dynamic_zone_expansion_is_deterministic_and_idempotent() -> None:
    first_state, _, first_session = _session_state()
    second_state, _, second_session = _session_state()

    first = first_session.expand_dynamic_zone(
        parent_zone_id="start",
        theme="Fungal market beneath the hill",
        idempotency_key="dynamic-zone-seed",
    )
    repeated = first_session.expand_dynamic_zone(
        parent_zone_id="start",
        theme="A different theme should be ignored by idempotency",
        idempotency_key="dynamic-zone-seed",
    )
    second = second_session.expand_dynamic_zone(
        parent_zone_id="start",
        theme="Fungal market beneath the hill",
        idempotency_key="dynamic-zone-seed",
    )

    assert isinstance(first, SessionResult)
    assert isinstance(second, SessionResult)
    assert repeated is first
    assert first.payload == second.payload
    assert first_state.world.flags["dynamic_zones"] == second_state.world.flags["dynamic_zones"]
    assert len(dynamic_zones_for_state(first_state)) == 1


def test_dynamic_zone_expansion_rejects_unknown_parent_and_audits() -> None:
    state, audit, session = _session_state()

    result = session.expand_dynamic_zone(
        parent_zone_id="missing",
        theme="Impossible branch",
        idempotency_key="dynamic-zone-bad-parent",
    )

    assert isinstance(result, SessionResult)
    assert result.accepted is False
    assert "unknown parent zone" in result.payload["reason"]
    assert dynamic_zones_for_state(state) == {}
    assert audit.events[-1].tool_name == "orchestrator.content.expand_zone"
    assert audit.events[-1].tool_result["accepted"] is False

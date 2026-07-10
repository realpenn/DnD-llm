from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from dnd_llm.content.campaign_pack import CampaignPackLoader, CampaignPackValidator
from dnd_llm.content.character_gen import default_fighter
from dnd_llm.content.runtime import (
    apply_campaign_pack,
    build_encounter_combatants,
    encounter_id_for_zone,
    tactical_graph_for_zone,
)
from dnd_llm.core.compendium.loader import CompendiumLoader
from dnd_llm.core.models import GameState
from dnd_llm.core.persistence import AuditLog, load_game, save_game
from dnd_llm.core.tools import EngineTools
from dnd_llm.dm.runtime import DMRuntime
from dnd_llm.orchestrator.session import GameSession, SessionResult


def test_local_exploration_event_combat_save_load_playtest(tmp_path: Path) -> None:
    state, audit_log, payload = _run_local_playtest(tmp_path / "slot")

    assert payload["move"]["success"] is True
    assert payload["event"]["success"] is True
    assert state.characters["pc1"].zone_id == "ruins"
    assert payload["attack"]["action_id"] == "srd.longsword_attack"
    assert payload["monster_turn"]["action_id"] == "srd.kobold_dagger"
    assert state.encounter is not None
    assert state.encounter.current_combatant_id == "pc1"
    assert audit_log.events


def test_local_playtest_replays_deterministically(tmp_path: Path) -> None:
    first_state, first_audit, first_payload = _run_local_playtest(tmp_path / "run-1")
    second_state, second_audit, second_payload = _run_local_playtest(tmp_path / "run-2")

    assert first_state.to_dict() == second_state.to_dict()
    assert first_payload == second_payload
    assert _without_timestamps(first_audit.to_dicts()) == _without_timestamps(
        second_audit.to_dicts()
    )


def test_local_party_playtest_reloads_in_fresh_process_and_continues_combat(
    tmp_path: Path,
) -> None:
    compendium = CompendiumLoader("rules_data").load()
    pack = CampaignPackLoader().load("rules_data/campaigns/starter/pack.json")
    pack_report = CampaignPackValidator(compendium=compendium).validate(pack)
    assert pack_report.ok, pack_report.errors

    party = {f"pc{index}": default_fighter(f"pc{index}", f"Penn {index}") for index in range(1, 5)}
    state = GameState(campaign_id="blank", rng_seed=20260629, characters=party)
    audit_log = AuditLog()
    apply_campaign_pack(state, pack)
    tools = EngineTools(state, compendium, audit_log)

    for character_id in party:
        moved = tools.move(
            character_id,
            to_zone_id="ruins",
            idempotency_key=f"party-playtest:move:{character_id}",
        )
        assert moved["success"] is True
    event = tools.trigger_event(
        "starter.loose_stones",
        actor_ids=list(party),
        targets=list(party),
    )
    assert event["success"] is True

    encounter_id = encounter_id_for_zone(pack, "ruins")
    assert encounter_id is not None
    session = GameSession(state, compendium, audit_log)
    started = session.start_combat(
        encounter_id=encounter_id,
        combatants=build_encounter_combatants(
            pack=pack,
            encounter_id=encounter_id,
            party=party,
            compendium=compendium,
            monster_start_node="front",
        ),
        tactical_graph=tactical_graph_for_zone(pack, "ruins"),
        idempotency_key="party-playtest:start-combat",
    )
    assert isinstance(started, SessionResult)
    assert started.accepted is True
    assert state.encounter is not None

    while state.encounter.current_combatant_id != "pc1":
        session.advance_turn(f"party-playtest:advance:{state.encounter.turn_index}")
    response = DMRuntime(session).handle_player_text(
        actor_id="pc1",
        text="DD 我用长剑攻击 Kobold Warrior",
        idempotency_key="party-playtest:attack",
    )
    assert response.accepted is True
    assert response.engine_payload["action_id"] == "srd.longsword_attack"
    assert state.encounter.current_combatant_id is not None
    while state.encounter.combatants[state.encounter.current_combatant_id].side != "monsters":
        session.advance_turn(f"party-playtest:advance-after-attack:{state.encounter.turn_index}")

    save_slot = tmp_path / "party-slot"
    save_game(save_slot, state, audit_log)
    repo_root = Path(__file__).parents[2]
    pythonpath = [str(repo_root / "src"), os.environ.get("PYTHONPATH", "")]
    child_code = """
import json
import sys
from pathlib import Path

from dnd_llm.core.compendium.loader import CompendiumLoader
from dnd_llm.core.persistence import load_game
from dnd_llm.orchestrator.session import GameSession

state, audit = load_game(Path(sys.argv[1]))
if state.encounter is None:
    raise SystemExit("loaded game has no encounter")
current = state.encounter.current_combatant_id
if current is None or state.encounter.combatants[current].side != "monsters":
    raise SystemExit("loaded game is not at a monster turn")
session = GameSession(state, CompendiumLoader("rules_data").load(), audit)
turn = session.run_current_monster_turn("party-playtest:fresh-process-monster-turn")
if not turn.accepted:
    raise SystemExit(f"monster turn rejected: {turn.payload}")
print(json.dumps({
    "character_ids": sorted(state.characters),
    "action_id": turn.payload["action_id"],
    "current_combatant_id": state.encounter.current_combatant_id,
}, sort_keys=True))
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(value for value in pythonpath if value)
    child = subprocess.run(
        [sys.executable, "-c", child_code, str(save_slot)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert child.returncode == 0, child.stderr
    child_payload = json.loads(child.stdout)
    assert child_payload["character_ids"] == ["pc1", "pc2", "pc3", "pc4"]
    assert child_payload["action_id"] in {"srd.kobold_dagger", "srd.dodge"}
    assert child_payload["current_combatant_id"] == "pc1"


def _run_local_playtest(
    save_slot: Path | None = None,
) -> tuple[GameState, AuditLog, dict[str, Any]]:
    compendium = CompendiumLoader("rules_data").load()
    pack = CampaignPackLoader().load("rules_data/campaigns/starter/pack.json")
    pack_report = CampaignPackValidator(compendium=compendium).validate(pack)
    assert pack_report.ok, pack_report.errors

    character = default_fighter("pc1", "Penn")
    state = GameState(campaign_id="blank", rng_seed=20260629, characters={"pc1": character})
    audit_log = AuditLog()
    apply_campaign_pack(state, pack)
    tools = EngineTools(state, compendium, audit_log)

    moved = tools.move("pc1", to_zone_id="ruins", idempotency_key="playtest:move")
    event = tools.trigger_event(
        "starter.loose_stones",
        actor_ids=["pc1"],
        targets=["pc1"],
    )

    assert moved["success"] is True
    assert event["success"] is True
    assert state.characters["pc1"].zone_id == "ruins"

    encounter_id = encounter_id_for_zone(pack, "ruins")
    assert encounter_id is not None
    session = GameSession(state, compendium, audit_log)
    started = session.start_combat(
        encounter_id=encounter_id,
        combatants=build_encounter_combatants(
            pack=pack,
            encounter_id=encounter_id,
            party=state.characters,
            compendium=compendium,
            monster_start_node="front",
        ),
        tactical_graph=tactical_graph_for_zone(pack, "ruins"),
        idempotency_key="playtest:start_combat",
    )
    assert isinstance(started, SessionResult)
    assert started.accepted is True
    assert state.encounter is not None

    while state.encounter.current_combatant_id != "pc1":
        session.advance_turn(f"playtest:advance:{state.encounter.turn_index}")
    dm = DMRuntime(session)
    response = dm.handle_player_text(
        actor_id="pc1",
        text="DD 我用长剑攻击 Kobold Warrior",
        idempotency_key="playtest:attack",
    )

    assert response.accepted is True
    assert response.engine_payload["action_id"] == "srd.longsword_attack"

    if save_slot is not None:
        save_game(save_slot, state, audit_log)
        loaded_state, loaded_audit = load_game(save_slot)

        assert loaded_state.to_dict() == state.to_dict()
        assert len(loaded_audit.events) == len(audit_log.events)
        state = loaded_state
        audit_log = loaded_audit
        session = GameSession(state, compendium, audit_log)

    assert state.encounter is not None
    current = state.encounter.current_combatant_id
    assert current is not None
    assert state.encounter.combatants[current].side == "monsters"
    loaded_roll_counter = state.roll_counter
    loaded_event_count = len(audit_log.events)

    monster_turn = session.run_current_monster_turn("playtest:loaded-monster-turn")

    assert isinstance(monster_turn, SessionResult)
    assert monster_turn.accepted is True
    assert monster_turn.payload["action_id"] == "srd.kobold_dagger"
    assert state.roll_counter > loaded_roll_counter
    assert len(audit_log.events) > loaded_event_count
    assert state.encounter.current_combatant_id == "pc1"

    return (
        state,
        audit_log,
        {
            "move": moved,
            "event": event,
            "attack": response.engine_payload,
            "monster_turn": monster_turn.payload,
        },
    )


def _without_timestamps(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scrubbed = []
    for event in events:
        payload = dict(event)
        payload["timestamp"] = "<timestamp>"
        scrubbed.append(payload)
    return scrubbed

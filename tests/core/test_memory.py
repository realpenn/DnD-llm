from __future__ import annotations

from pathlib import Path

from dnd_llm.core.compendium.loader import CompendiumLoader
from dnd_llm.core.memory import remember_fragment, retrieve_memory
from dnd_llm.core.persistence import AuditLog, load_game, save_game
from dnd_llm.orchestrator.session import GameSession, SessionResult


def test_memory_retrieval_ranks_relevant_public_fragments(make_state) -> None:
    state = make_state()
    windmill = remember_fragment(
        state,
        text="The miller hid the brass key under the old windmill stone.",
        tags=["windmill", "key"],
    )
    remember_fragment(
        state,
        text="The chapel bell was cracked during the winter festival.",
        tags=["chapel"],
    )

    results = retrieve_memory(state, query="Where is the windmill key?", limit=1)

    assert [result.fragment.id for result in results] == [windmill.id]
    assert results[0].score > 0


def test_memory_retrieval_filters_non_public_fragments(make_state) -> None:
    state = make_state()
    hidden = remember_fragment(
        state,
        text="Goblin chief hidden weakness: fire.",
        tags=["goblin"],
        visibility="gm",
    )

    public_results = retrieve_memory(state, query="goblin weakness fire")
    gm_results = retrieve_memory(
        state,
        query="goblin weakness fire",
        visible_to={"public", "gm"},
    )

    assert hidden.id not in [result.fragment.id for result in public_results]
    assert hidden.id in [result.fragment.id for result in gm_results]


def test_memory_round_trips_through_save_load(tmp_path: Path, make_state) -> None:
    state = make_state()
    remember_fragment(
        state,
        text="Lyra promised the river shrine a silver candle.",
        tags=["lyra", "shrine"],
    )
    audit = AuditLog()

    save_game(tmp_path / "slot", state, audit)
    loaded_state, loaded_audit = load_game(tmp_path / "slot")

    assert loaded_state.to_dict() == state.to_dict()
    assert loaded_audit.to_dicts() == []
    assert retrieve_memory(loaded_state, query="silver candle shrine")[0].fragment.text.startswith(
        "Lyra"
    )


def test_session_remember_is_audited_and_idempotent(make_state) -> None:
    state = make_state()
    audit = AuditLog()
    session = GameSession(state, CompendiumLoader("rules_data").load(), audit)

    first = session.remember(
        text="The broken obelisk points toward the moon gate.",
        tags=["obelisk", "moon"],
        idempotency_key="remember-1",
    )
    second = session.remember(
        text="A duplicate should not be written.",
        tags=["duplicate"],
        idempotency_key="remember-1",
    )

    assert isinstance(first, SessionResult)
    assert second is first
    assert len(state.memory_fragments) == 1
    assert audit.events[-1].tool_name == "orchestrator.memory.remember"
    assert audit.events[-1].tool_result["memory_id"] == state.memory_fragments[0].id
    context = session.context_for("pc1", query="moon gate obelisk")
    assert context.memory_fragments[0]["memory_id"] == state.memory_fragments[0].id

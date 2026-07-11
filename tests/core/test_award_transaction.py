from __future__ import annotations

import pytest

from dnd_llm.core.compendium.loader import CompendiumLoader
from dnd_llm.core.persistence import AuditLog
from dnd_llm.core.tools import EngineTools


def _tools(make_state):
    state = make_state()
    state.world.flags["campaign_rewards"] = {
        "test.party_reward": {
            "gold": 5,
            "experience": 10,
            "items": [{"item_id": "srd.potion_of_healing", "quantity": 1}],
        }
    }
    audit = AuditLog()
    return state, audit, EngineTools(state, CompendiumLoader("rules_data").load(), audit)


def test_award_rejects_missing_recipient_without_partial_side_effects(make_state) -> None:
    state, audit, tools = _tools(make_state)
    before = state.characters["pc1"].to_dict()
    event_counter_before = state.event_counter

    with pytest.raises(ValueError, match="unknown award recipient: missing"):
        tools.award(
            ["pc1", "missing"],
            "test.party_reward",
            idempotency_key="award-missing-recipient",
        )

    assert state.characters["pc1"].to_dict() == before
    assert state.event_counter == event_counter_before
    assert audit.events == []


def test_award_rolls_back_all_recipients_when_audit_commit_fails(
    make_state,
    monkeypatch,
) -> None:
    state, audit, tools = _tools(make_state)
    before = {actor_id: state.characters[actor_id].to_dict() for actor_id in ("pc1", "pc2")}
    event_counter_before = state.event_counter

    def fail_append(*args, **kwargs):
        raise OSError("injected audit failure")

    monkeypatch.setattr(audit, "append", fail_append)

    with pytest.raises(OSError, match="injected audit failure"):
        tools.award(
            ["pc1", "pc2"],
            "test.party_reward",
            idempotency_key="award-audit-failure",
        )

    assert {actor_id: state.characters[actor_id].to_dict() for actor_id in ("pc1", "pc2")} == before
    assert state.event_counter == event_counter_before
    assert audit.events == []

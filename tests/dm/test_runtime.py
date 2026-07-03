from __future__ import annotations

from typing import Any

from dnd_llm.core.compendium.loader import CompendiumLoader
from dnd_llm.core.persistence import AuditLog
from dnd_llm.dm.runtime import DMRuntime
from dnd_llm.orchestrator.session import GameSession


class FakeSummaryClient:
    def __init__(self, response: dict):
        self.response = response
        self.calls: list[dict] = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class FakeDMClient:
    def __init__(self, response: dict[str, Any]):
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self.calls.append({"messages": messages, "tools": tools or []})
        return self.response


def _tool_response(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {"name": name, "arguments": arguments},
                        }
                    ]
                }
            }
        ],
        "usage": {"prompt_tokens": 9, "completion_tokens": 5, "total_tokens": 14},
    }


def test_dm_runtime_maps_text_to_tool_result(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "goblin1"]
    state.encounter.turn_index = 0
    compendium = CompendiumLoader("rules_data").load()
    session = GameSession(state, compendium, AuditLog())
    runtime = DMRuntime(session)

    response = runtime.handle_player_text(
        actor_id="pc1",
        text="DD 我用短剑攻击 Goblin",
        idempotency_key="dm-attack",
    )

    assert response.accepted is True
    assert response.draft.candidate_action_id == "srd.shortsword_attack"
    assert "伤害" in response.narration or "行动完成" in response.narration
    assert response.engine_payload["action_id"] == "srd.shortsword_attack"


def test_dm_runtime_unconfigured_model_falls_back_to_heuristic(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "goblin1"]
    state.encounter.turn_index = 0
    compendium = CompendiumLoader("rules_data").load()
    session = GameSession(state, compendium, AuditLog())
    runtime = DMRuntime(
        session,
        client=FakeDMClient({"type": "unconfigured"}),
        model_id="fake-dm",
    )

    response = runtime.handle_player_text(
        actor_id="pc1",
        text="DD 我用短剑攻击 Goblin",
        idempotency_key="dm-unconfigured-fallback",
    )

    assert response.accepted is True
    assert response.draft.candidate_action_id == "srd.shortsword_attack"
    assert response.engine_payload["action_id"] == "srd.shortsword_attack"
    assert not any(event.tool_name == "dm.model_draft" for event in session.audit_log.events)


def test_dm_runtime_timeout_takeover_returns_model_draft(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "goblin1"]
    state.encounter.turn_index = 0
    compendium = CompendiumLoader("rules_data").load()
    session = GameSession(state, compendium, AuditLog())
    runtime = DMRuntime(
        session,
        client=FakeDMClient(
            _tool_response(
                "attack",
                {
                    "attacker_id": "pc1",
                    "target_id": "goblin1",
                    "action_id": "srd.shortsword_attack",
                },
            )
        ),
        model_id="fake-dm",
    )

    draft = runtime.timeout_takeover_draft("pc1", now=111, idempotency_key="timeout-ai")

    assert draft is not None
    assert draft.actor_id == "pc1"
    assert draft.candidate_action_id == "srd.shortsword_attack"
    assert draft.target_ids == ["goblin1"]
    assert state.encounter.combatants["goblin1"].hp_current == 7
    assert any(event.tool_name == "dm.timeout_model_draft" for event in session.audit_log.events)
    assert session.audit_log.model_usage_totals()["total_tokens"] == 14


def test_dm_runtime_monster_turn_returns_model_draft(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["goblin1", "pc1"]
    state.encounter.turn_index = 0
    compendium = CompendiumLoader("rules_data").load()
    session = GameSession(state, compendium, AuditLog())
    runtime = DMRuntime(
        session,
        client=FakeDMClient(
            _tool_response(
                "attack",
                {
                    "attacker_id": "goblin1",
                    "target_id": "pc1",
                    "action_id": "srd.kobold_dagger",
                },
            )
        ),
        model_id="fake-dm",
    )

    draft = runtime.monster_turn_draft("goblin1", now=7, idempotency_key="monster-ai")

    assert draft is not None
    assert draft.actor_id == "goblin1"
    assert draft.candidate_action_id == "srd.kobold_dagger"
    assert draft.target_ids == ["pc1"]
    assert state.encounter.combatants["pc1"].hp_current == 10
    assert any(event.tool_name == "dm.monster_model_draft" for event in session.audit_log.events)


def test_dm_runtime_monster_turn_prompt_includes_compact_affordances(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["goblin1", "pc1"]
    state.encounter.turn_index = 0
    leader = state.encounter.combatants["goblin1"]
    leader.name = "Bandit Captain"
    leader.actions = ["srd.bandit_captain_scimitar"]
    leader.position_node_id = "front"
    state.encounter.combatants["pc1"].position_node_id = "front"
    compendium = CompendiumLoader("rules_data").load()
    client = FakeDMClient(
        _tool_response(
            "attack",
            {
                "attacker_id": "goblin1",
                "target_id": "pc1",
                "action_id": "srd.bandit_captain_scimitar",
            },
        )
    )
    session = GameSession(state, compendium, AuditLog())
    runtime = DMRuntime(session, client=client, model_id="fake-dm")

    draft = runtime.monster_turn_draft("goblin1", now=7, idempotency_key="monster-ai")

    serialized_prompt = repr(client.calls[0]["messages"])
    assert draft is not None
    assert draft.candidate_action_id == "srd.bandit_captain_scimitar"
    assert "affordances" in serialized_prompt
    assert "srd.bandit_captain_scimitar" in serialized_prompt
    assert "candidate_target_ids" in serialized_prompt
    assert "automation" not in serialized_prompt


def test_dm_runtime_captures_accepted_public_memory(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "goblin1"]
    state.encounter.turn_index = 0
    compendium = CompendiumLoader("rules_data").load()
    session = GameSession(state, compendium, AuditLog())
    runtime = DMRuntime(session)

    response = runtime.handle_player_text(
        actor_id="pc1",
        text="DD 我用短剑攻击 Goblin",
        idempotency_key="dm-memory-capture",
    )

    assert response.accepted is True
    assert state.memory_fragments
    assert "玩家行动" in state.memory_fragments[0].text
    assert "短剑攻击" in state.memory_fragments[0].text
    assert any(
        event.tool_name == "orchestrator.memory.remember" for event in session.audit_log.events
    )
    context = session.context_for("pc1", query="短剑攻击 Goblin")
    assert context.memory_fragments[0]["memory_id"] == state.memory_fragments[0].id


def test_dm_runtime_retries_missing_target_once(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "goblin1"]
    state.encounter.turn_index = 0
    compendium = CompendiumLoader("rules_data").load()
    session = GameSession(state, compendium, AuditLog())
    runtime = DMRuntime(session, max_retries=1)

    response = runtime.handle_player_text(
        actor_id="pc1",
        text="DD 短剑",
        idempotency_key="dm-retry",
    )

    assert response.accepted is True
    assert response.retries in {0, 1}
    assert any(
        event.tool_name in {"dm.retry", "resolver.resolve"} for event in session.audit_log.events
    )


def test_dm_runtime_retry_audits_legal_options_and_degrades_after_default_limit(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "goblin1"]
    state.encounter.turn_index = 0
    state.encounter.action_budgets["pc1"] = {
        "action": 0,
        "bonus_action": 1,
        "reaction": 1,
        "movement": 30,
        "movement_used": 0,
        "free": 1,
    }
    compendium = CompendiumLoader("rules_data").load()
    session = GameSession(state, compendium, AuditLog())
    runtime = DMRuntime(session)

    response = runtime.handle_player_text(
        actor_id="pc1",
        text="DD 做点什么",
        idempotency_key="dm-retry-limit",
    )

    retry_events = [event for event in session.audit_log.events if event.tool_name == "dm.retry"]
    resolver_events = [
        event for event in session.audit_log.events if event.tool_name == "resolver.resolve"
    ]
    degrade_events = [
        event for event in session.audit_log.events if event.tool_name == "dm.degrade"
    ]
    assert response.accepted is False
    assert response.retries == 1
    assert len(retry_events) == 1
    assert len(resolver_events) == 2
    assert len(degrade_events) == 1
    assert retry_events[0].tool_args["error"]["reason"] == "no matching action"
    assert retry_events[0].tool_args["legal_options"][0]["action_id"] == ("srd.shortsword_attack")
    assert retry_events[0].tool_result["draft"]["candidate_action_id"] == ("srd.shortsword_attack")
    assert response.engine_payload["reason"] == "insufficient action economy"


def test_dm_runtime_degrades_after_illegal_out_of_turn_action(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["goblin1", "pc1"]
    state.encounter.turn_index = 0
    compendium = CompendiumLoader("rules_data").load()
    session = GameSession(state, compendium, AuditLog())
    runtime = DMRuntime(session, max_retries=1)

    response = runtime.handle_player_text(
        actor_id="pc1",
        text="DD 短剑攻击 Goblin",
        idempotency_key="dm-degrade",
    )

    assert response.accepted is False
    assert "不能执行" in response.narration
    assert any(event.tool_name == "dm.degrade" for event in session.audit_log.events)


def test_dm_runtime_updates_sanitized_rolling_summary_without_model(make_state) -> None:
    state = make_state()
    compendium = CompendiumLoader("rules_data").load()
    session = GameSession(state, compendium, AuditLog())
    runtime = DMRuntime(session, summary_max_chars=200)

    summary = runtime.summarize_scene(
        "Goblin 1 took 7 damage and has HP 3/10 after the public exchange.",
        idempotency_key="summary-fallback",
    )

    assert state.summary == summary
    assert "7" not in summary
    assert "3/10" not in summary
    assert "Goblin <num>" in summary
    assert "<num>/<num>" in summary
    assert session.context_for("pc1").summary == summary
    assert any(event.tool_name == "dm.summary.update" for event in session.audit_log.events)


def test_dm_runtime_summary_uses_model_and_idempotency_cache(make_state) -> None:
    state = make_state()
    compendium = CompendiumLoader("rules_data").load()
    session = GameSession(state, compendium, AuditLog())
    client = FakeSummaryClient(
        {
            "choices": [
                {"message": {"content": "The party returned to camp after 2 tense exchanges."}}
            ],
            "usage": {"prompt_tokens": 11, "completion_tokens": 4, "total_tokens": 15},
        }
    )
    runtime = DMRuntime(
        session,
        summary_client=client,
        summary_model_id="summary-model",
        summary_max_chars=200,
    )

    summary = runtime.summarize_scene("The party returned to camp.", idempotency_key="summary-ai")
    cached = runtime.summarize_scene("Different 99 note.", idempotency_key="summary-ai")

    assert summary == cached
    assert len(client.calls) == 1
    assert "2" not in summary
    assert "<num>" in summary
    event = next(
        event for event in session.audit_log.events if event.tool_name == "dm.summary.update"
    )
    assert event.model_id == "summary-model"
    assert event.prompt_version == "summary-v1"
    assert event.model_usage == {"prompt_tokens": 11, "completion_tokens": 4, "total_tokens": 15}
    assert session.audit_log.model_usage_totals()["total_tokens"] == 15


def test_dm_runtime_summary_rejects_model_invented_rewards(make_state) -> None:
    state = make_state()
    compendium = CompendiumLoader("rules_data").load()
    session = GameSession(state, compendium, AuditLog())
    client = FakeSummaryClient(
        {
            "choices": [{"message": {"content": "The party returned to camp and gained 10 gold."}}],
            "usage": {"prompt_tokens": 8, "completion_tokens": 7},
        }
    )
    runtime = DMRuntime(session, summary_client=client, summary_model_id="summary-model")

    summary = runtime.summarize_scene(
        "The party returned to camp.", idempotency_key="summary-guard"
    )

    assert summary == "The party returned to camp."
    assert "gold" not in summary.casefold()
    assert state.summary == summary

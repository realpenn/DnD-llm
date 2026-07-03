from __future__ import annotations

from typing import Any

from dnd_llm.content.character_gen import default_fighter
from dnd_llm.core.compendium.loader import CompendiumLoader
from dnd_llm.core.persistence import AuditLog
from dnd_llm.core.resolver import PlayerActionDraft
from dnd_llm.dm.runtime import DMRuntime
from dnd_llm.orchestrator.reactions import ReactionManager
from dnd_llm.orchestrator.session import GameSession
from dnd_llm.telegram_bot.characters import CharacterRegistry
from dnd_llm.telegram_bot.commands import CommandRouter
from dnd_llm.telegram_bot.runtime import IncomingMessage, RateLimiter, TelegramRuntime


class FakeClient:
    def __init__(self, response: dict[str, Any]):
        self.response = response

    def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return self.response


class ExplodingDMRuntime:
    def handle_player_text(self, **_: Any) -> object:
        raise AssertionError("commands must not call DM runtime")


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
        ]
    }


def _runtime(
    make_state,
    *,
    rate_limiter: RateLimiter | None = None,
    reaction_mode: str = "auto",
) -> TelegramRuntime:
    state = make_state()
    assert state.encounter is not None
    state.encounter.initiative_order = ["pc1", "goblin1"]
    state.encounter.turn_index = 0
    state.encounter.combatants["pc1"].position_node_id = "front"
    state.encounter.combatants["goblin1"].position_node_id = "front"
    compendium = CompendiumLoader("rules_data").load()
    session = GameSession(
        state,
        compendium,
        AuditLog(),
        reactions=ReactionManager(mode=reaction_mode),
    )
    registry = CharacterRegistry(
        characters_by_user={"u1": {"pc1": default_fighter("pc1", "Penn")}},
        active_by_user={"u1": "pc1"},
        campaign_members={"u1": "pc1"},
    )
    commands = CommandRouter(characters=registry)
    dm = DMRuntime(session)
    return TelegramRuntime(
        session=session,
        dm_runtime=dm,
        commands=commands,
        bot_username="dnd_bot",
        rate_limiter=rate_limiter,
        campaign_chat_id="group-1",
    )


def test_private_start_binds_chat_and_group_sheet_redirects(make_state) -> None:
    runtime = _runtime(make_state)

    start = runtime.handle_message(
        IncomingMessage(user_id="u1", chat_id="private-u1", text="/start", is_private=True),
        now=1,
    )
    sheet = runtime.handle_message(
        IncomingMessage(user_id="u1", chat_id="group-1", text="/sheet", is_private=False),
        now=2,
    )

    assert start[0].text == "私聊已激活。"
    assert len(sheet) == 2
    assert sheet[0].chat_id == "private-u1"
    assert sheet[0].private is True
    assert "Penn" in sheet[0].text
    assert sheet[1].metadata["private_redirect"] is True


def test_commands_do_not_call_dm_runtime(make_state) -> None:
    runtime = _runtime(make_state)
    runtime.dm_runtime = ExplodingDMRuntime()  # type: ignore[assignment]

    result = runtime.handle_message(
        IncomingMessage(user_id="u1", chat_id="group-1", text="/status"),
        now=1,
    )

    assert result[0].metadata["command"] == "/status"


def test_group_private_command_requires_start(make_state) -> None:
    runtime = _runtime(make_state)

    result = runtime.handle_message(
        IncomingMessage(user_id="u1", chat_id="group-1", text="/sheet", is_private=False),
        now=1,
    )

    assert result[0].metadata["private_required"] is True
    assert "需要先私聊" in result[0].text


def test_group_newchar_redirects_to_private_and_syncs_character(make_state) -> None:
    runtime = _runtime(make_state)
    runtime.commands.characters.characters_by_user.pop("u2", None)
    runtime.commands.characters.active_by_user.pop("u2", None)

    runtime.handle_message(
        IncomingMessage(user_id="u2", chat_id="private-u2", text="/start", is_private=True),
        now=1,
    )
    result = runtime.handle_message(
        IncomingMessage(user_id="u2", chat_id="group-1", text="/newchar Lyra"),
        now=2,
    )

    assert len(result) == 2
    assert result[0].chat_id == "private-u2"
    assert "已创建并选中角色" in result[0].text
    assert result[1].metadata["private_redirect"] is True
    character = runtime.commands.characters.active_character("u2")
    assert character is not None
    assert character.id in runtime.session.state.characters


def test_group_editchar_redirects_to_private_and_syncs_state_character(make_state) -> None:
    runtime = _runtime(make_state)
    runtime.handle_message(
        IncomingMessage(user_id="u1", chat_id="private-u1", text="/start", is_private=True),
        now=1,
    )

    result = runtime.handle_message(
        IncomingMessage(user_id="u1", chat_id="group-1", text="/editchar 职业 牧师"),
        now=2,
    )

    stored = runtime.commands.characters.active_character("u1")
    state_character = runtime.session.state.characters["pc1"]
    assert len(result) == 2
    assert result[0].chat_id == "private-u1"
    assert result[0].private is True
    assert "已更新角色" in result[0].text
    assert result[1].metadata["private_redirect"] is True
    assert stored is not None
    assert stored.class_levels == {"cleric": 1}
    assert state_character.class_levels == {"cleric": 1}


def test_duplicate_command_message_id_replays_cached_result_without_side_effects(
    make_state,
) -> None:
    runtime = _runtime(make_state, rate_limiter=RateLimiter(max_messages=1, window_seconds=10))
    runtime.commands.characters.characters_by_user.pop("u2", None)
    runtime.commands.characters.active_by_user.pop("u2", None)
    incoming = IncomingMessage(
        user_id="u2",
        chat_id="private-u2",
        text="/newchar Lyra",
        is_private=True,
        message_id="cmd-newchar-1",
    )

    first = runtime.handle_message(incoming, now=1)
    repeated = runtime.handle_message(incoming, now=2)

    assert repeated == first
    assert len(runtime.commands.characters.list_characters("u2")) == 1
    assert not repeated[0].metadata.get("rate_limited", False)


def test_duplicate_dd_message_id_replays_cached_result_without_side_effects(
    make_state,
) -> None:
    runtime = _runtime(make_state, rate_limiter=RateLimiter(max_messages=1, window_seconds=10))
    incoming = IncomingMessage(
        user_id="u1",
        chat_id="group-1",
        text="DD 我用短剑攻击 Goblin",
        message_id="dd-retry-1",
    )

    first = runtime.handle_message(incoming, now=1)
    event_counter_after_first = runtime.session.state.event_counter
    roll_counter_after_first = runtime.session.state.roll_counter
    repeated = runtime.handle_message(incoming, now=2)

    assert repeated == first
    assert repeated[0].metadata["accepted"] is True
    assert not repeated[0].metadata.get("rate_limited", False)
    assert runtime.session.state.event_counter == event_counter_after_first
    assert runtime.session.state.roll_counter == roll_counter_after_first


def test_dd_group_message_routes_to_dm_runtime(make_state) -> None:
    runtime = _runtime(make_state)

    result = runtime.handle_message(
        IncomingMessage(
            user_id="u1",
            chat_id="group-1",
            text="DD 我用短剑攻击 Goblin",
            message_id="m1",
        ),
        now=1,
    )

    assert result
    assert result[0].chat_id == "group-1"
    assert result[0].metadata["accepted"] is True
    assert result[0].metadata["actor_id"] == "pc1"


def test_group_dm_action_prompts_next_party_player(make_state) -> None:
    runtime = _runtime(make_state)
    assert runtime.session.state.encounter is not None
    runtime.session.state.encounter.initiative_order = ["pc1", "pc2", "goblin1"]
    runtime.session.state.encounter.turn_index = 0
    runtime.commands.characters.characters_by_user["u2"] = {"pc2": default_fighter("pc2", "Ally")}
    runtime.commands.characters.active_by_user["u2"] = "pc2"
    runtime.commands.characters.campaign_members["u2"] = "pc2"

    result = runtime.handle_message(
        IncomingMessage(
            user_id="u1",
            chat_id="group-1",
            text="DD 我用短剑攻击 Goblin",
            message_id="m-turn-prompt",
        ),
        now=1,
    )

    assert result[0].metadata["accepted"] is True
    assert result[1].metadata["turn_prompt"] is True
    assert result[1].metadata["combatant_id"] == "pc2"
    assert result[1].text == "@u2，轮到你行动。"


def test_gm_forceturn_command_prompts_next_party_player(make_state) -> None:
    runtime = _runtime(make_state)
    assert runtime.session.state.encounter is not None
    runtime.session.state.encounter.initiative_order = ["goblin1", "pc2"]
    runtime.session.state.encounter.turn_index = 0
    runtime.commands.gm_user_ids.add("gm")
    runtime.commands.characters.characters_by_user["u2"] = {"pc2": default_fighter("pc2", "Ally")}
    runtime.commands.characters.active_by_user["u2"] = "pc2"
    runtime.commands.characters.campaign_members["u2"] = "pc2"

    result = runtime.handle_message(
        IncomingMessage(
            user_id="gm",
            chat_id="group-1",
            text="/forceturn",
            message_id="m-forceturn-prompt",
        ),
        now=1,
    )

    assert result[0].metadata["command"] == "/forceturn"
    assert result[1].metadata["turn_prompt"] is True
    assert result[1].metadata["combatant_id"] == "pc2"
    assert result[1].text == "@u2，轮到你行动。"


def test_dm_action_syncs_character_growth_back_to_registry(make_state) -> None:
    runtime = _runtime(make_state)
    runtime.dm_runtime = DMRuntime(
        runtime.session,
        client=FakeClient(
            _tool_response(
                "award",
                {
                    "actor_ids": ["pc1"],
                    "reward_id": "gold:5",
                },
            )
        ),
        model_id="fake-dm",
    )

    result = runtime.handle_message(
        IncomingMessage(
            user_id="u1",
            chat_id="group-1",
            text="DD 搜刮钱袋",
            message_id="m-award",
        ),
        now=1,
    )

    stored = runtime.commands.characters.campaign_character_for_user("u1")
    assert result[0].metadata["accepted"] is True
    assert runtime.session.state.characters["pc1"].gold == 5
    assert stored is not None
    assert stored.gold == 5


def test_dm_action_does_not_clobber_existing_state_character_before_sync(make_state) -> None:
    runtime = _runtime(make_state)
    stored_before = runtime.commands.characters.campaign_character_for_user("u1")
    assert stored_before is not None
    stored_before.gold = 0
    runtime.session.state.characters["pc1"].gold = 7
    runtime.dm_runtime = DMRuntime(
        runtime.session,
        client=FakeClient(
            _tool_response(
                "roll_check",
                {
                    "actor_id": "pc1",
                    "ability": "str",
                    "difficulty_tier": "easy",
                    "dc_ref": None,
                    "advantage": None,
                },
            )
        ),
        model_id="fake-dm",
    )

    result = runtime.handle_message(
        IncomingMessage(
            user_id="u1",
            chat_id="group-1",
            text="DD 我检查旧钱袋",
            message_id="m-roll-check-sync",
        ),
        now=1,
    )

    stored = runtime.commands.characters.campaign_character_for_user("u1")
    assert result[0].metadata["accepted"] is True
    assert runtime.session.state.characters["pc1"].gold == 7
    assert stored is not None
    assert stored.gold == 7


def test_group_dd_requires_join_even_with_active_character(make_state) -> None:
    runtime = _runtime(make_state)
    runtime.commands.characters.campaign_members.clear()

    result = runtime.handle_message(
        IncomingMessage(
            user_id="u1",
            chat_id="group-1",
            text="DD 我用短剑攻击 Goblin",
            message_id="m-unjoined",
        ),
        now=1,
    )

    assert result[0].metadata["missing_character"] is True
    assert "先私聊 /newchar" in result[0].text


def test_spectator_group_dd_is_read_only(make_state) -> None:
    runtime = _runtime(make_state)
    runtime.commands.characters.campaign_members.clear()
    runtime.commands.characters.spectate_campaign("u1")

    result = runtime.handle_message(
        IncomingMessage(
            user_id="u1",
            chat_id="group-1",
            text="DD 我用短剑攻击 Goblin",
            message_id="m-spectator",
        ),
        now=1,
    )

    assert result[0].metadata["spectator_blocked_action"] is True
    assert "观战模式" in result[0].text
    assert "accepted" not in result[0].metadata


def test_join_command_clears_spectator_mode(make_state) -> None:
    runtime = _runtime(make_state)
    runtime.commands.characters.campaign_members.clear()
    runtime.commands.characters.spectate_campaign("u1")

    result = runtime.handle_message(
        IncomingMessage(user_id="u1", chat_id="group-1", text="/join"),
        now=1,
    )

    assert "已加入当前战役" in result[0].text
    assert not runtime.commands.characters.is_spectator("u1")
    assert runtime.commands.characters.campaign_character_for_user("u1") is not None


def test_mention_message_routes_to_dm_runtime(make_state) -> None:
    runtime = _runtime(make_state)

    result = runtime.handle_message(
        IncomingMessage(
            user_id="u1",
            chat_id="group-1",
            text="@dnd_bot 我用短剑攻击 Goblin",
            message_id="m2",
        ),
        now=1,
    )

    assert result[0].metadata["source"] == "mention"


def test_join_command_syncs_active_character_into_game_state(make_state) -> None:
    runtime = _runtime(make_state)
    runtime.commands.characters.campaign_members.clear()

    result = runtime.handle_message(
        IncomingMessage(user_id="u1", chat_id="group-1", text="/join"),
        now=1,
    )

    assert "已加入当前战役" in result[0].text
    assert "pc1" in runtime.session.state.characters


def test_react_command_confirms_pending_reaction_window(make_state) -> None:
    runtime = _runtime(make_state, reaction_mode="interactive")
    state = runtime.session.state
    assert state.encounter is not None
    state.encounter.initiative_order = ["goblin1", "pc1"]
    state.encounter.turn_index = 0
    state.encounter.combatants["goblin1"].position_node_id = "front"
    state.encounter.combatants["goblin1"].speed_ft = 60
    state.encounter.combatants["pc2"].position_node_id = "back"
    opened = runtime.session.submit_player_action(
        PlayerActionDraft(
            actor_id="goblin1",
            verb="移动",
            candidate_action_id="srd.move",
            params={"to_position_node_id": "back"},
        ),
        "telegram-open-reaction",
    )
    reaction_id = opened.payload["reaction_windows"][0]["reaction_id"]
    now = opened.payload["reaction_windows"][0]["opened_at"] + 1

    result = runtime.handle_message(
        IncomingMessage(
            user_id="u1",
            chat_id="private-u1",
            text=f"/react {reaction_id} yes",
            is_private=True,
            message_id="react-1",
        ),
        now=now,
    )

    assert result[0].text == "反应已确认。"
    assert result[0].metadata["accepted"] is True
    assert result[1].chat_id == "group-1"
    assert result[1].metadata["turn_prompt"] is True
    assert result[1].metadata["combatant_id"] == "pc1"
    assert state.encounter.pending_reactions == {}
    assert state.encounter.action_budgets["pc1"]["reaction"] == 0


def test_spectator_cannot_confirm_reaction_window(make_state) -> None:
    runtime = _runtime(make_state, reaction_mode="interactive")
    runtime.commands.characters.campaign_members.clear()
    runtime.commands.characters.spectate_campaign("u1")
    state = runtime.session.state
    assert state.encounter is not None
    state.encounter.initiative_order = ["goblin1", "pc1"]
    state.encounter.turn_index = 0
    state.encounter.combatants["goblin1"].position_node_id = "front"
    state.encounter.combatants["goblin1"].speed_ft = 60
    state.encounter.combatants["pc2"].position_node_id = "back"
    opened = runtime.session.submit_player_action(
        PlayerActionDraft(
            actor_id="goblin1",
            verb="移动",
            candidate_action_id="srd.move",
            params={"to_position_node_id": "back"},
        ),
        "telegram-open-spectator-reaction",
    )
    reaction_id = opened.payload["reaction_windows"][0]["reaction_id"]

    result = runtime.handle_message(
        IncomingMessage(
            user_id="u1",
            chat_id="private-u1",
            text=f"/react {reaction_id} yes",
            is_private=True,
            message_id="react-spectator",
        ),
        now=opened.payload["reaction_windows"][0]["opened_at"] + 1,
    )

    assert result[0].metadata["spectator_blocked_action"] is True
    assert state.encounter.pending_reactions != {}
    assert state.encounter.action_budgets["pc1"]["reaction"] == 1


def test_reaction_prompt_prefers_private_chat(make_state) -> None:
    runtime = _runtime(make_state)
    runtime.handle_message(
        IncomingMessage(user_id="u1", chat_id="private-u1", text="/start", is_private=True),
        now=1,
    )

    messages = runtime._reaction_prompt_messages(
        group_chat_id="group-1",
        reaction_windows=[
            {
                "reaction_id": "reaction-1",
                "actor_id": "pc1",
                "prompt": "Penn 可以触发借机攻击。",
            }
        ],
    )

    assert messages[0].chat_id == "private-u1"
    assert messages[0].private is True
    assert "/react reaction-1 yes|no" in messages[0].text


def test_reaction_prompt_without_private_chat_requires_start_without_leaking_detail(
    make_state,
) -> None:
    runtime = _runtime(make_state)

    messages = runtime._reaction_prompt_messages(
        group_chat_id="group-1",
        reaction_windows=[
            {
                "reaction_id": "reaction-secret",
                "actor_id": "pc1",
                "prompt": "Penn 可以触发借机攻击。",
            }
        ],
    )

    assert messages[0].chat_id == "group-1"
    assert messages[0].private is False
    assert messages[0].metadata["private_required"] is True
    assert "需要先私聊" in messages[0].text
    assert "借机攻击" not in messages[0].text
    assert "reaction-secret" not in messages[0].text


def test_rate_limiter_rejects_burst(make_state) -> None:
    runtime = _runtime(make_state, rate_limiter=RateLimiter(max_messages=1, window_seconds=10))

    first = runtime.handle_message(
        IncomingMessage(user_id="u1", chat_id="group-1", text="/status"),
        now=1,
    )
    second = runtime.handle_message(
        IncomingMessage(user_id="u1", chat_id="group-1", text="/status"),
        now=2,
    )

    assert first[0].metadata["command"] == "/status"
    assert second[0].metadata["rate_limited"] is True

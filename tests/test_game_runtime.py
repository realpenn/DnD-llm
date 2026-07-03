from __future__ import annotations

import json
from pathlib import Path

from dnd_llm.config import Settings
from dnd_llm.content.campaign_gen import starter_campaign_pack
from dnd_llm.runtime import GameRuntime, MultiCampaignRuntime
from dnd_llm.telegram_bot.runtime import IncomingMessage


def _settings(tmp_path: Path, *, gm_user_ids: tuple[str, ...] = ("gm",)) -> Settings:
    return Settings(
        rules_data_dir="rules_data",
        save_dir=str(tmp_path / "saves"),
        gm_user_ids=gm_user_ids,
        rng_seed=12345,
    )


def test_game_runtime_builds_starter_campaign(tmp_path: Path) -> None:
    runtime = GameRuntime.build(_settings(tmp_path))

    assert runtime.state.campaign_id == "starter"
    assert runtime.state.world.current_zone_id == "start"
    assert "starter.loose_stones" in runtime.compendium.events
    assert runtime.status().campaign_id == "starter"
    assert runtime.session.reactions.interactive is True


def test_game_runtime_can_keep_phase1_auto_reaction_mode_configured(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    runtime = GameRuntime.build(
        Settings(
            rules_data_dir=settings.rules_data_dir,
            save_dir=settings.save_dir,
            gm_user_ids=settings.gm_user_ids,
            rng_seed=settings.rng_seed,
            reaction_mode="auto",
        )
    )

    assert runtime.session.reactions.interactive is False


def test_game_runtime_wires_separate_dm_and_summary_models(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    runtime = GameRuntime.build(
        Settings(
            rules_data_dir=settings.rules_data_dir,
            save_dir=settings.save_dir,
            gm_user_ids=settings.gm_user_ids,
            rng_seed=settings.rng_seed,
            dm_model="dm-model",
            summary_model="summary-model",
        )
    )

    assert runtime.dm_runtime.model_id == "dm-model"
    assert runtime.dm_runtime.summary_model_id == "summary-model"
    assert getattr(runtime.dm_runtime.client, "model") == "dm-model"
    assert getattr(runtime.dm_runtime.summary_client, "model") == "summary-model"


def test_status_renders_combatants_with_fuzzy_hp(tmp_path: Path, make_state) -> None:
    runtime = GameRuntime.build(_settings(tmp_path))
    state = make_state()
    runtime.state.encounter = state.encounter

    text = runtime.status().render()

    assert "参战者" in text
    assert "Goblin" in text
    assert "Healthy" in text
    assert "7/7" not in text


def test_status_respects_exact_hp_display_strategy_without_mutating_state(
    tmp_path: Path,
    make_state,
) -> None:
    runtime = GameRuntime.build(_settings(tmp_path))
    state = make_state()
    runtime.state.encounter = state.encounter
    runtime.state.config.hp_display_strategy = "exact"
    assert runtime.state.encounter is not None
    before = runtime.state.encounter.combatants["goblin1"].hp_current

    text = runtime.status().render()

    assert "Goblin" in text
    assert "7/7" in text
    assert "Healthy" not in text
    assert runtime.state.encounter.combatants["goblin1"].hp_current == before


def test_group_status_filters_monster_details_without_mutating_state(
    tmp_path: Path,
    make_state,
) -> None:
    runtime = GameRuntime.build(_settings(tmp_path))
    state = make_state()
    runtime.state.encounter = state.encounter
    assert runtime.state.encounter is not None
    goblin = runtime.state.encounter.combatants["goblin1"]
    goblin.hp_current = 3
    goblin_hp_before = goblin.hp_current
    goblin_ac_before = goblin.armor_class

    result = runtime.telegram_runtime.handle_message(
        IncomingMessage(user_id="player", chat_id="group", text="/status"),
        now=1,
    )

    text = result[0].text
    assert result[0].chat_id == "group"
    assert result[0].private is False
    assert result[0].metadata["command"] == "/status"
    assert "Goblin" in text
    assert "Bloodied" in text
    assert "3/7" not in text
    assert "AC" not in text
    assert "armor_class" not in text
    assert goblin.hp_current == goblin_hp_before
    assert goblin.armor_class == goblin_ac_before


def test_status_renders_model_usage_totals(tmp_path: Path) -> None:
    runtime = GameRuntime.build(_settings(tmp_path))
    runtime.audit_log.append(
        runtime.state,
        idempotency_key="model:usage",
        tool_name="dm.model_draft",
        tool_result={"draft": {}},
        model_id="fake-dm",
        prompt_version="test-v1",
        model_usage={"prompt_tokens": 12, "completion_tokens": 7, "total_tokens": 19},
    )

    text = runtime.status().render()

    assert "模型用量" in text
    assert "prompt=12" in text
    assert "completion=7" in text
    assert "total=19" in text


def test_status_renders_model_cost_when_pricing_is_configured(tmp_path: Path) -> None:
    base = _settings(tmp_path)
    runtime = GameRuntime.build(
        Settings(
            rules_data_dir=base.rules_data_dir,
            save_dir=base.save_dir,
            gm_user_ids=base.gm_user_ids,
            rng_seed=base.rng_seed,
            model_input_cost_per_million=2.0,
            model_output_cost_per_million=8.0,
            model_cost_budget=0.01,
        )
    )
    runtime.audit_log.append(
        runtime.state,
        idempotency_key="model:cost",
        tool_name="dm.model_draft",
        tool_result={"draft": {}},
        model_id="fake-dm",
        prompt_version="test-v1",
        model_usage={"prompt_tokens": 1000, "completion_tokens": 1000, "total_tokens": 2000},
    )

    text = runtime.status().render()

    assert "模型成本" in text
    assert "USD 0.010000" in text
    assert "预算 100.0%" in text
    assert "已超出" in text


def test_gm_cost_command_renders_model_cost_report(tmp_path: Path) -> None:
    base = _settings(tmp_path)
    runtime = GameRuntime.build(
        Settings(
            rules_data_dir=base.rules_data_dir,
            save_dir=base.save_dir,
            gm_user_ids=base.gm_user_ids,
            rng_seed=base.rng_seed,
            model_input_cost_per_million=1.0,
            model_output_cost_per_million=3.0,
            model_cost_budget=0.01,
        )
    )
    runtime.audit_log.append(
        runtime.state,
        idempotency_key="model:cost-command",
        tool_name="dm.model_draft",
        tool_result={"draft": {}},
        model_id="fake-dm",
        prompt_version="test-v1",
        model_usage={"prompt_tokens": 2000, "completion_tokens": 1000, "total_tokens": 3000},
    )

    result = runtime.telegram_runtime.handle_message(
        IncomingMessage(user_id="gm", chat_id="group", text="/cost"),
        now=1,
    )

    assert "成本监控" in result[0].text
    assert "USD 0.005000" in result[0].text
    assert "预算：USD 0.010000（50.0%，未超出）" in result[0].text
    assert "fake-dm" in result[0].text
    assert result[0].metadata["command"] == "/cost"


def test_cost_command_is_gm_only(tmp_path: Path) -> None:
    runtime = GameRuntime.build(_settings(tmp_path))

    result = runtime.telegram_runtime.handle_message(
        IncomingMessage(user_id="player", chat_id="group", text="/cost"),
        now=1,
    )

    assert result[0].text == "该指令仅 GM 可用。"


def test_game_runtime_registers_embedded_campaign_pack_events(tmp_path: Path) -> None:
    pack = starter_campaign_pack()
    pack_path = tmp_path / "generated_pack.json"
    pack_path.write_text(json.dumps(pack.to_dict(), ensure_ascii=False), encoding="utf-8")

    runtime = GameRuntime.build(
        Settings(
            rules_data_dir="rules_data",
            campaign_pack_path=str(pack_path),
            save_dir=str(tmp_path / "saves"),
            rng_seed=12345,
        )
    )

    assert runtime.state.campaign_id == "starter_generated"
    assert "starter.generated_loose_stones" in runtime.compendium.events


def test_gm_save_load_and_saves_commands_round_trip_state(tmp_path: Path) -> None:
    runtime = GameRuntime.build(_settings(tmp_path))
    runtime.state.world.current_zone_id = "ruins"

    saved = runtime.telegram_runtime.handle_message(
        IncomingMessage(user_id="gm", chat_id="group", text="/save slot1"),
        now=1,
    )
    runtime.state.world.current_zone_id = "vault"
    saves = runtime.telegram_runtime.handle_message(
        IncomingMessage(user_id="gm", chat_id="group", text="/saves"),
        now=2,
    )
    loaded = runtime.telegram_runtime.handle_message(
        IncomingMessage(user_id="gm", chat_id="group", text="/load slot1"),
        now=3,
    )

    assert "已保存" in saved[0].text
    assert "slot1" in saves[0].text
    assert "已读取" in loaded[0].text
    assert runtime.state.world.current_zone_id == "ruins"


def test_gm_commands_reject_non_gm_through_runtime(tmp_path: Path) -> None:
    runtime = GameRuntime.build(_settings(tmp_path))

    result = runtime.telegram_runtime.handle_message(
        IncomingMessage(user_id="player", chat_id="group", text="/save slot1"),
        now=1,
    )

    assert result[0].text == "该指令仅 GM 可用。"


def test_gm_kick_command_removes_campaign_member(tmp_path: Path) -> None:
    runtime = GameRuntime.build(_settings(tmp_path))
    character = runtime.command_router.characters.create_default("u1", "Penn")
    runtime.command_router.characters.join_campaign("u1")

    kicked = runtime.telegram_runtime.handle_message(
        IncomingMessage(user_id="gm", chat_id="group", text="/kick u1"),
        now=1,
    )
    repeated = runtime.telegram_runtime.handle_message(
        IncomingMessage(user_id="gm", chat_id="group", text="/kick u1"),
        now=2,
    )

    assert character.id not in runtime.command_router.characters.campaign_members.values()
    assert kicked[0].text == "已移出战役。"
    assert repeated[0].text == "该用户未加入战役。"


def test_roll_command_uses_core_roll_service_and_audits(tmp_path: Path) -> None:
    runtime = GameRuntime.build(_settings(tmp_path))

    result = runtime.telegram_runtime.handle_message(
        IncomingMessage(user_id="player", chat_id="group", text="/roll 1d20+2"),
        now=1,
    )
    invalid = runtime.telegram_runtime.handle_message(
        IncomingMessage(user_id="player", chat_id="group", text="/roll 1d20*2"),
        now=2,
    )

    assert result[0].text.startswith("掷骰 1d20+2：")
    assert runtime.state.roll_counter == 1
    assert any(event.tool_name == "telegram.roll" for event in runtime.audit_log.events)
    assert invalid[0].text == "骰子表达式不合法。"


def test_roll_command_repeated_telegram_message_is_idempotent(tmp_path: Path) -> None:
    runtime = GameRuntime.build(_settings(tmp_path))
    incoming = IncomingMessage(
        user_id="player",
        chat_id="group",
        text="/roll 1d20+2",
        message_id="roll-retry-1",
    )

    first = runtime.telegram_runtime.handle_message(incoming, now=1)
    repeated = runtime.telegram_runtime.handle_message(incoming, now=2)

    assert repeated == first
    assert runtime.state.roll_counter == 1
    assert [event.tool_name for event in runtime.audit_log.events].count("telegram.roll") == 1


def test_multi_campaign_runtime_isolates_group_state_and_saves(tmp_path: Path) -> None:
    runtime = MultiCampaignRuntime.build(_settings(tmp_path))

    group_a_roll = runtime.handle_message(
        IncomingMessage(user_id="gm", chat_id="group-a", text="/roll 1d20"),
        now=1,
    )
    group_b_roll = runtime.handle_message(
        IncomingMessage(user_id="gm", chat_id="group-b", text="/roll 1d20"),
        now=2,
    )
    group_a_save = runtime.handle_message(
        IncomingMessage(user_id="gm", chat_id="group-a", text="/save alpha"),
        now=3,
    )
    group_b_save = runtime.handle_message(
        IncomingMessage(user_id="gm", chat_id="group-b", text="/save beta"),
        now=4,
    )

    group_a = runtime.runtime_for_group("group-a")
    group_b = runtime.runtime_for_group("group-b")
    assert group_a_roll[0].text.startswith("掷骰 1d20")
    assert group_b_roll[0].text.startswith("掷骰 1d20")
    assert group_a.state.campaign_id != group_b.state.campaign_id
    assert group_a.state.roll_counter == 1
    assert group_b.state.roll_counter == 1
    assert "alpha" in group_a_save[0].text
    assert "beta" in group_b_save[0].text
    assert (tmp_path / "saves" / group_a.state.campaign_id / "alpha").is_dir()
    assert (tmp_path / "saves" / group_b.state.campaign_id / "beta").is_dir()


def test_multi_campaign_runtime_keeps_group_character_registries_separate(
    tmp_path: Path,
) -> None:
    runtime = MultiCampaignRuntime.build(_settings(tmp_path))

    started = runtime.handle_message(
        IncomingMessage(user_id="u1", chat_id="private-u1", text="/start", is_private=True),
        now=1,
    )
    first = runtime.handle_message(
        IncomingMessage(user_id="u1", chat_id="group-a", text="/newchar Aria"),
        now=2,
    )
    second = runtime.handle_message(
        IncomingMessage(user_id="u1", chat_id="group-b", text="/newchar Bryn"),
        now=3,
    )
    sheet = runtime.handle_message(
        IncomingMessage(user_id="u1", chat_id="private-u1", text="/sheet", is_private=True),
        now=4,
    )

    group_a = runtime.runtime_for_group("group-a")
    group_b = runtime.runtime_for_group("group-b")
    assert started[0].text == "私聊已激活。"
    assert first[0].chat_id == "private-u1"
    assert second[0].chat_id == "private-u1"
    assert group_a.command_router.characters.active_character("u1").name == "Aria"
    assert group_b.command_router.characters.active_character("u1").name == "Bryn"
    assert "Bryn" in sheet[0].text
    assert "Aria" not in sheet[0].text


def test_newcampaign_resets_state_and_forceturn_reports_failure_without_encounter(
    tmp_path: Path,
) -> None:
    runtime = GameRuntime.build(_settings(tmp_path))
    runtime.state.world.current_zone_id = "vault"

    new_campaign = runtime.telegram_runtime.handle_message(
        IncomingMessage(user_id="gm", chat_id="group", text="/newcampaign"),
        now=1,
    )
    force_turn = runtime.telegram_runtime.handle_message(
        IncomingMessage(user_id="gm", chat_id="group", text="/forceturn"),
        now=2,
    )

    assert "已创建新战役" in new_campaign[0].text
    assert runtime.state.world.current_zone_id == "start"
    assert force_turn[0].text == "当前无法推进回合。"

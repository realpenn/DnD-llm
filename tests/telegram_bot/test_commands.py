from __future__ import annotations

from dnd_llm.content.character_gen import default_fighter
from dnd_llm.telegram_bot.commands import CommandRouter
from dnd_llm.telegram_bot.gateway import PlayerIntent


def intent(text: str, *, user_id: str = "u1") -> PlayerIntent:
    return PlayerIntent(user_id=user_id, chat_id="c1", text=text, source="command", is_command=True)


def test_character_commands_create_select_join_and_leave() -> None:
    router = CommandRouter()

    created = router.dispatch(intent("/newchar Penn"))
    listed = router.dispatch(intent("/mychars"))
    sheet = router.dispatch(intent("/sheet"))
    joined = router.dispatch(intent("/join"))
    left = router.dispatch(intent("/leave"))

    assert "已创建并选中角色" in created
    assert "Penn" in listed
    assert "HP" in sheet
    assert "已加入当前战役" in joined
    assert left == "已离开当前战役。"


def test_editchar_updates_active_character_with_valid_srd_choices() -> None:
    router = CommandRouter()
    router.dispatch(intent("/newchar Penn"))

    edited = router.dispatch(
        intent("/editchar 职业 牧师 力量 12 敏捷 14 体质 13 智力 10 感知 15 魅力 8")
    )
    sheet = router.dispatch(intent("/sheet"))
    character = router.characters.active_character("u1")

    assert character is not None
    assert "已更新角色" in edited
    assert character.class_levels == {"cleric": 1}
    assert character.abilities["wis"] == 15
    assert "职业：cleric1" in sheet


def test_editchar_rejects_invalid_character_request() -> None:
    router = CommandRouter()
    router.dispatch(intent("/newchar Penn"))

    edited = router.dispatch(intent("/editchar 职业 超级英雄 力量 18 敏捷 18"))
    character = router.characters.active_character("u1")

    assert character is not None
    assert edited.startswith("角色修改被拒绝")
    assert character.class_levels == {"fighter": 1}


def test_gm_commands_reject_non_gm() -> None:
    router = CommandRouter(gm_user_ids={"gm"})

    assert router.dispatch(intent("/save")) == "该指令仅 GM 可用。"


def test_help_lists_player_and_gm_commands() -> None:
    router = CommandRouter()

    text = router.dispatch(intent("/help"))

    assert "/newchar" in text
    assert "/editchar" in text
    assert "/spectate" in text
    assert "/forceturn" in text


def test_sheet_lists_feats() -> None:
    router = CommandRouter()
    router.characters.characters_by_user["u1"] = {"pc1": default_fighter("pc1", "Penn")}
    router.characters.active_by_user["u1"] = "pc1"
    router.characters.characters_by_user["u1"]["pc1"].feats = ["tough"]
    router.characters.characters_by_user["u1"]["pc1"].skill_proficiencies = ["perception"]
    router.characters.characters_by_user["u1"]["pc1"].tool_proficiencies = ["thieves_tools"]

    text = router.dispatch(intent("/sheet"))

    assert "专长：tough" in text
    assert "技能熟练：perception" in text
    assert "工具熟练：thieves_tools" in text


def test_spectator_commands_register_and_clear_read_only_mode() -> None:
    router = CommandRouter()

    spectating = router.dispatch(intent("/spectate"))
    duplicate_leave = router.dispatch(intent("/unspectate"))

    assert "已进入观战模式" in spectating
    assert duplicate_leave == "已退出观战模式。"
    assert not router.characters.is_spectator("u1")


def test_join_clears_spectator_mode() -> None:
    router = CommandRouter()
    router.characters.characters_by_user["u1"] = {"pc1": default_fighter("pc1", "Penn")}
    router.characters.active_by_user["u1"] = "pc1"

    router.dispatch(intent("/spectate"))
    joined = router.dispatch(intent("/join"))

    assert "已加入当前战役" in joined
    assert not router.characters.is_spectator("u1")
    assert router.characters.campaign_character_for_user("u1") is not None


def test_joined_player_cannot_enter_spectator_mode() -> None:
    router = CommandRouter()
    router.characters.characters_by_user["u1"] = {"pc1": default_fighter("pc1", "Penn")}
    router.characters.active_by_user["u1"] = "pc1"
    router.dispatch(intent("/join"))

    spectating = router.dispatch(intent("/spectate"))

    assert spectating == "你已经作为玩家加入当前战役。"
    assert not router.characters.is_spectator("u1")

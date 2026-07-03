from __future__ import annotations

from dnd_llm.telegram_bot.gateway import normalize_message


def test_gateway_accepts_uppercase_dd_without_space() -> None:
    intent = normalize_message(
        user_id="u1",
        chat_id="group-1",
        text="DD攻击最近的敌人",
        bot_username="dnd_bot",
    )

    assert intent is not None
    assert intent.source == "prefix"
    assert intent.text == "攻击最近的敌人"
    assert intent.is_command is False


def test_gateway_rejects_lowercase_dd_prefix() -> None:
    assert (
        normalize_message(
            user_id="u1",
            chat_id="group-1",
            text="dd 攻击最近的敌人",
            bot_username="dnd_bot",
        )
        is None
    )


def test_gateway_normalizes_commands_and_mentions() -> None:
    command = normalize_message(
        user_id="u1",
        chat_id="group-1",
        text=" /status ",
        bot_username="dnd_bot",
    )
    mention = normalize_message(
        user_id="u1",
        chat_id="group-1",
        text="@dnd_bot 我检查门缝",
        bot_username="dnd_bot",
    )

    assert command is not None
    assert command.source == "command"
    assert command.is_command is True
    assert command.text == "/status"
    assert mention is not None
    assert mention.source == "mention"
    assert mention.text == "我检查门缝"

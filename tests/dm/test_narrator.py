from __future__ import annotations

from dnd_llm.dm.narrator import Narrator


def test_narrator_restates_engine_payload_without_inventing_hidden_numbers() -> None:
    narrator = Narrator()

    text = narrator.narrate_tool_result(
        {
            "success": True,
            "state_changes": [
                {"type": "damage", "target_id": "goblin1", "applied": 5},
                {"type": "condition", "target_id": "goblin1", "condition": "prone"},
            ],
        }
    )

    assert "goblin1 受到 5 点伤害。" in text
    assert "goblin1 获得状态：prone。" in text
    assert "HP" not in text
    assert "hp" not in text
    assert "AC" not in text
    assert "骰" not in text
    assert "掉落" not in text
    assert "获得物品" not in text


def test_narrator_restates_rejection_reason_without_extra_rewards() -> None:
    narrator = Narrator()

    text = narrator.narrate_rejection("no matching action")

    assert text == "这个行动暂时不能执行：no matching action"
    assert "奖励" not in text
    assert "金币" not in text
    assert "物品" not in text

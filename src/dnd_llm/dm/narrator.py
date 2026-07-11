from __future__ import annotations

from typing import Any


class Narrator:
    def narrate_tool_result(self, result: dict[str, Any]) -> str:
        if not result.get("success", True):
            return "行动未能执行。"
        parts = []
        for change in result.get("state_changes", []):
            if change.get("type") == "damage":
                parts.append(f"{change['target_id']} 受到 {change['applied']} 点伤害。")
            elif change.get("type") == "healing":
                parts.append(f"{change['target_id']} 恢复 {change['applied']} 点生命值。")
            elif change.get("type") == "condition":
                parts.append(f"{change['target_id']} 获得状态：{change['condition']}。")
            elif change.get("type") == "remove_condition":
                removed = "、".join(sorted(change.get("removed", {})))
                parts.append(f"{change['target_id']} 移除了状态：{removed}。")
            elif change.get("type") == "max_hp_delta":
                parts.append(f"{change['target_id']} 生命值上限变为 {change['hp_max_after']}。")
            elif change.get("type") == "passive_effect":
                parts.append(f"{change['target_id']} 获得持续效果。")
            elif change.get("type") == "world_effect":
                parts.append(f"场景效果生效：{change['effect_type']}。")
        return "".join(parts) or "行动完成。"

    def narrate_rejection(self, reason: str) -> str:
        return f"这个行动暂时不能执行：{reason}"

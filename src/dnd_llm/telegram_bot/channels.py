from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChannelDirectory:
    private_chat_by_user: dict[str, str] = field(default_factory=dict)

    def bind_private_chat(self, user_id: str, chat_id: str) -> None:
        self.private_chat_by_user[user_id] = chat_id

    def private_chat_for(self, user_id: str) -> str | None:
        return self.private_chat_by_user.get(user_id)


def render_private_required(user_id: str) -> str:
    return f"需要先私聊 bot 并发送 /start 才能接收私密信息（user={user_id}）。"


def fuzzy_hp(current: int, maximum: int) -> str:
    if maximum <= 0:
        return "Unknown"
    ratio = current / maximum
    if ratio >= 0.75:
        return "Healthy"
    if ratio >= 0.5:
        return "Injured"
    if ratio >= 0.25:
        return "Bloodied"
    return "Critical"

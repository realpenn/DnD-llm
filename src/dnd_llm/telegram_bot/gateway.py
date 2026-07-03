from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlayerIntent:
    user_id: str
    chat_id: str
    text: str
    source: str
    is_command: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "user_id": self.user_id,
            "chat_id": self.chat_id,
            "text": self.text,
            "source": self.source,
            "is_command": self.is_command,
        }


def normalize_message(
    *,
    user_id: str,
    chat_id: str,
    text: str,
    bot_username: str | None = None,
) -> PlayerIntent | None:
    raw = text.strip()
    if not raw:
        return None
    if raw.startswith("/"):
        return PlayerIntent(
            user_id=user_id, chat_id=chat_id, text=raw, source="command", is_command=True
        )
    if raw.startswith("DD"):
        return PlayerIntent(user_id=user_id, chat_id=chat_id, text=raw[2:].strip(), source="prefix")
    if bot_username and f"@{bot_username}" in raw:
        cleaned = raw.replace(f"@{bot_username}", "").strip()
        return PlayerIntent(user_id=user_id, chat_id=chat_id, text=cleaned, source="mention")
    return None

from __future__ import annotations

import re
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
        command_parts = raw.split(maxsplit=1)
        command_token = command_parts[0]
        if "@" in command_token:
            command, addressed_username = command_token.rsplit("@", maxsplit=1)
            if (
                not command
                or not bot_username
                or addressed_username.casefold() != bot_username.lstrip("@").casefold()
            ):
                return None
            raw = command + (f" {command_parts[1]}" if len(command_parts) > 1 else "")
        return PlayerIntent(
            user_id=user_id, chat_id=chat_id, text=raw, source="command", is_command=True
        )
    if raw.startswith("DD"):
        return PlayerIntent(user_id=user_id, chat_id=chat_id, text=raw[2:].strip(), source="prefix")
    mention_pattern = (
        re.compile(rf"@{re.escape(bot_username.lstrip('@'))}(?![A-Za-z0-9_])", re.I)
        if bot_username
        else None
    )
    if mention_pattern is not None and mention_pattern.search(raw):
        cleaned = mention_pattern.sub("", raw).strip()
        return PlayerIntent(user_id=user_id, chat_id=chat_id, text=cleaned, source="mention")
    return None

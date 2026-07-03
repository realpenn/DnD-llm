from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dnd_llm.content.character_gen import default_fighter
from dnd_llm.core.models import Character, GameState


@dataclass
class CharacterRegistry:
    characters_by_user: dict[str, dict[str, Character]] = field(default_factory=dict)
    active_by_user: dict[str, str] = field(default_factory=dict)
    campaign_members: dict[str, str] = field(default_factory=dict)
    campaign_spectators: set[str] = field(default_factory=set)

    def create_default(self, user_id: str, name: str) -> Character:
        character_id = f"pc_{user_id}_{len(self.characters_by_user.get(user_id, {})) + 1}"
        character = default_fighter(character_id, name)
        self.characters_by_user.setdefault(user_id, {})[character_id] = character
        self.active_by_user[user_id] = character_id
        return character

    def list_characters(self, user_id: str) -> list[Character]:
        return list(self.characters_by_user.get(user_id, {}).values())

    def active_character(self, user_id: str) -> Character | None:
        character_id = self.active_by_user.get(user_id)
        if character_id is None:
            return None
        return self.characters_by_user.get(user_id, {}).get(character_id)

    def use_character(self, user_id: str, character_id: str) -> Character:
        character = self.characters_by_user.get(user_id, {}).get(character_id)
        if character is None:
            raise KeyError(f"unknown character for user: {character_id}")
        self.active_by_user[user_id] = character_id
        return character

    def update_character(self, user_id: str, character: Character) -> Character:
        updated = Character.from_dict(character.to_dict())
        self.characters_by_user.setdefault(user_id, {})[updated.id] = updated
        if user_id not in self.active_by_user:
            self.active_by_user[user_id] = updated.id
        return updated

    def sync_from_state(self, state: GameState) -> list[str]:
        synced: list[str] = []
        for user_id, character_id in self.campaign_members.items():
            character = state.characters.get(character_id)
            if character is None:
                continue
            self.update_character(user_id, character)
            synced.append(character_id)
        return synced

    def join_campaign(self, user_id: str) -> Character:
        character = self.active_character(user_id)
        if character is None:
            raise ValueError("no active character")
        self.campaign_spectators.discard(user_id)
        self.campaign_members[user_id] = character.id
        return character

    def leave_campaign(self, user_id: str) -> str | None:
        character_id = self.campaign_members.pop(user_id, None)
        if character_id is not None:
            return character_id
        if user_id in self.campaign_spectators:
            self.campaign_spectators.remove(user_id)
            return "spectator"
        return None

    def spectate_campaign(self, user_id: str) -> bool:
        if user_id in self.campaign_members:
            return False
        self.campaign_spectators.add(user_id)
        return True

    def leave_spectator(self, user_id: str) -> bool:
        if user_id not in self.campaign_spectators:
            return False
        self.campaign_spectators.remove(user_id)
        return True

    def is_spectator(self, user_id: str) -> bool:
        return user_id in self.campaign_spectators and user_id not in self.campaign_members

    def character_for_user(self, user_id: str) -> Character | None:
        character_id = self.campaign_members.get(user_id)
        if character_id is None:
            return self.active_character(user_id)
        return self.characters_by_user.get(user_id, {}).get(character_id)

    def campaign_character_for_user(self, user_id: str) -> Character | None:
        character_id = self.campaign_members.get(user_id)
        if character_id is None:
            return None
        return self.characters_by_user.get(user_id, {}).get(character_id)

    def user_for_character(self, character_id: str) -> str | None:
        for user_id, member_character_id in self.campaign_members.items():
            if member_character_id == character_id:
                return user_id
        for user_id, active_character_id in self.active_by_user.items():
            if active_character_id == character_id:
                return user_id
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "characters_by_user": {
                user_id: {
                    character_id: character.to_dict()
                    for character_id, character in characters.items()
                }
                for user_id, characters in self.characters_by_user.items()
            },
            "active_by_user": dict(self.active_by_user),
            "campaign_members": dict(self.campaign_members),
            "campaign_spectators": sorted(self.campaign_spectators),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CharacterRegistry:
        characters_by_user = {
            str(user_id): {
                str(character_id): Character.from_dict(character_data)
                for character_id, character_data in dict(characters).items()
            }
            for user_id, characters in dict(data.get("characters_by_user", {})).items()
        }
        return cls(
            characters_by_user=characters_by_user,
            active_by_user={
                str(user_id): str(character_id)
                for user_id, character_id in dict(data.get("active_by_user", {})).items()
            },
            campaign_members={
                str(user_id): str(character_id)
                for user_id, character_id in dict(data.get("campaign_members", {})).items()
            },
            campaign_spectators={str(user_id) for user_id in data.get("campaign_spectators", [])},
        )

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> CharacterRegistry:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

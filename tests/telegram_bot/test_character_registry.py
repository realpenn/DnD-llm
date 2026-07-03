from __future__ import annotations

from pathlib import Path

from dnd_llm.content.character_gen import default_fighter
from dnd_llm.core.models import GameState
from dnd_llm.telegram_bot.characters import CharacterRegistry


def test_character_registry_syncs_campaign_growth_from_state() -> None:
    registry = CharacterRegistry(
        characters_by_user={"u1": {"pc1": default_fighter("pc1", "Penn")}},
        active_by_user={"u1": "pc1"},
        campaign_members={"u1": "pc1"},
    )
    state_character = default_fighter("pc1", "Penn")
    state_character.gold = 25
    state_character.experience = 100
    state_character.hp_current = 7
    state = GameState(
        campaign_id="test",
        rng_seed=20260629,
        characters={"pc1": state_character},
    )

    synced = registry.sync_from_state(state)
    stored = registry.campaign_character_for_user("u1")

    assert synced == ["pc1"]
    assert stored is not None
    assert stored.gold == 25
    assert stored.experience == 100
    assert stored.hp_current == 7
    assert stored is not state_character


def test_join_binds_current_active_until_rejoined() -> None:
    registry = CharacterRegistry()
    first = registry.create_default("u1", "Aria")
    second = registry.create_default("u1", "Bryn")
    registry.use_character("u1", first.id)

    joined_first = registry.join_campaign("u1")
    registry.use_character("u1", second.id)
    still_joined_first = registry.campaign_character_for_user("u1")
    joined_second = registry.join_campaign("u1")

    assert joined_first.id == first.id
    assert still_joined_first is not None
    assert still_joined_first.id == first.id
    assert registry.active_character("u1") is not None
    assert registry.active_character("u1").id == second.id
    assert joined_second.id == second.id
    assert registry.campaign_members["u1"] == second.id


def test_character_registry_round_trips_to_json(tmp_path: Path) -> None:
    registry = CharacterRegistry(
        characters_by_user={"u1": {"pc1": default_fighter("pc1", "Penn")}},
        active_by_user={"u1": "pc1"},
        campaign_members={"u1": "pc1"},
        campaign_spectators={"u2"},
    )
    registry.characters_by_user["u1"]["pc1"].gold = 12
    registry.characters_by_user["u1"]["pc1"].feats = ["tough"]
    path = tmp_path / "characters.json"

    registry.save(path)
    loaded = CharacterRegistry.load(path)

    assert loaded.to_dict() == registry.to_dict()
    assert loaded.characters_by_user["u1"]["pc1"].feats == ["tough"]
    assert loaded.campaign_character_for_user("u1") is not registry.campaign_character_for_user(
        "u1"
    )

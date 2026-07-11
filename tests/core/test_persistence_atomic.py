from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from dnd_llm.core import persistence
from dnd_llm.core.persistence import AuditLog, load_game, save_game


def _registry_for(state) -> dict[str, object]:
    return {
        "characters_by_user": {"u1": {"pc1": state.characters["pc1"].to_dict()}},
        "active_by_user": {"u1": "pc1"},
        "campaign_members": {"u1": "pc1"},
        "campaign_spectators": [],
    }


def test_save_failure_before_manifest_swap_keeps_previous_generation(
    tmp_path: Path,
    make_state,
    monkeypatch,
) -> None:
    slot = tmp_path / "slot"
    state = make_state()
    state.world.current_zone_id = "start"
    registry = _registry_for(state)
    save_game(slot, state, AuditLog(), registry=registry)
    state.world.current_zone_id = "ruins"
    real_replace = os.replace

    def fail_manifest_swap(source, destination) -> None:
        if Path(destination).name == persistence.SAVE_MANIFEST_NAME:
            raise OSError("injected manifest swap failure")
        real_replace(source, destination)

    monkeypatch.setattr(persistence.os, "replace", fail_manifest_swap)

    with pytest.raises(OSError, match="injected manifest swap failure"):
        save_game(slot, state, AuditLog(), registry=registry)

    loaded_state, _, registry = load_game(slot, include_registry=True)
    assert loaded_state.world.current_zone_id == "start"
    assert registry is not None
    assert registry["campaign_members"] == {"u1": "pc1"}


def test_load_rejects_generation_file_checksum_mismatch(tmp_path: Path, make_state) -> None:
    slot = tmp_path / "slot"
    save_game(slot, make_state(), AuditLog(), registry={})
    manifest = json.loads((slot / persistence.SAVE_MANIFEST_NAME).read_text(encoding="utf-8"))
    state_path = slot / manifest["files"]["state"]["name"]
    state_path.write_text(state_path.read_text(encoding="utf-8") + " ", encoding="utf-8")

    with pytest.raises(ValueError, match="size does not match manifest"):
        load_game(slot)


def test_load_rejects_descriptor_from_another_generation(tmp_path: Path, make_state) -> None:
    slot = tmp_path / "slot"
    save_game(slot, make_state(), AuditLog(), registry={})
    manifest_path = slot / persistence.SAVE_MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["audit"]["generation"] = "different-generation"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="audit generation does not match manifest"):
        load_game(slot)


def test_save_rejects_registry_member_missing_from_state(tmp_path: Path, make_state) -> None:
    state = make_state()
    registry = _registry_for(state)
    registry["characters_by_user"] = {"u1": {"missing": state.characters["pc1"].to_dict()}}
    registry["active_by_user"] = {"u1": "missing"}
    registry["campaign_members"] = {"u1": "missing"}

    with pytest.raises(ValueError, match="missing from saved state"):
        save_game(tmp_path / "slot", state, AuditLog(), registry=registry)

    assert not (tmp_path / "slot" / persistence.SAVE_MANIFEST_NAME).exists()


def test_load_game_remains_compatible_with_legacy_two_file_save(
    tmp_path: Path,
    make_state,
) -> None:
    slot = tmp_path / "legacy"
    slot.mkdir()
    state = make_state()
    (slot / "state.json").write_text(
        json.dumps(state.to_dict(), ensure_ascii=False),
        encoding="utf-8",
    )
    (slot / "audit.jsonl").write_text("", encoding="utf-8")

    loaded_state, loaded_audit, registry = load_game(slot, include_registry=True)

    assert loaded_state.to_dict() == state.to_dict()
    assert loaded_audit.events == []
    assert registry is None


def test_save_rejects_state_event_counter_without_matching_audit(
    tmp_path: Path, make_state
) -> None:
    state = make_state()
    state.event_counter = 5

    with pytest.raises(ValueError, match="contiguous and match state event counter"):
        save_game(tmp_path / "slot", state, AuditLog(), registry={})

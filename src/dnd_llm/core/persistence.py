from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, overload

from .models import GameState


@dataclass
class AuditEvent:
    event_id: str
    event_counter: int
    timestamp: str
    idempotency_key: str
    player_text: str | None = None
    player_intent: dict[str, Any] | None = None
    tool_name: str | None = None
    tool_args: dict[str, Any] = field(default_factory=dict)
    tool_result: dict[str, Any] = field(default_factory=dict)
    automation_node_path: str | None = None
    dice_rolls: list[dict[str, Any]] = field(default_factory=list)
    model_id: str | None = None
    prompt_version: str | None = None
    model_usage: dict[str, int] = field(default_factory=dict)
    schema_version: str = "1.0"
    rules_data_version: str = "srd-5.2.1"
    campaign_pack_version: str = "dev"

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_counter": self.event_counter,
            "timestamp": self.timestamp,
            "idempotency_key": self.idempotency_key,
            "player_text": self.player_text,
            "player_intent": self.player_intent,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "tool_result": self.tool_result,
            "automation_node_path": self.automation_node_path,
            "dice_rolls": self.dice_rolls,
            "model_id": self.model_id,
            "prompt_version": self.prompt_version,
            "model_usage": self.model_usage,
            "schema_version": self.schema_version,
            "rules_data_version": self.rules_data_version,
            "campaign_pack_version": self.campaign_pack_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditEvent:
        return cls(**data)


class AuditLog:
    def __init__(self, events: list[AuditEvent] | None = None):
        self.events = events or []

    def append(
        self,
        state: GameState,
        *,
        idempotency_key: str,
        player_text: str | None = None,
        player_intent: dict[str, Any] | None = None,
        tool_name: str | None = None,
        tool_args: dict[str, Any] | None = None,
        tool_result: dict[str, Any] | None = None,
        automation_node_path: str | None = None,
        dice_rolls: list[dict[str, Any]] | None = None,
        model_id: str | None = None,
        prompt_version: str | None = None,
        model_usage: dict[str, int] | None = None,
    ) -> AuditEvent:
        event_counter = state.event_counter
        event = AuditEvent(
            event_id=f"event-{event_counter:08d}",
            event_counter=event_counter,
            timestamp=datetime.now(UTC).isoformat(),
            idempotency_key=idempotency_key,
            player_text=player_text,
            player_intent=player_intent,
            tool_name=tool_name,
            tool_args=tool_args or {},
            tool_result=tool_result or {},
            automation_node_path=automation_node_path,
            dice_rolls=dice_rolls or [],
            model_id=model_id,
            prompt_version=prompt_version,
            model_usage={key: int(value) for key, value in (model_usage or {}).items()},
            schema_version=state.schema_version,
            rules_data_version=state.rules_data_version,
            campaign_pack_version=state.campaign_pack_version,
        )
        self.events.append(event)
        state.event_counter += 1
        return event

    def to_dicts(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.events]

    def model_usage_totals(self) -> dict[str, int]:
        totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        for event in self.events:
            for key in totals:
                totals[key] += int(event.model_usage.get(key, 0))
        return {key: value for key, value in totals.items() if value > 0}

    @classmethod
    def from_dicts(cls, data: list[dict[str, Any]]) -> AuditLog:
        return cls([AuditEvent.from_dict(item) for item in data])


SAVE_FORMAT_VERSION = 2
SAVE_MANIFEST_NAME = "manifest.json"


def save_game(
    path: str | Path,
    state: GameState,
    audit_log: AuditLog,
    *,
    registry: Mapping[str, Any] | None = None,
) -> None:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    _validate_audit_consistency(state, audit_log)
    registry_data = dict(registry) if registry is not None else None
    if registry_data is not None:
        _validate_registry_consistency(state, registry_data)

    generation = uuid.uuid4().hex
    payloads: dict[str, bytes] = {
        "state": _json_bytes(state.to_dict(), pretty=True),
        "audit": "".join(
            json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True) + "\n"
            for event in audit_log.events
        ).encode("utf-8"),
    }
    if registry_data is not None:
        payloads["registry"] = _json_bytes(registry_data, pretty=True)

    descriptors: dict[str, dict[str, Any]] = {}
    temporary_paths: list[Path] = []
    try:
        for kind, payload in payloads.items():
            suffix = "jsonl" if kind == "audit" else "json"
            filename = f"{kind}-{generation}.{suffix}"
            final_path = target / filename
            temporary_path = target / f".{filename}.{uuid.uuid4().hex}.tmp"
            temporary_paths.append(temporary_path)
            _write_fsynced(temporary_path, payload)
            os.replace(temporary_path, final_path)
            descriptors[kind] = {
                "generation": generation,
                "name": filename,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
            }

        last_counter = audit_log.events[-1].event_counter if audit_log.events else None
        manifest = {
            "format_version": SAVE_FORMAT_VERSION,
            "generation": generation,
            "state_event_counter": state.event_counter,
            "audit_event_count": len(audit_log.events),
            "audit_last_event_counter": last_counter,
            "files": descriptors,
        }
        manifest_path = target / SAVE_MANIFEST_NAME
        manifest_temp = target / f".{SAVE_MANIFEST_NAME}.{generation}.tmp"
        temporary_paths.append(manifest_temp)
        _write_fsynced(manifest_temp, _json_bytes(manifest, pretty=True))
        os.replace(manifest_temp, manifest_path)
        _fsync_directory(target)
    finally:
        for temporary_path in temporary_paths:
            temporary_path.unlink(missing_ok=True)


@overload
def load_game(path: str | Path) -> tuple[GameState, AuditLog]: ...


@overload
def load_game(
    path: str | Path, *, include_registry: Literal[True]
) -> tuple[GameState, AuditLog, dict[str, Any] | None]: ...


def load_game(
    path: str | Path,
    *,
    include_registry: bool = False,
) -> tuple[GameState, AuditLog] | tuple[GameState, AuditLog, dict[str, Any] | None]:
    target = Path(path)
    manifest_path = target / SAVE_MANIFEST_NAME
    if manifest_path.exists():
        state, audit_log, registry = _load_generation(target, manifest_path)
    else:
        state, audit_log, registry = _load_legacy_save(target)
    if include_registry:
        return state, audit_log, registry
    return state, audit_log


def _load_generation(
    target: Path,
    manifest_path: Path,
) -> tuple[GameState, AuditLog, dict[str, Any] | None]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("save manifest must be a JSON object")
    if manifest.get("format_version") != SAVE_FORMAT_VERSION:
        raise ValueError("unsupported save manifest format")
    generation = manifest.get("generation")
    files = manifest.get("files")
    if not isinstance(generation, str) or not generation:
        raise ValueError("save manifest generation is missing")
    if not isinstance(files, dict):
        raise ValueError("save manifest files are missing")

    state_payload = _read_generation_payload(target, files, "state", generation)
    audit_payload = _read_generation_payload(target, files, "audit", generation)
    registry_payload = (
        _read_generation_payload(target, files, "registry", generation)
        if "registry" in files
        else None
    )
    state_data = json.loads(state_payload)
    if not isinstance(state_data, dict):
        raise ValueError("saved state must be a JSON object")
    state = GameState.from_dict(state_data)
    events = _parse_audit_lines(audit_payload)
    audit_log = AuditLog.from_dicts(events)
    registry: dict[str, Any] | None = None
    if registry_payload is not None:
        parsed_registry = json.loads(registry_payload)
        if not isinstance(parsed_registry, dict):
            raise ValueError("saved character registry must be a JSON object")
        registry = parsed_registry
        _validate_registry_consistency(state, registry)

    if manifest.get("state_event_counter") != state.event_counter:
        raise ValueError("save state event counter does not match manifest")
    if manifest.get("audit_event_count") != len(audit_log.events):
        raise ValueError("save audit event count does not match manifest")
    last_counter = audit_log.events[-1].event_counter if audit_log.events else None
    if manifest.get("audit_last_event_counter") != last_counter:
        raise ValueError("save audit event counter does not match manifest")
    _validate_audit_consistency(state, audit_log)
    return state, audit_log, registry


def _load_legacy_save(
    target: Path,
) -> tuple[GameState, AuditLog, dict[str, Any] | None]:
    state_data = json.loads((target / "state.json").read_text(encoding="utf-8"))
    if not isinstance(state_data, dict):
        raise ValueError("saved state must be a JSON object")
    state = GameState.from_dict(state_data)
    audit_path = target / "audit.jsonl"
    events = _parse_audit_lines(
        audit_path.read_text(encoding="utf-8") if audit_path.exists() else ""
    )
    registry_path = target / "registry.json"
    registry: dict[str, Any] | None = None
    if registry_path.exists():
        parsed_registry = json.loads(registry_path.read_text(encoding="utf-8"))
        if not isinstance(parsed_registry, dict):
            raise ValueError("saved character registry must be a JSON object")
        registry = parsed_registry
        _validate_registry_consistency(state, registry)
    audit_log = AuditLog.from_dicts(events)
    _validate_audit_consistency(state, audit_log)
    return state, audit_log, registry


def _read_generation_payload(
    target: Path,
    files: dict[str, Any],
    kind: str,
    generation: str,
) -> str:
    descriptor = files.get(kind)
    if not isinstance(descriptor, dict):
        raise ValueError(f"save manifest is missing {kind} descriptor")
    if descriptor.get("generation") != generation:
        raise ValueError(f"save {kind} generation does not match manifest")
    filename = descriptor.get("name")
    if not isinstance(filename, str) or Path(filename).name != filename:
        raise ValueError(f"save {kind} filename is invalid")
    if f"-{generation}." not in filename:
        raise ValueError(f"save {kind} filename does not match generation")
    path = (target / filename).resolve()
    resolved_target = target.resolve()
    try:
        path.relative_to(resolved_target)
    except ValueError as exc:
        raise ValueError(f"save {kind} file escapes save directory") from exc
    payload = path.read_bytes()
    if descriptor.get("size") != len(payload):
        raise ValueError(f"save {kind} size does not match manifest")
    if descriptor.get("sha256") != hashlib.sha256(payload).hexdigest():
        raise ValueError(f"save {kind} checksum does not match manifest")
    return payload.decode("utf-8")


def _parse_audit_lines(payload: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in payload.splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if not isinstance(event, dict):
            raise ValueError("saved audit event must be a JSON object")
        events.append(event)
    return events


def _validate_audit_consistency(state: GameState, audit_log: AuditLog) -> None:
    counters = [event.event_counter for event in audit_log.events]
    expected = list(range(state.event_counter))
    if counters != expected:
        raise ValueError("audit event counters must be contiguous and match state event counter")


def _validate_registry_consistency(state: GameState, registry: dict[str, Any]) -> None:
    characters_by_user = registry.get("characters_by_user", {})
    active_by_user = registry.get("active_by_user", {})
    campaign_members = registry.get("campaign_members", {})
    campaign_spectators = registry.get("campaign_spectators", [])
    if not isinstance(characters_by_user, dict):
        raise ValueError("character registry ownership must be an object")
    if not isinstance(active_by_user, dict) or not isinstance(campaign_members, dict):
        raise ValueError("character registry active and member maps must be objects")
    if not isinstance(campaign_spectators, list):
        raise ValueError("character registry spectators must be a list")

    owned_by: dict[str, str] = {}
    for raw_user_id, raw_characters in characters_by_user.items():
        user_id = str(raw_user_id)
        if not isinstance(raw_characters, dict):
            raise ValueError(f"character registry ownership for {user_id} must be an object")
        for raw_character_id, character_payload in raw_characters.items():
            character_id = str(raw_character_id)
            if not isinstance(character_payload, dict):
                raise ValueError(f"character registry character {character_id} must be an object")
            previous_owner = owned_by.setdefault(character_id, user_id)
            if previous_owner != user_id:
                raise ValueError(f"character registry character {character_id} has multiple owners")

    for raw_user_id, raw_character_id in active_by_user.items():
        user_id = str(raw_user_id)
        character_id = str(raw_character_id)
        if owned_by.get(character_id) != user_id:
            raise ValueError(f"active character {character_id} is not owned by user {user_id}")

    member_users = {str(user_id) for user_id in campaign_members}
    for raw_user_id, raw_character_id in campaign_members.items():
        user_id = str(raw_user_id)
        character_id = str(raw_character_id)
        if owned_by.get(character_id) != user_id:
            raise ValueError(f"campaign character {character_id} is not owned by user {user_id}")
        if character_id not in state.characters:
            raise ValueError(f"campaign character {character_id} is missing from saved state")

    spectator_users = {str(user_id) for user_id in campaign_spectators}
    overlap = member_users.intersection(spectator_users)
    if overlap:
        raise ValueError(f"campaign users cannot be both members and spectators: {sorted(overlap)}")


def _json_bytes(value: object, *, pretty: bool) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2 if pretty else None,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _write_fsynced(path: Path, payload: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)

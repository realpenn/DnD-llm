from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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


def save_game(path: str | Path, state: GameState, audit_log: AuditLog) -> None:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    (target / "state.json").write_text(
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    with (target / "audit.jsonl").open("w", encoding="utf-8") as handle:
        for event in audit_log.events:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")


def load_game(path: str | Path) -> tuple[GameState, AuditLog]:
    target = Path(path)
    state = GameState.from_dict(json.loads((target / "state.json").read_text(encoding="utf-8")))
    events: list[dict[str, Any]] = []
    audit_path = target / "audit.jsonl"
    if audit_path.exists():
        for line in audit_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
    return state, AuditLog.from_dicts(events)

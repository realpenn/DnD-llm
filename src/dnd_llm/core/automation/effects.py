from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EffectInstance:
    effect_id: str
    source_ref: str
    source_action_id: str
    target_id: str
    applied_by: str
    condition: str | None = None
    passive_modifiers: dict[str, Any] = field(default_factory=dict)
    duration: dict[str, Any] = field(default_factory=dict)
    tick_on: str | None = None
    concentration: bool = False
    stacking_policy: str = "replace"
    parent_effect_id: str | None = None
    child_effect_ids: list[str] = field(default_factory=list)
    remove_conditions: list[str] = field(default_factory=list)
    audit: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "effect_id": self.effect_id,
            "source_ref": self.source_ref,
            "source_action_id": self.source_action_id,
            "target_id": self.target_id,
            "applied_by": self.applied_by,
            "condition": self.condition,
            "passive_modifiers": self.passive_modifiers,
            "duration": self.duration,
            "tick_on": self.tick_on,
            "concentration": self.concentration,
            "stacking_policy": self.stacking_policy,
            "parent_effect_id": self.parent_effect_id,
            "child_effect_ids": self.child_effect_ids,
            "remove_conditions": self.remove_conditions,
            "audit": self.audit,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EffectInstance:
        return cls(**data)

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Cost:
    spell_slot_level: int | None = None
    resources: dict[str, int] = field(default_factory=dict)
    resource_params: dict[str, str] = field(default_factory=dict)
    items: dict[str, int] = field(default_factory=dict)
    gold: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "spell_slot_level": self.spell_slot_level,
            "resources": self.resources,
            "resource_params": self.resource_params,
            "items": self.items,
            "gold": self.gold,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Cost:
        return cls(**(data or {}))


@dataclass
class ActionDefinition:
    id: str
    name: str
    localization: dict[str, Any]
    source: str
    rules_version: str
    action_type: str
    action_economy: str
    range: dict[str, Any]
    target_policy: dict[str, Any]
    requirements: dict[str, Any] = field(default_factory=dict)
    properties: dict[str, Any] = field(default_factory=dict)
    friendly_fire_policy: str = "confirm"
    cost: Cost = field(default_factory=Cost)
    automation: list[dict[str, Any]] = field(default_factory=list)
    audit_label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "localization": self.localization,
            "source": self.source,
            "rules_version": self.rules_version,
            "action_type": self.action_type,
            "action_economy": self.action_economy,
            "range": self.range,
            "target_policy": self.target_policy,
            "requirements": self.requirements,
            "properties": self.properties,
            "friendly_fire_policy": self.friendly_fire_policy,
            "cost": self.cost.to_dict(),
            "automation": self.automation,
            "audit_label": self.audit_label or self.name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionDefinition:
        payload = dict(data)
        payload["cost"] = Cost.from_dict(payload.get("cost"))
        return cls(**payload)


@dataclass
class HazardDefinition:
    id: str
    name: str
    hazard_type: str
    source: str
    rules_version: str
    params_schema: dict[str, Any]
    automation: list[dict[str, Any]]
    audit_label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "hazard_type": self.hazard_type,
            "source": self.source,
            "rules_version": self.rules_version,
            "params_schema": self.params_schema,
            "automation": self.automation,
            "audit_label": self.audit_label or self.name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HazardDefinition:
        return cls(**data)


@dataclass
class EventDefinition:
    id: str
    name: str
    source: str
    rules_version: str
    trigger: dict[str, Any]
    automation: list[dict[str, Any]]
    audit_label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "source": self.source,
            "rules_version": self.rules_version,
            "trigger": self.trigger,
            "automation": self.automation,
            "audit_label": self.audit_label or self.name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EventDefinition:
        return cls(**data)


@dataclass
class ConditionDefinition:
    id: str
    name: str
    localization: dict[str, Any]
    source: str
    rules_version: str
    effects: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "localization": self.localization,
            "source": self.source,
            "rules_version": self.rules_version,
            "effects": self.effects,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConditionDefinition:
        return cls(**data)


@dataclass
class ClassDefinition:
    id: str
    name: str
    localization: dict[str, Any]
    source: str
    rules_version: str
    hit_die: str
    primary_abilities: list[str]
    saving_throw_proficiencies: list[str]
    levels: dict[str, dict[str, Any]]
    subclasses: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "localization": self.localization,
            "source": self.source,
            "rules_version": self.rules_version,
            "hit_die": self.hit_die,
            "primary_abilities": self.primary_abilities,
            "saving_throw_proficiencies": self.saving_throw_proficiencies,
            "levels": self.levels,
            "subclasses": self.subclasses,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClassDefinition:
        return cls(**data)


@dataclass
class SpellDefinition:
    id: str
    name: str
    localization: dict[str, Any]
    source: str
    rules_version: str
    level: int
    school: str
    classes: list[str]
    ritual: bool = False
    action_id: str | None = None
    action: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "localization": self.localization,
            "source": self.source,
            "rules_version": self.rules_version,
            "level": self.level,
            "school": self.school,
            "classes": self.classes,
            "ritual": self.ritual,
            "action_id": self.action_id,
            "action": self.action,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpellDefinition:
        return cls(**data)


@dataclass
class MonsterDefinition:
    id: str
    name: str
    localization: dict[str, Any]
    source: str
    rules_version: str
    armor_class: int
    hit_points: int
    speed_ft: int
    cr: float
    abilities: dict[str, int]
    size: str = "medium"
    creature_type: str = "humanoid"
    actions: list[str] = field(default_factory=list)
    resistances: list[str] = field(default_factory=list)
    immunities: list[str] = field(default_factory=list)
    vulnerabilities: list[str] = field(default_factory=list)
    condition_immunities: list[str] = field(default_factory=list)
    traits: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "localization": self.localization,
            "source": self.source,
            "rules_version": self.rules_version,
            "armor_class": self.armor_class,
            "hit_points": self.hit_points,
            "speed_ft": self.speed_ft,
            "cr": self.cr,
            "abilities": self.abilities,
            "size": self.size,
            "creature_type": self.creature_type,
            "actions": self.actions,
            "resistances": self.resistances,
            "immunities": self.immunities,
            "vulnerabilities": self.vulnerabilities,
            "condition_immunities": self.condition_immunities,
            "traits": self.traits,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MonsterDefinition:
        return cls(**data)


@dataclass
class ItemDefinition:
    id: str
    name: str
    localization: dict[str, Any]
    source: str
    rules_version: str
    item_type: str
    actions: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    quantity: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "localization": self.localization,
            "source": self.source,
            "rules_version": self.rules_version,
            "item_type": self.item_type,
            "actions": self.actions,
            "properties": self.properties,
            "quantity": self.quantity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ItemDefinition:
        return cls(**data)

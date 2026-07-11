from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..automation.definitions import (
    ActionDefinition,
    ClassDefinition,
    ConditionDefinition,
    EventDefinition,
    HazardDefinition,
    ItemDefinition,
    MonsterDefinition,
    SpellDefinition,
)
from .localization import AliasIndex
from .schema_loader import SchemaRegistry
from .validators import RuleDataValidator, trusted_srd_catalog


@dataclass
class Compendium:
    actions: dict[str, ActionDefinition] = field(default_factory=dict)
    hazards: dict[str, HazardDefinition] = field(default_factory=dict)
    events: dict[str, EventDefinition] = field(default_factory=dict)
    conditions: dict[str, ConditionDefinition] = field(default_factory=dict)
    classes: dict[str, ClassDefinition] = field(default_factory=dict)
    spells: dict[str, SpellDefinition] = field(default_factory=dict)
    monsters: dict[str, MonsterDefinition] = field(default_factory=dict)
    items: dict[str, ItemDefinition] = field(default_factory=dict)
    aliases: AliasIndex = field(default_factory=AliasIndex)
    attributions: list[dict[str, Any]] = field(default_factory=list)

    def action(self, action_id: str) -> ActionDefinition:
        if action_id not in self.actions:
            raise KeyError(f"unknown action: {action_id}")
        return self.actions[action_id]

    def hazard(self, hazard_id: str) -> HazardDefinition:
        if hazard_id not in self.hazards:
            raise KeyError(f"unknown hazard: {hazard_id}")
        return self.hazards[hazard_id]

    def spell(self, spell_id: str) -> SpellDefinition:
        if spell_id not in self.spells:
            raise KeyError(f"unknown spell: {spell_id}")
        return self.spells[spell_id]


class CompendiumLoader:
    def __init__(self, root: str | Path, validator: RuleDataValidator | None = None):
        self.root = Path(root)
        self.validator = validator or RuleDataValidator(
            schema_registry=SchemaRegistry(self.root / "schemas")
        )

    def load(self) -> Compendium:
        self.validator.srd_catalog = trusted_srd_catalog()
        compendium = Compendium()
        compendium.attributions = self._load_attributions()
        for path in sorted(self.root.glob("srd/actions/**/*.json")):
            for item in _load_items(path):
                report = self.validator.validate_action(item)
                report.require_ok()
                action = ActionDefinition.from_dict(item)
                _store_unique(compendium.actions, action.id, action, "action")
                self._add_aliases(compendium, action)
        scoped_validator = RuleDataValidator(
            known_action_ids=set(compendium.actions),
            schema_registry=self.validator.schema_registry,
            srd_catalog=self.validator.srd_catalog,
        )
        self._load_spells(compendium, scoped_validator)
        scoped_validator.known_action_ids = set(compendium.actions)
        self._load_conditions(compendium, scoped_validator)
        self._load_classes(compendium, scoped_validator)
        self._load_monsters(compendium, scoped_validator)
        self._load_items(compendium, scoped_validator)
        for path in sorted(self.root.glob("srd/hazards/**/*.json")):
            for item in _load_items(path):
                report = self.validator.validate_hazard(item)
                report.require_ok()
                hazard = HazardDefinition.from_dict(item)
                _store_unique(compendium.hazards, hazard.id, hazard, "hazard")
        for path in sorted(self.root.glob("campaigns/events/**/*.json")):
            for item in _load_items(path):
                report = self.validator.validate_event(item)
                report.require_ok()
                event = EventDefinition.from_dict(item)
                _store_unique(compendium.events, event.id, event, "event")
        return compendium

    def _load_conditions(
        self,
        compendium: Compendium,
        validator: RuleDataValidator,
    ) -> None:
        for path in sorted(self.root.glob("srd/conditions/**/*.json")):
            for item in _load_items(path):
                if isinstance(item, str):
                    item = {
                        "id": item,
                        "name": item.title(),
                        "localization": {"en": item.title(), "zh": item, "aliases": []},
                        "source": "SRD 5.2.1",
                        "rules_version": "srd-5.2.1",
                        "effects": {},
                    }
                report = validator.validate_condition(item)
                report.require_ok()
                condition = ConditionDefinition.from_dict(item)
                _store_unique(compendium.conditions, condition.id, condition, "condition")

    def _load_classes(
        self,
        compendium: Compendium,
        validator: RuleDataValidator,
    ) -> None:
        for path in sorted(self.root.glob("srd/classes/**/*.json")):
            for item in _load_items(path):
                report = validator.validate_class(item)
                report.require_ok()
                class_definition = ClassDefinition.from_dict(item)
                _store_unique(compendium.classes, class_definition.id, class_definition, "class")

    def _load_spells(
        self,
        compendium: Compendium,
        validator: RuleDataValidator,
    ) -> None:
        for path in sorted(self.root.glob("srd/spells/**/*.json")):
            for item in _load_items(path):
                report = validator.validate_spell(item)
                report.require_ok()
                spell = SpellDefinition.from_dict(item)
                if spell.action is not None:
                    action = ActionDefinition.from_dict(spell.action)
                    action.properties = {
                        **action.properties,
                        "spell_definition_id": spell.id,
                        "spell_level": spell.level,
                        "spell_classes": list(spell.classes),
                    }
                    if spell.ritual:
                        action.properties["ritual"] = True
                    _store_unique(compendium.actions, action.id, action, "action")
                    self._add_aliases(compendium, action)
                    spell.action_id = action.id
                _store_unique(compendium.spells, spell.id, spell, "spell")

    def _load_monsters(
        self,
        compendium: Compendium,
        validator: RuleDataValidator,
    ) -> None:
        for path in sorted(self.root.glob("srd/monsters/**/*.json")):
            for item in _load_items(path):
                report = validator.validate_monster(item)
                report.require_ok()
                monster = MonsterDefinition.from_dict(item)
                _store_unique(compendium.monsters, monster.id, monster, "monster")

    def _load_items(
        self,
        compendium: Compendium,
        validator: RuleDataValidator,
    ) -> None:
        for path in sorted(self.root.glob("srd/items/**/*.json")):
            for item in _load_items(path):
                report = validator.validate_item(item)
                report.require_ok()
                item_definition = ItemDefinition.from_dict(item)
                _store_unique(compendium.items, item_definition.id, item_definition, "item")

    def _load_attributions(self) -> list[dict[str, Any]]:
        path = self.root / "attribution.json"
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise ValueError("rules_data/attribution.json must contain an items list")
        items: list[dict[str, Any]] = []
        for index, item in enumerate(data["items"]):
            if not isinstance(item, dict):
                raise ValueError(f"attribution item {index} must be an object")
            for field_name in ("id", "title", "license", "source_url"):
                if not item.get(field_name):
                    raise ValueError(f"attribution item {index} missing {field_name}")
            items.append(item)
        return items

    @staticmethod
    def _add_aliases(compendium: Compendium, action: ActionDefinition) -> None:
        names = [action.name]
        loc = action.localization
        for key in ("en", "zh"):
            if isinstance(loc.get(key), str):
                names.append(loc[key])
        aliases = loc.get("aliases", [])
        if isinstance(aliases, list):
            names.extend(str(alias) for alias in aliases)
        compendium.aliases.add(action.id, *names)


def _load_items(path: Path) -> list[Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return list(data["items"])
    if isinstance(data, dict):
        return [data]
    raise ValueError(f"unsupported rule data file: {path}")


def _store_unique(
    entries: dict[str, Any],
    entry_id: str,
    entry: Any,
    namespace: str,
) -> None:
    if entry_id in entries:
        raise ValueError(f"duplicate {namespace} id {entry_id}")
    entries[entry_id] = entry

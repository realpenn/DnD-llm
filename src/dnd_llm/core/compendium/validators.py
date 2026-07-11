from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
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
from ..automation.nodes import validate_node
from .localization import AliasIndex
from .schema_loader import SchemaRegistry
from .srd_catalog_manifest import SRD_CATALOG_MANIFEST

SrdCatalog = dict[str, dict[str, tuple[str, str, str]]]


def trusted_srd_catalog() -> SrdCatalog:
    return {namespace: dict(entries) for namespace, entries in SRD_CATALOG_MANIFEST.items()}


def claims_official_srd(owner_id: str, source: str) -> bool:
    return owner_id.startswith("srd.") or source.casefold().startswith("srd 5.2.1")


def rule_payload_digest(data: object) -> str:
    payload = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


ALLOWED_ACTION_ECONOMY = {"action", "bonus_action", "reaction", "movement", "free", "none"}
ALLOWED_FRIENDLY_FIRE = {"off", "confirm", "raw"}
ALLOWED_DAMAGE_TYPES = {
    "acid",
    "bludgeoning",
    "cold",
    "fire",
    "force",
    "lightning",
    "necrotic",
    "piercing",
    "poison",
    "psychic",
    "radiant",
    "slashing",
    "thunder",
    "untyped",
}
ALLOWED_CREATURE_TYPES = {
    "aberration",
    "beast",
    "celestial",
    "construct",
    "dragon",
    "elemental",
    "fey",
    "fiend",
    "giant",
    "humanoid",
    "monstrosity",
    "ooze",
    "plant",
    "undead",
}
ALLOWED_CONDITIONS = {
    "blinded",
    "charmed",
    "deafened",
    "exhaustion",
    "frightened",
    "grappled",
    "incapacitated",
    "invisible",
    "paralyzed",
    "petrified",
    "poisoned",
    "prone",
    "restrained",
    "stunned",
    "unconscious",
}
ALLOWED_ACTION_MARKERS = {
    "bardic_inspiration",
    "dodging",
    "disengaged",
    "divine_sense",
    "helping",
    "hidden",
    "innate_sorcery",
    "jump_distance_doubled",
    "reckless_attack",
    "raging",
    "sacred_weapon",
    "steady_aim",
    "superior_defense",
    "turned",
    "wild_shape",
}
ALLOWED_EFFECT_MARKERS = {
    "magical_contagion",
}


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def extend(self, errors: list[str]) -> None:
        self.errors.extend(errors)

    def require_ok(self) -> None:
        if self.errors:
            raise ValueError("; ".join(self.errors))


class RuleDataValidator:
    def __init__(
        self,
        known_action_ids: set[str] | None = None,
        schema_registry: SchemaRegistry | None = None,
        srd_catalog: SrdCatalog | None = None,
    ):
        self.known_action_ids = set(known_action_ids or set())
        self._validate_action_references = known_action_ids is not None
        self.schema_registry = schema_registry or SchemaRegistry()
        self.srd_catalog = srd_catalog

    def validate_action(self, data: dict[str, Any]) -> ValidationReport:
        report = ValidationReport()
        report.extend(self.schema_registry.validate("action", data))
        if report.errors:
            return report
        required = {
            "id",
            "name",
            "localization",
            "source",
            "rules_version",
            "action_type",
            "action_economy",
            "range",
            "target_policy",
            "automation",
        }
        for required_field in sorted(required):
            if required_field not in data:
                report.errors.append(f"ActionDefinition missing {required_field}")
        if report.errors:
            return report
        try:
            action = ActionDefinition.from_dict(data)
        except TypeError as exc:
            report.errors.append(str(exc))
            return report
        self._validate_source_metadata(
            "action",
            action.id,
            action.source,
            action.rules_version,
            data,
            report,
        )
        if action.action_economy not in ALLOWED_ACTION_ECONOMY:
            report.errors.append(f"{action.id}: invalid action_economy {action.action_economy}")
        if action.friendly_fire_policy not in ALLOWED_FRIENDLY_FIRE:
            report.errors.append(f"{action.id}: invalid friendly_fire_policy")
        allowed_damage_types = action.properties.get("allowed_damage_types")
        if allowed_damage_types is not None:
            if not isinstance(allowed_damage_types, list) or not allowed_damage_types:
                report.errors.append(f"{action.id}: allowed_damage_types must be a non-empty list")
            else:
                for damage_type in allowed_damage_types:
                    if damage_type not in ALLOWED_DAMAGE_TYPES:
                        report.errors.append(
                            f"{action.id}: invalid allowed_damage_type {damage_type}"
                        )
        allowed_creature_types = action.properties.get("allowed_creature_types")
        if allowed_creature_types is not None:
            if not isinstance(allowed_creature_types, list) or not allowed_creature_types:
                report.errors.append(
                    f"{action.id}: allowed_creature_types must be a non-empty list"
                )
            else:
                for creature_type in allowed_creature_types:
                    if creature_type not in ALLOWED_CREATURE_TYPES:
                        report.errors.append(
                            f"{action.id}: invalid allowed_creature_type {creature_type}"
                        )
        for param_property in ("damage_type_param", "creature_types_param"):
            param_name = action.properties.get(param_property)
            if param_name is not None and (not isinstance(param_name, str) or not param_name):
                report.errors.append(f"{action.id}: {param_property} must be a non-empty string")
        if not isinstance(action.cost.resource_params, dict):
            report.errors.append(f"{action.id}: cost.resource_params must be an object")
        else:
            for resource, param_name in action.cost.resource_params.items():
                if not isinstance(resource, str) or not isinstance(param_name, str):
                    report.errors.append(
                        f"{action.id}: cost.resource_params keys and values must be strings"
                    )
                elif not resource or not param_name:
                    report.errors.append(
                        f"{action.id}: cost.resource_params cannot contain empty strings"
                    )
        if not isinstance(action.automation, list):
            report.errors.append(f"{action.id}: automation must be a list")
        for index, node in enumerate(action.automation):
            report.extend(validate_node(node, f"{action.id}.automation[{index}]"))
            self._validate_rule_node(action.id, node, report)
        return report

    def validate_condition(self, data: dict[str, Any]) -> ValidationReport:
        report = ValidationReport()
        report.extend(self.schema_registry.validate("condition", data))
        if report.errors:
            return report
        try:
            condition = ConditionDefinition.from_dict(data)
        except TypeError as exc:
            report.errors.append(str(exc))
            return report
        self._validate_source_metadata(
            "condition",
            condition.id,
            condition.source,
            condition.rules_version,
            data,
            report,
        )
        if condition.id not in ALLOWED_CONDITIONS and not condition.id.startswith("marker."):
            report.errors.append(f"{condition.id}: unknown core condition id")
        if not condition.localization:
            report.errors.append(f"{condition.id}: localization is required")
        return report

    def validate_class(self, data: dict[str, Any]) -> ValidationReport:
        report = ValidationReport()
        report.extend(self.schema_registry.validate("class", data))
        if report.errors:
            return report
        try:
            class_definition = ClassDefinition.from_dict(data)
        except TypeError as exc:
            report.errors.append(str(exc))
            return report
        self._validate_source_metadata(
            "class",
            class_definition.id,
            class_definition.source,
            class_definition.rules_version,
            data,
            report,
        )
        if class_definition.hit_die not in {"d6", "d8", "d10", "d12"}:
            report.errors.append(f"{class_definition.id}: invalid hit_die")
        levels = {int(level) for level in class_definition.levels}
        missing = set(range(1, 6)) - levels
        if missing:
            report.errors.append(
                f"{class_definition.id}: missing levels 1-5 entries {sorted(missing)}"
            )
        if not class_definition.subclasses:
            report.errors.append(f"{class_definition.id}: missing level 3 subclass entry")
        for subclass_id, subclass in class_definition.subclasses.items():
            level = subclass.get("level")
            if level != 3:
                report.errors.append(
                    f"{class_definition.id}.{subclass_id}: subclass level must be 3"
                )
            features = subclass.get("features", [])
            if not isinstance(features, list) or not features:
                report.errors.append(
                    f"{class_definition.id}.{subclass_id}: subclass features are required"
                )
            for action_id in subclass.get("actions", []):
                self._validate_action_ref(
                    f"{class_definition.id}.{subclass_id}",
                    str(action_id),
                    report,
                )
        for level, payload in class_definition.levels.items():
            if int(level) < 1:
                report.errors.append(f"{class_definition.id}: level must be positive")
            for action_id in payload.get("actions", []):
                self._validate_action_ref(class_definition.id, str(action_id), report)
        return report

    def validate_spell(self, data: dict[str, Any]) -> ValidationReport:
        report = ValidationReport()
        report.extend(self.schema_registry.validate("spell", data))
        if report.errors:
            return report
        try:
            spell = SpellDefinition.from_dict(data)
        except TypeError as exc:
            report.errors.append(str(exc))
            return report
        self._validate_source_metadata(
            "spell",
            spell.id,
            spell.source,
            spell.rules_version,
            data,
            report,
        )
        if spell.level < 0 or spell.level > 9:
            report.errors.append(f"{spell.id}: SRD spell level must be 0-9")
        if bool(spell.action_id) == bool(spell.action):
            report.errors.append(f"{spell.id}: exactly one of action_id or action is required")
        if spell.action_id:
            self._validate_action_ref(spell.id, spell.action_id, report)
        if spell.action:
            action_report = self.validate_action(spell.action)
            for error in action_report.errors:
                report.errors.append(f"{spell.id}.action: {error}")
        return report

    def validate_monster(self, data: dict[str, Any]) -> ValidationReport:
        report = ValidationReport()
        report.extend(self.schema_registry.validate("monster", data))
        if report.errors:
            return report
        try:
            monster = MonsterDefinition.from_dict(data)
        except TypeError as exc:
            report.errors.append(str(exc))
            return report
        self._validate_source_metadata(
            "monster",
            monster.id,
            monster.source,
            monster.rules_version,
            data,
            report,
        )
        if monster.armor_class <= 0 or monster.hit_points <= 0:
            report.errors.append(f"{monster.id}: armor_class and hit_points must be positive")
        if monster.cr < 0:
            report.errors.append(f"{monster.id}: cr cannot be negative")
        if monster.creature_type not in ALLOWED_CREATURE_TYPES:
            report.errors.append(f"{monster.id}: invalid creature_type {monster.creature_type}")
        for ability in ("str", "dex", "con", "int", "wis", "cha"):
            if ability not in monster.abilities:
                report.errors.append(f"{monster.id}: missing ability {ability}")
        for action_id in monster.actions:
            self._validate_action_ref(monster.id, action_id, report)
        return report

    def validate_item(self, data: dict[str, Any]) -> ValidationReport:
        report = ValidationReport()
        report.extend(self.schema_registry.validate("item", data))
        if report.errors:
            return report
        try:
            item = ItemDefinition.from_dict(data)
        except TypeError as exc:
            report.errors.append(str(exc))
            return report
        self._validate_source_metadata(
            "item",
            item.id,
            item.source,
            item.rules_version,
            data,
            report,
        )
        if item.quantity < 0:
            report.errors.append(f"{item.id}: quantity cannot be negative")
        for action_id in item.actions:
            self._validate_action_ref(item.id, action_id, report)
        return report

    def validate_hazard(self, data: dict[str, Any]) -> ValidationReport:
        report = ValidationReport()
        report.extend(self.schema_registry.validate("hazard", data))
        if report.errors:
            return report
        try:
            hazard = HazardDefinition.from_dict(data)
        except TypeError as exc:
            report.errors.append(str(exc))
            return report
        self._validate_source_metadata(
            "hazard",
            hazard.id,
            hazard.source,
            hazard.rules_version,
            data,
            report,
        )
        if not hazard.hazard_type:
            report.errors.append(f"{hazard.id}: hazard_type is required")
        for index, node in enumerate(hazard.automation):
            report.extend(validate_node(node, f"{hazard.id}.automation[{index}]"))
            self._validate_rule_node(hazard.id, node, report)
        return report

    def validate_event(self, data: dict[str, Any]) -> ValidationReport:
        report = ValidationReport()
        report.extend(self.schema_registry.validate("event", data))
        if report.errors:
            return report
        try:
            event = EventDefinition.from_dict(data)
        except TypeError as exc:
            report.errors.append(str(exc))
            return report
        self._validate_source_metadata(
            "event",
            event.id,
            event.source,
            event.rules_version,
            data,
            report,
        )
        if not isinstance(event.trigger, dict):
            report.errors.append(f"{event.id}: trigger must be object")
        for index, node in enumerate(event.automation):
            report.extend(validate_node(node, f"{event.id}.automation[{index}]"))
            self._validate_rule_node(event.id, node, report)
        return report

    def validate_aliases(self, actions: list[ActionDefinition]) -> dict[str, list[str]]:
        index = AliasIndex()
        for action in actions:
            names = [action.name]
            loc = action.localization
            for key in ("en", "zh"):
                if isinstance(loc.get(key), str):
                    names.append(loc[key])
            aliases = loc.get("aliases", [])
            if isinstance(aliases, list):
                names.extend(str(alias) for alias in aliases)
            index.add(action.id, *names)
        return index.ambiguous()

    def _validate_rule_node(
        self,
        owner_id: str,
        node: dict[str, Any],
        report: ValidationReport,
    ) -> None:
        node_type = node.get("type")
        if node_type == "damage" and node.get("damage_type", "untyped") not in ALLOWED_DAMAGE_TYPES:
            report.errors.append(f"{owner_id}: invalid damage_type {node.get('damage_type')}")
        if node_type == "condition" and node.get("condition") not in (
            ALLOWED_CONDITIONS | ALLOWED_ACTION_MARKERS
        ):
            report.errors.append(f"{owner_id}: invalid condition {node.get('condition')}")
        if node_type == "condition" and "passive_modifiers" in node:
            modifiers = node.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                report.errors.append(f"{owner_id}: passive_modifiers must be an object")
        if node_type == "remove_condition":
            conditions = node.get("conditions", [])
            for condition in conditions:
                if condition not in ALLOWED_CONDITIONS:
                    report.errors.append(f"{owner_id}: invalid condition {condition}")
            effect_markers = node.get("effect_markers", [])
            for marker in effect_markers:
                if marker not in ALLOWED_EFFECT_MARKERS:
                    report.errors.append(f"{owner_id}: invalid effect_marker {marker}")
        if node_type == "restoring_touch":
            conditions = node.get("allowed_conditions", [])
            for condition in conditions:
                if condition not in ALLOWED_CONDITIONS:
                    report.errors.append(f"{owner_id}: invalid condition {condition}")
        if node_type == "passive_effect":
            condition = node.get("condition")
            if condition is not None and condition not in (
                ALLOWED_CONDITIONS | ALLOWED_ACTION_MARKERS
            ):
                report.errors.append(f"{owner_id}: invalid condition {condition}")
            modifiers = node.get("passive_modifiers", {})
            if not isinstance(modifiers, dict):
                report.errors.append(f"{owner_id}: passive_modifiers must be an object")
        if node_type == "world_effect":
            if not isinstance(node.get("effect_type"), str) or not node.get("effect_type"):
                report.errors.append(f"{owner_id}: world_effect requires effect_type")
            if "scope" in node and not isinstance(node["scope"], dict):
                report.errors.append(f"{owner_id}: world_effect scope must be an object")
            if "metadata" in node and not isinstance(node["metadata"], dict):
                report.errors.append(f"{owner_id}: world_effect metadata must be an object")
        if node_type == "repeat_use_save_before_long_rest":
            condition = node.get("failure_condition")
            if condition is not None and condition not in ALLOWED_CONDITIONS:
                report.errors.append(f"{owner_id}: invalid condition {condition}")
        if "automation" in node:
            report.errors.append(f"{owner_id}: nested runtime automation injection is forbidden")
        if node_type == "branch":
            for child in node.get("if_true", []):
                self._validate_rule_node(owner_id, child, report)
            for child in node.get("if_false", []):
                self._validate_rule_node(owner_id, child, report)

    def _validate_action_ref(
        self,
        owner_id: str,
        action_id: str,
        report: ValidationReport,
    ) -> None:
        if self._validate_action_references and action_id not in self.known_action_ids:
            report.errors.append(f"{owner_id}: unknown action reference {action_id}")

    def _validate_source_metadata(
        self,
        namespace: str,
        owner_id: str,
        source: str,
        rules_version: str,
        payload: dict[str, Any],
        report: ValidationReport,
    ) -> None:
        source_text = source.casefold()
        rules_text = rules_version.casefold()
        if owner_id.startswith("srd.") and not rules_text.startswith("srd-"):
            report.errors.append(f"{owner_id}: srd namespace requires srd rules_version")
        if owner_id.startswith("srd.") and "srd" not in source_text:
            report.errors.append(f"{owner_id}: srd namespace requires SRD source")
        if not claims_official_srd(owner_id, source):
            return
        if self.srd_catalog is None:
            return
        catalog_entry = self.srd_catalog.get(namespace, {}).get(owner_id)
        if catalog_entry is None:
            report.errors.append(f"{owner_id}: unknown {namespace} id in verified SRD catalog")
            return
        expected_source, expected_rules_version, expected_digest = catalog_entry
        if source != expected_source:
            report.errors.append(f"{owner_id}: source does not match verified SRD catalog entry")
        if rules_version != expected_rules_version:
            report.errors.append(
                f"{owner_id}: rules_version does not match verified SRD catalog entry"
            )
        if rule_payload_digest(payload) != expected_digest:
            report.errors.append(f"{owner_id}: content does not match verified SRD catalog entry")

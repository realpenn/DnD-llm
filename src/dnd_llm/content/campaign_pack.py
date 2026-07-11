from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

from dnd_llm.core.compendium.loader import Compendium
from dnd_llm.core.compendium.schema_loader import SchemaRegistry
from dnd_llm.core.compendium.validators import RuleDataValidator, ValidationReport
from dnd_llm.core.positioning import TacticalGraph

from .encounter_budget import EncounterBudget, budget_from_encounter, cr_fraction, xp_for_cr

_CAMPAIGN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


def campaign_id_validation_error(campaign_id: str) -> str | None:
    if not campaign_id:
        return "campaign_id is required"
    if Path(campaign_id).is_absolute():
        return "campaign_id must not be an absolute path"
    if ".." in campaign_id:
        return "campaign_id must not contain '..'"
    if "/" in campaign_id or "\\" in campaign_id:
        return "campaign_id must not contain path separators"
    if _CAMPAIGN_ID_RE.fullmatch(campaign_id) is None:
        return "campaign_id may contain only letters, numbers, underscores, and hyphens"
    return None


@dataclass
class CampaignPackDefinition:
    campaign_id: str
    title: str
    version: str
    rules_version: str
    start_zone_id: str
    zones: dict[str, dict[str, Any]]
    outline: dict[str, Any] = field(default_factory=dict)
    encounters: dict[str, dict[str, Any]] = field(default_factory=dict)
    rewards: dict[str, dict[str, Any]] = field(default_factory=dict)
    events: dict[str, dict[str, Any]] = field(default_factory=dict)
    attribution: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CampaignPackDefinition:
        return cls(
            campaign_id=str(data["campaign_id"]),
            title=str(data["title"]),
            version=str(data.get("version", "dev")),
            rules_version=str(data.get("rules_version", "srd-5.2.1")),
            start_zone_id=str(data.get("start_zone_id", "start")),
            zones=dict(data.get("zones", {})),
            outline=dict(data.get("outline", {})),
            encounters=dict(data.get("encounters", {})),
            rewards=dict(data.get("rewards", {})),
            events=dict(data.get("events", {})),
            attribution=[str(item) for item in data.get("attribution", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "title": self.title,
            "version": self.version,
            "rules_version": self.rules_version,
            "start_zone_id": self.start_zone_id,
            "zones": self.zones,
            "outline": self.outline,
            "encounters": self.encounters,
            "rewards": self.rewards,
            "events": self.events,
            "attribution": self.attribution,
        }


class CampaignPackLoader:
    def load(self, path: str | Path) -> CampaignPackDefinition:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("campaign pack must be a JSON object")
        return CampaignPackDefinition.from_dict(data)


class CampaignPackValidator:
    def __init__(
        self,
        *,
        compendium: Compendium | None = None,
        rule_validator: RuleDataValidator | None = None,
    ):
        self.compendium = compendium
        self.rule_validator = rule_validator or RuleDataValidator()
        self.schema_registry: SchemaRegistry = self.rule_validator.schema_registry

    def validate(self, pack: CampaignPackDefinition) -> ValidationReport:
        report = ValidationReport()
        report.extend(self.schema_registry.validate("campaign_pack", pack.to_dict()))
        if report.errors:
            return report
        campaign_id_error = campaign_id_validation_error(pack.campaign_id)
        if campaign_id_error is not None:
            report.errors.append(campaign_id_error)
        if not pack.title:
            report.errors.append("title is required")
        if pack.start_zone_id not in pack.zones:
            report.errors.append("start_zone_id must reference an existing zone")
        if not pack.attribution:
            report.errors.append("campaign pack attribution is required")
        elif not any("SRD" in line or "CC-BY-4.0" in line for line in pack.attribution):
            report.errors.append("campaign pack attribution must include SRD/CC-BY notice")

        self._validate_outline(pack, report)
        self._validate_zone_graph(pack, report)
        self._validate_tactical_graphs(pack, report)
        self._validate_encounters(pack, report)
        self._validate_rewards(pack, report)
        self._validate_events(pack, report)
        return report

    def _validate_outline(
        self,
        pack: CampaignPackDefinition,
        report: ValidationReport,
    ) -> None:
        outline = pack.outline
        if not isinstance(outline, dict) or not outline:
            report.errors.append("campaign outline is required")
            return
        mainline = outline.get("mainline")
        if not isinstance(mainline, str) or not mainline.strip():
            report.errors.append("campaign outline mainline is required")
        for key in ("chapters", "npcs", "objectives", "endings"):
            value = outline.get(key)
            if not isinstance(value, list) or not value:
                report.errors.append(f"campaign outline {key} must be a non-empty list")

    def _validate_zone_graph(
        self,
        pack: CampaignPackDefinition,
        report: ValidationReport,
    ) -> None:
        for zone_id, zone in pack.zones.items():
            if "name" not in zone:
                report.errors.append(f"zone {zone_id}: name is required")
            edges = zone.get("edges", [])
            if not isinstance(edges, list):
                report.errors.append(f"zone {zone_id}: edges must be a list")
                continue
            for target in edges:
                if target not in pack.zones:
                    report.errors.append(f"zone {zone_id}: edge references unknown zone {target}")
        if pack.start_zone_id in pack.zones:
            seen = self._reachable_zones(pack)
            missing = sorted(set(pack.zones) - seen)
            if missing:
                report.errors.append(f"zone graph is not connected: {missing}")

    def _validate_tactical_graphs(
        self,
        pack: CampaignPackDefinition,
        report: ValidationReport,
    ) -> None:
        for zone_id, zone in pack.zones.items():
            graph_data = zone.get("tactical_graph")
            if graph_data is None:
                continue
            try:
                graph = TacticalGraph.from_dict(graph_data)
            except TypeError as exc:
                report.errors.append(f"zone {zone_id}: invalid tactical_graph: {exc}")
                continue
            if not graph.nodes:
                report.errors.append(f"zone {zone_id}: tactical_graph must contain nodes")
            for edge in graph.edges:
                if edge.source not in graph.nodes or edge.target not in graph.nodes:
                    report.errors.append(
                        f"zone {zone_id}: edge {edge.source}->{edge.target} references unknown node"
                    )
                if edge.distance_ft <= 0:
                    report.errors.append(f"zone {zone_id}: edge distance must be positive")
            if graph.nodes:
                start = next(iter(graph.nodes))
                reachable = graph.reachable(start, 10_000)
                if set(graph.nodes) - reachable:
                    report.errors.append(f"zone {zone_id}: tactical_graph is not connected")

    def _validate_encounters(
        self,
        pack: CampaignPackDefinition,
        report: ValidationReport,
    ) -> None:
        for zone_id, zone in pack.zones.items():
            encounter_id = zone.get("encounter_id")
            if encounter_id is not None and encounter_id not in pack.encounters:
                report.errors.append(f"zone {zone_id}: unknown encounter_id {encounter_id}")
        for encounter_id, encounter in pack.encounters.items():
            monsters = encounter.get("monsters", [])
            if not isinstance(monsters, list) or not monsters:
                report.errors.append(f"encounter {encounter_id}: monsters must be a non-empty list")
            total_cr = cr_fraction(0)
            total_xp = 0
            for index, monster in enumerate(monsters):
                if not isinstance(monster, dict):
                    report.errors.append(
                        f"encounter {encounter_id}: monster {index} must be object"
                    )
                    continue
                monster_id = str(monster.get("monster_id", ""))
                monster_definition = (
                    self.compendium.monsters.get(monster_id)
                    if self.compendium is not None
                    else None
                )
                if self.compendium is not None and monster_definition is None:
                    report.errors.append(
                        f"encounter {encounter_id}: unknown monster_id {monster_id}"
                    )
                count = int(monster.get("count", 1))
                if count <= 0:
                    report.errors.append(
                        f"encounter {encounter_id}: monster count must be positive"
                    )
                raw_cr = monster.get("cr")
                if raw_cr is None:
                    raw_cr = monster_definition.cr if monster_definition is not None else 0
                cr = cr_fraction(raw_cr)
                total_cr += cr * max(count, 0)
                try:
                    xp = self._monster_xp(monster, cr)
                except (TypeError, ValueError) as exc:
                    report.errors.append(
                        f"encounter {encounter_id}: invalid monster XP budget: {exc}"
                    )
                    xp = 0
                total_xp += xp * max(count, 0)
                for action_id in monster.get("actions", []):
                    if self.compendium is not None and action_id not in self.compendium.actions:
                        report.errors.append(
                            f"encounter {encounter_id}: unknown monster action {action_id}"
                        )
            budget = self._encounter_budget(encounter_id, encounter, report)
            if budget is not None:
                if total_xp > budget.max_xp:
                    report.errors.append(
                        f"encounter {encounter_id}: total XP {total_xp} "
                        f"exceeds XP budget {budget.max_xp}"
                    )
            else:
                max_cr = self._encounter_max_cr(encounter_id, encounter, total_cr, report)
                if total_cr > max_cr:
                    report.errors.append(
                        f"encounter {encounter_id}: total CR {float(total_cr):g} "
                        f"exceeds max_total_cr {float(max_cr):g}"
                    )
            reward_id = encounter.get("reward_id")
            if reward_id is not None and reward_id not in pack.rewards:
                report.errors.append(f"encounter {encounter_id}: unknown reward_id {reward_id}")

    def _validate_rewards(
        self,
        pack: CampaignPackDefinition,
        report: ValidationReport,
    ) -> None:
        for reward_id, reward in pack.rewards.items():
            for field_name in ("gold", "experience"):
                if field_name not in reward:
                    continue
                try:
                    amount = int(reward[field_name])
                except (TypeError, ValueError):
                    report.errors.append(f"reward {reward_id}: {field_name} must be an integer")
                    continue
                if amount < 0:
                    report.errors.append(f"reward {reward_id}: {field_name} cannot be negative")
            items = reward.get("items", [])
            if not isinstance(items, list):
                report.errors.append(f"reward {reward_id}: items must be a list")
                continue
            for index, item in enumerate(items):
                item_id: str
                quantity = 1
                if isinstance(item, str):
                    item_id = item
                elif isinstance(item, dict):
                    item_id = str(item.get("item_id", ""))
                    try:
                        quantity = int(item.get("quantity", 1))
                    except (TypeError, ValueError):
                        report.errors.append(
                            f"reward {reward_id}: item {index} quantity must be an integer"
                        )
                        quantity = 0
                else:
                    report.errors.append(
                        f"reward {reward_id}: item {index} must be string or object"
                    )
                    continue
                if not item_id:
                    report.errors.append(f"reward {reward_id}: item {index} requires item_id")
                    continue
                if quantity <= 0:
                    report.errors.append(
                        f"reward {reward_id}: item {item_id} quantity must be positive"
                    )
                if self.compendium is not None and item_id not in self.compendium.items:
                    report.errors.append(f"reward {reward_id}: unknown reward item {item_id}")

    def _encounter_max_cr(
        self,
        encounter_id: str,
        encounter: dict[str, Any],
        total_cr: Fraction,
        report: ValidationReport,
    ) -> Fraction:
        try:
            return cr_fraction(encounter.get("max_total_cr", total_cr))
        except (TypeError, ValueError) as exc:
            report.errors.append(f"encounter {encounter_id}: invalid max_total_cr: {exc}")
            return total_cr

    def _encounter_budget(
        self,
        encounter_id: str,
        encounter: dict[str, Any],
        report: ValidationReport,
    ) -> EncounterBudget | None:
        try:
            return budget_from_encounter(encounter)
        except (TypeError, ValueError) as exc:
            report.errors.append(f"encounter {encounter_id}: invalid XP budget: {exc}")
            return None

    @staticmethod
    def _monster_xp(monster: dict[str, Any], cr: Fraction) -> int:
        raw_xp = monster.get("xp")
        if raw_xp is not None:
            xp = int(raw_xp)
            if xp < 0:
                raise ValueError("xp cannot be negative")
            return xp
        return xp_for_cr(cr)

    def _validate_events(
        self,
        pack: CampaignPackDefinition,
        report: ValidationReport,
    ) -> None:
        for zone_id, zone in pack.zones.items():
            for event_id in zone.get("event_ids", []):
                if event_id not in pack.events and (
                    self.compendium is None or event_id not in self.compendium.events
                ):
                    report.errors.append(f"zone {zone_id}: unknown event_id {event_id}")
        for event_id, event_data in pack.events.items():
            event_report = self.rule_validator.validate_event(event_data)
            for error in event_report.errors:
                report.errors.append(f"event {event_id}: {error}")

    def _reachable_zones(self, pack: CampaignPackDefinition) -> set[str]:
        queue: deque[str] = deque([pack.start_zone_id])
        seen = {pack.start_zone_id}
        while queue:
            zone_id = queue.popleft()
            for neighbor in pack.zones.get(zone_id, {}).get("edges", []):
                if neighbor not in seen and neighbor in pack.zones:
                    seen.add(neighbor)
                    queue.append(neighbor)
        return seen

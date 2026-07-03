from __future__ import annotations

import re
from dataclasses import dataclass

from .campaign_pack import CampaignPackDefinition, CampaignPackValidator

TITLE_RE = re.compile(r"^(?:title|标题)\s*[:=：]?\s*(?P<title>.+)$", re.I)
ZONE_NAME_RE = re.compile(
    r"^(?:zone|区域)\s+(?P<zone_id>[\w.-]+)\s+(?:name|名称)\s*[:=：]?\s*(?P<name>.+)$",
    re.I,
)
ADD_ZONE_RE = re.compile(
    r"^(?:add zone|新增区域)\s+(?P<zone_id>[\w.-]+)\s+"
    r"(?:name|名称)\s*[:=：]?\s*(?P<name>.+?)\s+"
    r"(?:connect(?:ed)? to|连接)\s+(?P<target_id>[\w.-]+)$",
    re.I,
)
CONNECT_RE = re.compile(
    r"^(?:connect|连接)\s+(?P<left>[\w.-]+)\s+(?P<right>[\w.-]+)$",
    re.I,
)
ZONE_EVENT_RE = re.compile(
    r"^(?:zone|区域)\s+(?P<zone_id>[\w.-]+)\s+(?:event|事件)\s+(?P<event_id>[\w.-]+)$",
    re.I,
)


@dataclass
class CampaignEditResult:
    accepted: bool
    pack: CampaignPackDefinition | None = None
    errors: list[str] | None = None
    applied: list[str] | None = None


def apply_natural_language_campaign_edit(
    pack: CampaignPackDefinition,
    text: str,
    *,
    validator: CampaignPackValidator,
) -> CampaignEditResult:
    edited = CampaignPackDefinition.from_dict(pack.to_dict())
    applied: list[str] = []
    errors: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _apply_title(edited, line, applied):
            continue
        if _apply_zone_name(edited, line, applied):
            continue
        if _apply_add_zone(edited, line, applied):
            continue
        if _apply_connect(edited, line, applied):
            continue
        if _apply_zone_event(edited, line, applied):
            continue
        errors.append(f"无法解析修改指令：{line}")

    if not applied and not errors:
        errors.append("没有可应用的修改。")
    if errors:
        return CampaignEditResult(accepted=False, errors=errors, applied=applied)

    report = validator.validate(edited)
    if not report.ok:
        return CampaignEditResult(accepted=False, errors=report.errors, applied=applied)
    return CampaignEditResult(accepted=True, pack=edited, errors=[], applied=applied)


def _apply_title(pack: CampaignPackDefinition, line: str, applied: list[str]) -> bool:
    match = TITLE_RE.match(line)
    if match is None:
        return False
    title = match.group("title").strip()
    if title:
        pack.title = title
        applied.append("title")
    return True


def _apply_zone_name(pack: CampaignPackDefinition, line: str, applied: list[str]) -> bool:
    match = ZONE_NAME_RE.match(line)
    if match is None:
        return False
    zone_id = match.group("zone_id")
    pack.zones.setdefault(zone_id, {"edges": []})["name"] = match.group("name").strip()
    applied.append(f"zone_name:{zone_id}")
    return True


def _apply_add_zone(pack: CampaignPackDefinition, line: str, applied: list[str]) -> bool:
    match = ADD_ZONE_RE.match(line)
    if match is None:
        return False
    zone_id = match.group("zone_id")
    target_id = match.group("target_id")
    pack.zones.setdefault(zone_id, {"edges": []})
    pack.zones[zone_id]["name"] = match.group("name").strip()
    _connect(pack, zone_id, target_id)
    applied.append(f"add_zone:{zone_id}")
    return True


def _apply_connect(pack: CampaignPackDefinition, line: str, applied: list[str]) -> bool:
    match = CONNECT_RE.match(line)
    if match is None:
        return False
    left = match.group("left")
    right = match.group("right")
    pack.zones.setdefault(left, {"name": left, "edges": []})
    pack.zones.setdefault(right, {"name": right, "edges": []})
    _connect(pack, left, right)
    applied.append(f"connect:{left}:{right}")
    return True


def _apply_zone_event(pack: CampaignPackDefinition, line: str, applied: list[str]) -> bool:
    match = ZONE_EVENT_RE.match(line)
    if match is None:
        return False
    zone_id = match.group("zone_id")
    zone = pack.zones.setdefault(zone_id, {"name": zone_id, "edges": []})
    events = zone.setdefault("event_ids", [])
    event_id = match.group("event_id")
    if event_id not in events:
        events.append(event_id)
    applied.append(f"zone_event:{zone_id}:{event_id}")
    return True


def _connect(pack: CampaignPackDefinition, left: str, right: str) -> None:
    for source, target in ((left, right), (right, left)):
        edges = pack.zones.setdefault(source, {"name": source, "edges": []}).setdefault("edges", [])
        if target not in edges:
            edges.append(target)

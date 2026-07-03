from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from dnd_llm.core.models import GameState
from dnd_llm.core.positioning import PositionEdge, PositionNode, TacticalGraph

DYNAMIC_ZONES_FLAG = "dynamic_zones"
_ASCII_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class DynamicZoneExpansion:
    zone_id: str
    parent_zone_id: str
    zone: dict[str, Any]
    content_seed: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "parent_zone_id": self.parent_zone_id,
            "zone": self.zone,
            "content_seed": self.content_seed,
        }


def expand_dynamic_zone(
    state: GameState,
    *,
    parent_zone_id: str,
    theme: str,
    zone_id: str | None = None,
    name: str | None = None,
) -> DynamicZoneExpansion:
    theme = theme.strip()
    if not theme:
        raise ValueError("dynamic zone theme is required")
    if parent_zone_id not in state.world.zone_edges:
        raise ValueError(f"unknown parent zone: {parent_zone_id}")

    content_seed = _content_seed(state, parent_zone_id=parent_zone_id, theme=theme)
    resolved_zone_id = zone_id or _zone_id_for(theme, content_seed)
    if resolved_zone_id in state.world.zone_edges or resolved_zone_id in _dynamic_zones(state):
        raise ValueError(f"zone already exists: {resolved_zone_id}")

    zone = generate_dynamic_zone(
        zone_id=resolved_zone_id,
        parent_zone_id=parent_zone_id,
        theme=theme,
        content_seed=content_seed,
        name=name,
    )
    _dynamic_zones(state)[resolved_zone_id] = zone
    state.world.zone_edges.setdefault(parent_zone_id, [])
    if resolved_zone_id not in state.world.zone_edges[parent_zone_id]:
        state.world.zone_edges[parent_zone_id].append(resolved_zone_id)
    state.world.zone_edges[resolved_zone_id] = [parent_zone_id]
    return DynamicZoneExpansion(
        zone_id=resolved_zone_id,
        parent_zone_id=parent_zone_id,
        zone=zone,
        content_seed=content_seed,
    )


def generate_dynamic_zone(
    *,
    zone_id: str,
    parent_zone_id: str,
    theme: str,
    content_seed: str,
    name: str | None = None,
) -> dict[str, Any]:
    display_name = (name or theme).strip()
    tactical_graph = dynamic_tactical_graph(zone_id=zone_id, content_seed=content_seed)
    return {
        "name": display_name,
        "edges": [parent_zone_id],
        "event_ids": [],
        "dynamic": True,
        "content_seed": content_seed,
        "outline": {
            "theme": theme,
            "hook": f"{display_name}出现了新的线索。",
            "goal": "探索该区域并确认它与当前任务的关系。",
        },
        "tactical_graph": tactical_graph.to_dict(),
    }


def dynamic_tactical_graph(*, zone_id: str, content_seed: str) -> TacticalGraph:
    prefix = _node_prefix(zone_id)
    has_cover = _seed_int(content_seed, "cover") % 2 == 0
    side_distance = 10 + (_seed_int(content_seed, "side-distance") % 3) * 5
    back_distance = 15 + (_seed_int(content_seed, "back-distance") % 3) * 5
    center_name = "中心地带"
    side_name = "侧翼掩护" if has_cover else "侧翼通路"
    back_name = "深处"
    return TacticalGraph(
        nodes={
            f"{prefix}_entry": PositionNode(f"{prefix}_entry", "入口", tags=["entry"]),
            f"{prefix}_center": PositionNode(f"{prefix}_center", center_name),
            f"{prefix}_side": PositionNode(
                f"{prefix}_side",
                side_name,
                tags=["cover"] if has_cover else ["side"],
                default_cover="half" if has_cover else "none",
            ),
            f"{prefix}_back": PositionNode(f"{prefix}_back", back_name, tags=["rear"]),
        },
        edges=[
            PositionEdge(f"{prefix}_entry", f"{prefix}_center", 15),
            PositionEdge(
                f"{prefix}_center",
                f"{prefix}_side",
                side_distance,
                cover="half" if has_cover else "none",
            ),
            PositionEdge(f"{prefix}_center", f"{prefix}_back", back_distance),
            PositionEdge(
                f"{prefix}_side",
                f"{prefix}_back",
                15,
                line_of_sight=not has_cover,
                cover="half" if has_cover else "none",
            ),
        ],
    )


def dynamic_zones_for_state(state: GameState) -> dict[str, dict[str, Any]]:
    return dict(_dynamic_zones(state))


def _dynamic_zones(state: GameState) -> dict[str, dict[str, Any]]:
    zones = state.world.flags.setdefault(DYNAMIC_ZONES_FLAG, {})
    if not isinstance(zones, dict):
        raise ValueError("dynamic_zones flag must be an object")
    return zones


def _content_seed(state: GameState, *, parent_zone_id: str, theme: str) -> str:
    raw = "|".join(
        [
            state.campaign_id,
            str(state.rng_seed),
            str(state.event_counter),
            parent_zone_id,
            theme,
        ]
    )
    return hashlib.blake2b(raw.encode(), digest_size=8).hexdigest()


def _zone_id_for(theme: str, content_seed: str) -> str:
    normalized = theme.casefold()
    tokens = _ASCII_TOKEN_RE.findall(normalized)
    slug = "_".join(tokens[:3]) if tokens else "zone"
    return f"dyn_{slug}_{content_seed[:8]}"


def _node_prefix(zone_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", zone_id)


def _seed_int(seed: str, label: str) -> int:
    digest = hashlib.blake2b(f"{seed}:{label}".encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big")

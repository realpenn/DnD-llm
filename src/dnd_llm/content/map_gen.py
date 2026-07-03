from __future__ import annotations

from ..core.positioning import PositionEdge, PositionNode, TacticalGraph


def starter_zone_graph() -> dict[str, dict[str, object]]:
    return {
        "start": {
            "name": "营地",
            "edges": ["ruins"],
            "event_ids": [],
        },
        "ruins": {
            "name": "遗迹入口",
            "edges": ["start", "vault"],
            "event_ids": [],
        },
        "vault": {
            "name": "塌陷宝库",
            "edges": ["ruins"],
            "event_ids": [],
        },
    }


def starter_tactical_graph() -> TacticalGraph:
    return TacticalGraph(
        nodes={
            "front": PositionNode("front", "前线", tags=["entry"]),
            "cover": PositionNode("cover", "碎墙掩体", tags=["cover"], default_cover="half"),
            "back": PositionNode("back", "后排", tags=["rear"]),
        },
        edges=[
            PositionEdge("front", "cover", 15, cover="half"),
            PositionEdge("cover", "back", 15, cover="half"),
            PositionEdge("front", "back", 30, line_of_sight=True),
        ],
    )

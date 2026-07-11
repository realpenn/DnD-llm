from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PositionNode:
    node_id: str
    name: str
    tags: list[str] = field(default_factory=list)
    capacity: int | None = None
    default_cover: str = "none"
    terrain: str = "normal"

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "tags": self.tags,
            "capacity": self.capacity,
            "default_cover": self.default_cover,
            "terrain": self.terrain,
        }


@dataclass
class PositionEdge:
    source: str
    target: str
    distance_ft: int
    movement_cost: int | None = None
    line_of_sight: bool = True
    cover: str = "none"
    difficult_terrain: bool = False

    def cost(self) -> int:
        base_cost = self.movement_cost if self.movement_cost is not None else self.distance_ft
        return base_cost * 2 if self.difficult_terrain else base_cost

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "distance_ft": self.distance_ft,
            "movement_cost": self.movement_cost,
            "line_of_sight": self.line_of_sight,
            "cover": self.cover,
            "difficult_terrain": self.difficult_terrain,
        }


@dataclass
class TacticalGraph:
    nodes: dict[str, PositionNode] = field(default_factory=dict)
    edges: list[PositionEdge] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TacticalGraph:
        return cls(
            nodes={key: PositionNode(**value) for key, value in data.get("nodes", {}).items()},
            edges=[PositionEdge(**edge) for edge in data.get("edges", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": {key: node.to_dict() for key, node in self.nodes.items()},
            "edges": [edge.to_dict() for edge in self.edges],
        }

    def neighbors(self, node_id: str) -> list[tuple[str, PositionEdge]]:
        result: list[tuple[str, PositionEdge]] = []
        for edge in self.edges:
            if edge.source == node_id:
                result.append((edge.target, edge))
            elif edge.target == node_id:
                result.append((edge.source, edge))
        return result

    def shortest_distance(
        self, start: str, goal: str, *, movement_cost: bool = False
    ) -> int | None:
        if start == goal:
            return 0
        queue: list[tuple[int, str]] = [(0, start)]
        seen: dict[str, int] = {start: 0}
        while queue:
            distance, node = heapq.heappop(queue)
            if node == goal:
                return distance
            if distance > seen[node]:
                continue
            for neighbor, edge in self.neighbors(node):
                step = edge.cost() if movement_cost else edge.distance_ft
                new_distance = distance + step
                if new_distance < seen.get(neighbor, 10**9):
                    seen[neighbor] = new_distance
                    heapq.heappush(queue, (new_distance, neighbor))
        return None

    def has_line_of_sight(self, start: str, goal: str) -> bool:
        if start == goal:
            return True
        queue = [start]
        seen = {start}
        while queue:
            node = queue.pop(0)
            for neighbor, edge in self.neighbors(node):
                if not edge.line_of_sight or neighbor in seen:
                    continue
                if neighbor == goal:
                    return True
                seen.add(neighbor)
                queue.append(neighbor)
        return False

    def cover_between(self, start: str, goal: str) -> str:
        path = self._shortest_path_edges(start, goal)
        if path is None:
            return "total"
        cover_rank = {"none": 0, "half": 1, "three_quarters": 2, "total": 3}
        return max(
            (edge.cover for edge in path),
            key=lambda cover: cover_rank.get(cover, 0),
            default="none",
        )

    def _shortest_path_edges(self, start: str, goal: str) -> list[PositionEdge] | None:
        if start == goal:
            return []
        queue: list[tuple[int, str]] = [(0, start)]
        distances: dict[str, int] = {start: 0}
        previous: dict[str, tuple[str, PositionEdge]] = {}
        while queue:
            distance, node = heapq.heappop(queue)
            if distance > distances[node]:
                continue
            if node == goal:
                path: list[PositionEdge] = []
                current = goal
                while current != start:
                    parent, edge = previous[current]
                    path.append(edge)
                    current = parent
                path.reverse()
                return path
            for neighbor, edge in self.neighbors(node):
                new_distance = distance + edge.distance_ft
                if new_distance < distances.get(neighbor, 10**9):
                    distances[neighbor] = new_distance
                    previous[neighbor] = (node, edge)
                    heapq.heappush(queue, (new_distance, neighbor))
        return None

    def reachable(self, start: str, movement_budget: int) -> set[str]:
        result = {start}
        queue: list[tuple[int, str]] = [(0, start)]
        seen: dict[str, int] = {start: 0}
        while queue:
            cost, node = heapq.heappop(queue)
            for neighbor, edge in self.neighbors(node):
                new_cost = cost + edge.cost()
                if new_cost <= movement_budget and new_cost < seen.get(neighbor, 10**9):
                    result.add(neighbor)
                    seen[neighbor] = new_cost
                    heapq.heappush(queue, (new_cost, neighbor))
        return result

    def area_nodes(self, center: str, radius_ft: int) -> set[str]:
        return {
            node_id
            for node_id in self.nodes
            if (distance := self.shortest_distance(center, node_id)) is not None
            and distance <= radius_ft
        }

    def opportunity_attack_triggers(
        self,
        *,
        actor_from: str,
        actor_to: str,
        enemy_positions: dict[str, str],
        enemy_reach_ft: dict[str, int],
    ) -> list[str]:
        triggers: list[str] = []
        for enemy_id, enemy_node in enemy_positions.items():
            before = self.shortest_distance(actor_from, enemy_node)
            after = self.shortest_distance(actor_to, enemy_node)
            reach = enemy_reach_ft.get(enemy_id, 5)
            if before is not None and before <= reach and (after is None or after > reach):
                triggers.append(enemy_id)
        return triggers

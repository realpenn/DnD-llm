from __future__ import annotations

import pytest

from dnd_llm.core.models import Character, Combatant, Encounter, GameState
from dnd_llm.core.positioning import PositionEdge, PositionNode, TacticalGraph


@pytest.fixture
def make_state():
    return _make_state


def _make_state() -> GameState:
    pc = Character(
        id="pc1",
        name="Penn",
        abilities={"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 8},
        class_levels={"fighter": 1},
        proficiency_bonus=2,
        hp_current=10,
        hp_max=12,
        hit_dice={"d10": 1},
        armor_class=16,
        actions=["srd.shortsword_attack", "srd.cure_wounds"],
        spell_slots={"1": 1},
        zone_id="start",
    )
    ally = Character(
        id="pc2",
        name="Ally",
        abilities={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
        class_levels={"cleric": 1},
        proficiency_bonus=2,
        hp_current=4,
        hp_max=8,
        armor_class=14,
        actions=["srd.cure_wounds"],
        zone_id="start",
    )
    graph = TacticalGraph(
        nodes={
            "front": PositionNode("front", "Front"),
            "cover": PositionNode("cover", "Cover"),
            "back": PositionNode("back", "Back"),
        },
        edges=[
            PositionEdge("front", "cover", 5, cover="half"),
            PositionEdge("cover", "back", 30),
        ],
    )
    encounter = Encounter(
        id="enc1",
        tactical_graph=graph.to_dict(),
        combatants={
            "pc1": Combatant(
                id="pc1",
                entity_id="pc1",
                name="Penn",
                side="party",
                hp_current=10,
                hp_max=12,
                armor_class=16,
                position_node_id="front",
            ),
            "pc2": Combatant(
                id="pc2",
                entity_id="pc2",
                name="Ally",
                side="party",
                hp_current=4,
                hp_max=8,
                armor_class=14,
                position_node_id="front",
            ),
            "goblin1": Combatant(
                id="goblin1",
                entity_id="goblin1",
                name="Goblin",
                side="monsters",
                hp_current=7,
                hp_max=7,
                armor_class=12,
                position_node_id="cover",
            ),
        },
    )
    return GameState(
        campaign_id="test",
        rng_seed=20260629,
        characters={"pc1": pc, "pc2": ally},
        encounter=encounter,
    )

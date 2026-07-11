from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

AbilityScores = dict[str, int]


def _clean(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _clean(val) for key, val in asdict(value).items()}  # type: ignore[arg-type]
    if isinstance(value, dict):
        return {str(key): _clean(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    return value


@dataclass
class Character:
    id: str
    name: str
    abilities: AbilityScores
    class_levels: dict[str, int]
    proficiency_bonus: int
    hp_current: int
    hp_max: int
    armor_class: int
    subclasses: dict[str, str] = field(default_factory=dict)
    feature_choices: dict[str, str] = field(default_factory=dict)
    size: str = "medium"
    speed_ft: int = 30
    temp_hp: int = 0
    temp_hp_source_effect_id: str | None = None
    hit_dice: dict[str, int] = field(default_factory=dict)
    skill_proficiencies: list[str] = field(default_factory=list)
    skill_expertise: list[str] = field(default_factory=list)
    tool_proficiencies: list[str] = field(default_factory=list)
    saving_throw_proficiencies: list[str] = field(default_factory=list)
    equipment: list[str] = field(default_factory=list)
    inventory: dict[str, int] = field(default_factory=dict)
    resources: dict[str, int] = field(default_factory=dict)
    spell_slots: dict[str, int] = field(default_factory=dict)
    spell_slots_max: dict[str, int] = field(default_factory=dict)
    pact_spell_slots: dict[str, int] = field(default_factory=dict)
    pact_spell_slots_max: dict[str, int] = field(default_factory=dict)
    known_spells: list[str] = field(default_factory=list)
    prepared_spells: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    feats: list[str] = field(default_factory=list)
    status_effects: list[dict[str, Any]] = field(default_factory=list)
    zone_id: str | None = None
    gold: int = 0
    experience: int = 0
    death_save_successes: int = 0
    death_save_failures: int = 0
    stable: bool = False
    dead: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _clean(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Character:
        payload = dict(data)
        payload.setdefault("resources", {})
        payload.setdefault("subclasses", {})
        payload.setdefault("feature_choices", {})
        payload.setdefault("skill_expertise", [])
        payload.setdefault("languages", [])
        if (
            "pact_spell_slots" not in payload
            and int(payload.get("class_levels", {}).get("warlock", 0)) > 0
        ):
            from .rules.spell_slots import (
                spell_slot_maxima_for_class_levels,
                warlock_pact_slot_maxima_for_class_levels,
            )

            class_levels = dict(payload.get("class_levels", {}))
            pact_maxima = warlock_pact_slot_maxima_for_class_levels(class_levels)
            regular_maxima = spell_slot_maxima_for_class_levels(class_levels)
            if regular_maxima:
                payload["pact_spell_slots"] = dict(pact_maxima)
                payload["pact_spell_slots_max"] = dict(pact_maxima)
            else:
                payload["pact_spell_slots"] = dict(payload.get("spell_slots", pact_maxima))
                payload["pact_spell_slots_max"] = dict(payload.get("spell_slots_max", pact_maxima))
                payload["spell_slots"] = {}
                payload["spell_slots_max"] = {}
        payload.setdefault("pact_spell_slots", {})
        payload.setdefault("pact_spell_slots_max", {})
        return cls(**payload)


@dataclass
class Monster:
    id: str
    name: str
    abilities: AbilityScores
    hp_current: int
    hp_max: int
    armor_class: int
    size: str = "medium"
    speed_ft: int = 30
    creature_type: str = "humanoid"
    proficiency_bonus: int = 2
    temp_hp: int = 0
    temp_hp_source_effect_id: str | None = None
    actions: list[str] = field(default_factory=list)
    status_effects: list[dict[str, Any]] = field(default_factory=list)
    resistances: list[str] = field(default_factory=list)
    immunities: list[str] = field(default_factory=list)
    vulnerabilities: list[str] = field(default_factory=list)
    condition_immunities: list[str] = field(default_factory=list)
    traits: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _clean(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Monster:
        return cls(**data)


@dataclass
class Combatant:
    id: str
    entity_id: str
    name: str
    side: str
    hp_current: int
    hp_max: int
    armor_class: int
    size: str = "medium"
    speed_ft: int = 30
    creature_type: str = "humanoid"
    abilities: AbilityScores = field(default_factory=dict)
    temp_hp: int = 0
    temp_hp_source_effect_id: str | None = None
    position_node_id: str | None = None
    reach_ft: int = 5
    status_effects: list[dict[str, Any]] = field(default_factory=list)
    resistances: list[str] = field(default_factory=list)
    immunities: list[str] = field(default_factory=list)
    vulnerabilities: list[str] = field(default_factory=list)
    condition_immunities: list[str] = field(default_factory=list)
    traits: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    death_save_successes: int = 0
    death_save_failures: int = 0
    stable: bool = False
    dead: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _clean(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Combatant:
        return cls(**data)


@dataclass
class Encounter:
    id: str
    combatants: dict[str, Combatant] = field(default_factory=dict)
    initiative_order: list[str] = field(default_factory=list)
    turn_index: int = 0
    round_number: int = 1
    tactical_graph: dict[str, Any] | None = None
    action_budgets: dict[str, dict[str, int]] = field(default_factory=dict)
    pending_reactions: dict[str, dict[str, Any]] = field(default_factory=dict)
    status_effect_baselines: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    ammunition_inventory_baselines: dict[str, dict[str, int]] = field(default_factory=dict)
    turn_started_at: dict[str, int] = field(default_factory=dict)

    @property
    def current_combatant_id(self) -> str | None:
        if not self.initiative_order:
            return None
        return self.initiative_order[self.turn_index % len(self.initiative_order)]

    def to_dict(self) -> dict[str, Any]:
        return _clean(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Encounter:
        combatants = {
            key: Combatant.from_dict(value) for key, value in data.get("combatants", {}).items()
        }
        payload = dict(data)
        payload["combatants"] = combatants
        if "status_effect_baselines" not in data:
            payload["status_effect_baselines"] = {
                combatant_id: [dict(effect) for effect in combatant.status_effects]
                for combatant_id, combatant in combatants.items()
            }
        return cls(**payload)


@dataclass
class WorldState:
    current_zone_id: str = "start"
    flags: dict[str, Any] = field(default_factory=dict)
    active_effects: list[dict[str, Any]] = field(default_factory=list)
    time_index: int = 0
    zone_edges: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _clean(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorldState:
        return cls(**data)


@dataclass
class SessionConfig:
    pvp_enabled: bool = False
    friendly_fire: str = "confirm"
    hp_display_strategy: str = "fuzzy"

    def to_dict(self) -> dict[str, Any]:
        return _clean(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionConfig:
        return cls(**data)


@dataclass
class MemoryFragment:
    id: str
    text: str
    embedding: dict[str, float]
    tags: list[str] = field(default_factory=list)
    visibility: str = "public"
    source_event_id: str | None = None
    created_at_event_counter: int = 0

    def to_dict(self) -> dict[str, Any]:
        return _clean(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryFragment:
        payload = dict(data)
        payload["embedding"] = {
            str(key): float(value) for key, value in payload.get("embedding", {}).items()
        }
        payload["tags"] = [str(tag) for tag in payload.get("tags", [])]
        return cls(**payload)


@dataclass
class GameState:
    campaign_id: str
    rng_seed: int
    schema_version: str = "1.0"
    rules_data_version: str = "srd-5.2.1"
    campaign_pack_version: str = "dev"
    roll_counter: int = 0
    event_counter: int = 0
    session_mode: str = "exploration"
    summary: str = ""
    characters: dict[str, Character] = field(default_factory=dict)
    monsters: dict[str, Monster] = field(default_factory=dict)
    encounter: Encounter | None = None
    world: WorldState = field(default_factory=WorldState)
    config: SessionConfig = field(default_factory=SessionConfig)
    memory_fragments: list[MemoryFragment] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _clean(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GameState:
        payload = dict(data)
        payload["characters"] = {
            key: Character.from_dict(value) for key, value in data.get("characters", {}).items()
        }
        payload["monsters"] = {
            key: Monster.from_dict(value) for key, value in data.get("monsters", {}).items()
        }
        payload["encounter"] = (
            Encounter.from_dict(data["encounter"]) if data.get("encounter") is not None else None
        )
        payload["world"] = WorldState.from_dict(data.get("world", {}))
        payload["config"] = SessionConfig.from_dict(data.get("config", {}))
        payload["memory_fragments"] = [
            MemoryFragment.from_dict(item) for item in data.get("memory_fragments", [])
        ]
        return cls(**payload)

    def get_combatant(self, combatant_id: str) -> Combatant:
        if self.encounter is None or combatant_id not in self.encounter.combatants:
            raise KeyError(f"unknown combatant: {combatant_id}")
        return self.encounter.combatants[combatant_id]

    def get_character(self, character_id: str) -> Character:
        if character_id not in self.characters:
            raise KeyError(f"unknown character: {character_id}")
        return self.characters[character_id]

    def entity_for_actor(self, actor_id: str) -> Character | Monster | Combatant:
        if self.encounter is not None and actor_id in self.encounter.combatants:
            return self.encounter.combatants[actor_id]
        if actor_id in self.characters:
            return self.characters[actor_id]
        if actor_id in self.monsters:
            return self.monsters[actor_id]
        raise KeyError(f"unknown actor: {actor_id}")

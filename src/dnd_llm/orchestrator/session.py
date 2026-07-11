from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..content.campaign_pack import CampaignPackDefinition
from ..content.dynamic import expand_dynamic_zone
from ..content.map_gen import starter_tactical_graph
from ..content.runtime import tactical_graph_for_state_zone
from ..core.compendium.loader import Compendium
from ..core.dice import RollService
from ..core.economy import EconomyTracker
from ..core.effect_lifecycle import EffectLifecycleResult, tick_effects
from ..core.memory import remember_fragment
from ..core.models import Character, Combatant, Encounter, GameState, Monster
from ..core.persistence import AuditLog
from ..core.positioning import TacticalGraph
from ..core.resolver import ActionResolver, PlayerActionDraft
from ..core.rules.class_features import (
    HEROIC_INSPIRATION_RESOURCE,
    champion_heroic_warrior_can_grant_inspiration,
    champion_survivor_heroic_rally_healing,
    class_feature_speed_bonus,
    has_monk_open_hand_feature,
)
from ..core.rules.conditions import effective_speed
from ..core.tools import EngineTools
from .queue import EventQueue, QueuedEvent
from .reactions import ReactionManager
from .router import ContextSlice, build_context_slice
from .tactics import MonsterTacticsLibrary
from .timeout import TimeoutController
from .turn import advance_turn as advance_encounter_turn
from .turn import roll_initiative

GENERATED_TACTICAL_GRAPHS_FLAG = "generated_tactical_graphs"
SESSION_IDEMPOTENCY_FLAG = "session_idempotency_results"
FLEET_STEP_ACTION_ID = "srd.fleet_step"
FLEET_STEP_CONDITION = "fleet_step_available"
TimeoutTakeoverPlanner = Callable[[str, int, str], PlayerActionDraft | None]
MonsterTurnPlanner = Callable[[str, int, str], PlayerActionDraft | None]


@dataclass
class SessionResult:
    accepted: bool
    payload: dict[str, Any]


def _serialize_session_result(result: object) -> object:
    if not isinstance(result, SessionResult):
        raise TypeError("session idempotency results must be SessionResult instances")
    return {"accepted": result.accepted, "payload": result.payload}


def _deserialize_session_result(value: object) -> object:
    if not isinstance(value, dict):
        raise TypeError("invalid persisted session result")
    payload = value.get("payload")
    if not isinstance(payload, dict):
        raise TypeError("invalid persisted session result payload")
    return SessionResult(accepted=bool(value.get("accepted", False)), payload=payload)


class GameSession:
    def __init__(
        self,
        state: GameState,
        compendium: Compendium,
        audit_log: AuditLog,
        *,
        tactics: MonsterTacticsLibrary | None = None,
        reactions: ReactionManager | None = None,
        timeout: TimeoutController | None = None,
        timeout_takeover_planner: TimeoutTakeoverPlanner | None = None,
        monster_turn_planner: MonsterTurnPlanner | None = None,
        campaign_pack: CampaignPackDefinition | None = None,
    ):
        self.state = state
        self.compendium = compendium
        self.audit_log = audit_log
        self.campaign_pack = campaign_pack
        self.roll_service = RollService(state)
        self.economy = EconomyTracker(
            state.encounter.action_budgets if state.encounter is not None else None
        )
        self.tools = EngineTools(state, compendium, audit_log, self.roll_service, self.economy)
        idempotency_results = state.world.flags.get(SESSION_IDEMPOTENCY_FLAG)
        if not isinstance(idempotency_results, dict):
            idempotency_results = {}
            state.world.flags[SESSION_IDEMPOTENCY_FLAG] = idempotency_results
        self.queue: EventQueue[SessionResult] = EventQueue(
            persistent_store=idempotency_results,
            serializer=_serialize_session_result,
            deserializer=_deserialize_session_result,
        )
        self.tactics = tactics or MonsterTacticsLibrary()
        self.reactions = reactions or ReactionManager()
        self.timeout = timeout or TimeoutController()
        self.timeout_takeover_planner = timeout_takeover_planner
        self.monster_turn_planner = monster_turn_planner
        self._current_time: int | None = None

    def set_current_time(self, now: int) -> None:
        self._current_time = now

    def _interaction_now(self) -> int:
        return self._current_time if self._current_time is not None else int(time.time())

    def context_for(self, actor_id: str | None, *, query: str = "") -> ContextSlice:
        return build_context_slice(
            self.state,
            actor_id=actor_id,
            actions=self.compendium.actions,
            query=query,
        )

    def remember(
        self,
        *,
        text: str,
        idempotency_key: str,
        tags: list[str] | None = None,
        visibility: str = "public",
    ) -> SessionResult | object:
        return self.queue.submit(
            QueuedEvent(
                idempotency_key=idempotency_key,
                payload={
                    "type": "remember",
                    "text": text,
                    "tags": tags or [],
                    "visibility": visibility,
                },
            ),
            self._handle_session_event,
        )

    def update_summary(
        self,
        *,
        summary: str,
        scene_notes: str,
        idempotency_key: str,
        model_id: str | None = None,
        prompt_version: str | None = None,
        model_usage: dict[str, int] | None = None,
    ) -> SessionResult | object:
        return self.queue.submit(
            QueuedEvent(
                idempotency_key=idempotency_key,
                payload={
                    "type": "update_summary",
                    "summary": summary,
                    "scene_notes": scene_notes,
                    "model_id": model_id,
                    "prompt_version": prompt_version,
                    "model_usage": model_usage or {},
                },
            ),
            self._handle_session_event,
        )

    def expand_dynamic_zone(
        self,
        *,
        parent_zone_id: str,
        theme: str,
        idempotency_key: str,
        zone_id: str | None = None,
        name: str | None = None,
    ) -> SessionResult | object:
        return self.queue.submit(
            QueuedEvent(
                idempotency_key=idempotency_key,
                payload={
                    "type": "expand_dynamic_zone",
                    "parent_zone_id": parent_zone_id,
                    "theme": theme,
                    "zone_id": zone_id,
                    "name": name,
                },
            ),
            self._handle_session_event,
        )

    def submit_player_action(
        self, draft: PlayerActionDraft, idempotency_key: str
    ) -> SessionResult | object:
        return self.queue.submit(
            QueuedEvent(idempotency_key=idempotency_key, payload=draft),
            self._handle_player_action,
        )

    def start_combat(
        self,
        *,
        encounter_id: str,
        combatants: dict[str, Combatant],
        tactical_graph: TacticalGraph | None = None,
        zone_id: str | None = None,
        idempotency_key: str,
    ) -> SessionResult | object:
        return self.queue.submit(
            QueuedEvent(
                idempotency_key=idempotency_key,
                payload={
                    "type": "start_combat",
                    "encounter_id": encounter_id,
                    "combatants": combatants,
                    "tactical_graph": tactical_graph,
                    "zone_id": zone_id,
                },
            ),
            self._handle_session_event,
        )

    def end_combat(self, idempotency_key: str) -> SessionResult | object:
        return self.queue.submit(
            QueuedEvent(idempotency_key=idempotency_key, payload={"type": "end_combat"}),
            self._handle_session_event,
        )

    def enter_cutscene(self, *, idempotency_key: str, reason: str = "") -> SessionResult | object:
        return self.queue.submit(
            QueuedEvent(
                idempotency_key=idempotency_key,
                payload={"type": "enter_cutscene", "reason": reason},
            ),
            self._handle_session_event,
        )

    def exit_cutscene(self, idempotency_key: str) -> SessionResult | object:
        return self.queue.submit(
            QueuedEvent(idempotency_key=idempotency_key, payload={"type": "exit_cutscene"}),
            self._handle_session_event,
        )

    def advance_turn(self, idempotency_key: str) -> SessionResult | object:
        return self.queue.submit(
            QueuedEvent(idempotency_key=idempotency_key, payload={"type": "advance_turn"}),
            self._handle_session_event,
        )

    def run_current_monster_turn(self, idempotency_key: str) -> SessionResult | object:
        return self.queue.submit(
            QueuedEvent(idempotency_key=idempotency_key, payload={"type": "monster_turn"}),
            self._handle_session_event,
        )

    def run_timeout_takeover(self, *, now: int, idempotency_key: str) -> SessionResult | object:
        return self.queue.submit(
            QueuedEvent(
                idempotency_key=idempotency_key,
                payload={"type": "timeout_takeover", "now": now},
            ),
            self._handle_session_event,
        )

    def resolve_reaction(
        self,
        *,
        reaction_id: str,
        accept: bool,
        now: int,
        idempotency_key: str,
    ) -> SessionResult | object:
        return self.queue.submit(
            QueuedEvent(
                idempotency_key=idempotency_key,
                payload={
                    "type": "resolve_reaction",
                    "reaction_id": reaction_id,
                    "accept": accept,
                    "now": now,
                },
            ),
            self._handle_session_event,
        )

    def expire_reactions(self, *, now: int, idempotency_key: str) -> SessionResult | object:
        return self.queue.submit(
            QueuedEvent(
                idempotency_key=idempotency_key,
                payload={"type": "expire_reactions", "now": now},
            ),
            self._handle_session_event,
        )

    def mark_current_turn_started(self, now: int) -> None:
        if self.state.encounter is None or self.state.encounter.current_combatant_id is None:
            return
        self.timeout.mark_turn_start(self.state.encounter.current_combatant_id, now)

    def current_turn_prompt(self, mentions: dict[str, str] | None = None) -> str | None:
        if self.state.encounter is None or self.state.encounter.current_combatant_id is None:
            return None
        combatant_id = self.state.encounter.current_combatant_id
        combatant = self.state.encounter.combatants[combatant_id]
        mention = (mentions or {}).get(combatant.entity_id) or (mentions or {}).get(combatant_id)
        display = mention or combatant.name
        return f"{display}，轮到你行动。"

    def _handle_player_action(self, event: QueuedEvent) -> SessionResult:
        draft = event.payload
        if not isinstance(draft, PlayerActionDraft):
            raise TypeError("payload must be PlayerActionDraft")
        if self.reactions.has_pending(self.state):
            pending_result = {
                "status": "rejected",
                "reason": "reaction pending",
                "pending_reactions": [
                    window.to_dict() for window in self.reactions.pending_windows(self.state)
                ],
            }
            self.audit_log.append(
                self.state,
                idempotency_key=f"{event.idempotency_key}:reaction_guard",
                player_text=draft.raw_text,
                player_intent=draft.__dict__,
                tool_name="orchestrator.reaction_guard",
                tool_args=draft.__dict__,
                tool_result=pending_result,
            )
            return SessionResult(accepted=False, payload=pending_result)
        if (
            self.state.encounter is not None
            and self.state.encounter.current_combatant_id is not None
            and draft.actor_id != self.state.encounter.current_combatant_id
        ):
            guard_result = {
                "status": "rejected",
                "reason": "not actor turn",
                "current_combatant_id": self.state.encounter.current_combatant_id,
            }
            self.audit_log.append(
                self.state,
                idempotency_key=f"{event.idempotency_key}:turn_guard",
                player_text=draft.raw_text,
                player_intent={
                    "actor_id": draft.actor_id,
                    "verb": draft.verb,
                    "targets": draft.target_ids,
                },
                tool_name="orchestrator.turn_guard",
                tool_args=draft.__dict__,
                tool_result=guard_result,
            )
            return SessionResult(accepted=False, payload=guard_result)
        resolver = ActionResolver(
            self.state,
            self.compendium.actions,
            self.compendium.items,
            self.economy,
        )
        decision = resolver.resolve(draft)
        self.audit_log.append(
            self.state,
            idempotency_key=f"{event.idempotency_key}:resolver",
            player_text=draft.raw_text,
            player_intent={
                "actor_id": draft.actor_id,
                "verb": draft.verb,
                "targets": draft.target_ids,
            },
            tool_name="resolver.resolve",
            tool_args=draft.__dict__,
            tool_result=decision.to_dict(),
        )
        if decision.status != "accepted" or decision.action_id is None:
            return SessionResult(accepted=False, payload=decision.to_dict())
        result = self._execute_resolved_draft(
            draft,
            decision.action_id,
            event.idempotency_key,
            allow_reactions=True,
        )
        if result.get("status") == "rejected":
            return SessionResult(accepted=False, payload=result)
        self._advance_after_action_if_ready(
            result,
            f"{event.idempotency_key}:advance",
            now=self._interaction_now(),
        )
        return SessionResult(accepted=True, payload=result)

    def _handle_session_event(self, event: QueuedEvent) -> SessionResult:
        payload = event.payload
        if not isinstance(payload, dict):
            raise TypeError("session event payload must be a dict")
        event_type = payload.get("type")
        if event_type == "remember":
            return self._handle_remember(event.idempotency_key, payload)
        if event_type == "update_summary":
            return self._handle_update_summary(event.idempotency_key, payload)
        if event_type == "expand_dynamic_zone":
            return self._handle_expand_dynamic_zone(event.idempotency_key, payload)
        if event_type == "start_combat":
            combatants = payload["combatants"]
            raw_tactical_graph = payload.get("tactical_graph")
            if raw_tactical_graph is not None and not isinstance(raw_tactical_graph, TacticalGraph):
                raise TypeError("invalid start_combat tactical_graph")
            if not isinstance(combatants, dict):
                raise TypeError("invalid start_combat payload")
            zone_id = _optional_text(payload.get("zone_id")) or self.state.world.current_zone_id
            tactical_graph, tactical_graph_source = self._resolve_tactical_graph_for_combat(
                raw_tactical_graph,
                zone_id=zone_id,
            )
            self.state.encounter = Encounter(
                id=str(payload["encounter_id"]),
                combatants=combatants,
                tactical_graph=tactical_graph.to_dict(),
            )
            self.state.session_mode = "combat"
            self.economy.use_backing(self.state.encounter.action_budgets)
            initiative_order = roll_initiative(self.state, self.audit_log)
            current = self.state.encounter.current_combatant_id
            if current is not None:
                self.economy.reset_turn_start(
                    current,
                    _effective_combatant_speed(
                        self.state,
                        self.state.encounter.combatants[current],
                    ),
                )
                self.timeout.mark_turn_start(current, self._interaction_now())
            result = {
                "encounter_id": self.state.encounter.id,
                "zone_id": zone_id,
                "tactical_graph_source": tactical_graph_source,
                "initiative_order": initiative_order,
                "current_combatant_id": current,
            }
            self.audit_log.append(
                self.state,
                idempotency_key=event.idempotency_key,
                tool_name="orchestrator.start_combat",
                tool_args={
                    "encounter_id": self.state.encounter.id,
                    "zone_id": zone_id,
                    "tactical_graph_source": tactical_graph_source,
                },
                tool_result=result,
            )
            return SessionResult(accepted=True, payload=result)
        if event_type == "end_combat":
            return self._handle_end_combat(event.idempotency_key)
        if event_type == "enter_cutscene":
            return self._handle_enter_cutscene(
                event.idempotency_key,
                reason=_optional_text(payload.get("reason")) or "",
            )
        if event_type == "exit_cutscene":
            return self._handle_exit_cutscene(event.idempotency_key)
        if event_type == "advance_turn":
            return self._advance_turn_unqueued(
                event.idempotency_key,
                now=self._interaction_now(),
            )
        if event_type == "monster_turn":
            return self._handle_monster_turn(event.idempotency_key)
        if event_type == "timeout_takeover":
            return self._handle_timeout_takeover(event.idempotency_key, int(payload["now"]))
        if event_type == "resolve_reaction":
            return self._handle_resolve_reaction(
                event.idempotency_key,
                reaction_id=str(payload["reaction_id"]),
                accept=bool(payload["accept"]),
                now=int(payload["now"]),
            )
        if event_type == "expire_reactions":
            return self._handle_expire_reactions(event.idempotency_key, int(payload["now"]))
        raise ValueError(f"unsupported session event type: {event_type}")

    def _handle_remember(self, idempotency_key: str, payload: dict[str, Any]) -> SessionResult:
        source_event_id = f"event-{self.state.event_counter:08d}"
        fragment = remember_fragment(
            self.state,
            text=str(payload["text"]),
            tags=[str(tag) for tag in payload.get("tags", [])],
            visibility=str(payload.get("visibility", "public")),
            source_event_id=source_event_id,
        )
        result = {
            "memory_id": fragment.id,
            "tags": list(fragment.tags),
            "visibility": fragment.visibility,
            "source_event_id": fragment.source_event_id,
            "created_at_event_counter": fragment.created_at_event_counter,
        }
        self.audit_log.append(
            self.state,
            idempotency_key=idempotency_key,
            tool_name="orchestrator.memory.remember",
            tool_args={
                "text": fragment.text,
                "tags": list(fragment.tags),
                "visibility": fragment.visibility,
            },
            tool_result=result,
        )
        return SessionResult(accepted=True, payload=result)

    def _handle_end_combat(self, idempotency_key: str) -> SessionResult:
        if self.state.encounter is None:
            return SessionResult(accepted=False, payload={"reason": "no active encounter"})
        ended_encounter_id = self.state.encounter.id
        _sync_encounter_status_effects_to_backing(self.state)
        self.state.encounter = None
        self.economy.use_backing({})
        self.state.session_mode = "exploration"
        result = {
            "ended_encounter_id": ended_encounter_id,
            "session_mode": self.state.session_mode,
        }
        self.audit_log.append(
            self.state,
            idempotency_key=idempotency_key,
            tool_name="orchestrator.end_combat",
            tool_result=result,
        )
        return SessionResult(accepted=True, payload=result)

    def _handle_enter_cutscene(self, idempotency_key: str, *, reason: str) -> SessionResult:
        if self.state.encounter is not None:
            return SessionResult(
                accepted=False,
                payload={"reason": "cannot enter cutscene during combat"},
            )
        previous_mode = self.state.session_mode
        self.state.session_mode = "cutscene"
        result = {
            "previous_mode": previous_mode,
            "session_mode": self.state.session_mode,
            "reason": reason,
        }
        self.audit_log.append(
            self.state,
            idempotency_key=idempotency_key,
            tool_name="orchestrator.enter_cutscene",
            tool_args={"reason": reason},
            tool_result=result,
        )
        return SessionResult(accepted=True, payload=result)

    def _handle_exit_cutscene(self, idempotency_key: str) -> SessionResult:
        if self.state.encounter is not None:
            return SessionResult(
                accepted=False,
                payload={"reason": "cannot exit cutscene during combat"},
            )
        previous_mode = self.state.session_mode
        self.state.session_mode = "exploration"
        result = {
            "previous_mode": previous_mode,
            "session_mode": self.state.session_mode,
        }
        self.audit_log.append(
            self.state,
            idempotency_key=idempotency_key,
            tool_name="orchestrator.exit_cutscene",
            tool_result=result,
        )
        return SessionResult(accepted=True, payload=result)

    def _resolve_tactical_graph_for_combat(
        self,
        explicit_graph: TacticalGraph | None,
        *,
        zone_id: str,
    ) -> tuple[TacticalGraph, str]:
        if explicit_graph is not None:
            return explicit_graph, "explicit"
        if self.campaign_pack is not None:
            try:
                return (
                    tactical_graph_for_state_zone(self.state, self.campaign_pack, zone_id),
                    "campaign_pack",
                )
            except (KeyError, TypeError, ValueError):
                pass
        generated_graph = _generated_tactical_graph(self.state, zone_id)
        if generated_graph is not None:
            return generated_graph, "generated_template"
        graph = starter_tactical_graph()
        _store_generated_tactical_graph(self.state, zone_id, graph)
        return graph, "generated_template"

    def _handle_update_summary(
        self,
        idempotency_key: str,
        payload: dict[str, Any],
    ) -> SessionResult:
        previous_summary = self.state.summary
        summary = str(payload["summary"])
        self.state.summary = summary
        result = {
            "previous_length": len(previous_summary),
            "summary_length": len(summary),
            "summary": summary,
        }
        self.audit_log.append(
            self.state,
            idempotency_key=idempotency_key,
            tool_name="dm.summary.update",
            tool_args={
                "scene_notes": str(payload.get("scene_notes", "")),
                "previous_length": len(previous_summary),
            },
            tool_result=result,
            model_id=_optional_text(payload.get("model_id")),
            prompt_version=_optional_text(payload.get("prompt_version")),
            model_usage={
                str(key): int(value) for key, value in dict(payload.get("model_usage", {})).items()
            },
        )
        return SessionResult(accepted=True, payload=result)

    def _handle_expand_dynamic_zone(
        self,
        idempotency_key: str,
        payload: dict[str, Any],
    ) -> SessionResult:
        parent_zone_id = str(payload["parent_zone_id"])
        theme = str(payload["theme"])
        zone_id = _optional_text(payload.get("zone_id"))
        name = _optional_text(payload.get("name"))
        args = {
            "parent_zone_id": parent_zone_id,
            "theme": theme,
            "zone_id": zone_id,
            "name": name,
        }
        try:
            expansion = expand_dynamic_zone(
                self.state,
                parent_zone_id=parent_zone_id,
                theme=theme,
                zone_id=zone_id,
                name=name,
            )
        except ValueError as exc:
            result = {"accepted": False, "reason": str(exc), **args}
            self.audit_log.append(
                self.state,
                idempotency_key=idempotency_key,
                tool_name="orchestrator.content.expand_zone",
                tool_args=args,
                tool_result=result,
            )
            return SessionResult(accepted=False, payload=result)
        result = expansion.to_dict()
        self.audit_log.append(
            self.state,
            idempotency_key=idempotency_key,
            tool_name="orchestrator.content.expand_zone",
            tool_args=args,
            tool_result=result,
        )
        return SessionResult(accepted=True, payload=result)

    def _advance_turn_unqueued(self, idempotency_key: str, now: int | None) -> SessionResult:
        if self.state.encounter is None:
            return SessionResult(accepted=False, payload={"reason": "no active encounter"})
        previous = self.state.encounter.current_combatant_id
        lifecycle_results: list[EffectLifecycleResult] = []
        if previous is not None:
            end_cycle = (
                f"{self.state.encounter.id}:round:{self.state.encounter.round_number}:turn_end"
            )
            lifecycle_results.extend(
                [
                    tick_effects(
                        self.state,
                        trigger="self_turn_end",
                        actor_id=previous,
                        roll_service=self.roll_service,
                        cycle_id=end_cycle,
                    ),
                    tick_effects(
                        self.state,
                        trigger="target_turn_end",
                        actor_id=previous,
                        roll_service=self.roll_service,
                        cycle_id=end_cycle,
                    ),
                ]
            )
        before_round = self.state.encounter.round_number
        current = advance_encounter_turn(self.state.encounter)
        if current is None:
            return SessionResult(accepted=False, payload={"reason": "empty initiative"})
        if self.state.encounter.round_number > before_round:
            for combatant_id in self.state.encounter.combatants:
                self.economy.reset_round_start(combatant_id)
        self.economy.reset_turn_start(
            current,
            _effective_combatant_speed(self.state, self.state.encounter.combatants[current]),
        )
        start_cycle = (
            f"{self.state.encounter.id}:round:{self.state.encounter.round_number}:turn_start"
        )
        lifecycle_results.extend(
            [
                tick_effects(
                    self.state,
                    trigger="self_turn_start",
                    actor_id=current,
                    roll_service=self.roll_service,
                    cycle_id=start_cycle,
                ),
                tick_effects(
                    self.state,
                    trigger="target_turn_start",
                    actor_id=current,
                    roll_service=self.roll_service,
                    cycle_id=start_cycle,
                ),
            ]
        )
        heroic_inspiration = _apply_champion_heroic_warrior(self.state, current)
        heroic_rally = _apply_champion_survivor_heroic_rally(self.state, current)
        result = {
            "round_number": self.state.encounter.round_number,
            "current_combatant_id": current,
        }
        if heroic_inspiration is not None:
            result["heroic_inspiration"] = heroic_inspiration
        if heroic_rally is not None:
            result["heroic_rally"] = heroic_rally
        changed_lifecycle = [item.to_dict() for item in lifecycle_results if item.changed]
        if changed_lifecycle:
            result["effect_lifecycle"] = changed_lifecycle
        if now is not None:
            self.timeout.mark_turn_start(current, now)
        self.audit_log.append(
            self.state,
            idempotency_key=idempotency_key,
            tool_name="orchestrator.advance_turn",
            tool_result=result,
        )
        return SessionResult(accepted=True, payload=result)

    def _handle_monster_turn(self, idempotency_key: str) -> SessionResult:
        if self.state.encounter is None or self.state.encounter.current_combatant_id is None:
            return SessionResult(accepted=False, payload={"reason": "no active encounter"})
        current = self.state.encounter.current_combatant_id
        combatant = self.state.encounter.combatants[current]
        if combatant.side == "party":
            return SessionResult(
                accepted=False, payload={"reason": "current combatant is not a monster"}
            )
        if self.monster_turn_planner is not None and self.tactics.uses_llm(combatant):
            planned = self.monster_turn_planner(current, self.state.event_counter, idempotency_key)
            if planned is not None:
                self.audit_log.append(
                    self.state,
                    idempotency_key=f"{idempotency_key}:monster_planner",
                    player_text=planned.raw_text,
                    player_intent=planned.__dict__,
                    tool_name="orchestrator.monster_turn",
                    tool_args={"source": "llm"},
                    tool_result={"draft": planned.__dict__, "source": "llm"},
                )
                planned_result = self._resolve_and_execute_draft(
                    planned,
                    f"{idempotency_key}:llm",
                    allow_reactions=True,
                )
                if planned_result.accepted:
                    self._advance_after_action_if_ready(
                        planned_result.payload,
                        f"{idempotency_key}:advance",
                        now=self._interaction_now(),
                    )
                    return planned_result
                self.audit_log.append(
                    self.state,
                    idempotency_key=f"{idempotency_key}:monster_planner_fallback",
                    player_text=planned.raw_text,
                    player_intent=planned.__dict__,
                    tool_name="orchestrator.monster_turn.fallback",
                    tool_args={"source": "llm"},
                    tool_result={
                        "reason": "planner draft rejected",
                        "draft": planned.__dict__,
                        "error": planned_result.payload,
                    },
                )
        draft = self.tactics.draft_for_current_turn(
            state=self.state,
            actions=self.compendium.actions,
            roll_service=self.roll_service,
        )
        self.audit_log.append(
            self.state,
            idempotency_key=f"{idempotency_key}:monster_tactics",
            player_text=draft.raw_text,
            player_intent=draft.__dict__,
            tool_name="orchestrator.monster_turn",
            tool_args={"source": "deterministic_tactics"},
            tool_result={"draft": draft.__dict__, "source": "deterministic_tactics"},
        )
        result = self._resolve_and_execute_draft(
            draft,
            f"{idempotency_key}:tactics",
            allow_reactions=True,
        )
        if result.accepted:
            self._advance_after_action_if_ready(
                result.payload,
                f"{idempotency_key}:advance",
                now=self._interaction_now(),
            )
        return result

    def _handle_timeout_takeover(self, idempotency_key: str, now: int) -> SessionResult:
        timed_out = self._timed_out_current_combatant(now)
        if timed_out is None:
            return SessionResult(accepted=False, payload={"reason": "turn has not timed out"})
        if self.timeout_takeover_planner is not None and self._is_party_combatant(timed_out):
            planned = self.timeout_takeover_planner(timed_out, now, idempotency_key)
            if planned is not None:
                self.audit_log.append(
                    self.state,
                    idempotency_key=f"{idempotency_key}:timeout_planner",
                    player_text=planned.raw_text,
                    player_intent=planned.__dict__,
                    tool_name="orchestrator.timeout_takeover",
                    tool_args={"now": now, "source": "llm"},
                    tool_result={"draft": planned.__dict__, "source": "llm"},
                )
                planned_result = self._resolve_and_execute_draft(
                    planned,
                    f"{idempotency_key}:llm",
                    allow_reactions=True,
                )
                if planned_result.accepted:
                    self._advance_after_action_if_ready(
                        planned_result.payload,
                        f"{idempotency_key}:advance",
                        now=now,
                    )
                    return planned_result
                self.audit_log.append(
                    self.state,
                    idempotency_key=f"{idempotency_key}:timeout_planner_fallback",
                    player_text=planned.raw_text,
                    player_intent=planned.__dict__,
                    tool_name="orchestrator.timeout_takeover.fallback",
                    tool_args={"now": now, "source": "llm"},
                    tool_result={
                        "reason": "planner draft rejected",
                        "draft": planned.__dict__,
                        "error": planned_result.payload,
                    },
                )
        draft = self.timeout.takeover_draft(
            state=self.state,
            now=now,
            tactics=self.tactics,
            actions=self.compendium.actions,
            roll_service=self.roll_service,
        )
        if draft is None:
            return SessionResult(accepted=False, payload={"reason": "turn has not timed out"})
        self.audit_log.append(
            self.state,
            idempotency_key=f"{idempotency_key}:timeout",
            player_text=draft.raw_text,
            player_intent=draft.__dict__,
            tool_name="orchestrator.timeout_takeover",
            tool_args={"now": now, "source": "deterministic_fallback"},
            tool_result={"draft": draft.__dict__, "source": "deterministic_fallback"},
        )
        result = self._resolve_and_execute_draft(
            draft,
            f"{idempotency_key}:fallback",
            allow_reactions=True,
        )
        if result.accepted:
            self._advance_after_action_if_ready(
                result.payload, f"{idempotency_key}:advance", now=now
            )
        return result

    def _timed_out_current_combatant(self, now: int) -> str | None:
        if self.state.encounter is None or self.state.encounter.current_combatant_id is None:
            return None
        current = self.state.encounter.current_combatant_id
        if not self.timeout.is_timed_out(current, now):
            return None
        return current

    def _is_party_combatant(self, combatant_id: str) -> bool:
        if self.state.encounter is None:
            return False
        combatant = self.state.encounter.combatants.get(combatant_id)
        return combatant is not None and combatant.side == "party"

    def _handle_resolve_reaction(
        self,
        idempotency_key: str,
        *,
        reaction_id: str,
        accept: bool,
        now: int,
    ) -> SessionResult:
        window, draft, status = self.reactions.resolve_window(
            self.state,
            reaction_id=reaction_id,
            accept=accept,
            now=now,
        )
        if window is None:
            return SessionResult(accepted=False, payload={"reason": status})
        payload: dict[str, Any] = {
            "reaction_id": reaction_id,
            "status": status,
            "actor_id": window.actor_id,
            "trigger_actor_id": window.trigger_actor_id,
        }
        if draft is not None:
            reaction = self._resolve_and_execute_draft(
                draft,
                f"{idempotency_key}:execute",
                allow_reactions=False,
            )
            payload["reaction"] = reaction.payload
            payload["reaction_accepted"] = reaction.accepted
        self.audit_log.append(
            self.state,
            idempotency_key=f"{idempotency_key}:reaction_resolve",
            player_intent=draft.__dict__ if draft is not None else None,
            tool_name="orchestrator.reaction_window.resolve",
            tool_args={"reaction_id": reaction_id, "accept": accept, "now": now},
            tool_result=payload,
        )
        self._advance_after_reactions_if_ready(payload, f"{idempotency_key}:advance", now=now)
        return SessionResult(accepted=True, payload=payload)

    def _handle_expire_reactions(self, idempotency_key: str, now: int) -> SessionResult:
        expired = self.reactions.expire_due(self.state, now=now)
        if not expired:
            return SessionResult(accepted=False, payload={"reason": "no expired reactions"})
        payload: dict[str, Any] = {
            "expired_reactions": [window.to_dict() for window in expired],
            "status": "expired",
        }
        self.audit_log.append(
            self.state,
            idempotency_key=f"{idempotency_key}:reaction_expire",
            tool_name="orchestrator.reaction_window.expire",
            tool_args={"now": now},
            tool_result=payload,
        )
        self._advance_after_reactions_if_ready(payload, f"{idempotency_key}:advance", now=now)
        return SessionResult(accepted=True, payload=payload)

    def _resolve_and_execute_draft(
        self,
        draft: PlayerActionDraft,
        idempotency_key: str,
        *,
        allow_reactions: bool,
    ) -> SessionResult:
        resolver = ActionResolver(
            self.state,
            self.compendium.actions,
            self.compendium.items,
            self.economy,
        )
        decision = resolver.resolve(draft)
        self.audit_log.append(
            self.state,
            idempotency_key=f"{idempotency_key}:resolver",
            player_text=draft.raw_text,
            player_intent=draft.__dict__,
            tool_name="resolver.resolve",
            tool_args=draft.__dict__,
            tool_result=decision.to_dict(),
        )
        if decision.status != "accepted" or decision.action_id is None:
            return SessionResult(accepted=False, payload=decision.to_dict())
        result = self._execute_resolved_draft(
            draft,
            decision.action_id,
            idempotency_key,
            allow_reactions=allow_reactions,
        )
        return SessionResult(accepted=result.get("status") != "rejected", payload=result)

    def _execute_resolved_draft(
        self,
        draft: PlayerActionDraft,
        action_id: str,
        idempotency_key: str,
        *,
        allow_reactions: bool,
    ) -> dict[str, Any]:
        action = self.compendium.action(action_id)
        if draft.verb == "use_item" and draft.candidate_action_id in self.compendium.items:
            result = self.tools.use_item(
                draft.actor_id,
                draft.candidate_action_id,
                draft.target_ids,
                action_id=action.id,
                params=draft.params,
                fast_hands=bool(draft.params.get("fast_hands", False)),
                idempotency_key=idempotency_key,
            )
        elif action.action_type == "spell":
            result = self.tools.cast_spell(
                draft.actor_id,
                action.id,
                draft.target_ids,
                int(draft.params.get("slot_level", action.cost.spell_slot_level or 0)),
                as_ritual=bool(draft.params.get("as_ritual", False)),
                idempotency_key=idempotency_key,
            )
        elif action.action_economy == "movement":
            try:
                result = self.tools.move(
                    draft.actor_id,
                    to_position_node_id=draft.params.get("to_position_node_id"),
                    to_zone_id=draft.params.get("to_zone_id"),
                    idempotency_key=idempotency_key,
                )
            except ValueError as exc:
                result = {
                    "success": False,
                    "status": "rejected",
                    "reason": str(exc),
                    "action_id": action.id,
                    "actor_id": draft.actor_id,
                }
                self.audit_log.append(
                    self.state,
                    idempotency_key=f"{idempotency_key}:movement_rejected",
                    player_text=draft.raw_text,
                    player_intent=draft.__dict__,
                    tool_name="orchestrator.movement.reject",
                    tool_args=draft.params,
                    tool_result=result,
                )
                return result
        else:
            result = self.tools.perform_action(
                draft.actor_id,
                action_id,
                draft.target_ids,
                draft.params,
                idempotency_key=idempotency_key,
            )
        if allow_reactions:
            result["reactions"] = self._run_reactions_for_result(
                moving_actor_id=draft.actor_id,
                result=result,
                idempotency_key=idempotency_key,
            )
        return result

    def _run_reactions_for_result(
        self,
        *,
        moving_actor_id: str,
        result: dict[str, Any],
        idempotency_key: str,
    ) -> list[dict[str, Any]]:
        reaction_results: list[dict[str, Any]] = []
        triggers: list[str] = []
        for change in result.get("state_changes", []):
            if change.get("type") == "move":
                triggers.extend(
                    str(actor_id) for actor_id in change.get("opportunity_attack_triggers", [])
                )
        if not triggers:
            return reaction_results
        if self.reactions.interactive:
            windows = self.reactions.open_opportunity_windows(
                state=self.state,
                economy=self.economy,
                moving_actor_id=moving_actor_id,
                trigger_actor_ids=triggers,
                group_id=idempotency_key,
                now=self._interaction_now(),
            )
            if windows:
                result["reaction_windows"] = [window.to_dict() for window in windows]
                self.audit_log.append(
                    self.state,
                    idempotency_key=f"{idempotency_key}:reaction_window",
                    tool_name="orchestrator.reaction_window.open",
                    tool_args={"moving_actor_id": moving_actor_id, "triggers": triggers},
                    tool_result={"reaction_windows": result["reaction_windows"]},
                )
            window_actor_ids = {window.actor_id for window in windows}
            triggers = [
                actor_id
                for actor_id in triggers
                if actor_id not in window_actor_ids
                and self.reactions.should_auto_resolve(self.state, actor_id)
            ]
            if not triggers:
                return reaction_results
        drafts = self.reactions.opportunity_attack_drafts(
            state=self.state,
            economy=self.economy,
            moving_actor_id=moving_actor_id,
            trigger_actor_ids=triggers,
        )
        for index, draft in enumerate(drafts):
            reaction = self._resolve_and_execute_draft(
                draft,
                f"{idempotency_key}:reaction:{index}",
                allow_reactions=False,
            )
            reaction_results.append(reaction.payload)
        return reaction_results

    def _advance_after_action_if_ready(
        self,
        result: dict[str, Any],
        idempotency_key: str,
        now: int | None,
    ) -> None:
        if self.reactions.has_pending(self.state):
            result["pending_reactions"] = [
                window.to_dict() for window in self.reactions.pending_windows(self.state)
            ]
            result["next_combatant_id"] = (
                self.state.encounter.current_combatant_id
                if self.state.encounter is not None
                else None
            )
            return
        fleet_step_actor = self._fleet_step_actor_waiting()
        if fleet_step_actor is not None:
            result["fleet_step_available"] = True
            result["next_combatant_id"] = fleet_step_actor
            return
        next_turn = self._advance_turn_unqueued(idempotency_key, now=now)
        result["next_combatant_id"] = next_turn.payload.get("current_combatant_id")

    def _advance_after_reactions_if_ready(
        self,
        payload: dict[str, Any],
        idempotency_key: str,
        now: int | None,
    ) -> None:
        if self.reactions.has_pending(self.state):
            payload["pending_reactions"] = [
                window.to_dict() for window in self.reactions.pending_windows(self.state)
            ]
            return
        fleet_step_actor = self._fleet_step_actor_waiting()
        if fleet_step_actor is not None:
            payload["fleet_step_available"] = True
            payload["next_combatant_id"] = fleet_step_actor
            return
        next_turn = self._advance_turn_unqueued(idempotency_key, now=now)
        payload["next_combatant_id"] = next_turn.payload.get("current_combatant_id")

    def _fleet_step_actor_waiting(self) -> str | None:
        if self.state.encounter is None or self.state.encounter.current_combatant_id is None:
            return None
        actor_id = self.state.encounter.current_combatant_id
        owner = _resource_owner(self.state, actor_id)
        if not isinstance(owner, Character) or not has_monk_open_hand_feature(owner, level=11):
            return None
        actor = _actor_entity(self.state, actor_id)
        if any(
            effect.get("condition") == FLEET_STEP_CONDITION
            and effect.get("source_action_id") == FLEET_STEP_ACTION_ID
            for effect in _status_effects_for(self.state, actor)
        ):
            return actor_id
        return None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _actor_entity(state: GameState, actor_id: str) -> Character | Monster | Combatant | None:
    try:
        return state.entity_for_actor(actor_id)
    except KeyError:
        return None


def _resource_owner(state: GameState, actor_id: str) -> Character | Monster | Combatant | None:
    actor = _actor_entity(state, actor_id)
    if isinstance(actor, Combatant) and actor.entity_id in state.characters:
        return state.characters[actor.entity_id]
    if isinstance(actor, Combatant) and actor.entity_id in state.monsters:
        return state.monsters[actor.entity_id]
    return actor


def _sync_encounter_status_effects_to_backing(state: GameState) -> None:
    if state.encounter is None:
        return
    for combatant in state.encounter.combatants.values():
        backing = state.characters.get(combatant.entity_id) or state.monsters.get(
            combatant.entity_id
        )
        if backing is None or combatant.status_effects is backing.status_effects:
            continue
        backing.status_effects = [dict(effect) for effect in combatant.status_effects]


def _status_effects_for(
    state: GameState,
    actor: Character | Monster | Combatant | None,
) -> list[dict[str, Any]]:
    if actor is None:
        return []
    effects = list(getattr(actor, "status_effects", []))
    if isinstance(actor, Combatant) and actor.entity_id in state.characters:
        backing_effects = state.characters[actor.entity_id].status_effects
        if backing_effects is not actor.status_effects:
            effects.extend(backing_effects)
    if isinstance(actor, Combatant) and actor.entity_id in state.monsters:
        backing_effects = state.monsters[actor.entity_id].status_effects
        if backing_effects is not actor.status_effects:
            effects.extend(backing_effects)
    return effects


def _effective_combatant_speed(state: GameState, combatant: Combatant) -> int:
    effects = list(combatant.status_effects)
    base_speed = combatant.speed_ft
    if combatant.entity_id in state.characters:
        backing_character = state.characters[combatant.entity_id]
        if backing_character.status_effects is not combatant.status_effects:
            effects.extend(backing_character.status_effects)
        base_speed += class_feature_speed_bonus(backing_character)
    if combatant.entity_id in state.monsters:
        backing_effects = state.monsters[combatant.entity_id].status_effects
        if backing_effects is not combatant.status_effects:
            effects.extend(backing_effects)
    return effective_speed(base_speed, effects)


def _apply_champion_heroic_warrior(
    state: GameState,
    combatant_id: str,
) -> dict[str, Any] | None:
    if state.encounter is None:
        return None
    combatant = state.encounter.combatants.get(combatant_id)
    if combatant is None:
        return None
    character = state.characters.get(combatant.entity_id)
    if character is None or not champion_heroic_warrior_can_grant_inspiration(character):
        return None
    before = int(character.resources.get(HEROIC_INSPIRATION_RESOURCE, 0))
    character.resources[HEROIC_INSPIRATION_RESOURCE] = 1
    return {
        "combatant_id": combatant_id,
        "character_id": character.id,
        "source_action_id": "srd.heroic_warrior",
        "resource": HEROIC_INSPIRATION_RESOURCE,
        "before": before,
        "after": 1,
    }


def _apply_champion_survivor_heroic_rally(
    state: GameState,
    combatant_id: str,
) -> dict[str, Any] | None:
    if state.encounter is None:
        return None
    combatant = state.encounter.combatants.get(combatant_id)
    if combatant is None:
        return None
    character = state.characters.get(combatant.entity_id)
    if character is None:
        return None
    hp_before = int(combatant.hp_current)
    healing = champion_survivor_heroic_rally_healing(
        character,
        hp_current=hp_before,
        hp_max=int(combatant.hp_max),
    )
    if healing <= 0:
        return None
    character_hp_before = int(character.hp_current)
    combatant.hp_current = min(int(combatant.hp_max), hp_before + healing)
    character.hp_current = combatant.hp_current
    applied = int(combatant.hp_current) - hp_before
    return {
        "combatant_id": combatant_id,
        "character_id": character.id,
        "source_action_id": "srd.survivor",
        "healing": healing,
        "applied": applied,
        "combatant_hp_before": hp_before,
        "combatant_hp_after": combatant.hp_current,
        "character_hp_before": character_hp_before,
        "character_hp_after": character.hp_current,
    }


def _generated_tactical_graph(state: GameState, zone_id: str) -> TacticalGraph | None:
    store = state.world.flags.get(GENERATED_TACTICAL_GRAPHS_FLAG, {})
    if not isinstance(store, dict):
        raise ValueError("generated_tactical_graphs flag must be an object")
    graph_data = store.get(zone_id)
    if graph_data is None:
        return None
    if not isinstance(graph_data, dict):
        raise TypeError("generated tactical graph must be an object")
    return TacticalGraph.from_dict(graph_data)


def _store_generated_tactical_graph(
    state: GameState,
    zone_id: str,
    graph: TacticalGraph,
) -> None:
    store = state.world.flags.setdefault(GENERATED_TACTICAL_GRAPHS_FLAG, {})
    if not isinstance(store, dict):
        raise ValueError("generated_tactical_graphs flag must be an object")
    store[zone_id] = graph.to_dict()

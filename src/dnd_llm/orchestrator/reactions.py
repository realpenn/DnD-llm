from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dnd_llm.core.economy import EconomyTracker
from dnd_llm.core.models import GameState
from dnd_llm.core.resolver import PlayerActionDraft


def _cannot_make_opportunity_attacks(status_effects: list[dict[str, Any]]) -> bool:
    for effect in status_effects:
        if effect.get("condition") == "open_hand_addled":
            return True
        modifiers = effect.get("passive_modifiers", {})
        if isinstance(modifiers, dict) and modifiers.get("cannot_make_opportunity_attacks"):
            return True
    return False


@dataclass
class ReactionPreference:
    actor_id: str
    opportunity_attacks: bool = True
    resource_spend_enabled: bool = False
    interactive: bool = True


@dataclass(frozen=True)
class ReactionWindow:
    reaction_id: str
    group_id: str
    actor_id: str
    trigger_actor_id: str
    action_id: str
    opened_at: int
    timeout_at: int
    prompt: str
    status: str = "pending"

    def to_dict(self) -> dict[str, Any]:
        return {
            "reaction_id": self.reaction_id,
            "group_id": self.group_id,
            "actor_id": self.actor_id,
            "trigger_actor_id": self.trigger_actor_id,
            "action_id": self.action_id,
            "opened_at": self.opened_at,
            "timeout_at": self.timeout_at,
            "prompt": self.prompt,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReactionWindow:
        return cls(
            reaction_id=str(data["reaction_id"]),
            group_id=str(data["group_id"]),
            actor_id=str(data["actor_id"]),
            trigger_actor_id=str(data["trigger_actor_id"]),
            action_id=str(data["action_id"]),
            opened_at=int(data["opened_at"]),
            timeout_at=int(data["timeout_at"]),
            prompt=str(data["prompt"]),
            status=str(data.get("status", "pending")),
        )

    def draft(self) -> PlayerActionDraft:
        return PlayerActionDraft(
            actor_id=self.actor_id,
            verb=self.action_id,
            candidate_action_id=self.action_id,
            target_ids=[self.trigger_actor_id],
            params={"reaction_trigger": "opportunity_attack", "ignore_range": True},
            raw_text=f"[reaction confirmed] {self.actor_id} uses {self.action_id}",
        )


class ReactionManager:
    def __init__(
        self,
        preferences: dict[str, ReactionPreference] | None = None,
        *,
        mode: str = "auto",
        timeout_seconds: int = 30,
        interactive_sides: set[str] | None = None,
    ):
        if mode not in {"interactive", "auto"}:
            raise ValueError("reaction mode must be interactive or auto")
        self.preferences = preferences or {}
        self.mode = mode
        self.timeout_seconds = timeout_seconds
        self.interactive_sides = interactive_sides or {"party"}

    @property
    def interactive(self) -> bool:
        return self.mode == "interactive"

    def has_pending(self, state: GameState) -> bool:
        return bool(self._pending_store(state))

    def pending_windows(self, state: GameState) -> list[ReactionWindow]:
        return [
            ReactionWindow.from_dict(data)
            for data in self._pending_store(state).values()
            if data.get("status", "pending") == "pending"
        ]

    def opportunity_attack_drafts(
        self,
        *,
        state: GameState,
        economy: EconomyTracker,
        moving_actor_id: str,
        trigger_actor_ids: list[str],
    ) -> list[PlayerActionDraft]:
        if state.encounter is None:
            return []
        drafts: list[PlayerActionDraft] = []
        for actor_id in trigger_actor_ids:
            actor = state.encounter.combatants.get(actor_id)
            if actor is None or actor.hp_current <= 0:
                continue
            if _cannot_make_opportunity_attacks(actor.status_effects):
                continue
            preference = self.preferences.get(actor_id, ReactionPreference(actor_id=actor_id))
            if not preference.opportunity_attacks:
                continue
            if not economy.budget_for(actor_id, actor.speed_ft).can_spend("reaction"):
                continue
            drafts.append(
                PlayerActionDraft(
                    actor_id=actor_id,
                    verb="srd.opportunity_attack",
                    candidate_action_id="srd.opportunity_attack",
                    target_ids=[moving_actor_id],
                    params={"reaction_trigger": "opportunity_attack", "ignore_range": True},
                    raw_text=f"[auto reaction] {actor.name} opportunity attack",
                )
            )
        return drafts

    def open_opportunity_windows(
        self,
        *,
        state: GameState,
        economy: EconomyTracker,
        moving_actor_id: str,
        trigger_actor_ids: list[str],
        group_id: str,
        now: int,
    ) -> list[ReactionWindow]:
        if state.encounter is None:
            return []
        windows: list[ReactionWindow] = []
        store = self._pending_store(state)
        for actor_id in trigger_actor_ids:
            actor = state.encounter.combatants.get(actor_id)
            if actor is None or actor.hp_current <= 0:
                continue
            if actor.side not in self.interactive_sides:
                continue
            preference = self.preferences.get(actor_id, ReactionPreference(actor_id=actor_id))
            if not preference.opportunity_attacks or not preference.interactive:
                continue
            if not economy.budget_for(actor_id, actor.speed_ft).can_spend("reaction"):
                continue
            reaction_id = f"{group_id}:opportunity:{actor_id}"
            if reaction_id in store:
                continue
            moving_actor = state.encounter.combatants.get(moving_actor_id)
            target_name = moving_actor.name if moving_actor is not None else moving_actor_id
            window = ReactionWindow(
                reaction_id=reaction_id,
                group_id=group_id,
                actor_id=actor_id,
                trigger_actor_id=moving_actor_id,
                action_id="srd.opportunity_attack",
                opened_at=now,
                timeout_at=now + self.timeout_seconds,
                prompt=(
                    f"{actor.name} 可以对 {target_name} 触发借机攻击。"
                    f"在 {self.timeout_seconds} 秒内确认，否则默认放弃。"
                ),
            )
            store[reaction_id] = window.to_dict()
            windows.append(window)
        return windows

    def resolve_window(
        self,
        state: GameState,
        *,
        reaction_id: str,
        accept: bool,
        now: int,
    ) -> tuple[ReactionWindow | None, PlayerActionDraft | None, str]:
        store = self._pending_store(state)
        data = store.pop(reaction_id, None)
        if data is None:
            return None, None, "unknown reaction window"
        window = ReactionWindow.from_dict(data)
        if now >= window.timeout_at:
            return window, None, "expired"
        if not accept:
            return window, None, "declined"
        return window, window.draft(), "accepted"

    def expire_due(self, state: GameState, *, now: int) -> list[ReactionWindow]:
        store = self._pending_store(state)
        expired: list[ReactionWindow] = []
        for reaction_id, data in list(store.items()):
            window = ReactionWindow.from_dict(data)
            if now >= window.timeout_at:
                expired.append(window)
                store.pop(reaction_id, None)
        return expired

    def should_auto_resolve(self, state: GameState, actor_id: str) -> bool:
        if self.mode == "auto":
            return True
        if state.encounter is None:
            return False
        actor = state.encounter.combatants.get(actor_id)
        return actor is not None and actor.side not in self.interactive_sides

    @staticmethod
    def _pending_store(state: GameState) -> dict[str, dict[str, Any]]:
        if state.encounter is None:
            return {}
        return state.encounter.pending_reactions

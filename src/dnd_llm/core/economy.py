from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ActionBudget:
    action: int = 1
    bonus_action: int = 1
    reaction: int = 1
    movement: int = 30
    movement_used: int = 0
    free: int = 1

    def to_dict(self) -> dict[str, int]:
        return {
            "action": self.action,
            "bonus_action": self.bonus_action,
            "reaction": self.reaction,
            "movement": self.movement,
            "movement_used": self.movement_used,
            "free": self.free,
        }

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> ActionBudget:
        return cls(
            action=int(data.get("action", 1)),
            bonus_action=int(data.get("bonus_action", 1)),
            reaction=int(data.get("reaction", 1)),
            movement=int(data.get("movement", 30)),
            movement_used=int(data.get("movement_used", 0)),
            free=int(data.get("free", 1)),
        )

    def can_spend(self, economy: str, amount: int = 1) -> bool:
        if economy == "none":
            return True
        return getattr(self, economy, 0) >= amount

    def spend(self, economy: str, amount: int = 1) -> None:
        if economy == "none":
            return
        if not self.can_spend(economy, amount):
            raise ValueError(f"not enough {economy} budget")
        setattr(self, economy, getattr(self, economy) - amount)
        if economy == "movement":
            self.movement_used += amount

    def reset_turn_start(self, speed_ft: int = 30) -> None:
        self.action = 1
        self.bonus_action = 1
        self.movement = speed_ft
        self.movement_used = 0
        self.free = 1

    def reset_round_start(self) -> None:
        self.reaction = 1


class EconomyTracker:
    def __init__(self, backing: dict[str, dict[str, int]] | None = None) -> None:
        self._budgets: dict[str, ActionBudget] = {}
        self._backing = backing if backing is not None else {}

    def use_backing(self, backing: dict[str, dict[str, int]]) -> None:
        self._backing = backing
        self._budgets.clear()

    def budget_for(self, actor_id: str, speed_ft: int = 30) -> ActionBudget:
        if actor_id not in self._budgets:
            if actor_id in self._backing:
                self._budgets[actor_id] = ActionBudget.from_dict(self._backing[actor_id])
            else:
                self._budgets[actor_id] = ActionBudget(movement=speed_ft)
                self._sync(actor_id)
        return self._budgets[actor_id]

    def spend(self, actor_id: str, economy: str, amount: int = 1) -> None:
        self.budget_for(actor_id).spend(economy, amount)
        self._sync(actor_id)

    def reset_turn_start(self, actor_id: str, speed_ft: int = 30) -> None:
        self.budget_for(actor_id, speed_ft).reset_turn_start(speed_ft)
        self._sync(actor_id)

    def reset_round_start(self, actor_id: str) -> None:
        self.budget_for(actor_id).reset_round_start()
        self._sync(actor_id)

    def add(self, actor_id: str, economy: str, delta: int) -> tuple[int, int]:
        budget = self.budget_for(actor_id)
        before = int(getattr(budget, economy))
        after = before + delta
        if after < 0:
            raise ValueError(f"{economy} budget cannot drop below zero")
        setattr(budget, economy, after)
        self._sync(actor_id)
        return before, after

    def set(self, actor_id: str, economy: str, value: int) -> tuple[int, int]:
        if value < 0:
            raise ValueError(f"{economy} budget cannot drop below zero")
        budget = self.budget_for(actor_id)
        before = int(getattr(budget, economy))
        setattr(budget, economy, value)
        self._sync(actor_id)
        return before, value

    def _sync(self, actor_id: str) -> None:
        self._backing[actor_id] = self._budgets[actor_id].to_dict()

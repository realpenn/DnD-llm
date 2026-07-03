from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any

from .models import GameState

_TOKEN_RE = re.compile(r"([+-]?)\s*(?:(\d*)d(\d+)|(\d+))", re.IGNORECASE)


@dataclass(frozen=True)
class RollDie:
    sides: int
    value: int
    kept: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"sides": self.sides, "value": self.value, "kept": self.kept}


@dataclass(frozen=True)
class RollResult:
    roll_id: str
    expression: str
    seed: int
    counter: int
    advantage: str | None
    dice: list[RollDie] = field(default_factory=list)
    modifier_total: int = 0
    total: int = 0
    display: str = ""
    replayed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "roll_id": self.roll_id,
            "expression": self.expression,
            "seed": self.seed,
            "counter": self.counter,
            "advantage": self.advantage,
            "dice": [die.to_dict() for die in self.dice],
            "modifier_total": self.modifier_total,
            "total": self.total,
            "display": self.display,
            "replayed": self.replayed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RollResult:
        payload = dict(data)
        payload["dice"] = [RollDie(**die) for die in payload.get("dice", [])]
        return cls(**payload)


class RollService:
    """Deterministic dice service keyed by state seed and monotonic counter."""

    def __init__(self, state: GameState):
        self.state = state

    def roll(self, expression: str, advantage: str | None = None) -> RollResult:
        if advantage not in {None, "advantage", "disadvantage"}:
            raise ValueError("advantage must be None, 'advantage', or 'disadvantage'")
        counter = self.state.roll_counter
        rng = random.Random(f"{self.state.rng_seed}:{counter}:{expression}:{advantage or 'normal'}")
        dice: list[RollDie] = []
        modifier_total = 0
        total = 0
        matched = False
        used_advantage = False

        for match in _TOKEN_RE.finditer(expression.replace(" ", "")):
            matched = True
            sign = -1 if match.group(1) == "-" else 1
            if match.group(3):
                count = int(match.group(2) or "1")
                sides = int(match.group(3))
                if count <= 0 or sides <= 0:
                    raise ValueError(f"invalid dice term in {expression!r}")
                term_values: list[RollDie] = []
                if (
                    advantage in {"advantage", "disadvantage"}
                    and not used_advantage
                    and count == 1
                    and sides == 20
                ):
                    first = RollDie(sides=sides, value=rng.randint(1, sides), kept=True)
                    second = RollDie(sides=sides, value=rng.randint(1, sides), kept=True)
                    keep_first = (
                        first.value >= second.value
                        if advantage == "advantage"
                        else first.value <= second.value
                    )
                    term_values = [
                        RollDie(sides=sides, value=first.value, kept=keep_first),
                        RollDie(sides=sides, value=second.value, kept=not keep_first),
                    ]
                    used_advantage = True
                else:
                    term_values = [
                        RollDie(sides=sides, value=rng.randint(1, sides), kept=True)
                        for _ in range(count)
                    ]
                dice.extend(term_values)
                total += sign * sum(die.value for die in term_values if die.kept)
            else:
                modifier = sign * int(match.group(4))
                modifier_total += modifier
                total += modifier

        if not matched:
            raise ValueError(f"unsupported dice expression: {expression!r}")

        roll_id = f"roll-{counter:08d}"
        self.state.roll_counter += 1
        display = self._display(expression, dice, modifier_total, total)
        return RollResult(
            roll_id=roll_id,
            expression=expression,
            seed=self.state.rng_seed,
            counter=counter,
            advantage=advantage,
            dice=dice,
            modifier_total=modifier_total,
            total=total,
            display=display,
        )

    @staticmethod
    def _display(expression: str, dice: list[RollDie], modifier_total: int, total: int) -> str:
        dice_bits = []
        for die in dice:
            marker = "" if die.kept else "dropped"
            dice_bits.append(f"d{die.sides}={die.value}{marker}")
        mod = f", mod={modifier_total}" if modifier_total else ""
        return f"{expression}: [{', '.join(dice_bits)}{mod}] => {total}"


class ReplayRollService:
    """Roll service that replays audited dice faces exactly."""

    def __init__(self, audited_rolls: list[dict[str, Any]]):
        self._rolls = [RollResult.from_dict(item) for item in audited_rolls]
        self._index = 0

    def roll(self, expression: str, advantage: str | None = None) -> RollResult:
        if self._index >= len(self._rolls):
            raise IndexError("no audited roll left to replay")
        result = self._rolls[self._index]
        self._index += 1
        if result.expression != expression or result.advantage != advantage:
            raise ValueError("audited roll does not match requested expression")
        return RollResult(
            roll_id=result.roll_id,
            expression=result.expression,
            seed=result.seed,
            counter=result.counter,
            advantage=result.advantage,
            dice=result.dice,
            modifier_total=result.modifier_total,
            total=result.total,
            display=result.display,
            replayed=True,
        )

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any

XP_BUDGET_PER_CHARACTER: dict[int, dict[str, int]] = {
    1: {"low": 50, "moderate": 75, "high": 100},
    2: {"low": 100, "moderate": 150, "high": 200},
    3: {"low": 150, "moderate": 225, "high": 400},
    4: {"low": 250, "moderate": 375, "high": 500},
    5: {"low": 500, "moderate": 750, "high": 1100},
    6: {"low": 600, "moderate": 1000, "high": 1400},
    7: {"low": 750, "moderate": 1300, "high": 1700},
    8: {"low": 1000, "moderate": 1700, "high": 2100},
    9: {"low": 1300, "moderate": 2000, "high": 2600},
    10: {"low": 1600, "moderate": 2300, "high": 3100},
    11: {"low": 1900, "moderate": 2900, "high": 4100},
    12: {"low": 2200, "moderate": 3700, "high": 4700},
    13: {"low": 2600, "moderate": 4200, "high": 5400},
    14: {"low": 2900, "moderate": 4900, "high": 6200},
    15: {"low": 3300, "moderate": 5400, "high": 7800},
    16: {"low": 3800, "moderate": 6100, "high": 9800},
    17: {"low": 4500, "moderate": 7200, "high": 11700},
    18: {"low": 5000, "moderate": 8700, "high": 14200},
    19: {"low": 5500, "moderate": 10700, "high": 17200},
    20: {"low": 6400, "moderate": 13200, "high": 22000},
}

XP_BY_CR: dict[Fraction, int] = {
    Fraction(1, 8): 25,
    Fraction(1, 4): 50,
    Fraction(1, 2): 100,
    Fraction(1): 200,
    Fraction(2): 450,
    Fraction(3): 700,
    Fraction(4): 1100,
    Fraction(5): 1800,
    Fraction(6): 2300,
    Fraction(7): 2900,
    Fraction(8): 3900,
    Fraction(9): 5000,
    Fraction(10): 5900,
    Fraction(11): 7200,
    Fraction(12): 8400,
    Fraction(13): 10000,
    Fraction(14): 11500,
    Fraction(15): 13000,
    Fraction(16): 15000,
    Fraction(17): 18000,
    Fraction(18): 20000,
    Fraction(19): 22000,
    Fraction(20): 25000,
    Fraction(21): 33000,
    Fraction(22): 41000,
    Fraction(23): 50000,
    Fraction(24): 62000,
    Fraction(25): 75000,
    Fraction(26): 90000,
    Fraction(27): 105000,
    Fraction(28): 120000,
    Fraction(29): 135000,
    Fraction(30): 155000,
}


@dataclass(frozen=True)
class EncounterBudget:
    party_size: int
    party_level: int
    difficulty: str
    max_xp: int

    def to_dict(self) -> dict[str, int | str]:
        return {
            "party_size": self.party_size,
            "party_level": self.party_level,
            "difficulty": self.difficulty,
            "max_xp": self.max_xp,
        }


def budget_from_encounter(encounter: dict[str, Any]) -> EncounterBudget | None:
    raw_budget = encounter.get("budget")
    if raw_budget is None:
        return None
    if not isinstance(raw_budget, dict):
        raise ValueError("budget must be an object")
    party_size = int(raw_budget.get("party_size", 0))
    party_level = int(raw_budget.get("party_level", 0))
    difficulty = str(raw_budget.get("difficulty", "")).casefold()
    return calculate_xp_budget(
        party_size=party_size,
        party_level=party_level,
        difficulty=difficulty,
    )


def calculate_xp_budget(
    *,
    party_size: int,
    party_level: int,
    difficulty: str,
) -> EncounterBudget:
    if party_size <= 0:
        raise ValueError("party_size must be positive")
    if party_level not in XP_BUDGET_PER_CHARACTER:
        raise ValueError("party_level must be between 1 and 20")
    difficulty = difficulty.casefold()
    if difficulty not in XP_BUDGET_PER_CHARACTER[party_level]:
        allowed = ", ".join(sorted(XP_BUDGET_PER_CHARACTER[party_level]))
        raise ValueError(f"difficulty must be one of: {allowed}")
    per_character = XP_BUDGET_PER_CHARACTER[party_level][difficulty]
    return EncounterBudget(
        party_size=party_size,
        party_level=party_level,
        difficulty=difficulty,
        max_xp=per_character * party_size,
    )


def calculate_cr_budget(
    *,
    party_size: int,
    party_level: int,
    difficulty: str,
) -> EncounterBudget:
    return calculate_xp_budget(
        party_size=party_size,
        party_level=party_level,
        difficulty=difficulty,
    )


def xp_for_cr(value: object, *, cr0_xp: int | None = None) -> int:
    cr = cr_fraction(value)
    if cr == 0:
        if cr0_xp not in {0, 10}:
            raise ValueError("CR 0 monsters require explicit xp 0 or 10")
        return cr0_xp
    if cr not in XP_BY_CR:
        raise ValueError(f"unsupported Challenge Rating for XP budget: {value}")
    return XP_BY_CR[cr]


def cr_fraction(value: object) -> Fraction:
    return Fraction(str(value))

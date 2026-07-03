from __future__ import annotations

FULL_CASTER_SLOTS = {
    1: {"1": 2},
    2: {"1": 3},
    3: {"1": 4, "2": 2},
    4: {"1": 4, "2": 3},
    5: {"1": 4, "2": 3, "3": 2},
    6: {"1": 4, "2": 3, "3": 3},
    7: {"1": 4, "2": 3, "3": 3, "4": 1},
    8: {"1": 4, "2": 3, "3": 3, "4": 2},
    9: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 1},
    10: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2},
    11: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1},
    12: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1},
    13: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1},
    14: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1},
    15: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1, "8": 1},
    16: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1, "8": 1},
    17: {
        "1": 4,
        "2": 3,
        "3": 3,
        "4": 3,
        "5": 2,
        "6": 1,
        "7": 1,
        "8": 1,
        "9": 1,
    },
    18: {
        "1": 4,
        "2": 3,
        "3": 3,
        "4": 3,
        "5": 3,
        "6": 1,
        "7": 1,
        "8": 1,
        "9": 1,
    },
    19: {
        "1": 4,
        "2": 3,
        "3": 3,
        "4": 3,
        "5": 3,
        "6": 2,
        "7": 1,
        "8": 1,
        "9": 1,
    },
    20: {
        "1": 4,
        "2": 3,
        "3": 3,
        "4": 3,
        "5": 3,
        "6": 2,
        "7": 2,
        "8": 1,
        "9": 1,
    },
}
HALF_CASTER_SLOTS = {
    1: {},
    2: {"1": 2},
    3: {"1": 3},
    4: {"1": 3},
    5: {"1": 4, "2": 2},
    6: {"1": 4, "2": 2},
    7: {"1": 4, "2": 3},
    8: {"1": 4, "2": 3},
    9: {"1": 4, "2": 3, "3": 2},
    10: {"1": 4, "2": 3, "3": 2},
    11: {"1": 4, "2": 3, "3": 3},
    12: {"1": 4, "2": 3, "3": 3},
    13: {"1": 4, "2": 3, "3": 3, "4": 1},
    14: {"1": 4, "2": 3, "3": 3, "4": 1},
    15: {"1": 4, "2": 3, "3": 3, "4": 2},
    16: {"1": 4, "2": 3, "3": 3, "4": 2},
    17: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 1},
    18: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 1},
    19: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2},
    20: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2},
}
WARLOCK_PACT_SLOTS = {
    1: {"1": 1},
    2: {"1": 2},
    3: {"2": 2},
    4: {"2": 2},
    5: {"3": 2},
    6: {"3": 2},
    7: {"4": 2},
    8: {"4": 2},
    9: {"5": 2},
    10: {"5": 2},
    11: {"5": 3},
    12: {"5": 3},
    13: {"5": 3},
    14: {"5": 3},
    15: {"5": 3},
    16: {"5": 3},
    17: {"5": 4},
    18: {"5": 4},
    19: {"5": 4},
    20: {"5": 4},
}

FULL_CASTERS = {"bard", "cleric", "druid", "sorcerer", "wizard"}
HALF_CASTERS = {"paladin", "ranger"}


def spell_slot_maxima_for_class_levels(class_levels: dict[str, int]) -> dict[str, int]:
    maxima: dict[str, int] = {}
    full_caster_level = 0
    half_caster_levels: list[int] = []
    for class_name, level in class_levels.items():
        capped_level = min(20, max(1, int(level)))
        if class_name in FULL_CASTERS:
            full_caster_level += capped_level
        elif class_name in HALF_CASTERS:
            half_caster_levels.append(capped_level)
        elif class_name == "warlock":
            _merge_slots(maxima, WARLOCK_PACT_SLOTS[capped_level])
    if full_caster_level:
        effective_level = min(
            20, full_caster_level + sum(level // 2 for level in half_caster_levels)
        )
        _merge_slots(maxima, FULL_CASTER_SLOTS[effective_level])
    else:
        for level in half_caster_levels:
            _merge_slots(maxima, HALF_CASTER_SLOTS[level])
    return maxima


def warlock_pact_slot_maxima_for_class_levels(class_levels: dict[str, int]) -> dict[str, int]:
    warlock_level = int(class_levels.get("warlock", 0))
    if warlock_level <= 0:
        return {}
    return dict(WARLOCK_PACT_SLOTS[min(20, max(1, warlock_level))])


def _merge_slots(target: dict[str, int], source: dict[str, int]) -> None:
    for level, count in source.items():
        target[level] = max(target.get(level, 0), count)

from __future__ import annotations

DIFFICULTY_TIERS: dict[str, int] = {
    "very_easy": 5,
    "easy": 10,
    "medium": 15,
    "hard": 20,
    "very_hard": 25,
    "nearly_impossible": 30,
}


def resolve_dc(
    *,
    difficulty_tier: str | None = None,
    dc_ref: str | None = None,
    dc_table: dict[str, int] | None = None,
) -> tuple[int, str]:
    if difficulty_tier is not None:
        if difficulty_tier not in DIFFICULTY_TIERS:
            raise ValueError(f"unknown difficulty tier: {difficulty_tier}")
        return DIFFICULTY_TIERS[difficulty_tier], f"difficulty_tier:{difficulty_tier}"
    if dc_ref is not None:
        table = dc_table or {}
        if dc_ref not in table:
            raise ValueError(f"unknown dc_ref: {dc_ref}")
        return table[dc_ref], f"dc_ref:{dc_ref}"
    raise ValueError("difficulty_tier or dc_ref is required")

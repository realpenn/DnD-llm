from __future__ import annotations

from fractions import Fraction

import pytest

from dnd_llm.content.encounter_budget import calculate_xp_budget, xp_for_cr


def test_calculate_xp_budget_uses_srd_budget_per_character_table() -> None:
    low = calculate_xp_budget(party_size=4, party_level=1, difficulty="low")
    moderate = calculate_xp_budget(party_size=5, party_level=3, difficulty="moderate")
    high = calculate_xp_budget(party_size=6, party_level=15, difficulty="high")

    assert low.max_xp == 200
    assert moderate.max_xp == 1125
    assert high.max_xp == 46800
    assert high.to_dict() == {
        "party_size": 6,
        "party_level": 15,
        "difficulty": "high",
        "max_xp": 46800,
    }


def test_xp_for_cr_uses_srd_experience_by_challenge_rating_table() -> None:
    assert xp_for_cr(Fraction(1, 8)) == 25
    assert xp_for_cr(Fraction(11)) == 7200
    assert xp_for_cr(Fraction(30)) == 155000
    assert xp_for_cr(0, cr0_xp=10) == 10
    with pytest.raises(ValueError, match="CR 0"):
        xp_for_cr(0)


def test_calculate_xp_budget_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="party_size"):
        calculate_xp_budget(party_size=0, party_level=1, difficulty="low")
    with pytest.raises(ValueError, match="party_level"):
        calculate_xp_budget(party_size=4, party_level=0, difficulty="low")
    with pytest.raises(ValueError, match="difficulty"):
        calculate_xp_budget(party_size=4, party_level=1, difficulty="easy")

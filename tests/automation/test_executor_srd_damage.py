from __future__ import annotations

import re

from dnd_llm.core.automation.definitions import ActionDefinition
from dnd_llm.core.automation.executor import AutomationExecutor
from dnd_llm.core.compendium.loader import CompendiumLoader
from dnd_llm.core.dice import RollDie, RollResult
from dnd_llm.core.persistence import AuditLog


class _FixedRollService:
    def __init__(self, values: list[int]) -> None:
        self.values = values
        self.counter = 0
        self.expressions: list[str] = []

    def roll(self, expression: str, advantage: str | None = None) -> RollResult:
        self.expressions.append(expression)
        total = 0
        modifier = 0
        dice: list[RollDie] = []
        for match in re.finditer(
            r"([+-]?)(?:(\d*)d(\d+)|(\d+))",
            expression.replace(" ", ""),
            re.IGNORECASE,
        ):
            sign = -1 if match.group(1) == "-" else 1
            if match.group(3) is not None:
                count = int(match.group(2) or "1")
                sides = int(match.group(3))
                for _ in range(count):
                    value = self.values.pop(0)
                    dice.append(RollDie(sides=sides, value=value, kept=True))
                    total += sign * value
            else:
                value = sign * int(match.group(4))
                modifier += value
                total += value
        counter = self.counter
        self.counter += 1
        return RollResult(
            roll_id=f"fixed-{counter}",
            expression=expression,
            seed=0,
            counter=counter,
            advantage=advantage,
            dice=dice,
            modifier_total=modifier,
            total=total,
            display=f"{expression}: fixed => {total}",
        )


def _damage_action(
    *,
    amount: int,
    attack: bool = False,
    damage_type: str = "slashing",
) -> ActionDefinition:
    automation: list[dict[str, object]] = [{"type": "target", "mode": "explicit"}]
    if attack:
        automation.append({"type": "attack_roll", "attack_bonus": 10, "ability": "str"})
    automation.append(
        {
            "type": "damage",
            "amount": amount,
            "damage_type": damage_type,
            "requires_hit": attack,
        }
    )
    return ActionDefinition(
        id="test.srd_damage",
        name="SRD Damage",
        localization={"en": "SRD Damage", "zh": "SRD 伤害", "aliases": []},
        source="test",
        rules_version="srd-5.2.1",
        action_type="weapon_attack" if attack else "test",
        action_economy="none",
        range={"normal_ft": 5},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=automation,
    )


def test_damage_at_zero_hp_adds_one_death_save_failure_and_syncs_character(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    combatant = state.encounter.combatants["pc2"]
    character = state.characters["pc2"]
    combatant.hp_current = character.hp_current = 0
    combatant.stable = character.stable = True

    result = AutomationExecutor(state, _FixedRollService([]), AuditLog()).execute(
        _damage_action(amount=1),
        actor_id="pc1",
        targets=["pc2"],
        idempotency_key="zero-hp-damage",
    )

    change = next(item for item in result.state_changes if item["type"] == "damage_at_zero_hp")
    assert change["death_save_failures_added"] == 1
    assert combatant.death_save_failures == character.death_save_failures == 1
    assert combatant.stable is character.stable is False
    assert combatant.dead is character.dead is False


def test_critical_damage_at_zero_hp_adds_two_death_save_failures(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    combatant = state.encounter.combatants["pc2"]
    character = state.characters["pc2"]
    combatant.hp_current = character.hp_current = 0

    result = AutomationExecutor(state, _FixedRollService([20]), AuditLog()).execute(
        _damage_action(amount=1, attack=True),
        actor_id="pc1",
        targets=["pc2"],
        idempotency_key="zero-hp-critical",
    )

    change = next(item for item in result.state_changes if item["type"] == "damage_at_zero_hp")
    assert change["critical"] is True
    assert change["death_save_failures_added"] == 2
    assert combatant.death_save_failures == character.death_save_failures == 2


def test_massive_damage_kills_character_and_syncs_combatant(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    combatant = state.encounter.combatants["pc2"]
    character = state.characters["pc2"]
    combatant.hp_current = character.hp_current = 5
    combatant.hp_max = character.hp_max = 8

    result = AutomationExecutor(state, _FixedRollService([]), AuditLog()).execute(
        _damage_action(amount=13),
        actor_id="pc1",
        targets=["pc2"],
        idempotency_key="massive-damage",
    )

    change = next(item for item in result.state_changes if item["type"] == "damage_at_zero_hp")
    assert change["massive_damage"] is True
    assert combatant.dead is character.dead is True
    assert combatant.death_save_failures == character.death_save_failures == 3


def test_zero_hp_damage_does_not_give_monster_death_save_failures(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    monster = state.encounter.combatants["goblin1"]
    monster.hp_current = 0

    result = AutomationExecutor(state, _FixedRollService([]), AuditLog()).execute(
        _damage_action(amount=20),
        actor_id="pc1",
        targets=["goblin1"],
        idempotency_key="monster-zero-hp-damage",
    )

    assert not any(item["type"] == "damage_at_zero_hp" for item in result.state_changes)
    assert monster.death_save_failures == 0
    assert monster.dead is False


def test_dynamic_damage_dice_double_on_critical_without_doubling_modifier(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"monk": 1}
    state.encounter.combatants["goblin1"].hp_current = 20
    state.encounter.combatants["goblin1"].hp_max = 20
    action = CompendiumLoader("rules_data").load().action("srd.monk_unarmed_strike")

    result = AutomationExecutor(state, _FixedRollService([20, 3, 4]), AuditLog()).execute(
        action,
        actor_id="pc1",
        targets=["goblin1"],
        idempotency_key="martial-arts-critical",
    )

    damage = next(item for item in result.state_changes if item["type"] == "damage")
    assert damage["amount"] == 9
    assert [roll["expression"] for roll in result.dice_rolls] == ["1d20+4", "1d6", "1d6"]


def test_resistance_and_vulnerability_cancel_each_other(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    target = state.encounter.combatants["goblin1"]
    target.hp_current = target.hp_max = 20
    target.resistances = ["fire"]
    target.vulnerabilities = ["fire"]

    result = AutomationExecutor(state, _FixedRollService([]), AuditLog()).execute(
        _damage_action(amount=10, damage_type="fire"),
        actor_id="pc1",
        targets=["goblin1"],
        idempotency_key="resistance-vulnerability",
    )

    damage = next(item for item in result.state_changes if item["type"] == "damage")
    assert damage["applied"] == 10
    assert target.hp_current == 10


def test_death_ward_refreshes_hp_and_applied_after_composite_damage(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    target = state.encounter.combatants["pc2"]
    character = state.characters["pc2"]
    target.hp_current = character.hp_current = 4
    target.status_effects.extend(
        [
            {
                "effect_id": "death-ward-test",
                "source_action_id": "srd.death_ward",
                "target_id": "pc2",
                "applied_by": "pc1",
                "passive_modifiers": {"death_ward": True},
            },
            {
                "effect_id": "hunters-mark-test",
                "source_action_id": "srd.hunters_mark",
                "target_id": "pc2",
                "applied_by": "pc1",
                "passive_modifiers": {
                    "hunters_mark": True,
                    "attacker_bonus_damage": "1d6",
                    "damage_type": "force",
                },
            },
        ]
    )
    action = ActionDefinition(
        id="test.composite_damage",
        name="Composite Damage",
        localization={"en": "Composite Damage", "zh": "复合伤害", "aliases": []},
        source="test",
        rules_version="srd-5.2.1",
        action_type="weapon_attack",
        action_economy="none",
        range={"normal_ft": 5},
        target_policy={"min": 1, "max": 1, "harmful": True},
        automation=[
            {"type": "target", "mode": "explicit"},
            {"type": "attack_roll", "attack_bonus": 10, "ability": "str"},
            {
                "type": "damage",
                "dice": "1d6",
                "damage_type": "slashing",
                "requires_hit": True,
            },
        ],
    )

    rolls = _FixedRollService([10, 3, 3])
    result = AutomationExecutor(state, rolls, AuditLog()).execute(
        action,
        actor_id="pc1",
        targets=["pc2"],
        idempotency_key="death-ward-composite",
    )

    damage = next(item for item in result.state_changes if item["type"] == "damage")
    assert any(item["type"] == "death_ward" for item in result.state_changes)
    assert target.hp_current == character.hp_current == 1
    assert damage["hp_after"] == 1
    assert damage["total_applied"] == 3
    assert (
        damage["applied"] + sum(item["applied"] for item in damage["extra_damage"])
        == damage["total_applied"]
    )
    assert rolls.expressions == ["1d20+10", "1d6", "1d6"]

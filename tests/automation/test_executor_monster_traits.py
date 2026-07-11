from __future__ import annotations

import copy
import re

from dnd_llm.core.automation.executor import AutomationExecutor
from dnd_llm.core.compendium.loader import CompendiumLoader
from dnd_llm.core.dice import RollDie, RollResult
from dnd_llm.core.models import Combatant, Monster
from dnd_llm.core.persistence import AuditLog


class _FixedRollService:
    def __init__(self, values: list[int]) -> None:
        self.values = values
        self.counter = 0

    def roll(self, expression: str, advantage: str | None = None) -> RollResult:
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


def test_pack_tactics_grants_advantage_with_non_incapacitated_ally(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.monsters["warrior"] = Monster(
        id="warrior",
        name="Warrior Infantry",
        abilities={"str": 13, "dex": 11, "con": 11, "int": 8, "wis": 11, "cha": 8},
        hp_current=9,
        hp_max=9,
        armor_class=13,
        actions=["srd.warrior_infantry_pack_tactics", "srd.warrior_infantry_spear"],
    )
    state.encounter.combatants["warrior-combatant"] = Combatant(
        id="warrior-combatant",
        entity_id="warrior",
        name="Warrior Infantry",
        side="monsters",
        hp_current=9,
        hp_max=9,
        armor_class=13,
        position_node_id="cover",
        actions=["srd.warrior_infantry_pack_tactics", "srd.warrior_infantry_spear"],
    )
    state.encounter.combatants["warrior-ally"] = Combatant(
        id="warrior-ally",
        entity_id="warrior-ally",
        name="Warrior Ally",
        side="monsters",
        hp_current=9,
        hp_max=9,
        armor_class=13,
        position_node_id="front",
    )
    action = CompendiumLoader("rules_data").load().action("srd.warrior_infantry_spear")

    result = AutomationExecutor(state, _FixedRollService([12]), AuditLog()).execute(
        action,
        actor_id="warrior-combatant",
        targets=["pc1"],
        idempotency_key="pack-tactics",
    )

    attack = result.node_results["automation[1]"]
    assert result.dice_rolls[0]["advantage"] == "advantage"
    assert any(
        source.get("source_action_id") == "srd.warrior_infantry_pack_tactics"
        for source in attack["status_sources"]
    )


def test_pack_tactics_ignores_incapacitated_ally(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    actor = state.encounter.combatants["goblin1"]
    actor.actions = ["srd.warrior_infantry_pack_tactics", "srd.warrior_infantry_spear"]
    ally = Combatant(
        id="warrior-ally",
        entity_id="warrior-ally",
        name="Warrior Ally",
        side="monsters",
        hp_current=9,
        hp_max=9,
        armor_class=13,
        position_node_id="front",
        status_effects=[{"effect_id": "stunned", "condition": "stunned"}],
    )
    state.encounter.combatants[ally.id] = ally
    action = CompendiumLoader("rules_data").load().action("srd.warrior_infantry_spear")

    result = AutomationExecutor(state, _FixedRollService([12]), AuditLog()).execute(
        action,
        actor_id="goblin1",
        targets=["pc1"],
        idempotency_key="pack-tactics-incapacitated",
    )

    assert result.dice_rolls[0]["advantage"] is None


def test_pack_tactics_ignores_dead_ally(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    actor = state.encounter.combatants["goblin1"]
    actor.actions = ["srd.warrior_infantry_pack_tactics", "srd.warrior_infantry_spear"]
    state.encounter.combatants["warrior-ally"] = Combatant(
        id="warrior-ally",
        entity_id="warrior-ally",
        name="Warrior Ally",
        side="monsters",
        hp_current=0,
        hp_max=9,
        armor_class=13,
        position_node_id="front",
        dead=True,
    )
    action = CompendiumLoader("rules_data").load().action("srd.warrior_infantry_spear")

    result = AutomationExecutor(state, _FixedRollService([12]), AuditLog()).execute(
        action,
        actor_id="goblin1",
        targets=["pc1"],
        idempotency_key="pack-tactics-dead-ally",
    )

    assert result.dice_rolls[0]["advantage"] is None


def test_bandit_captain_parry_turns_one_melee_hit_into_miss(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.monsters["captain"] = Monster(
        id="captain",
        name="Bandit Captain",
        abilities={"str": 15, "dex": 16, "con": 14, "int": 14, "wis": 11, "cha": 14},
        hp_current=52,
        hp_max=52,
        armor_class=15,
        actions=["srd.bandit_captain_scimitar", "srd.bandit_captain_parry"],
    )
    captain = Combatant(
        id="captain-combatant",
        entity_id="captain",
        name="Bandit Captain",
        side="monsters",
        hp_current=52,
        hp_max=52,
        armor_class=15,
        position_node_id="cover",
        actions=["srd.bandit_captain_scimitar", "srd.bandit_captain_parry"],
    )
    state.encounter.combatants[captain.id] = captain
    action = copy.deepcopy(CompendiumLoader("rules_data").load().action("srd.shortsword_attack"))
    action.action_economy = "none"
    executor = AutomationExecutor(state, _FixedRollService([11, 11, 3]), AuditLog())

    first = executor.execute(
        action,
        actor_id="pc1",
        targets=[captain.id],
        idempotency_key="captain-parry-first",
    )
    second = executor.execute(
        action,
        actor_id="pc1",
        targets=[captain.id],
        idempotency_key="captain-parry-second",
    )

    first_attack = first.node_results["automation[1]"]
    assert first_attack["hit"] is False
    assert first_attack["ac"] == 17
    assert first_attack["parry"]["hit_before"] is True
    assert state.encounter.action_budgets[captain.id]["reaction"] == 0
    assert second.node_results["automation[1]"]["hit"] is True
    assert captain.hp_current == 46

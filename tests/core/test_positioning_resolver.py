from __future__ import annotations

from dnd_llm.core.compendium.loader import CompendiumLoader
from dnd_llm.core.models import Combatant
from dnd_llm.core.positioning import PositionEdge, PositionNode, TacticalGraph
from dnd_llm.core.resolver import ActionResolver, PlayerActionDraft


def test_tactical_graph_distance_area_and_opportunity(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    graph = TacticalGraph.from_dict(state.encounter.tactical_graph or {})

    assert graph.shortest_distance("front", "back") == 35
    assert graph.area_nodes("front", 5) == {"front", "cover"}
    assert graph.opportunity_attack_triggers(
        actor_from="front",
        actor_to="back",
        enemy_positions={"goblin1": "cover"},
        enemy_reach_ft={"goblin1": 5},
    ) == ["goblin1"]


def test_resolver_accepts_legal_and_rejects_out_of_range(make_state) -> None:
    state = make_state()
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    legal = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="短剑",
            target_ids=["goblin1"],
            candidate_action_id="srd.shortsword_attack",
        )
    )
    assert legal.status == "accepted"

    assert state.encounter is not None
    state.encounter.combatants["goblin1"].position_node_id = "back"
    out_of_range = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="短剑",
            target_ids=["goblin1"],
            candidate_action_id="srd.shortsword_attack",
        )
    )
    assert out_of_range.status == "rejected"
    assert out_of_range.reason == "target out of range"


def test_resolver_extends_selected_eldritch_blast_range_with_eldritch_spear(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"warlock": 2}
    state.characters["pc1"].actions = [
        "srd.eldritch_blast",
        "srd.eldritch_invocations",
        "srd.magical_cunning",
    ]
    state.encounter.tactical_graph = TacticalGraph(
        nodes={
            "front": PositionNode("front", "Front"),
            "far": PositionNode("far", "Far"),
        },
        edges=[PositionEdge("front", "far", 150)],
    ).to_dict()
    state.encounter.combatants["goblin1"].position_node_id = "far"
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    base_range = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="eldritch blast",
            target_ids=["goblin1"],
            candidate_action_id="srd.eldritch_blast",
        )
    )
    assert base_range.status == "rejected"
    assert base_range.reason == "target out of range"

    state.characters["pc1"].feature_choices = {
        "warlock.eldritch_invocation.eldritch_spear.cantrip": "srd.spell.eldritch_blast"
    }
    state.characters["pc1"].actions.append("srd.eldritch_spear")
    extended_range = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="eldritch blast",
            target_ids=["goblin1"],
            candidate_action_id="srd.eldritch_blast",
        )
    )
    assert extended_range.status == "accepted"


def test_resolver_accepts_selected_repelling_blast_push_destination(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    assert state.encounter.tactical_graph is not None
    state.encounter.tactical_graph["nodes"]["far"] = {
        "node_id": "far",
        "name": "Far",
        "tags": [],
        "capacity": None,
        "default_cover": "none",
        "terrain": "normal",
    }
    state.encounter.tactical_graph["edges"].append(
        {
            "source": "cover",
            "target": "far",
            "distance_ft": 10,
            "movement_cost": None,
            "line_of_sight": True,
            "cover": "none",
            "difficult_terrain": False,
        }
    )
    state.characters["pc1"].class_levels = {"warlock": 2}
    state.characters["pc1"].feature_choices = {
        "warlock.eldritch_invocation.repelling_blast.cantrip": "srd.spell.eldritch_blast"
    }
    state.characters["pc1"].actions = [
        "srd.eldritch_blast",
        "srd.eldritch_invocations",
        "srd.magical_cunning",
        "srd.repelling_blast",
    ]
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    accepted = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="eldritch blast",
            target_ids=["goblin1"],
            candidate_action_id="srd.eldritch_blast",
            params={
                "use_repelling_blast": True,
                "repelling_blast_to_position_node_id": "far",
            },
        )
    )
    assert accepted.status == "accepted"

    state.characters["pc1"].actions.remove("srd.repelling_blast")
    state.characters["pc1"].feature_choices = {}
    rejected = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="eldritch blast",
            target_ids=["goblin1"],
            candidate_action_id="srd.eldritch_blast",
            params={
                "use_repelling_blast": True,
                "repelling_blast_to_position_node_id": "far",
            },
        )
    )
    assert rejected.status == "rejected"
    assert rejected.reason == "Repelling Blast requires the selected Warlock invocation"


def test_resolver_rejects_repelling_blast_push_over_10_feet(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"warlock": 2}
    state.characters["pc1"].feature_choices = {
        "warlock.eldritch_invocation.repelling_blast.cantrip": "srd.spell.eldritch_blast"
    }
    state.characters["pc1"].actions = [
        "srd.eldritch_blast",
        "srd.eldritch_invocations",
        "srd.magical_cunning",
        "srd.repelling_blast",
    ]
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="eldritch blast",
            target_ids=["goblin1"],
            candidate_action_id="srd.eldritch_blast",
            params={
                "use_repelling_blast": True,
                "repelling_blast_to_position_node_id": "back",
            },
        )
    )

    assert result.status == "rejected"
    assert result.reason == "Repelling Blast cannot exceed 10 feet"


def test_resolver_accepts_legal_preserve_life_distribution(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"cleric": 3}
    state.characters["pc1"].subclasses = {"cleric": "life"}
    state.characters["pc1"].actions.append("srd.preserve_life")
    state.characters["pc1"].resources["srd.resource.channel_divinity"] = 2
    state.characters["pc2"].hp_current = 1
    state.characters["pc2"].hp_max = 8
    state.encounter.combatants["pc2"].hp_current = 1
    state.encounter.combatants["pc2"].hp_max = 8
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="preserve life",
            target_ids=["pc2"],
            candidate_action_id="srd.preserve_life",
            params={"preserve_life_points": {"pc2": 3}},
        )
    )

    assert result.status == "accepted"


def test_resolver_rejects_preserve_life_above_half_hp(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"cleric": 3}
    state.characters["pc1"].subclasses = {"cleric": "life"}
    state.characters["pc1"].actions.append("srd.preserve_life")
    state.characters["pc1"].resources["srd.resource.channel_divinity"] = 2
    state.characters["pc2"].hp_current = 1
    state.characters["pc2"].hp_max = 8
    state.encounter.combatants["pc2"].hp_current = 1
    state.encounter.combatants["pc2"].hp_max = 8
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="preserve life",
            target_ids=["pc2"],
            candidate_action_id="srd.preserve_life",
            params={"preserve_life_points": {"pc2": 4}},
        )
    )

    assert result.status == "rejected"
    assert result.reason == "Preserve Life cannot heal a target above half HP"


def test_resolver_rejects_preserve_life_out_of_range(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"cleric": 3}
    state.characters["pc1"].subclasses = {"cleric": "life"}
    state.characters["pc1"].actions.append("srd.preserve_life")
    state.characters["pc1"].resources["srd.resource.channel_divinity"] = 2
    state.characters["pc2"].hp_current = 1
    state.characters["pc2"].hp_max = 8
    state.encounter.combatants["pc2"].hp_current = 1
    state.encounter.combatants["pc2"].hp_max = 8
    state.encounter.combatants["pc2"].position_node_id = "back"
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="preserve life",
            target_ids=["pc2"],
            candidate_action_id="srd.preserve_life",
            params={"preserve_life_points": {"pc2": 3}},
        )
    )

    assert result.status == "rejected"
    assert result.reason == "target out of range"


def test_resolver_blocks_pvp_by_default(make_state) -> None:
    state = make_state()
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="短剑",
            target_ids=["pc2"],
            candidate_action_id="srd.shortsword_attack",
        )
    )

    assert result.status == "rejected"
    assert result.reason == "pvp is disabled"


def test_resolver_rejects_hallucinated_action_id(make_state) -> None:
    state = make_state()
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="imaginary",
            target_ids=["goblin1"],
            candidate_action_id="srd.not_a_real_action",
        )
    )

    assert result.status == "ambiguous"
    assert result.reason == "no matching action"


def test_resolver_rejects_insufficient_spell_slot(make_state) -> None:
    state = make_state()
    state.characters["pc1"].actions.append("srd.fireball")
    state.characters["pc1"].spell_slots["3"] = 0
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="火球",
            target_ids=["goblin1"],
            candidate_action_id="srd.fireball",
        )
    )

    assert result.status == "rejected"
    assert result.reason == "insufficient spell slot"


def test_resolver_rejects_spell_slot_below_spell_base_level(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"druid": 7}
    character.actions.append("srd.blight")
    character.spell_slots["3"] = 1
    character.spell_slots["4"] = 1
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="枯萎术",
            target_ids=["goblin1"],
            candidate_action_id="srd.blight",
            params={"slot_level": 3},
        )
    )

    assert result.status == "rejected"
    assert result.reason == "spell requires level 4 slot or higher"


def test_resolver_scales_spell_target_cap_with_requested_slot_level(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"wizard": 9}
    character.actions.append("srd.hold_monster")
    character.spell_slots["5"] = 1
    character.spell_slots["6"] = 1
    state.encounter.combatants["goblin2"] = Combatant(
        id="goblin2",
        entity_id="goblin2",
        name="Goblin 2",
        side="monsters",
        hp_current=7,
        hp_max=7,
        armor_class=12,
        position_node_id="cover",
    )
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    base_slot = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="怪物定身术",
            target_ids=["goblin1", "goblin2"],
            candidate_action_id="srd.hold_monster",
            params={"slot_level": 5},
        )
    )
    upcast = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="怪物定身术",
            target_ids=["goblin1", "goblin2"],
            candidate_action_id="srd.hold_monster",
            params={"slot_level": 6},
        )
    )

    assert base_slot.status == "rejected"
    assert base_slot.reason == "too many targets"
    assert upcast.status == "accepted"
    assert upcast.action_id == "srd.hold_monster"


def test_resolver_checks_greater_restoration_choice_and_component_cost(
    make_state,
) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"cleric": 9}
    character.actions.append("srd.greater_restoration")
    character.spell_slots["5"] = 1
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    missing_choice = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="高等复原术",
            target_ids=["pc2"],
            candidate_action_id="srd.greater_restoration",
            params={"slot_level": 5},
        )
    )
    no_gold = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="高等复原术",
            target_ids=["pc2"],
            candidate_action_id="srd.greater_restoration",
            params={"slot_level": 5, "greater_restoration_choice": "exhaustion"},
        )
    )
    character.gold = 100
    accepted = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="高等复原术",
            target_ids=["pc2"],
            candidate_action_id="srd.greater_restoration",
            params={"slot_level": 5, "greater_restoration_choice": "exhaustion"},
        )
    )

    assert missing_choice.status == "rejected"
    assert missing_choice.reason == "missing required parameter greater_restoration_choice"
    assert no_gold.status == "rejected"
    assert no_gold.reason == "insufficient gold"
    assert accepted.status == "accepted"
    assert accepted.action_id == "srd.greater_restoration"


def test_resolver_rejects_font_of_inspiration_when_bardic_inspiration_full(
    make_state,
) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"bard": 5}
    character.abilities["cha"] = 16
    character.actions.append("srd.font_of_inspiration_restore_bardic_inspiration_slot_1")
    character.resources["srd.resource.bardic_inspiration"] = 3
    character.spell_slots["1"] = 1
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    full = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="恢复吟游激励",
            candidate_action_id="srd.font_of_inspiration_restore_bardic_inspiration_slot_1",
        )
    )

    assert full.status == "rejected"
    assert full.reason == "resource srd.resource.bardic_inspiration would exceed maximum 3"

    character.resources["srd.resource.bardic_inspiration"] = 2
    available = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="恢复吟游激励",
            candidate_action_id="srd.font_of_inspiration_restore_bardic_inspiration_slot_1",
        )
    )

    assert available.status == "accepted"


def test_resolver_checks_cunning_strike_poison_requires_poisoners_kit(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"rogue": 5}
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    missing_kit = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="狡诈毒击",
            target_ids=["goblin1"],
            candidate_action_id="srd.shortsword_attack",
            params={"use_sneak_attack": True, "cunning_strike": "poison"},
        )
    )

    assert missing_kit.status == "rejected"
    assert missing_kit.reason == "Cunning Strike Poison requires a Poisoner's Kit"

    character.inventory["srd.poisoners_kit"] = 1
    accepted = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="狡诈毒击",
            target_ids=["goblin1"],
            candidate_action_id="srd.shortsword_attack",
            params={"use_sneak_attack": True, "cunning_strike": "poison"},
        )
    )

    assert accepted.status == "accepted"


def test_resolver_rejects_cunning_strike_withdraw_over_half_speed(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"rogue": 5}
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    too_far = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="狡诈撤离",
            target_ids=["goblin1"],
            candidate_action_id="srd.shortsword_attack",
            params={
                "use_sneak_attack": True,
                "cunning_strike": "withdraw",
                "cunning_strike_withdraw_to_position_node_id": "back",
            },
        )
    )

    assert too_far.status == "rejected"
    assert too_far.reason == "Cunning Strike Withdraw movement cannot exceed half Speed"


def test_resolver_accepts_uncanny_dodge_on_visible_attack_hit_context(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"rogue": 5}
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="goblin1",
            verb="强盗弯刀",
            target_ids=["pc1"],
            candidate_action_id="srd.bandit_scimitar",
            params={"use_uncanny_dodge": True},
        )
    )

    assert result.status == "accepted"
    assert result.action_id == "srd.bandit_scimitar"


def test_resolver_rejects_uncanny_dodge_without_reaction(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"rogue": 5}
    state.encounter.action_budgets["pc1"] = {
        "action": 1,
        "bonus_action": 1,
        "reaction": 0,
        "movement": 30,
        "movement_used": 0,
        "free": 1,
    }
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="goblin1",
            verb="强盗弯刀",
            target_ids=["pc1"],
            candidate_action_id="srd.bandit_scimitar",
            params={"use_uncanny_dodge": True},
        )
    )

    assert result.status == "rejected"
    assert result.reason == "insufficient reaction economy"


def test_resolver_rejects_uncanny_dodge_for_non_rogue_target(make_state) -> None:
    state = make_state()
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="goblin1",
            verb="强盗弯刀",
            target_ids=["pc1"],
            candidate_action_id="srd.bandit_scimitar",
            params={"use_uncanny_dodge": True},
        )
    )

    assert result.status == "rejected"
    assert result.reason == "Uncanny Dodge requires Rogue level 5"


def test_resolver_rejects_spellcasting_blocked_by_passive_effect(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].actions.append("srd.cure_wounds")
    state.characters["pc1"].spell_slots["1"] = 1
    state.encounter.combatants["pc1"].status_effects.append(
        {
            "effect_id": "rage-test",
            "source_action_id": "srd.rage",
            "condition": "raging",
            "passive_modifiers": {"blocks_spellcasting": True},
        }
    )
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="治疗术",
            target_ids=["pc1"],
            candidate_action_id="srd.cure_wounds",
        )
    )

    assert result.status == "rejected"
    assert result.reason == "actor cannot cast spells while affected by srd.rage"


def test_resolver_checks_dynamic_resource_cost_params(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"paladin": 1}
    state.characters["pc1"].actions.append("srd.lay_on_hands")
    state.characters["pc1"].resources["srd.resource.lay_on_hands"] = 5
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    accepted = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="圣疗",
            target_ids=["pc1"],
            candidate_action_id="srd.lay_on_hands",
            params={"lay_on_hands_points": 5},
        )
    )
    too_much = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="圣疗",
            target_ids=["pc1"],
            candidate_action_id="srd.lay_on_hands",
            params={"lay_on_hands_points": 6},
        )
    )
    missing = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="圣疗",
            target_ids=["pc1"],
            candidate_action_id="srd.lay_on_hands",
        )
    )

    assert accepted.status == "accepted"
    assert too_much.status == "rejected"
    assert too_much.reason == "insufficient resource srd.resource.lay_on_hands"
    assert missing.status == "rejected"
    assert missing.reason == "missing required parameter lay_on_hands_points"


def test_resolver_enforces_exclude_self_target_policy(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"bard": 1}
    state.characters["pc1"].actions.append("srd.bardic_inspiration")
    state.characters["pc1"].resources["srd.resource.bardic_inspiration"] = 1
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    self_target = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="吟游灵感",
            target_ids=["pc1"],
            candidate_action_id="srd.bardic_inspiration",
        )
    )
    ally_target = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="吟游灵感",
            target_ids=["pc2"],
            candidate_action_id="srd.bardic_inspiration",
        )
    )

    assert self_target.status == "rejected"
    assert self_target.reason == "target cannot be self"
    assert ally_target.status == "accepted"


def test_resolver_checks_favored_enemy_resource_instead_of_spell_slot(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"ranger": 1}
    state.characters["pc1"].actions.append("srd.favored_enemy_hunters_mark")
    state.characters["pc1"].resources["srd.resource.favored_enemy_hunters_mark"] = 0
    state.characters["pc1"].spell_slots["1"] = 0
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    no_resource = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="宿敌猎人印记",
            target_ids=["goblin1"],
            candidate_action_id="srd.favored_enemy_hunters_mark",
        )
    )
    state.characters["pc1"].resources["srd.resource.favored_enemy_hunters_mark"] = 1
    has_resource = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="宿敌猎人印记",
            target_ids=["goblin1"],
            candidate_action_id="srd.favored_enemy_hunters_mark",
        )
    )

    assert no_resource.status == "rejected"
    assert no_resource.reason == "insufficient resource srd.resource.favored_enemy_hunters_mark"
    assert has_resource.status == "accepted"


def test_resolver_checks_faithful_steed_resource_instead_of_spell_slot(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"paladin": 5}
    state.characters["pc1"].actions.append("srd.faithful_steed_find_steed")
    state.characters["pc1"].resources["srd.resource.faithful_steed"] = 0
    state.characters["pc1"].spell_slots["2"] = 0
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    no_resource = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="免法术位寻找坐骑",
            target_ids=[],
            candidate_action_id="srd.faithful_steed_find_steed",
        )
    )
    state.characters["pc1"].resources["srd.resource.faithful_steed"] = 1
    has_resource = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="免法术位寻找坐骑",
            target_ids=[],
            candidate_action_id="srd.faithful_steed_find_steed",
        )
    )

    assert no_resource.status == "rejected"
    assert no_resource.reason == "insufficient resource srd.resource.faithful_steed"
    assert has_resource.status == "accepted"


def test_resolver_accepts_armor_of_shadows_without_spell_slot(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"warlock": 1}
    state.characters["pc1"].feature_choices = {
        "warlock.eldritch_invocation.armor_of_shadows": "selected"
    }
    state.characters["pc1"].actions.extend(
        ["srd.armor_of_shadows", "srd.armor_of_shadows_mage_armor"]
    )
    state.characters["pc1"].spell_slots["1"] = 0
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="armor of shadows",
            target_ids=[],
            candidate_action_id="srd.armor_of_shadows_mage_armor",
        )
    )

    assert result.status == "accepted"


def test_resolver_accepts_fiendish_vigor_without_spell_slot(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"warlock": 2}
    state.characters["pc1"].feature_choices = {
        "warlock.eldritch_invocation.fiendish_vigor": "selected"
    }
    state.characters["pc1"].actions.extend(["srd.fiendish_vigor", "srd.fiendish_vigor_false_life"])
    state.characters["pc1"].spell_slots["1"] = 0
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="fiendish vigor",
            target_ids=[],
            candidate_action_id="srd.fiendish_vigor_false_life",
        )
    )

    assert result.status == "accepted"


def test_resolver_accepts_mask_of_many_faces_without_spell_slot(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"warlock": 2}
    state.characters["pc1"].feature_choices = {
        "warlock.eldritch_invocation.mask_of_many_faces": "selected"
    }
    state.characters["pc1"].actions.extend(
        ["srd.mask_of_many_faces", "srd.mask_of_many_faces_disguise_self"]
    )
    state.characters["pc1"].spell_slots["1"] = 0
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="mask of many faces",
            target_ids=[],
            candidate_action_id="srd.mask_of_many_faces_disguise_self",
        )
    )

    assert result.status == "accepted"


def test_resolver_accepts_misty_visions_without_spell_slot(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"warlock": 2}
    state.characters["pc1"].feature_choices = {
        "warlock.eldritch_invocation.misty_visions": "selected"
    }
    state.characters["pc1"].actions.extend(["srd.misty_visions", "srd.misty_visions_silent_image"])
    state.characters["pc1"].spell_slots["1"] = 0
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="misty visions",
            target_ids=[],
            candidate_action_id="srd.misty_visions_silent_image",
        )
    )

    assert result.status == "accepted"


def test_resolver_accepts_otherworldly_leap_without_spell_slot(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"warlock": 2}
    state.characters["pc1"].feature_choices = {
        "warlock.eldritch_invocation.otherworldly_leap": "selected"
    }
    state.characters["pc1"].actions.extend(["srd.otherworldly_leap", "srd.otherworldly_leap_jump"])
    state.characters["pc1"].spell_slots["1"] = 0
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="otherworldly leap",
            target_ids=[],
            candidate_action_id="srd.otherworldly_leap_jump",
        )
    )

    assert result.status == "accepted"


def test_resolver_accepts_pact_of_the_chain_find_familiar_without_spell_slot(
    make_state,
) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 1}
    character.feature_choices = {"warlock.eldritch_invocation.pact_of_the_chain": "selected"}
    character.actions.extend(
        ["srd.find_familiar", "srd.pact_of_the_chain", "srd.pact_of_the_chain_find_familiar"]
    )
    character.known_spells = ["srd.spell.find_familiar"]
    character.spell_slots["1"] = 0
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    ordinary = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="find familiar",
            target_ids=[],
            candidate_action_id="srd.find_familiar",
        )
    )
    assert ordinary.status == "rejected"
    assert ordinary.reason == "insufficient spell slot"

    pact = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="pact of the chain find familiar",
            target_ids=[],
            candidate_action_id="srd.pact_of_the_chain_find_familiar",
        )
    )
    assert pact.status == "accepted"
    assert pact.action_id == "srd.pact_of_the_chain_find_familiar"


def test_resolver_requires_investment_chain_master_familiar_speed_choice(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 5}
    character.feature_choices = {
        "warlock.eldritch_invocation.pact_of_the_chain": "selected",
        "warlock.eldritch_invocation.investment_of_the_chain_master": "selected",
    }
    character.actions.extend(
        [
            "srd.pact_of_the_chain",
            "srd.pact_of_the_chain_find_familiar",
            "srd.investment_of_the_chain_master",
        ]
    )
    character.known_spells = ["srd.spell.find_familiar"]
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    missing_choice = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="pact of the chain find familiar",
            target_ids=[],
            candidate_action_id="srd.pact_of_the_chain_find_familiar",
        )
    )
    invalid_choice = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="pact of the chain find familiar",
            target_ids=[],
            candidate_action_id="srd.pact_of_the_chain_find_familiar",
            params={"investment_familiar_speed": "burrow"},
        )
    )
    accepted = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="pact of the chain find familiar",
            target_ids=[],
            candidate_action_id="srd.pact_of_the_chain_find_familiar",
            params={"investment_familiar_speed": "fly"},
        )
    )

    assert missing_choice.status == "rejected"
    assert (
        missing_choice.reason
        == "Investment of the Chain Master requires investment_familiar_speed fly or swim"
    )
    assert invalid_choice.status == "rejected"
    assert (
        invalid_choice.reason
        == "Investment of the Chain Master requires investment_familiar_speed fly or swim"
    )
    assert accepted.status == "accepted"
    assert accepted.action_id == "srd.pact_of_the_chain_find_familiar"


def test_resolver_accepts_pact_of_the_tome_prepared_ritual_without_spell_slot(
    make_state,
) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 1}
    character.feature_choices = {
        "warlock.eldritch_invocation.pact_of_the_tome": "selected",
        "warlock.eldritch_invocation.pact_of_the_tome.cantrip.1": "srd.spell.fire_bolt",
        "warlock.eldritch_invocation.pact_of_the_tome.cantrip.2": "srd.spell.guidance",
        "warlock.eldritch_invocation.pact_of_the_tome.cantrip.3": "srd.spell.mage_hand",
        "warlock.eldritch_invocation.pact_of_the_tome.ritual.1": "srd.spell.detect_magic",
        "warlock.eldritch_invocation.pact_of_the_tome.ritual.2": "srd.spell.speak_with_animals",
    }
    character.actions = [
        "srd.pact_of_the_tome",
        "srd.fire_bolt",
        "srd.guidance",
        "srd.mage_hand",
        "srd.detect_magic",
        "srd.speak_with_animals",
    ]
    character.prepared_spells = [
        "srd.spell.fire_bolt",
        "srd.spell.guidance",
        "srd.spell.mage_hand",
        "srd.spell.detect_magic",
        "srd.spell.speak_with_animals",
    ]
    character.spell_slots["1"] = 0
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    ordinary = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="detect magic",
            target_ids=[],
            candidate_action_id="srd.detect_magic",
        )
    )
    assert ordinary.status == "rejected"
    assert ordinary.reason == "insufficient spell slot"

    ritual = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="detect magic ritual",
            target_ids=[],
            candidate_action_id="srd.detect_magic",
            params={"slot_level": 1, "as_ritual": True},
        )
    )
    assert ritual.status == "accepted"
    assert ritual.action_id == "srd.detect_magic"


def test_resolver_checks_pact_of_the_blade_weapon_selection_and_granted_attack(
    make_state,
) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 1}
    character.feature_choices = {"warlock.eldritch_invocation.pact_of_the_blade": "selected"}
    character.actions = ["srd.pact_of_the_blade", "srd.pact_of_the_blade_weapon"]
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    missing_selection = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="pact of the blade",
            target_ids=[],
            candidate_action_id="srd.pact_of_the_blade_weapon",
        )
    )
    unsupported_selection = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="pact of the blade",
            target_ids=[],
            candidate_action_id="srd.pact_of_the_blade_weapon",
            params={"pact_weapon_action_id": "srd.shortbow_attack"},
        )
    )
    valid_selection = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="pact of the blade",
            target_ids=[],
            candidate_action_id="srd.pact_of_the_blade_weapon",
            params={"pact_weapon_action_id": "srd.longsword_attack"},
        )
    )
    before_binding = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="longsword",
            target_ids=["goblin1"],
            candidate_action_id="srd.longsword_attack",
        )
    )
    assert state.encounter is not None
    state.encounter.combatants["pc1"].status_effects.append(
        {
            "effect_id": "test-pact-weapon",
            "source_action_id": "srd.pact_of_the_blade_weapon",
            "condition": "pact_weapon",
            "passive_modifiers": {
                "pact_weapon": True,
                "pact_weapon_action_id": "srd.longsword_attack",
            },
        }
    )
    after_binding = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="longsword",
            target_ids=["goblin1"],
            candidate_action_id="srd.longsword_attack",
        )
    )

    assert missing_selection.status == "rejected"
    assert missing_selection.reason == "missing required parameter pact_weapon_action_id"
    assert unsupported_selection.status == "rejected"
    assert (
        unsupported_selection.reason
        == "Pact of the Blade weapon must be an implemented SRD melee weapon"
    )
    assert valid_selection.status == "accepted"
    assert before_binding.status == "rejected"
    assert before_binding.reason == "actor does not own action"
    assert after_binding.status == "accepted"
    assert after_binding.action_id == "srd.longsword_attack"


def test_resolver_allows_thirsting_blade_extra_attack_only_after_pact_weapon_attack(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 5}
    character.feature_choices = {
        "warlock.eldritch_invocation.pact_of_the_blade": "selected",
        "warlock.eldritch_invocation.thirsting_blade": "selected",
    }
    character.actions = [
        "srd.pact_of_the_blade",
        "srd.pact_of_the_blade_weapon",
        "srd.thirsting_blade",
    ]
    state.encounter.action_budgets["pc1"] = {
        "action": 0,
        "bonus_action": 1,
        "reaction": 1,
        "movement": 30,
        "movement_used": 0,
        "free": 1,
    }
    state.encounter.combatants["pc1"].status_effects.append(
        {
            "effect_id": "pact-weapon",
            "source_action_id": "srd.pact_of_the_blade_weapon",
            "target_id": "pc1",
            "applied_by": "pc1",
            "condition": "pact_weapon",
            "passive_modifiers": {
                "pact_weapon": True,
                "pact_weapon_action_id": "srd.longsword_attack",
            },
            "duration": {"until": "pact_ends_or_replaced_or_warlock_dies"},
            "tick_on": "weapon_attack",
            "stacking_policy": "replace_condition",
            "audit": {},
        }
    )
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    no_prior_attack = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="longsword",
            target_ids=["goblin1"],
            candidate_action_id="srd.longsword_attack",
            params={"use_thirsting_blade_extra_attack": True},
        )
    )
    assert no_prior_attack.status == "rejected"
    assert no_prior_attack.reason == (
        "Thirsting Blade extra attack requires a prior pact weapon attack this turn"
    )

    state.encounter.combatants["pc1"].status_effects.append(
        {
            "effect_id": "thirsting-prior-attack",
            "source_action_id": "srd.longsword_attack",
            "target_id": "pc1",
            "applied_by": "pc1",
            "condition": "thirsting_blade_pact_weapon_attack_this_turn",
            "duration": {"until": "start_of_next_turn"},
            "tick_on": "self_turn_start",
            "stacking_policy": "append",
            "audit": {
                "pact_weapon_action_id": "srd.longsword_attack",
                "attacked_target_id": "goblin1",
            },
        }
    )
    without_thirsting_param = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="longsword",
            target_ids=["goblin1"],
            candidate_action_id="srd.longsword_attack",
        )
    )
    assert without_thirsting_param.status == "rejected"
    assert without_thirsting_param.reason == "insufficient action economy"

    extra_attack = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="longsword",
            target_ids=["goblin1"],
            candidate_action_id="srd.longsword_attack",
            params={"use_thirsting_blade_extra_attack": True},
        )
    )
    assert extra_attack.status == "accepted"
    assert extra_attack.action_id == "srd.longsword_attack"

    state.encounter.combatants["pc1"].status_effects.append(
        {
            "effect_id": "thirsting-used",
            "source_action_id": "srd.thirsting_blade",
            "target_id": "pc1",
            "applied_by": "pc1",
            "condition": "thirsting_blade_extra_attack_used",
            "duration": {"until": "start_of_next_turn"},
            "tick_on": "self_turn_start",
            "stacking_policy": "append",
            "audit": {"pact_weapon_action_id": "srd.longsword_attack"},
        }
    )
    repeated = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="longsword",
            target_ids=["goblin1"],
            candidate_action_id="srd.longsword_attack",
            params={"use_thirsting_blade_extra_attack": True},
        )
    )
    assert repeated.status == "rejected"
    assert repeated.reason == "Thirsting Blade extra attack already used this turn"


def test_resolver_checks_eldritch_smite_pact_weapon_slot_and_prone_size(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 5}
    character.feature_choices = {
        "warlock.eldritch_invocation.pact_of_the_blade": "selected",
        "warlock.eldritch_invocation.eldritch_smite": "selected",
    }
    character.actions = [
        "srd.pact_of_the_blade",
        "srd.pact_of_the_blade_weapon",
        "srd.eldritch_smite",
    ]
    character.spell_slots = {"3": 1}
    character.spell_slots_max = {"3": 2}
    state.encounter.combatants["goblin1"].size = "huge"
    pact_weapon_effect = {
        "effect_id": "pact-weapon",
        "source_action_id": "srd.pact_of_the_blade_weapon",
        "target_id": "pc1",
        "applied_by": "pc1",
        "condition": "pact_weapon",
        "passive_modifiers": {
            "pact_weapon": True,
            "pact_weapon_action_id": "srd.longsword_attack",
        },
        "duration": {"until": "pact_ends_or_replaced_or_warlock_dies"},
        "tick_on": "weapon_attack",
        "stacking_policy": "replace_condition",
        "audit": {},
    }
    state.encounter.combatants["pc1"].status_effects.append(pact_weapon_effect)
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    accepted = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="longsword",
            target_ids=["goblin1"],
            candidate_action_id="srd.longsword_attack",
            params={"use_eldritch_smite": True, "eldritch_smite_prone": True},
        )
    )
    assert accepted.status == "accepted"
    assert accepted.action_id == "srd.longsword_attack"

    character.spell_slots = {"3": 0}
    no_slot = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="longsword",
            target_ids=["goblin1"],
            candidate_action_id="srd.longsword_attack",
            params={"use_eldritch_smite": True},
        )
    )
    assert no_slot.status == "rejected"
    assert no_slot.reason == "insufficient Pact Magic spell slot"
    character.spell_slots = {"3": 1}

    state.encounter.combatants["pc1"].status_effects.append(
        {
            "effect_id": "eldritch-smite-used",
            "source_action_id": "srd.eldritch_smite",
            "target_id": "pc1",
            "applied_by": "pc1",
            "condition": "eldritch_smite_used",
            "duration": {"until": "start_of_next_turn"},
            "tick_on": "self_turn_start",
            "stacking_policy": "append",
            "audit": {"pact_weapon_action_id": "srd.longsword_attack"},
        }
    )
    repeated = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="longsword",
            target_ids=["goblin1"],
            candidate_action_id="srd.longsword_attack",
            params={"use_eldritch_smite": True},
        )
    )
    assert repeated.status == "rejected"
    assert repeated.reason == "Eldritch Smite already used this turn"
    state.encounter.combatants["pc1"].status_effects = [pact_weapon_effect]

    state.encounter.combatants["goblin1"].size = "gargantuan"
    too_large = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="longsword",
            target_ids=["goblin1"],
            candidate_action_id="srd.longsword_attack",
            params={"use_eldritch_smite": True, "eldritch_smite_prone": True},
        )
    )
    assert too_large.status == "rejected"
    assert too_large.reason == "Eldritch Smite Prone target must be Huge or smaller"

    state.encounter.combatants["pc1"].status_effects = []
    character.actions.append("srd.longsword_attack")
    no_pact_weapon = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="longsword",
            target_ids=["goblin1"],
            candidate_action_id="srd.longsword_attack",
            params={"use_eldritch_smite": True},
        )
    )
    assert no_pact_weapon.status == "rejected"
    assert no_pact_weapon.reason == "Eldritch Smite requires the selected pact weapon"


def test_resolver_accepts_master_of_myriad_forms_alter_self_without_spell_slot(
    make_state,
) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 5}
    character.feature_choices = {"warlock.eldritch_invocation.master_of_myriad_forms": "selected"}
    character.actions.extend(
        ["srd.alter_self", "srd.master_of_myriad_forms", "srd.master_of_myriad_forms_alter_self"]
    )
    character.spell_slots["2"] = 0
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    ordinary = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="alter self",
            target_ids=[],
            candidate_action_id="srd.alter_self",
        )
    )
    assert ordinary.status == "rejected"
    assert ordinary.reason == "insufficient spell slot"

    master = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="master of myriad forms alter self",
            target_ids=[],
            candidate_action_id="srd.master_of_myriad_forms_alter_self",
        )
    )
    assert master.status == "accepted"
    assert master.action_id == "srd.master_of_myriad_forms_alter_self"


def test_resolver_accepts_ascendant_step_levitate_without_spell_slot(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 5}
    character.feature_choices = {"warlock.eldritch_invocation.ascendant_step": "selected"}
    character.actions.extend(["srd.levitate", "srd.ascendant_step", "srd.ascendant_step_levitate"])
    character.spell_slots["2"] = 0
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    ordinary = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="levitate",
            target_ids=["pc1"],
            candidate_action_id="srd.levitate",
        )
    )
    ascendant = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="ascendant step levitate",
            target_ids=[],
            candidate_action_id="srd.ascendant_step_levitate",
        )
    )

    assert ordinary.status == "rejected"
    assert ordinary.reason == "insufficient spell slot"
    assert ascendant.status == "accepted"
    assert ascendant.action_id == "srd.ascendant_step_levitate"


def test_resolver_checks_one_with_shadows_lighting_instead_of_spell_slot(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 5}
    character.feature_choices = {"warlock.eldritch_invocation.one_with_shadows": "selected"}
    character.actions.extend(
        ["srd.invisibility", "srd.one_with_shadows", "srd.one_with_shadows_invisibility"]
    )
    character.spell_slots["2"] = 0
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    ordinary = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="invisibility",
            target_ids=["pc1"],
            candidate_action_id="srd.invisibility",
        )
    )
    missing_light = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="one with shadows invisibility",
            target_ids=[],
            candidate_action_id="srd.one_with_shadows_invisibility",
        )
    )
    one_with_shadows = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="one with shadows invisibility",
            target_ids=[],
            candidate_action_id="srd.one_with_shadows_invisibility",
            params={"in_dim_light_or_darkness": True},
        )
    )

    assert ordinary.status == "rejected"
    assert ordinary.reason == "insufficient spell slot"
    assert missing_light.status == "rejected"
    assert missing_light.reason == "One with Shadows requires Dim Light or Darkness"
    assert one_with_shadows.status == "accepted"
    assert one_with_shadows.action_id == "srd.one_with_shadows_invisibility"


def test_resolver_checks_gift_of_depths_resource_instead_of_spell_slot(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 5}
    character.feature_choices = {"warlock.eldritch_invocation.gift_of_the_depths": "selected"}
    character.actions.extend(
        [
            "srd.water_breathing",
            "srd.gift_of_the_depths",
            "srd.gift_of_the_depths_water_breathing",
        ]
    )
    character.spell_slots["3"] = 0
    character.resources["srd.resource.gift_of_the_depths"] = 0
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    ordinary = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="water breathing",
            target_ids=["pc1"],
            candidate_action_id="srd.water_breathing",
        )
    )
    no_resource = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="gift of the depths water breathing",
            target_ids=["pc1"],
            candidate_action_id="srd.gift_of_the_depths_water_breathing",
        )
    )
    character.resources["srd.resource.gift_of_the_depths"] = 1
    gift = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="gift of the depths water breathing",
            target_ids=["pc1"],
            candidate_action_id="srd.gift_of_the_depths_water_breathing",
        )
    )

    assert ordinary.status == "rejected"
    assert ordinary.reason == "insufficient spell slot"
    assert no_resource.status == "rejected"
    assert no_resource.reason == "insufficient resource srd.resource.gift_of_the_depths"
    assert gift.status == "accepted"
    assert gift.action_id == "srd.gift_of_the_depths_water_breathing"


def test_resolver_checks_gaze_of_two_minds_willing_touch_target(make_state) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"warlock": 5}
    character.feature_choices = {"warlock.eldritch_invocation.gaze_of_two_minds": "selected"}
    character.actions.extend(["srd.gaze_of_two_minds", "srd.gaze_of_two_minds_touch"])
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    missing_willing = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="gaze of two minds",
            target_ids=["pc2"],
            candidate_action_id="srd.gaze_of_two_minds_touch",
        )
    )
    assert state.encounter is not None
    state.encounter.combatants["pc2"].position_node_id = "back"
    out_of_range = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="gaze of two minds",
            target_ids=["pc2"],
            candidate_action_id="srd.gaze_of_two_minds_touch",
            params={"target_willing": True},
        )
    )
    state.encounter.combatants["pc2"].position_node_id = "front"
    accepted = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="gaze of two minds",
            target_ids=["pc2"],
            candidate_action_id="srd.gaze_of_two_minds_touch",
            params={"target_willing": True},
        )
    )

    assert missing_willing.status == "rejected"
    assert missing_willing.reason == "target must be willing"
    assert out_of_range.status == "rejected"
    assert out_of_range.reason == "target out of range"
    assert accepted.status == "accepted"
    assert accepted.action_id == "srd.gaze_of_two_minds_touch"


def test_resolver_rejects_armor_of_shadows_while_wearing_armor(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"warlock": 1}
    state.characters["pc1"].feature_choices = {
        "warlock.eldritch_invocation.armor_of_shadows": "selected"
    }
    state.characters["pc1"].actions.extend(
        ["srd.armor_of_shadows", "srd.armor_of_shadows_mage_armor"]
    )
    state.characters["pc1"].equipment = ["srd.leather_armor"]
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="armor of shadows",
            target_ids=[],
            candidate_action_id="srd.armor_of_shadows_mage_armor",
        )
    )

    assert result.status == "rejected"
    assert result.reason == "Mage Armor target must not be wearing armor"


def test_resolver_checks_channel_divinity_resource(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"cleric": 2}
    state.characters["pc1"].actions.append("srd.divine_spark_heal")
    state.characters["pc1"].resources["srd.resource.channel_divinity"] = 0
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    no_resource = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="神圣火花治疗",
            target_ids=["pc2"],
            candidate_action_id="srd.divine_spark_heal",
        )
    )
    state.characters["pc1"].resources["srd.resource.channel_divinity"] = 1
    accepted = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="神圣火花治疗",
            target_ids=["pc2"],
            candidate_action_id="srd.divine_spark_heal",
        )
    )

    assert no_resource.status == "rejected"
    assert no_resource.reason == "insufficient resource srd.resource.channel_divinity"
    assert accepted.status == "accepted"


def test_resolver_checks_turn_undead_creature_type_policy(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"cleric": 2}
    state.characters["pc1"].actions.append("srd.turn_undead")
    state.characters["pc1"].resources["srd.resource.channel_divinity"] = 2
    state.encounter.combatants["skeleton1"] = Combatant(
        id="skeleton1",
        entity_id="skeleton1",
        name="Skeleton",
        side="monsters",
        hp_current=13,
        hp_max=13,
        armor_class=14,
        creature_type="undead",
        abilities={"str": 10, "dex": 16, "con": 15, "int": 6, "wis": 8, "cha": 5},
        position_node_id="cover",
    )
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    rejected = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="驱散亡灵",
            target_ids=["goblin1"],
            candidate_action_id="srd.turn_undead",
        )
    )
    accepted = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="驱散亡灵",
            target_ids=["skeleton1"],
            candidate_action_id="srd.turn_undead",
        )
    )

    assert rejected.status == "rejected"
    assert rejected.reason == "target must be undead"
    assert accepted.status == "accepted"


def test_resolver_rejects_unmet_class_requirements(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"fighter": 1}
    state.characters["pc1"].actions.append("srd.cunning_action_dash")
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="机敏疾走",
            candidate_action_id="srd.cunning_action_dash",
        )
    )

    assert result.status == "rejected"
    assert result.reason == "requires rogue level 2"


def test_resolver_rejects_steady_aim_after_movement_used(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"rogue": 3}
    state.characters["pc1"].actions.append("srd.steady_aim")
    state.encounter.action_budgets["pc1"] = {
        "action": 1,
        "bonus_action": 1,
        "reaction": 1,
        "movement": 25,
        "movement_used": 5,
        "free": 1,
    }
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="稳定瞄准",
            candidate_action_id="srd.steady_aim",
        )
    )

    assert result.status == "rejected"
    assert result.reason == "requires no movement used this turn"


def test_resolver_uses_encounter_budget_for_steady_aim_bonus_action(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    state.characters["pc1"].class_levels = {"rogue": 3}
    state.characters["pc1"].actions.append("srd.steady_aim")
    state.encounter.action_budgets["pc1"] = {
        "action": 1,
        "bonus_action": 0,
        "reaction": 1,
        "movement": 30,
        "movement_used": 0,
        "free": 1,
    }
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="稳定瞄准",
            candidate_action_id="srd.steady_aim",
        )
    )

    assert result.status == "rejected"
    assert result.reason == "insufficient action economy"


def test_resolver_accepts_fleet_step_when_bonus_action_is_spent(make_state) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"monk": 11}
    character.subclasses = {"monk": "open_hand"}
    character.actions.extend(["srd.step_of_the_wind", "srd.fleet_step"])
    state.encounter.action_budgets["pc1"] = {
        "action": 1,
        "bonus_action": 0,
        "reaction": 1,
        "movement": 30,
        "movement_used": 0,
        "free": 1,
    }
    state.encounter.combatants["pc1"].status_effects.append(
        {
            "effect_id": "fleet-step-window",
            "source_ref": "SRD 5.2.1",
            "source_action_id": "srd.fleet_step",
            "target_id": "pc1",
            "applied_by": "pc1",
            "condition": "fleet_step_available",
            "duration": {"until": "end_of_current_turn"},
            "tick_on": "self_turn_end",
        }
    )
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    accepted = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="step",
            candidate_action_id="srd.step_of_the_wind",
            params={"use_fleet_step": True},
        )
    )
    missing_param = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="step",
            candidate_action_id="srd.step_of_the_wind",
        )
    )

    assert accepted.status == "accepted"
    assert missing_param.status == "rejected"
    assert missing_param.reason == "insufficient action economy"


def test_resolver_accepts_harmless_quivering_palm_release_without_action_budget(
    make_state,
) -> None:
    state = make_state()
    assert state.encounter is not None
    character = state.characters["pc1"]
    character.class_levels = {"monk": 17}
    character.subclasses = {"monk": "open_hand"}
    character.actions.extend(["srd.quivering_palm", "srd.quivering_palm_release"])
    state.encounter.action_budgets["pc1"] = {
        "action": 0,
        "bonus_action": 0,
        "reaction": 1,
        "movement": 30,
        "movement_used": 0,
        "free": 1,
    }
    state.encounter.combatants["pc2"].status_effects.append(
        {
            "effect_id": "quivering-palm-window",
            "source_ref": "SRD 5.2.1",
            "source_action_id": "srd.quivering_palm",
            "target_id": "pc2",
            "applied_by": "pc1",
            "condition": "quivering_palm",
            "duration": {"until": "duration_monk_level_days", "days": 17},
            "tick_on": None,
        }
    )
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    accepted = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="结束震颤掌",
            target_ids=["pc2"],
            candidate_action_id="srd.quivering_palm_release",
            params={"harmless": True},
        )
    )
    harmful = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="结束震颤掌",
            target_ids=["pc2"],
            candidate_action_id="srd.quivering_palm_release",
            params={"same_plane": True},
        )
    )

    assert accepted.status == "accepted"
    assert harmful.status == "rejected"
    assert harmful.reason == "insufficient action economy"


def test_resolver_rejects_font_of_magic_conversion_above_sorcery_point_cap(
    make_state,
) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"sorcerer": 2}
    state.characters["pc1"].actions.append("srd.font_of_magic_convert_slot_1")
    state.characters["pc1"].resources["srd.resource.sorcery_points"] = 2
    state.characters["pc1"].spell_slots["1"] = 1
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    rejected = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="转化1环法术位",
            candidate_action_id="srd.font_of_magic_convert_slot_1",
        )
    )
    state.characters["pc1"].resources["srd.resource.sorcery_points"] = 1
    accepted = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="转化1环法术位",
            candidate_action_id="srd.font_of_magic_convert_slot_1",
        )
    )

    assert rejected.status == "rejected"
    assert rejected.reason == "resource srd.resource.sorcery_points would exceed maximum 2"
    assert accepted.status == "accepted"


def test_resolver_uses_highest_single_class_for_generic_level_requirements(make_state) -> None:
    state = make_state()
    state.characters["pc1"].class_levels = {"fighter": 4, "cleric": 1}
    state.characters["pc1"].actions.append("srd.extra_attack")
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="额外攻击",
            candidate_action_id="srd.extra_attack",
        )
    )

    assert result.status == "rejected"
    assert result.reason == "requires class level 5"


def test_resolver_requires_confirmation_for_aoe_friendly_fire(make_state) -> None:
    state = make_state()
    state.characters["pc1"].actions.append("srd.fireball")
    state.characters["pc1"].spell_slots["3"] = 1
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="火球",
            target_ids=["goblin1", "pc2"],
            candidate_action_id="srd.fireball",
        )
    )

    assert result.status == "confirm_required"
    assert result.confirm_required is True
    assert result.reason == "friendly fire confirmation required"


def test_resolver_honors_friendly_fire_off_for_aoe(make_state) -> None:
    state = make_state()
    state.config.friendly_fire = "off"
    state.characters["pc1"].actions.append("srd.fireball")
    state.characters["pc1"].spell_slots["3"] = 1
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="火球",
            target_ids=["goblin1", "pc2"],
            candidate_action_id="srd.fireball",
        )
    )

    assert result.status == "rejected"
    assert result.reason == "friendly fire is disabled"


def test_resolver_accepts_item_id_when_inventory_or_equipment_has_item(make_state) -> None:
    state = make_state()
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions, compendium.items)

    missing_item = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["pc1"],
            candidate_action_id="srd.potion_of_healing",
        )
    )
    assert missing_item.status == "rejected"
    assert missing_item.reason == "actor does not have item srd.potion_of_healing"

    state.characters["pc1"].inventory["srd.potion_of_healing"] = 1
    accepted = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["pc1"],
            candidate_action_id="srd.potion_of_healing",
        )
    )

    assert accepted.status == "accepted"
    assert accepted.action_id == "srd.use_potion_of_healing"

    state.characters["pc1"].equipment.append("srd.boots_of_elvenkind")
    equipped = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["pc1"],
            candidate_action_id="srd.boots_of_elvenkind",
        )
    )

    assert equipped.status == "accepted"
    assert equipped.action_id == "srd.wear_boots_of_elvenkind"


def test_resolver_rejects_ring_of_water_walking_non_self_target(make_state) -> None:
    state = make_state()
    state.characters["pc1"].inventory["srd.ring_of_water_walking"] = 1
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions, compendium.items)

    rejected = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["pc2"],
            candidate_action_id="srd.ring_of_water_walking",
        )
    )
    accepted = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["pc1"],
            candidate_action_id="srd.ring_of_water_walking",
        )
    )

    assert rejected.status == "rejected"
    assert rejected.reason == "target must be self"
    assert rejected.action_id == "srd.ring_of_water_walking_water_walk"
    assert accepted.status == "accepted"
    assert accepted.action_id == "srd.ring_of_water_walking_water_walk"


def test_resolver_rejects_ring_of_xray_vision_non_self_target(make_state) -> None:
    state = make_state()
    state.characters["pc1"].inventory["srd.ring_of_xray_vision"] = 1
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions, compendium.items)

    rejected = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["pc2"],
            candidate_action_id="srd.ring_of_xray_vision",
        )
    )
    accepted = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["pc1"],
            candidate_action_id="srd.ring_of_xray_vision",
        )
    )

    assert rejected.status == "rejected"
    assert rejected.reason == "target must be self"
    assert rejected.action_id == "srd.use_ring_of_xray_vision"
    assert accepted.status == "accepted"
    assert accepted.action_id == "srd.use_ring_of_xray_vision"


def test_resolver_accepts_robe_of_eyes_selected_item_actions_and_rejects_non_self(
    make_state,
) -> None:
    state = make_state()
    state.characters["pc1"].inventory["srd.robe_of_eyes"] = 1
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions, compendium.items)

    light = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["pc1"],
            candidate_action_id="srd.robe_of_eyes",
            params={"item_action_id": "srd.robe_of_eyes_light_drawback"},
        )
    )
    rejected = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["pc2"],
            candidate_action_id="srd.robe_of_eyes",
            params={"item_action_id": "srd.wear_robe_of_eyes"},
        )
    )

    assert light.status == "accepted"
    assert light.action_id == "srd.robe_of_eyes_light_drawback"
    assert rejected.status == "rejected"
    assert rejected.reason == "target must be self"
    assert rejected.action_id == "srd.wear_robe_of_eyes"


def test_resolver_enforces_robe_of_the_archmagi_class_attunement(
    make_state,
) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.inventory["srd.robe_of_the_archmagi"] = 1
    character.class_levels = {"fighter": 5}
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions, compendium.items)

    rejected = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["pc1"],
            candidate_action_id="srd.robe_of_the_archmagi",
        )
    )
    character.class_levels = {"wizard": 1}
    accepted = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["pc1"],
            candidate_action_id="srd.robe_of_the_archmagi",
        )
    )

    assert rejected.status == "rejected"
    assert rejected.reason == "requires one of sorcerer, warlock, wizard"
    assert rejected.action_id == "srd.wear_robe_of_the_archmagi"
    assert accepted.status == "accepted"
    assert accepted.action_id == "srd.wear_robe_of_the_archmagi"


def test_resolver_validates_robe_of_useful_items_patch_selection(
    make_state,
) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.inventory["srd.robe_of_useful_items"] = 1
    character.resources["srd.robe_of_useful_items.initialized"] = 1
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions, compendium.items)

    missing = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["pc1"],
            candidate_action_id="srd.robe_of_useful_items",
            params={"item_action_id": "srd.detach_robe_of_useful_items_patch"},
        )
    )
    invalid = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["pc1"],
            candidate_action_id="srd.robe_of_useful_items",
            params={
                "item_action_id": "srd.detach_robe_of_useful_items_patch",
                "robe_of_useful_items_patch": "imaginary_patch",
            },
        )
    )
    unavailable = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["pc1"],
            candidate_action_id="srd.robe_of_useful_items",
            params={
                "item_action_id": "srd.detach_robe_of_useful_items_patch",
                "robe_of_useful_items_patch": "dagger",
            },
        )
    )
    character.resources["srd.robe_of_useful_items.patch.dagger"] = 1
    accepted = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["pc1"],
            candidate_action_id="srd.robe_of_useful_items",
            params={
                "item_action_id": "srd.detach_robe_of_useful_items_patch",
                "robe_of_useful_items_patch": "dagger",
            },
        )
    )

    assert missing.status == "rejected"
    assert missing.reason == "missing required parameter robe_of_useful_items_patch"
    assert invalid.status == "rejected"
    assert invalid.reason == "Robe of Useful Items patch is not in the SRD patch table"
    assert unavailable.status == "rejected"
    assert unavailable.reason == "Robe of Useful Items patch dagger is unavailable"
    assert accepted.status == "accepted"
    assert accepted.action_id == "srd.detach_robe_of_useful_items_patch"


def test_resolver_validates_rod_of_absorption_absorb_spell_params(
    make_state,
) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.inventory["srd.rod_of_absorption"] = 1
    character.resources["srd.rod_of_absorption.initialized"] = 1
    character.resources["srd.rod_of_absorption.stored_levels"] = 1
    character.resources["srd.rod_of_absorption.lifetime_absorbed_levels"] = 49
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions, compendium.items)

    missing = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["pc1"],
            candidate_action_id="srd.rod_of_absorption",
            params={"item_action_id": "srd.rod_of_absorption_absorb_spell"},
        )
    )
    area = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["pc1"],
            candidate_action_id="srd.rod_of_absorption",
            params={
                "item_action_id": "srd.rod_of_absorption_absorb_spell",
                "absorbed_spell_level": 1,
                "targeting_only_you": True,
                "creates_area_of_effect": True,
            },
        )
    )
    over_cap = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["pc1"],
            candidate_action_id="srd.rod_of_absorption",
            params={
                "item_action_id": "srd.rod_of_absorption_absorb_spell",
                "absorbed_spell_level": 2,
                "targeting_only_you": True,
                "creates_area_of_effect": False,
            },
        )
    )
    accepted = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["pc1"],
            candidate_action_id="srd.rod_of_absorption",
            params={
                "item_action_id": "srd.rod_of_absorption_absorb_spell",
                "absorbed_spell_level": 1,
                "targeting_only_you": True,
                "creates_area_of_effect": False,
            },
        )
    )

    assert missing.status == "rejected"
    assert missing.reason == "missing required parameter absorbed_spell_level"
    assert area.status == "rejected"
    assert area.reason == "Rod of Absorption cannot absorb an area-of-effect spell"
    assert over_cap.status == "rejected"
    assert over_cap.reason == "Rod of Absorption cannot store that spell level"
    assert accepted.status == "accepted"
    assert accepted.action_id == "srd.rod_of_absorption_absorb_spell"


def test_resolver_validates_rod_of_alertness_protective_aura_targets_and_reuse(
    make_state,
) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.inventory["srd.rod_of_alertness"] = 1
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions, compendium.items)

    hostile = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["goblin1"],
            candidate_action_id="srd.rod_of_alertness",
            params={"item_action_id": "srd.rod_of_alertness_protective_aura"},
        )
    )
    accepted = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["pc1", "pc2"],
            candidate_action_id="srd.rod_of_alertness",
            params={"item_action_id": "srd.rod_of_alertness_protective_aura"},
        )
    )
    character.resources["srd.rod_of_alertness.protective_aura_used_until_next_dawn"] = 1
    repeated = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["pc1", "pc2"],
            candidate_action_id="srd.rod_of_alertness",
            params={"item_action_id": "srd.rod_of_alertness_protective_aura"},
        )
    )

    assert hostile.status == "rejected"
    assert hostile.reason == "Rod of Alertness Protective Aura affects only you and your allies"
    assert hostile.action_id == "srd.rod_of_alertness_protective_aura"
    assert accepted.status == "accepted"
    assert accepted.action_id == "srd.rod_of_alertness_protective_aura"
    assert repeated.status == "rejected"
    assert repeated.reason == (
        "Rod of Alertness Protective Aura can't be used again until the next dawn"
    )


def test_resolver_accepts_rod_of_absorption_stored_energy_spell_slot(
    make_state,
) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.inventory["srd.rod_of_absorption"] = 1
    character.spell_slots = {"1": 0, "3": 0, "6": 0}
    character.spell_slots_max = {"1": 4, "3": 2, "6": 1}
    character.resources["srd.rod_of_absorption.stored_levels"] = 5
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions, compendium.items)

    accepted = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="cast_spell",
            target_ids=["pc2"],
            candidate_action_id="srd.cure_wounds",
            params={"slot_level": 3, "use_rod_of_absorption": True},
        )
    )
    too_high_for_rod = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="cast_spell",
            target_ids=["pc2"],
            candidate_action_id="srd.cure_wounds",
            params={"slot_level": 6, "use_rod_of_absorption": True},
        )
    )
    character.resources["srd.rod_of_absorption.stored_levels"] = 2
    insufficient_energy = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="cast_spell",
            target_ids=["pc2"],
            candidate_action_id="srd.cure_wounds",
            params={"slot_level": 5, "use_rod_of_absorption": True},
        )
    )
    character.inventory["srd.rod_of_absorption"] = 0
    missing_rod = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="cast_spell",
            target_ids=["pc2"],
            candidate_action_id="srd.cure_wounds",
            params={"slot_level": 1, "use_rod_of_absorption": True},
        )
    )

    assert accepted.status == "accepted"
    assert accepted.action_id == "srd.cure_wounds"
    assert too_high_for_rod.status == "rejected"
    assert too_high_for_rod.reason == "Rod of Absorption cannot create spell slots above level 5"
    assert insufficient_energy.status == "rejected"
    assert insufficient_energy.reason == "Rod of Absorption has insufficient stored spell energy"
    assert missing_rod.status == "rejected"
    assert missing_rod.reason == "Rod of Absorption requires holding the rod"


def test_resolver_validates_potion_of_resistance_damage_type(make_state) -> None:
    state = make_state()
    state.characters["pc1"].inventory["srd.potion_of_resistance"] = 1
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions, compendium.items)

    missing = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["pc1"],
            candidate_action_id="srd.potion_of_resistance",
        )
    )
    assert missing.status == "rejected"
    assert missing.reason == "missing required parameter damage_type"

    invalid = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["pc1"],
            candidate_action_id="srd.potion_of_resistance",
            params={"damage_type": "slashing"},
        )
    )
    assert invalid.status == "rejected"
    assert invalid.reason.startswith("damage_type must be one of:")

    draft = PlayerActionDraft(
        actor_id="pc1",
        verb="use_item",
        target_ids=["pc1"],
        candidate_action_id="srd.potion_of_resistance",
        params={"damage_type": "FIRE"},
    )
    accepted = resolver.resolve(draft)
    assert accepted.status == "accepted"
    assert accepted.action_id == "srd.use_potion_of_resistance"
    assert draft.params["damage_type"] == "fire"


def test_resolver_rejects_fast_hands_for_item_that_is_already_bonus_action(
    make_state,
) -> None:
    state = make_state()
    character = state.characters["pc1"]
    character.class_levels = {"rogue": 3}
    character.subclasses = {"rogue": "thief"}
    character.actions.append("srd.fast_hands_magic_item")
    character.inventory["srd.potion_of_healing"] = 1
    compendium = CompendiumLoader("rules_data").load()
    resolver = ActionResolver(state, compendium.actions, compendium.items)

    result = resolver.resolve(
        PlayerActionDraft(
            actor_id="pc1",
            verb="use_item",
            target_ids=["pc1"],
            candidate_action_id="srd.potion_of_healing",
            params={"fast_hands": True},
        )
    )

    assert result.status == "rejected"
    assert result.reason == "Fast Hands requires a magic item action that normally uses an action"

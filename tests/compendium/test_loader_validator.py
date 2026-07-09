from __future__ import annotations

from dnd_llm.core.compendium.loader import CompendiumLoader
from dnd_llm.core.compendium.schema_loader import SchemaRegistry
from dnd_llm.core.compendium.validators import RuleDataValidator


def test_compendium_loads_srd_actions() -> None:
    compendium = CompendiumLoader("rules_data").load()

    assert "srd.shortsword_attack" in compendium.actions
    assert "srd.longsword_attack" in compendium.actions
    assert "srd.fire_bolt" in compendium.actions
    assert {
        "srd.sacred_flame",
        "srd.eldritch_blast",
        "srd.acid_splash",
        "srd.chill_touch",
        "srd.guiding_bolt",
        "srd.healing_word",
        "srd.aid",
        "srd.alarm",
        "srd.bless",
        "srd.detect_magic",
        "srd.lesser_restoration",
        "srd.fly",
        "srd.light",
        "srd.magic_missile",
        "srd.burning_hands",
        "srd.shatter",
        "srd.web",
        "srd.scorching_ray",
        "srd.spirit_guardians",
        "srd.hold_person",
        "srd.fireball",
        "srd.lightning_bolt",
        "srd.ice_storm",
        "srd.fire_shield",
        "srd.vitriolic_sphere",
        "srd.wall_of_fire",
        "srd.cone_of_cold",
        "srd.blade_barrier",
        "srd.chain_lightning",
        "srd.fire_storm",
        "srd.forcecage",
        "srd.sunburst",
        "srd.mind_blank",
        "srd.meteor_swarm",
        "srd.flame_strike",
        "srd.circle_of_death",
        "srd.disintegrate",
        "srd.heal",
        "srd.harm",
        "srd.finger_of_death",
        "srd.greater_invisibility",
        "srd.hallucinatory_terrain",
        "srd.phantasmal_killer",
        "srd.freedom_of_movement",
        "srd.private_sanctum",
        "srd.resilient_sphere",
        "srd.banishment",
        "srd.antilife_shell",
        "srd.aura_of_life",
        "srd.death_ward",
        "srd.arcane_eye",
        "srd.blight",
        "srd.mass_cure_wounds",
        "srd.charm_monster",
        "srd.commune",
        "srd.commune_with_nature",
        "srd.contact_other_plane",
        "srd.confusion",
        "srd.conjure_minor_elementals",
        "srd.conjure_woodland_beings",
        "srd.conjure_woodland_beings_disengage",
        "srd.creation",
        "srd.dominate_beast",
        "srd.dominate_person",
        "srd.compulsion",
        "srd.hold_monster",
        "srd.irresistible_dance",
        "srd.mass_suggestion",
        "srd.greater_restoration",
        "srd.globe_of_invulnerability",
        "srd.forbiddance",
        "srd.cloudkill",
        "srd.teleportation_circle",
        "srd.dimension_door",
        "srd.faithful_hound",
        "srd.guardian_of_faith",
        "srd.black_tentacles",
        "srd.secret_chest",
        "srd.insect_plague",
        "srd.transport_via_plants",
        "srd.word_of_recall",
        "srd.legend_lore",
        "srd.divination",
        "srd.etherealness",
        "srd.find_the_path",
        "srd.foresight",
        "srd.locate_creature",
        "srd.telepathic_bond",
        "srd.true_seeing",
        "srd.passwall",
        "srd.move_earth",
        "srd.wind_walk",
        "srd.tree_stride",
        "srd.fabricate",
        "srd.stone_shape",
        "srd.stoneskin",
        "srd.wall_of_force",
        "srd.wall_of_stone",
        "srd.wall_of_ice",
        "srd.wall_of_thorns",
    } <= set(compendium.actions)
    assert "srd.monster_melee_attack" not in compendium.actions
    assert "srd.action_surge" in compendium.actions
    assert compendium.action("srd.action_surge").cost.resources == {"srd.resource.action_surge": 1}
    assert compendium.action("srd.action_surge").properties == {
        "resource": "srd.resource.action_surge",
        "recharge": "short_or_long_rest",
        "uses_by_fighter_level": {"2": 1, "17": 2},
        "once_per_turn": True,
    }
    assert "srd.tactical_mind" in compendium.actions
    assert compendium.action("srd.tactical_mind").requirements == {
        "class": "fighter",
        "class_level_min": 2,
    }
    assert compendium.action("srd.tactical_mind").action_economy == "none"
    assert "srd.tactical_master" in compendium.actions
    assert compendium.action("srd.tactical_master").requirements == {
        "class": "fighter",
        "class_level_min": 9,
    }
    assert compendium.action("srd.tactical_master").action_economy == "none"
    assert compendium.action("srd.tactical_master").properties == {
        "weapon_mastery_property_replacement": True,
        "requires_weapon_mastery_property_you_can_use": True,
        "replacement_mastery_properties": ["Push", "Sap", "Slow"],
        "scope": "one_attack",
    }
    assert "srd.two_extra_attacks" in compendium.actions
    assert compendium.action("srd.two_extra_attacks").requirements == {
        "class": "fighter",
        "class_level_min": 11,
    }
    assert compendium.action("srd.two_extra_attacks").action_economy == "none"
    assert compendium.action("srd.two_extra_attacks").properties == {
        "attack_action_attack_count": 3,
        "applies_when_taking_attack_action_on_turn": True,
        "instead_of_once": True,
    }
    assert "srd.studied_attacks" in compendium.actions
    assert compendium.action("srd.studied_attacks").requirements == {
        "class": "fighter",
        "class_level_min": 13,
    }
    assert compendium.action("srd.studied_attacks").action_economy == "none"
    assert compendium.action("srd.studied_attacks").properties == {
        "triggers_on_attack_roll_miss": True,
        "target_scope": "missed_creature",
        "grants_advantage_on_next_attack_roll_against_target": True,
        "expires": "before_end_of_next_turn",
    }
    assert "srd.three_extra_attacks" in compendium.actions
    assert compendium.action("srd.three_extra_attacks").requirements == {
        "class": "fighter",
        "class_level_min": 20,
    }
    assert compendium.action("srd.three_extra_attacks").action_economy == "none"
    assert compendium.action("srd.three_extra_attacks").properties == {
        "attack_action_attack_count": 4,
        "applies_when_taking_attack_action_on_turn": True,
        "instead_of_once": True,
    }
    assert "srd.improved_critical" in compendium.actions
    assert compendium.action("srd.improved_critical").requirements == {
        "class": "fighter",
        "class_level_min": 3,
        "subclass": "champion",
    }
    assert "srd.remarkable_athlete" in compendium.actions
    assert compendium.action("srd.remarkable_athlete").requirements == {
        "class": "fighter",
        "class_level_min": 3,
        "subclass": "champion",
    }
    assert "srd.additional_fighting_style" in compendium.actions
    assert compendium.action("srd.additional_fighting_style").requirements == {
        "class": "fighter",
        "class_level_min": 7,
        "subclass": "champion",
    }
    assert compendium.action("srd.additional_fighting_style").properties == {
        "grants_additional_fighting_style_feat": True,
        "requires_explicit_fighting_style_feat_choice": True,
        "fighting_style_feat_prerequisite": "Fighting Style Feature",
        "available_srd_fighting_style_feats": [
            "Archery",
            "Defense",
            "Great Weapon Fighting",
            "Two-Weapon Fighting",
        ],
        "does_not_select_default_feat": True,
    }
    assert "srd.heroic_warrior" in compendium.actions
    assert compendium.action("srd.heroic_warrior").requirements == {
        "class": "fighter",
        "class_level_min": 10,
        "subclass": "champion",
    }
    assert "srd.superior_critical" in compendium.actions
    assert compendium.action("srd.superior_critical").requirements == {
        "class": "fighter",
        "class_level_min": 15,
        "subclass": "champion",
    }
    assert "srd.second_wind" in compendium.actions
    assert compendium.action("srd.second_wind").cost.resources == {"srd.resource.second_wind": 1}
    assert compendium.action("srd.second_wind").automation[1] == {
        "type": "healing",
        "dice": "1d10",
        "bonus_from": {"class_level": "fighter"},
    }
    assert compendium.action("srd.second_wind").automation[2] == {
        "type": "branch",
        "condition": "actor_class_level_min",
        "class": "fighter",
        "level": 5,
        "if_true": [
            {
                "type": "tactical_shift_move",
                "destination_param": "tactical_shift_to_position_node_id",
            }
        ],
    }
    assert "srd.rage" in compendium.actions
    assert compendium.action("srd.rage").cost.resources == {"srd.resource.rage": 1}
    assert compendium.action("srd.rage").automation[1]["condition"] == "raging"
    assert compendium.action("srd.rage").automation[1]["passive_modifiers"][
        "damage_resistances"
    ] == ["bludgeoning", "piercing", "slashing"]
    assert compendium.action("srd.rage").automation[2] == {
        "type": "branch",
        "condition": "actor_class_level_min",
        "class": "barbarian",
        "level": 7,
        "if_true": [
            {
                "type": "instinctive_pounce_move",
                "destination_param": "instinctive_pounce_to_position_node_id",
            }
        ],
    }
    assert compendium.action("srd.barbarian_unarmored_defense").requirements == {
        "class": "barbarian",
        "class_level_min": 1,
    }
    assert compendium.action("srd.danger_sense").action_economy == "none"
    assert compendium.action("srd.danger_sense").requirements == {
        "class": "barbarian",
        "class_level_min": 2,
    }
    assert compendium.action("srd.primal_knowledge").action_economy == "none"
    assert compendium.action("srd.primal_knowledge").requirements == {
        "class": "barbarian",
        "class_level_min": 3,
    }
    assert compendium.action("srd.mindless_rage").requirements == {
        "class": "barbarian",
        "class_level_min": 6,
        "subclass": "berserker",
    }
    assert compendium.action("srd.monk_unarmored_defense").requirements == {
        "class": "monk",
        "class_level_min": 1,
    }
    assert compendium.action("srd.bard_expertise").requirements == {
        "class": "bard",
        "class_level_min": 2,
    }
    assert compendium.action("srd.rogue_expertise").requirements == {
        "class": "rogue",
        "class_level_min": 1,
    }
    reliable_talent = compendium.action("srd.reliable_talent")
    assert reliable_talent.requirements == {
        "class": "rogue",
        "class_level_min": 7,
    }
    assert reliable_talent.action_economy == "none"
    assert reliable_talent.properties == {
        "ability_check_uses_skill_or_tool_proficiency": True,
        "d20_floor": 10,
        "d20_floor_applies_to_rolls_at_or_below": 9,
    }
    improved_cunning_strike = compendium.action("srd.improved_cunning_strike")
    assert improved_cunning_strike.requirements == {
        "class": "rogue",
        "class_level_min": 11,
    }
    assert improved_cunning_strike.action_economy == "none"
    assert improved_cunning_strike.properties == {
        "max_cunning_strike_effects_per_sneak_attack": 2,
        "pay_die_cost_for_each_effect": True,
    }
    slippery_mind = compendium.action("srd.slippery_mind")
    assert slippery_mind.requirements == {
        "class": "rogue",
        "class_level_min": 15,
    }
    assert slippery_mind.action_economy == "none"
    assert slippery_mind.properties == {
        "saving_throw_proficiencies": ["wis", "cha"],
    }
    elusive = compendium.action("srd.elusive")
    assert elusive.requirements == {
        "class": "rogue",
        "class_level_min": 18,
    }
    assert elusive.action_economy == "none"
    assert elusive.properties == {
        "blocks_attack_roll_advantage_against_self": True,
        "disabled_by_condition": "incapacitated",
    }
    stroke_of_luck = compendium.action("srd.stroke_of_luck")
    assert stroke_of_luck.requirements == {
        "class": "rogue",
        "class_level_min": 20,
    }
    assert stroke_of_luck.action_economy == "none"
    assert stroke_of_luck.properties == {
        "applies_to": "failed_d20_test",
        "turns_d20_roll_into": 20,
        "resource": "srd.resource.stroke_of_luck",
        "restores_on": ["short_rest", "long_rest"],
    }
    assert compendium.action("srd.deft_explorer").requirements == {
        "class": "ranger",
        "class_level_min": 2,
    }
    ranger_expertise = compendium.action("srd.ranger_expertise")
    assert ranger_expertise.requirements == {
        "class": "ranger",
        "class_level_min": 9,
    }
    assert ranger_expertise.properties == {
        "skill_expertise_choices": 2,
        "requires_skill_proficiency": True,
        "requires_lacking_expertise": True,
    }
    tireless = compendium.action("srd.tireless")
    assert tireless.action_economy == "action"
    assert tireless.requirements == {"class": "ranger", "class_level_min": 10}
    assert tireless.properties == {
        "magic_action": True,
        "tireless": True,
        "resource": "srd.resource.tireless",
        "short_rest_decreases_exhaustion": 1,
    }
    assert tireless.cost.resources == {"srd.resource.tireless": 1}
    assert tireless.automation[1] == {
        "type": "temp_hp",
        "dice": "1d8",
        "bonus_from": {"ability_modifier": "wis"},
        "minimum_amount": 1,
    }
    assert compendium.action("srd.scholar").requirements == {
        "class": "wizard",
        "class_level_min": 2,
    }
    assert compendium.action("srd.memorize_spell").requirements == {
        "class": "wizard",
        "class_level_min": 5,
    }
    assert compendium.action("srd.ritual_adept").requirements == {
        "class": "wizard",
        "class_level_min": 1,
    }
    assert compendium.action("srd.detect_magic").properties["ritual"] is True
    assert compendium.action("srd.detect_magic").properties["spell_definition_id"] == (
        "srd.spell.detect_magic"
    )
    assert compendium.spell("srd.spell.detect_magic").ritual is True
    ice_storm = compendium.action("srd.ice_storm")
    assert ice_storm.requirements == {
        "spell_level": 4,
        "class_any": ["druid", "sorcerer", "wizard"],
    }
    assert ice_storm.properties["spell_classes"] == ["druid", "sorcerer", "wizard"]
    assert ice_storm.properties["material_component"] == {
        "description": "a mitten",
        "consumed": False,
    }
    assert (
        ice_storm.properties["ground_in_cylinder_becomes_difficult_terrain_until_end_of_next_turn"]
        is True
    )
    assert ice_storm.properties["higher_level_increases_bludgeoning_damage_only"] is True
    assert ice_storm.range == {
        "normal_ft": 300,
        "shape": "cylinder",
        "radius_ft": 20,
        "height_ft": 40,
    }
    assert ice_storm.target_policy == {"min": 1, "max": 12, "harmful": True}
    assert ice_storm.automation == [
        {"type": "target", "mode": "area"},
        {"type": "saving_throw", "ability": "dex", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "damage",
            "dice": "2d10",
            "damage_type": "bludgeoning",
            "save_half": True,
            "base_spell_slot_level": 4,
            "extra_dice_per_slot_above": "1d10",
        },
        {"type": "damage", "dice": "4d6", "damage_type": "cold", "save_half": True},
        {
            "type": "world_effect",
            "effect_type": "difficult_terrain",
            "scope": {"shape": "cylinder", "radius_ft": 20, "height_ft": 40},
            "duration": {"until": "end_of_next_turn"},
            "metadata": {"ground_in_cylinder": True, "source": "hailstones"},
        },
    ]
    fire_shield = compendium.action("srd.fire_shield")
    assert fire_shield.requirements == {
        "spell_level": 4,
        "class_any": ["druid", "sorcerer", "wizard"],
    }
    assert fire_shield.properties["spell_classes"] == ["druid", "sorcerer", "wizard"]
    assert fire_shield.properties["material_component"] == {
        "description": "a bit of phosphorus or a firefly",
        "consumed": False,
    }
    assert fire_shield.properties["fire_shield_type_param"] == "fire_shield_type"
    assert fire_shield.properties["allowed_fire_shield_types"] == ["warm", "chill"]
    assert fire_shield.range == {"self": True}
    assert fire_shield.target_policy == {
        "min": 1,
        "max": 1,
        "self": True,
        "harmful": False,
    }
    assert fire_shield.cost.spell_slot_level == 4
    assert fire_shield.automation == [
        {"type": "target", "mode": "self"},
        {
            "type": "passive_effect",
            "passive_modifiers": {
                "damage_resistances": {"param": "fire_shield_resistance_type"},
                "fire_shield": True,
                "fire_shield_type": {"param": "fire_shield_type"},
                "bright_light_radius_ft": 10,
                "dim_light_additional_ft": 10,
                "melee_hit_retaliation_within_ft": 5,
                "melee_hit_retaliation_damage": "2d8",
                "melee_hit_retaliation_damage_type": {
                    "param": "fire_shield_retaliation_damage_type"
                },
            },
            "duration": {"until": "duration_10_minutes"},
            "tick_on": "self_turn_end",
        },
    ]
    vitriolic_sphere = compendium.action("srd.vitriolic_sphere")
    assert vitriolic_sphere.requirements == {
        "spell_level": 4,
        "class_any": ["sorcerer", "wizard"],
    }
    assert vitriolic_sphere.properties["spell_classes"] == ["sorcerer", "wizard"]
    assert vitriolic_sphere.properties["material_component"] == {
        "description": "a drop of bile",
        "consumed": False,
    }
    assert vitriolic_sphere.properties["delayed_failed_save_damage_not_automated"] is True
    assert vitriolic_sphere.range == {
        "normal_ft": 150,
        "shape": "sphere",
        "radius_ft": 20,
    }
    assert vitriolic_sphere.target_policy == {"min": 1, "max": 12, "harmful": True}
    assert vitriolic_sphere.automation == [
        {"type": "target", "mode": "area"},
        {"type": "saving_throw", "ability": "dex", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "damage",
            "dice": "10d4",
            "damage_type": "acid",
            "save_half": True,
            "base_spell_slot_level": 4,
            "extra_dice_per_slot_above": "2d4",
        },
        {
            "type": "passive_effect",
            "requires_failed_save": True,
            "passive_modifiers": {
                "vitriolic_sphere_delayed_acid_damage": "5d4",
                "vitriolic_sphere_delayed_acid_damage_type": "acid",
                "delayed_damage_trigger": "target_turn_end",
                "delayed_damage_not_automated": True,
            },
            "duration": {"until": "end_of_next_turn"},
            "tick_on": "target_turn_end",
        },
    ]
    wall_of_fire = compendium.action("srd.wall_of_fire")
    assert wall_of_fire.requirements == {
        "spell_level": 4,
        "class_any": ["druid", "sorcerer", "wizard"],
    }
    assert wall_of_fire.properties["spell_classes"] == ["druid", "sorcerer", "wizard"]
    assert wall_of_fire.properties["material_component"] == {
        "description": "a piece of charcoal",
        "consumed": False,
    }
    assert wall_of_fire.range == {"normal_ft": 120}
    assert wall_of_fire.target_policy == {"min": 0, "max": 12, "harmful": True}
    assert wall_of_fire.automation == [
        {"type": "target", "mode": "area"},
        {"type": "saving_throw", "ability": "dex", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "damage",
            "dice": "5d8",
            "damage_type": "fire",
            "save_half": True,
            "base_spell_slot_level": 4,
            "extra_dice_per_slot_above": "1d8",
        },
        {
            "type": "world_effect",
            "effect_type": "wall_of_fire",
            "scope": {"target": "solid_surface", "range_ft": 120},
            "duration": {"until": "concentration_1_minute"},
            "tick_on": "self_turn_end",
            "metadata": {
                "solid_surface_required": True,
                "opaque": True,
                "shape_options": ["wall", "ringed_wall"],
                "wall_max_length_ft": 60,
                "wall_max_height_ft": 20,
                "wall_thickness_ft": 1,
                "ringed_wall_max_diameter_ft": 20,
                "ringed_wall_max_height_ft": 20,
                "ringed_wall_thickness_ft": 1,
                "initial_save": {
                    "ability": "dex",
                    "damage": "5d8 fire",
                    "save_half": True,
                    "higher_level_damage_increase": "1d8 per slot above 4",
                },
                "damaging_side_selected_on_cast": True,
                "damaging_side_range_ft": 10,
                "other_side_deals_no_damage": True,
                "repeat_damage_triggers": [
                    "creature_ends_turn_within_10_ft_of_damaging_side",
                    "creature_enters_wall_first_time_on_turn",
                    "creature_ends_turn_inside_wall",
                ],
                "repeat_damage_once_per_turn": True,
                "repeat_damage": {
                    "damage": "5d8 fire",
                    "higher_level_damage_increase": "1d8 per slot above 4",
                },
            },
        },
    ]
    blight = compendium.action("srd.blight")
    assert blight.requirements == {
        "spell_level": 4,
        "class_any": ["druid", "sorcerer", "warlock", "wizard"],
    }
    assert blight.properties["spell_classes"] == ["druid", "sorcerer", "warlock", "wizard"]
    assert blight.automation == [
        {"type": "target", "mode": "explicit"},
        {
            "type": "saving_throw",
            "ability": "con",
            "dc_from": {"spell_save_dc": "actor"},
            "auto_fail_creature_types": ["plant"],
        },
        {
            "type": "damage",
            "dice": "8d8",
            "damage_type": "necrotic",
            "save_half": True,
            "base_spell_slot_level": 4,
            "extra_dice_per_slot_above": "1d8",
        },
    ]
    cone_of_cold = compendium.action("srd.cone_of_cold")
    assert cone_of_cold.requirements == {
        "spell_level": 5,
        "class_any": ["druid", "sorcerer", "wizard"],
    }
    assert cone_of_cold.properties["spell_classes"] == ["druid", "sorcerer", "wizard"]
    assert cone_of_cold.properties["material_component"] == {
        "description": "a small crystal or glass cone",
        "consumed": False,
    }
    assert cone_of_cold.properties["creature_killed_becomes_frozen_statue_until_thaws"] is True
    assert cone_of_cold.range == {"self": True, "shape": "cone", "length_ft": 60}
    assert cone_of_cold.target_policy == {"min": 1, "max": 12, "harmful": True}
    assert cone_of_cold.automation == [
        {"type": "target", "mode": "area"},
        {"type": "saving_throw", "ability": "con", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "damage",
            "dice": "8d8",
            "damage_type": "cold",
            "save_half": True,
            "base_spell_slot_level": 5,
            "extra_dice_per_slot_above": "1d8",
        },
        {
            "type": "text_result",
            "text": "A creature killed by Cone of Cold becomes a frozen statue until it thaws.",
        },
    ]
    flame_strike = compendium.action("srd.flame_strike")
    assert flame_strike.requirements == {"spell_level": 5, "class_any": ["cleric"]}
    assert flame_strike.properties["spell_classes"] == ["cleric"]
    assert flame_strike.properties["material_component"] == {
        "description": "a pinch of sulfur",
        "consumed": False,
    }
    assert flame_strike.properties["higher_level_increases_fire_and_radiant_damage"] is True
    assert flame_strike.range == {
        "normal_ft": 60,
        "shape": "cylinder",
        "radius_ft": 10,
        "height_ft": 40,
    }
    assert flame_strike.target_policy == {"min": 1, "max": 8, "harmful": True}
    assert flame_strike.automation == [
        {"type": "target", "mode": "area"},
        {"type": "saving_throw", "ability": "dex", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "damage",
            "dice": "5d6",
            "damage_type": "fire",
            "save_half": True,
            "base_spell_slot_level": 5,
            "extra_dice_per_slot_above": "1d6",
        },
        {
            "type": "damage",
            "dice": "5d6",
            "damage_type": "radiant",
            "save_half": True,
            "base_spell_slot_level": 5,
            "extra_dice_per_slot_above": "1d6",
        },
    ]
    harm = compendium.action("srd.harm")
    assert harm.requirements == {"spell_level": 6, "class_any": ["cleric"]}
    assert harm.properties["spell_classes"] == ["cleric"]
    assert harm.properties["hp_max_reduction_equals_necrotic_damage_taken"] is True
    assert harm.properties["hp_max_reduction_minimum_hp_max"] == 1
    assert harm.range == {"normal_ft": 60}
    assert harm.target_policy == {"min": 1, "max": 1, "harmful": True}
    assert harm.automation == [
        {"type": "target", "mode": "explicit"},
        {"type": "saving_throw", "ability": "con", "dc_from": {"spell_save_dc": "actor"}},
        {"type": "damage", "dice": "14d6", "damage_type": "necrotic", "save_half": True},
        {
            "type": "branch",
            "condition": "last_save_success",
            "if_true": [],
            "if_false": [
                {
                    "type": "max_hp_delta",
                    "amount_from": "-last_damage_taken",
                    "record_hp_max_reduction_marker": True,
                }
            ],
        },
    ]
    circle_of_death = compendium.action("srd.circle_of_death")
    assert circle_of_death.requirements == {
        "spell_level": 6,
        "class_any": ["sorcerer", "warlock", "wizard"],
    }
    assert circle_of_death.properties["spell_classes"] == ["sorcerer", "warlock", "wizard"]
    assert circle_of_death.properties["material_component"] == {
        "description": "the powder of a crushed black pearl worth 500+ GP",
        "consumed": False,
    }
    assert circle_of_death.range == {"normal_ft": 150, "shape": "sphere", "radius_ft": 60}
    assert circle_of_death.target_policy == {"min": 1, "max": 32, "harmful": True}
    assert circle_of_death.automation == [
        {"type": "target", "mode": "area"},
        {"type": "saving_throw", "ability": "con", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "damage",
            "dice": "8d8",
            "damage_type": "necrotic",
            "save_half": True,
            "base_spell_slot_level": 6,
            "extra_dice_per_slot_above": "2d8",
        },
    ]
    chain_lightning = compendium.action("srd.chain_lightning")
    assert chain_lightning.requirements == {
        "spell_level": 6,
        "class_any": ["sorcerer", "wizard"],
    }
    assert chain_lightning.properties["spell_classes"] == ["sorcerer", "wizard"]
    assert chain_lightning.properties["material_component"] == {
        "description": "three silver pins",
        "consumed": False,
    }
    assert chain_lightning.properties["primary_target_must_be_visible_within_range"] is True
    assert chain_lightning.properties["secondary_bolts_leap_from_first_target"] is True
    assert chain_lightning.properties["secondary_targets_must_be_within_ft_of_first_target"] == 30
    assert chain_lightning.properties["targets_can_be_creatures_or_objects"] is True
    assert chain_lightning.properties["target_can_be_hit_by_only_one_bolt"] is True
    assert chain_lightning.properties["higher_level_additional_targets_per_slot_above_6"] == 1
    assert chain_lightning.range == {"normal_ft": 150}
    assert chain_lightning.target_policy == {
        "min": 1,
        "max": 4,
        "harmful": True,
        "base_spell_slot_level": 6,
        "max_targets_per_slot_above": 1,
    }
    assert chain_lightning.automation == [
        {"type": "target", "mode": "explicit"},
        {"type": "saving_throw", "ability": "dex", "dc_from": {"spell_save_dc": "actor"}},
        {"type": "damage", "dice": "10d8", "damage_type": "lightning", "save_half": True},
    ]
    sunburst_spell = compendium.spell("srd.spell.sunburst")
    assert sunburst_spell.level == 8
    assert sunburst_spell.school == "evocation"
    assert sunburst_spell.classes == ["cleric", "druid", "sorcerer", "wizard"]
    sunburst = compendium.action("srd.sunburst")
    assert sunburst.requirements == {
        "spell_level": 8,
        "class_any": ["cleric", "druid", "sorcerer", "wizard"],
    }
    assert sunburst.properties == {
        "spell_classes": ["cleric", "druid", "sorcerer", "wizard"],
        "components": ["V", "S", "M"],
        "material_component": {
            "description": "a piece of sunstone",
            "consumed": False,
        },
        "sunlight_sphere_radius_ft": 60,
        "dispels_spell_created_darkness_in_area": True,
        "spell_definition_id": "srd.spell.sunburst",
        "spell_level": 8,
    }
    assert sunburst.cost.spell_slot_level == 8
    assert sunburst.range == {"normal_ft": 150, "shape": "sphere", "radius_ft": 60}
    assert sunburst.target_policy == {"min": 1, "max": 32, "harmful": True}
    assert sunburst.automation == [
        {"type": "target", "mode": "area"},
        {"type": "saving_throw", "ability": "con", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "damage",
            "dice": "12d6",
            "damage_type": "radiant",
            "save_half": True,
        },
        {
            "type": "condition",
            "condition": "blinded",
            "requires_failed_save": True,
            "duration": {
                "until": "duration_1_minute",
                "repeat_save": {
                    "ability": "con",
                    "dc_from": {"spell_save_dc": "actor"},
                    "end_on_success": True,
                    "trigger": "target_turn_end",
                },
            },
            "tick_on": "target_turn_end",
        },
        {
            "type": "text_result",
            "text": (
                "Brilliant sunlight fills a 60-foot-radius Sphere and dispels "
                "Darkness in the area that was created by any spell."
            ),
        },
    ]
    mind_blank_spell = compendium.spell("srd.spell.mind_blank")
    assert mind_blank_spell.level == 8
    assert mind_blank_spell.school == "abjuration"
    assert mind_blank_spell.classes == ["bard", "wizard"]
    mind_blank = compendium.action("srd.mind_blank")
    assert mind_blank.requirements == {
        "spell_level": 8,
        "class_any": ["bard", "wizard"],
    }
    assert mind_blank.properties == {
        "spell_classes": ["bard", "wizard"],
        "components": ["V", "S"],
        "target_type": "creature",
        "target_must_be_touched": True,
        "requires_willing_target": True,
        "unaffected_by_emotion_sensing": True,
        "unaffected_by_alignment_sensing": True,
        "unaffected_by_read_thoughts": True,
        "unaffected_by_magical_location_detection": True,
        "no_spell_can_gather_information_about_target": True,
        "no_spell_can_observe_target_remotely": True,
        "no_spell_can_control_targets_mind": True,
        "wish_is_not_exception": True,
        "spell_definition_id": "srd.spell.mind_blank",
        "spell_level": 8,
    }
    assert mind_blank.cost.spell_slot_level == 8
    assert mind_blank.range == {"touch": True}
    assert mind_blank.target_policy == {"min": 1, "max": 1, "harmful": False}
    assert mind_blank.automation == [
        {"type": "target", "mode": "explicit"},
        {
            "type": "passive_effect",
            "passive_modifiers": {
                "mind_blank": True,
                "damage_immunities": ["psychic"],
                "condition_immunities": ["charmed"],
                "unaffected_by_emotion_sensing": True,
                "unaffected_by_alignment_sensing": True,
                "unaffected_by_read_thoughts": True,
                "unaffected_by_magical_location_detection": True,
                "spell_information_gathering_blocked": True,
                "remote_observation_blocked": True,
                "mind_control_blocked": True,
                "wish_is_not_exception": True,
                "information_observation_and_mind_control_resolution_not_automated": True,
            },
            "duration": {"until": "duration_24_hours"},
            "tick_on": "self_turn_end",
        },
    ]
    glibness_spell = compendium.spell("srd.spell.glibness")
    assert glibness_spell.level == 8
    assert glibness_spell.school == "enchantment"
    assert glibness_spell.classes == ["bard", "warlock"]
    glibness = compendium.action("srd.glibness")
    assert glibness.requirements == {
        "spell_level": 8,
        "class_any": ["bard", "warlock"],
    }
    assert glibness.properties == {
        "spell_classes": ["bard", "warlock"],
        "components": ["V"],
        "charisma_check_minimum_d20": 15,
        "magic_truth_detection_indicates_truthful": True,
        "truth_detection_resolution_not_automated": True,
        "spell_definition_id": "srd.spell.glibness",
        "spell_level": 8,
    }
    assert glibness.cost.spell_slot_level == 8
    assert glibness.range == {"self": True}
    assert glibness.target_policy == {"min": 1, "max": 1, "self": True, "harmful": False}
    assert glibness.automation == [
        {"type": "target", "mode": "self"},
        {
            "type": "passive_effect",
            "passive_modifiers": {
                "glibness": True,
                "charisma_check_minimum_d20": 15,
                "magic_truth_detection_indicates_truthful": True,
                "truth_detection_resolution_not_automated": True,
            },
            "duration": {"until": "duration_1_hour"},
            "tick_on": "self_turn_end",
        },
    ]
    disintegrate = compendium.action("srd.disintegrate")
    assert disintegrate.requirements == {
        "spell_level": 6,
        "class_any": ["sorcerer", "wizard"],
    }
    assert disintegrate.properties["spell_classes"] == ["sorcerer", "wizard"]
    assert disintegrate.properties["material_component"] == {
        "description": "a lodestone and dust",
        "consumed": False,
    }
    assert disintegrate.properties["target_options"] == [
        "creature",
        "nonmagical_object",
        "creation_of_magical_force",
    ]
    assert disintegrate.properties["creation_of_magical_force_example"] == "Wall of Force"
    assert (
        disintegrate.properties["zero_hp_disintegrates_target_and_nonmagical_worn_carried"] is True
    )
    assert disintegrate.properties["disintegrated_into"] == "gray dust"
    assert disintegrate.properties["revival_only_by"] == ["True Resurrection", "Wish"]
    assert (
        disintegrate.properties[
            "auto_disintegrates_large_or_smaller_nonmagical_object_or_magical_force"
        ]
        is True
    )
    assert disintegrate.properties["huge_or_larger_object_or_force_disintegrated_portion"] == {
        "shape": "cube",
        "size_ft": 10,
    }
    assert disintegrate.range == {"normal_ft": 60}
    assert disintegrate.target_policy == {"min": 1, "max": 1, "harmful": True}
    assert disintegrate.automation == [
        {"type": "target", "mode": "explicit"},
        {"type": "saving_throw", "ability": "dex", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "branch",
            "condition": "last_save_success",
            "if_true": [
                {
                    "type": "text_result",
                    "text": "The target succeeds; Disintegrate deals no damage.",
                }
            ],
            "if_false": [
                {
                    "type": "damage",
                    "dice": "10d6+40",
                    "damage_type": "force",
                    "base_spell_slot_level": 6,
                    "extra_dice_per_slot_above": "3d6",
                },
                {
                    "type": "text_result",
                    "text": (
                        "If this damage reduces the target to 0 HP, apply the SRD "
                        "disintegration aftermath."
                    ),
                },
            ],
        },
    ]
    finger_of_death = compendium.action("srd.finger_of_death")
    assert finger_of_death.requirements == {
        "spell_level": 7,
        "class_any": ["sorcerer", "warlock", "wizard"],
    }
    assert finger_of_death.properties["spell_classes"] == ["sorcerer", "warlock", "wizard"]
    assert finger_of_death.properties["humanoid_killed_rises_as"] == "srd.zombie"
    assert finger_of_death.properties["humanoid_killed_rises_at"] == "start_of_caster_next_turn"
    assert finger_of_death.properties["zombie_follows_verbal_orders"] is True
    assert finger_of_death.range == {"normal_ft": 60}
    assert finger_of_death.target_policy == {"min": 1, "max": 1, "harmful": True}
    assert finger_of_death.automation == [
        {"type": "target", "mode": "explicit"},
        {"type": "saving_throw", "ability": "con", "dc_from": {"spell_save_dc": "actor"}},
        {"type": "damage", "dice": "7d8+30", "damage_type": "necrotic", "save_half": True},
        {
            "type": "text_result",
            "text": (
                "If a Humanoid is killed by this spell, it rises at the start of the "
                "caster's next turn as a Zombie that follows the caster's verbal orders."
            ),
        },
    ]
    fire_storm = compendium.action("srd.fire_storm")
    assert fire_storm.requirements == {
        "spell_level": 7,
        "class_any": ["cleric", "druid", "sorcerer"],
    }
    assert fire_storm.properties["spell_classes"] == ["cleric", "druid", "sorcerer"]
    assert fire_storm.properties["area_shape"] == {
        "shape": "contiguous_cubes",
        "max_cubes": 10,
        "cube_size_ft": 10,
        "cube_contiguity": "contiguous_with_at_least_one_other_cube",
    }
    assert fire_storm.properties["flammable_objects_not_worn_or_carried_start_burning"] is True
    assert fire_storm.range == {"normal_ft": 150, "shape": "area"}
    assert fire_storm.target_policy == {"min": 1, "max": 20, "harmful": True}
    assert fire_storm.automation == [
        {"type": "target", "mode": "area"},
        {"type": "saving_throw", "ability": "dex", "dc_from": {"spell_save_dc": "actor"}},
        {"type": "damage", "dice": "7d10", "damage_type": "fire", "save_half": True},
        {
            "type": "text_result",
            "text": (
                "The fire storm uses up to ten contiguous 10-foot cubes; "
                "flammable objects not worn or carried in the area start burning."
            ),
        },
    ]
    meteor_swarm = compendium.action("srd.meteor_swarm")
    assert meteor_swarm.requirements == {
        "spell_level": 9,
        "class_any": ["sorcerer", "wizard"],
    }
    assert meteor_swarm.properties["spell_classes"] == ["sorcerer", "wizard"]
    assert meteor_swarm.properties["points"] == 4
    assert meteor_swarm.properties["points_must_be_visible"] is True
    assert meteor_swarm.properties["sphere_radius_ft"] == 40
    assert meteor_swarm.properties["creature_in_multiple_spheres_affected_once"] is True
    assert meteor_swarm.properties["nonmagical_objects_not_worn_or_carried_take_damage"] is True
    assert meteor_swarm.properties["flammable_objects_not_worn_or_carried_start_burning"] is True
    assert meteor_swarm.range == {"normal_ft": 5280, "shape": "sphere", "radius_ft": 40}
    assert meteor_swarm.target_policy == {"min": 1, "max": 24, "harmful": True}
    assert meteor_swarm.automation == [
        {"type": "target", "mode": "area"},
        {"type": "saving_throw", "ability": "dex", "dc_from": {"spell_save_dc": "actor"}},
        {"type": "damage", "dice": "20d6", "damage_type": "fire", "save_half": True},
        {
            "type": "damage",
            "dice": "20d6",
            "damage_type": "bludgeoning",
            "save_half": True,
        },
    ]
    greater_invisibility = compendium.action("srd.greater_invisibility")
    assert greater_invisibility.requirements == {
        "spell_level": 4,
        "class_any": ["bard", "sorcerer", "wizard"],
    }
    assert greater_invisibility.properties["spell_classes"] == ["bard", "sorcerer", "wizard"]
    assert greater_invisibility.properties["target_type"] == "creature"
    assert greater_invisibility.properties["target_must_be_touched"] is True
    assert greater_invisibility.properties["does_not_end_early_on_attack_damage_or_spell"] is True
    assert greater_invisibility.range == {"touch": True}
    assert greater_invisibility.automation == [
        {"type": "target", "mode": "explicit"},
        {
            "type": "condition",
            "condition": "invisible",
            "duration": {"until": "concentration_1_minute"},
            "tick_on": "target_turn_start",
            "concentration": True,
        },
    ]
    hallucinatory_terrain = compendium.action("srd.hallucinatory_terrain")
    assert hallucinatory_terrain.requirements == {
        "spell_level": 4,
        "class_any": ["bard", "druid", "warlock", "wizard"],
    }
    assert hallucinatory_terrain.properties["spell_classes"] == [
        "bard",
        "druid",
        "warlock",
        "wizard",
    ]
    assert hallucinatory_terrain.properties["casting_time"] == {"minutes": 10}
    assert hallucinatory_terrain.properties["material_component"] == {
        "description": "a mushroom",
        "consumed": False,
    }
    assert hallucinatory_terrain.cost.spell_slot_level == 4
    assert hallucinatory_terrain.range == {
        "normal_ft": 300,
        "shape": "cube",
        "size_ft": 150,
    }
    assert hallucinatory_terrain.target_policy == {"min": 0, "max": 0, "harmful": False}
    assert hallucinatory_terrain.automation == [
        {
            "type": "world_effect",
            "effect_type": "hallucinatory_terrain",
            "scope": {
                "target": "natural_terrain",
                "range_ft": 300,
                "shape": "cube",
                "size_ft": 150,
            },
            "duration": {"until": "duration_24_hours"},
            "tick_on": "self_turn_end",
            "metadata": {
                "natural_terrain_only": True,
                "makes_terrain_look_sound_and_smell_like_another_natural_terrain": True,
                "examples": [
                    "open_field_or_road_to_swamp_hill_crevasse_or_other_difficult_or_impassable_terrain",
                    "pond_to_grassy_meadow",
                    "precipice_to_gentle_slope",
                    "rock_strewn_gully_to_wide_smooth_road",
                ],
                "manufactured_structures_equipment_and_creatures_unchanged": True,
                "tactile_characteristics_unchanged": True,
                "creatures_entering_likely_notice_by_touch": True,
                "disbelieve_check": {
                    "action": "study",
                    "ability": "int",
                    "skill": "investigation",
                    "dc_from": {"spell_save_dc": "actor"},
                },
                "disbelieved_illusion_appears_as_vague_image_superimposed_on_real_terrain": True,
            },
        }
    ]
    phantasmal_killer = compendium.action("srd.phantasmal_killer")
    assert phantasmal_killer.requirements == {
        "spell_level": 4,
        "class_any": ["bard", "wizard"],
    }
    assert phantasmal_killer.properties == {
        "spell_classes": ["bard", "wizard"],
        "target_must_be_visible": True,
        "target_type": "creature",
        "components": ["V", "S"],
        "spell_definition_id": "srd.spell.phantasmal_killer",
        "spell_level": 4,
    }
    assert phantasmal_killer.cost.spell_slot_level == 4
    assert phantasmal_killer.range == {"normal_ft": 120}
    assert phantasmal_killer.target_policy == {"min": 1, "max": 1, "harmful": True}
    assert phantasmal_killer.automation == [
        {"type": "target", "mode": "explicit"},
        {"type": "saving_throw", "ability": "wis", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "damage",
            "dice": "4d10",
            "damage_type": "psychic",
            "save_half": True,
            "base_spell_slot_level": 4,
            "extra_dice_per_slot_above": "1d10",
        },
        {
            "type": "passive_effect",
            "requires_failed_save": True,
            "passive_modifiers": {
                "phantasmal_killer": True,
                "ability_check_disadvantage_abilities": [
                    "str",
                    "dex",
                    "con",
                    "int",
                    "wis",
                    "cha",
                ],
                "attack_roll_disadvantage": True,
            },
            "duration": {
                "until": "concentration_1_minute",
                "repeat_save": {
                    "ability": "wis",
                    "dc_from": {"spell_save_dc": "actor"},
                    "end_on_success": True,
                    "trigger": "target_turn_end",
                    "failure_damage": {
                        "dice": "4d10",
                        "damage_type": "psychic",
                        "base_spell_slot_level": 4,
                        "extra_dice_per_slot_above": "1d10",
                    },
                },
            },
            "tick_on": "target_turn_end",
            "concentration": True,
        },
    ]
    creation_spell = compendium.spell("srd.spell.creation")
    assert creation_spell.level == 5
    assert creation_spell.school == "illusion"
    assert creation_spell.classes == ["sorcerer", "wizard"]
    creation = compendium.action("srd.creation")
    assert creation.requirements == {
        "spell_level": 5,
        "class_any": ["sorcerer", "wizard"],
    }
    assert creation.properties == {
        "spell_classes": ["sorcerer", "wizard"],
        "components": ["V", "S", "M"],
        "casting_time": {"minutes": 1},
        "material_component": {
            "description": "a paintbrush",
            "consumed": False,
        },
        "creation_material_param": "creation_material",
        "allowed_list_params": {
            "creation_material": [
                "vegetable_matter",
                "stone_or_crystal",
                "precious_metals",
                "gems",
                "adamantine_or_mithral",
            ]
        },
        "required_list_param_counts": {
            "creation_material": 1,
        },
        "spell_definition_id": "srd.spell.creation",
        "spell_level": 5,
    }
    assert creation.cost.spell_slot_level == 5
    assert creation.cost.gold == 0
    assert creation.range == {"normal_ft": 30}
    assert creation.target_policy == {"min": 0, "max": 0, "harmful": False}
    assert creation.automation == [
        {
            "type": "world_effect",
            "effect_type": "created_object",
            "scope": {
                "target": "object_within_range",
                "range_ft": 30,
            },
            "duration": {
                "duration_from_param": {
                    "param": "creation_material",
                    "by_value": {
                        "vegetable_matter": "duration_24_hours",
                        "stone_or_crystal": "duration_12_hours",
                        "precious_metals": "duration_1_hour",
                        "gems": "duration_10_minutes",
                        "adamantine_or_mithral": "duration_1_minute",
                    },
                }
            },
            "tick_on": "self_turn_end",
            "metadata": {
                "created_from_shadowfell_shadow_material": True,
                "selected_material": {"param_list": "creation_material"},
                "object_must_be_vegetable_or_mineral_matter": True,
                "vegetable_matter_examples": ["soft_goods", "rope", "wood"],
                "mineral_matter_examples": ["stone", "crystal", "metal"],
                "object_must_be_form_and_material_caster_has_seen": True,
                "multiple_materials_use_shortest_duration": True,
                "selected_material_must_be_shortest_duration_if_multiple_materials": True,
                "duration_by_material": {
                    "vegetable_matter": "duration_24_hours",
                    "stone_or_crystal": "duration_12_hours",
                    "precious_metals": "duration_1_hour",
                    "gems": "duration_10_minutes",
                    "adamantine_or_mithral": "duration_1_minute",
                },
                "using_created_object_as_material_component_causes_other_spell_to_fail": True,
            },
            "metadata_from_slot": {
                "max_cube_side_ft": {
                    "base_spell_slot_level": 5,
                    "base_value": 5,
                    "value_per_slot_above": 5,
                }
            },
        }
    ]
    programmed_illusion_spell = compendium.spell("srd.spell.programmed_illusion")
    assert programmed_illusion_spell.level == 6
    assert programmed_illusion_spell.school == "illusion"
    assert programmed_illusion_spell.classes == ["bard", "wizard"]
    programmed_illusion = compendium.action("srd.programmed_illusion")
    assert programmed_illusion.requirements == {
        "spell_level": 6,
        "class_any": ["bard", "wizard"],
    }
    assert programmed_illusion.properties == {
        "spell_classes": ["bard", "wizard"],
        "components": ["V", "S", "M"],
        "material_component": {
            "description": "jade dust worth 25+ GP",
            "consumed": False,
        },
        "max_cube_size_ft": 30,
        "scripted_performance_max_minutes": 5,
        "trigger_range_ft": 30,
        "dormant_after_performance_minutes": 10,
        "spell_definition_id": "srd.spell.programmed_illusion",
        "spell_level": 6,
    }
    assert programmed_illusion.cost.spell_slot_level == 6
    assert programmed_illusion.cost.gold == 0
    assert programmed_illusion.range == {"normal_ft": 120, "shape": "cube", "max_size_ft": 30}
    assert programmed_illusion.target_policy == {"min": 0, "max": 0, "harmful": False}
    assert programmed_illusion.automation == [
        {
            "type": "world_effect",
            "effect_type": "programmed_illusion",
            "scope": {
                "target": "visible_phenomenon_within_range",
                "range_ft": 120,
                "shape": "cube",
                "max_size_ft": 30,
            },
            "duration": {"until": "until_dispelled"},
            "metadata": {
                "illusion_can_be_object_creature_or_visible_phenomenon": True,
                "imperceptible_until_triggered": True,
                "trigger_specified_on_cast": True,
                "trigger_must_be_visual_or_audible_phenomenon": True,
                "trigger_must_occur_within_ft_of_area": 30,
                "behavior_and_sounds_scripted_on_cast": True,
                "scripted_performance_max_minutes": 5,
                "disappears_after_performance": True,
                "dormant_after_performance_minutes": 10,
                "can_activate_again_after_dormant_period": True,
                "physical_interaction_reveals_illusion": True,
                "things_can_pass_through_image": True,
                "disbelieve_check": {
                    "action": "study",
                    "ability": "int",
                    "skill": "investigation",
                    "dc_from": {"spell_save_dc": "actor"},
                },
                "discerned_creature_can_see_through_image": True,
                "discerned_noise_sounds_hollow": True,
                "trigger_and_performance_resolution_not_automated": True,
            },
        }
    ]
    freedom_of_movement = compendium.action("srd.freedom_of_movement")
    assert freedom_of_movement.requirements == {
        "spell_level": 4,
        "class_any": ["bard", "cleric", "druid", "ranger"],
    }
    assert freedom_of_movement.properties["spell_classes"] == [
        "bard",
        "cleric",
        "druid",
        "ranger",
    ]
    assert freedom_of_movement.properties["requires_willing_target"] is True
    assert freedom_of_movement.properties["material_component"] == {
        "description": "a leather strap",
        "consumed": False,
    }
    assert (
        freedom_of_movement.properties["higher_level_additional_targets_per_slot_above_4"] == 1
    )
    assert freedom_of_movement.cost.spell_slot_level == 4
    assert freedom_of_movement.range == {"touch": True}
    assert freedom_of_movement.target_policy == {
        "min": 1,
        "max": 1,
        "harmful": False,
        "base_spell_slot_level": 4,
        "max_targets_per_slot_above": 1,
    }
    assert freedom_of_movement.automation == [
        {"type": "target", "mode": "explicit"},
        {
            "type": "passive_effect",
            "passive_modifiers": {
                "freedom_of_movement": True,
                "difficult_terrain_unaffected": True,
                "magical_speed_reduction_immunity": True,
                "magical_paralyzed_restrained_immunity": True,
                "swim_speed_equals_speed": True,
                "nonmagical_restraints_escape_movement_cost_ft": 5,
            },
            "duration": {"until": "duration_1_hour"},
            "tick_on": "self_turn_end",
        },
    ]
    private_sanctum = compendium.action("srd.private_sanctum")
    assert private_sanctum.requirements == {
        "spell_level": 4,
        "class_any": ["wizard"],
    }
    assert private_sanctum.properties["spell_classes"] == ["wizard"]
    assert private_sanctum.properties["casting_time"] == {"minutes": 10}
    assert private_sanctum.properties["material_component"] == {
        "description": "a thin sheet of lead",
        "consumed": False,
    }
    assert private_sanctum.properties["protections_param"] == "private_sanctum_protections"
    assert private_sanctum.properties["allowed_list_params"] == {
        "private_sanctum_protections": [
            "blocks_sound_through_barrier",
            "blocks_vision_through_barrier_including_darkvision",
            "blocks_divination_sensors_entering_or_appearing_inside",
            "blocks_divination_targeting_creatures_inside",
            "blocks_teleport_into_or_out_of_area",
            "blocks_planar_travel_within_area",
        ]
    }
    assert private_sanctum.cost.spell_slot_level == 4
    assert private_sanctum.cost.gold == 0
    assert private_sanctum.range == {"normal_ft": 120, "shape": "cube", "min_side_ft": 5}
    assert private_sanctum.target_policy == {"min": 0, "max": 0, "harmful": False}
    assert private_sanctum.automation == [
        {
            "type": "world_effect",
            "effect_type": "private_sanctum_ward",
            "scope": {
                "target": "warded_area",
                "range_ft": 120,
                "shape": "cube",
                "min_side_ft": 5,
            },
            "duration": {"until": "duration_24_hours"},
            "tick_on": "self_turn_end",
            "metadata": {
                "selected_protections": {"param_list": "private_sanctum_protections"},
                "allowed_protections": [
                    "blocks_sound_through_barrier",
                    "blocks_vision_through_barrier_including_darkvision",
                    "blocks_divination_sensors_entering_or_appearing_inside",
                    "blocks_divination_targeting_creatures_inside",
                    "blocks_teleport_into_or_out_of_area",
                    "blocks_planar_travel_within_area",
                ],
                "choose_any_listed_protections_on_cast": True,
                "permanent_if_cast_daily_same_location_days": 365,
            },
            "metadata_from_slot": {
                "max_cube_side_ft": {
                    "base_spell_slot_level": 4,
                    "base_value": 100,
                    "value_per_slot_above": 100,
                }
            },
        }
    ]
    resilient_sphere = compendium.action("srd.resilient_sphere")
    assert resilient_sphere.requirements == {
        "spell_level": 4,
        "class_any": ["wizard"],
    }
    assert resilient_sphere.properties["spell_classes"] == ["wizard"]
    assert resilient_sphere.properties["material_component"] == {
        "description": "a glass sphere",
        "consumed": False,
    }
    assert resilient_sphere.properties["target_size_max"] == "large"
    assert resilient_sphere.properties["allows_willing_target"] is True
    assert resilient_sphere.properties["can_enclose_large_or_smaller_creature_or_object"] is True
    assert resilient_sphere.properties["object_targets_recorded_as_metadata_only"] is True
    assert resilient_sphere.cost.spell_slot_level == 4
    assert resilient_sphere.range == {"normal_ft": 30}
    assert resilient_sphere.target_policy == {"min": 1, "max": 1, "harmful": True}
    assert resilient_sphere.automation == [
        {"type": "target", "mode": "explicit"},
        {
            "type": "saving_throw",
            "ability": "dex",
            "dc_from": {"spell_save_dc": "actor"},
            "auto_fail_willing_targets": True,
        },
        {
            "type": "passive_effect",
            "requires_failed_save": True,
            "passive_modifiers": {
                "resilient_sphere": True,
                "enclosed_in_resilient_sphere": True,
                "can_enclose_large_or_smaller_creature_or_object": True,
                "barrier_blocks_physical_objects_energy_and_spell_effects": True,
                "barrier_blocks_in_or_out": True,
                "inside_can_breathe": True,
                "barrier_immune_to_all_damage": True,
                "outside_origin_attacks_and_effects_cannot_damage_inside": True,
                "inside_creature_cannot_damage_outside": True,
                "sphere_weightless": True,
                "sphere_just_large_enough_for_contents": True,
                "enclosed_creature_can_action_roll_sphere_up_to_half_speed": True,
                "globe_can_be_picked_up_and_moved": True,
                "disintegrate_targeting_globe_destroys_it": True,
            },
            "duration": {"until": "concentration_1_minute"},
            "tick_on": "self_turn_end",
            "concentration": True,
        },
    ]
    banishment = compendium.action("srd.banishment")
    assert banishment.requirements == {
        "spell_level": 4,
        "class_any": ["cleric", "paladin", "sorcerer", "warlock", "wizard"],
    }
    assert banishment.properties["spell_classes"] == [
        "cleric",
        "paladin",
        "sorcerer",
        "warlock",
        "wizard",
    ]
    assert banishment.properties["material_component"] == {
        "description": "a pentacle",
        "consumed": False,
    }
    assert banishment.properties["target_must_be_visible"] is True
    assert banishment.properties["higher_level_additional_targets_per_slot_above_4"] == 1
    assert banishment.cost.spell_slot_level == 4
    assert banishment.range == {"normal_ft": 30}
    assert banishment.target_policy == {
        "min": 1,
        "max": 1,
        "harmful": True,
        "base_spell_slot_level": 4,
        "max_targets_per_slot_above": 1,
    }
    assert banishment.automation == [
        {"type": "target", "mode": "explicit"},
        {"type": "saving_throw", "ability": "cha", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "passive_effect",
            "requires_failed_save": True,
            "passive_modifiers": {
                "banished": True,
                "out_of_play": True,
                "banished_to_harmless_demiplane": True,
                "returns_when_spell_ends": True,
                "returns_to_space_left_or_nearest_unoccupied": True,
                "does_not_return_if_full_duration_creature_types": [
                    "aberration",
                    "celestial",
                    "elemental",
                    "fey",
                    "fiend",
                ],
                "full_duration_transport_destination": (
                    "random_location_on_gm_chosen_associated_plane"
                ),
            },
            "duration": {"until": "concentration_1_minute"},
            "tick_on": "self_turn_end",
            "concentration": True,
        },
        {
            "type": "condition",
            "condition": "incapacitated",
            "requires_failed_save": True,
            "duration": {"until": "concentration_1_minute"},
            "tick_on": "self_turn_end",
            "concentration": True,
        },
    ]
    aura_of_life = compendium.action("srd.aura_of_life")
    assert aura_of_life.requirements == {
        "spell_level": 4,
        "class_any": ["cleric", "paladin"],
    }
    assert aura_of_life.properties == {
        "spell_classes": ["cleric", "paladin"],
        "components": ["V"],
        "self_centered_emanation_radius_ft": 30,
        "spell_definition_id": "srd.spell.aura_of_life",
        "spell_level": 4,
    }
    assert aura_of_life.cost.spell_slot_level == 4
    assert aura_of_life.range == {"self": True, "shape": "emanation", "radius_ft": 30}
    assert aura_of_life.target_policy == {
        "min": 0,
        "max": 0,
        "self": True,
        "harmful": False,
    }
    assert aura_of_life.automation == [
        {"type": "target", "mode": "self"},
        {
            "type": "world_effect",
            "effect_type": "aura_of_life",
            "scope": {"target": "self_centered_emanation", "radius_ft": 30},
            "duration": {"until": "concentration_10_minutes"},
            "tick_on": "self_turn_end",
            "metadata": {
                "self_centered_emanation": True,
                "caster_and_allies_in_aura_gain_necrotic_resistance": True,
                "caster_and_allies_in_aura_hp_max_cannot_be_reduced": True,
                "ally_at_0_hp_starts_turn_in_aura_regains_hp": 1,
                "dynamic_aura_membership_not_automated": True,
                "turn_start_healing_not_automated": True,
            },
            "concentration": True,
        },
        {
            "type": "passive_effect",
            "passive_modifiers": {
                "aura_of_life": True,
                "damage_resistances": ["necrotic"],
                "prevents_hp_max_reduction": True,
            },
            "duration": {"until": "concentration_10_minutes"},
            "tick_on": "self_turn_end",
            "concentration": True,
        },
    ]
    death_ward = compendium.action("srd.death_ward")
    assert death_ward.requirements == {
        "spell_level": 4,
        "class_any": ["cleric", "paladin"],
    }
    assert death_ward.properties == {
        "spell_classes": ["cleric", "paladin"],
        "target_type": "creature",
        "target_must_be_touched": True,
        "first_drop_to_0_hp_sets_hp_to_1_and_ends": True,
        "negates_instant_death_without_damage_and_ends": True,
        "spell_definition_id": "srd.spell.death_ward",
        "spell_level": 4,
    }
    assert death_ward.cost.spell_slot_level == 4
    assert death_ward.range == {"touch": True}
    assert death_ward.target_policy == {"min": 1, "max": 1, "harmful": False}
    assert death_ward.automation == [
        {"type": "target", "mode": "explicit"},
        {
            "type": "passive_effect",
            "passive_modifiers": {
                "death_ward": True,
                "first_drop_to_0_hp_sets_hp_to_1": True,
                "negates_instant_death_without_damage": True,
            },
            "duration": {"until": "duration_8_hours"},
            "tick_on": "self_turn_end",
        },
    ]
    mass_cure_wounds = compendium.action("srd.mass_cure_wounds")
    assert mass_cure_wounds.requirements == {
        "spell_level": 5,
        "class_any": ["bard", "cleric", "druid"],
    }
    assert mass_cure_wounds.properties["spell_classes"] == ["bard", "cleric", "druid"]
    assert mass_cure_wounds.range == {"normal_ft": 60, "shape": "sphere", "radius_ft": 30}
    assert mass_cure_wounds.target_policy == {"min": 1, "max": 6, "harmful": False}
    assert mass_cure_wounds.automation == [
        {"type": "target", "mode": "explicit"},
        {
            "type": "healing",
            "dice": "5d8",
            "bonus_from": {"spellcasting_ability_modifier": "actor"},
            "base_spell_slot_level": 5,
            "extra_dice_per_slot_above": "1d8",
        },
    ]
    heal = compendium.action("srd.heal")
    assert heal.requirements == {"spell_level": 6, "class_any": ["cleric", "druid"]}
    assert heal.properties["spell_classes"] == ["cleric", "druid"]
    assert heal.properties["target_type"] == "creature"
    assert heal.properties["target_must_be_visible"] is True
    assert heal.properties["higher_level_healing_increase_per_slot_above_6"] == 10
    assert heal.range == {"normal_ft": 60}
    assert heal.target_policy == {"min": 1, "max": 1, "harmful": False}
    assert heal.automation == [
        {"type": "target", "mode": "explicit"},
        {
            "type": "healing",
            "amount": 70,
            "base_spell_slot_level": 6,
            "extra_amount_per_slot_above": 10,
        },
        {"type": "remove_condition", "conditions": ["blinded", "deafened", "poisoned"]},
    ]
    charm_monster = compendium.action("srd.charm_monster")
    assert charm_monster.requirements == {
        "spell_level": 4,
        "class_any": ["bard", "druid", "sorcerer", "warlock", "wizard"],
    }
    assert charm_monster.properties["spell_classes"] == [
        "bard",
        "druid",
        "sorcerer",
        "warlock",
        "wizard",
    ]
    assert charm_monster.properties["target_must_be_visible"] is True
    assert charm_monster.properties["target_type"] == "creature"
    assert (
        charm_monster.properties["saving_throw_advantage_if_caster_or_allies_fighting_target"]
        is True
    )
    assert charm_monster.properties["target_friendly_to_applier"] is True
    assert charm_monster.properties["target_knows_charmed_when_spell_ends"] is True
    assert charm_monster.range == {"normal_ft": 30}
    assert charm_monster.target_policy == {
        "min": 1,
        "max": 1,
        "harmful": True,
        "base_spell_slot_level": 4,
        "max_targets_per_slot_above": 1,
    }
    assert charm_monster.automation == [
        {"type": "target", "mode": "explicit"},
        {"type": "saving_throw", "ability": "wis", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "condition",
            "condition": "charmed",
            "requires_failed_save": True,
            "passive_modifiers": {
                "target_friendly_to_applier": True,
                "target_knows_charmed_when_spell_ends": True,
            },
            "duration": {
                "until": "duration_1_hour_or_harmed",
                "break_on_damage": True,
                "break_on_damage_by": "applied_by_or_allies",
            },
            "tick_on": "duration_or_damage",
        },
    ]
    confusion = compendium.action("srd.confusion")
    confusion_behavior_table = [
        {
            "min": 1,
            "max": 1,
            "behavior": "no_action_uses_all_movement_random_direction",
            "direction_roll": "1d4",
            "directions": {"1": "north", "2": "east", "3": "south", "4": "west"},
        },
        {"min": 2, "max": 6, "behavior": "no_movement_or_actions"},
        {
            "min": 7,
            "max": 8,
            "behavior": "attack_action_one_melee_attack_random_creature_within_reach_or_no_action",
        },
        {"min": 9, "max": 10, "behavior": "target_chooses_behavior"},
    ]
    assert confusion.requirements == {
        "spell_level": 4,
        "class_any": ["bard", "druid", "sorcerer", "wizard"],
    }
    assert confusion.properties == {
        "spell_classes": ["bard", "druid", "sorcerer", "wizard"],
        "material_component": {
            "description": "three nut shells",
            "consumed": False,
        },
        "base_sphere_radius_ft": 10,
        "sphere_radius_increase_ft_per_slot_above_4": 5,
        "target_turn_start_behavior_roll": "1d10",
        "behavior_roll_not_automated": True,
        "behavior_table": confusion_behavior_table,
        "spell_definition_id": "srd.spell.confusion",
        "spell_level": 4,
    }
    assert confusion.range == {"normal_ft": 90, "shape": "sphere", "radius_ft": 10}
    assert confusion.target_policy == {"min": 1, "max": 8, "harmful": True}
    assert confusion.automation == [
        {"type": "target", "mode": "area"},
        {"type": "saving_throw", "ability": "wis", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "passive_effect",
            "requires_failed_save": True,
            "passive_modifiers": {
                "confusion": True,
                "area_shape": "sphere",
                "sphere_radius_ft": {
                    "slot_scaled": {
                        "base_value": 10,
                        "base_spell_slot_level": 4,
                        "value_per_slot_above": 5,
                    }
                },
                "blocked_action_economies": ["bonus_action", "reaction"],
                "target_turn_start_behavior_roll": "1d10",
                "behavior_roll_not_automated": True,
                "behavior_table": confusion_behavior_table,
            },
            "duration": {
                "until": "concentration_1_minute",
                "repeat_save": {
                    "ability": "wis",
                    "dc_from": {"spell_save_dc": "actor"},
                    "end_on_success": True,
                    "trigger": "target_turn_end",
                },
            },
            "tick_on": "target_turn_end",
            "concentration": True,
        },
    ]
    dominate_beast = compendium.action("srd.dominate_beast")
    assert dominate_beast.requirements == {
        "spell_level": 4,
        "class_any": ["druid", "ranger", "sorcerer"],
    }
    assert dominate_beast.properties == {
        "spell_classes": ["druid", "ranger", "sorcerer"],
        "components": ["V", "S"],
        "target_must_be_visible": True,
        "target_type": "beast",
        "saving_throw_advantage_if_caster_or_allies_fighting_target": True,
        "telepathic_link_same_plane": True,
        "commands_no_action_on_caster_turn": True,
        "target_obeys_commands_best_ability": True,
        "target_self_protects_without_new_direction": True,
        "can_command_target_reaction_by_spending_caster_reaction": True,
        "command_ai_not_automated": True,
        "reaction_command_not_automated": True,
        "spell_definition_id": "srd.spell.dominate_beast",
        "spell_level": 4,
    }
    assert dominate_beast.range == {"normal_ft": 60}
    assert dominate_beast.target_policy == {
        "min": 1,
        "max": 1,
        "harmful": True,
        "creature_types": ["beast"],
    }
    assert dominate_beast.automation == [
        {"type": "target", "mode": "explicit"},
        {"type": "saving_throw", "ability": "wis", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "condition",
            "condition": "charmed",
            "requires_failed_save": True,
            "passive_modifiers": {
                "dominate_beast": True,
                "telepathic_link_same_plane": True,
                "commands_no_action_on_caster_turn": True,
                "target_obeys_commands_best_ability": True,
                "target_self_protects_without_new_direction": True,
                "can_command_target_reaction_by_spending_caster_reaction": True,
                "command_ai_not_automated": True,
                "reaction_command_not_automated": True,
            },
            "duration": {
                "until": "concentration_1_minute",
                "repeat_save": {
                    "ability": "wis",
                    "dc_from": {"spell_save_dc": "actor"},
                    "end_on_success": True,
                    "trigger": "damage",
                },
                "duration_from_slot": {
                    "base_spell_slot_level": 4,
                    "by_slot_level": {
                        "5": "concentration_10_minutes",
                        "6": "concentration_1_hour",
                        "7": "concentration_8_hours",
                        "8": "concentration_8_hours",
                        "9": "concentration_8_hours",
                    },
                },
            },
            "tick_on": "damage",
            "concentration": True,
        },
    ]
    dominate_person = compendium.action("srd.dominate_person")
    assert dominate_person.requirements == {
        "spell_level": 5,
        "class_any": ["bard", "sorcerer", "wizard"],
    }
    assert dominate_person.properties == {
        "spell_classes": ["bard", "sorcerer", "wizard"],
        "components": ["V", "S"],
        "target_must_be_visible": True,
        "target_type": "humanoid",
        "saving_throw_advantage_if_caster_or_allies_fighting_target": True,
        "telepathic_link_same_plane": True,
        "commands_no_action_on_caster_turn": True,
        "target_obeys_commands_best_ability": True,
        "target_self_protects_without_new_direction": True,
        "can_command_target_reaction_by_spending_caster_reaction": True,
        "command_ai_not_automated": True,
        "reaction_command_not_automated": True,
        "spell_definition_id": "srd.spell.dominate_person",
        "spell_level": 5,
    }
    assert dominate_person.range == {"normal_ft": 60}
    assert dominate_person.target_policy == {
        "min": 1,
        "max": 1,
        "harmful": True,
        "creature_types": ["humanoid"],
    }
    assert dominate_person.automation == [
        {"type": "target", "mode": "explicit"},
        {"type": "saving_throw", "ability": "wis", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "condition",
            "condition": "charmed",
            "requires_failed_save": True,
            "passive_modifiers": {
                "dominate_person": True,
                "telepathic_link_same_plane": True,
                "commands_no_action_on_caster_turn": True,
                "target_obeys_commands_best_ability": True,
                "target_self_protects_without_new_direction": True,
                "can_command_target_reaction_by_spending_caster_reaction": True,
                "command_ai_not_automated": True,
                "reaction_command_not_automated": True,
            },
            "duration": {
                "until": "concentration_1_minute",
                "repeat_save": {
                    "ability": "wis",
                    "dc_from": {"spell_save_dc": "actor"},
                    "end_on_success": True,
                    "trigger": "damage",
                },
                "duration_from_slot": {
                    "base_spell_slot_level": 5,
                    "by_slot_level": {
                        "6": "concentration_10_minutes",
                        "7": "concentration_1_hour",
                        "8": "concentration_8_hours",
                        "9": "concentration_8_hours",
                    },
                },
            },
            "tick_on": "damage",
            "concentration": True,
        },
    ]
    compulsion = compendium.action("srd.compulsion")
    assert compulsion.requirements == {
        "spell_level": 4,
        "class_any": ["bard"],
    }
    assert compulsion.properties == {
        "spell_classes": ["bard"],
        "target_must_be_visible": True,
        "target_type": "creature",
        "creatures_of_your_choice_in_range": True,
        "forced_movement_not_automated": True,
        "spell_definition_id": "srd.spell.compulsion",
        "spell_level": 4,
    }
    assert compulsion.range == {"normal_ft": 30}
    assert compulsion.target_policy == {"min": 1, "max": 12, "harmful": True}
    assert compulsion.automation == [
        {"type": "target", "mode": "explicit"},
        {"type": "saving_throw", "ability": "wis", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "condition",
            "condition": "charmed",
            "requires_failed_save": True,
            "passive_modifiers": {
                "compulsion": True,
                "direction_designated_by_bonus_action": True,
                "direction_relative_to_caster": "horizontal",
                "must_use_as_much_movement_as_possible": True,
                "move_on_next_turn": True,
                "safest_route_required": True,
                "forced_movement_not_automated": True,
                "repeat_save_after_moving": True,
                "repeat_save_trigger_approximated_as": "target_turn_end",
            },
            "duration": {
                "until": "concentration_1_minute",
                "repeat_save": {
                    "ability": "wis",
                    "dc_from": {"spell_save_dc": "actor"},
                    "end_on_success": True,
                    "trigger": "target_turn_end",
                },
            },
            "tick_on": "target_turn_end",
            "concentration": True,
        },
    ]
    hold_monster = compendium.action("srd.hold_monster")
    assert hold_monster.requirements == {
        "spell_level": 5,
        "class_any": ["bard", "sorcerer", "warlock", "wizard"],
    }
    assert hold_monster.properties["spell_classes"] == ["bard", "sorcerer", "warlock", "wizard"]
    assert hold_monster.range == {"normal_ft": 90}
    assert hold_monster.target_policy == {
        "min": 1,
        "max": 1,
        "harmful": True,
        "base_spell_slot_level": 5,
        "max_targets_per_slot_above": 1,
    }
    assert hold_monster.automation == [
        {"type": "target", "mode": "explicit"},
        {"type": "saving_throw", "ability": "wis", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "condition",
            "condition": "paralyzed",
            "requires_failed_save": True,
            "duration": {
                "until": "concentration_1_minute",
                "repeat_save": {
                    "ability": "wis",
                    "dc_from": {"spell_save_dc": "actor"},
                    "end_on_success": True,
                },
            },
            "tick_on": "target_turn_end",
            "concentration": True,
        },
    ]
    irresistible_dance = compendium.action("srd.irresistible_dance")
    assert irresistible_dance.requirements == {
        "spell_level": 6,
        "class_any": ["bard", "wizard"],
    }
    assert irresistible_dance.properties["spell_classes"] == ["bard", "wizard"]
    assert irresistible_dance.range == {"normal_ft": 30}
    assert irresistible_dance.target_policy == {"min": 1, "max": 1, "harmful": True}
    assert irresistible_dance.automation == [
        {"type": "target", "mode": "explicit"},
        {"type": "saving_throw", "ability": "wis", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "passive_effect",
            "requires_successful_save": True,
            "passive_modifiers": {
                "must_spend_all_movement_dancing_in_place": True,
            },
            "duration": {"until": "end_of_next_turn"},
            "tick_on": "target_turn_end",
            "concentration": True,
        },
        {
            "type": "condition",
            "condition": "charmed",
            "requires_failed_save": True,
            "passive_modifiers": {
                "must_spend_all_movement_dancing_in_place": True,
                "saving_throw_disadvantage_abilities": ["dex"],
                "attack_roll_disadvantage": True,
                "incoming_attack_advantage": True,
            },
            "duration": {
                "until": "concentration_1_minute",
                "repeat_save": {
                    "ability": "wis",
                    "dc_from": {"spell_save_dc": "actor"},
                    "end_on_success": True,
                    "trigger": "target_action",
                },
            },
            "tick_on": "target_action",
            "concentration": True,
        },
    ]
    mass_suggestion = compendium.action("srd.mass_suggestion")
    assert mass_suggestion.requirements == {
        "spell_level": 6,
        "class_any": ["bard", "sorcerer", "wizard"],
    }
    assert mass_suggestion.properties["spell_classes"] == ["bard", "sorcerer", "wizard"]
    assert mass_suggestion.properties["material_component"] == {
        "description": "a snake's tongue",
        "consumed": False,
    }
    assert mass_suggestion.properties["suggestion_word_limit"] == 25
    assert mass_suggestion.properties["targets_must_hear_and_understand"] is True
    assert mass_suggestion.properties["suggestion_must_sound_achievable"] is True
    assert (
        mass_suggestion.properties["suggestion_cannot_obviously_damage_targets_or_allies"] is True
    )
    assert mass_suggestion.range == {"normal_ft": 60}
    assert mass_suggestion.target_policy == {"min": 1, "max": 12, "harmful": True}
    assert mass_suggestion.automation == [
        {"type": "target", "mode": "explicit"},
        {"type": "saving_throw", "ability": "wis", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "condition",
            "condition": "charmed",
            "requires_failed_save": True,
            "passive_modifiers": {
                "compelled_suggestion": True,
                "mass_suggestion": True,
                "suggestion_word_limit": 25,
                "targets_must_hear_and_understand": True,
                "suggestion_must_sound_achievable": True,
                "suggestion_cannot_obviously_damage_targets_or_allies": True,
                "pursues_suggestion_to_best_ability": True,
                "ends_when_suggested_activity_completed": True,
            },
            "duration": {
                "until": "duration_24_hours_or_harmed",
                "break_on_damage": True,
                "break_on_damage_by": "applied_by_or_allies",
                "duration_from_slot": {
                    "base_spell_slot_level": 6,
                    "by_slot_level": {
                        "7": "duration_10_days_or_harmed",
                        "8": "duration_30_days_or_harmed",
                        "9": "duration_366_days_or_harmed",
                    },
                },
            },
            "tick_on": "duration_or_damage",
        },
    ]
    greater_restoration = compendium.action("srd.greater_restoration")
    assert greater_restoration.requirements == {
        "spell_level": 5,
        "class_any": ["bard", "cleric", "druid", "paladin", "ranger"],
    }
    assert greater_restoration.properties["spell_classes"] == [
        "bard",
        "cleric",
        "druid",
        "paladin",
        "ranger",
    ]
    assert greater_restoration.properties["greater_restoration_choices"] == [
        "exhaustion",
        "charmed_or_petrified",
        "curse",
        "ability_score_reduction",
        "hp_max_reduction",
        "contact_other_plane_incapacitation",
    ]
    assert greater_restoration.cost.spell_slot_level == 5
    assert greater_restoration.cost.gold == 100
    assert greater_restoration.range == {"touch": True}
    assert greater_restoration.automation == [
        {"type": "target", "mode": "explicit"},
        {
            "type": "greater_restoration",
            "choice_param": "greater_restoration_choice",
            "choices": [
                "exhaustion",
                "charmed_or_petrified",
                "curse",
                "ability_score_reduction",
                "hp_max_reduction",
                "contact_other_plane_incapacitation",
            ],
        },
    ]
    antilife_shell = compendium.action("srd.antilife_shell")
    assert antilife_shell.requirements == {
        "spell_level": 5,
        "class_any": ["druid"],
    }
    assert antilife_shell.properties == {
        "components": ["V", "S"],
        "self_centered_emanation_radius_ft": 10,
        "spell_classes": ["druid"],
        "spell_definition_id": "srd.spell.antilife_shell",
        "spell_level": 5,
    }
    assert antilife_shell.cost.spell_slot_level == 5
    assert antilife_shell.range == {
        "self": True,
        "shape": "emanation",
        "radius_ft": 10,
    }
    assert antilife_shell.target_policy == {
        "min": 0,
        "max": 0,
        "self": True,
        "harmful": False,
    }
    assert antilife_shell.automation == [
        {"type": "target", "mode": "self"},
        {
            "type": "world_effect",
            "effect_type": "antilife_shell",
            "scope": {"target": "self_centered_emanation", "radius_ft": 10},
            "duration": {"until": "concentration_1_hour"},
            "tick_on": "self_turn_end",
            "metadata": {
                "self_centered_emanation": True,
                "blocks_creatures_other_than_constructs_and_undead": True,
                "prevents_passing_or_reaching_through": True,
                "constructs_and_undead_unaffected": True,
                "affected_creatures_can_cast_spells_through_barrier": True,
                "affected_creatures_can_attack_with_ranged_or_reach_weapons_through_barrier": True,
                "ends_if_caster_moves_and_forces_affected_creature_through_barrier": True,
                "barrier_collision_not_automated": True,
            },
        },
    ]
    globe_of_invulnerability = compendium.action("srd.globe_of_invulnerability")
    assert globe_of_invulnerability.requirements == {
        "spell_level": 6,
        "class_any": ["sorcerer", "wizard"],
    }
    assert globe_of_invulnerability.properties["spell_classes"] == ["sorcerer", "wizard"]
    assert globe_of_invulnerability.properties["material_component"] == {
        "description": "a glass bead",
        "consumed": False,
    }
    assert globe_of_invulnerability.range == {
        "self": True,
        "shape": "emanation",
        "radius_ft": 10,
    }
    assert globe_of_invulnerability.target_policy == {
        "min": 0,
        "max": 0,
        "self": True,
        "harmful": False,
    }
    assert globe_of_invulnerability.automation == [
        {
            "type": "world_effect",
            "effect_type": "globe_of_invulnerability",
            "scope": {"target": "self_centered_emanation", "radius_ft": 10},
            "duration": {"until": "concentration_1_minute"},
            "tick_on": "self_turn_end",
            "metadata": {
                "immobile": True,
                "shimmering_barrier": True,
                "spells_must_be_cast_from_outside_barrier": True,
                "protected_targets": "creatures_and_objects_within_barrier",
                "outside_spell_can_target_inside_but_has_no_effect": True,
                "area_inside_excluded_from_outside_spell_areas": True,
            },
            "metadata_from_slot": {
                "blocks_spell_level_lte": {
                    "base_spell_slot_level": 6,
                    "base_value": 5,
                    "value_per_slot_above": 1,
                }
            },
        }
    ]
    forbiddance = compendium.action("srd.forbiddance")
    assert forbiddance.requirements == {
        "spell_level": 6,
        "class_any": ["cleric"],
    }
    assert compendium.spell("srd.spell.forbiddance").ritual is True
    assert forbiddance.properties["ritual"] is True
    assert forbiddance.properties["spell_classes"] == ["cleric"]
    assert forbiddance.properties["casting_time"] == {"minutes": 10}
    assert forbiddance.properties["material_component"] == {
        "description": "ruby dust worth 1,000+ GP",
        "consumed": False,
        "consumed_on_permanent_cast": True,
    }
    assert forbiddance.properties["allowed_damage_types"] == ["necrotic", "radiant"]
    assert forbiddance.properties["damage_type_param"] == "forbiddance_damage_type"
    assert forbiddance.properties["allowed_creature_types"] == [
        "aberration",
        "celestial",
        "elemental",
        "fey",
        "fiend",
        "undead",
    ]
    assert forbiddance.properties["creature_types_param"] == "forbiddance_creature_types"
    assert forbiddance.properties["password_param"] == "forbiddance_password"
    assert forbiddance.range == {"touch": True}
    assert forbiddance.target_policy == {"min": 0, "max": 0, "harmful": False}
    assert forbiddance.cost.gold == 0
    assert forbiddance.automation == [
        {
            "type": "world_effect",
            "effect_type": "forbiddance_ward",
            "scope": {
                "target": "touched_area",
                "max_floor_area_sq_ft": 40000,
                "height_ft": 30,
            },
            "duration": {"until": "duration_1_day"},
            "tick_on": "self_turn_end",
            "metadata": {
                "blocks_teleport_into_area": True,
                "blocks_portals_into_area": True,
                "proofs_against_planar_travel": True,
                "blocked_planar_routes": [
                    "astral_plane",
                    "ethereal_plane",
                    "feywild",
                    "shadowfell",
                    "plane_shift",
                ],
                "chosen_creature_types": {"param_list": "forbiddance_creature_types"},
                "damage_type": {"param": "forbiddance_damage_type"},
                "damage": "5d10",
                "repeat_damage_triggers": [
                    "chosen_creature_enters_area_first_time_on_turn",
                    "chosen_creature_ends_turn_in_area",
                ],
                "password_prevents_spell_damage_when_spoken_on_entry": True,
                "password_param": "forbiddance_password",
                "area_cannot_overlap_another_forbiddance": True,
                "permanent_if_cast_daily_same_location_days": 30,
                "material_components_consumed_on_permanent_cast": True,
            },
        }
    ]
    cloudkill = compendium.action("srd.cloudkill")
    assert cloudkill.requirements == {
        "spell_level": 5,
        "class_any": ["sorcerer", "wizard"],
    }
    assert cloudkill.properties["spell_classes"] == ["sorcerer", "wizard"]
    assert cloudkill.range == {"normal_ft": 120, "shape": "sphere", "radius_ft": 20}
    assert cloudkill.target_policy == {"min": 1, "max": 12, "harmful": True}
    assert cloudkill.automation == [
        {"type": "target", "mode": "area"},
        {"type": "saving_throw", "ability": "con", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "damage",
            "dice": "5d8",
            "damage_type": "poison",
            "save_half": True,
            "base_spell_slot_level": 5,
            "extra_dice_per_slot_above": "1d8",
        },
        {
            "type": "world_effect",
            "effect_type": "cloudkill_fog",
            "scope": {"shape": "sphere", "radius_ft": 20, "range_ft": 120},
            "duration": {"until": "concentration_10_minutes"},
            "metadata": {
                "heavily_obscured": True,
                "dispersed_by_strong_wind": True,
                "moves_away_from_caster_ft_at_start_of_turn": 10,
                "repeat_save_triggers": [
                    "sphere_moves_into_space",
                    "creature_enters_area",
                    "creature_ends_turn_in_area",
                ],
                "repeat_save_once_per_turn": True,
                "repeat_save": {
                    "ability": "con",
                    "dc_from": {"spell_save_dc": "actor"},
                    "damage": "5d8 poison",
                    "higher_level_damage_increase": "1d8 per slot above 5",
                },
            },
        },
    ]
    insect_plague = compendium.action("srd.insect_plague")
    assert insect_plague.requirements == {
        "spell_level": 5,
        "class_any": ["cleric", "druid", "sorcerer"],
    }
    assert insect_plague.properties["spell_classes"] == ["cleric", "druid", "sorcerer"]
    assert insect_plague.properties["material_component"] == {
        "description": "a locust",
        "consumed": False,
    }
    assert insect_plague.range == {"normal_ft": 300, "shape": "sphere", "radius_ft": 20}
    assert insect_plague.target_policy == {"min": 1, "max": 12, "harmful": True}
    assert insect_plague.automation == [
        {"type": "target", "mode": "area"},
        {"type": "saving_throw", "ability": "con", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "damage",
            "dice": "4d10",
            "damage_type": "piercing",
            "save_half": True,
            "base_spell_slot_level": 5,
            "extra_dice_per_slot_above": "1d10",
        },
        {
            "type": "world_effect",
            "effect_type": "insect_plague_swarm",
            "scope": {"shape": "sphere", "radius_ft": 20, "range_ft": 300},
            "duration": {"until": "concentration_10_minutes"},
            "tick_on": "self_turn_end",
            "metadata": {
                "lightly_obscured": True,
                "difficult_terrain": True,
                "repeat_save_triggers": [
                    "creature_enters_area",
                    "creature_ends_turn_in_area",
                ],
                "repeat_save_once_per_turn": True,
                "repeat_save": {
                    "ability": "con",
                    "dc_from": {"spell_save_dc": "actor"},
                    "damage": "4d10 piercing",
                    "higher_level_damage_increase": "1d10 per slot above 5",
                },
            },
        },
    ]
    teleportation_circle = compendium.action("srd.teleportation_circle")
    assert teleportation_circle.requirements == {
        "spell_level": 5,
        "class_any": ["bard", "sorcerer", "warlock", "wizard"],
    }
    assert teleportation_circle.properties["spell_classes"] == [
        "bard",
        "sorcerer",
        "warlock",
        "wizard",
    ]
    assert teleportation_circle.properties["casting_time"] == {"minutes": 1}
    assert teleportation_circle.properties["material_component"] == {
        "description": "rare inks worth 50+ GP",
        "consumed": True,
    }
    assert teleportation_circle.cost.spell_slot_level == 5
    assert teleportation_circle.cost.gold == 50
    assert teleportation_circle.range == {"normal_ft": 10, "shape": "circle", "radius_ft": 5}
    assert teleportation_circle.target_policy == {"min": 0, "max": 0, "harmful": False}
    assert teleportation_circle.automation == [
        {
            "type": "world_effect",
            "effect_type": "teleportation_circle_portal",
            "scope": {"target": "point", "radius_ft": 5, "range_ft": 10},
            "duration": {"until": "end_of_next_turn", "remaining_ticks": 2},
            "tick_on": "self_turn_end",
            "metadata": {
                "requires_known_sigil_sequence": True,
                "destination": "permanent_teleportation_circle",
                "same_plane_required": True,
                "portal_open_until_end_of_next_turn": True,
                "entering_creature_appears_within_ft_of_destination_circle": 5,
                "nearest_unoccupied_space_if_destination_occupied": True,
                "initial_known_material_plane_destination_count": 2,
                "learn_new_sigil_sequence_study_minutes": 1,
                "permanent_circle_daily_castings_required": 365,
            },
        }
    ]
    dimension_door = compendium.action("srd.dimension_door")
    assert dimension_door.requirements == {
        "spell_level": 4,
        "class_any": ["bard", "sorcerer", "warlock", "wizard"],
    }
    assert dimension_door.properties["spell_classes"] == [
        "bard",
        "sorcerer",
        "warlock",
        "wizard",
    ]
    assert dimension_door.properties["requires_willing_target"] is True
    assert dimension_door.properties["optional_companion_must_be_within_ft"] == 5
    assert dimension_door.cost.spell_slot_level == 4
    assert dimension_door.range == {"normal_ft": 500}
    assert dimension_door.target_policy == {"min": 0, "max": 1, "harmful": False}
    assert dimension_door.automation == [
        {
            "type": "world_effect",
            "effect_type": "dimension_door_teleport",
            "scope": {"target": "explicit", "range_ft": 500},
            "duration": {"until": "instant"},
            "metadata": {
                "teleports_actor": True,
                "destination_within_ft": 500,
                "destination_can_be_seen_visualized_or_described": True,
                "arrives_at_exact_spot_desired": True,
                "optional_willing_companion": True,
                "companion_must_be_within_ft": 5,
                "companion_arrives_within_ft_of_destination": 5,
                "occupied_or_filled_destination_causes_force_damage_and_fails": True,
                "failed_teleport_force_damage": "4d6",
            },
        }
    ]
    faithful_hound = compendium.action("srd.faithful_hound")
    assert faithful_hound.requirements == {
        "spell_level": 4,
        "class_any": ["wizard"],
    }
    assert faithful_hound.properties["spell_classes"] == ["wizard"]
    assert faithful_hound.properties["material_component"] == {
        "description": "a silver whistle",
        "consumed": False,
    }
    assert faithful_hound.cost.spell_slot_level == 4
    assert faithful_hound.range == {"normal_ft": 30}
    assert faithful_hound.target_policy == {"min": 0, "max": 0, "harmful": False}
    assert faithful_hound.automation == [
        {
            "type": "world_effect",
            "effect_type": "faithful_hound_watchdog",
            "scope": {"target": "unoccupied_space_you_can_see", "range_ft": 30},
            "duration": {"until": "duration_8_hours"},
            "tick_on": "self_turn_end",
            "metadata": {
                "phantom_watchdog": True,
                "ends_if_caster_more_than_ft_from_hound": 300,
                "visible_only_to_caster": True,
                "intangible": True,
                "invulnerable": True,
                "password_specified_on_cast": True,
                "barks_when_small_or_larger_creature_without_password_within_ft": 30,
                "truesight_ft": 30,
                "start_of_caster_turn_bite_one_enemy_within_ft": 5,
                "bite": {
                    "save": {
                        "ability": "dex",
                        "dc_from": {"spell_save_dc": "actor"},
                        "success_avoids_damage": True,
                    },
                    "damage": "4d8 force",
                },
                "can_move_with_magic_action": True,
                "move_distance_ft": 30,
            },
        }
    ]
    guardian_of_faith = compendium.action("srd.guardian_of_faith")
    assert guardian_of_faith.requirements == {
        "spell_level": 4,
        "class_any": ["cleric"],
    }
    assert guardian_of_faith.properties["spell_classes"] == ["cleric"]
    assert guardian_of_faith.properties["target_must_be_visible"] is True
    assert guardian_of_faith.properties["space_must_be_unoccupied"] is True
    assert guardian_of_faith.cost.spell_slot_level == 4
    assert guardian_of_faith.range == {"normal_ft": 30}
    assert guardian_of_faith.target_policy == {"min": 0, "max": 0, "harmful": False}
    assert guardian_of_faith.automation == [
        {
            "type": "world_effect",
            "effect_type": "guardian_of_faith",
            "scope": {
                "target": "unoccupied_space_you_can_see",
                "range_ft": 30,
                "size": "large",
            },
            "duration": {"until": "duration_8_hours"},
            "tick_on": "self_turn_end",
            "metadata": {
                "spectral_guardian": True,
                "size": "large",
                "hovers": True,
                "occupies_space": True,
                "invulnerable": True,
                "form_appropriate_for_deity_or_pantheon": True,
                "trigger_targets": "enemy",
                "trigger_range_ft": 10,
                "repeat_save_triggers": [
                    "enemy_moves_within_10_ft_first_time_on_turn",
                    "enemy_starts_turn_within_10_ft",
                ],
                "repeat_save_once_per_turn": True,
                "repeat_save": {
                    "ability": "dex",
                    "dc_from": {"spell_save_dc": "actor"},
                    "damage": "20 radiant",
                    "save_half": True,
                },
                "vanishes_after_total_damage_dealt": 60,
            },
        }
    ]
    black_tentacles = compendium.action("srd.black_tentacles")
    assert black_tentacles.requirements == {
        "spell_level": 4,
        "class_any": ["wizard"],
    }
    assert black_tentacles.properties["spell_classes"] == ["wizard"]
    assert black_tentacles.properties["material_component"] == {
        "description": "a tentacle",
        "consumed": False,
    }
    assert black_tentacles.properties["ground_you_can_see"] is True
    assert black_tentacles.cost.spell_slot_level == 4
    assert black_tentacles.range == {"normal_ft": 90, "shape": "square", "size_ft": 20}
    assert black_tentacles.target_policy == {"min": 0, "max": 16, "harmful": True}
    assert black_tentacles.automation == [
        {"type": "target", "mode": "area"},
        {"type": "saving_throw", "ability": "str", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "damage",
            "dice": "3d6",
            "damage_type": "bludgeoning",
            "requires_failed_save": True,
        },
        {
            "type": "condition",
            "condition": "restrained",
            "requires_failed_save": True,
            "passive_modifiers": {
                "black_tentacles": True,
                "area_escape_check": {
                    "action": "action",
                    "ability": "str",
                    "skill": "athletics",
                    "dc_from": {"spell_save_dc": "actor"},
                    "ends_condition": "restrained",
                },
            },
            "duration": {"until": "concentration_1_minute"},
            "tick_on": "self_turn_end",
            "concentration": True,
        },
        {
            "type": "world_effect",
            "effect_type": "black_tentacles_area",
            "scope": {
                "target": "ground_area",
                "range_ft": 90,
                "shape": "square",
                "size_ft": 20,
            },
            "duration": {"until": "concentration_1_minute"},
            "tick_on": "self_turn_end",
            "metadata": {
                "ground_you_can_see": True,
                "difficult_terrain": True,
                "repeat_save_triggers": [
                    "creature_enters_area",
                    "creature_ends_turn_in_area",
                ],
                "repeat_save_once_per_turn": True,
                "repeat_save": {
                    "ability": "str",
                    "dc_from": {"spell_save_dc": "actor"},
                    "damage": "3d6 bludgeoning",
                    "failed_condition": "restrained",
                },
                "restrained_escape_check": {
                    "action": "action",
                    "ability": "str",
                    "skill": "athletics",
                    "dc_from": {"spell_save_dc": "actor"},
                    "ends_condition": "restrained",
                },
            },
        },
    ]
    conjure_minor_spell = compendium.spell("srd.spell.conjure_minor_elementals")
    assert conjure_minor_spell.level == 4
    assert conjure_minor_spell.school == "conjuration"
    assert conjure_minor_spell.classes == ["druid", "wizard"]
    conjure_minor = compendium.action("srd.conjure_minor_elementals")
    assert conjure_minor.requirements == {
        "spell_level": 4,
        "class_any": ["druid", "wizard"],
    }
    assert conjure_minor.properties == {
        "spell_classes": ["druid", "wizard"],
        "components": ["V", "S"],
        "self_centered_emanation_radius_ft": 15,
        "extra_damage_base": "2d8",
        "extra_damage_types": ["acid", "cold", "fire", "lightning"],
        "extra_damage_type_param": "conjure_minor_elementals_damage_type",
        "extra_damage_requires_attack_hit": True,
        "extra_damage_requires_target_in_emanation": True,
        "extra_damage_target_range_ft": 15,
        "difficult_terrain_for_enemies": True,
        "elemental_spirits_no_stat_block": True,
        "spell_definition_id": "srd.spell.conjure_minor_elementals",
        "spell_level": 4,
    }
    assert conjure_minor.cost.spell_slot_level == 4
    assert conjure_minor.range == {
        "self": True,
        "shape": "emanation",
        "radius_ft": 15,
    }
    assert conjure_minor.target_policy == {
        "min": 0,
        "max": 0,
        "self": True,
        "harmful": False,
    }
    assert conjure_minor.automation == [
        {
            "type": "world_effect",
            "effect_type": "conjure_minor_elementals_emanation",
            "scope": {
                "target": "self_centered_emanation",
                "radius_ft": 15,
            },
            "duration": {"until": "concentration_10_minutes"},
            "tick_on": "self_turn_end",
            "metadata_from_slot": {
                "extra_damage_dice_count": {
                    "base_spell_slot_level": 4,
                    "base_value": 2,
                    "value_per_slot_above": 1,
                }
            },
            "metadata": {
                "elemental_spirits_from_elemental_planes": True,
                "self_centered_emanation": True,
                "emanation_radius_ft": 15,
                "extra_damage_die": "d8",
                "base_extra_damage": "2d8",
                "higher_level_damage_increase": "1d8 per slot above 4",
                "extra_damage_triggers": [
                    "caster_attack_hits_creature_in_emanation",
                ],
                "extra_damage_types": ["acid", "cold", "fire", "lightning"],
                "damage_type_chosen_when_attack_is_made": True,
                "damage_type_param": "conjure_minor_elementals_damage_type",
                "ground_in_emanation_is_difficult_terrain_for_enemies": True,
                "spirit_stat_blocks_not_created": True,
                "area_damage_not_automated": True,
            },
        }
    ]
    conjure_woodland = compendium.action("srd.conjure_woodland_beings")
    assert conjure_woodland.requirements == {
        "spell_level": 4,
        "class_any": ["druid", "ranger"],
    }
    assert conjure_woodland.properties == {
        "spell_classes": ["druid", "ranger"],
        "components": ["V", "S"],
        "self_centered_emanation_radius_ft": 10,
        "bonus_action_disengage_action_id": "srd.conjure_woodland_beings_disengage",
        "emanation_trigger_not_automated": True,
        "nature_spirits_no_stat_block": True,
        "spell_definition_id": "srd.spell.conjure_woodland_beings",
        "spell_level": 4,
    }
    assert conjure_woodland.cost.spell_slot_level == 4
    assert conjure_woodland.range == {
        "self": True,
        "shape": "emanation",
        "radius_ft": 10,
    }
    assert conjure_woodland.target_policy == {"min": 0, "max": 12, "harmful": True}
    assert conjure_woodland.automation == [
        {"type": "target", "mode": "area"},
        {"type": "saving_throw", "ability": "wis", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "damage",
            "dice": "5d8",
            "damage_type": "force",
            "save_half": True,
            "base_spell_slot_level": 4,
            "extra_dice_per_slot_above": "1d8",
        },
        {
            "type": "world_effect",
            "effect_type": "conjure_woodland_beings_emanation",
            "scope": {
                "target": "self_centered_emanation",
                "radius_ft": 10,
            },
            "duration": {"until": "concentration_10_minutes"},
            "tick_on": "self_turn_end",
            "metadata": {
                "nature_spirits": True,
                "self_centered_emanation": True,
                "wisdom_save": True,
                "damage": "5d8 force",
                "save_half": True,
                "higher_level_damage_increase": "1d8 per slot above 4",
                "repeat_save_triggers": [
                    "emanation_enters_visible_creature_space",
                    "visible_creature_enters_emanation",
                    "visible_creature_ends_turn_in_emanation",
                ],
                "repeat_save_once_per_turn": True,
                "repeat_save": {
                    "ability": "wis",
                    "dc_from": {"spell_save_dc": "actor"},
                    "damage": "5d8 force",
                    "save_half": True,
                    "higher_level_damage_increase": "1d8 per slot above 4",
                },
                "bonus_action_disengage_action_id": "srd.conjure_woodland_beings_disengage",
                "emanation_trigger_not_automated": True,
                "nature_spirits_no_stat_block": True,
            },
        },
    ]
    conjure_disengage = compendium.action("srd.conjure_woodland_beings_disengage")
    assert conjure_disengage.action_type == "base_action"
    assert conjure_disengage.action_economy == "bonus_action"
    assert conjure_disengage.properties == {
        "requires_active_effect_source_action_id": "srd.conjure_woodland_beings",
        "spell_definition_id": "srd.spell.conjure_woodland_beings",
        "spell_level": 4,
    }
    assert conjure_disengage.automation == [
        {"type": "target", "mode": "self"},
        {
            "type": "condition",
            "condition": "disengaged",
            "duration": {"until": "end_of_current_turn"},
            "tick_on": "self_turn_end",
        },
        {
            "type": "text_result",
            "text": (
                "The caster takes the Disengage action as a Bonus Action while "
                "Conjure Woodland Beings lasts."
            ),
        },
    ]
    secret_chest = compendium.action("srd.secret_chest")
    assert secret_chest.requirements == {
        "spell_level": 4,
        "class_any": ["wizard"],
    }
    assert secret_chest.properties["spell_classes"] == ["wizard"]
    assert secret_chest.properties["material_component"] == {
        "description": (
            "a chest, 3 feet by 2 feet by 2 feet, constructed from rare materials "
            "worth 5,000+ GP, and a Tiny replica of the chest made from the same "
            "materials worth 50+ GP"
        ),
        "consumed": False,
    }
    assert secret_chest.cost.spell_slot_level == 4
    assert secret_chest.cost.gold == 0
    assert secret_chest.range == {"touch": True}
    assert secret_chest.target_policy == {"min": 0, "max": 0, "harmful": False}
    assert secret_chest.automation == [
        {
            "type": "world_effect",
            "effect_type": "secret_chest_ethereal_storage",
            "scope": {"target": "touched_chest_and_replica"},
            "duration": {"until": "dispelled"},
            "metadata": {
                "hides_chest_on_ethereal_plane": True,
                "requires_touching_chest_and_tiny_replica": True,
                "chest_dimensions_ft": {"length": 3, "width": 2, "height": 2},
                "max_contents_volume_cubic_ft": 12,
                "contents_must_be_nonliving_material": True,
                "recall_requires_magic_action_touch_replica": True,
                "recalled_chest_appears_on_ground_unoccupied_space_within_ft": 5,
                "send_back_requires_magic_action_touch_chest_and_replica": True,
                "cumulative_end_chance_starts_after_days": 60,
                "daily_cumulative_end_chance_percent": 5,
                "ends_if_cast_again": True,
                "ends_if_tiny_replica_destroyed": True,
                "if_ends_while_chest_on_ethereal_plane_chest_remains_there_to_find": True,
            },
        }
    ]
    transport_via_plants = compendium.action("srd.transport_via_plants")
    assert transport_via_plants.requirements == {
        "spell_level": 6,
        "class_any": ["druid"],
    }
    assert transport_via_plants.properties["spell_classes"] == ["druid"]
    assert transport_via_plants.range == {"normal_ft": 10}
    assert transport_via_plants.target_policy == {"min": 0, "max": 0, "harmful": False}
    assert transport_via_plants.automation == [
        {
            "type": "world_effect",
            "effect_type": "transport_via_plants_link",
            "scope": {"target": "large_or_larger_inanimate_plant", "range_ft": 10},
            "duration": {"until": "duration_1_minute"},
            "tick_on": "self_turn_end",
            "metadata": {
                "destination": "another_plant",
                "same_plane_required": True,
                "destination_must_have_been_seen_or_touched_before": True,
                "any_creature_can_use": True,
                "movement_cost_ft": 5,
                "enter_target_plant_and_exit_destination_plant": True,
            },
        }
    ]
    word_of_recall = compendium.action("srd.word_of_recall")
    assert word_of_recall.requirements == {
        "spell_level": 6,
        "class_any": ["cleric"],
    }
    assert word_of_recall.properties["spell_classes"] == ["cleric"]
    assert word_of_recall.properties["requires_willing_target"] is True
    assert word_of_recall.range == {"normal_ft": 5}
    assert word_of_recall.target_policy == {
        "min": 1,
        "max": 6,
        "self": True,
        "harmful": False,
    }
    assert word_of_recall.automation == [
        {"type": "target", "mode": "explicit"},
        {
            "type": "world_effect",
            "effect_type": "word_of_recall_teleport",
            "scope": {"target": "explicit", "range_ft": 5},
            "duration": {"until": "instant"},
            "metadata": {
                "teleports_actor": True,
                "max_willing_companions": 5,
                "companions_must_be_within_ft": 5,
                "requires_previously_designated_sanctuary": True,
                "no_effect_without_prepared_sanctuary": True,
                "appears_nearest_unoccupied_space_to_designated_spot": True,
                "designates_sanctuary_by_casting_this_spell_there": True,
                "destination": "previously_designated_sanctuary",
            },
        },
    ]
    etherealness = compendium.action("srd.etherealness")
    assert etherealness.requirements == {
        "spell_level": 7,
        "class_any": ["bard", "cleric", "sorcerer", "warlock", "wizard"],
    }
    assert etherealness.properties["spell_classes"] == [
        "bard",
        "cleric",
        "sorcerer",
        "warlock",
        "wizard",
    ]
    assert etherealness.properties["requires_willing_target"] is True
    assert etherealness.properties["requires_self_target"] is True
    assert etherealness.range == {"self": True}
    assert etherealness.target_policy == {
        "min": 1,
        "max": 1,
        "self": True,
        "harmful": False,
        "base_spell_slot_level": 7,
        "max_targets_per_slot_above": 3,
    }
    assert etherealness.automation == [
        {"type": "target", "mode": "explicit"},
        {
            "type": "world_effect",
            "effect_type": "etherealness",
            "scope": {"target": "explicit", "range_ft": 10},
            "duration": {"until": "duration_8_hours"},
            "tick_on": "self_turn_end",
            "metadata": {
                "border_ethereal": True,
                "current_plane_must_border_ethereal": True,
                "ends_instantly_if_cast_on_ethereal_or_nonbordering_plane": True,
                "can_move_in_any_direction": True,
                "vertical_movement_extra_cost_per_foot": 1,
                "perceives_origin_plane_gray": True,
                "origin_plane_vision_range_ft": 60,
                "can_affect_only_ethereal_plane": True,
                "can_be_affected_only_by_ethereal_plane": True,
                "non_ethereal_creatures_cannot_perceive_or_interact_without_special_ability": True,
                "returns_to_origin_plane_when_spell_ends": True,
                "returns_to_corresponding_space": True,
                "shunted_to_nearest_unoccupied_space_if_occupied": True,
                "shunted_force_damage_per_ft": 2,
                "willing_creatures_must_be_within_ft": 10,
                "higher_level_targets_per_slot_above_7": 3,
                "includes_self": True,
            },
        },
    ]
    arcane_eye = compendium.action("srd.arcane_eye")
    assert arcane_eye.requirements == {
        "spell_level": 4,
        "class_any": ["wizard"],
    }
    assert arcane_eye.properties["spell_classes"] == ["wizard"]
    assert arcane_eye.properties["material_component"] == {
        "description": "a bit of bat fur",
        "consumed": False,
    }
    assert arcane_eye.cost.spell_slot_level == 4
    assert arcane_eye.range == {"normal_ft": 30}
    assert arcane_eye.target_policy == {"min": 0, "max": 0, "harmful": False}
    assert arcane_eye.automation == [
        {
            "type": "world_effect",
            "effect_type": "arcane_eye_sensor",
            "scope": {"target": "point_within_range", "range_ft": 30},
            "duration": {"until": "concentration_1_hour"},
            "tick_on": "self_turn_end",
            "metadata": {
                "invisible": True,
                "invulnerable": True,
                "hovers": True,
                "mentally_receives_visual_information": True,
                "sees_in_every_direction": True,
                "darkvision_ft": 30,
                "movable_as_bonus_action": True,
                "move_distance_ft": 30,
                "movement_direction": "any_direction",
                "solid_barrier_blocks_movement": True,
                "can_pass_through_opening_min_diameter_in": 1,
            },
        }
    ]
    locate_creature = compendium.action("srd.locate_creature")
    assert locate_creature.requirements == {
        "spell_level": 4,
        "class_any": ["bard", "cleric", "druid", "paladin", "ranger", "wizard"],
    }
    assert locate_creature.properties["spell_classes"] == [
        "bard",
        "cleric",
        "druid",
        "paladin",
        "ranger",
        "wizard",
    ]
    assert locate_creature.properties["material_component"] == {
        "description": "fur from a bloodhound",
        "consumed": False,
    }
    assert locate_creature.cost.spell_slot_level == 4
    assert locate_creature.range == {"self": True}
    assert locate_creature.target_policy == {"min": 0, "max": 0, "harmful": False}
    assert locate_creature.automation == [
        {
            "type": "world_effect",
            "effect_type": "locate_creature",
            "scope": {"target": "described_or_named_creature", "range_ft": 1000},
            "duration": {"until": "concentration_1_hour"},
            "tick_on": "self_turn_end",
            "metadata": {
                "describe_or_name_creature_familiar_to_you": True,
                "senses_direction_to_creature_within_ft": 1000,
                "knows_direction_of_movement_if_moving": True,
                "can_locate_specific_known_creature": True,
                "can_locate_nearest_creature_of_kind_seen_within_ft": 30,
                "fails_if_creature_in_different_form": True,
                "different_form_examples": ["flesh_to_stone", "polymorph"],
                "lead_blocks_direct_path": True,
            },
        }
    ]
    divination_spell = compendium.spell("srd.spell.divination")
    assert divination_spell.ritual is True
    divination = compendium.action("srd.divination")
    assert divination.requirements == {
        "spell_level": 4,
        "class_any": ["cleric", "druid", "wizard"],
    }
    assert divination.properties["spell_classes"] == ["cleric", "druid", "wizard"]
    assert divination.properties["ritual"] is True
    assert divination.properties["spell_definition_id"] == "srd.spell.divination"
    assert divination.properties["material_component"] == {
        "description": "incense worth 25+ GP",
        "consumed": True,
    }
    assert divination.properties["question_scope"] == (
        "specific_goal_event_or_activity_within_7_days"
    )
    assert divination.properties["repeat_casting_failure_chance_increment_percent"] == 25
    assert divination.cost.spell_slot_level == 4
    assert divination.cost.gold == 25
    assert divination.range == {"self": True}
    assert divination.target_policy == {"min": 0, "max": 0, "harmful": False}
    assert divination.automation == [
        {
            "type": "world_effect",
            "effect_type": "divination_answer",
            "scope": {"target": "self"},
            "duration": {"until": "instant"},
            "metadata": {
                "contacts_god_or_gods_servants": True,
                "question_about_specific_goal_event_or_activity_within_days": 7,
                "gm_offers_truthful_reply": True,
                "reply_may_be_short_phrase_or_cryptic_rhyme": True,
                "does_not_account_for_changed_circumstances": True,
                "changed_circumstance_example": "casting_other_spells",
                "repeat_casting_before_long_rest_cumulative_no_answer_chance_percent": 25,
            },
        }
    ]
    contact_spell = compendium.spell("srd.spell.contact_other_plane")
    assert contact_spell.ritual is True
    assert contact_spell.level == 5
    assert contact_spell.school == "divination"
    assert contact_spell.classes == ["warlock", "wizard"]
    contact = compendium.action("srd.contact_other_plane")
    assert contact.requirements == {
        "spell_level": 5,
        "class_any": ["warlock", "wizard"],
    }
    assert contact.properties["spell_classes"] == ["warlock", "wizard"]
    assert contact.properties["ritual"] is True
    assert contact.properties["spell_definition_id"] == "srd.spell.contact_other_plane"
    assert contact.properties["casting_time"] == {"minutes": 1}
    assert contact.properties["components"] == ["V"]
    assert contact.properties["max_questions"] == 5
    assert contact.properties["intelligence_save_dc"] == 15
    assert contact.cost.spell_slot_level == 5
    assert contact.cost.gold == 0
    assert contact.range == {"self": True}
    assert contact.target_policy == {"min": 0, "max": 0, "self": True, "harmful": False}
    assert contact.automation == [
        {"type": "target", "mode": "self"},
        {
            "type": "saving_throw",
            "ability": "int",
            "dc_ref": "srd.contact_other_plane.int_save",
            "dc_table": {"srd.contact_other_plane.int_save": 15},
        },
        {
            "type": "branch",
            "condition": "last_save_success",
            "if_true": [
                {
                    "type": "world_effect",
                    "effect_type": "contact_other_plane_answer_window",
                    "scope": {"target": "self"},
                    "duration": {"until": "duration_1_minute"},
                    "tick_on": "self_turn_end",
                    "metadata": {
                        "mentally_contacts_otherworldly_intelligence": True,
                        "possible_entities": [
                            "demigod",
                            "long_dead_sage_spirit",
                            "knowledgeable_entity_from_another_plane",
                        ],
                        "max_questions": 5,
                        "questions_must_be_asked_before_spell_ends": True,
                        "gm_answers_each_question_with_one_word": True,
                        "example_answers": [
                            "yes",
                            "no",
                            "maybe",
                            "never",
                            "irrelevant",
                            "unclear",
                        ],
                        "unclear_if_entity_does_not_know_answer": True,
                        "gm_may_offer_short_phrase_if_one_word_misleading": True,
                        "answer_generation_not_automated": True,
                        "entity_selection_not_automated": True,
                    },
                }
            ],
            "if_false": [
                {"type": "damage", "dice": "6d6", "damage_type": "psychic"},
                {
                    "type": "condition",
                    "condition": "incapacitated",
                    "duration": {"until": "long_rest"},
                    "passive_modifiers": {
                        "contact_other_plane_incapacitation": True,
                        "greater_restoration_ends_effect": True,
                    },
                },
            ],
        },
    ]
    legend_lore_spell = compendium.spell("srd.spell.legend_lore")
    assert legend_lore_spell.level == 5
    assert legend_lore_spell.school == "divination"
    assert legend_lore_spell.classes == ["bard", "cleric", "wizard"]
    legend_lore = compendium.action("srd.legend_lore")
    assert legend_lore.requirements == {
        "spell_level": 5,
        "class_any": ["bard", "cleric", "wizard"],
    }
    assert legend_lore.properties == {
        "spell_classes": ["bard", "cleric", "wizard"],
        "spell_definition_id": "srd.spell.legend_lore",
        "spell_level": 5,
        "casting_time": {"minutes": 10},
        "components": ["V", "S", "M"],
        "material_component": {
            "description": (
                "incense worth 250+ GP, consumed, and four ivory strips "
                "worth 50+ GP each"
            ),
            "consumed": True,
            "consumed_gold": 250,
            "non_consumed_components": [
                "four ivory strips worth 50+ GP each",
            ],
        },
        "lore_target": "famous_person_place_or_object",
    }
    assert legend_lore.cost.spell_slot_level == 5
    assert legend_lore.cost.gold == 250
    assert legend_lore.range == {"self": True}
    assert legend_lore.target_policy == {
        "min": 0,
        "max": 0,
        "self": True,
        "harmful": False,
    }
    assert legend_lore.automation == [
        {
            "type": "world_effect",
            "effect_type": "legend_lore_summary",
            "scope": {"target": "self"},
            "duration": {"until": "instant"},
            "metadata": {
                "name_or_describe_famous_person_place_or_object": True,
                "gm_provides_brief_summary_of_significant_lore": True,
                "lore_may_include_important_details_amusing_revelations_or_secret_lore": True,
                "more_existing_knowledge_makes_result_more_precise_and_detailed": True,
                "information_is_accurate": True,
                "gm_may_couch_information_in_figurative_language_or_poetry": True,
                "fails_if_chosen_thing_is_not_actually_famous": True,
                "sad_trombone_on_non_famous_failure": True,
                "lore_generation_not_automated": True,
                "fame_determination_not_automated": True,
                "non_consumed_material_components": [
                    "four ivory strips worth 50+ GP each",
                ],
                "consumed_material_component": "incense worth 250+ GP",
            },
        }
    ]
    commune_spell = compendium.spell("srd.spell.commune")
    assert commune_spell.ritual is True
    assert commune_spell.level == 5
    assert commune_spell.school == "divination"
    assert commune_spell.classes == ["cleric"]
    commune = compendium.action("srd.commune")
    assert commune.requirements == {
        "spell_level": 5,
        "class_any": ["cleric"],
    }
    assert commune.properties["spell_classes"] == ["cleric"]
    assert commune.properties["ritual"] is True
    assert commune.properties["spell_definition_id"] == "srd.spell.commune"
    assert commune.properties["casting_time"] == {"minutes": 1}
    assert commune.properties["components"] == ["V", "S", "M"]
    assert commune.properties["material_component"] == {
        "description": "incense",
        "consumed": False,
    }
    assert commune.properties["max_yes_or_no_questions"] == 3
    assert commune.properties["repeat_casting_failure_chance_increment_percent"] == 25
    assert commune.cost.spell_slot_level == 5
    assert commune.cost.gold == 0
    assert commune.range == {"self": True}
    assert commune.target_policy == {"min": 0, "max": 0, "self": True, "harmful": False}
    assert commune.automation == [
        {
            "type": "world_effect",
            "effect_type": "commune_answer_window",
            "scope": {"target": "self"},
            "duration": {"until": "duration_1_minute"},
            "tick_on": "self_turn_end",
            "metadata": {
                "contacts_deity_or_divine_proxy": True,
                "max_yes_or_no_questions": 3,
                "questions_must_be_asked_before_spell_ends": True,
                "receives_correct_answer_for_each_question": True,
                "divine_beings_not_necessarily_omniscient": True,
                "unclear_answer_if_beyond_deity_knowledge": True,
                (
                    "gm_may_offer_short_phrase_if_yes_no_misleading_or_contrary_"
                    "to_deity_interests"
                ): True,
                "repeat_casting_before_long_rest_cumulative_no_answer_chance_percent": 25,
                "answer_generation_not_automated": True,
                "repeat_casting_chance_not_automated": True,
            },
        }
    ]
    commune_facts = [
        "settlements",
        "portals_to_other_planes",
        "one_cr_10_plus_celestial_elemental_fey_fiend_or_undead",
        "prevalent_plant_mineral_or_beast",
        "bodies_of_water",
    ]
    commune_spell = compendium.spell("srd.spell.commune_with_nature")
    assert commune_spell.ritual is True
    assert commune_spell.level == 5
    assert commune_spell.school == "divination"
    assert commune_spell.classes == ["druid", "ranger"]
    commune = compendium.action("srd.commune_with_nature")
    assert commune.requirements == {
        "spell_level": 5,
        "class_any": ["druid", "ranger"],
    }
    assert commune.properties["spell_classes"] == ["druid", "ranger"]
    assert commune.properties["ritual"] is True
    assert commune.properties["spell_definition_id"] == "srd.spell.commune_with_nature"
    assert commune.properties["casting_time"] == {"minutes": 1}
    assert commune.properties["components"] == ["V", "S"]
    assert commune.properties["facts_param"] == "commune_with_nature_facts"
    assert commune.properties["allowed_list_params"] == {
        "commune_with_nature_facts": commune_facts
    }
    assert commune.properties["required_list_param_counts"] == {
        "commune_with_nature_facts": 3
    }
    assert commune.properties["max_facts"] == 3
    assert commune.cost.spell_slot_level == 5
    assert commune.range == {"self": True}
    assert commune.target_policy == {"min": 0, "max": 0, "self": True, "harmful": False}
    assert commune.automation == [
        {
            "type": "world_effect",
            "effect_type": "commune_with_nature_knowledge",
            "scope": {"target": "self"},
            "duration": {"until": "instant"},
            "metadata": {
                "communes_with_nature_spirits": True,
                "outdoors_radius_miles": 3,
                "natural_underground_radius_ft": 300,
                "does_not_function_where_nature_replaced_by_construction": True,
                "construction_examples": ["castles", "settlements"],
                "facts_chosen": {"param_list": "commune_with_nature_facts"},
                "max_facts": 3,
                "available_facts": commune_facts,
                "prevalent_fact_requires_choice_of_plant_mineral_or_beast": True,
                "cr_10_plus_creature_is_gm_choice": True,
                "map_query_not_automated": True,
            },
        }
    ]
    telepathic_bond_spell = compendium.spell("srd.spell.telepathic_bond")
    assert telepathic_bond_spell.ritual is True
    assert telepathic_bond_spell.level == 5
    assert telepathic_bond_spell.school == "divination"
    assert telepathic_bond_spell.classes == ["bard", "wizard"]
    telepathic_bond = compendium.action("srd.telepathic_bond")
    assert telepathic_bond.requirements == {
        "spell_level": 5,
        "class_any": ["bard", "wizard"],
    }
    assert telepathic_bond.properties["spell_classes"] == ["bard", "wizard"]
    assert telepathic_bond.properties["ritual"] is True
    assert telepathic_bond.properties["spell_definition_id"] == "srd.spell.telepathic_bond"
    assert telepathic_bond.properties["components"] == ["V", "S", "M"]
    assert telepathic_bond.properties["material_component"] == {
        "description": "two eggs",
        "consumed": False,
    }
    assert telepathic_bond.properties["requires_willing_target"] is True
    assert telepathic_bond.properties["max_willing_creatures"] == 8
    assert telepathic_bond.cost.spell_slot_level == 5
    assert telepathic_bond.cost.gold == 0
    assert telepathic_bond.range == {"normal_ft": 30}
    assert telepathic_bond.target_policy == {"min": 1, "max": 8, "harmful": False}
    assert telepathic_bond.automation == [
        {"type": "target", "mode": "explicit"},
        {
            "type": "world_effect",
            "effect_type": "telepathic_bond",
            "scope": {"target": "explicit", "range_ft": 30},
            "duration": {"until": "duration_1_hour"},
            "tick_on": "self_turn_end",
            "metadata": {
                "psychically_links_targets_to_each_other": True,
                "max_willing_creatures": 8,
                "targets_must_be_within_ft": 30,
                "creatures_unable_to_communicate_in_any_languages_unaffected": True,
                "targets_can_communicate_telepathically_through_bond": True,
                "shared_language_not_required": True,
                "communication_any_distance": True,
                "communication_cannot_extend_to_other_planes": True,
                "language_capability_not_automated": True,
                "telepathic_message_routing_not_automated": True,
            },
        },
    ]
    find_the_path = compendium.action("srd.find_the_path")
    assert find_the_path.requirements == {
        "spell_level": 6,
        "class_any": ["bard", "cleric", "druid"],
    }
    assert find_the_path.properties["spell_classes"] == ["bard", "cleric", "druid"]
    assert find_the_path.properties["casting_time"] == {"minutes": 1}
    assert find_the_path.properties["material_component"] == {
        "description": "a set of divination tools worth 100+ GP",
        "consumed": False,
    }
    assert find_the_path.cost.spell_slot_level == 6
    assert find_the_path.cost.gold == 0
    assert find_the_path.range == {"self": True}
    assert find_the_path.target_policy == {
        "min": 1,
        "max": 1,
        "self": True,
        "harmful": False,
    }
    assert find_the_path.automation == [
        {"type": "target", "mode": "self"},
        {
            "type": "passive_effect",
            "passive_modifiers": {
                "find_the_path": True,
                "senses_most_direct_physical_route": True,
                "requires_familiar_named_location": True,
                "fails_for_other_plane_destination": True,
                "fails_for_moving_destination": True,
                "fails_for_unspecific_destination": True,
                "same_plane_required_to_know_distance_and_direction": True,
                "knows_distance_and_direction_to_destination": True,
                "knows_most_direct_path_when_choosing_paths": True,
            },
            "duration": {"until": "concentration_1_day"},
            "tick_on": "self_turn_end",
            "concentration": True,
        },
    ]
    true_seeing = compendium.action("srd.true_seeing")
    assert true_seeing.requirements == {
        "spell_level": 6,
        "class_any": ["bard", "cleric", "sorcerer", "warlock", "wizard"],
    }
    assert true_seeing.properties["spell_classes"] == [
        "bard",
        "cleric",
        "sorcerer",
        "warlock",
        "wizard",
    ]
    assert true_seeing.properties["requires_willing_target"] is True
    assert true_seeing.properties["material_component"] == {
        "description": "mushroom powder worth 25+ GP",
        "consumed": True,
    }
    assert true_seeing.cost.spell_slot_level == 6
    assert true_seeing.cost.gold == 25
    assert true_seeing.range == {"touch": True}
    assert true_seeing.target_policy == {"min": 1, "max": 1, "harmful": False}
    assert true_seeing.automation == [
        {"type": "target", "mode": "explicit"},
        {
            "type": "passive_effect",
            "passive_modifiers": {"truesight_ft": 120},
            "duration": {"until": "duration_1_hour"},
            "tick_on": "self_turn_end",
        },
    ]
    foresight_spell = compendium.spell("srd.spell.foresight")
    assert foresight_spell.level == 9
    assert foresight_spell.school == "divination"
    assert foresight_spell.classes == ["bard", "druid", "warlock", "wizard"]
    foresight = compendium.action("srd.foresight")
    assert foresight.requirements == {
        "spell_level": 9,
        "class_any": ["bard", "druid", "warlock", "wizard"],
    }
    assert foresight.properties == {
        "spell_classes": ["bard", "druid", "warlock", "wizard"],
        "components": ["V", "S", "M"],
        "casting_time": {"minutes": 1},
        "material_component": {
            "description": "a hummingbird feather",
            "consumed": False,
        },
        "target_must_be_touched": True,
        "requires_willing_target": True,
        "ends_existing_same_spell_from_caster": True,
        "spell_definition_id": "srd.spell.foresight",
        "spell_level": 9,
    }
    assert foresight.cost.spell_slot_level == 9
    assert foresight.cost.gold == 0
    assert foresight.range == {"touch": True}
    assert foresight.target_policy == {"min": 1, "max": 1, "harmful": False}
    assert foresight.automation == [
        {"type": "target", "mode": "explicit"},
        {
            "type": "passive_effect",
            "passive_modifiers": {
                "foresight": True,
                "d20_tests_advantage": True,
                "ability_check_advantage_abilities": ["str", "dex", "con", "int", "wis", "cha"],
                "saving_throw_advantage_abilities": ["str", "dex", "con", "int", "wis", "cha"],
                "death_saves_advantage": True,
                "attack_roll_advantage": True,
                "initiative_advantage": True,
                "initiative_advantage_source": "srd.foresight",
                "incoming_attacks_disadvantage": True,
                "ends_existing_same_spell_from_caster": True,
            },
            "duration": {"until": "duration_8_hours"},
            "tick_on": "self_turn_end",
        },
    ]
    fabricate = compendium.action("srd.fabricate")
    assert fabricate.requirements == {
        "spell_level": 4,
        "class_any": ["wizard"],
    }
    assert fabricate.properties["spell_classes"] == ["wizard"]
    assert fabricate.properties["casting_time"] == {"minutes": 10}
    assert fabricate.cost.spell_slot_level == 4
    assert fabricate.range == {"normal_ft": 120}
    assert fabricate.target_policy == {"min": 0, "max": 0, "harmful": False}
    assert fabricate.automation == [
        {
            "type": "world_effect",
            "effect_type": "fabricated_object",
            "scope": {"target": "visible_raw_materials", "range_ft": 120},
            "duration": {"until": "instant"},
            "metadata": {
                "converts_raw_materials_into_products_of_same_material": True,
                "requires_sufficient_quantity_of_material": True,
                "examples": [
                    "wooden_bridge_from_clump_of_trees",
                    "rope_from_patch_of_hemp",
                    "clothes_from_flax_or_wool",
                ],
                "large_or_smaller_object_max_cube_ft": 10,
                "alternative_eight_connected_5_ft_cubes": True,
                "metal_stone_or_mineral_object_max_size": "medium",
                "metal_stone_or_mineral_object_max_cube_ft": 5,
                "quality_based_on_raw_materials": True,
                "cannot_create_creatures": True,
                "cannot_create_magic_items": True,
                "high_skill_items_require_matching_artisans_tools_proficiency": True,
                "high_skill_item_examples": ["weapons", "armor"],
            },
        }
    ]
    move_earth = compendium.action("srd.move_earth")
    assert move_earth.requirements == {
        "spell_level": 6,
        "class_any": ["druid", "sorcerer", "wizard"],
    }
    assert move_earth.properties["spell_classes"] == ["druid", "sorcerer", "wizard"]
    assert move_earth.properties["material_component"] == {
        "description": "a miniature shovel",
        "consumed": False,
    }
    assert move_earth.range == {"normal_ft": 120, "shape": "square", "max_side_ft": 40}
    assert move_earth.target_policy == {"min": 0, "max": 0, "harmful": False}
    assert move_earth.automation == [
        {
            "type": "world_effect",
            "effect_type": "move_earth_terrain_reshaping",
            "scope": {"target": "terrain_area", "range_ft": 120, "max_side_ft": 40},
            "duration": {"until": "concentration_2_hours"},
            "tick_on": "self_turn_end",
            "metadata": {
                "terrain_types": ["dirt", "sand", "clay"],
                "max_area_side_ft": 40,
                "allowed_shapes": [
                    "raise_elevation",
                    "lower_elevation",
                    "create_trench",
                    "fill_trench",
                    "erect_wall",
                    "flatten_wall",
                    "form_pillar",
                ],
                "max_change_fraction_of_largest_dimension": 0.5,
                "changes_complete_after_minutes": 10,
                "creatures_cannot_usually_be_trapped_or_injured_by_slow_movement": True,
                "can_choose_new_area_every_minutes": 10,
                "cannot_manipulate_natural_stone_or_stone_construction": True,
                "rocks_and_structures_shift_to_accommodate_new_terrain": True,
                "unstable_structures_might_collapse": True,
                "does_not_directly_affect_plant_growth": True,
                "moved_earth_carries_plants_along": True,
            },
        }
    ]
    wind_walk = compendium.action("srd.wind_walk")
    assert wind_walk.requirements == {
        "spell_level": 6,
        "class_any": ["druid"],
    }
    assert wind_walk.properties["spell_classes"] == ["druid"]
    assert wind_walk.properties["casting_time"] == {"minutes": 1}
    assert wind_walk.properties["requires_willing_target"] is True
    assert wind_walk.properties["material_component"] == {
        "description": "a candle",
        "consumed": False,
    }
    assert wind_walk.range == {"normal_ft": 30}
    assert wind_walk.target_policy == {"min": 1, "max": 11, "self": True, "harmful": False}
    assert wind_walk.automation == [
        {"type": "target", "mode": "explicit"},
        {
            "type": "passive_effect",
            "passive_modifiers": {
                "wind_walk_cloud_form": True,
                "gaseous_form": True,
                "fly_speed_ft": 300,
                "can_hover": True,
                "condition_immunities": ["prone"],
                "damage_resistances": ["bludgeoning", "piercing", "slashing"],
                "allowed_action_ids": ["srd.dash"],
                "allowed_unimplemented_magic_actions": [
                    "begin_reverting_to_normal_form",
                ],
                "revert_to_normal_form": {
                    "action_economy": "magic_action",
                    "transformation_duration": "duration_1_minute",
                    "condition_during_transformation": "stunned",
                },
                "revert_to_cloud_form": {
                    "action_economy": "magic_action",
                    "transformation_duration": "duration_1_minute",
                },
                "cloud_form_end_descent": {
                    "descent_ft_per_round": 60,
                    "duration_rounds": 10,
                    "lands_safely_if_reaches_ground": True,
                    "falls_remaining_distance_after_rounds": 10,
                },
            },
            "duration": {"until": "duration_8_hours"},
            "tick_on": "self_turn_end",
        },
    ]
    tree_stride = compendium.action("srd.tree_stride")
    assert tree_stride.requirements == {
        "spell_level": 5,
        "class_any": ["druid", "ranger"],
    }
    assert tree_stride.properties["spell_classes"] == ["druid", "ranger"]
    assert tree_stride.range == {"self": True}
    assert tree_stride.target_policy == {"min": 1, "max": 1, "self": True, "harmful": False}
    assert tree_stride.automation == [
        {"type": "target", "mode": "self"},
        {
            "type": "passive_effect",
            "passive_modifiers": {
                "tree_stride": True,
                "tree_stride_range_ft": 500,
                "same_kind_living_tree_required": True,
                "tree_must_be_at_least_actor_size": True,
                "enter_tree_movement_cost_ft": 5,
                "destination_exit_movement_cost_ft": 5,
                "knows_same_kind_tree_locations_within_ft": 500,
                "appears_within_ft_of_destination_tree": 5,
                "returns_within_ft_of_entered_tree_if_no_movement_left": 5,
                "uses_per_turn": 1,
                "must_end_turn_outside_tree": True,
            },
            "duration": {"until": "concentration_1_minute"},
            "tick_on": "self_turn_end",
            "concentration": True,
        },
    ]
    stone_shape = compendium.action("srd.stone_shape")
    assert stone_shape.requirements == {
        "spell_level": 4,
        "class_any": ["cleric", "druid", "wizard"],
    }
    assert stone_shape.properties["spell_classes"] == ["cleric", "druid", "wizard"]
    assert stone_shape.properties["material_component"] == {
        "description": "soft clay",
        "consumed": False,
    }
    assert stone_shape.cost.spell_slot_level == 4
    assert stone_shape.range == {"touch": True}
    assert stone_shape.target_policy == {"min": 0, "max": 0, "harmful": False}
    assert stone_shape.automation == [
        {
            "type": "world_effect",
            "effect_type": "stone_shape",
            "scope": {"target": "touched_stone"},
            "duration": {"until": "instant"},
            "metadata": {
                "target_material": "stone",
                "stone_object_max_size": "medium",
                "stone_section_max_dimension_ft": 5,
                "forms_into_shape_of_choice": True,
                "srd_example_outputs": [
                    "weapon",
                    "statue",
                    "coffer",
                    "small_passage_through_wall",
                    "sealed_stone_door_or_frame",
                ],
                "small_passage_wall_thickness_ft": 5,
                "created_object_max_hinges": 2,
                "created_object_can_have_latch": True,
                "finer_mechanical_detail_not_possible": True,
            },
        }
    ]
    stoneskin = compendium.action("srd.stoneskin")
    assert stoneskin.requirements == {
        "spell_level": 4,
        "class_any": ["druid", "ranger", "sorcerer", "wizard"],
    }
    assert stoneskin.properties["spell_classes"] == [
        "druid",
        "ranger",
        "sorcerer",
        "wizard",
    ]
    assert stoneskin.properties["requires_willing_target"] is True
    assert stoneskin.properties["material_component"] == {
        "description": "diamond dust worth 100+ GP",
        "consumed": True,
    }
    assert stoneskin.cost.spell_slot_level == 4
    assert stoneskin.cost.gold == 100
    assert stoneskin.range == {"touch": True}
    assert stoneskin.target_policy == {"min": 1, "max": 1, "harmful": False}
    assert stoneskin.automation == [
        {"type": "target", "mode": "explicit"},
        {
            "type": "passive_effect",
            "passive_modifiers": {
                "damage_resistances": ["bludgeoning", "piercing", "slashing"],
            },
            "duration": {"until": "concentration_1_hour"},
            "tick_on": "self_turn_end",
            "concentration": True,
        },
    ]
    passwall = compendium.action("srd.passwall")
    assert passwall.requirements == {"spell_level": 5, "class_any": ["wizard"]}
    assert passwall.properties["spell_classes"] == ["wizard"]
    assert passwall.properties["material_component"] == {
        "description": "a pinch of sesame seeds",
        "consumed": False,
    }
    assert passwall.cost.spell_slot_level == 5
    assert passwall.range == {"normal_ft": 30}
    assert passwall.target_policy == {"min": 0, "max": 0, "harmful": False}
    assert passwall.automation == [
        {
            "type": "world_effect",
            "effect_type": "passwall_passage",
            "scope": {"target": "point_on_surface", "range_ft": 30},
            "duration": {"until": "duration_1_hour"},
            "tick_on": "self_turn_end",
            "metadata": {
                "surface_types": ["wooden", "plaster", "stone"],
                "surface_examples": ["wall", "ceiling", "floor"],
                "max_width_ft": 5,
                "max_height_ft": 8,
                "max_depth_ft": 20,
                "creates_no_structural_instability": True,
                "ejects_occupants_to_nearest_unoccupied_space_on_expiry": True,
            },
        }
    ]
    wall_of_force = compendium.action("srd.wall_of_force")
    assert wall_of_force.requirements == {
        "spell_level": 5,
        "class_any": ["wizard"],
    }
    assert wall_of_force.properties["spell_classes"] == ["wizard"]
    assert wall_of_force.properties["material_component"] == {
        "description": "a shard of glass",
        "consumed": False,
    }
    assert wall_of_force.range == {"normal_ft": 120}
    assert wall_of_force.target_policy == {"min": 0, "max": 0, "harmful": False}
    assert wall_of_force.automation == [
        {
            "type": "world_effect",
            "effect_type": "wall_of_force",
            "scope": {"target": "point", "range_ft": 120},
            "duration": {"until": "concentration_10_minutes"},
            "tick_on": "self_turn_end",
            "metadata": {
                "invisible": True,
                "orientation_options": ["horizontal", "vertical", "angled"],
                "can_be_free_floating": True,
                "can_rest_on_solid_surface": True,
                "hemispherical_dome_max_radius_ft": 10,
                "globe_max_radius_ft": 10,
                "flat_panel_count": 10,
                "flat_panel_width_ft": 10,
                "flat_panel_height_ft": 10,
                "flat_panels_must_be_contiguous": True,
                "thickness_inches": 0.25,
                "pushes_creatures_to_chosen_side_if_cutting_space": True,
                "blocks_physical_passage": True,
                "immune_to_all_damage": True,
                "not_dispelled_by_dispel_magic": True,
                "destroyed_by_disintegrate": True,
                "extends_into_ethereal_plane": True,
                "blocks_ethereal_travel": True,
            },
        }
    ]
    wall_of_stone = compendium.action("srd.wall_of_stone")
    assert wall_of_stone.requirements == {
        "spell_level": 5,
        "class_any": ["druid", "sorcerer", "wizard"],
    }
    assert wall_of_stone.properties["spell_classes"] == ["druid", "sorcerer", "wizard"]
    assert wall_of_stone.properties["material_component"] == {
        "description": "a cube of granite",
        "consumed": False,
    }
    assert wall_of_stone.range == {"normal_ft": 120}
    assert wall_of_stone.target_policy == {"min": 0, "max": 0, "harmful": False}
    assert wall_of_stone.automation == [
        {
            "type": "world_effect",
            "effect_type": "wall_of_stone",
            "scope": {"target": "point", "range_ft": 120},
            "duration": {"until": "concentration_10_minutes"},
            "tick_on": "self_turn_end",
            "metadata": {
                "nonmagical": True,
                "material": "solid_stone",
                "standard_panel_count": 10,
                "standard_panel_width_ft": 10,
                "standard_panel_height_ft": 10,
                "standard_panel_thickness_inches": 6,
                "thin_panel_width_ft": 10,
                "thin_panel_height_ft": 20,
                "thin_panel_thickness_inches": 3,
                "panels_must_be_contiguous": True,
                "pushes_creatures_to_chosen_side_if_cutting_space": True,
                "enclosed_creature_escape_save": {
                    "ability": "dex",
                    "on_success": "may_use_reaction_to_move_up_to_speed_out_of_enclosure",
                },
                "can_have_any_shape": True,
                "cannot_occupy_creature_or_object_space": True,
                "does_not_need_vertical_orientation_or_firm_foundation": True,
                "must_merge_with_and_be_supported_by_existing_stone": True,
                "can_bridge_chasm_or_create_ramp": True,
                "span_over_20_ft_requires_halved_panels_for_support": True,
                "can_create_crude_battlements": True,
                "panel_ac": 15,
                "panel_hp_per_inch_of_thickness": 30,
                "damage_immunities": ["poison", "psychic"],
                "panel_destroyed_at_0_hp": True,
                "connected_panels_may_collapse_at_gm_discretion": True,
                "permanent_if_concentration_full_duration": True,
                "cannot_be_dispelled_when_permanent": True,
                "disappears_when_spell_ends_unless_permanent": True,
            },
        }
    ]
    wall_of_ice = compendium.action("srd.wall_of_ice")
    assert wall_of_ice.requirements == {
        "spell_level": 6,
        "class_any": ["wizard"],
    }
    assert wall_of_ice.properties["spell_classes"] == ["wizard"]
    assert wall_of_ice.properties["material_component"] == {
        "description": "a piece of quartz",
        "consumed": False,
    }
    assert wall_of_ice.range == {"normal_ft": 120}
    assert wall_of_ice.target_policy == {"min": 0, "max": 12, "harmful": True}
    assert wall_of_ice.automation == [
        {"type": "target", "mode": "area"},
        {"type": "saving_throw", "ability": "dex", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "damage",
            "dice": "10d6",
            "damage_type": "cold",
            "save_half": True,
            "base_spell_slot_level": 6,
            "extra_dice_per_slot_above": "2d6",
        },
        {
            "type": "world_effect",
            "effect_type": "wall_of_ice",
            "scope": {"target": "solid_surface", "range_ft": 120},
            "duration": {"until": "concentration_10_minutes"},
            "tick_on": "self_turn_end",
            "metadata": {
                "solid_surface_required": True,
                "shape_options": ["hemispherical_dome", "globe", "flat_panels"],
                "hemispherical_dome_max_radius_ft": 10,
                "globe_max_radius_ft": 10,
                "flat_panel_count": 10,
                "flat_panel_width_ft": 10,
                "flat_panel_height_ft": 10,
                "flat_panels_must_be_contiguous": True,
                "thickness_ft": 1,
                "pushes_creatures_to_chosen_side_if_cutting_space": True,
                "initial_save": {
                    "ability": "dex",
                    "damage": "10d6 cold",
                    "save_half": True,
                    "higher_level_damage_increase": "2d6 per slot above 6",
                },
                "object_ac": 12,
                "hp_per_10_ft_section": 30,
                "damage_immunities": ["cold", "poison", "psychic"],
                "damage_vulnerabilities": ["fire"],
                "section_destroyed_at_0_hp": True,
                "destroyed_section_leaves_frigid_air": True,
                "frigid_air": {
                    "trigger": "creature_moves_through_first_time_on_turn",
                    "save": {
                        "ability": "con",
                        "damage": "5d6 cold",
                        "save_half": True,
                        "higher_level_damage_increase": "1d6 per slot above 6",
                    },
                },
            },
        },
    ]
    blade_barrier = compendium.action("srd.blade_barrier")
    assert blade_barrier.requirements == {
        "spell_level": 6,
        "class_any": ["cleric"],
    }
    assert blade_barrier.properties["spell_classes"] == ["cleric"]
    assert blade_barrier.range == {"normal_ft": 90}
    assert blade_barrier.target_policy == {"min": 0, "max": 20, "harmful": True}
    assert blade_barrier.automation == [
        {"type": "target", "mode": "area"},
        {"type": "saving_throw", "ability": "dex", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "damage",
            "dice": "6d10",
            "damage_type": "force",
            "save_half": True,
        },
        {
            "type": "world_effect",
            "effect_type": "blade_barrier",
            "scope": {"target": "wall", "range_ft": 90},
            "duration": {"until": "concentration_10_minutes"},
            "tick_on": "self_turn_end",
            "metadata": {
                "magical_energy_blades": True,
                "shape_options": ["straight_wall", "ringed_wall"],
                "straight_wall_max_length_ft": 100,
                "straight_wall_max_height_ft": 20,
                "wall_thickness_ft": 5,
                "ringed_wall_max_diameter_ft": 60,
                "ringed_wall_max_height_ft": 20,
                "ringed_wall_thickness_ft": 5,
                "provides_cover": "three_quarters",
                "difficult_terrain": True,
                "initial_save": {
                    "ability": "dex",
                    "damage": "6d10 force",
                    "save_half": True,
                },
                "repeat_save_triggers": [
                    "creature_enters_wall_space",
                    "creature_ends_turn_in_wall_space",
                ],
                "repeat_save_once_per_turn": True,
                "repeat_save": {
                    "ability": "dex",
                    "dc_from": {"spell_save_dc": "actor"},
                    "damage": "6d10 force",
                    "save_half": True,
                },
            },
        },
    ]
    forcecage = compendium.action("srd.forcecage")
    assert forcecage.requirements == {
        "spell_level": 7,
        "class_any": ["bard", "warlock", "wizard"],
    }
    assert forcecage.properties["spell_classes"] == ["bard", "warlock", "wizard"]
    assert forcecage.properties["material_component"] == {
        "description": "ruby dust worth 1,500+ GP",
        "consumed": True,
    }
    assert forcecage.range == {"normal_ft": 100, "shape": "cube"}
    assert forcecage.target_policy == {"min": 0, "max": 0, "harmful": True}
    assert forcecage.cost.gold == 1500
    assert forcecage.automation == [
        {
            "type": "world_effect",
            "effect_type": "forcecage_prison",
            "scope": {"target": "area", "range_ft": 100, "shape": "cube"},
            "duration": {"until": "concentration_1_hour"},
            "tick_on": "self_turn_end",
            "metadata": {
                "immobile": True,
                "invisible": True,
                "composed_of_magical_force": True,
                "form_options": ["cage", "solid_box"],
                "cage_max_side_ft": 20,
                "cage_bar_diameter_inches": 0.5,
                "cage_bar_spacing_inches": 0.5,
                "solid_box_max_side_ft": 10,
                "solid_box_blocks_matter": True,
                "solid_box_blocks_spells_in_or_out": True,
                "creatures_completely_inside_area_are_trapped": True,
                "pushes_partial_or_too_large_creatures_outward": True,
                "cannot_leave_by_nonmagical_means": True,
                "teleport_or_interplanar_exit_requires_save": {
                    "ability": "cha",
                    "dc_from": {"spell_save_dc": "actor"},
                    "success": "magic_can_exit_cage",
                    "failure": "does_not_exit_and_spell_or_effect_is_wasted",
                },
                "extends_into_ethereal_plane": True,
                "blocks_ethereal_travel": True,
                "not_dispelled_by_dispel_magic": True,
            },
        }
    ]
    wall_of_thorns = compendium.action("srd.wall_of_thorns")
    assert wall_of_thorns.requirements == {
        "spell_level": 6,
        "class_any": ["druid"],
    }
    assert wall_of_thorns.properties["spell_classes"] == ["druid"]
    assert wall_of_thorns.properties["material_component"] == {
        "description": "a handful of thorns",
        "consumed": False,
    }
    assert wall_of_thorns.range == {"normal_ft": 120}
    assert wall_of_thorns.target_policy == {"min": 0, "max": 12, "harmful": True}
    assert wall_of_thorns.automation == [
        {"type": "target", "mode": "area"},
        {"type": "saving_throw", "ability": "dex", "dc_from": {"spell_save_dc": "actor"}},
        {
            "type": "damage",
            "dice": "7d8",
            "damage_type": "piercing",
            "save_half": True,
            "base_spell_slot_level": 6,
            "extra_dice_per_slot_above": "1d8",
        },
        {
            "type": "world_effect",
            "effect_type": "wall_of_thorns",
            "scope": {"target": "solid_surface", "range_ft": 120},
            "duration": {"until": "concentration_10_minutes"},
            "tick_on": "self_turn_end",
            "metadata": {
                "solid_surface_required": True,
                "shape_options": ["wall", "circle"],
                "wall_max_length_ft": 60,
                "wall_max_height_ft": 10,
                "wall_thickness_ft": 5,
                "circle_diameter_ft": 20,
                "circle_max_height_ft": 20,
                "circle_thickness_ft": 5,
                "blocks_line_of_sight": True,
                "initial_save": {
                    "ability": "dex",
                    "damage": "7d8 piercing",
                    "save_half": True,
                    "higher_level_damage_increase": "1d8 per slot above 6",
                },
                "movement_cost_per_foot": 4,
                "repeat_save_triggers": [
                    "creature_enters_wall",
                    "creature_ends_turn_in_wall",
                ],
                "repeat_save_once_per_turn": True,
                "repeat_save": {
                    "ability": "dex",
                    "dc_from": {"spell_save_dc": "actor"},
                    "damage": "7d8 slashing",
                    "save_half": True,
                    "higher_level_damage_increase": "1d8 per slot above 6",
                },
            },
        },
    ]
    assert "srd.innate_sorcery" in compendium.actions
    assert compendium.action("srd.innate_sorcery").cost.resources == {
        "srd.resource.innate_sorcery": 1
    }
    assert compendium.action("srd.innate_sorcery").automation[1] == {
        "type": "passive_effect",
        "condition": "innate_sorcery",
        "duration": {"until": "duration_1_minute"},
        "tick_on": "self_turn_end",
        "passive_modifiers": {
            "spell_save_dc_bonus": {"sorcerer": 1},
            "spell_attack_advantage_classes": ["sorcerer"],
        },
    }
    assert compendium.action("srd.font_of_magic_convert_slot_1").cost.spell_slot_level == 1
    assert compendium.action("srd.font_of_magic_convert_slot_1").automation[0] == {
        "type": "resource_delta",
        "resource": "srd.resource.sorcery_points",
        "delta": 1,
        "max_from": {"class_level": "sorcerer"},
    }
    assert compendium.action("srd.font_of_magic_convert_slot_3").requirements == {
        "class": "sorcerer",
        "class_level_min": 5,
    }
    assert compendium.action("srd.font_of_magic_create_slot_1").cost.resources == {
        "srd.resource.sorcery_points": 2
    }
    assert compendium.action("srd.font_of_magic_create_slot_1").automation[0] == {
        "type": "resource_delta",
        "resource": "spell_slot_1",
        "delta": 1,
    }
    assert compendium.action("srd.font_of_magic_create_slot_3").cost.resources == {
        "srd.resource.sorcery_points": 5
    }
    assert compendium.action("srd.sorcerous_restoration").action_economy == "none"
    assert compendium.action("srd.sorcerous_restoration").requirements == {
        "class": "sorcerer",
        "class_level_min": 5,
    }
    assert compendium.action("srd.magical_cunning").cost.resources == {
        "srd.resource.magical_cunning": 1
    }
    assert compendium.action("srd.magical_cunning").automation[0] == {"type": "pact_magic_recovery"}
    eldritch_master = compendium.action("srd.eldritch_master")
    assert eldritch_master.action_economy == "none"
    assert eldritch_master.requirements == {"class": "warlock", "class_level_min": 20}
    assert eldritch_master.properties == {
        "upgrades_action": "srd.magical_cunning",
        "pact_magic_recovery": "all_expended_slots",
    }
    assert compendium.action("srd.eldritch_invocations").requirements == {
        "class": "warlock",
        "class_level_min": 1,
    }
    eldritch_mind = compendium.action("srd.eldritch_mind")
    assert eldritch_mind.requirements == {"class": "warlock", "class_level_min": 1}
    assert eldritch_mind.action_economy == "none"
    assert eldritch_mind.automation[0] == {
        "type": "text_result",
        "text": "The Warlock has Advantage on Constitution saving throws made to maintain Concentration.",
    }
    devils_sight = compendium.action("srd.devils_sight")
    assert devils_sight.requirements == {"class": "warlock", "class_level_min": 2}
    assert devils_sight.action_economy == "none"
    assert devils_sight.automation[0] == {
        "type": "text_result",
        "text": "This invocation lets the Warlock see normally in Dim Light and Darkness, both magical and nonmagical, within 120 feet.",
    }
    lessons = compendium.action("srd.lessons_of_the_first_ones")
    assert lessons.requirements == {"class": "warlock", "class_level_min": 2}
    assert lessons.action_economy == "none"
    assert lessons.automation[0] == {
        "type": "text_result",
        "text": "This invocation lets the Warlock gain one explicitly chosen Origin feat; repeat selections must choose different Origin feats.",
    }
    pact_of_blade = compendium.action("srd.pact_of_the_blade")
    assert pact_of_blade.requirements == {"class": "warlock", "class_level_min": 1}
    assert pact_of_blade.action_economy == "none"
    assert pact_of_blade.automation[0] == {
        "type": "text_result",
        "text": "This invocation lets the Warlock use a Bonus Action to conjure or bond with a Simple or Martial melee weapon as a pact weapon; the bonded weapon can be used as a Spellcasting Focus, and its attacks can use Charisma for attack and damage rolls and can deal Necrotic, Psychic, Radiant, or normal damage.",
    }
    pact_of_tome = compendium.action("srd.pact_of_the_tome")
    assert pact_of_tome.requirements == {"class": "warlock", "class_level_min": 1}
    assert pact_of_tome.action_economy == "none"
    assert pact_of_tome.properties == {
        "pact_of_the_tome": True,
        "book_of_shadows": True,
        "book_appears_at_end_of_short_or_long_rest": True,
        "book_disappears_if_reconjured_or_warlock_dies": True,
        "cantrip_choice_count": 3,
        "ritual_choice_count": 2,
        "ritual_spell_level": 1,
        "chosen_spells_function_as_warlock_spells": True,
        "book_spellcasting_focus": True,
    }
    assert pact_of_tome.automation[0] == {
        "type": "text_result",
        "text": "This invocation conjures a Book of Shadows at the end of a Short or Long Rest; while the book is on the Warlock's person, three explicitly chosen cantrips and two explicitly chosen level 1 Ritual spells are prepared, function as Warlock spells, and the book can be used as a Spellcasting Focus.",
    }
    pact_weapon = compendium.action("srd.pact_of_the_blade_weapon")
    assert pact_weapon.requirements == {"class": "warlock", "class_level_min": 1}
    assert pact_weapon.action_economy == "bonus_action"
    assert pact_weapon.properties == {
        "pact_of_the_blade_weapon": True,
        "allowed_pact_weapon_action_ids": ["srd.longsword_attack", "srd.shortsword_attack"],
    }
    assert pact_weapon.automation == [
        {"type": "target", "mode": "self"},
        {
            "type": "passive_effect",
            "condition": None,
            "passive_modifiers": {
                "pact_weapon": True,
                "pact_weapon_action_id": {"param": "pact_weapon_action_id"},
                "pact_weapon_attack_ability": "cha",
                "pact_weapon_damage_ability": "cha",
                "pact_weapon_damage_types": ["normal", "necrotic", "psychic", "radiant"],
                "pact_weapon_spellcasting_focus": True,
                "pact_weapon_grants_proficiency": True,
                "pact_weapon_conjured_or_bonded": True,
            },
            "duration": {"until": "pact_ends_or_replaced_or_warlock_dies"},
            "tick_on": "weapon_attack",
            "stacking_policy": "replace_condition",
        },
    ]
    eldritch_smite = compendium.action("srd.eldritch_smite")
    assert eldritch_smite.requirements == {"class": "warlock", "class_level_min": 5}
    assert eldritch_smite.action_economy == "none"
    assert eldritch_smite.properties == {
        "requires_pact_of_the_blade": True,
        "requires_pact_weapon_hit": True,
        "expends_pact_magic_spell_slot": True,
        "extra_force_damage": "1d8_plus_1d8_per_pact_slot_level",
        "prone_target_size_max": "huge",
    }
    assert eldritch_smite.automation[0] == {
        "type": "text_result",
        "text": "Once per turn when the Warlock hits a creature with their pact weapon, the Warlock can expend a Pact Magic spell slot to deal 1d8 Force damage plus 1d8 per spell slot level and can give a Huge or smaller target the Prone condition.",
    }
    thirsting_blade = compendium.action("srd.thirsting_blade")
    assert thirsting_blade.requirements == {"class": "warlock", "class_level_min": 5}
    assert thirsting_blade.action_economy == "none"
    assert thirsting_blade.properties == {
        "requires_pact_of_the_blade": True,
        "pact_weapon_extra_attack": True,
        "allowed_pact_weapon_action_ids": ["srd.longsword_attack", "srd.shortsword_attack"],
    }
    assert thirsting_blade.automation[0] == {
        "type": "text_result",
        "text": "This invocation grants Extra Attack for the Warlock's pact weapon only, allowing two attacks with that weapon instead of one when taking the Attack action on the Warlock's turn.",
    }
    pact_of_chain = compendium.action("srd.pact_of_the_chain")
    assert pact_of_chain.requirements == {"class": "warlock", "class_level_min": 1}
    assert pact_of_chain.action_economy == "none"
    assert pact_of_chain.automation[0] == {
        "type": "text_result",
        "text": "This invocation lets the Warlock learn Find Familiar and cast it as a Magic action without expending a spell slot; special familiar forms are recorded from SRD only.",
    }
    investment = compendium.action("srd.investment_of_the_chain_master")
    assert investment.requirements == {"class": "warlock", "class_level_min": 5}
    assert investment.action_economy == "none"
    assert investment.properties == {
        "requires_pact_of_the_chain": True,
        "familiar_aerial_or_aquatic_speed_ft": 40,
        "familiar_quick_attack_bonus_action": True,
        "familiar_damage_type_options": ["necrotic", "radiant"],
        "familiar_uses_warlock_save_dc": True,
        "familiar_reaction_resistance": True,
    }
    assert investment.automation[0] == {
        "type": "text_result",
        "text": "When the Warlock casts Find Familiar, this invocation infuses the summoned familiar: the Warlock chooses a 40-foot Fly or Swim Speed, can command it to Attack as a Bonus Action, can make its Bludgeoning, Piercing, or Slashing damage Necrotic or Radiant, uses the Warlock's spell save DC for its saving throw effects, and can use a Reaction to grant it Resistance against damage.",
    }
    pact_find_familiar = compendium.action("srd.pact_of_the_chain_find_familiar")
    assert pact_find_familiar.requirements == {
        "class": "warlock",
        "class_level_min": 1,
        "spell_level": 1,
    }
    assert pact_find_familiar.cost.spell_slot_level is None
    assert pact_find_familiar.properties == {
        "spell_definition_id": "srd.spell.find_familiar",
        "spell_level": 1,
        "pact_of_the_chain_free_cast": True,
        "familiar_special_forms": [
            "imp",
            "pseudodragon",
            "quasit",
            "skeleton",
            "sphinx_of_wonder",
            "sprite",
            "venomous_snake",
        ],
    }
    assert pact_find_familiar.automation == [
        {
            "type": "world_effect",
            "effect_type": "familiar_bound",
            "scope": {"target": "empty_space", "range_ft": 10},
            "duration": {"until": "dismissed_or_reduced_to_0_hp"},
            "metadata": {
                "spirit_form": True,
                "shares_senses": True,
                "pact_of_the_chain": True,
                "can_forgo_attack_for_familiar_reaction": True,
                "special_forms": [
                    "imp",
                    "pseudodragon",
                    "quasit",
                    "skeleton",
                    "sphinx_of_wonder",
                    "sprite",
                    "venomous_snake",
                ],
            },
        }
    ]
    master_of_myriad_forms = compendium.action("srd.master_of_myriad_forms")
    assert master_of_myriad_forms.requirements == {"class": "warlock", "class_level_min": 5}
    assert master_of_myriad_forms.action_economy == "none"
    assert master_of_myriad_forms.automation[0] == {
        "type": "text_result",
        "text": "This invocation lets the Warlock cast Alter Self without expending a spell slot.",
    }
    master_alter_self = compendium.action("srd.master_of_myriad_forms_alter_self")
    assert master_alter_self.requirements == {
        "class": "warlock",
        "class_level_min": 5,
        "spell_level": 2,
    }
    assert master_alter_self.cost.spell_slot_level is None
    assert master_alter_self.properties == {
        "spell_definition_id": "srd.spell.alter_self",
        "spell_level": 2,
        "master_of_myriad_forms_free_cast": True,
    }
    assert master_alter_self.automation == [
        {"type": "target", "mode": "self"},
        {
            "type": "passive_effect",
            "passive_modifiers": {
                "alter_self_modes": [
                    "aquatic_adaptation",
                    "change_appearance",
                    "natural_weapons",
                ]
            },
            "duration": {"until": "concentration_1_hour"},
            "tick_on": "self_turn",
            "concentration": True,
        },
    ]
    gift_of_depths = compendium.action("srd.gift_of_the_depths")
    assert gift_of_depths.requirements == {"class": "warlock", "class_level_min": 5}
    assert gift_of_depths.action_economy == "none"
    assert gift_of_depths.automation[0] == {
        "type": "text_result",
        "text": "This invocation lets the Warlock breathe underwater, gives a Swim Speed equal to Speed, and lets the Warlock cast Water Breathing once without expending a spell slot; the free casting is regained after a Long Rest.",
    }
    gift_water_breathing = compendium.action("srd.gift_of_the_depths_water_breathing")
    assert gift_water_breathing.requirements == {
        "class": "warlock",
        "class_level_min": 5,
        "spell_level": 3,
    }
    assert gift_water_breathing.cost.resources == {"srd.resource.gift_of_the_depths": 1}
    assert gift_water_breathing.cost.spell_slot_level is None
    assert gift_water_breathing.properties == {
        "spell_definition_id": "srd.spell.water_breathing",
        "spell_level": 3,
        "gift_of_the_depths_free_cast": True,
    }
    assert gift_water_breathing.automation == [
        {"type": "target", "mode": "explicit"},
        {
            "type": "passive_effect",
            "passive_modifiers": {"can_breathe_underwater": True},
            "duration": {"until": "duration_24_hours"},
            "tick_on": "environment",
        },
    ]
    agonizing_blast = compendium.action("srd.agonizing_blast")
    assert agonizing_blast.requirements == {"class": "warlock", "class_level_min": 2}
    assert agonizing_blast.action_economy == "none"
    assert agonizing_blast.automation[0] == {
        "type": "text_result",
        "text": "This invocation lets the Warlock add Charisma modifier to the damage rolls of the explicitly chosen damaging Warlock cantrip.",
    }
    eldritch_spear = compendium.action("srd.eldritch_spear")
    assert eldritch_spear.requirements == {"class": "warlock", "class_level_min": 2}
    assert eldritch_spear.action_economy == "none"
    assert eldritch_spear.automation[0] == {
        "type": "text_result",
        "text": "This invocation increases the range of the explicitly chosen damaging Warlock cantrip with range 10+ feet by 30 feet times Warlock level.",
    }
    repelling_blast = compendium.action("srd.repelling_blast")
    assert repelling_blast.requirements == {"class": "warlock", "class_level_min": 2}
    assert repelling_blast.action_economy == "none"
    assert repelling_blast.automation[0] == {
        "type": "text_result",
        "text": "This invocation lets the Warlock push a Large or smaller creature up to 10 feet straight away when hitting it with the explicitly chosen damaging Warlock cantrip that requires an attack roll.",
    }
    ascendant_step = compendium.action("srd.ascendant_step")
    assert ascendant_step.requirements == {"class": "warlock", "class_level_min": 5}
    assert ascendant_step.action_economy == "none"
    assert ascendant_step.automation[0] == {
        "type": "text_result",
        "text": "This invocation lets the Warlock cast Levitate on themself without expending a spell slot.",
    }
    ascendant_levitate = compendium.action("srd.ascendant_step_levitate")
    assert ascendant_levitate.requirements == {
        "class": "warlock",
        "class_level_min": 5,
        "spell_level": 2,
    }
    assert ascendant_levitate.cost.spell_slot_level is None
    assert ascendant_levitate.properties == {
        "spell_definition_id": "srd.spell.levitate",
        "spell_level": 2,
        "ascendant_step_free_cast": True,
    }
    assert ascendant_levitate.automation == [
        {"type": "target", "mode": "self"},
        {
            "type": "passive_effect",
            "passive_modifiers": {"levitated": True, "vertical_move_ft": 20},
            "duration": {"until": "concentration_10_minutes"},
            "tick_on": "movement",
            "concentration": True,
        },
    ]
    armor_of_shadows = compendium.action("srd.armor_of_shadows")
    assert armor_of_shadows.requirements == {"class": "warlock", "class_level_min": 1}
    assert armor_of_shadows.action_economy == "none"
    armor_of_shadows_cast = compendium.action("srd.armor_of_shadows_mage_armor")
    assert armor_of_shadows_cast.requirements == {
        "class": "warlock",
        "class_level_min": 1,
        "spell_level": 1,
    }
    assert armor_of_shadows_cast.cost.spell_slot_level is None
    assert armor_of_shadows_cast.properties == {
        "spell_definition_id": "srd.spell.mage_armor",
        "spell_level": 1,
        "armor_of_shadows_free_cast": True,
    }
    assert armor_of_shadows_cast.automation[0] == {"type": "target", "mode": "self"}
    assert armor_of_shadows_cast.automation[1]["passive_modifiers"] == {
        "armor_class_formula": "13+dex_modifier"
    }
    fiendish_vigor = compendium.action("srd.fiendish_vigor")
    assert fiendish_vigor.requirements == {"class": "warlock", "class_level_min": 2}
    assert fiendish_vigor.action_economy == "none"
    fiendish_vigor_cast = compendium.action("srd.fiendish_vigor_false_life")
    assert fiendish_vigor_cast.requirements == {
        "class": "warlock",
        "class_level_min": 2,
        "spell_level": 1,
    }
    assert fiendish_vigor_cast.cost.spell_slot_level is None
    assert fiendish_vigor_cast.properties == {
        "spell_definition_id": "srd.spell.false_life",
        "spell_level": 1,
        "fiendish_vigor_free_cast": True,
    }
    assert fiendish_vigor_cast.automation == [
        {"type": "target", "mode": "self"},
        {"type": "temp_hp", "amount": 12},
    ]
    mask_of_many_faces = compendium.action("srd.mask_of_many_faces")
    assert mask_of_many_faces.requirements == {"class": "warlock", "class_level_min": 2}
    assert mask_of_many_faces.action_economy == "none"
    mask_of_many_faces_cast = compendium.action("srd.mask_of_many_faces_disguise_self")
    assert mask_of_many_faces_cast.requirements == {
        "class": "warlock",
        "class_level_min": 2,
        "spell_level": 1,
    }
    assert mask_of_many_faces_cast.cost.spell_slot_level is None
    assert mask_of_many_faces_cast.properties == {
        "spell_definition_id": "srd.spell.disguise_self",
        "spell_level": 1,
        "mask_of_many_faces_free_cast": True,
    }
    assert mask_of_many_faces_cast.automation == [
        {
            "type": "world_effect",
            "effect_type": "illusory_disguise",
            "scope": {"target": "self"},
            "duration": {"until": "duration_1_hour"},
            "metadata": {"requires_investigation_to_notice": True},
        }
    ]
    misty_visions = compendium.action("srd.misty_visions")
    assert misty_visions.requirements == {"class": "warlock", "class_level_min": 2}
    assert misty_visions.action_economy == "none"
    misty_visions_cast = compendium.action("srd.misty_visions_silent_image")
    assert misty_visions_cast.requirements == {
        "class": "warlock",
        "class_level_min": 2,
        "spell_level": 1,
    }
    assert misty_visions_cast.cost.spell_slot_level is None
    assert misty_visions_cast.properties == {
        "spell_definition_id": "srd.spell.silent_image",
        "spell_level": 1,
        "misty_visions_free_cast": True,
    }
    assert misty_visions_cast.automation == [
        {
            "type": "world_effect",
            "effect_type": "silent_illusion",
            "scope": {"target": "point", "range_ft": 60, "cube_ft": 15},
            "duration": {"until": "concentration_10_minutes"},
            "metadata": {"visual_only": True, "concentration": True},
        }
    ]
    one_with_shadows = compendium.action("srd.one_with_shadows")
    assert one_with_shadows.requirements == {"class": "warlock", "class_level_min": 5}
    assert one_with_shadows.action_economy == "none"
    assert one_with_shadows.automation[0] == {
        "type": "text_result",
        "text": "This invocation lets the Warlock cast Invisibility on themself without expending a spell slot while in an area of Dim Light or Darkness.",
    }
    one_with_shadows_cast = compendium.action("srd.one_with_shadows_invisibility")
    assert one_with_shadows_cast.requirements == {
        "class": "warlock",
        "class_level_min": 5,
        "spell_level": 2,
    }
    assert one_with_shadows_cast.cost.spell_slot_level is None
    assert one_with_shadows_cast.properties == {
        "spell_definition_id": "srd.spell.invisibility",
        "spell_level": 2,
        "one_with_shadows_free_cast": True,
        "requires_dim_light_or_darkness": True,
    }
    assert one_with_shadows_cast.automation == [
        {"type": "target", "mode": "self"},
        {
            "type": "condition",
            "condition": "invisible",
            "duration": {"until": "duration_1_hour_or_attacks_or_casts"},
            "tick_on": "target_action",
            "concentration": True,
        },
    ]
    gaze_of_two_minds = compendium.action("srd.gaze_of_two_minds")
    assert gaze_of_two_minds.requirements == {"class": "warlock", "class_level_min": 5}
    assert gaze_of_two_minds.action_economy == "none"
    assert gaze_of_two_minds.automation[0] == {
        "type": "text_result",
        "text": "This invocation lets the Warlock use a Bonus Action to touch a willing creature and perceive through its senses until the end of the Warlock's next turn; subsequent Bonus Actions can maintain the connection while on the same plane, and spells can be cast as if from either creature's space while within 60 feet of each other.",
    }
    gaze_touch = compendium.action("srd.gaze_of_two_minds_touch")
    assert gaze_touch.requirements == {"class": "warlock", "class_level_min": 5}
    assert gaze_touch.action_economy == "bonus_action"
    assert gaze_touch.range == {"normal_ft": 5, "touch": True}
    assert gaze_touch.target_policy == {
        "min": 1,
        "max": 1,
        "harmful": False,
        "exclude_self": True,
    }
    assert gaze_touch.properties == {
        "requires_willing_target": True,
        "requires_touch": True,
        "gaze_of_two_minds_connection": True,
    }
    assert gaze_touch.automation == [
        {"type": "target", "mode": "explicit"},
        {
            "type": "world_effect",
            "effect_type": "gaze_of_two_minds_connection",
            "scope": {"target": "explicit"},
            "duration": {"until": "end_of_next_turn_or_not_maintained"},
            "metadata": {
                "perceive_through_target_senses": True,
                "benefits_from_target_special_senses": True,
                "can_cast_spells_from_target_space_within_60_ft": True,
                "same_plane_required_to_maintain": True,
                "requires_bonus_action_to_maintain": True,
                "initial_touch_required": True,
            },
        },
    ]
    otherworldly_leap = compendium.action("srd.otherworldly_leap")
    assert otherworldly_leap.requirements == {"class": "warlock", "class_level_min": 2}
    assert otherworldly_leap.action_economy == "none"
    otherworldly_leap_cast = compendium.action("srd.otherworldly_leap_jump")
    assert otherworldly_leap_cast.requirements == {
        "class": "warlock",
        "class_level_min": 2,
        "spell_level": 1,
    }
    assert otherworldly_leap_cast.cost.spell_slot_level is None
    assert otherworldly_leap_cast.properties == {
        "spell_definition_id": "srd.spell.jump",
        "spell_level": 1,
        "otherworldly_leap_free_cast": True,
    }
    assert otherworldly_leap_cast.automation == [
        {"type": "target", "mode": "self"},
        {
            "type": "passive_effect",
            "passive_modifiers": {"jump_distance_multiplier": 3},
            "duration": {"until": "duration_1_minute"},
            "tick_on": "movement",
        },
    ]
    assert "srd.bardic_inspiration" in compendium.actions
    assert compendium.action("srd.bardic_inspiration").target_policy["exclude_self"] is True
    assert compendium.action("srd.bardic_inspiration").cost.resources == {
        "srd.resource.bardic_inspiration": 1
    }
    assert compendium.action("srd.bardic_inspiration").automation[1]["passive_modifiers"][
        "bardic_inspiration_die"
    ] == {
        "class_level_die": "bard",
        "default": "d6",
        "tiers": [
            {"level": 5, "die": "d8"},
            {"level": 10, "die": "d10"},
            {"level": 15, "die": "d12"},
        ],
    }
    assert "srd.jack_of_all_trades" in compendium.actions
    assert compendium.action("srd.jack_of_all_trades").requirements == {
        "class": "bard",
        "class_level_min": 2,
    }
    assert compendium.action("srd.jack_of_all_trades").action_economy == "none"
    cutting_words = compendium.action("srd.cutting_words")
    assert cutting_words.action_economy == "reaction"
    assert cutting_words.range == {"normal_ft": 60}
    assert cutting_words.target_policy == {"min": 1, "max": 1, "harmful": True}
    assert cutting_words.requirements == {
        "class": "bard",
        "class_level_min": 3,
        "subclass": "lore",
    }
    assert cutting_words.cost.resources == {"srd.resource.bardic_inspiration": 1}
    assert cutting_words.automation[1] == {"type": "cutting_words"}
    font_restore = compendium.action("srd.font_of_inspiration_restore_bardic_inspiration_slot_1")
    assert font_restore.cost.spell_slot_level == 1
    assert font_restore.action_economy == "none"
    assert font_restore.automation[0] == {
        "type": "resource_delta",
        "resource": "srd.resource.bardic_inspiration",
        "delta": 1,
        "max_from": {"class_resource": "srd.resource.bardic_inspiration"},
    }
    assert (
        compendium.action(
            "srd.font_of_inspiration_restore_bardic_inspiration_slot_3"
        ).cost.spell_slot_level
        == 3
    )
    assert compendium.action("srd.disciple_of_life").requirements == {
        "class": "cleric",
        "class_level_min": 3,
        "subclass": "life",
    }
    assert compendium.action("srd.disciple_of_life").automation[0]["type"] == "text_result"
    assert compendium.action("srd.blessed_healer").requirements == {
        "class": "cleric",
        "class_level_min": 6,
        "subclass": "life",
    }
    assert compendium.action("srd.supreme_healing").requirements == {
        "class": "cleric",
        "class_level_min": 17,
        "subclass": "life",
    }
    assert compendium.action("srd.supreme_healing").automation[0]["type"] == "text_result"
    preserve_life = compendium.action("srd.preserve_life")
    assert preserve_life.cost.resources == {"srd.resource.channel_divinity": 1}
    assert preserve_life.range == {"normal_ft": 30, "line_of_sight": False}
    assert preserve_life.automation[1] == {
        "type": "preserve_life_healing",
        "points_param": "preserve_life_points",
    }
    assert compendium.action("srd.dark_ones_blessing").requirements == {
        "class": "warlock",
        "class_level_min": 3,
        "subclass": "fiend",
    }
    assert compendium.action("srd.dark_ones_blessing").automation[0]["type"] == "text_result"
    assert compendium.action("srd.dark_ones_own_luck").requirements == {
        "class": "warlock",
        "class_level_min": 6,
        "subclass": "fiend",
    }
    assert compendium.action("srd.dark_ones_own_luck").automation[0]["type"] == "text_result"
    fiendish_resilience = compendium.action("srd.fiendish_resilience")
    assert fiendish_resilience.requirements == {
        "class": "warlock",
        "class_level_min": 10,
        "subclass": "fiend",
    }
    assert fiendish_resilience.action_economy == "none"
    assert fiendish_resilience.properties["choice_timing"] == "finish_short_or_long_rest"
    assert fiendish_resilience.properties["choice_key"] == (
        "warlock.fiend.fiendish_resilience.damage_type"
    )
    assert "force" not in fiendish_resilience.properties["allowed_damage_types"]
    assert fiendish_resilience.properties["excluded_damage_types"] == ["force"]
    assert fiendish_resilience.automation[0]["type"] == "text_result"
    assert "srd.divine_spark_heal" in compendium.actions
    assert compendium.action("srd.divine_spark_heal").target_policy["exclude_self"] is True
    assert compendium.action("srd.divine_spark_heal").cost.resources == {
        "srd.resource.channel_divinity": 1
    }
    assert compendium.action("srd.divine_spark_heal").automation[1] == {
        "type": "healing",
        "dice": "1d8",
        "bonus_from": {"ability_modifier": "wis"},
    }
    assert compendium.action("srd.divine_spark_radiant").automation[1] == {
        "type": "saving_throw",
        "ability": "con",
        "dc_from": {"spell_save_dc": "cleric"},
    }
    assert compendium.action("srd.divine_spark_radiant").automation[2] == {
        "type": "damage",
        "dice": "1d8",
        "bonus_from": {"ability_modifier": "wis"},
        "damage_type": "radiant",
        "save_half": True,
    }
    assert compendium.action("srd.divine_spark_necrotic").automation[2]["damage_type"] == "necrotic"
    turn_undead = compendium.action("srd.turn_undead")
    assert turn_undead.target_policy["creature_types"] == ["undead"]
    assert turn_undead.cost.resources == {"srd.resource.channel_divinity": 1}
    assert turn_undead.automation[1] == {
        "type": "saving_throw",
        "ability": "wis",
        "dc_from": {"spell_save_dc": "cleric"},
    }
    assert turn_undead.automation[2] == {
        "type": "condition",
        "condition": "frightened",
        "requires_failed_save": True,
        "duration": {"until": "duration_1_minute", "break_on_damage": True},
        "tick_on": "target_turn_end",
    }
    assert turn_undead.automation[4]["condition"] == "turned"
    assert turn_undead.automation[4]["passive_modifiers"] == {"must_move_away_from_source": True}
    assert turn_undead.automation[5] == {
        "type": "branch",
        "condition": "actor_class_level_min",
        "class": "cleric",
        "level": 5,
        "if_true": [
            {
                "type": "damage",
                "damage_type": "radiant",
                "dice_from": {"ability_modifier": "wis", "die": "d8", "minimum": 1},
                "requires_failed_save": True,
                "shared_roll": True,
                "breaks_on_damage": False,
            }
        ],
        "if_false": [],
    }
    wild_shape = compendium.action("srd.wild_shape_wolf")
    assert wild_shape.action_economy == "bonus_action"
    assert wild_shape.cost.resources == {"srd.resource.wild_shape": 1}
    assert wild_shape.automation[1] == {
        "type": "temp_hp",
        "amount": 0,
        "bonus_from": {"class_level": "druid"},
    }
    assert wild_shape.automation[2]["condition"] == "wild_shape"
    assert wild_shape.automation[2]["stacking_policy"] == "replace_condition"
    assert wild_shape.automation[2]["passive_modifiers"]["wild_shape_form"] == "srd.wolf"
    assert wild_shape.automation[2]["passive_modifiers"]["blocks_spellcasting"] is True
    assert (
        compendium.action("srd.wild_shape_giant_rat").automation[2]["passive_modifiers"][
            "wild_shape_form"
        ]
        == "srd.giant_rat"
    )
    wild_companion = compendium.action("srd.wild_companion_wild_shape")
    assert wild_companion.cost.resources == {"srd.resource.wild_shape": 1}
    assert wild_companion.automation[0] == {
        "type": "world_effect",
        "effect_type": "familiar_bound",
        "scope": {"target": "empty_space", "range_ft": 10},
        "duration": {"until": "long_rest_or_reduced_to_0_hp"},
        "metadata": {
            "spirit_form": True,
            "shares_senses": True,
            "creature_type": "fey",
            "no_material_components": True,
        },
    }
    assert compendium.action("srd.wild_companion_spell_slot").cost.spell_slot_level == 1
    lands_aid = compendium.action("srd.lands_aid")
    assert lands_aid.action_economy == "action"
    assert lands_aid.range == {"normal_ft": 60, "shape": "sphere", "radius_ft": 10}
    assert lands_aid.target_policy == {"min": 1, "harmful": True}
    assert lands_aid.requirements == {
        "class": "druid",
        "class_level_min": 3,
        "subclass": "land",
    }
    assert lands_aid.cost.resources == {"srd.resource.wild_shape": 1}
    assert lands_aid.automation[1] == {
        "type": "saving_throw",
        "ability": "con",
        "dc_from": {"spell_save_dc": "druid"},
    }
    assert lands_aid.automation[2] == {
        "type": "damage",
        "dice": "2d6",
        "damage_type": "necrotic",
        "save_half": True,
        "shared_roll": True,
    }
    assert lands_aid.automation[3] == {
        "type": "target",
        "mode": "param",
        "param": "lands_aid_healing_target_id",
    }
    assert lands_aid.automation[4] == {"type": "healing", "dice": "2d6"}
    assert (
        compendium.action("srd.wild_resurgence_restore_wild_shape_slot_1").cost.spell_slot_level
        == 1
    )
    assert compendium.action("srd.wild_resurgence_restore_wild_shape_slot_1").automation[0] == {
        "type": "wild_resurgence_restore_wild_shape"
    }
    assert (
        compendium.action("srd.wild_resurgence_restore_wild_shape_slot_3").cost.spell_slot_level
        == 3
    )
    assert compendium.action("srd.wild_resurgence_create_spell_slot").cost.resources == {
        "srd.resource.wild_shape": 1,
        "srd.resource.wild_resurgence_spell_slot": 1,
    }
    assert compendium.action("srd.wild_resurgence_create_spell_slot").automation[0] == {
        "type": "resource_delta",
        "resource": "spell_slot_1",
        "delta": 1,
    }
    assert "srd.lay_on_hands" in compendium.actions
    assert compendium.action("srd.lay_on_hands").cost.resource_params == {
        "srd.resource.lay_on_hands": "lay_on_hands_points"
    }
    assert compendium.action("srd.lay_on_hands").automation[1] == {
        "type": "healing",
        "amount_from": "param.lay_on_hands_points",
    }
    assert compendium.action("srd.lay_on_hands_remove_poisoned").cost.resources == {
        "srd.resource.lay_on_hands": 5
    }
    restoring_touch = compendium.action("srd.restoring_touch")
    assert restoring_touch.requirements == {"class": "paladin", "class_level_min": 14}
    assert restoring_touch.cost.resource_params == {
        "srd.resource.lay_on_hands": "lay_on_hands_points"
    }
    assert restoring_touch.properties == {
        "restoring_touch": True,
        "uses_lay_on_hands_pool": True,
        "allowed_conditions": [
            "blinded",
            "charmed",
            "deafened",
            "frightened",
            "paralyzed",
            "stunned",
        ],
        "point_cost_per_condition": 5,
    }
    assert restoring_touch.automation[1] == {
        "type": "restoring_touch",
        "points_param": "lay_on_hands_points",
        "conditions_param": "restoring_touch_conditions",
        "point_cost_per_condition": 5,
        "allowed_conditions": [
            "blinded",
            "charmed",
            "deafened",
            "frightened",
            "paralyzed",
            "stunned",
        ],
    }
    assert compendium.action("srd.divine_smite").cost.spell_slot_level == 1
    assert compendium.action("srd.paladins_smite_divine_smite").cost.resources == {
        "srd.resource.paladins_smite": 1
    }
    assert compendium.action("srd.paladins_smite_divine_smite").automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "next_melee_hit_bonus_damage": "2d8",
            "damage_type": "radiant",
        },
        "duration": {"until": "next_melee_hit_or_1_minute"},
        "tick_on": "weapon_hit",
    }
    faithful_steed = compendium.action("srd.faithful_steed")
    assert faithful_steed.requirements == {"class": "paladin", "class_level_min": 5}
    assert faithful_steed.action_economy == "none"
    aura_of_protection = compendium.action("srd.aura_of_protection")
    assert aura_of_protection.requirements == {"class": "paladin", "class_level_min": 6}
    assert aura_of_protection.action_economy == "none"
    assert aura_of_protection.range == {"self": True, "shape": "emanation", "radius_ft": 10}
    aura_of_courage = compendium.action("srd.aura_of_courage")
    assert aura_of_courage.requirements == {"class": "paladin", "class_level_min": 10}
    assert aura_of_courage.action_economy == "none"
    assert aura_of_courage.range == {"self": True, "shape": "emanation", "radius_ft": 10}
    assert aura_of_courage.properties == {
        "condition_immunity": "frightened",
        "requires_aura_of_protection": True,
    }
    aura_of_devotion = compendium.action("srd.aura_of_devotion")
    assert aura_of_devotion.requirements == {
        "class": "paladin",
        "class_level_min": 7,
        "subclass": "devotion",
    }
    assert aura_of_devotion.action_economy == "none"
    assert aura_of_devotion.range == {"self": True, "shape": "emanation", "radius_ft": 10}
    assert aura_of_devotion.properties == {
        "condition_immunity": "charmed",
        "requires_aura_of_protection": True,
    }
    faithful_steed_cast = compendium.action("srd.faithful_steed_find_steed")
    assert faithful_steed_cast.cost.resources == {"srd.resource.faithful_steed": 1}
    assert faithful_steed_cast.cost.spell_slot_level is None
    assert faithful_steed_cast.properties == {
        "spell_definition_id": "srd.spell.find_steed",
        "spell_level": 2,
        "faithful_steed_free_cast": True,
    }
    assert faithful_steed_cast.automation[0] == {
        "type": "world_effect",
        "effect_type": "steed_bound",
        "scope": {"target": "empty_space", "range_ft": 30},
        "duration": {"until": "dismissed_or_reduced_to_0_hp"},
        "metadata": {"mount": True, "telepathic_bond": True},
    }
    sacred_weapon = compendium.action("srd.sacred_weapon")
    assert sacred_weapon.action_economy == "none"
    assert sacred_weapon.requirements == {
        "class": "paladin",
        "class_level_min": 3,
        "subclass": "devotion",
    }
    assert sacred_weapon.cost.resources == {"srd.resource.channel_divinity": 1}
    assert sacred_weapon.automation[1] == {
        "type": "passive_effect",
        "condition": "sacred_weapon",
        "stacking_policy": "replace_condition",
        "duration": {"until": "duration_10_minutes_or_ended_or_reused"},
        "tick_on": "self_turn_start",
        "passive_modifiers": {
            "sacred_weapon": True,
            "sacred_weapon_action_id": {"param": "sacred_weapon_action_id"},
            "sacred_weapon_attack_bonus_ability": "cha",
            "sacred_weapon_attack_bonus_minimum": 1,
            "sacred_weapon_radiant_damage_choice": True,
            "bright_light_radius_ft": 20,
            "dim_light_beyond_ft": 20,
        },
    }
    assert "srd.favored_enemy_hunters_mark" in compendium.actions
    assert compendium.action("srd.favored_enemy_hunters_mark").cost.resources == {
        "srd.resource.favored_enemy_hunters_mark": 1
    }
    assert compendium.action("srd.favored_enemy_hunters_mark").cost.spell_slot_level is None
    assert compendium.action("srd.favored_enemy_hunters_mark").automation[1][
        "passive_modifiers"
    ] == {
        "hunters_mark": True,
        "attacker_bonus_damage": "1d6",
        "damage_type": "force",
        "tracking_advantage": True,
    }
    roving = compendium.action("srd.roving")
    assert roving.action_economy == "none"
    assert roving.requirements == {"class": "ranger", "class_level_min": 6}
    relentless_hunter = compendium.action("srd.relentless_hunter")
    assert relentless_hunter.action_economy == "none"
    assert relentless_hunter.requirements == {"class": "ranger", "class_level_min": 13}
    assert relentless_hunter.properties == {
        "damage_cannot_break_concentration_on_hunters_mark": True,
        "protected_action_id": "srd.favored_enemy_hunters_mark",
    }
    natures_veil = compendium.action("srd.natures_veil")
    assert natures_veil.action_economy == "bonus_action"
    assert natures_veil.requirements == {"class": "ranger", "class_level_min": 14}
    assert natures_veil.properties == {
        "resource": "srd.resource.natures_veil",
        "uses": "wisdom_modifier_min_1_per_long_rest",
        "condition": "invisible",
        "duration": "until_end_of_next_turn",
        "concentration": False,
    }
    assert natures_veil.cost.resources == {"srd.resource.natures_veil": 1}
    assert natures_veil.automation[1] == {
        "type": "condition",
        "condition": "invisible",
        "duration": {"until": "end_of_next_turn", "remaining_ticks": 2},
        "tick_on": "self_turn_end",
        "concentration": False,
        "stacking_policy": "replace",
    }
    precise_hunter = compendium.action("srd.precise_hunter")
    assert precise_hunter.action_economy == "none"
    assert precise_hunter.requirements == {"class": "ranger", "class_level_min": 17}
    assert precise_hunter.properties == {
        "requires_hunters_mark": True,
        "attack_roll_advantage_against_current_hunters_mark_target": True,
    }
    feral_senses = compendium.action("srd.feral_senses")
    assert feral_senses.action_economy == "none"
    assert feral_senses.requirements == {"class": "ranger", "class_level_min": 18}
    assert feral_senses.properties == {"blindsight_ft": 30}
    foe_slayer = compendium.action("srd.foe_slayer")
    assert foe_slayer.action_economy == "none"
    assert foe_slayer.requirements == {"class": "ranger", "class_level_min": 20}
    assert foe_slayer.properties == {
        "hunters_mark_damage_die": "d10",
        "replaces_hunters_mark_damage_die": "d6",
    }
    assert compendium.classes["ranger"].subclasses["hunter"] == {
        "name": "Hunter",
        "level": 3,
        "features": [
            "Hunter's Lore",
            "Hunter's Prey",
            "Defensive Tactics",
            "Superior Hunter's Prey",
            "Superior Hunter's Defense",
        ],
        "actions": [
            "srd.hunters_lore",
            "srd.defensive_tactics",
            "srd.superior_hunters_prey",
            "srd.superior_hunters_defense",
        ],
        "feature_options": {
            "hunters_prey": [
                "srd.hunters_prey_colossus_slayer",
                "srd.hunters_prey_horde_breaker",
            ],
            "defensive_tactics": [
                "srd.escape_the_horde",
                "srd.multiattack_defense",
            ],
        },
    }
    hunters_lore = compendium.action("srd.hunters_lore")
    assert hunters_lore.action_economy == "none"
    assert hunters_lore.requirements == {
        "class": "ranger",
        "class_level_min": 3,
        "subclass": "hunter",
    }
    assert hunters_lore.automation[1] == {"type": "hunter_lore"}
    colossus_slayer = compendium.action("srd.hunters_prey_colossus_slayer")
    assert colossus_slayer.action_economy == "none"
    assert colossus_slayer.requirements == {
        "class": "ranger",
        "class_level_min": 3,
        "subclass": "hunter",
    }
    horde_breaker = compendium.action("srd.hunters_prey_horde_breaker")
    assert horde_breaker.action_economy == "none"
    assert horde_breaker.requirements == {
        "class": "ranger",
        "class_level_min": 3,
        "subclass": "hunter",
    }
    defensive_tactics = compendium.action("srd.defensive_tactics")
    assert defensive_tactics.action_economy == "none"
    assert defensive_tactics.requirements == {
        "class": "ranger",
        "class_level_min": 7,
        "subclass": "hunter",
    }
    assert defensive_tactics.properties == {
        "feature_choice_key": "ranger.hunter.defensive_tactics",
        "feature_options": ["escape_the_horde", "multiattack_defense"],
    }
    escape_the_horde = compendium.action("srd.escape_the_horde")
    assert escape_the_horde.properties == {
        "defensive_tactics_option": "escape_the_horde",
        "opportunity_attacks_against_self_disadvantage": True,
    }
    multiattack_defense = compendium.action("srd.multiattack_defense")
    assert multiattack_defense.properties == {
        "defensive_tactics_option": "multiattack_defense",
        "same_attacker_follow_up_attacks_disadvantage": True,
    }
    superior_hunters_prey = compendium.action("srd.superior_hunters_prey")
    assert superior_hunters_prey.action_economy == "none"
    assert superior_hunters_prey.requirements == {
        "class": "ranger",
        "class_level_min": 11,
        "subclass": "hunter",
    }
    assert superior_hunters_prey.properties == {
        "requires_hunters_mark": True,
        "once_per_turn": True,
        "secondary_target_within_ft_of_marked_target": 30,
        "secondary_target_must_be_visible": True,
        "copies_hunters_mark_extra_damage": True,
    }
    superior_hunters_defense = compendium.action("srd.superior_hunters_defense")
    assert superior_hunters_defense.action_economy == "reaction"
    assert superior_hunters_defense.requirements == {
        "class": "ranger",
        "class_level_min": 15,
        "subclass": "hunter",
    }
    assert superior_hunters_defense.properties == {
        "reaction_when_taking_damage": True,
        "grants_resistance_to_triggering_damage_type": True,
        "duration": "until_end_of_current_turn",
    }
    assert {
        "srd.cunning_action_dash",
        "srd.cunning_action_disengage",
        "srd.cunning_action_hide",
        "srd.cunning_strike",
        "srd.steady_aim",
        "srd.uncanny_dodge",
    } <= set(compendium.actions)
    assert compendium.action("srd.cunning_strike").requirements == {
        "class": "rogue",
        "class_level_min": 5,
    }
    assert compendium.action("srd.uncanny_dodge").requirements == {
        "class": "rogue",
        "class_level_min": 5,
    }
    assert compendium.action("srd.uncanny_dodge").action_economy == "reaction"
    assert compendium.action("srd.cunning_action_dash").action_economy == "bonus_action"
    assert compendium.action("srd.cunning_action_disengage").requirements == {
        "class": "rogue",
        "class_level_min": 2,
    }
    assert compendium.action("srd.steady_aim").requirements == {
        "class": "rogue",
        "class_level_min": 3,
        "no_movement_used": True,
    }
    assert compendium.action("srd.steady_aim").automation[1]["passive_modifiers"] == {
        "attack_roll_advantage": True
    }
    assert compendium.action("srd.steady_aim").automation[2] == {
        "type": "resource_delta",
        "resource": "budget.movement",
        "set": 0,
    }
    assert compendium.action("srd.cunning_action_hide").automation[1] == {
        "type": "ability_check",
        "ability": "dex",
        "skill": "stealth",
        "difficulty_tier": "medium",
    }
    assert compendium.action("srd.hide").automation[2]["if_true"][0]["duration"] == {
        "until": "revealed_or_attacks_or_casts"
    }
    assert compendium.action("srd.cunning_action_hide").automation[2]["if_true"][0]["duration"] == {
        "until": "revealed_or_attacks_or_casts"
    }
    assert {
        "srd.patient_defense",
        "srd.patient_defense_focus",
        "srd.step_of_the_wind",
        "srd.step_of_the_wind_focus",
    } <= set(compendium.actions)
    assert compendium.action("srd.patient_defense").requirements == {
        "class": "monk",
        "class_level_min": 2,
    }
    assert compendium.action("srd.patient_defense_focus").cost.resources == {
        "srd.resource.focus_points": 1
    }
    assert compendium.action("srd.step_of_the_wind").automation[1] == {
        "type": "resource_delta",
        "resource": "budget.movement",
        "delta_from": "speed",
    }
    assert compendium.action("srd.step_of_the_wind_focus").automation[3] == {
        "type": "passive_effect",
        "condition": "jump_distance_doubled",
        "passive_modifiers": {"jump_distance_multiplier": 2},
        "duration": {"until": "end_of_current_turn"},
        "tick_on": "self_turn_end",
    }
    assert {
        "srd.bandit_scimitar",
        "srd.bandit_light_crossbow",
        "srd.bandit_captain_scimitar",
        "srd.bandit_captain_pistol",
        "srd.cultist_ritual_sickle",
        "srd.giant_rat_bite",
        "srd.kobold_dagger",
        "srd.warrior_infantry_spear",
        "srd.skeleton_shortsword",
        "srd.skeleton_shortbow",
        "srd.wolf_bite",
        "srd.zombie_slam",
    } <= set(compendium.actions)
    assert compendium.action("srd.kobold_dagger").automation[1]["attack_bonus"] == 4
    assert compendium.action("srd.longsword_attack").automation[2] == {
        "type": "damage",
        "dice": "1d8+2",
        "damage_type": "slashing",
        "ability": "str",
        "requires_hit": True,
    }
    assert compendium.action("srd.cultist_ritual_sickle").automation[3] == {
        "type": "damage",
        "amount": 1,
        "damage_type": "necrotic",
        "requires_hit": True,
    }
    assert "srd.extra_attack" in compendium.actions
    assert "srd.use_potion_of_healing" in compendium.actions
    assert "srd.use_potion_of_greater_healing" in compendium.actions
    assert "srd.use_elixir_of_health" in compendium.actions
    assert "srd.use_potion_of_growth" in compendium.actions
    assert "srd.use_potion_of_diminution" in compendium.actions
    assert "srd.use_potion_of_climbing" in compendium.actions
    assert "srd.use_potion_of_clairvoyance" in compendium.actions
    assert "srd.use_potion_of_flying" in compendium.actions
    assert "srd.use_potion_of_invisibility" in compendium.actions
    assert "srd.use_potion_of_vitality" in compendium.actions
    potion_of_growth = compendium.action("srd.use_potion_of_growth")
    assert potion_of_growth.action_economy == "bonus_action"
    assert potion_of_growth.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "size_change": "enlarge",
            "size_category_delta": 1,
            "ability_check_advantage_abilities": ["str"],
            "saving_throw_advantage_abilities": ["str"],
            "enlarge_weapon_damage_bonus": "1d4",
        },
        "duration": {"until": "duration_10_minutes"},
        "tick_on": "self_turn_start",
    }
    potion_of_diminution = compendium.action("srd.use_potion_of_diminution")
    assert potion_of_diminution.action_economy == "bonus_action"
    assert potion_of_diminution.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "size_change": "reduce",
            "size_category_delta": -1,
            "ability_check_disadvantage_abilities": ["str"],
            "saving_throw_disadvantage_abilities": ["str"],
            "reduce_weapon_damage_penalty": "1d4",
        },
        "duration": {"until": "duration_1d4_hours"},
        "duration_roll": {"dice": "1d4", "unit": "hours", "ticks_per_unit": 600},
        "tick_on": "self_turn_start",
    }
    potion_of_climbing = compendium.action("srd.use_potion_of_climbing")
    assert potion_of_climbing.action_economy == "bonus_action"
    assert potion_of_climbing.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "climb_speed_equals_speed": True,
            "ability_check_advantage_skills": [{"ability": "str", "skill": "athletics"}],
        },
        "duration": {"until": "duration_1_hour"},
        "tick_on": "self_turn_start",
    }
    potion_of_clairvoyance = compendium.action("srd.use_potion_of_clairvoyance")
    assert potion_of_clairvoyance.action_economy == "bonus_action"
    assert potion_of_clairvoyance.automation[0] == {
        "type": "world_effect",
        "effect_type": "clairvoyant_sensor",
        "scope": {"target": "known_or_obvious_location", "range_ft": 5280},
        "duration": {"until": "duration_10_minutes"},
        "metadata": {"choose_sight_or_hearing": True, "concentration": False},
    }
    potion_of_flying = compendium.action("srd.use_potion_of_flying")
    assert potion_of_flying.action_economy == "bonus_action"
    assert potion_of_flying.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "fly_speed_equals_speed": True,
            "can_hover": True,
            "fall_if_airborne_on_expiry": True,
        },
        "duration": {"until": "duration_1_hour"},
        "tick_on": "self_turn_start",
    }
    potion_of_gaseous_form = compendium.action("srd.use_potion_of_gaseous_form")
    assert potion_of_gaseous_form.action_economy == "bonus_action"
    assert potion_of_gaseous_form.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "gaseous_form": True,
            "fly_speed_ft": 10,
            "can_hover": True,
            "can_enter_creature_space": True,
            "damage_resistances": ["bludgeoning", "piercing", "slashing"],
            "condition_immunities": ["prone"],
            "saving_throw_advantage_abilities": ["str", "dex", "con"],
            "can_pass_through_narrow_openings": True,
            "liquids_treated_as_solid": True,
            "cannot_talk": True,
            "cannot_manipulate_objects": True,
            "cannot_drop_or_use_carried_objects": True,
            "blocks_attacks": True,
            "blocks_spellcasting": True,
            "can_end_as_bonus_action": True,
        },
        "duration": {"until": "duration_1_hour"},
        "tick_on": "self_turn_start",
    }
    elixir_of_health = compendium.action("srd.use_elixir_of_health")
    assert elixir_of_health.action_economy == "bonus_action"
    assert elixir_of_health.automation[1] == {
        "type": "remove_condition",
        "conditions": ["blinded", "deafened", "paralyzed", "poisoned"],
        "effect_markers": ["magical_contagion"],
    }
    potion_of_invisibility = compendium.action("srd.use_potion_of_invisibility")
    assert potion_of_invisibility.action_economy == "bonus_action"
    assert potion_of_invisibility.automation[1] == {
        "type": "condition",
        "condition": "invisible",
        "duration": {"until": "duration_1_hour_or_attack_damage_spell"},
        "tick_on": "self_turn_start",
    }
    potion_of_heroism = compendium.action("srd.use_potion_of_heroism")
    assert potion_of_heroism.action_economy == "bonus_action"
    assert potion_of_heroism.automation[1] == {
        "type": "temp_hp",
        "amount": 10,
        "duration": {"until": "duration_1_hour"},
        "tick_on": "self_turn_start",
    }
    assert potion_of_heroism.automation[2] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "attack_roll_bonus_dice": "1d4",
            "saving_throw_bonus_dice": "1d4",
        },
        "duration": {"until": "duration_1_hour"},
        "tick_on": "self_turn_start",
    }
    potion_of_invulnerability = compendium.action("srd.use_potion_of_invulnerability")
    assert potion_of_invulnerability.action_economy == "bonus_action"
    assert potion_of_invulnerability.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {"all_damage_resistance": True},
        "duration": {"until": "duration_1_minute"},
        "tick_on": "self_turn_start",
    }
    potion_of_mind_reading = compendium.action("srd.use_potion_of_mind_reading")
    assert potion_of_mind_reading.action_economy == "bonus_action"
    assert potion_of_mind_reading.automation[0] == {
        "type": "world_effect",
        "effect_type": "detect_thoughts",
        "scope": {"target": "self", "radius_ft": 30},
        "duration": {"until": "duration_10_minutes"},
        "metadata": {"surface_thoughts": True, "save_dc": 13, "concentration": False},
    }
    potion_of_poison = compendium.action("srd.use_potion_of_poison")
    assert potion_of_poison.action_economy == "bonus_action"
    assert potion_of_poison.automation[1] == {
        "type": "damage",
        "dice": "4d6",
        "damage_type": "poison",
    }
    assert potion_of_poison.automation[2] == {
        "type": "saving_throw",
        "ability": "con",
        "dc_ref": "srd.potion_of_poison.con_save",
        "dc_table": {"srd.potion_of_poison.con_save": 13},
    }
    assert potion_of_poison.automation[3] == {
        "type": "condition",
        "condition": "poisoned",
        "duration": {"until": "duration_1_hour"},
        "tick_on": "self_turn_start",
        "requires_failed_save": True,
    }
    potion_of_speed = compendium.action("srd.use_potion_of_speed")
    assert potion_of_speed.action_economy == "bonus_action"
    assert potion_of_speed.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "armor_class_bonus": 2,
            "speed_multiplier": 2,
            "extra_action_limited": True,
            "no_haste_lethargy_on_expiry": True,
        },
        "duration": {"until": "duration_1_minute"},
        "tick_on": "self_turn_start",
    }
    potion_of_water_breathing = compendium.action("srd.use_potion_of_water_breathing")
    assert potion_of_water_breathing.action_economy == "bonus_action"
    assert potion_of_water_breathing.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {"can_breathe_underwater": True},
        "duration": {"until": "duration_24_hours"},
        "tick_on": "environment",
    }
    potion_of_vitality = compendium.action("srd.use_potion_of_vitality")
    assert potion_of_vitality.action_economy == "bonus_action"
    assert potion_of_vitality.automation[1] == {
        "type": "remove_condition",
        "conditions": ["exhaustion", "poisoned"],
    }
    assert potion_of_vitality.automation[2] == {
        "type": "passive_effect",
        "passive_modifiers": {"hit_die_healing_maximized": True},
        "duration": {"until": "duration_24_hours"},
        "tick_on": "environment",
        "persistent": True,
    }
    potion_of_animal_friendship = compendium.action("srd.use_potion_of_animal_friendship")
    assert compendium.items["srd.potion_of_animal_friendship"].actions == [
        "srd.use_potion_of_animal_friendship"
    ]
    assert compendium.items["srd.potion_of_animal_friendship"].properties == {
        "spell_definition_id": "srd.spell.animal_friendship",
        "spell_level": 3,
        "save_dc": 13,
    }
    assert potion_of_animal_friendship.action_economy == "bonus_action"
    assert potion_of_animal_friendship.range == {"normal_ft": 30}
    assert potion_of_animal_friendship.target_policy == {
        "min": 1,
        "max": 3,
        "harmful": True,
        "creature_types": ["beast"],
    }
    assert potion_of_animal_friendship.cost.items == {"srd.potion_of_animal_friendship": 1}
    assert potion_of_animal_friendship.automation[1] == {
        "type": "saving_throw",
        "ability": "wis",
        "dc_ref": "srd.potion_of_animal_friendship.wis_save",
        "dc_table": {"srd.potion_of_animal_friendship.wis_save": 13},
    }
    assert potion_of_animal_friendship.automation[2] == {
        "type": "condition",
        "condition": "charmed",
        "duration": {
            "until": "duration_24_hours_or_harmed",
            "break_on_damage": True,
            "break_on_damage_by": "applied_by_or_allies",
        },
        "tick_on": "duration_or_damage",
        "requires_failed_save": True,
    }
    oil_of_sharpness = compendium.action("srd.apply_oil_of_sharpness")
    assert compendium.items["srd.oil_of_sharpness"].actions == ["srd.apply_oil_of_sharpness"]
    assert compendium.items["srd.oil_of_sharpness"].properties == {
        "rarity": "very_rare",
        "application_time_minutes": 1,
        "weapon_bonus": 3,
        "ammunition_count": 20,
    }
    assert oil_of_sharpness.action_economy == "none"
    assert oil_of_sharpness.target_policy == {"min": 1, "max": 1, "harmful": False}
    assert oil_of_sharpness.cost.items == {"srd.oil_of_sharpness": 1}
    assert oil_of_sharpness.properties == {
        "oil_of_sharpness": True,
        "application_time_minutes": 1,
        "weapon_bonus": 3,
        "ammunition_count": 20,
        "allowed_weapon_action_ids": [
            "srd.longsword_attack",
            "srd.shortsword_attack",
        ],
        "ammunition_supported_by_current_rules": False,
    }
    assert oil_of_sharpness.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "weapon_enhancement_bonus": 3,
            "weapon_bonus_action_id": {"param": "oil_of_sharpness_action_id"},
            "coated_weapon_is_magical": True,
            "oil_of_sharpness": True,
        },
        "duration": {"until": "oil_sharpness_replaced_or_weapon_lost"},
        "tick_on": "weapon_attack",
        "stacking_policy": "replace",
    }
    oil_of_etherealness = compendium.action("srd.apply_oil_of_etherealness")
    assert compendium.items["srd.oil_of_etherealness"].actions == ["srd.apply_oil_of_etherealness"]
    assert compendium.items["srd.oil_of_etherealness"].properties == {
        "rarity": "rare",
        "application_time_minutes": 10,
        "base_vial_target_size": "medium",
        "additional_vial_per_size_category_above_medium": 1,
        "duration": "duration_1_hour",
    }
    assert oil_of_etherealness.action_economy == "none"
    assert oil_of_etherealness.target_policy == {"min": 1, "max": 1, "harmful": False}
    assert oil_of_etherealness.cost.resource_params == {
        "srd.oil_of_etherealness": "oil_of_etherealness_vials"
    }
    assert oil_of_etherealness.properties == {
        "oil_of_etherealness": True,
        "application_time_minutes": 10,
        "base_vial_target_size": "medium",
        "additional_vial_per_size_category_above_medium": 1,
        "spell_definition_id": "srd.spell.etherealness",
    }
    assert oil_of_etherealness.automation[1] == {
        "type": "world_effect",
        "effect_type": "etherealness",
        "scope": {"target": "explicit"},
        "duration": {"until": "duration_1_hour"},
        "metadata": {
            "spell_definition_id": "srd.spell.etherealness",
            "equipment_worn_and_carried_included": True,
            "application_time_minutes": 10,
            "concentration": False,
        },
    }
    oil_of_slipperiness = compendium.action("srd.apply_oil_of_slipperiness")
    pour_oil_of_slipperiness = compendium.action("srd.pour_oil_of_slipperiness_on_ground")
    assert compendium.items["srd.oil_of_slipperiness"].actions == [
        "srd.apply_oil_of_slipperiness",
        "srd.pour_oil_of_slipperiness_on_ground",
    ]
    assert compendium.items["srd.oil_of_slipperiness"].properties == {
        "rarity": "uncommon",
        "application_time_minutes": 10,
        "base_vial_target_size": "medium",
        "additional_vial_per_size_category_above_medium": 1,
        "creature_effect_duration": "duration_8_hours",
        "ground_effect_area_size_ft": 10,
        "ground_effect_duration": "duration_8_hours",
    }
    assert oil_of_slipperiness.action_economy == "none"
    assert oil_of_slipperiness.target_policy == {"min": 1, "max": 1, "harmful": False}
    assert oil_of_slipperiness.cost.resource_params == {
        "srd.oil_of_slipperiness": "oil_of_slipperiness_vials"
    }
    assert oil_of_slipperiness.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "freedom_of_movement": True,
            "difficult_terrain_unaffected": True,
            "magical_speed_reduction_immunity": True,
            "magical_paralyzed_restrained_immunity": True,
            "swim_speed_equals_speed": True,
            "nonmagical_restraints_escape_movement_cost_ft": 5,
        },
        "duration": {"until": "duration_8_hours"},
        "tick_on": "self_turn_start",
    }
    assert pour_oil_of_slipperiness.action_economy == "action"
    assert pour_oil_of_slipperiness.properties == {
        "oil_of_slipperiness": True,
        "oil_application_mode": "ground",
        "magic_action": True,
        "spell_definition_id": "srd.spell.grease",
        "ground_effect_area_size_ft": 10,
    }
    assert pour_oil_of_slipperiness.target_policy == {"min": 0, "max": 0, "harmful": True}
    assert pour_oil_of_slipperiness.cost.items == {"srd.oil_of_slipperiness": 1}
    assert pour_oil_of_slipperiness.automation[0] == {
        "type": "world_effect",
        "effect_type": "grease_area",
        "scope": {"target": "ground_area", "shape": "square", "size_ft": 10},
        "duration": {"until": "duration_8_hours"},
        "metadata": {
            "spell_definition_id": "srd.spell.grease",
            "duplicates_spell_effect": True,
            "concentration": False,
        },
    }
    amulet_proof_detection = compendium.action(
        "srd.wear_amulet_of_proof_against_detection_and_location"
    )
    assert compendium.items["srd.amulet_of_proof_against_detection_and_location"].actions == [
        "srd.wear_amulet_of_proof_against_detection_and_location"
    ]
    assert compendium.items["srd.amulet_of_proof_against_detection_and_location"].properties == {
        "rarity": "uncommon",
        "requires_attunement": True,
        "worn_slot": "neck",
    }
    assert amulet_proof_detection.action_economy == "none"
    assert amulet_proof_detection.target_policy == {
        "min": 1,
        "max": 1,
        "self": True,
        "harmful": False,
    }
    assert amulet_proof_detection.requirements == {
        "item": "srd.amulet_of_proof_against_detection_and_location"
    }
    assert amulet_proof_detection.properties == {
        "amulet_of_proof_against_detection_and_location": True,
        "self_only": True,
        "requires_attunement": True,
        "worn_slot": "neck",
    }
    assert amulet_proof_detection.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "hidden_from_divination": True,
            "cannot_be_scryed": True,
            "divination_targeting_allowed_by_wearer": True,
        },
        "duration": {"until": "while_wearing_amulet_of_proof_against_detection_and_location"},
        "stacking_policy": "replace",
    }
    belt_of_giant_strength_variants = {
        "hill": (21, "rare"),
        "frost": (23, "very_rare"),
        "stone": (23, "very_rare"),
        "fire": (25, "very_rare"),
        "cloud": (27, "legendary"),
        "storm": (29, "legendary"),
    }
    for giant_type, (score, rarity) in belt_of_giant_strength_variants.items():
        item_id = f"srd.belt_of_{giant_type}_giant_strength"
        action_id = f"srd.wear_belt_of_{giant_type}_giant_strength"
        item = compendium.items[item_id]
        action = compendium.action(action_id)
        assert item.actions == [action_id]
        assert item.properties == {
            "giant_type": giant_type,
            "strength_score": score,
            "rarity": rarity,
            "requires_attunement": True,
            "worn_slot": "waist",
        }
        assert action.action_economy == "none"
        assert action.target_policy == {
            "min": 1,
            "max": 1,
            "self": True,
            "harmful": False,
        }
        assert action.requirements == {"item": item_id}
        assert action.properties == {
            "belt_of_giant_strength": True,
            "giant_type": giant_type,
            "strength_score": score,
            "self_only": True,
            "requires_attunement": True,
            "worn_slot": "waist",
        }
        assert action.automation[1] == {
            "type": "passive_effect",
            "passive_modifiers": {
                "ability_score_set": {"str": score},
                "giant_strength_type": giant_type,
            },
            "duration": {"until": f"while_wearing_belt_of_{giant_type}_giant_strength"},
            "stacking_policy": "replace",
        }
    boots_of_elvenkind = compendium.action("srd.wear_boots_of_elvenkind")
    assert compendium.items["srd.boots_of_elvenkind"].actions == ["srd.wear_boots_of_elvenkind"]
    assert compendium.items["srd.boots_of_elvenkind"].properties == {
        "rarity": "uncommon",
        "requires_attunement": False,
        "worn_slot": "feet",
    }
    assert boots_of_elvenkind.action_economy == "none"
    assert boots_of_elvenkind.target_policy == {"min": 1, "max": 1, "harmful": False}
    assert boots_of_elvenkind.requirements == {"item": "srd.boots_of_elvenkind"}
    assert boots_of_elvenkind.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "silent_steps": True,
            "ability_check_advantage_skills": [{"ability": "dex", "skill": "stealth"}],
        },
        "duration": {"until": "while_wearing_boots_of_elvenkind"},
        "stacking_policy": "replace",
    }
    boots_of_levitation = compendium.action("srd.boots_of_levitation_levitate")
    assert compendium.items["srd.boots_of_levitation"].actions == [
        "srd.boots_of_levitation_levitate"
    ]
    assert compendium.items["srd.boots_of_levitation"].properties == {
        "rarity": "rare",
        "requires_attunement": True,
        "worn_slot": "feet",
    }
    assert boots_of_levitation.action_economy == "action"
    assert boots_of_levitation.target_policy == {
        "min": 1,
        "max": 1,
        "self": True,
        "harmful": False,
    }
    assert boots_of_levitation.requirements == {
        "item": "srd.boots_of_levitation",
        "spell_level": 2,
    }
    assert boots_of_levitation.cost.spell_slot_level is None
    assert boots_of_levitation.properties == {
        "spell_definition_id": "srd.spell.levitate",
        "spell_level": 2,
        "boots_of_levitation": True,
        "self_only": True,
        "requires_attunement": True,
        "worn_slot": "feet",
    }
    assert boots_of_levitation.automation == [
        {"type": "target", "mode": "explicit"},
        {
            "type": "passive_effect",
            "passive_modifiers": {"levitated": True, "vertical_move_ft": 20},
            "duration": {"until": "concentration_10_minutes"},
            "tick_on": "movement",
            "concentration": True,
        },
    ]
    bracers_of_defense = compendium.action("srd.wear_bracers_of_defense")
    assert compendium.items["srd.bracers_of_defense"].actions == ["srd.wear_bracers_of_defense"]
    assert compendium.items["srd.bracers_of_defense"].properties == {
        "rarity": "rare",
        "requires_attunement": True,
        "worn_slot": "wrists",
    }
    assert bracers_of_defense.action_economy == "none"
    assert bracers_of_defense.target_policy == {
        "min": 1,
        "max": 1,
        "self": True,
        "harmful": False,
    }
    assert bracers_of_defense.requirements == {"item": "srd.bracers_of_defense"}
    assert bracers_of_defense.properties == {
        "bracers_of_defense": True,
        "self_only": True,
        "requires_attunement": True,
        "worn_slot": "wrists",
    }
    assert bracers_of_defense.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "armor_class_bonus": 2,
            "armor_class_requires_unarmored": True,
            "armor_class_requires_no_shield": True,
        },
        "duration": {"until": "while_wearing_bracers_of_defense"},
        "stacking_policy": "replace",
    }
    cloak_of_protection = compendium.action("srd.wear_cloak_of_protection")
    assert compendium.items["srd.cloak_of_protection"].actions == ["srd.wear_cloak_of_protection"]
    assert compendium.items["srd.cloak_of_protection"].properties == {
        "rarity": "uncommon",
        "requires_attunement": True,
        "worn_slot": "shoulders",
    }
    assert cloak_of_protection.action_economy == "none"
    assert cloak_of_protection.target_policy == {
        "min": 1,
        "max": 1,
        "self": True,
        "harmful": False,
    }
    assert cloak_of_protection.requirements == {"item": "srd.cloak_of_protection"}
    assert cloak_of_protection.properties == {
        "cloak_of_protection": True,
        "self_only": True,
        "requires_attunement": True,
        "worn_slot": "shoulders",
    }
    assert cloak_of_protection.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "armor_class_bonus": 1,
            "saving_throw_bonus": 1,
        },
        "duration": {"until": "while_wearing_cloak_of_protection"},
        "stacking_policy": "replace",
    }
    cloak_of_manta_ray = compendium.action("srd.wear_cloak_of_the_manta_ray")
    assert compendium.items["srd.cloak_of_the_manta_ray"].actions == [
        "srd.wear_cloak_of_the_manta_ray"
    ]
    assert compendium.items["srd.cloak_of_the_manta_ray"].properties == {
        "rarity": "uncommon",
        "requires_attunement": True,
        "worn_slot": "shoulders",
    }
    assert cloak_of_manta_ray.action_economy == "none"
    assert cloak_of_manta_ray.target_policy == {
        "min": 1,
        "max": 1,
        "self": True,
        "harmful": False,
    }
    assert cloak_of_manta_ray.requirements == {"item": "srd.cloak_of_the_manta_ray"}
    assert cloak_of_manta_ray.properties == {
        "cloak_of_the_manta_ray": True,
        "self_only": True,
        "requires_attunement": True,
        "worn_slot": "shoulders",
    }
    assert cloak_of_manta_ray.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "can_breathe_underwater": True,
            "swim_speed_ft": 60,
        },
        "duration": {"until": "while_wearing_cloak_of_the_manta_ray"},
        "stacking_policy": "replace",
    }
    eyes_of_the_eagle = compendium.action("srd.wear_eyes_of_the_eagle")
    assert compendium.items["srd.eyes_of_the_eagle"].actions == ["srd.wear_eyes_of_the_eagle"]
    assert compendium.items["srd.eyes_of_the_eagle"].properties == {
        "rarity": "uncommon",
        "requires_attunement": False,
        "worn_slot": "eyes",
    }
    assert eyes_of_the_eagle.action_economy == "none"
    assert eyes_of_the_eagle.target_policy == {
        "min": 1,
        "max": 1,
        "self": True,
        "harmful": False,
    }
    assert eyes_of_the_eagle.requirements == {"item": "srd.eyes_of_the_eagle"}
    assert eyes_of_the_eagle.properties == {
        "eyes_of_the_eagle": True,
        "self_only": True,
        "requires_attunement": False,
        "worn_slot": "eyes",
    }
    assert eyes_of_the_eagle.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "ability_check_advantage_skills": [
                {"ability": "wis", "skill": "perception", "requires_context": "sight"}
            ],
            "clear_visibility_extremely_distant_detail_min_size_ft": 2,
        },
        "duration": {"until": "while_wearing_eyes_of_the_eagle"},
        "stacking_policy": "replace",
    }
    eyes_of_minute_seeing = compendium.action("srd.wear_eyes_of_minute_seeing")
    assert compendium.items["srd.eyes_of_minute_seeing"].actions == [
        "srd.wear_eyes_of_minute_seeing"
    ]
    assert compendium.items["srd.eyes_of_minute_seeing"].properties == {
        "rarity": "uncommon",
        "requires_attunement": False,
        "worn_slot": "eyes",
    }
    assert eyes_of_minute_seeing.action_economy == "none"
    assert eyes_of_minute_seeing.target_policy == {
        "min": 1,
        "max": 1,
        "self": True,
        "harmful": False,
    }
    assert eyes_of_minute_seeing.requirements == {"item": "srd.eyes_of_minute_seeing"}
    assert eyes_of_minute_seeing.properties == {
        "eyes_of_minute_seeing": True,
        "self_only": True,
        "requires_attunement": False,
        "worn_slot": "eyes",
    }
    assert eyes_of_minute_seeing.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "darkvision_ft": 1,
            "ability_check_advantage_skills": [
                {
                    "ability": "int",
                    "skill": "investigation",
                    "requires_context": "within_1_ft_examination",
                }
            ],
        },
        "duration": {"until": "while_wearing_eyes_of_minute_seeing"},
        "stacking_policy": "replace",
    }
    gauntlets_of_ogre_power = compendium.action("srd.wear_gauntlets_of_ogre_power")
    assert compendium.items["srd.gauntlets_of_ogre_power"].actions == [
        "srd.wear_gauntlets_of_ogre_power"
    ]
    assert compendium.items["srd.gauntlets_of_ogre_power"].properties == {
        "rarity": "uncommon",
        "requires_attunement": True,
        "worn_slot": "hands",
    }
    assert gauntlets_of_ogre_power.action_economy == "none"
    assert gauntlets_of_ogre_power.target_policy == {
        "min": 1,
        "max": 1,
        "self": True,
        "harmful": False,
    }
    assert gauntlets_of_ogre_power.requirements == {"item": "srd.gauntlets_of_ogre_power"}
    assert gauntlets_of_ogre_power.properties == {
        "gauntlets_of_ogre_power": True,
        "self_only": True,
        "requires_attunement": True,
        "worn_slot": "hands",
    }
    assert gauntlets_of_ogre_power.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {"ability_score_set": {"str": 19}},
        "duration": {"until": "while_wearing_gauntlets_of_ogre_power"},
        "stacking_policy": "replace",
    }
    goggles_of_night = compendium.action("srd.wear_goggles_of_night")
    assert compendium.items["srd.goggles_of_night"].actions == ["srd.wear_goggles_of_night"]
    assert compendium.items["srd.goggles_of_night"].properties == {
        "rarity": "uncommon",
        "requires_attunement": False,
        "worn_slot": "eyes",
    }
    assert goggles_of_night.action_economy == "none"
    assert goggles_of_night.target_policy == {
        "min": 1,
        "max": 1,
        "self": True,
        "harmful": False,
    }
    assert goggles_of_night.requirements == {"item": "srd.goggles_of_night"}
    assert goggles_of_night.properties == {
        "goggles_of_night": True,
        "self_only": True,
        "requires_attunement": False,
        "worn_slot": "eyes",
    }
    assert goggles_of_night.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "darkvision_ft": 60,
            "darkvision_existing_bonus_ft": 60,
        },
        "duration": {"until": "while_wearing_goggles_of_night"},
        "stacking_policy": "replace",
    }
    headband_of_intellect = compendium.action("srd.wear_headband_of_intellect")
    assert compendium.items["srd.headband_of_intellect"].actions == [
        "srd.wear_headband_of_intellect"
    ]
    assert compendium.items["srd.headband_of_intellect"].properties == {
        "rarity": "uncommon",
        "requires_attunement": True,
        "worn_slot": "head",
    }
    assert headband_of_intellect.action_economy == "none"
    assert headband_of_intellect.target_policy == {
        "min": 1,
        "max": 1,
        "self": True,
        "harmful": False,
    }
    assert headband_of_intellect.requirements == {"item": "srd.headband_of_intellect"}
    assert headband_of_intellect.properties == {
        "headband_of_intellect": True,
        "self_only": True,
        "requires_attunement": True,
        "worn_slot": "head",
    }
    assert headband_of_intellect.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {"ability_score_set": {"int": 19}},
        "duration": {"until": "while_wearing_headband_of_intellect"},
        "stacking_policy": "replace",
    }
    helm_languages = compendium.action("srd.helm_of_comprehending_languages_comprehend_languages")
    assert compendium.items["srd.helm_of_comprehending_languages"].actions == [
        "srd.helm_of_comprehending_languages_comprehend_languages"
    ]
    assert compendium.items["srd.helm_of_comprehending_languages"].properties == {
        "rarity": "uncommon",
        "requires_attunement": False,
        "worn_slot": "head",
    }
    assert helm_languages.action_economy == "action"
    assert helm_languages.target_policy == {
        "min": 1,
        "max": 1,
        "self": True,
        "harmful": False,
    }
    assert helm_languages.requirements == {
        "item": "srd.helm_of_comprehending_languages",
        "spell_level": 1,
    }
    assert helm_languages.cost.spell_slot_level is None
    assert helm_languages.properties == {
        "spell_definition_id": "srd.spell.comprehend_languages",
        "spell_level": 1,
        "helm_of_comprehending_languages": True,
        "self_only": True,
        "requires_attunement": False,
        "worn_slot": "head",
    }
    assert helm_languages.automation == [
        {"type": "target", "mode": "explicit"},
        {
            "type": "world_effect",
            "effect_type": "comprehend_languages",
            "scope": {"target": "self"},
            "duration": {"until": "duration_1_hour"},
            "metadata": {"language_mode": "understand_literal_meaning"},
        },
    ]
    necklace_of_adaptation = compendium.action("srd.wear_necklace_of_adaptation")
    assert compendium.items["srd.necklace_of_adaptation"].actions == [
        "srd.wear_necklace_of_adaptation"
    ]
    assert compendium.items["srd.necklace_of_adaptation"].properties == {
        "rarity": "uncommon",
        "requires_attunement": True,
        "worn_slot": "neck",
    }
    assert necklace_of_adaptation.action_economy == "none"
    assert necklace_of_adaptation.target_policy == {
        "min": 1,
        "max": 1,
        "self": True,
        "harmful": False,
    }
    assert necklace_of_adaptation.requirements == {"item": "srd.necklace_of_adaptation"}
    assert necklace_of_adaptation.properties == {
        "necklace_of_adaptation": True,
        "self_only": True,
        "requires_attunement": True,
        "worn_slot": "neck",
    }
    assert necklace_of_adaptation.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "can_breathe_normally_any_environment": True,
            "saving_throw_advantage_contexts": ["avoid_or_end_condition:poisoned"],
        },
        "duration": {"until": "while_wearing_necklace_of_adaptation"},
        "stacking_policy": "replace",
    }
    periapt_poison = compendium.action("srd.wear_periapt_of_proof_against_poison")
    assert compendium.items["srd.periapt_of_proof_against_poison"].actions == [
        "srd.wear_periapt_of_proof_against_poison"
    ]
    assert compendium.items["srd.periapt_of_proof_against_poison"].properties == {
        "rarity": "rare",
        "requires_attunement": True,
        "worn_slot": "neck",
    }
    assert periapt_poison.action_economy == "none"
    assert periapt_poison.target_policy == {
        "min": 1,
        "max": 1,
        "self": True,
        "harmful": False,
    }
    assert periapt_poison.requirements == {"item": "srd.periapt_of_proof_against_poison"}
    assert periapt_poison.properties == {
        "periapt_of_proof_against_poison": True,
        "self_only": True,
        "requires_attunement": True,
        "worn_slot": "neck",
    }
    assert periapt_poison.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "condition_immunities": ["poisoned"],
            "damage_immunities": ["poison"],
        },
        "duration": {"until": "while_wearing_periapt_of_proof_against_poison"},
        "stacking_policy": "replace",
    }
    slippers_spider = compendium.action("srd.wear_slippers_of_spider_climbing")
    assert compendium.items["srd.slippers_of_spider_climbing"].actions == [
        "srd.wear_slippers_of_spider_climbing"
    ]
    assert compendium.items["srd.slippers_of_spider_climbing"].properties == {
        "rarity": "uncommon",
        "requires_attunement": True,
        "worn_slot": "feet",
    }
    assert slippers_spider.action_economy == "none"
    assert slippers_spider.target_policy == {
        "min": 1,
        "max": 1,
        "self": True,
        "harmful": False,
    }
    assert slippers_spider.requirements == {"item": "srd.slippers_of_spider_climbing"}
    assert slippers_spider.properties == {
        "slippers_of_spider_climbing": True,
        "self_only": True,
        "requires_attunement": True,
        "worn_slot": "feet",
    }
    assert slippers_spider.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "climb_speed_equals_speed": True,
            "can_move_along_vertical_surfaces": True,
            "can_move_along_ceilings": True,
            "hands_free_while_climbing": True,
            "slippery_surface_blocks_spider_climbing": True,
        },
        "duration": {"until": "while_wearing_slippers_of_spider_climbing"},
        "stacking_policy": "replace",
    }
    stone_of_good_luck = compendium.action("srd.carry_stone_of_good_luck")
    assert compendium.items["srd.stone_of_good_luck"].actions == ["srd.carry_stone_of_good_luck"]
    assert compendium.items["srd.stone_of_good_luck"].properties == {
        "rarity": "uncommon",
        "requires_attunement": True,
        "carried_on_person": True,
    }
    assert stone_of_good_luck.action_economy == "none"
    assert stone_of_good_luck.target_policy == {
        "min": 1,
        "max": 1,
        "self": True,
        "harmful": False,
    }
    assert stone_of_good_luck.requirements == {"item": "srd.stone_of_good_luck"}
    assert stone_of_good_luck.properties == {
        "stone_of_good_luck": True,
        "self_only": True,
        "requires_attunement": True,
        "carried_on_person": True,
    }
    assert stone_of_good_luck.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "ability_check_bonus": 1,
            "saving_throw_bonus": 1,
        },
        "duration": {"until": "while_carrying_stone_of_good_luck"},
        "stacking_policy": "replace",
    }
    robe_of_eyes = compendium.action("srd.wear_robe_of_eyes")
    robe_light = compendium.action("srd.robe_of_eyes_light_drawback")
    robe_daylight = compendium.action("srd.robe_of_eyes_daylight_drawback")
    robe_archmagi = compendium.action("srd.wear_robe_of_the_archmagi")
    robe_useful_init = compendium.action("srd.initialize_robe_of_useful_items_patches")
    robe_useful_detach = compendium.action("srd.detach_robe_of_useful_items_patch")
    rod_absorption_init = compendium.action("srd.initialize_rod_of_absorption_energy")
    rod_absorption_absorb = compendium.action("srd.rod_of_absorption_absorb_spell")
    rod_alertness_hold = compendium.action("srd.hold_rod_of_alertness")
    rod_alertness_detect_magic = compendium.action("srd.rod_of_alertness_detect_magic")
    rod_alertness_see_invisibility = compendium.action("srd.rod_of_alertness_see_invisibility")
    rod_alertness_aura = compendium.action("srd.rod_of_alertness_protective_aura")
    assert compendium.items["srd.robe_of_eyes"].actions == [
        "srd.wear_robe_of_eyes",
        "srd.robe_of_eyes_light_drawback",
        "srd.robe_of_eyes_daylight_drawback",
    ]
    assert compendium.items["srd.robe_of_eyes"].properties == {
        "rarity": "rare",
        "requires_attunement": True,
        "worn_slot": "body",
    }
    assert robe_of_eyes.action_economy == "none"
    assert robe_of_eyes.target_policy == {
        "min": 1,
        "max": 1,
        "self": True,
        "harmful": False,
    }
    assert robe_of_eyes.requirements == {"item": "srd.robe_of_eyes"}
    assert robe_of_eyes.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "ability_check_advantage_skills": [
                {"ability": "wis", "skill": "perception", "requires_context": "sight"}
            ],
            "darkvision_ft": 120,
            "truesight_ft": 120,
            "robe_of_eyes_drawback_light": True,
            "robe_of_eyes_drawback_daylight": True,
        },
        "duration": {"until": "while_wearing_robe_of_eyes"},
        "stacking_policy": "replace",
    }
    assert robe_light.automation[1]["condition"] == "blinded"
    assert robe_light.automation[1]["duration"]["repeat_save"] == {
        "ability": "con",
        "dc": 11,
        "dc_source": "dc_ref:srd.robe_of_eyes.light_con_save",
        "end_on_success": True,
    }
    assert robe_daylight.properties["trigger_range_ft"] == 5
    assert robe_daylight.automation[1]["condition"] == "blinded"
    assert robe_daylight.automation[1]["duration"]["repeat_save"] == {
        "ability": "con",
        "dc": 15,
        "dc_source": "dc_ref:srd.robe_of_eyes.daylight_con_save",
        "end_on_success": True,
    }
    assert compendium.items["srd.robe_of_the_archmagi"].actions == ["srd.wear_robe_of_the_archmagi"]
    assert compendium.items["srd.robe_of_the_archmagi"].properties == {
        "rarity": "legendary",
        "requires_attunement": True,
        "attunement_class_any": ["sorcerer", "warlock", "wizard"],
        "worn_slot": "body",
    }
    assert robe_archmagi.action_economy == "none"
    assert robe_archmagi.target_policy == {
        "min": 1,
        "max": 1,
        "self": True,
        "harmful": False,
    }
    assert robe_archmagi.requirements == {
        "item": "srd.robe_of_the_archmagi",
        "class_any": ["sorcerer", "warlock", "wizard"],
    }
    assert robe_archmagi.properties == {
        "robe_of_the_archmagi": True,
        "self_only": True,
        "requires_attunement": True,
        "attunement_class_any": ["sorcerer", "warlock", "wizard"],
        "worn_slot": "body",
    }
    assert robe_archmagi.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "armor_class_formula": "15+dex_modifier",
            "armor_class_requires_unarmored": True,
            "saving_throw_advantage_contexts": ["spell", "magical_effect"],
            "spell_save_dc_bonus": {
                "sorcerer": 2,
                "warlock": 2,
                "wizard": 2,
            },
            "spell_attack_bonus": {
                "sorcerer": 2,
                "warlock": 2,
                "wizard": 2,
            },
        },
        "duration": {"until": "while_wearing_robe_of_the_archmagi"},
        "stacking_policy": "replace",
    }
    assert compendium.items["srd.robe_of_useful_items"].actions == [
        "srd.initialize_robe_of_useful_items_patches",
        "srd.detach_robe_of_useful_items_patch",
    ]
    assert compendium.items["srd.robe_of_useful_items"].properties == {
        "rarity": "uncommon",
        "requires_attunement": False,
        "worn_slot": "body",
    }
    assert robe_useful_init.action_economy == "none"
    assert robe_useful_init.requirements == {"item": "srd.robe_of_useful_items"}
    assert robe_useful_init.automation[1]["fixed_patches"] == {
        "bullseye_lantern": 2,
        "dagger": 2,
        "mirror": 2,
        "pole": 2,
        "rope_coiled": 2,
        "sack": 2,
    }
    assert robe_useful_init.automation[1]["extra_patch_roll"] == "4d4"
    assert robe_useful_init.automation[1]["extra_patch_table"] == [
        {"min": 1, "max": 8, "patch": "bag_of_100_gp"},
        {"min": 9, "max": 15, "patch": "silver_coffer"},
        {"min": 16, "max": 22, "patch": "iron_door"},
        {"min": 23, "max": 30, "patch": "ten_gems"},
        {"min": 31, "max": 44, "patch": "wooden_ladder"},
        {"min": 45, "max": 51, "patch": "riding_horse"},
        {"min": 52, "max": 59, "patch": "open_pit"},
        {"min": 60, "max": 68, "patch": "potions_of_healing"},
        {"min": 69, "max": 75, "patch": "rowboat"},
        {"min": 76, "max": 83, "patch": "spell_scroll"},
        {"min": 84, "max": 90, "patch": "mastiffs"},
        {"min": 91, "max": 96, "patch": "window"},
        {"min": 97, "max": 100, "patch": "portable_ram"},
    ]
    assert robe_useful_detach.action_economy == "action"
    assert robe_useful_detach.properties["magic_action"] is True
    assert robe_useful_detach.properties["robe_of_useful_items_patch_keys"] == [
        "bullseye_lantern",
        "dagger",
        "mirror",
        "pole",
        "rope_coiled",
        "sack",
        "bag_of_100_gp",
        "silver_coffer",
        "iron_door",
        "ten_gems",
        "wooden_ladder",
        "riding_horse",
        "open_pit",
        "potions_of_healing",
        "rowboat",
        "spell_scroll",
        "mastiffs",
        "window",
        "portable_ram",
    ]
    useful_patches = robe_useful_detach.automation[1]["patches"]
    assert useful_patches["dagger"] == {"items": [{"item_id": "srd.dagger", "quantity": 1}]}
    assert useful_patches["bag_of_100_gp"] == {"gold": 100}
    assert useful_patches["potions_of_healing"] == {
        "items": [{"item_id": "srd.potion_of_healing", "quantity": 4}]
    }
    assert useful_patches["iron_door"]["world_effect"]["metadata"]["max_width_ft"] == 10
    assert useful_patches["mastiffs"]["world_effect"]["metadata"] == {
        "creature": "mastiff",
        "count": 2,
    }
    assert compendium.items["srd.bullseye_lantern"].properties == {
        "robe_of_useful_items_patch": True,
        "filled_and_lit": True,
    }
    assert compendium.items["srd.portable_ram"].properties == {"robe_of_useful_items_patch": True}
    assert compendium.items["srd.spell_scroll_level_1_3"].properties == {
        "robe_of_useful_items_patch": True,
        "spell_level_choices": [1, 2, 3],
    }
    assert compendium.items["srd.rod_of_absorption"].actions == [
        "srd.initialize_rod_of_absorption_energy",
        "srd.rod_of_absorption_absorb_spell",
    ]
    assert compendium.items["srd.rod_of_absorption"].properties == {
        "rarity": "very_rare",
        "requires_attunement": True,
        "held_item": True,
        "max_lifetime_absorbed_levels": 50,
        "max_created_spell_slot_level": 5,
    }
    assert rod_absorption_init.action_economy == "none"
    assert rod_absorption_init.requirements == {"item": "srd.rod_of_absorption"}
    assert rod_absorption_init.automation[1] == {
        "type": "rod_of_absorption_initialize",
        "stored_energy_roll": "1d10",
    }
    assert rod_absorption_absorb.action_economy == "reaction"
    assert rod_absorption_absorb.target_policy == {
        "min": 1,
        "max": 1,
        "self": True,
        "harmful": False,
    }
    assert rod_absorption_absorb.properties == {
        "rod_of_absorption": True,
        "rod_of_absorption_absorb_spell": True,
        "spell_level_param": "absorbed_spell_level",
        "targeting_only_you_param": "targeting_only_you",
        "creates_area_of_effect_param": "creates_area_of_effect",
        "self_only": True,
        "requires_attunement": True,
        "held_item": True,
        "max_lifetime_absorbed_levels": 50,
    }
    assert rod_absorption_absorb.automation[1] == {
        "type": "rod_of_absorption_absorb_spell",
        "spell_level_param": "absorbed_spell_level",
        "targeting_only_you_param": "targeting_only_you",
        "creates_area_of_effect_param": "creates_area_of_effect",
    }
    assert compendium.items["srd.rod_of_alertness"].actions == [
        "srd.hold_rod_of_alertness",
        "srd.rod_of_alertness_detect_evil_and_good",
        "srd.rod_of_alertness_detect_magic",
        "srd.rod_of_alertness_detect_poison_and_disease",
        "srd.rod_of_alertness_see_invisibility",
        "srd.rod_of_alertness_protective_aura",
    ]
    assert compendium.items["srd.rod_of_alertness"].properties == {
        "rarity": "very_rare",
        "requires_attunement": True,
        "held_item": True,
        "spells": [
            "srd.spell.detect_evil_and_good",
            "srd.spell.detect_magic",
            "srd.spell.detect_poison_and_disease",
            "srd.spell.see_invisibility",
        ],
        "protective_aura_once_until_next_dawn": True,
    }
    assert rod_alertness_hold.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "ability_check_advantage_skills": [{"ability": "wis", "skill": "perception"}],
            "initiative_advantage": True,
            "initiative_advantage_source": "rod_of_alertness",
        },
        "duration": {"until": "while_holding_rod_of_alertness"},
        "stacking_policy": "replace",
    }
    assert rod_alertness_detect_magic.action_type == "spell"
    assert rod_alertness_detect_magic.cost.spell_slot_level is None
    assert rod_alertness_detect_magic.requirements == {
        "item": "srd.rod_of_alertness",
        "spell_level": 1,
    }
    assert rod_alertness_detect_magic.properties["spell_definition_id"] == (
        "srd.spell.detect_magic"
    )
    assert rod_alertness_detect_magic.automation[0] == {
        "type": "world_effect",
        "effect_type": "detect_magic",
        "scope": {"target": "self", "radius_ft": 30},
        "duration": {"until": "concentration_10_minutes"},
        "metadata": {
            "reveals_school": True,
            "concentration": True,
            "spell_definition_id": "srd.spell.detect_magic",
            "duplicates_spell_effect": True,
        },
    }
    assert rod_alertness_see_invisibility.cost.spell_slot_level is None
    assert rod_alertness_see_invisibility.properties["spell_definition_id"] == (
        "srd.spell.see_invisibility"
    )
    assert rod_alertness_aura.action_economy == "action"
    assert rod_alertness_aura.properties == {
        "rod_of_alertness": True,
        "rod_of_alertness_protective_aura": True,
        "magic_action": True,
        "requires_attunement": True,
        "held_item": True,
        "bright_light_radius_ft": 60,
        "dim_light_additional_ft": 60,
        "once_until_next_dawn": True,
    }
    assert rod_alertness_aura.automation[1] == {
        "type": "rod_of_alertness_protective_aura",
        "bright_light_radius_ft": 60,
        "dim_light_additional_ft": 60,
        "passive_modifiers": {
            "armor_class_bonus": 1,
            "saving_throw_bonus": 1,
            "sense_invisible_creature_locations_in_same_bright_light": True,
        },
        "duration": {"until": "duration_10_minutes_or_magic_action_to_remove"},
        "tick_on": "aura",
        "stacking_policy": "replace",
    }
    ring_of_protection = compendium.action("srd.wear_ring_of_protection")
    assert compendium.items["srd.ring_of_protection"].actions == ["srd.wear_ring_of_protection"]
    assert compendium.items["srd.ring_of_protection"].properties == {
        "rarity": "rare",
        "requires_attunement": True,
        "worn_slot": "ring",
    }
    assert ring_of_protection.action_economy == "none"
    assert ring_of_protection.target_policy == {
        "min": 1,
        "max": 1,
        "self": True,
        "harmful": False,
    }
    assert ring_of_protection.requirements == {"item": "srd.ring_of_protection"}
    assert ring_of_protection.properties == {
        "ring_of_protection": True,
        "self_only": True,
        "requires_attunement": True,
        "worn_slot": "ring",
    }
    assert ring_of_protection.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "armor_class_bonus": 1,
            "saving_throw_bonus": 1,
        },
        "duration": {"until": "while_wearing_ring_of_protection"},
        "stacking_policy": "replace",
    }
    ring_of_swimming = compendium.action("srd.wear_ring_of_swimming")
    assert compendium.items["srd.ring_of_swimming"].actions == ["srd.wear_ring_of_swimming"]
    assert compendium.items["srd.ring_of_swimming"].properties == {
        "rarity": "uncommon",
        "requires_attunement": False,
        "worn_slot": "ring",
    }
    assert ring_of_swimming.action_economy == "none"
    assert ring_of_swimming.target_policy == {"min": 1, "max": 1, "harmful": False}
    assert ring_of_swimming.requirements == {"item": "srd.ring_of_swimming"}
    assert ring_of_swimming.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {"swim_speed_ft": 40},
        "duration": {"until": "while_wearing_ring_of_swimming"},
        "stacking_policy": "replace",
    }
    ring_of_water_walking = compendium.action("srd.ring_of_water_walking_water_walk")
    assert compendium.items["srd.ring_of_water_walking"].actions == [
        "srd.ring_of_water_walking_water_walk"
    ]
    assert compendium.items["srd.ring_of_water_walking"].properties == {
        "rarity": "uncommon",
        "requires_attunement": False,
        "worn_slot": "ring",
        "spell_definition_id": "srd.spell.water_walk",
    }
    assert ring_of_water_walking.action_economy == "action"
    assert ring_of_water_walking.target_policy == {
        "min": 1,
        "max": 1,
        "self": True,
        "harmful": False,
    }
    assert ring_of_water_walking.requirements == {"item": "srd.ring_of_water_walking"}
    assert ring_of_water_walking.properties == {
        "ring_of_water_walking": True,
        "spell_definition_id": "srd.spell.water_walk",
        "self_only": True,
        "requires_attunement": False,
        "worn_slot": "ring",
    }
    assert ring_of_water_walking.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {"walk_on_liquid_surface": True},
        "duration": {"until": "duration_1_hour"},
        "tick_on": "movement",
        "stacking_policy": "replace",
    }
    ring_of_xray_vision = compendium.action("srd.use_ring_of_xray_vision")
    assert compendium.items["srd.ring_of_xray_vision"].actions == ["srd.use_ring_of_xray_vision"]
    assert compendium.items["srd.ring_of_xray_vision"].properties == {
        "rarity": "rare",
        "requires_attunement": True,
        "worn_slot": "ring",
    }
    assert ring_of_xray_vision.action_economy == "action"
    assert ring_of_xray_vision.target_policy == {
        "min": 1,
        "max": 1,
        "self": True,
        "harmful": False,
    }
    assert ring_of_xray_vision.requirements == {"item": "srd.ring_of_xray_vision"}
    assert ring_of_xray_vision.properties == {
        "ring_of_xray_vision": True,
        "self_only": True,
        "magic_action": True,
        "requires_attunement": True,
        "worn_slot": "ring",
    }
    assert ring_of_xray_vision.automation[1] == {
        "type": "repeat_use_save_before_long_rest",
        "marker": "ring_of_xray_vision_used_before_long_rest",
        "ability": "con",
        "dc_ref": "srd.ring_of_xray_vision.con_save",
        "dc_table": {"srd.ring_of_xray_vision.con_save": 15},
        "failure_condition": "exhaustion",
    }
    assert ring_of_xray_vision.automation[2] == {
        "type": "passive_effect",
        "passive_modifiers": {
            "xray_vision_range_ft": 30,
            "xray_vision_solid_objects_transparent": True,
            "xray_vision_penetration": {
                "stone_ft": 1,
                "common_metal_in": 1,
                "wood_or_dirt_ft": 3,
            },
            "xray_vision_blocked_by_lead": True,
        },
        "duration": {"until": "duration_1_minute"},
        "tick_on": "self_turn_start",
        "stacking_policy": "replace",
    }
    giant_strength_variants = {
        "hill": (21, "uncommon"),
        "frost": (23, "rare"),
        "stone": (23, "rare"),
        "fire": (25, "rare"),
        "cloud": (27, "very_rare"),
        "storm": (29, "legendary"),
    }
    for giant_type, (score, rarity) in giant_strength_variants.items():
        item_id = f"srd.potion_of_{giant_type}_giant_strength"
        action_id = f"srd.use_potion_of_{giant_type}_giant_strength"
        item = compendium.items[item_id]
        action = compendium.action(action_id)
        assert item.actions == [action_id]
        assert item.properties == {
            "giant_type": giant_type,
            "strength_score": score,
            "rarity": rarity,
        }
        assert action.action_economy == "bonus_action"
        assert action.requirements == {"item": item_id}
        assert action.cost.items == {item_id: 1}
        assert action.properties == {
            "giant_type": giant_type,
            "strength_score": score,
            "rarity": rarity,
        }
        assert action.automation[1] == {
            "type": "passive_effect",
            "passive_modifiers": {
                "ability_score_set": {"str": score},
                "giant_strength_type": giant_type,
            },
            "duration": {"until": "duration_1_hour"},
            "tick_on": "self_turn_start",
        }
    potion_of_resistance = compendium.action("srd.use_potion_of_resistance")
    assert potion_of_resistance.action_economy == "bonus_action"
    assert potion_of_resistance.properties["allowed_damage_types"] == [
        "acid",
        "cold",
        "fire",
        "force",
        "lightning",
        "necrotic",
        "poison",
        "psychic",
        "radiant",
        "thunder",
    ]
    assert potion_of_resistance.automation[1] == {
        "type": "passive_effect",
        "passive_modifiers": {"damage_resistances": {"param": "damage_type"}},
        "duration": {"until": "duration_1_hour"},
        "tick_on": "self_turn_start",
    }
    assert compendium.action("srd.shortsword_attack").properties["weapon_properties"] == [
        "finesse",
        "light",
    ]
    assert compendium.aliases.resolve("短剑") == ("srd.shortsword_attack",)
    assert compendium.aliases.resolve("长剑") == ("srd.longsword_attack",)
    assert "srd.falling_30ft" in compendium.hazards
    assert compendium.hazards["srd.burning"].automation[1] == {
        "type": "damage",
        "dice": "1d4",
        "damage_type": "fire",
    }
    assert compendium.hazards["srd.burning_oil"].automation[1] == {
        "type": "damage",
        "amount": 5,
        "damage_type": "fire",
    }
    assert compendium.hazards["srd.falling_10ft"].automation[2]["condition"] == "prone"
    strong_wind = compendium.hazards["srd.strong_wind"].automation
    assert strong_wind[1]["type"] == "passive_effect"
    assert strong_wind[1]["passive_modifiers"]["ranged_weapon_attack_disadvantage"] is True
    assert "prone" not in str(strong_wind)
    assert "srd.malnutrition" in compendium.hazards
    assert "srd.starvation" not in compendium.hazards
    assert "blinded" in compendium.conditions
    assert "exhaustion" in compendium.conditions
    assert "fighter" in compendium.classes
    assert "srd.bardic_inspiration" in compendium.classes["bard"].levels["1"]["actions"]
    assert "srd.bard_expertise" not in compendium.classes["bard"].levels["1"]["actions"]
    assert "srd.bard_expertise" in compendium.classes["bard"].levels["2"]["actions"]
    assert "srd.bard_expertise" in compendium.classes["bard"].levels["5"]["actions"]
    assert compendium.classes["bard"].levels["8"]["features"] == ["Ability Score Improvement"]
    assert compendium.classes["bard"].levels["9"]["features"] == ["Expertise"]
    assert "srd.bard_expertise" in compendium.classes["bard"].levels["9"]["actions"]
    assert "Bard level 9" in compendium.action("srd.bard_expertise").source
    assert "srd.jack_of_all_trades" not in compendium.classes["bard"].levels["1"]["actions"]
    assert "srd.jack_of_all_trades" in compendium.classes["bard"].levels["2"]["actions"]
    assert "srd.jack_of_all_trades" in compendium.classes["bard"].levels["5"]["actions"]
    assert {
        "srd.font_of_inspiration_restore_bardic_inspiration_slot_1",
        "srd.font_of_inspiration_restore_bardic_inspiration_slot_2",
        "srd.font_of_inspiration_restore_bardic_inspiration_slot_3",
    } <= set(compendium.classes["bard"].levels["5"]["actions"])
    assert compendium.classes["bard"].levels["10"]["features"] == ["Magical Secrets"]
    assert compendium.classes["bard"].levels["17"]["features"] == []
    assert "srd.superior_inspiration" not in compendium.classes["bard"].levels["17"]["actions"]
    assert compendium.classes["bard"].levels["18"]["features"] == ["Superior Inspiration"]
    assert "srd.superior_inspiration" in compendium.classes["bard"].levels["18"]["actions"]
    superior_inspiration = compendium.action("srd.superior_inspiration")
    assert superior_inspiration.action_economy == "none"
    assert superior_inspiration.requirements == {"class": "bard", "class_level_min": 18}
    assert superior_inspiration.properties == {
        "trigger": "roll_initiative",
        "resource": "srd.resource.bardic_inspiration",
        "restore_until_at_least": 2,
    }
    assert compendium.action("srd.divine_order").requirements == {
        "class": "cleric",
        "class_level_min": 1,
    }
    assert compendium.action("srd.divine_order").action_economy == "none"
    assert "Protector" in compendium.action("srd.divine_order").automation[0]["text"]
    assert "Thaumaturge" in compendium.action("srd.divine_order").automation[0]["text"]
    assert "srd.divine_order" in compendium.classes["cleric"].levels["1"]["actions"]
    assert "srd.divine_order" in compendium.classes["cleric"].levels["5"]["actions"]
    blessed_strikes = compendium.action("srd.blessed_strikes")
    assert blessed_strikes.requirements == {
        "class": "cleric",
        "class_level_min": 7,
    }
    assert blessed_strikes.action_economy == "none"
    assert blessed_strikes.properties == {
        "choice_key": "cleric.blessed_strikes",
        "options": [
            "srd.blessed_strikes_divine_strike",
            "srd.blessed_strikes_potent_spellcasting",
        ],
    }
    divine_strike = compendium.action("srd.blessed_strikes_divine_strike")
    assert divine_strike.properties == {
        "choice_key": "cleric.blessed_strikes",
        "choice_value": "divine_strike",
        "extra_damage": "1d8",
        "damage_types": ["necrotic", "radiant"],
        "selection_param": "divine_strike_damage_type",
        "applies_to": ["weapon_attack_hit"],
        "once_per_turn": True,
    }
    potent_spellcasting = compendium.action("srd.blessed_strikes_potent_spellcasting")
    assert potent_spellcasting.properties == {
        "choice_key": "cleric.blessed_strikes",
        "choice_value": "potent_spellcasting",
        "damage_bonus": "wisdom_modifier",
        "applies_to": ["cleric_cantrip_damage"],
    }
    improved_blessed_strikes = compendium.action("srd.improved_blessed_strikes")
    assert improved_blessed_strikes.requirements == {
        "class": "cleric",
        "class_level_min": 14,
    }
    assert improved_blessed_strikes.action_economy == "none"
    assert improved_blessed_strikes.properties == {
        "choice_key": "cleric.blessed_strikes",
        "improves": "srd.blessed_strikes",
        "divine_strike_extra_damage": "2d8",
        "potent_spellcasting_temp_hp": "2 * wisdom_modifier",
        "potent_spellcasting_temp_hp_range_ft": 60,
        "applies_to": [
            "blessed_strikes_divine_strike",
            "blessed_strikes_potent_spellcasting",
        ],
    }
    assert {
        "srd.divine_spark_heal",
        "srd.divine_spark_radiant",
        "srd.divine_spark_necrotic",
        "srd.turn_undead",
    } <= set(compendium.classes["cleric"].levels["2"]["actions"])
    assert "srd.disciple_of_life" not in compendium.classes["cleric"].levels["3"]["actions"]
    assert "srd.preserve_life" not in compendium.classes["cleric"].levels["3"]["actions"]
    assert compendium.classes["cleric"].levels["5"]["features"] == ["Sear Undead"]
    assert compendium.classes["cleric"].levels["6"]["features"] == ["Subclass Feature"]
    assert "srd.blessed_strikes" not in compendium.classes["cleric"].levels["6"]["actions"]
    assert compendium.classes["cleric"].levels["7"]["features"] == ["Blessed Strikes"]
    assert "srd.blessed_strikes" in compendium.classes["cleric"].levels["7"]["actions"]
    assert "srd.improved_blessed_strikes" not in compendium.classes["cleric"].levels["13"][
        "actions"
    ]
    assert compendium.classes["cleric"].levels["14"]["features"] == [
        "Improved Blessed Strikes"
    ]
    assert "srd.improved_blessed_strikes" in compendium.classes["cleric"].levels["14"][
        "actions"
    ]
    assert compendium.classes["cleric"].levels["17"]["features"] == ["Subclass Feature"]
    assert "srd.blessed_healer" in compendium.classes["cleric"].levels["6"]["actions"]
    assert "srd.supreme_healing" not in compendium.classes["cleric"].levels["16"]["actions"]
    assert "srd.supreme_healing" in compendium.classes["cleric"].levels["17"]["actions"]
    assert {
        "srd.druidic",
        "srd.primal_order",
        "srd.speak_with_animals",
        "srd.wild_shape_wolf",
        "srd.wild_shape_giant_rat",
        "srd.wild_companion_wild_shape",
        "srd.wild_companion_spell_slot",
    } <= set(compendium.classes["druid"].levels["2"]["actions"])
    assert compendium.classes["druid"].levels["1"]["features"] == [
        "Spellcasting",
        "Druidic",
        "Primal Order",
    ]
    assert compendium.action("srd.druidic").requirements == {
        "class": "druid",
        "class_level_min": 1,
    }
    assert compendium.action("srd.druidic").action_economy == "none"
    assert "Speak with Animals" in compendium.action("srd.druidic").automation[0]["text"]
    assert "srd.druidic" in compendium.classes["druid"].levels["1"]["actions"]
    assert "srd.speak_with_animals" in compendium.classes["druid"].levels["1"]["actions"]
    assert "srd.druidic" in compendium.classes["druid"].levels["5"]["actions"]
    assert "srd.speak_with_animals" in compendium.classes["druid"].levels["5"]["actions"]
    assert compendium.action("srd.primal_order").requirements == {
        "class": "druid",
        "class_level_min": 1,
    }
    assert compendium.action("srd.primal_order").action_economy == "none"
    assert "Magician" in compendium.action("srd.primal_order").automation[0]["text"]
    assert "Warden" in compendium.action("srd.primal_order").automation[0]["text"]
    assert "srd.primal_order" in compendium.classes["druid"].levels["1"]["actions"]
    assert "srd.primal_order" in compendium.classes["druid"].levels["5"]["actions"]
    assert compendium.classes["druid"].levels["3"]["features"] == ["Druid Subclass"]
    assert compendium.classes["druid"].subclasses["land"] == {
        "name": "Circle of the Land",
        "level": 3,
        "features": [
            "Circle of the Land Spells",
            "Land's Aid",
            "Natural Recovery",
            "Nature's Ward",
            "Nature's Sanctuary",
        ],
        "actions": [
            "srd.lands_aid",
            "srd.natural_recovery",
            "srd.natures_ward",
            "srd.natures_sanctuary",
            "srd.natures_sanctuary_move",
        ],
    }
    assert compendium.classes["druid"].levels["5"]["features"] == ["Wild Resurgence"]
    assert {
        "srd.wild_resurgence_restore_wild_shape_slot_1",
        "srd.wild_resurgence_restore_wild_shape_slot_2",
        "srd.wild_resurgence_restore_wild_shape_slot_3",
        "srd.wild_resurgence_create_spell_slot",
    } <= set(compendium.classes["druid"].levels["5"]["actions"])
    natural_recovery = compendium.action("srd.natural_recovery")
    assert natural_recovery.requirements == {
        "class": "druid",
        "class_level_min": 6,
        "subclass": "land",
    }
    assert natural_recovery.action_economy == "none"
    assert natural_recovery.properties["free_circle_spell"] == {
        "minimum_spell_level": 1,
        "requires_prepared_from_circle_spells": True,
        "without_expending_spell_slot": True,
        "resource": "srd.resource.natural_recovery_circle_spell",
        "recharge": "long_rest",
    }
    assert natural_recovery.properties["short_rest_spell_slot_recovery"] == {
        "combined_level_cap_from": {"half_class_level_round_up": "druid"},
        "maximum_slot_level": 5,
        "resource": "srd.resource.natural_recovery_spell_slots",
        "recharge": "long_rest",
    }
    assert compendium.classes["druid"].levels["6"]["features"] == ["Subclass Feature"]
    assert "srd.natural_recovery" in compendium.classes["druid"].levels["6"]["actions"]
    natures_ward = compendium.action("srd.natures_ward")
    assert natures_ward.requirements == {
        "class": "druid",
        "class_level_min": 10,
        "subclass": "land",
    }
    assert natures_ward.action_economy == "none"
    assert natures_ward.properties == {
        "condition_immunities": ["poisoned"],
        "land_choice_feature": "druid.land.current_land",
        "resistance_by_land": {
            "arid": "fire",
            "polar": "cold",
            "temperate": "lightning",
            "tropical": "poison",
        },
    }
    assert compendium.classes["druid"].levels["10"]["features"] == ["Subclass Feature"]
    assert "srd.natures_ward" in compendium.classes["druid"].levels["10"]["actions"]
    natures_sanctuary = compendium.action("srd.natures_sanctuary")
    assert natures_sanctuary.requirements == {
        "class": "druid",
        "class_level_min": 14,
        "subclass": "land",
    }
    assert natures_sanctuary.action_economy == "action"
    assert natures_sanctuary.cost.resources == {"srd.resource.wild_shape": 1}
    assert natures_sanctuary.properties == {
        "magic_action": True,
        "natures_sanctuary": True,
        "destination_param": "natures_sanctuary_position_node_id",
    }
    assert natures_sanctuary.automation[0] == {
        "type": "natures_sanctuary",
        "destination_param": "natures_sanctuary_position_node_id",
    }
    natures_sanctuary_move = compendium.action("srd.natures_sanctuary_move")
    assert natures_sanctuary_move.requirements == {
        "class": "druid",
        "class_level_min": 14,
        "subclass": "land",
    }
    assert natures_sanctuary_move.action_economy == "bonus_action"
    assert natures_sanctuary_move.cost.resources == {}
    assert natures_sanctuary_move.properties == {
        "natures_sanctuary_move": True,
        "destination_param": "natures_sanctuary_position_node_id",
    }
    assert natures_sanctuary_move.automation[0] == {
        "type": "natures_sanctuary_move",
        "destination_param": "natures_sanctuary_position_node_id",
    }
    assert compendium.classes["druid"].levels["14"]["features"] == ["Subclass Feature"]
    assert {
        "srd.natures_sanctuary",
        "srd.natures_sanctuary_move",
    } <= set(compendium.classes["druid"].levels["14"]["actions"])
    assert compendium.classes["sorcerer"].levels["1"]["features"] == [
        "Spellcasting",
        "Innate Sorcery",
    ]
    assert "srd.innate_sorcery" in compendium.classes["sorcerer"].levels["1"]["actions"]
    assert {
        "srd.font_of_magic_convert_slot_1",
        "srd.font_of_magic_create_slot_1",
    } <= set(compendium.classes["sorcerer"].levels["2"]["actions"])
    assert {
        "srd.font_of_magic_convert_slot_3",
        "srd.font_of_magic_create_slot_3",
    } <= set(compendium.classes["sorcerer"].levels["5"]["actions"])
    assert compendium.classes["sorcerer"].levels["2"]["features"] == [
        "Font of Magic",
        "Metamagic",
    ]
    assert compendium.classes["sorcerer"].levels["5"]["features"] == ["Sorcerous Restoration"]
    assert compendium.classes["sorcerer"].levels["6"]["features"] == ["Subclass Feature"]
    assert "srd.sorcerous_restoration" not in compendium.classes["sorcerer"].levels["4"]["actions"]
    assert "srd.sorcerous_restoration" in compendium.classes["sorcerer"].levels["5"]["actions"]
    assert "srd.elemental_affinity" in compendium.classes["sorcerer"].levels["6"]["actions"]
    assert compendium.classes["sorcerer"].subclasses["draconic"]["name"] == "Draconic Sorcery"
    assert compendium.action("srd.draconic_resilience").requirements == {
        "class": "sorcerer",
        "class_level_min": 3,
        "subclass": "draconic",
    }
    assert compendium.action("srd.elemental_affinity").requirements == {
        "class": "sorcerer",
        "class_level_min": 6,
        "subclass": "draconic",
    }
    assert compendium.classes["sorcerer"].subclasses["draconic"]["features"] == [
        "Draconic Resilience",
        "Elemental Affinity",
    ]
    assert compendium.classes["sorcerer"].subclasses["draconic"]["actions"] == [
        "srd.draconic_resilience",
        "srd.elemental_affinity",
    ]
    assert "srd.draconic_resilience" not in compendium.classes["sorcerer"].levels["3"]["actions"]
    assert "srd.second_wind" in compendium.classes["fighter"].levels["1"]["actions"]
    assert compendium.classes["fighter"].levels["1"]["features"] == [
        "Fighting Style",
        "Second Wind",
        "Weapon Mastery",
    ]
    assert "srd.action_surge" in compendium.classes["fighter"].levels["2"]["actions"]
    assert "srd.tactical_mind" in compendium.classes["fighter"].levels["2"]["actions"]
    assert "srd.tactical_mind" in compendium.classes["fighter"].levels["5"]["actions"]
    assert compendium.classes["fighter"].levels["2"]["features"] == [
        "Action Surge",
        "Tactical Mind",
    ]
    assert compendium.classes["fighter"].levels["3"]["features"] == ["Fighter Subclass"]
    assert "srd.improved_critical" not in compendium.classes["fighter"].levels["3"]["actions"]
    assert compendium.classes["fighter"].subclasses["champion"]["features"] == [
        "Improved Critical",
        "Remarkable Athlete",
        "Additional Fighting Style",
        "Heroic Warrior",
        "Superior Critical",
        "Survivor",
    ]
    assert compendium.classes["fighter"].subclasses["champion"]["actions"] == [
        "srd.improved_critical",
        "srd.remarkable_athlete",
        "srd.additional_fighting_style",
        "srd.heroic_warrior",
        "srd.superior_critical",
        "srd.survivor",
    ]
    assert compendium.classes["fighter"].levels["5"]["features"] == [
        "Extra Attack",
        "Tactical Shift",
    ]
    assert compendium.classes["fighter"].levels["7"]["features"] == ["Subclass Feature"]
    assert "srd.additional_fighting_style" in compendium.classes["fighter"].levels["7"]["actions"]
    indomitable = compendium.action("srd.indomitable")
    assert indomitable.requirements == {"class": "fighter", "class_level_min": 9}
    assert indomitable.action_economy == "none"
    assert indomitable.properties == {
        "saving_throw_reroll": True,
        "resource": "srd.resource.indomitable",
        "reroll_bonus": {"class_level": "fighter"},
        "recharge": "long_rest",
        "uses_by_fighter_level": {"9": 1, "13": 2, "17": 3},
    }
    assert compendium.classes["fighter"].levels["9"]["features"] == [
        "Indomitable",
        "Tactical Master",
    ]
    assert "srd.indomitable" in compendium.classes["fighter"].levels["9"]["actions"]
    assert "srd.tactical_master" in compendium.classes["fighter"].levels["9"]["actions"]
    heroic_warrior = compendium.action("srd.heroic_warrior")
    assert heroic_warrior.properties == {
        "grants_heroic_inspiration": True,
        "resource": "srd.resource.heroic_inspiration",
        "trigger": "self_turn_start",
        "requires_combat": True,
        "requires_without_resource": True,
        "maximum_instances": 1,
    }
    assert compendium.classes["fighter"].levels["10"]["features"] == ["Subclass Feature"]
    assert "srd.heroic_warrior" in compendium.classes["fighter"].levels["10"]["actions"]
    assert compendium.classes["fighter"].levels["11"]["features"] == ["Two Extra Attacks"]
    assert "srd.two_extra_attacks" in compendium.classes["fighter"].levels["11"]["actions"]
    assert compendium.classes["fighter"].levels["13"]["features"] == [
        "Indomitable (Two Uses)",
        "Studied Attacks",
    ]
    assert "srd.studied_attacks" in compendium.classes["fighter"].levels["13"]["actions"]
    assert compendium.classes["fighter"].levels["15"]["features"] == ["Subclass Feature"]
    assert "srd.superior_critical" in compendium.classes["fighter"].levels["15"]["actions"]
    assert compendium.classes["fighter"].levels["17"]["features"] == [
        "Action Surge (Two Uses)",
        "Indomitable (Three Uses)",
    ]
    assert "srd.action_surge" in compendium.classes["fighter"].levels["17"]["actions"]
    assert "srd.indomitable" in compendium.classes["fighter"].levels["17"]["actions"]
    survivor = compendium.action("srd.survivor")
    assert survivor.requirements == {
        "class": "fighter",
        "class_level_min": 18,
        "subclass": "champion",
    }
    assert survivor.properties == {
        "death_saves_advantage": True,
        "death_save_roll_18_to_20_counts_as_20": True,
        "heroic_rally": {
            "trigger": "self_turn_start",
            "healing": "5 + constitution_modifier",
            "requires_bloodied": True,
            "requires_hp_minimum": 1,
        },
    }
    assert compendium.classes["fighter"].levels["18"]["features"] == ["Subclass Feature"]
    assert "srd.survivor" in compendium.classes["fighter"].levels["18"]["actions"]
    assert compendium.classes["fighter"].levels["20"]["features"] == ["Three Extra Attacks"]
    assert "srd.three_extra_attacks" in compendium.classes["fighter"].levels["20"]["actions"]
    assert "srd.rage" in compendium.classes["barbarian"].levels["1"]["actions"]
    assert compendium.classes["barbarian"].levels["1"]["features"] == [
        "Rage",
        "Unarmored Defense",
        "Weapon Mastery",
    ]
    assert (
        "srd.barbarian_unarmored_defense" in compendium.classes["barbarian"].levels["1"]["actions"]
    )
    assert "srd.danger_sense" not in compendium.classes["barbarian"].levels["1"]["actions"]
    assert "srd.danger_sense" in compendium.classes["barbarian"].levels["2"]["actions"]
    assert "srd.danger_sense" in compendium.classes["barbarian"].levels["5"]["actions"]
    assert "srd.primal_knowledge" not in compendium.classes["barbarian"].levels["2"]["actions"]
    assert "srd.primal_knowledge" in compendium.classes["barbarian"].levels["3"]["actions"]
    assert "srd.primal_knowledge" in compendium.classes["barbarian"].levels["5"]["actions"]
    assert "srd.reckless_attack" in compendium.classes["barbarian"].levels["2"]["actions"]
    assert compendium.classes["barbarian"].levels["3"]["features"] == [
        "Barbarian Subclass",
        "Primal Knowledge",
    ]
    assert compendium.classes["barbarian"].levels["6"]["features"] == ["Subclass Feature"]
    assert "srd.mindless_rage" in compendium.classes["barbarian"].levels["6"]["actions"]
    assert compendium.action("srd.frenzy").requirements == {
        "class": "barbarian",
        "class_level_min": 3,
        "subclass": "berserker",
    }
    assert compendium.classes["barbarian"].subclasses["berserker"]["features"] == [
        "Frenzy",
        "Mindless Rage",
    ]
    assert compendium.classes["barbarian"].subclasses["berserker"]["actions"] == [
        "srd.frenzy",
        "srd.mindless_rage",
    ]
    assert "srd.frenzy" not in compendium.classes["barbarian"].levels["3"]["actions"]
    assert compendium.classes["barbarian"].levels["7"]["features"] == [
        "Feral Instinct",
        "Instinctive Pounce",
    ]
    assert "srd.feral_instinct" in compendium.classes["barbarian"].levels["7"]["actions"]
    assert "srd.instinctive_pounce" in compendium.classes["barbarian"].levels["7"]["actions"]
    feral_instinct = compendium.action("srd.feral_instinct")
    assert feral_instinct.requirements == {"class": "barbarian", "class_level_min": 7}
    assert feral_instinct.properties == {"initiative_advantage": True}
    instinctive_pounce = compendium.action("srd.instinctive_pounce")
    assert instinctive_pounce.requirements == {"class": "barbarian", "class_level_min": 7}
    assert instinctive_pounce.properties == {
        "rage_bonus_action_move": True,
        "movement_limit": "half_speed",
        "destination_param": "instinctive_pounce_to_position_node_id",
        "triggers_opportunity_attacks": True,
    }
    assert compendium.classes["barbarian"].levels["9"]["features"] == ["Brutal Strike"]
    assert "srd.brutal_strike" in compendium.classes["barbarian"].levels["9"]["actions"]
    brutal_strike = compendium.action("srd.brutal_strike")
    assert brutal_strike.requirements == {"class": "barbarian", "class_level_min": 9}
    assert brutal_strike.properties == {
        "requires_reckless_attack": True,
        "requires_strength_attack": True,
        "forgoes_advantage": True,
        "extra_damage": "1d10",
        "damage_type": "same_as_attack",
        "effects": {
            "forceful_blow": {
                "push_ft": 15,
                "follow_move_limit": "half_speed",
                "follow_move_opportunity_attacks": False,
            },
            "hamstring_blow": {
                "speed_penalty_ft": 15,
                "duration": "start_of_next_turn",
            },
            "staggering_blow": {
                "requires_barbarian_level_min": 13,
                "next_saving_throw_disadvantage": True,
                "cannot_make_opportunity_attacks_duration": "start_of_next_turn",
            },
            "sundering_blow": {
                "requires_barbarian_level_min": 13,
                "next_attack_roll_by_another_creature_bonus": 5,
                "duration": "start_of_next_turn",
                "one_sundering_blow_bonus_per_attack_roll": True,
            },
        },
    }
    assert compendium.classes["barbarian"].levels["11"]["features"] == ["Relentless Rage"]
    assert "srd.relentless_rage" in compendium.classes["barbarian"].levels["11"]["actions"]
    relentless_rage = compendium.action("srd.relentless_rage")
    assert relentless_rage.requirements == {"class": "barbarian", "class_level_min": 11}
    assert relentless_rage.action_economy == "none"
    assert relentless_rage.properties == {
        "trigger": "drop_to_0_hp_while_rage_active_and_not_die_outright",
        "saving_throw": {"ability": "con", "initial_dc": 10},
        "dc_increase_after_each_use": 5,
        "dc_resets_on": ["short_rest", "long_rest"],
        "success_hp_formula": "2 * barbarian_level",
        "no_use_limit": True,
    }
    assert compendium.classes["barbarian"].levels["13"]["features"] == ["Improved Brutal Strike"]
    assert "srd.brutal_strike" in compendium.classes["barbarian"].levels["13"]["actions"]
    assert "srd.relentless_rage" in compendium.classes["barbarian"].levels["13"]["actions"]
    assert "srd.improved_brutal_strike" in compendium.classes["barbarian"].levels["13"]["actions"]
    improved_brutal_strike = compendium.action("srd.improved_brutal_strike")
    assert improved_brutal_strike.requirements == {
        "class": "barbarian",
        "class_level_min": 13,
    }
    assert improved_brutal_strike.action_economy == "none"
    assert improved_brutal_strike.properties == {
        "adds_brutal_strike_options": ["staggering_blow", "sundering_blow"],
        "level_13_extra_damage": "1d10",
        "level_13_max_effects_per_brutal_strike": 1,
        "level_17_extra_damage": "2d10",
        "level_17_max_effects_per_brutal_strike": 2,
        "level_17_requires_different_effects": True,
    }
    assert compendium.classes["barbarian"].levels["14"]["features"] == ["Subclass Feature"]
    assert "srd.persistent_rage" not in compendium.classes["barbarian"].levels["14"]["actions"]
    assert compendium.classes["barbarian"].levels["15"]["features"] == ["Persistent Rage"]
    assert "srd.persistent_rage" in compendium.classes["barbarian"].levels["15"]["actions"]
    persistent_rage = compendium.action("srd.persistent_rage")
    assert persistent_rage.requirements == {"class": "barbarian", "class_level_min": 15}
    assert persistent_rage.action_economy == "none"
    assert persistent_rage.properties == {
        "trigger": "roll_initiative",
        "initiative_restore_expended_rage_uses": True,
        "initiative_restore_resource": "srd.resource.persistent_rage_initiative_restore",
        "initiative_restore_resets_on": "long_rest",
        "rage_duration": "duration_10_minutes",
        "rage_no_round_to_round_extension_required": True,
        "rage_ends_early_on_conditions": ["unconscious"],
        "rage_ends_early_on_heavy_armor": True,
    }
    assert compendium.classes["barbarian"].levels["16"]["features"] == ["Ability Score Improvement"]
    assert "srd.persistent_rage" in compendium.classes["barbarian"].levels["16"]["actions"]
    assert compendium.classes["barbarian"].levels["17"]["features"] == ["Improved Brutal Strike"]
    assert "srd.improved_brutal_strike" in compendium.classes["barbarian"].levels["17"]["actions"]
    assert "srd.indomitable_might" not in compendium.classes["barbarian"].levels["17"]["actions"]
    assert compendium.classes["barbarian"].levels["18"]["features"] == ["Indomitable Might"]
    assert "srd.indomitable_might" in compendium.classes["barbarian"].levels["18"]["actions"]
    indomitable_might = compendium.action("srd.indomitable_might")
    assert indomitable_might.requirements == {"class": "barbarian", "class_level_min": 18}
    assert indomitable_might.action_economy == "none"
    assert indomitable_might.properties == {
        "affected_tests": ["strength_check", "strength_saving_throw"],
        "use_strength_score_when_total_below_score": True,
    }
    assert compendium.classes["barbarian"].levels["19"]["features"] == ["Epic Boon"]
    assert "srd.primal_champion" not in compendium.classes["barbarian"].levels["19"]["actions"]
    assert compendium.classes["barbarian"].levels["20"]["features"] == ["Primal Champion"]
    assert "srd.primal_champion" in compendium.classes["barbarian"].levels["20"]["actions"]
    primal_champion = compendium.action("srd.primal_champion")
    assert primal_champion.requirements == {"class": "barbarian", "class_level_min": 20}
    assert primal_champion.action_economy == "none"
    assert primal_champion.properties == {
        "ability_score_increase": {"str": 4, "con": 4},
        "ability_score_maximum": {"str": 25, "con": 25},
    }
    assert compendium.classes["bard"].levels["3"]["features"] == ["Bard Subclass"]
    assert compendium.classes["bard"].subclasses["lore"] == {
        "name": "College of Lore",
        "level": 3,
        "features": ["Bonus Proficiencies", "Cutting Words"],
        "actions": ["srd.cutting_words"],
    }
    assert "srd.cutting_words" not in compendium.classes["bard"].levels["3"]["actions"]
    assert compendium.classes["cleric"].levels["1"]["features"] == [
        "Spellcasting",
        "Divine Order",
    ]
    assert compendium.classes["cleric"].levels["3"]["features"] == ["Cleric Subclass"]
    assert compendium.classes["cleric"].subclasses["life"]["features"] == [
        "Disciple of Life",
        "Preserve Life",
        "Blessed Healer",
        "Supreme Healing",
    ]
    assert compendium.classes["cleric"].subclasses["life"]["actions"] == [
        "srd.disciple_of_life",
        "srd.preserve_life",
        "srd.blessed_healer",
        "srd.supreme_healing",
    ]
    assert compendium.classes["paladin"].levels["1"]["features"] == [
        "Lay On Hands",
        "Spellcasting",
        "Weapon Mastery",
    ]
    assert "srd.lay_on_hands" in compendium.classes["paladin"].levels["1"]["actions"]
    assert (
        "srd.lay_on_hands_remove_poisoned" in compendium.classes["paladin"].levels["1"]["actions"]
    )
    assert "srd.cure_wounds" in compendium.classes["paladin"].levels["1"]["actions"]
    assert compendium.classes["paladin"].levels["2"]["features"] == [
        "Fighting Style",
        "Paladin's Smite",
    ]
    assert "srd.divine_smite" in compendium.classes["paladin"].levels["2"]["actions"]
    assert "srd.paladins_smite_divine_smite" in compendium.classes["paladin"].levels["2"]["actions"]
    assert compendium.classes["paladin"].levels["3"]["features"] == [
        "Channel Divinity",
        "Paladin Subclass",
    ]
    assert "srd.divine_sense" in compendium.classes["paladin"].levels["3"]["actions"]
    assert compendium.action("srd.divine_sense").cost.resources == {
        "srd.resource.channel_divinity": 1
    }
    assert compendium.classes["paladin"].subclasses["devotion"] == {
        "name": "Oath of Devotion",
        "level": 3,
        "features": ["Oath of Devotion Spells", "Sacred Weapon", "Aura of Devotion"],
        "actions": ["srd.sacred_weapon", "srd.aura_of_devotion"],
    }
    assert "srd.sacred_weapon" not in compendium.classes["paladin"].levels["3"]["actions"]
    assert compendium.classes["paladin"].levels["5"]["features"] == [
        "Extra Attack",
        "Faithful Steed",
    ]
    assert {
        "srd.faithful_steed",
        "srd.find_steed",
        "srd.faithful_steed_find_steed",
    } <= set(compendium.classes["paladin"].levels["5"]["actions"])
    assert compendium.classes["paladin"].levels["6"]["features"] == ["Aura of Protection"]
    assert "srd.aura_of_protection" in compendium.classes["paladin"].levels["6"]["actions"]
    assert compendium.classes["paladin"].levels["7"]["features"] == ["Subclass Feature"]
    assert "srd.aura_of_devotion" not in compendium.classes["paladin"].levels["7"]["actions"]
    assert compendium.classes["paladin"].levels["10"]["features"] == ["Aura of Courage"]
    assert "srd.aura_of_courage" in compendium.classes["paladin"].levels["10"]["actions"]
    assert compendium.classes["paladin"].levels["11"]["features"] == ["Radiant Strikes"]
    assert "srd.radiant_strikes" in compendium.classes["paladin"].levels["11"]["actions"]
    radiant_strikes = compendium.action("srd.radiant_strikes")
    assert radiant_strikes.requirements == {"class": "paladin", "class_level_min": 11}
    assert radiant_strikes.properties == {
        "extra_damage": "1d8",
        "damage_type": "radiant",
        "applies_to": ["melee_weapon_attack_hit", "unarmed_strike_hit"],
    }
    assert compendium.classes["paladin"].levels["14"]["features"] == ["Restoring Touch"]
    assert "srd.radiant_strikes" in compendium.classes["paladin"].levels["14"]["actions"]
    assert "srd.restoring_touch" in compendium.classes["paladin"].levels["14"]["actions"]
    assert compendium.classes["paladin"].levels["15"]["features"] == ["Subclass feature"]
    assert "srd.aura_expansion" not in compendium.classes["paladin"].levels["17"]["actions"]
    assert compendium.classes["paladin"].levels["18"]["features"] == ["Aura Expansion"]
    assert "srd.aura_expansion" in compendium.classes["paladin"].levels["18"]["actions"]
    aura_expansion = compendium.action("srd.aura_expansion")
    assert aura_expansion.action_economy == "none"
    assert aura_expansion.requirements == {"class": "paladin", "class_level_min": 18}
    assert aura_expansion.range == {"self": True, "shape": "emanation", "radius_ft": 30}
    assert aura_expansion.properties == {
        "aura_of_protection_radius_ft": 30,
        "replaces_aura_of_protection_radius_ft": 10,
    }
    assert {
        "srd.cunning_action_dash",
        "srd.cunning_action_disengage",
        "srd.cunning_action_hide",
    } <= set(compendium.classes["rogue"].levels["2"]["actions"])
    assert "srd.dash" not in compendium.classes["rogue"].levels["2"]["actions"]
    assert compendium.classes["rogue"].levels["3"]["features"] == [
        "Rogue Subclass",
        "Steady Aim",
    ]
    assert compendium.classes["rogue"].levels["1"]["features"] == [
        "Expertise",
        "Sneak Attack",
        "Thieves' Cant",
        "Weapon Mastery",
    ]
    assert compendium.action("srd.thieves_cant").requirements == {
        "class": "rogue",
        "class_level_min": 1,
    }
    assert compendium.action("srd.thieves_cant").action_economy == "none"
    assert "one other language" in compendium.action("srd.thieves_cant").automation[0]["text"]
    assert "srd.thieves_cant" in compendium.classes["rogue"].levels["1"]["actions"]
    assert "srd.thieves_cant" in compendium.classes["rogue"].levels["5"]["actions"]
    assert "srd.steady_aim" in compendium.classes["rogue"].levels["3"]["actions"]
    assert compendium.classes["rogue"].levels["6"]["features"] == ["Expertise"]
    assert "srd.rogue_expertise" in compendium.classes["rogue"].levels["6"]["actions"]
    assert compendium.classes["rogue"].levels["7"]["features"] == [
        "Evasion",
        "Reliable Talent",
    ]
    assert "srd.evasion" in compendium.classes["rogue"].levels["7"]["actions"]
    assert "srd.reliable_talent" in compendium.classes["rogue"].levels["7"]["actions"]
    assert compendium.classes["rogue"].levels["11"]["features"] == ["Improved Cunning Strike"]
    assert "srd.improved_cunning_strike" in compendium.classes["rogue"].levels["11"]["actions"]
    assert compendium.classes["rogue"].levels["15"]["features"] == ["Slippery Mind"]
    assert "srd.slippery_mind" in compendium.classes["rogue"].levels["15"]["actions"]
    assert compendium.classes["rogue"].levels["18"]["features"] == ["Elusive"]
    assert "srd.elusive" in compendium.classes["rogue"].levels["18"]["actions"]
    assert compendium.classes["rogue"].levels["20"]["features"] == ["Stroke of Luck"]
    assert "srd.stroke_of_luck" in compendium.classes["rogue"].levels["20"]["actions"]
    assert {
        "srd.cunning_strike",
        "srd.uncanny_dodge",
    } <= set(compendium.classes["rogue"].levels["5"]["actions"])
    assert {
        "srd.monk_unarmed_strike",
        "srd.martial_arts_bonus_unarmed_strike",
        "srd.monk_unarmored_defense",
    } <= set(compendium.classes["monk"].levels["1"]["actions"])
    assert compendium.action("srd.monk_unarmed_strike").automation[2]["dice_from"] == {
        "class_feature": "monk_martial_arts_die"
    }
    assert compendium.action("srd.martial_arts_bonus_unarmed_strike").automation[2][
        "dice_from"
    ] == {"class_feature": "monk_martial_arts_die"}
    assert compendium.action("srd.flurry_of_blows").automation[2]["dice_from"] == {
        "class_feature": "monk_martial_arts_die"
    }
    assert compendium.action("srd.flurry_of_blows").automation[5]["dice_from"] == {
        "class_feature": "monk_martial_arts_die"
    }
    assert compendium.action("srd.flurry_of_blows").target_policy["max"] == 3
    assert compendium.action("srd.flurry_of_blows").automation[6] == {
        "type": "branch",
        "condition": "actor_class_level_min",
        "class": "monk",
        "level": 10,
        "if_true": [
            {
                "type": "target",
                "mode": "param",
                "param": "strike_3_target",
                "fallback": "explicit_index",
                "fallback_index": 2,
            },
            {"type": "attack_roll", "ability": "dex"},
            {
                "type": "damage",
                "dice_from": {"class_feature": "monk_martial_arts_die"},
                "bonus_from": {"ability_modifier": "dex"},
                "damage_type": "bludgeoning",
                "ability": "dex",
                "requires_hit": True,
            },
        ],
    }
    assert compendium.classes["monk"].levels["2"]["features"] == [
        "Monk's Focus",
        "Unarmored Movement",
        "Uncanny Metabolism",
    ]
    assert compendium.classes["monk"].subclasses["open_hand"]["name"] == (
        "Warrior of the Open Hand"
    )
    assert compendium.classes["monk"].subclasses["open_hand"]["features"] == [
        "Open Hand Technique",
        "Wholeness of Body",
        "Fleet Step",
        "Quivering Palm",
    ]
    assert compendium.classes["monk"].subclasses["open_hand"]["actions"] == [
        "srd.open_hand_technique",
        "srd.wholeness_of_body",
        "srd.fleet_step",
        "srd.quivering_palm",
        "srd.quivering_palm_release",
    ]
    open_hand = compendium.action("srd.open_hand_technique")
    assert open_hand.requirements == {
        "class": "monk",
        "class_level_min": 3,
        "subclass": "open_hand",
    }
    assert open_hand.action_economy == "none"
    assert {
        "srd.flurry_of_blows",
        "srd.monk_unarmored_movement",
        "srd.patient_defense",
        "srd.patient_defense_focus",
        "srd.step_of_the_wind",
        "srd.step_of_the_wind_focus",
        "srd.uncanny_metabolism",
    } <= set(compendium.classes["monk"].levels["2"]["actions"])
    unarmored_movement = compendium.action("srd.monk_unarmored_movement")
    assert unarmored_movement.action_economy == "none"
    assert unarmored_movement.requirements == {"class": "monk", "class_level_min": 2}
    uncanny_metabolism = compendium.action("srd.uncanny_metabolism")
    assert uncanny_metabolism.action_economy == "none"
    assert uncanny_metabolism.requirements == {"class": "monk", "class_level_min": 2}
    assert "srd.deflect_attacks" not in compendium.classes["monk"].levels["2"]["actions"]
    assert "srd.deflect_attacks" in compendium.classes["monk"].levels["3"]["actions"]
    assert "srd.deflect_attacks" in compendium.classes["monk"].levels["4"]["actions"]
    assert "srd.deflect_attacks" in compendium.classes["monk"].levels["5"]["actions"]
    deflect_attacks = compendium.action("srd.deflect_attacks")
    assert deflect_attacks.action_economy == "reaction"
    assert deflect_attacks.requirements == {"class": "monk", "class_level_min": 3}
    assert "srd.slow_fall" in compendium.classes["monk"].levels["4"]["actions"]
    assert "srd.slow_fall" in compendium.classes["monk"].levels["5"]["actions"]
    slow_fall = compendium.action("srd.slow_fall")
    assert slow_fall.action_economy == "reaction"
    assert slow_fall.requirements == {"class": "monk", "class_level_min": 4}
    assert "srd.stunning_strike" in compendium.classes["monk"].levels["5"]["actions"]
    stunning_strike = compendium.action("srd.stunning_strike")
    assert stunning_strike.action_economy == "none"
    assert stunning_strike.requirements == {"class": "monk", "class_level_min": 5}
    assert compendium.classes["monk"].levels["6"]["features"] == [
        "Empowered Strikes",
        "Subclass Feature",
    ]
    assert {
        "srd.empowered_strikes",
        "srd.wholeness_of_body",
    } <= set(compendium.classes["monk"].levels["6"]["actions"])
    empowered_strikes = compendium.action("srd.empowered_strikes")
    assert empowered_strikes.action_economy == "none"
    assert empowered_strikes.requirements == {"class": "monk", "class_level_min": 6}
    wholeness = compendium.action("srd.wholeness_of_body")
    assert wholeness.action_economy == "bonus_action"
    assert wholeness.requirements == {
        "class": "monk",
        "class_level_min": 6,
        "subclass": "open_hand",
    }
    assert wholeness.automation[1]["minimum_amount"] == 1
    assert compendium.classes["monk"].levels["11"]["features"] == ["Subclass Feature"]
    assert "srd.fleet_step" in compendium.classes["monk"].levels["11"]["actions"]
    fleet_step = compendium.action("srd.fleet_step")
    assert fleet_step.action_economy == "none"
    assert fleet_step.requirements == {
        "class": "monk",
        "class_level_min": 11,
        "subclass": "open_hand",
    }
    assert fleet_step.properties == {
        "trigger": "bonus_action_other_than_step_of_the_wind",
        "allows_immediate_step_of_the_wind": True,
        "step_of_the_wind_actions": [
            "srd.step_of_the_wind",
            "srd.step_of_the_wind_focus",
        ],
        "does_not_waive_focus_cost": True,
    }
    assert compendium.classes["monk"].levels["7"]["features"] == ["Evasion"]
    assert "srd.evasion" in compendium.classes["monk"].levels["7"]["actions"]
    evasion = compendium.action("srd.evasion")
    assert evasion.action_economy == "none"
    assert evasion.requirements == {
        "class_any": ["monk", "rogue"],
        "class_any_level_min": 7,
    }
    assert evasion.properties == {
        "dexterity_save_half_damage": True,
        "success_damage": 0,
        "failure_damage": "half",
        "disabled_by_condition": "incapacitated",
    }
    assert compendium.classes["monk"].levels["8"]["features"] == ["Ability Score Improvement"]
    assert "srd.acrobatic_movement" not in compendium.classes["monk"].levels["8"]["actions"]
    assert compendium.classes["monk"].levels["9"]["features"] == ["Acrobatic Movement"]
    assert "srd.acrobatic_movement" in compendium.classes["monk"].levels["9"]["actions"]
    acrobatic_movement = compendium.action("srd.acrobatic_movement")
    assert acrobatic_movement.action_economy == "none"
    assert acrobatic_movement.requirements == {"class": "monk", "class_level_min": 9}
    assert acrobatic_movement.properties == {
        "requires_no_armor_or_shield": True,
        "turn_only": True,
        "during_movement_only": True,
        "can_move_along_vertical_surfaces": True,
        "can_move_across_liquids": True,
        "without_falling_during_movement": True,
        "does_not_grant_climb_speed": True,
        "does_not_grant_swim_speed": True,
        "does_not_allow_standing_on_liquids_after_movement": True,
    }
    assert compendium.classes["monk"].levels["10"]["features"] == [
        "Heightened Focus",
        "Self-Restoration",
    ]
    assert "srd.heightened_focus" in compendium.classes["monk"].levels["10"]["actions"]
    assert "srd.self_restoration" in compendium.classes["monk"].levels["10"]["actions"]
    heightened_focus = compendium.action("srd.heightened_focus")
    assert heightened_focus.action_economy == "none"
    assert heightened_focus.requirements == {"class": "monk", "class_level_min": 10}
    assert heightened_focus.properties == {
        "enhances_actions": [
            "srd.flurry_of_blows",
            "srd.patient_defense_focus",
            "srd.step_of_the_wind_focus",
        ],
        "flurry_of_blows_unarmed_strikes": 3,
        "patient_defense_focus_temp_hp_dice_count": 2,
        "patient_defense_focus_temp_hp_dice_from": "monk_martial_arts_die",
        "step_of_the_wind_focus_companion_param": "heightened_focus_companion_id",
        "step_of_the_wind_focus_companion_within_ft": 5,
        "step_of_the_wind_focus_companion_size_max": "large",
        "step_of_the_wind_focus_companion_must_be_willing": True,
        "step_of_the_wind_focus_companion_no_opportunity_attacks": True,
    }
    self_restoration = compendium.action("srd.self_restoration")
    assert self_restoration.action_economy == "none"
    assert self_restoration.requirements == {"class": "monk", "class_level_min": 10}
    assert self_restoration.properties == {
        "self_turn_end_remove_one_condition": ["charmed", "frightened", "poisoned"],
        "requires_choice_if_multiple_conditions": True,
        "forgoing_food_and_drink_does_not_cause_exhaustion": True,
        "food_drink_exhaustion_hazards": ["srd.dehydration", "srd.malnutrition"],
    }
    assert "srd.deflect_energy" not in compendium.classes["monk"].levels["10"]["actions"]
    assert compendium.classes["monk"].levels["13"]["features"] == ["Deflect Energy"]
    assert "srd.deflect_energy" in compendium.classes["monk"].levels["13"]["actions"]
    deflect_energy = compendium.action("srd.deflect_energy")
    assert deflect_energy.action_economy == "none"
    assert deflect_energy.requirements == {"class": "monk", "class_level_min": 13}
    assert deflect_energy.properties == {
        "enhances_action": "srd.deflect_attacks",
        "deflect_attacks_damage_types": "any",
        "replaces_basic_weapon_damage_type_limit": True,
    }
    assert compendium.classes["monk"].levels["14"]["features"] == ["Disciplined Survivor"]
    assert "srd.disciplined_survivor" in compendium.classes["monk"].levels["14"]["actions"]
    assert "srd.disciplined_survivor" in compendium.classes["monk"].levels["17"]["actions"]
    disciplined_survivor = compendium.action("srd.disciplined_survivor")
    assert disciplined_survivor.action_economy == "none"
    assert disciplined_survivor.requirements == {"class": "monk", "class_level_min": 14}
    assert disciplined_survivor.properties == {
        "saving_throw_proficiency": "all",
        "failed_saving_throw_reroll": True,
        "reroll_cost": {"resource": "srd.resource.focus_points", "amount": 1},
        "must_use_new_roll": True,
    }
    assert compendium.classes["monk"].levels["15"]["features"] == ["Perfect Focus"]
    assert "srd.perfect_focus" in compendium.classes["monk"].levels["15"]["actions"]
    assert "srd.perfect_focus" in compendium.classes["monk"].levels["17"]["actions"]
    perfect_focus = compendium.action("srd.perfect_focus")
    assert perfect_focus.action_economy == "none"
    assert perfect_focus.requirements == {"class": "monk", "class_level_min": 15}
    assert perfect_focus.properties == {
        "trigger": "roll_initiative",
        "requires_uncanny_metabolism_not_used": True,
        "focus_points_threshold_max": 3,
        "focus_points_after": 4,
    }
    assert compendium.classes["monk"].levels["17"]["features"] == ["Subclass Feature"]
    assert "srd.quivering_palm" in compendium.classes["monk"].levels["17"]["actions"]
    assert "srd.quivering_palm_release" in compendium.classes["monk"].levels["17"]["actions"]
    assert "srd.superior_defense" not in compendium.classes["monk"].levels["17"]["actions"]
    quivering_palm = compendium.action("srd.quivering_palm")
    assert quivering_palm.action_economy == "none"
    assert quivering_palm.requirements == {
        "class": "monk",
        "class_level_min": 17,
        "subclass": "open_hand",
    }
    assert quivering_palm.properties == {
        "trigger": "unarmed_strike_hit_creature",
        "focus_point_cost": 4,
        "duration_days_from": "monk_level",
        "maximum_active_targets": 1,
        "can_end_harmlessly_without_action": True,
        "release_action": "srd.quivering_palm_release",
        "release_can_replace_one_attack_during_attack_action": True,
    }
    quivering_release = compendium.action("srd.quivering_palm_release")
    assert quivering_release.action_economy == "action"
    assert quivering_release.range == {"same_plane": True}
    assert compendium.classes["monk"].levels["18"]["features"] == ["Superior Defense"]
    assert "srd.superior_defense" in compendium.classes["monk"].levels["18"]["actions"]
    superior_defense = compendium.action("srd.superior_defense")
    assert superior_defense.action_economy == "none"
    assert superior_defense.requirements == {"class": "monk", "class_level_min": 18}
    assert superior_defense.cost.resources == {"srd.resource.focus_points": 3}
    assert superior_defense.properties == {
        "trigger": "self_turn_start",
        "focus_point_cost": 3,
        "duration": "duration_1_minute_or_incapacitated",
        "damage_resistance": "all_except_force",
    }
    assert superior_defense.automation[1] == {
        "type": "passive_effect",
        "condition": "superior_defense",
        "passive_modifiers": {
            "all_damage_resistance": True,
            "all_damage_resistance_except": ["force"],
            "ends_if_condition": "incapacitated",
        },
        "duration": {"until": "duration_1_minute"},
        "tick_on": "self_turn_start",
        "stacking_policy": "replace",
    }
    assert quivering_release.requirements == {
        "class": "monk",
        "class_level_min": 17,
        "subclass": "open_hand",
    }
    assert quivering_release.properties == {
        "ends_effect_from": "srd.quivering_palm",
        "requires_same_plane": True,
        "save": {"ability": "con", "dc_from": "monk_focus"},
        "damage": {"dice": "10d12", "damage_type": "force", "save_half": True},
        "can_replace_one_attack_during_attack_action": True,
        "can_end_harmlessly_without_action": True,
    }
    assert compendium.classes["monk"].levels["19"]["features"] == ["Epic Boon"]
    assert "srd.body_and_mind" not in compendium.classes["monk"].levels["19"]["actions"]
    assert compendium.classes["monk"].levels["20"]["features"] == ["Body and Mind"]
    assert "srd.body_and_mind" in compendium.classes["monk"].levels["20"]["actions"]
    body_and_mind = compendium.action("srd.body_and_mind")
    assert body_and_mind.action_economy == "none"
    assert body_and_mind.requirements == {"class": "monk", "class_level_min": 20}
    assert body_and_mind.properties == {
        "ability_score_increase": {"dex": 4, "wis": 4},
        "ability_score_maximum": {"dex": 25, "wis": 25},
    }
    patient_focus = compendium.action("srd.patient_defense_focus")
    assert patient_focus.automation[3]["if_true"] == [
        {
            "type": "temp_hp",
            "dice_from": {"class_feature": "monk_martial_arts_die"},
            "dice_count": 2,
        }
    ]
    step_focus = compendium.action("srd.step_of_the_wind_focus")
    assert step_focus.automation[4]["if_true"] == [
        {
            "type": "heightened_focus_step_of_the_wind",
            "companion_param": "heightened_focus_companion_id",
            "duration": {"until": "end_of_current_turn"},
            "tick_on": "self_turn_end",
        }
    ]
    assert "srd.dodge" not in compendium.classes["monk"].levels["2"]["actions"]
    assert "srd.favored_enemy_hunters_mark" in compendium.classes["ranger"].levels["1"]["actions"]
    assert "srd.deft_explorer" not in compendium.classes["ranger"].levels["1"]["actions"]
    assert "srd.deft_explorer" in compendium.classes["ranger"].levels["2"]["actions"]
    assert "srd.deft_explorer" in compendium.classes["ranger"].levels["5"]["actions"]
    assert compendium.classes["ranger"].levels["6"]["features"] == ["Roving"]
    assert "srd.roving" in compendium.classes["ranger"].levels["6"]["actions"]
    assert compendium.classes["ranger"].levels["7"]["features"] == ["Subclass Feature"]
    assert "srd.ranger_expertise" not in compendium.classes["ranger"].levels["8"]["actions"]
    assert compendium.classes["ranger"].levels["9"]["features"] == ["Expertise"]
    assert "srd.ranger_expertise" in compendium.classes["ranger"].levels["9"]["actions"]
    assert compendium.classes["ranger"].levels["10"]["features"] == ["Tireless"]
    assert "srd.tireless" in compendium.classes["ranger"].levels["10"]["actions"]
    assert compendium.classes["ranger"].levels["11"]["features"] == ["Subclass Feature"]
    assert "srd.tireless" in compendium.classes["ranger"].levels["11"]["actions"]
    assert "srd.superior_hunters_prey" not in compendium.classes["ranger"].levels["11"]["actions"]
    assert compendium.classes["ranger"].levels["12"]["features"] == ["Ability Score Improvement"]
    assert compendium.classes["ranger"].levels["13"]["features"] == ["Relentless Hunter"]
    assert "srd.relentless_hunter" in compendium.classes["ranger"].levels["13"]["actions"]
    assert compendium.classes["ranger"].levels["14"]["features"] == ["Nature's Veil"]
    assert "srd.natures_veil" in compendium.classes["ranger"].levels["14"]["actions"]
    assert compendium.classes["ranger"].levels["15"]["features"] == ["Subclass Feature"]
    assert "srd.precise_hunter" not in compendium.classes["ranger"].levels["15"]["actions"]
    assert compendium.classes["ranger"].levels["16"]["features"] == ["Ability Score Improvement"]
    assert "srd.precise_hunter" not in compendium.classes["ranger"].levels["16"]["actions"]
    assert compendium.classes["ranger"].levels["17"]["features"] == ["Precise Hunter"]
    assert "srd.precise_hunter" in compendium.classes["ranger"].levels["17"]["actions"]
    assert compendium.classes["ranger"].levels["18"]["features"] == ["Feral Senses"]
    assert "srd.feral_senses" in compendium.classes["ranger"].levels["18"]["actions"]
    assert compendium.classes["ranger"].levels["19"]["features"] == ["Epic Boon"]
    assert "srd.foe_slayer" not in compendium.classes["ranger"].levels["19"]["actions"]
    assert compendium.classes["ranger"].levels["20"]["features"] == ["Foe Slayer"]
    assert "srd.foe_slayer" in compendium.classes["ranger"].levels["20"]["actions"]
    assert compendium.classes["ranger"].levels["1"]["features"] == [
        "Spellcasting",
        "Favored Enemy",
        "Weapon Mastery",
    ]
    assert compendium.classes["ranger"].levels["3"]["features"] == ["Ranger Subclass"]
    assert "srd.rogue_expertise" in compendium.classes["rogue"].levels["1"]["actions"]
    assert "srd.rogue_expertise" in compendium.classes["rogue"].levels["5"]["actions"]
    assert "srd.sneak_attack" in compendium.classes["rogue"].levels["1"]["actions"]
    assert "srd.thieves_cant" in compendium.classes["rogue"].levels["1"]["actions"]
    assert compendium.classes["rogue"].subclasses["thief"] == {
        "name": "Thief",
        "level": 3,
        "features": [
            "Fast Hands",
            "Second-Story Work",
            "Supreme Sneak",
            "Thief's Reflexes",
        ],
        "actions": [
            "srd.fast_hands_sleight_of_hand",
            "srd.fast_hands_utilize",
            "srd.fast_hands_magic_item",
            "srd.second_story_work",
            "srd.supreme_sneak",
            "srd.thiefs_reflexes",
        ],
    }
    supreme_sneak = compendium.action("srd.supreme_sneak")
    assert supreme_sneak.requirements == {
        "class": "rogue",
        "class_level_min": 9,
        "subclass": "thief",
    }
    assert supreme_sneak.properties == {
        "adds_cunning_strike_effect": "stealth_attack",
        "die_cost": "1d6",
        "requires_hide_invisible_condition": True,
        "preserves_hide_invisible_on_attack_when_end_turn_cover": [
            "three_quarters",
            "total",
        ],
    }
    thiefs_reflexes = compendium.action("srd.thiefs_reflexes")
    assert thiefs_reflexes.requirements == {
        "class": "rogue",
        "class_level_min": 17,
        "subclass": "thief",
    }
    assert thiefs_reflexes.properties == {
        "first_round_turns": 2,
        "second_turn_initiative_penalty": -10,
        "only_first_round": True,
    }
    fast_hands = compendium.action("srd.fast_hands_sleight_of_hand")
    assert fast_hands.action_economy == "bonus_action"
    assert fast_hands.requirements == {
        "class": "rogue",
        "class_level_min": 3,
        "subclass": "thief",
    }
    assert fast_hands.automation[1] == {
        "type": "ability_check",
        "ability": "dex",
        "skill": "sleight_of_hand",
        "tool": "thieves_tools",
        "difficulty_tier": "medium",
    }
    assert "srd.spell.fire_bolt" in compendium.spells
    assert compendium.spell("srd.spell.fire_bolt").action_id == "srd.fire_bolt"
    assert {
        "srd.spell.magic_missile",
        "srd.spell.healing_word",
        "srd.spell.poison_spray",
        "srd.spell.aid",
        "srd.spell.alarm",
        "srd.spell.bless",
        "srd.spell.detect_magic",
        "srd.spell.lesser_restoration",
        "srd.spell.fly",
        "srd.spell.light",
        "srd.spell.web",
        "srd.spell.spirit_guardians",
        "srd.spell.shatter",
        "srd.spell.hold_person",
        "srd.spell.fireball",
        "srd.spell.ice_storm",
        "srd.spell.fire_shield",
        "srd.spell.vitriolic_sphere",
        "srd.spell.wall_of_fire",
        "srd.spell.phantasmal_killer",
        "srd.spell.resilient_sphere",
        "srd.spell.banishment",
        "srd.spell.antilife_shell",
        "srd.spell.aura_of_life",
        "srd.spell.death_ward",
        "srd.spell.cone_of_cold",
        "srd.spell.chain_lightning",
        "srd.spell.fire_storm",
        "srd.spell.forcecage",
        "srd.spell.sunburst",
        "srd.spell.mind_blank",
        "srd.spell.meteor_swarm",
        "srd.spell.flame_strike",
        "srd.spell.disintegrate",
        "srd.spell.heal",
        "srd.spell.harm",
        "srd.spell.finger_of_death",
        "srd.spell.charm_monster",
        "srd.spell.commune",
        "srd.spell.commune_with_nature",
        "srd.spell.contact_other_plane",
        "srd.spell.legend_lore",
        "srd.spell.telepathic_bond",
        "srd.spell.compulsion",
        "srd.spell.conjure_minor_elementals",
        "srd.spell.conjure_woodland_beings",
        "srd.spell.creation",
        "srd.spell.guardian_of_faith",
        "srd.spell.black_tentacles",
        "srd.spell.etherealness",
    } <= set(compendium.spells)
    assert compendium.spell("srd.spell.meteor_swarm").level == 9
    assert compendium.spell("srd.spell.flame_strike").level == 5
    assert compendium.action("srd.heal").automation[2]["conditions"] == [
        "blinded",
        "deafened",
        "poisoned",
    ]
    assert compendium.action("srd.disintegrate").automation[2]["if_false"][0] == {
        "type": "damage",
        "dice": "10d6+40",
        "damage_type": "force",
        "base_spell_slot_level": 6,
        "extra_dice_per_slot_above": "3d6",
    }
    assert compendium.action("srd.harm").automation[3]["if_false"] == [
        {
            "type": "max_hp_delta",
            "amount_from": "-last_damage_taken",
            "record_hp_max_reduction_marker": True,
        }
    ]
    assert "srd.kobold" in compendium.monsters
    assert {
        "srd.bandit_captain",
        "srd.bandit",
        "srd.cultist",
        "srd.kobold",
        "srd.warrior_infantry",
        "srd.skeleton",
        "srd.wolf",
        "srd.zombie",
    } <= set(compendium.monsters)
    assert compendium.monsters["srd.giant_rat"].armor_class == 13
    assert compendium.monsters["srd.giant_rat"].abilities["dex"] == 16
    assert compendium.monsters["srd.bandit_captain"].armor_class == 15
    assert compendium.monsters["srd.bandit_captain"].hit_points == 52
    assert compendium.monsters["srd.bandit"].actions == [
        "srd.bandit_scimitar",
        "srd.bandit_light_crossbow",
    ]
    assert compendium.monsters["srd.cultist"].actions == ["srd.cultist_ritual_sickle"]
    assert compendium.monsters["srd.kobold"].name == "Kobold Warrior"
    assert compendium.monsters["srd.kobold"].armor_class == 14
    assert compendium.monsters["srd.kobold"].actions == ["srd.kobold_dagger"]
    assert compendium.monsters["srd.skeleton"].armor_class == 14
    assert compendium.monsters["srd.skeleton"].creature_type == "undead"
    assert compendium.monsters["srd.skeleton"].abilities["dex"] == 16
    assert compendium.monsters["srd.skeleton"].actions == [
        "srd.skeleton_shortsword",
        "srd.skeleton_shortbow",
    ]
    assert compendium.monsters["srd.wolf"].armor_class == 12
    assert compendium.monsters["srd.wolf"].creature_type == "beast"
    assert compendium.monsters["srd.wolf"].abilities["str"] == 14
    assert compendium.monsters["srd.wolf"].size == "medium"
    assert compendium.monsters["srd.wolf"].actions == ["srd.wolf_bite"]
    assert compendium.monsters["srd.zombie"].hit_points == 15
    assert compendium.monsters["srd.zombie"].creature_type == "undead"
    assert compendium.monsters["srd.zombie"].actions == ["srd.zombie_slam"]
    assert compendium.monsters["srd.warrior_infantry"].hit_points == 9
    assert compendium.monsters["srd.warrior_infantry"].actions == ["srd.warrior_infantry_spear"]
    assert "srd.shortsword" in compendium.items
    assert compendium.items["srd.longsword"].actions == ["srd.longsword_attack"]
    assert compendium.items["srd.potion_of_healing"].actions == ["srd.use_potion_of_healing"]
    assert compendium.items["srd.potion_of_greater_healing"].actions == [
        "srd.use_potion_of_greater_healing"
    ]
    assert compendium.items["srd.elixir_of_health"].actions == ["srd.use_elixir_of_health"]
    assert compendium.items["srd.potion_of_growth"].actions == ["srd.use_potion_of_growth"]
    assert compendium.items["srd.potion_of_diminution"].actions == ["srd.use_potion_of_diminution"]
    assert compendium.items["srd.potion_of_climbing"].actions == ["srd.use_potion_of_climbing"]
    assert compendium.items["srd.potion_of_clairvoyance"].actions == [
        "srd.use_potion_of_clairvoyance"
    ]
    assert compendium.items["srd.potion_of_flying"].actions == ["srd.use_potion_of_flying"]
    assert compendium.items["srd.potion_of_gaseous_form"].actions == [
        "srd.use_potion_of_gaseous_form"
    ]
    assert compendium.items["srd.potion_of_invisibility"].actions == [
        "srd.use_potion_of_invisibility"
    ]
    assert compendium.items["srd.potion_of_mind_reading"].actions == [
        "srd.use_potion_of_mind_reading"
    ]
    assert compendium.items["srd.potion_of_speed"].actions == ["srd.use_potion_of_speed"]
    assert compendium.items["srd.potion_of_heroism"].actions == ["srd.use_potion_of_heroism"]
    assert compendium.items["srd.potion_of_invulnerability"].actions == [
        "srd.use_potion_of_invulnerability"
    ]
    assert compendium.items["srd.potion_of_poison"].actions == ["srd.use_potion_of_poison"]
    assert compendium.items["srd.potion_of_water_breathing"].actions == [
        "srd.use_potion_of_water_breathing"
    ]
    assert compendium.items["srd.potion_of_vitality"].actions == ["srd.use_potion_of_vitality"]
    assert compendium.items["srd.potion_of_resistance"].actions == ["srd.use_potion_of_resistance"]
    assert compendium.items["srd.amulet_of_proof_against_detection_and_location"].actions == [
        "srd.wear_amulet_of_proof_against_detection_and_location"
    ]
    for giant_type in ["hill", "frost", "stone", "fire", "cloud", "storm"]:
        assert compendium.items[f"srd.belt_of_{giant_type}_giant_strength"].actions == [
            f"srd.wear_belt_of_{giant_type}_giant_strength"
        ]
    assert compendium.items["srd.boots_of_elvenkind"].actions == ["srd.wear_boots_of_elvenkind"]
    assert compendium.items["srd.boots_of_levitation"].actions == [
        "srd.boots_of_levitation_levitate"
    ]
    assert compendium.items["srd.bracers_of_defense"].actions == ["srd.wear_bracers_of_defense"]
    assert compendium.items["srd.cloak_of_protection"].actions == ["srd.wear_cloak_of_protection"]
    assert compendium.items["srd.cloak_of_the_manta_ray"].actions == [
        "srd.wear_cloak_of_the_manta_ray"
    ]
    assert compendium.items["srd.eyes_of_the_eagle"].actions == ["srd.wear_eyes_of_the_eagle"]
    assert compendium.items["srd.eyes_of_minute_seeing"].actions == [
        "srd.wear_eyes_of_minute_seeing"
    ]
    assert compendium.items["srd.gauntlets_of_ogre_power"].actions == [
        "srd.wear_gauntlets_of_ogre_power"
    ]
    assert compendium.items["srd.goggles_of_night"].actions == ["srd.wear_goggles_of_night"]
    assert compendium.items["srd.headband_of_intellect"].actions == [
        "srd.wear_headband_of_intellect"
    ]
    assert compendium.items["srd.helm_of_comprehending_languages"].actions == [
        "srd.helm_of_comprehending_languages_comprehend_languages"
    ]
    assert compendium.items["srd.necklace_of_adaptation"].actions == [
        "srd.wear_necklace_of_adaptation"
    ]
    assert compendium.items["srd.periapt_of_proof_against_poison"].actions == [
        "srd.wear_periapt_of_proof_against_poison"
    ]
    assert compendium.items["srd.slippers_of_spider_climbing"].actions == [
        "srd.wear_slippers_of_spider_climbing"
    ]
    assert compendium.items["srd.stone_of_good_luck"].actions == ["srd.carry_stone_of_good_luck"]
    assert compendium.items["srd.ring_of_protection"].actions == ["srd.wear_ring_of_protection"]
    assert compendium.items["srd.ring_of_swimming"].actions == ["srd.wear_ring_of_swimming"]
    assert compendium.items["srd.leather_armor"].properties["armor_category"] == "light"
    assert compendium.items["srd.chain_mail"].properties["armor_category"] == "heavy"
    assert compendium.items["srd.shield"].properties["armor_category"] == "shield"
    assert compendium.items["srd.poisoners_kit"].item_type == "tool"
    assert {
        "srd.dagger",
        "srd.chain_mail",
        "srd.shield",
        "srd.thieves_tools",
        "srd.poisoners_kit",
        "srd.arcane_focus",
        "srd.explorers_pack",
    } <= set(compendium.items)
    assert set(compendium.classes) >= {
        "barbarian",
        "bard",
        "cleric",
        "druid",
        "fighter",
        "monk",
        "paladin",
        "ranger",
        "rogue",
        "sorcerer",
        "warlock",
        "wizard",
    }
    assert compendium.classes["warlock"].levels["1"]["features"] == [
        "Eldritch Invocations",
        "Pact Magic",
    ]
    assert compendium.classes["warlock"].levels["2"]["features"] == ["Magical Cunning"]
    assert compendium.classes["warlock"].levels["5"]["features"] == []
    assert compendium.classes["warlock"].levels["6"]["features"] == ["Subclass Feature"]
    assert compendium.classes["warlock"].levels["19"]["features"] == ["Epic Boon"]
    assert "srd.eldritch_master" not in compendium.classes["warlock"].levels["19"]["actions"]
    assert compendium.classes["warlock"].levels["20"]["features"] == ["Eldritch Master"]
    assert "srd.eldritch_master" in compendium.classes["warlock"].levels["20"]["actions"]
    assert compendium.classes["warlock"].subclasses["fiend"]["name"] == "Fiend Patron"
    assert compendium.classes["warlock"].subclasses["fiend"]["actions"] == [
        "srd.dark_ones_blessing",
        "srd.dark_ones_own_luck",
        "srd.fiendish_resilience",
    ]
    assert compendium.classes["warlock"].levels["2"]["actions"] == [
        "srd.eldritch_blast",
        "srd.eldritch_invocations",
        "srd.magical_cunning",
    ]
    assert "srd.dark_ones_blessing" not in compendium.classes["warlock"].levels["3"]["actions"]
    assert "srd.dark_ones_own_luck" in compendium.classes["warlock"].levels["6"]["actions"]
    assert compendium.classes["wizard"].levels["1"]["features"] == [
        "Spellcasting",
        "Ritual Adept",
        "Arcane Recovery",
    ]
    assert compendium.action("srd.arcane_recovery").requirements == {
        "class": "wizard",
        "class_level_min": 1,
    }
    assert compendium.action("srd.ritual_adept").action_economy == "none"
    assert compendium.action("srd.arcane_recovery").action_economy == "none"
    assert "srd.ritual_adept" in compendium.classes["wizard"].levels["1"]["actions"]
    assert "srd.ritual_adept" in compendium.classes["wizard"].levels["5"]["actions"]
    assert "srd.arcane_recovery" in compendium.classes["wizard"].levels["1"]["actions"]
    assert "srd.arcane_recovery" in compendium.classes["wizard"].levels["5"]["actions"]
    assert compendium.classes["wizard"].levels["2"]["features"] == ["Scholar"]
    assert "srd.scholar" not in compendium.classes["wizard"].levels["1"]["actions"]
    assert "srd.scholar" in compendium.classes["wizard"].levels["2"]["actions"]
    assert "srd.scholar" in compendium.classes["wizard"].levels["5"]["actions"]
    assert compendium.classes["wizard"].levels["3"]["features"] == ["Wizard Subclass"]
    assert compendium.classes["wizard"].levels["5"]["features"] == ["Memorize Spell"]
    assert "srd.memorize_spell" in compendium.classes["wizard"].levels["5"]["actions"]
    assert compendium.classes["wizard"].subclasses["evocation"]["name"] == "Evoker"
    assert compendium.classes["wizard"].subclasses["evocation"]["features"] == ["Potent Cantrip"]
    assert compendium.action("srd.potent_cantrip").requirements == {
        "class": "wizard",
        "class_level_min": 3,
        "subclass": "evocation",
    }
    assert compendium.classes["wizard"].subclasses["evocation"]["actions"] == ["srd.potent_cantrip"]
    assert "srd.potent_cantrip" not in compendium.classes["wizard"].levels["3"]["actions"]
    assert all(
        any(subclass.get("level") == 3 for subclass in class_def.subclasses.values())
        for class_def in compendium.classes.values()
    )
    assert {item["id"] for item in compendium.attributions} >= {
        "srd-5.2.1-structured-data",
        "starter-campaign-pack",
    }


def test_validator_rejects_unsafe_or_invalid_nodes() -> None:
    data = {
        "id": "bad",
        "name": "Bad",
        "localization": {"en": "Bad", "zh": "坏"},
        "source": "test",
        "rules_version": "test",
        "action_type": "spell",
        "action_economy": "action",
        "range": {},
        "target_policy": {},
        "automation": [
            {"type": "damage", "dice": "1d6", "damage_type": "nonsense"},
            {"type": "condition", "condition": "not-a-condition"},
            {"type": "text_result", "automation": []},
        ],
    }

    report = RuleDataValidator().validate_action(data)

    assert not report.ok
    assert any("invalid damage_type" in error for error in report.errors)
    assert any("runtime automation injection" in error for error in report.errors)


def test_validator_rejects_bare_automation_dc() -> None:
    data = {
        "id": "bad_dc",
        "name": "Bad DC",
        "localization": {"en": "Bad DC", "zh": "坏 DC"},
        "source": "test",
        "rules_version": "test",
        "action_type": "base_action",
        "action_economy": "action",
        "range": {"self": True},
        "target_policy": {"min": 0, "max": 0},
        "automation": [{"type": "ability_check", "ability": "dex", "dc": 15}],
    }

    report = RuleDataValidator().validate_action(data)

    assert not report.ok
    assert any("bare dc is forbidden" in error for error in report.errors)


def test_validator_rejects_srd_namespace_without_srd_metadata() -> None:
    data = {
        "id": "srd.imaginary_blade",
        "name": "Imaginary Blade",
        "localization": {"en": "Imaginary Blade", "zh": "虚构刃"},
        "source": "homebrew",
        "rules_version": "homebrew",
        "action_type": "weapon_attack",
        "action_economy": "action",
        "range": {"normal_ft": 5},
        "target_policy": {"min": 1, "max": 1, "harmful": True},
        "automation": [
            {"type": "target", "mode": "explicit"},
            {"type": "attack_roll", "attack_bonus": 3},
        ],
    }

    report = RuleDataValidator().validate_action(data)

    assert not report.ok
    assert any("srd namespace requires srd rules_version" in error for error in report.errors)
    assert any("srd namespace requires SRD source" in error for error in report.errors)


def test_schema_registry_reports_required_and_type_errors() -> None:
    errors = SchemaRegistry().validate("action", {"id": 123, "automation": {}})

    assert any("missing required field name" in error for error in errors)
    assert any("action.id: expected string" in error for error in errors)
    assert any("action.automation: expected array" in error for error in errors)


def test_rule_data_validator_runs_json_schema_first() -> None:
    report = RuleDataValidator().validate_action({"id": "bad"})

    assert not report.ok
    assert any("missing required field name" in error for error in report.errors)


def test_validator_rejects_bad_compendium_references() -> None:
    validator = RuleDataValidator(known_action_ids={"known.action"})

    class_report = validator.validate_class(
        {
            "id": "bad_class",
            "name": "Bad",
            "localization": {"en": "Bad", "zh": "坏"},
            "source": "test",
            "rules_version": "test",
            "hit_die": "d10",
            "primary_abilities": ["str"],
            "saving_throw_proficiencies": ["str"],
            "levels": {
                "1": {"actions": ["missing.action"]},
                "2": {"actions": []},
                "3": {"actions": []},
                "4": {"actions": []},
                "5": {"actions": []},
            },
        }
    )
    spell_report = validator.validate_spell(
        {
            "id": "bad_spell",
            "name": "Bad Spell",
            "localization": {"en": "Bad Spell", "zh": "坏法术"},
            "source": "test",
            "rules_version": "test",
            "level": 4,
            "school": "evocation",
            "classes": ["wizard"],
            "action_id": "missing.action",
        }
    )

    assert any("unknown action reference" in error for error in class_report.errors)
    assert any("unknown action reference" in error for error in spell_report.errors)

    too_high_spell_report = validator.validate_spell(
        {
            "id": "too_high_spell",
            "name": "Too High Spell",
            "localization": {"en": "Too High Spell", "zh": "过高法术"},
            "source": "test",
            "rules_version": "test",
            "level": 10,
            "school": "evocation",
            "classes": ["wizard"],
            "action_id": "known.action",
        }
    )
    assert any("SRD spell level" in error for error in too_high_spell_report.errors)


def test_validator_requires_level_three_subclasses_for_phase1_classes() -> None:
    validator = RuleDataValidator()

    report = validator.validate_class(
        {
            "id": "bad_subclass",
            "name": "Bad Subclass",
            "localization": {"en": "Bad", "zh": "坏"},
            "source": "test",
            "rules_version": "test",
            "hit_die": "d8",
            "primary_abilities": ["cha"],
            "saving_throw_proficiencies": ["cha"],
            "levels": {
                "1": {"actions": []},
                "2": {"actions": []},
                "3": {"actions": []},
                "4": {"actions": []},
                "5": {"actions": []},
            },
            "subclasses": {
                "too_early": {"name": "Too Early", "level": 1, "features": ["Early Feature"]}
            },
        }
    )

    assert any("subclass level must be 3" in error for error in report.errors)

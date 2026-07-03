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
        "srd.cone_of_cold",
        "srd.chain_lightning",
        "srd.fire_storm",
        "srd.meteor_swarm",
        "srd.flame_strike",
        "srd.circle_of_death",
        "srd.disintegrate",
        "srd.heal",
        "srd.harm",
        "srd.finger_of_death",
        "srd.greater_invisibility",
        "srd.blight",
        "srd.mass_cure_wounds",
        "srd.hold_monster",
        "srd.irresistible_dance",
        "srd.greater_restoration",
        "srd.globe_of_invulnerability",
        "srd.cloudkill",
        "srd.teleportation_circle",
        "srd.insect_plague",
        "srd.transport_via_plants",
        "srd.passwall",
        "srd.tree_stride",
        "srd.wall_of_force",
        "srd.wall_of_stone",
    } <= set(compendium.actions)
    assert "srd.monster_melee_attack" not in compendium.actions
    assert "srd.action_surge" in compendium.actions
    assert compendium.action("srd.action_surge").cost.resources == {"srd.resource.action_surge": 1}
    assert "srd.tactical_mind" in compendium.actions
    assert compendium.action("srd.tactical_mind").requirements == {
        "class": "fighter",
        "class_level_min": 2,
    }
    assert compendium.action("srd.tactical_mind").action_economy == "none"
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
    assert compendium.action("srd.deft_explorer").requirements == {
        "class": "ranger",
        "class_level_min": 2,
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
    greater_invisibility = compendium.action("srd.greater_invisibility")
    assert greater_invisibility.requirements == {"spell_level": 4}
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
            ],
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
    assert compendium.classes["ranger"].subclasses["hunter"] == {
        "name": "Hunter",
        "level": 3,
        "features": ["Hunter's Lore", "Hunter's Prey"],
        "actions": ["srd.hunters_lore"],
        "feature_options": {
            "hunters_prey": [
                "srd.hunters_prey_colossus_slayer",
                "srd.hunters_prey_horde_breaker",
            ]
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
    assert "srd.jack_of_all_trades" not in compendium.classes["bard"].levels["1"]["actions"]
    assert "srd.jack_of_all_trades" in compendium.classes["bard"].levels["2"]["actions"]
    assert "srd.jack_of_all_trades" in compendium.classes["bard"].levels["5"]["actions"]
    assert {
        "srd.font_of_inspiration_restore_bardic_inspiration_slot_1",
        "srd.font_of_inspiration_restore_bardic_inspiration_slot_2",
        "srd.font_of_inspiration_restore_bardic_inspiration_slot_3",
    } <= set(compendium.classes["bard"].levels["5"]["actions"])
    assert compendium.action("srd.divine_order").requirements == {
        "class": "cleric",
        "class_level_min": 1,
    }
    assert compendium.action("srd.divine_order").action_economy == "none"
    assert "Protector" in compendium.action("srd.divine_order").automation[0]["text"]
    assert "Thaumaturge" in compendium.action("srd.divine_order").automation[0]["text"]
    assert "srd.divine_order" in compendium.classes["cleric"].levels["1"]["actions"]
    assert "srd.divine_order" in compendium.classes["cleric"].levels["5"]["actions"]
    assert {
        "srd.divine_spark_heal",
        "srd.divine_spark_radiant",
        "srd.divine_spark_necrotic",
        "srd.turn_undead",
    } <= set(compendium.classes["cleric"].levels["2"]["actions"])
    assert "srd.disciple_of_life" not in compendium.classes["cleric"].levels["3"]["actions"]
    assert "srd.preserve_life" not in compendium.classes["cleric"].levels["3"]["actions"]
    assert compendium.classes["cleric"].levels["5"]["features"] == ["Sear Undead"]
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
        "features": ["Circle of the Land Spells", "Land's Aid"],
        "actions": ["srd.lands_aid"],
    }
    assert compendium.classes["druid"].levels["5"]["features"] == ["Wild Resurgence"]
    assert {
        "srd.wild_resurgence_restore_wild_shape_slot_1",
        "srd.wild_resurgence_restore_wild_shape_slot_2",
        "srd.wild_resurgence_restore_wild_shape_slot_3",
        "srd.wild_resurgence_create_spell_slot",
    } <= set(compendium.classes["druid"].levels["5"]["actions"])
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
    assert "srd.sorcerous_restoration" not in compendium.classes["sorcerer"].levels["4"]["actions"]
    assert "srd.sorcerous_restoration" in compendium.classes["sorcerer"].levels["5"]["actions"]
    assert compendium.classes["sorcerer"].subclasses["draconic"]["name"] == "Draconic Sorcery"
    assert compendium.action("srd.draconic_resilience").requirements == {
        "class": "sorcerer",
        "class_level_min": 3,
        "subclass": "draconic",
    }
    assert compendium.classes["sorcerer"].subclasses["draconic"]["actions"] == [
        "srd.draconic_resilience"
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
    ]
    assert compendium.classes["fighter"].subclasses["champion"]["actions"] == [
        "srd.improved_critical",
        "srd.remarkable_athlete",
    ]
    assert compendium.classes["fighter"].levels["5"]["features"] == [
        "Extra Attack",
        "Tactical Shift",
    ]
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
    assert compendium.action("srd.frenzy").requirements == {
        "class": "barbarian",
        "class_level_min": 3,
        "subclass": "berserker",
    }
    assert compendium.classes["barbarian"].subclasses["berserker"]["features"] == ["Frenzy"]
    assert compendium.classes["barbarian"].subclasses["berserker"]["actions"] == ["srd.frenzy"]
    assert "srd.frenzy" not in compendium.classes["barbarian"].levels["3"]["actions"]
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
    ]
    assert compendium.classes["cleric"].subclasses["life"]["actions"] == [
        "srd.disciple_of_life",
        "srd.preserve_life",
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
        "features": ["Oath of Devotion Spells", "Sacred Weapon"],
        "actions": ["srd.sacred_weapon"],
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
    assert compendium.classes["monk"].levels["2"]["features"] == [
        "Monk's Focus",
        "Unarmored Movement",
        "Uncanny Metabolism",
    ]
    assert compendium.classes["monk"].subclasses["open_hand"]["name"] == (
        "Warrior of the Open Hand"
    )
    assert compendium.classes["monk"].subclasses["open_hand"]["features"] == ["Open Hand Technique"]
    assert compendium.classes["monk"].subclasses["open_hand"]["actions"] == [
        "srd.open_hand_technique"
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
    assert "srd.dodge" not in compendium.classes["monk"].levels["2"]["actions"]
    assert "srd.favored_enemy_hunters_mark" in compendium.classes["ranger"].levels["1"]["actions"]
    assert "srd.deft_explorer" not in compendium.classes["ranger"].levels["1"]["actions"]
    assert "srd.deft_explorer" in compendium.classes["ranger"].levels["2"]["actions"]
    assert "srd.deft_explorer" in compendium.classes["ranger"].levels["5"]["actions"]
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
        "features": ["Fast Hands", "Second-Story Work"],
        "actions": [
            "srd.fast_hands_sleight_of_hand",
            "srd.fast_hands_utilize",
            "srd.fast_hands_magic_item",
            "srd.second_story_work",
        ],
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
        "srd.spell.cone_of_cold",
        "srd.spell.chain_lightning",
        "srd.spell.fire_storm",
        "srd.spell.meteor_swarm",
        "srd.spell.flame_strike",
        "srd.spell.disintegrate",
        "srd.spell.heal",
        "srd.spell.harm",
        "srd.spell.finger_of_death",
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
    }
    assert compendium.action("srd.harm").automation[3]["if_false"] == [
        {"type": "max_hp_delta", "amount_from": "-last_damage_taken"}
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
    assert compendium.items["srd.boots_of_elvenkind"].actions == ["srd.wear_boots_of_elvenkind"]
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
    assert compendium.classes["warlock"].subclasses["fiend"]["name"] == "Fiend Patron"
    assert compendium.classes["warlock"].subclasses["fiend"]["actions"] == [
        "srd.dark_ones_blessing"
    ]
    assert compendium.classes["warlock"].levels["2"]["actions"] == [
        "srd.eldritch_blast",
        "srd.eldritch_invocations",
        "srd.magical_cunning",
    ]
    assert "srd.dark_ones_blessing" not in compendium.classes["warlock"].levels["3"]["actions"]
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

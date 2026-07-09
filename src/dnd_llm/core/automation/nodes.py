from __future__ import annotations

from typing import Any

NODE_TYPES = {
    "target",
    "attack_roll",
    "saving_throw",
    "ability_check",
    "maze_escape",
    "teleport_outcome",
    "damage",
    "instant_death",
    "resurrection",
    "restore_all_hit_points",
    "healing",
    "healing_pool",
    "temp_hp",
    "condition",
    "cutting_words",
    "hunter_lore",
    "remove_condition",
    "optional_reaction_remove_condition",
    "eyebite_effect",
    "greater_restoration",
    "restoring_touch",
    "passive_effect",
    "world_effect",
    "natures_sanctuary",
    "natures_sanctuary_move",
    "repeat_use_save_before_long_rest",
    "rod_of_absorption_initialize",
    "rod_of_absorption_absorb_spell",
    "rod_of_alertness_protective_aura",
    "robe_of_useful_items_initialize",
    "robe_of_useful_items_patch",
    "max_hp_delta",
    "pact_magic_recovery",
    "preserve_life_healing",
    "wild_resurgence_restore_wild_shape",
    "resource_delta",
    "heightened_focus_step_of_the_wind",
    "quivering_palm_release",
    "tactical_shift_move",
    "instinctive_pounce_move",
    "move",
    "branch",
    "text_result",
}

STATE_CHANGING_NODE_TYPES = {
    "damage",
    "instant_death",
    "resurrection",
    "restore_all_hit_points",
    "healing",
    "healing_pool",
    "temp_hp",
    "condition",
    "remove_condition",
    "optional_reaction_remove_condition",
    "eyebite_effect",
    "greater_restoration",
    "restoring_touch",
    "passive_effect",
    "world_effect",
    "maze_escape",
    "teleport_outcome",
    "natures_sanctuary",
    "natures_sanctuary_move",
    "repeat_use_save_before_long_rest",
    "rod_of_absorption_initialize",
    "rod_of_absorption_absorb_spell",
    "rod_of_alertness_protective_aura",
    "robe_of_useful_items_initialize",
    "robe_of_useful_items_patch",
    "max_hp_delta",
    "pact_magic_recovery",
    "preserve_life_healing",
    "wild_resurgence_restore_wild_shape",
    "resource_delta",
    "heightened_focus_step_of_the_wind",
    "quivering_palm_release",
    "tactical_shift_move",
    "instinctive_pounce_move",
    "move",
}


def _validate_duration_from_slot(duration: dict[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    spec = duration.get("duration_from_slot")
    if spec is None:
        return errors
    if not isinstance(spec, dict):
        errors.append(f"{path}: duration.duration_from_slot must be an object")
        return errors
    base_slot = spec.get("base_spell_slot_level")
    if base_slot is not None and (
        not isinstance(base_slot, int) or isinstance(base_slot, bool) or base_slot < 1
    ):
        errors.append(f"{path}: duration.duration_from_slot base_spell_slot_level must be positive")
    by_slot = spec.get("by_slot_level")
    if not isinstance(by_slot, dict) or not by_slot:
        errors.append(
            f"{path}: duration.duration_from_slot.by_slot_level must be a non-empty object"
        )
        return errors
    for slot_level, until in by_slot.items():
        valid_slot_level = (
            isinstance(slot_level, str)
            and slot_level.isdigit()
            or isinstance(slot_level, int)
            and not isinstance(slot_level, bool)
            and slot_level > 0
        )
        if not valid_slot_level:
            errors.append(
                f"{path}: duration.duration_from_slot.by_slot_level keys must be slot levels"
            )
        if not isinstance(until, str) or not until:
            errors.append(
                f"{path}: duration.duration_from_slot.by_slot_level values must be strings"
            )
    return errors


def _validate_duration_from_param(duration: dict[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    spec = duration.get("duration_from_param")
    if spec is None:
        return errors
    if not isinstance(spec, dict):
        errors.append(f"{path}: duration.duration_from_param must be an object")
        return errors
    param = spec.get("param")
    if not isinstance(param, str) or not param:
        errors.append(f"{path}: duration.duration_from_param.param must be a string")
    by_value = spec.get("by_value")
    if not isinstance(by_value, dict) or not by_value:
        errors.append(
            f"{path}: duration.duration_from_param.by_value must be a non-empty object"
        )
        return errors
    for value_key, until in by_value.items():
        if not isinstance(value_key, str) or not value_key:
            errors.append(
                f"{path}: duration.duration_from_param.by_value keys must be strings"
            )
        if not isinstance(until, str) or not until:
            errors.append(
                f"{path}: duration.duration_from_param.by_value values must be strings"
            )
    return errors


def _validate_repeat_save(duration: dict[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    repeat_save = duration.get("repeat_save")
    if repeat_save is None:
        return errors
    if not isinstance(repeat_save, dict):
        return [f"{path}: duration.repeat_save must be an object"]
    if not isinstance(repeat_save.get("ability"), str):
        errors.append(f"{path}: duration.repeat_save ability must be a string")
    has_dc = isinstance(repeat_save.get("dc"), int) and not isinstance(
        repeat_save.get("dc"),
        bool,
    )
    has_dc_from = isinstance(repeat_save.get("dc_from"), dict)
    if not has_dc and not has_dc_from:
        errors.append(f"{path}: duration.repeat_save requires dc or dc_from")
    if "end_on_success" in repeat_save and not isinstance(
        repeat_save["end_on_success"],
        bool,
    ):
        errors.append(f"{path}: duration.repeat_save end_on_success must be boolean")
    failure_damage = repeat_save.get("failure_damage")
    if failure_damage is not None:
        errors.extend(_validate_repeat_save_failure_damage(failure_damage, path))
    return errors


def _validate_repeat_save_failure_damage(value: Any, path: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{path}: duration.repeat_save.failure_damage must be an object"]
    errors: list[str] = []
    dice = value.get("dice")
    damage_type = value.get("damage_type")
    if not isinstance(dice, str) or not dice:
        errors.append(f"{path}: duration.repeat_save.failure_damage.dice must be a dice string")
    if not isinstance(damage_type, str) or not damage_type:
        errors.append(f"{path}: duration.repeat_save.failure_damage.damage_type must be a string")
    if "extra_dice_per_slot_above" in value:
        extra_dice = value["extra_dice_per_slot_above"]
        if not isinstance(extra_dice, str) or not extra_dice:
            errors.append(
                f"{path}: duration.repeat_save.failure_damage.extra_dice_per_slot_above "
                "must be a dice string"
            )
        base_slot = value.get("base_spell_slot_level")
        if not isinstance(base_slot, int) or isinstance(base_slot, bool) or base_slot < 1:
            errors.append(
                f"{path}: duration.repeat_save.failure_damage.base_spell_slot_level "
                "must be a positive integer"
            )
    return errors


def _validate_duration_roll(node: dict[str, Any], path: str) -> list[str]:
    duration_roll = node.get("duration_roll")
    if duration_roll is None:
        return []
    errors: list[str] = []
    if not isinstance(duration_roll, dict):
        return [f"{path}: duration_roll must be an object"]
    dice = duration_roll.get("dice")
    unit = duration_roll.get("unit")
    ticks_per_unit = duration_roll.get("ticks_per_unit")
    if not isinstance(dice, str) or not dice:
        errors.append(f"{path}: duration_roll.dice must be a die expression")
    if not isinstance(unit, str) or not unit:
        errors.append(f"{path}: duration_roll.unit must be a string")
    if (
        not isinstance(ticks_per_unit, int)
        or isinstance(ticks_per_unit, bool)
        or ticks_per_unit <= 0
    ):
        errors.append(f"{path}: duration_roll.ticks_per_unit must be positive")
    return errors


def validate_node(node: dict[str, Any], path: str = "automation") -> list[str]:
    errors: list[str] = []
    node_type = node.get("type")
    if node_type not in NODE_TYPES:
        errors.append(f"{path}: unsupported node type {node_type!r}")
        return errors
    if node_type == "branch":
        for branch_name in ("if_true", "if_false"):
            branch = node.get(branch_name, [])
            if not isinstance(branch, list):
                errors.append(f"{path}.{branch_name}: must be a list")
                continue
            for index, child in enumerate(branch):
                errors.extend(validate_node(child, f"{path}.{branch_name}[{index}]"))
    if node_type == "target" and node.get("mode") not in {
        "self",
        "explicit",
        "all",
        "each",
        "area",
        "param",
    }:
        errors.append(f"{path}: target.mode is required")
    if node_type == "target" and node.get("mode") == "param":
        param = node.get("param")
        if not isinstance(param, str) or not param:
            errors.append(f"{path}: target.mode param requires param")
    if (
        node_type in {"damage", "healing", "temp_hp"}
        and "dice" not in node
        and "amount" not in node
        and "amount_from" not in node
        and "dice_from" not in node
    ):
        errors.append(f"{path}: {node_type} requires dice, amount, amount_from, or dice_from")
    if node_type in {"damage", "healing", "temp_hp"} and "amount_from" in node:
        amount_from = node["amount_from"]
        if not isinstance(amount_from, str) or not amount_from.startswith("param."):
            errors.append(f"{path}: amount_from supports only param.<name>")
    if node_type in {"damage", "healing", "temp_hp"} and "dice_from" in node:
        dice_from = node["dice_from"]
        if not isinstance(dice_from, dict):
            errors.append(f"{path}: dice_from must be an object")
        elif set(dice_from) == {"class_feature"}:
            if dice_from.get("class_feature") != "monk_martial_arts_die":
                errors.append(f"{path}: dice_from class_feature is unsupported")
        else:
            unsupported_keys = set(dice_from) - {"ability_modifier", "die", "minimum"}
            if unsupported_keys:
                errors.append(f"{path}: dice_from has unsupported keys")
            if not isinstance(dice_from.get("ability_modifier"), str):
                errors.append(f"{path}: dice_from ability_modifier must be a string")
            die = dice_from.get("die")
            if not isinstance(die, str) or not die.startswith("d"):
                errors.append(f"{path}: dice_from die must be a die string")
            minimum = dice_from.get("minimum", 0)
            if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1:
                errors.append(f"{path}: dice_from minimum must be a positive integer")
    if node_type in {"damage", "healing", "temp_hp"} and "dice_count" in node:
        dice_count = node["dice_count"]
        if not isinstance(dice_count, int) or isinstance(dice_count, bool) or dice_count < 1:
            errors.append(f"{path}: dice_count must be a positive integer")
    if (
        node_type == "damage"
        and "breaks_on_damage" in node
        and not isinstance(node["breaks_on_damage"], bool)
    ):
        errors.append(f"{path}: breaks_on_damage must be a boolean")
    if (
        node_type == "damage"
        and "shared_roll" in node
        and not isinstance(node["shared_roll"], bool)
    ):
        errors.append(f"{path}: shared_roll must be a boolean")
    if node_type == "instant_death":
        reason = node.get("reason")
        if reason is not None and (not isinstance(reason, str) or not reason):
            errors.append(f"{path}: instant_death.reason must be a non-empty string")
        negated_reason = node.get("death_ward_negated_reason")
        if negated_reason is not None and (
            not isinstance(negated_reason, str) or not negated_reason
        ):
            errors.append(
                f"{path}: instant_death.death_ward_negated_reason "
                "must be a non-empty string"
            )
    if node_type == "optional_reaction_remove_condition":
        condition = node.get("condition")
        if not isinstance(condition, str) or not condition:
            errors.append(
                f"{path}: optional_reaction_remove_condition.condition "
                "must be a non-empty string"
            )
        param = node.get("param")
        if param is not None and (not isinstance(param, str) or not param):
            errors.append(
                f"{path}: optional_reaction_remove_condition.param "
                "must be a non-empty string"
            )
    if node_type == "healing_pool":
        points_param = node.get("points_param", "healing_points")
        max_points = node.get("max_points")
        if not isinstance(points_param, str) or not points_param:
            errors.append(f"{path}: healing_pool points_param must be a string")
        if not isinstance(max_points, int) or isinstance(max_points, bool) or max_points < 1:
            errors.append(f"{path}: healing_pool max_points must be a positive integer")
    if node_type in {"damage", "healing", "temp_hp"} and "minimum_amount" in node:
        minimum_amount = node["minimum_amount"]
        if (
            not isinstance(minimum_amount, int)
            or isinstance(minimum_amount, bool)
            or minimum_amount < 0
        ):
            errors.append(f"{path}: minimum_amount must be a non-negative integer")
    if node_type in {"damage", "healing"} and "extra_dice_per_slot_above" in node:
        extra_dice = node["extra_dice_per_slot_above"]
        if not isinstance(extra_dice, str) or not extra_dice:
            errors.append(f"{path}: extra_dice_per_slot_above must be a dice string")
        base_slot = node.get("base_spell_slot_level")
        if not isinstance(base_slot, int) or isinstance(base_slot, bool) or base_slot < 1:
            errors.append(f"{path}: base_spell_slot_level must be a positive integer")
    if node_type in {"damage", "healing", "temp_hp"} and "extra_amount_per_slot_above" in node:
        extra_amount = node["extra_amount_per_slot_above"]
        if not isinstance(extra_amount, int) or isinstance(extra_amount, bool):
            errors.append(f"{path}: extra_amount_per_slot_above must be an integer")
        base_slot = node.get("base_spell_slot_level")
        if not isinstance(base_slot, int) or isinstance(base_slot, bool) or base_slot < 1:
            errors.append(f"{path}: base_spell_slot_level must be a positive integer")
    if node_type in {"damage", "healing", "temp_hp"} and "bonus_from" in node:
        bonus_from = node["bonus_from"]
        if not isinstance(bonus_from, dict):
            errors.append(f"{path}: bonus_from must be an object")
        elif (
            not (
                set(bonus_from) == {"class_level"}
                and isinstance(bonus_from.get("class_level"), str)
            )
            and not (
                set(bonus_from) == {"ability_modifier"}
                and isinstance(bonus_from.get("ability_modifier"), str)
            )
            and not (
                set(bonus_from) == {"spellcasting_ability_modifier"}
                and bonus_from.get("spellcasting_ability_modifier") == "actor"
            )
        ):
            errors.append(
                f"{path}: bonus_from supports only class_level, ability_modifier string, "
                "or spellcasting_ability_modifier actor"
            )
    if node_type == "condition" and "condition" not in node:
        errors.append(f"{path}: condition node requires condition")
    if node_type == "condition":
        duration = node.get("duration")
        if isinstance(duration, dict):
            errors.extend(_validate_duration_from_slot(duration, path))
            errors.extend(_validate_duration_from_param(duration, path))
            errors.extend(_validate_repeat_save(duration, path))
    if (
        node_type in {"damage", "condition", "passive_effect"}
        and "requires_failed_save" in node
        and not isinstance(node["requires_failed_save"], bool)
    ):
        errors.append(f"{path}: requires_failed_save must be a boolean")
    if (
        node_type in {"damage", "condition", "passive_effect"}
        and "requires_successful_save" in node
        and not isinstance(node["requires_successful_save"], bool)
    ):
        errors.append(f"{path}: requires_successful_save must be a boolean")
    if (
        node_type in {"damage", "condition", "passive_effect"}
        and node.get("requires_failed_save") is True
        and node.get("requires_successful_save") is True
    ):
        errors.append(
            f"{path}: requires_failed_save and requires_successful_save cannot both be true"
        )
    if (
        node_type == "condition"
        and "passive_modifiers" in node
        and not isinstance(node["passive_modifiers"], dict)
    ):
        errors.append(f"{path}: passive_modifiers must be an object")
    if node_type == "remove_condition":
        conditions = node.get("conditions")
        effect_markers = node.get("effect_markers")
        targets_from = node.get("targets_from")
        has_conditions = isinstance(conditions, list) and bool(conditions)
        has_effect_markers = isinstance(effect_markers, list) and bool(effect_markers)
        if not has_conditions and not has_effect_markers:
            errors.append(f"{path}: remove_condition requires conditions or effect_markers")
        if conditions is not None and not isinstance(conditions, list):
            errors.append(f"{path}: remove_condition conditions must be a list")
        if effect_markers is not None and not isinstance(effect_markers, list):
            errors.append(f"{path}: remove_condition effect_markers must be a list")
        if targets_from is not None and targets_from != "healing_pool":
            errors.append(f"{path}: remove_condition targets_from is unsupported")
    if node_type == "greater_restoration":
        choices = node.get("choices")
        if not isinstance(choices, list) or not choices:
            errors.append(f"{path}: greater_restoration requires choices")
        elif not all(isinstance(choice, str) and choice for choice in choices):
            errors.append(f"{path}: greater_restoration choices must be strings")
        choice_param = node.get("choice_param", "greater_restoration_choice")
        if not isinstance(choice_param, str) or not choice_param:
            errors.append(f"{path}: greater_restoration choice_param must be a string")
    if node_type == "restoring_touch":
        conditions_param = node.get("conditions_param", "restoring_touch_conditions")
        points_param = node.get("points_param", "lay_on_hands_points")
        point_cost = node.get("point_cost_per_condition", 5)
        allowed_conditions = node.get("allowed_conditions")
        if not isinstance(conditions_param, str) or not conditions_param:
            errors.append(f"{path}: restoring_touch conditions_param must be a string")
        if not isinstance(points_param, str) or not points_param:
            errors.append(f"{path}: restoring_touch points_param must be a string")
        if not isinstance(point_cost, int) or isinstance(point_cost, bool) or point_cost < 1:
            errors.append(f"{path}: restoring_touch point_cost_per_condition must be positive")
        if not isinstance(allowed_conditions, list) or not allowed_conditions:
            errors.append(f"{path}: restoring_touch requires allowed_conditions")
        elif not all(isinstance(condition, str) and condition for condition in allowed_conditions):
            errors.append(f"{path}: restoring_touch allowed_conditions must be strings")
    if node_type == "resurrection":
        for key in (
            "dead_days_param",
            "died_of_old_age_param",
            "undead_when_died_param",
            "restored_creature_type_param",
            "original_body_exists_param",
            "creature_name_param",
        ):
            value = node.get(key)
            if value is not None and (not isinstance(value, str) or not value):
                errors.append(f"{path}: resurrection {key} must be a string")
        for key in ("max_dead_days", "caster_tax_dead_days_at_least"):
            value = node.get(key)
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 1
            ):
                errors.append(f"{path}: resurrection {key} must be a positive integer")
        target_penalty = node.get("target_d20_test_penalty")
        if target_penalty is not None and (
            not isinstance(target_penalty, int)
            or isinstance(target_penalty, bool)
            or target_penalty < 0
        ):
            errors.append(
                f"{path}: resurrection target_d20_test_penalty must be a non-negative integer"
            )
        for key in ("allow_undead_when_died", "restores_undead_to_non_undead_form"):
            value = node.get(key)
            if value is not None and not isinstance(value, bool):
                errors.append(f"{path}: resurrection {key} must be a boolean")
        markers = node.get("remove_effect_markers")
        if markers is not None and (
            not isinstance(markers, list)
            or not all(isinstance(marker, str) and marker for marker in markers)
        ):
            errors.append(f"{path}: resurrection remove_effect_markers must be strings")
    if node_type == "teleport_outcome":
        for key in ("familiarity_param", "target_mode_param"):
            value = node.get(key)
            if value is not None and (not isinstance(value, str) or not value):
                errors.append(f"{path}: teleport_outcome {key} must be a string")
        table = node.get("outcome_table")
        if not isinstance(table, dict) or not table:
            errors.append(f"{path}: teleport_outcome requires outcome_table")
        else:
            for familiarity, outcomes in table.items():
                if not isinstance(familiarity, str) or not familiarity:
                    errors.append(f"{path}: teleport_outcome familiarity keys must be strings")
                    continue
                if not isinstance(outcomes, dict) or not outcomes:
                    errors.append(
                        f"{path}: teleport_outcome table for {familiarity} must be an object"
                    )
                    continue
                for outcome, span in outcomes.items():
                    if not isinstance(outcome, str) or not outcome:
                        errors.append(f"{path}: teleport_outcome outcomes must be strings")
                    if (
                        not isinstance(span, list)
                        or len(span) != 2
                        or not all(
                            isinstance(value, int)
                            and not isinstance(value, bool)
                            and 1 <= value <= 100
                            for value in span
                        )
                        or int(span[0]) > int(span[1])
                    ):
                        errors.append(
                            f"{path}: teleport_outcome {familiarity}.{outcome} "
                            "must be a [min, max] d100 range"
                        )
        mishap_damage = node.get("mishap_damage")
        if not isinstance(mishap_damage, dict):
            errors.append(f"{path}: teleport_outcome requires mishap_damage")
        else:
            dice = mishap_damage.get("dice")
            damage_type = mishap_damage.get("damage_type")
            if not isinstance(dice, str) or not dice:
                errors.append(f"{path}: teleport_outcome mishap_damage.dice must be a string")
            if not isinstance(damage_type, str) or not damage_type:
                errors.append(
                    f"{path}: teleport_outcome mishap_damage.damage_type must be a string"
                )
        for key in ("off_target_distance_dice", "off_target_direction_dice"):
            value = node.get(key)
            if value is not None and (not isinstance(value, str) or not value):
                errors.append(f"{path}: teleport_outcome {key} must be a string")
        direction_table = node.get("direction_table")
        if direction_table is not None and (
            not isinstance(direction_table, dict)
            or not all(str(key).isdigit() and isinstance(value, str) and value for key, value in direction_table.items())
        ):
            errors.append(f"{path}: teleport_outcome direction_table must map dice to strings")
    if node_type == "preserve_life_healing":
        points_param = node.get("points_param", "preserve_life_points")
        if not isinstance(points_param, str) or not points_param:
            errors.append(f"{path}: preserve_life_healing points_param must be a string")
    if node_type == "instinctive_pounce_move":
        destination_param = node.get(
            "destination_param",
            "instinctive_pounce_to_position_node_id",
        )
        if not isinstance(destination_param, str) or not destination_param:
            errors.append(f"{path}: instinctive_pounce_move destination_param must be a string")
    if node_type == "passive_effect":
        modifiers = node.get("passive_modifiers")
        if not isinstance(modifiers, dict) or not modifiers:
            errors.append(f"{path}: passive_effect requires passive_modifiers")
        duration = node.get("duration")
        if isinstance(duration, dict):
            errors.extend(_validate_duration_from_slot(duration, path))
            errors.extend(_validate_duration_from_param(duration, path))
            errors.extend(_validate_repeat_save(duration, path))
        errors.extend(_validate_duration_roll(node, path))
    if node_type == "world_effect" and not node.get("effect_type"):
        errors.append(f"{path}: world_effect requires effect_type")
    if node_type == "world_effect":
        duration = node.get("duration")
        if isinstance(duration, dict):
            errors.extend(_validate_duration_from_slot(duration, path))
            errors.extend(_validate_duration_from_param(duration, path))
        errors.extend(_validate_duration_roll(node, path))
    if node_type == "world_effect" and "metadata_from_slot" in node:
        metadata_from_slot = node["metadata_from_slot"]
        if not isinstance(metadata_from_slot, dict):
            errors.append(f"{path}: metadata_from_slot must be an object")
        else:
            for metadata_key, spec in metadata_from_slot.items():
                if not isinstance(metadata_key, str) or not metadata_key:
                    errors.append(f"{path}: metadata_from_slot keys must be non-empty strings")
                if not isinstance(spec, dict):
                    errors.append(f"{path}: metadata_from_slot entries must be objects")
                    continue
                base_value = spec.get("base_value")
                if (
                    not isinstance(base_value, int)
                    or isinstance(base_value, bool)
                    or base_value < 0
                ):
                    errors.append(f"{path}: metadata_from_slot base_value must be non-negative")
                base_slot = spec.get("base_spell_slot_level", 1)
                if not isinstance(base_slot, int) or isinstance(base_slot, bool) or base_slot < 1:
                    errors.append(
                        f"{path}: metadata_from_slot base_spell_slot_level must be positive"
                    )
                per_slot = spec.get("value_per_slot_above", 1)
                if not isinstance(per_slot, int) or isinstance(per_slot, bool) or per_slot < 0:
                    errors.append(
                        f"{path}: metadata_from_slot value_per_slot_above must be non-negative"
                    )
    if node_type in {"natures_sanctuary", "natures_sanctuary_move"}:
        destination_param = node.get(
            "destination_param",
            "natures_sanctuary_position_node_id",
        )
        if not isinstance(destination_param, str) or not destination_param:
            errors.append(f"{path}: {node_type} destination_param must be a string")
    if node_type == "repeat_use_save_before_long_rest":
        marker = node.get("marker")
        if not isinstance(marker, str) or not marker:
            errors.append(f"{path}: repeat_use_save_before_long_rest requires marker")
        if "ability" not in node:
            errors.append(f"{path}: repeat_use_save_before_long_rest requires ability")
        if "dc" in node:
            errors.append(f"{path}: bare dc is forbidden; use difficulty_tier or dc_ref")
        if "difficulty_tier" not in node and "dc_ref" not in node and "dc_from" not in node:
            errors.append(
                f"{path}: repeat_use_save_before_long_rest requires difficulty_tier, "
                "dc_ref, or dc_from"
            )
        condition = node.get("failure_condition")
        if condition is not None and not isinstance(condition, str):
            errors.append(f"{path}: failure_condition must be a string")
    if node_type == "rod_of_absorption_initialize":
        stored_energy_roll = node.get("stored_energy_roll")
        if not isinstance(stored_energy_roll, str) or not stored_energy_roll:
            errors.append(f"{path}: rod_of_absorption_initialize requires stored_energy_roll")
    if node_type == "rod_of_absorption_absorb_spell":
        for field_name in (
            "spell_level_param",
            "targeting_only_you_param",
            "creates_area_of_effect_param",
        ):
            field_value = node.get(field_name)
            if not isinstance(field_value, str) or not field_value:
                errors.append(f"{path}: rod_of_absorption_absorb_spell requires {field_name}")
    if node_type == "rod_of_alertness_protective_aura":
        bright_radius = node.get("bright_light_radius_ft")
        dim_radius = node.get("dim_light_additional_ft")
        if not isinstance(bright_radius, int) or isinstance(bright_radius, bool):
            errors.append(
                f"{path}: rod_of_alertness_protective_aura requires bright_light_radius_ft"
            )
        if not isinstance(dim_radius, int) or isinstance(dim_radius, bool):
            errors.append(
                f"{path}: rod_of_alertness_protective_aura requires dim_light_additional_ft"
            )
        modifiers = node.get("passive_modifiers")
        if not isinstance(modifiers, dict) or not modifiers:
            errors.append(f"{path}: rod_of_alertness_protective_aura requires passive_modifiers")
    if node_type == "robe_of_useful_items_initialize":
        fixed_patches = node.get("fixed_patches")
        if not isinstance(fixed_patches, dict) or not fixed_patches:
            errors.append(f"{path}: robe_of_useful_items_initialize requires fixed_patches")
        extra_patch_roll = node.get("extra_patch_roll")
        if not isinstance(extra_patch_roll, str) or not extra_patch_roll:
            errors.append(f"{path}: robe_of_useful_items_initialize requires extra_patch_roll")
        extra_patch_table = node.get("extra_patch_table")
        if not isinstance(extra_patch_table, list) or not extra_patch_table:
            errors.append(f"{path}: robe_of_useful_items_initialize requires extra_patch_table")
        elif not all(isinstance(entry, dict) for entry in extra_patch_table):
            errors.append(f"{path}: robe_of_useful_items_initialize table entries must be objects")
    if node_type == "robe_of_useful_items_patch":
        patch_param = node.get("patch_param")
        if not isinstance(patch_param, str) or not patch_param:
            errors.append(f"{path}: robe_of_useful_items_patch requires patch_param")
        patches = node.get("patches")
        if not isinstance(patches, dict) or not patches:
            errors.append(f"{path}: robe_of_useful_items_patch requires patches")
    if node_type == "max_hp_delta":
        if "amount" not in node and "amount_from" not in node:
            errors.append(f"{path}: max_hp_delta requires amount or amount_from")
        if "amount_from" in node and node["amount_from"] not in {
            "last_damage_taken",
            "-last_damage_taken",
        }:
            errors.append(f"{path}: unsupported max_hp_delta amount_from")
        if "record_hp_max_reduction_marker" in node and not isinstance(
            node["record_hp_max_reduction_marker"], bool
        ):
            errors.append(f"{path}: record_hp_max_reduction_marker must be a boolean")
    if node_type == "resource_delta":
        if "resource" not in node:
            errors.append(f"{path}: resource_delta requires resource")
        delta_fields = [field for field in ("delta", "delta_from", "set") if field in node]
        if not delta_fields:
            errors.append(f"{path}: resource_delta requires delta, delta_from, or set")
        if len(delta_fields) > 1:
            errors.append(f"{path}: resource_delta supports only one of delta, delta_from, or set")
        if "delta_from" in node and node["delta_from"] != "speed":
            errors.append(f"{path}: resource_delta supports only delta_from=speed")
        if "set" in node and (
            not isinstance(node["set"], int) or isinstance(node["set"], bool) or node["set"] < 0
        ):
            errors.append(f"{path}: resource_delta set must be a non-negative integer")
        if "max_from" in node:
            max_from = node["max_from"]
            if not isinstance(max_from, dict):
                errors.append(f"{path}: max_from must be an object")
            elif not (
                set(max_from) == {"class_level"} and isinstance(max_from.get("class_level"), str)
            ) and not (
                set(max_from) == {"class_resource"}
                and isinstance(max_from.get("class_resource"), str)
            ):
                errors.append(f"{path}: max_from supports class_level or class_resource string")
    if node_type == "tactical_shift_move":
        destination_param = node.get("destination_param", "tactical_shift_to_position_node_id")
        if not isinstance(destination_param, str) or not destination_param:
            errors.append(f"{path}: tactical_shift_move destination_param must be a string")
    if node_type in {"ability_check", "saving_throw"}:
        if "ability" not in node:
            errors.append(f"{path}: {node_type} requires ability")
        if "dc" in node:
            errors.append(f"{path}: bare dc is forbidden; use difficulty_tier or dc_ref")
        if "difficulty_tier" not in node and "dc_ref" not in node and "dc_from" not in node:
            errors.append(f"{path}: {node_type} requires difficulty_tier, dc_ref, or dc_from")
        if "dc_from" in node:
            dc_from = node["dc_from"]
            if not isinstance(dc_from, dict):
                errors.append(f"{path}: dc_from must be an object")
            elif set(dc_from) != {"spell_save_dc"} or not isinstance(
                dc_from.get("spell_save_dc"), str
            ):
                errors.append(f"{path}: dc_from supports only spell_save_dc string")
        if "skill" in node and not isinstance(node["skill"], str):
            errors.append(f"{path}: {node_type} skill must be a string")
        if "tool" in node and not isinstance(node["tool"], str):
            errors.append(f"{path}: {node_type} tool must be a string")
        if "auto_fail_creature_types" in node:
            creature_types = node["auto_fail_creature_types"]
            if not isinstance(creature_types, list) or not all(
                isinstance(item, str) and item for item in creature_types
            ):
                errors.append(f"{path}: auto_fail_creature_types must be a list of strings")
    return errors

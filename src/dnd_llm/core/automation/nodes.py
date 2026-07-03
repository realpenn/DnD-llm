from __future__ import annotations

from typing import Any

NODE_TYPES = {
    "target",
    "attack_roll",
    "saving_throw",
    "ability_check",
    "damage",
    "healing",
    "temp_hp",
    "condition",
    "cutting_words",
    "hunter_lore",
    "remove_condition",
    "greater_restoration",
    "passive_effect",
    "world_effect",
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
    "tactical_shift_move",
    "move",
    "branch",
    "text_result",
}

STATE_CHANGING_NODE_TYPES = {
    "damage",
    "healing",
    "temp_hp",
    "condition",
    "remove_condition",
    "greater_restoration",
    "passive_effect",
    "world_effect",
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
    "tactical_shift_move",
    "move",
}


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
    if node_type in {"damage", "healing"} and "extra_dice_per_slot_above" in node:
        extra_dice = node["extra_dice_per_slot_above"]
        if not isinstance(extra_dice, str) or not extra_dice:
            errors.append(f"{path}: extra_dice_per_slot_above must be a dice string")
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
        if isinstance(duration, dict) and "repeat_save" in duration:
            repeat_save = duration["repeat_save"]
            if not isinstance(repeat_save, dict):
                errors.append(f"{path}: duration.repeat_save must be an object")
            else:
                if not isinstance(repeat_save.get("ability"), str):
                    errors.append(f"{path}: duration.repeat_save ability must be a string")
                has_dc = isinstance(repeat_save.get("dc"), int) and not isinstance(
                    repeat_save.get("dc"), bool
                )
                has_dc_from = isinstance(repeat_save.get("dc_from"), dict)
                if not has_dc and not has_dc_from:
                    errors.append(f"{path}: duration.repeat_save requires dc or dc_from")
                if "end_on_success" in repeat_save and not isinstance(
                    repeat_save["end_on_success"], bool
                ):
                    errors.append(f"{path}: duration.repeat_save end_on_success must be boolean")
    if (
        node_type in {"damage", "condition", "passive_effect"}
        and "requires_failed_save" in node
        and not isinstance(node["requires_failed_save"], bool)
    ):
        errors.append(f"{path}: requires_failed_save must be a boolean")
    if node_type == "remove_condition":
        conditions = node.get("conditions")
        effect_markers = node.get("effect_markers")
        has_conditions = isinstance(conditions, list) and bool(conditions)
        has_effect_markers = isinstance(effect_markers, list) and bool(effect_markers)
        if not has_conditions and not has_effect_markers:
            errors.append(f"{path}: remove_condition requires conditions or effect_markers")
        if conditions is not None and not isinstance(conditions, list):
            errors.append(f"{path}: remove_condition conditions must be a list")
        if effect_markers is not None and not isinstance(effect_markers, list):
            errors.append(f"{path}: remove_condition effect_markers must be a list")
    if node_type == "greater_restoration":
        choices = node.get("choices")
        if not isinstance(choices, list) or not choices:
            errors.append(f"{path}: greater_restoration requires choices")
        elif not all(isinstance(choice, str) and choice for choice in choices):
            errors.append(f"{path}: greater_restoration choices must be strings")
        choice_param = node.get("choice_param", "greater_restoration_choice")
        if not isinstance(choice_param, str) or not choice_param:
            errors.append(f"{path}: greater_restoration choice_param must be a string")
    if node_type == "preserve_life_healing":
        points_param = node.get("points_param", "preserve_life_points")
        if not isinstance(points_param, str) or not points_param:
            errors.append(f"{path}: preserve_life_healing points_param must be a string")
    if node_type == "passive_effect":
        modifiers = node.get("passive_modifiers")
        if not isinstance(modifiers, dict) or not modifiers:
            errors.append(f"{path}: passive_effect requires passive_modifiers")
        duration_roll = node.get("duration_roll")
        if duration_roll is not None:
            if not isinstance(duration_roll, dict):
                errors.append(f"{path}: duration_roll must be an object")
            else:
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
    if node_type == "world_effect" and not node.get("effect_type"):
        errors.append(f"{path}: world_effect requires effect_type")
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

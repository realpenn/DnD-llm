from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from dnd_llm.core.resolver import PlayerActionDraft

DM_TOOL_SCHEMA_VERSION = "dm-tools-v2"

DRAFT_TOOL_NAME = "submit_player_action_draft"

DM_VISIBLE_TOOL_NAMES = frozenset(
    {
        DRAFT_TOOL_NAME,
        "roll_check",
        "roll_save",
        "attack",
        "cast_spell",
        "use_item",
        "move",
        "interact",
        "trigger_event",
        "apply_hazard",
        "award",
        "request_combat",
        "request_end_combat",
        "expand_zone",
    }
)


@dataclass(frozen=True)
class DMToolCall:
    name: str
    arguments: dict[str, Any]


class DMToolCallError(ValueError):
    pass


def dm_tool_schemas() -> list[dict[str, Any]]:
    """OpenAI-compatible tool schemas visible to the DM model.

    The model can choose a tool-shaped intent, but the runtime still converts
    that intent into PlayerActionDraft and lets the resolver/tool facade decide.
    """

    return [
        _tool(
            DRAFT_TOOL_NAME,
            "Submit a player action draft. This does not execute directly.",
            {
                "actor_id": _string("The acting combatant or character id."),
                "verb": _string("Short natural-language verb or action label."),
                "candidate_action_id": _nullable_string(
                    "Optional known ActionDefinition id from affordances."
                ),
                "target_ids": _string_array("Explicit target combatant or character ids."),
                "params": _object("Non-numeric routing parameters such as destination node ids."),
            },
            required=["actor_id", "verb"],
        ),
        _tool(
            "attack",
            "Route a weapon or monster attack intent through the resolver.",
            {
                "attacker_id": _string("Actor id. Must match the current player actor."),
                "target_id": _string("Single target id."),
                "action_id": _string("ActionDefinition id for the attack."),
                "two_handed": _boolean(
                    "Whether to make this attack using two hands. Only use when the "
                    "weapon affordance exposes this optional parameter."
                ),
                "weapon_ability": {
                    "type": "string",
                    "enum": ["str", "dex"],
                    "description": (
                        "Strength or Dexterity for this weapon attack. Only use a value "
                        "listed by the weapon affordance."
                    ),
                },
                "use_weapon_mastery": _boolean(
                    "Whether to apply the exposed, registered weapon Mastery property."
                ),
                "use_light_extra_attack": _boolean(
                    "Whether this is the different Light weapon's extra attack after a prior "
                    "Light weapon attack on the same turn."
                ),
            },
            required=["attacker_id", "target_id", "action_id"],
        ),
        _tool(
            "cast_spell",
            "Route a spell intent through the resolver.",
            {
                "caster_id": _string("Actor id. Must match the current player actor."),
                "spell_id": _string("Spell ActionDefinition id."),
                "targets": _string_array("Target ids."),
                "slot_level": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 9,
                    "description": "Requested spell slot level. Resolver/executor validates cost.",
                },
                "spell_slot_pool": {
                    "type": "string",
                    "enum": ["auto", "spellcasting", "pact_magic"],
                    "description": "Which slot pool to spend for multiclass Warlocks.",
                },
                "as_ritual": {
                    "type": "boolean",
                    "description": "Whether to cast a Ritual-tagged spell as a Ritual.",
                },
                "use_rod_of_absorption": {
                    "type": "boolean",
                    "description": "Whether to use stored energy from an owned Rod of Absorption instead of a spell slot.",
                },
            },
            required=["caster_id", "spell_id", "targets", "slot_level"],
        ),
        _tool(
            "use_item",
            "Route an item-use intent through the resolver.",
            {
                "actor_id": _string("Actor id. Must match the current player actor."),
                "item_id": _string("ItemDefinition id, or a legacy item action id."),
                "targets": _string_array("Target ids."),
                "fast_hands": _boolean(
                    "Whether an eligible Thief uses Fast Hands to activate a magic item as a Bonus Action."
                ),
                "damage_type": _nullable_string(
                    "Optional SRD damage type chosen by the GM for items such as Potion of Resistance."
                ),
                "params": _object("Optional item-use parameters validated by the resolver."),
            },
            required=["actor_id", "item_id"],
        ),
        _tool(
            "move",
            "Route validated movement intent through the resolver.",
            {
                "actor_id": _string("Actor id. Must match the current player actor."),
                "to_zone_id": _nullable_string("Exploration destination zone id."),
                "to_position_node_id": _nullable_string("Combat destination position node id."),
            },
            required=["actor_id"],
        ),
        _tool(
            "roll_check",
            "Request a rules check. DCs must use difficulty_tier or dc_ref, never bare numbers.",
            {
                "actor_id": _string("Actor id. Must match the current player actor."),
                "ability": _string("Ability key such as str, dex, con, int, wis, cha."),
                "skill": _nullable_string("Optional canonical skill key such as perception."),
                "tool": _nullable_string("Optional canonical tool key such as thieves_tools."),
                "difficulty_tier": _nullable_string("Named difficulty tier."),
                "dc_ref": _nullable_string("Rules or campaign DC reference."),
                "advantage": _nullable_string("advantage, disadvantage, or null."),
                "use_tactical_mind": _boolean(
                    "Whether to expend Second Wind for Tactical Mind if this check fails."
                ),
                "use_primal_knowledge": _boolean(
                    "Whether an eligible raging Barbarian uses Primal Knowledge to make the check with Strength."
                ),
                "use_stroke_of_luck": _boolean(
                    "Whether an eligible Rogue 20 uses Stroke of Luck if this D20 Test fails."
                ),
                "examines_within_1_ft": _boolean(
                    "Whether this check examines something within 1 foot, for SRD effects such as Eyes of Minute Seeing."
                ),
            },
            required=["actor_id", "ability"],
        ),
        _tool(
            "roll_save",
            "Request a saving throw. DCs must use difficulty_tier or dc_ref.",
            {
                "actor_id": _string("Actor id. Must match the current player actor."),
                "ability": _string("Ability key such as str, dex, con, int, wis, cha."),
                "difficulty_tier": _nullable_string("Named difficulty tier."),
                "dc_ref": _nullable_string("Rules or campaign DC reference."),
                "advantage": _nullable_string("advantage, disadvantage, or null."),
                "avoid_or_end_condition": _nullable_string(
                    "Optional condition key, such as poisoned, when this save avoids or ends that condition."
                ),
                "use_stroke_of_luck": _boolean(
                    "Whether an eligible Rogue 20 uses Stroke of Luck if this D20 Test fails."
                ),
            },
            required=["actor_id", "ability"],
        ),
        _tool(
            "interact",
            "Route an interaction declaration. The engine audits but does not invent rewards.",
            {
                "actor_id": _string("Actor id. Must match the current player actor."),
                "feature_id": _string("Visible feature id."),
                "intent": _string("Interaction intent."),
            },
            required=["actor_id", "feature_id", "intent"],
        ),
        _tool(
            "trigger_event",
            "Request a predefined campaign event by id.",
            {
                "event_id": _string("Predefined EventDefinition id."),
                "actor_ids": _string_array("Actor ids involved."),
                "targets": _string_array("Target ids."),
            },
            required=["event_id"],
        ),
        _tool(
            "apply_hazard",
            "Request a predefined hazard with traceable source parameters.",
            {
                "target_ids": _string_array("Target ids."),
                "hazard_type": _string("HazardDefinition id or type."),
                "params": _object(
                    "Must include source such as map, campaign_pack, or player_declaration."
                ),
            },
            required=["target_ids", "hazard_type", "params"],
        ),
        _tool(
            "award",
            "Request a predefined reward. The engine decides and audits concrete changes.",
            {
                "actor_ids": _string_array("Recipient actor ids."),
                "reward_id": _string("Predefined reward id."),
            },
            required=["actor_ids", "reward_id"],
        ),
        _tool(
            "request_combat",
            "Ask the orchestrator/GM layer to start combat with participants.",
            {"participants": _string_array("Participant ids.")},
            required=["participants"],
        ),
        _tool(
            "request_end_combat",
            "Ask the orchestrator/GM layer to end the current combat.",
            {
                "recover_ammunition": _boolean(
                    "Whether the party spends 1 minute after the fight searching the "
                    "battlefield to recover half its expended ammunition, rounded down."
                )
            },
            required=[],
        ),
        _tool(
            "expand_zone",
            "Request a new adjacent exploration zone. The engine generates ids and tactical graph.",
            {
                "actor_id": _string("Actor id. Must match the current player actor."),
                "parent_zone_id": _nullable_string(
                    "Current visible parent zone id, or null to use the actor's current zone."
                ),
                "theme": _string("Short non-mechanical theme for the new zone."),
                "name": _nullable_string("Optional display name for the new zone."),
            },
            required=["actor_id", "theme"],
        ),
    ]


def extract_dm_tool_calls(response: dict[str, Any]) -> list[DMToolCall]:
    calls: list[DMToolCall] = []
    for item in _raw_tool_calls(response):
        parsed = _parse_raw_tool_call(item)
        if parsed is not None:
            calls.append(parsed)
    return calls


def draft_from_tool_call(
    *,
    actor_id: str,
    player_text: str,
    tool_call: DMToolCall,
) -> PlayerActionDraft:
    validate_dm_tool_call(tool_call)
    args = tool_call.arguments
    if tool_call.name == DRAFT_TOOL_NAME:
        _require_actor_match(actor_id, args.get("actor_id"))
        return PlayerActionDraft(
            actor_id=actor_id,
            verb=str(args.get("verb") or args.get("candidate_action_id") or player_text),
            target_ids=_string_list(args.get("target_ids")),
            candidate_action_id=_optional_str(args.get("candidate_action_id")),
            params=_dict(args.get("params")),
            raw_text=player_text,
        )
    if tool_call.name == "attack":
        _require_actor_match(actor_id, args.get("attacker_id"))
        attack_params: dict[str, Any] = {}
        for param_name in ("two_handed", "use_weapon_mastery", "use_light_extra_attack"):
            if param_name in args:
                attack_params[param_name] = _required_bool(args[param_name], name=param_name)
        if "weapon_ability" in args:
            attack_params["weapon_ability"] = _weapon_ability(args["weapon_ability"])
        return PlayerActionDraft(
            actor_id=actor_id,
            verb="attack",
            target_ids=[str(args["target_id"])],
            candidate_action_id=str(args["action_id"]),
            params=attack_params,
            raw_text=player_text,
        )
    if tool_call.name == "cast_spell":
        _require_actor_match(actor_id, args.get("caster_id"))
        params: dict[str, Any] = {
            "slot_level": int(args.get("slot_level", 0)),
            "as_ritual": bool(args.get("as_ritual", False)),
        }
        if "spell_slot_pool" in args:
            params["spell_slot_pool"] = str(args["spell_slot_pool"]).casefold()
        if bool(args.get("use_rod_of_absorption", False)):
            params["use_rod_of_absorption"] = True
        return PlayerActionDraft(
            actor_id=actor_id,
            verb="cast_spell",
            target_ids=_string_list(args.get("targets")),
            candidate_action_id=str(args["spell_id"]),
            params=params,
            raw_text=player_text,
        )
    if tool_call.name == "use_item":
        _require_actor_match(actor_id, args.get("actor_id"))
        params = _dict(args.get("params"))
        damage_type = _optional_str(args.get("damage_type"))
        if damage_type is not None:
            params["damage_type"] = damage_type
        params["fast_hands"] = bool(args.get("fast_hands", False))
        return PlayerActionDraft(
            actor_id=actor_id,
            verb="use_item",
            target_ids=_string_list(args.get("targets")),
            candidate_action_id=str(args["item_id"]),
            params=params,
            raw_text=player_text,
        )
    if tool_call.name == "move":
        _require_actor_match(actor_id, args.get("actor_id"))
        params = {
            key: value
            for key, value in {
                "to_zone_id": _optional_str(args.get("to_zone_id")),
                "to_position_node_id": _optional_str(args.get("to_position_node_id")),
            }.items()
            if value is not None
        }
        return PlayerActionDraft(
            actor_id=actor_id,
            verb="move",
            target_ids=[],
            candidate_action_id="srd.move",
            params=params,
            raw_text=player_text,
        )
    raise DMToolCallError(
        f"DM tool {tool_call.name} must be executed by an orchestrator handler, not directly"
    )


def validate_dm_tool_call(tool_call: DMToolCall) -> None:
    if tool_call.name not in DM_VISIBLE_TOOL_NAMES:
        raise DMToolCallError(f"tool is not allowed for DM runtime: {tool_call.name}")
    schemas = {
        str(item["function"]["name"]): item["function"]["parameters"] for item in dm_tool_schemas()
    }
    schema = schemas.get(tool_call.name)
    if not isinstance(schema, dict):
        raise DMToolCallError(f"tool schema is unavailable: {tool_call.name}")
    errors = _validate_schema_value(tool_call.arguments, schema, path=tool_call.name)
    if errors:
        raise DMToolCallError("; ".join(errors))


def _validate_schema_value(value: Any, schema: dict[str, Any], *, path: str) -> list[str]:
    errors: list[str] = []
    expected = schema.get("type")
    if expected is not None and not _matches_schema_type(value, expected):
        return [f"{path} must be {_schema_type_label(expected)}"]
    if isinstance(value, int) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, int | float) and value < minimum:
            errors.append(f"{path} must be at least {minimum}")
        if isinstance(maximum, int | float) and value > maximum:
            errors.append(f"{path} must be at most {maximum}")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if isinstance(required, list):
            for name in required:
                if name not in value:
                    errors.append(f"{path} is missing required argument {name}")
        if isinstance(properties, dict):
            for name, child in properties.items():
                if name in value and isinstance(child, dict):
                    errors.extend(_validate_schema_value(value[name], child, path=f"{path}.{name}"))
            if schema.get("additionalProperties") is False:
                for name in value:
                    if name not in properties:
                        errors.append(f"{path} has unknown argument {name}")
    if isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(_validate_schema_value(item, item_schema, path=f"{path}[{index}]"))
    return errors


def _matches_schema_type(value: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        return any(_matches_schema_type(value, item) for item in expected)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _schema_type_label(expected: Any) -> str:
    if isinstance(expected, list):
        return " or ".join(str(item) for item in expected)
    if expected in {"boolean", "integer", "string", "array", "object"}:
        return f"a{'n' if expected == 'integer' else ''} {expected}"
    return str(expected)


def _tool(
    name: str,
    description: str,
    properties: dict[str, Any],
    *,
    required: list[str],
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


def _string(description: str) -> dict[str, Any]:
    return {"type": "string", "description": description}


def _nullable_string(description: str) -> dict[str, Any]:
    return {"type": ["string", "null"], "description": description}


def _boolean(description: str) -> dict[str, Any]:
    return {"type": "boolean", "description": description, "default": False}


def _string_array(description: str) -> dict[str, Any]:
    return {
        "type": "array",
        "items": {"type": "string"},
        "description": description,
        "default": [],
    }


def _object(description: str) -> dict[str, Any]:
    return {"type": "object", "description": description, "additionalProperties": True}


def _required_bool(value: Any, *, name: str) -> bool:
    if not isinstance(value, bool):
        raise DMToolCallError(f"{name} must be a boolean")
    return value


def _weapon_ability(value: Any) -> str:
    if not isinstance(value, str):
        raise DMToolCallError("weapon_ability must be str or dex")
    ability = value.casefold().strip()
    if ability not in {"str", "dex"}:
        raise DMToolCallError("weapon_ability must be str or dex")
    return ability


def _raw_tool_calls(response: dict[str, Any]) -> list[dict[str, Any]]:
    direct = response.get("tool_calls")
    if isinstance(direct, list):
        return [item for item in direct if isinstance(item, dict)]
    choices = response.get("choices")
    if not isinstance(choices, list):
        return []
    calls: list[dict[str, Any]] = []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list):
            calls.extend(item for item in tool_calls if isinstance(item, dict))
    return calls


def _parse_raw_tool_call(raw: dict[str, Any]) -> DMToolCall | None:
    if "function" in raw and isinstance(raw["function"], dict):
        function = raw["function"]
        name = function.get("name")
        arguments = function.get("arguments", {})
    else:
        name = raw.get("name")
        arguments = raw.get("arguments", {})
    if not isinstance(name, str) or not name:
        return None
    return DMToolCall(name=name, arguments=_arguments_dict(arguments))


def _arguments_dict(arguments: Any) -> dict[str, Any]:
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        try:
            loaded = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise DMToolCallError("tool call arguments are not valid JSON") from exc
        if isinstance(loaded, dict):
            return loaded
    raise DMToolCallError("tool call arguments must be an object")


def _require_actor_match(expected_actor_id: str, received_actor_id: Any) -> None:
    if received_actor_id is None:
        return
    if str(received_actor_id) != expected_actor_id:
        raise DMToolCallError("tool call actor does not match player actor")


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise DMToolCallError("tool argument must be a list of strings")
    return [str(item) for item in value]


def _dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise DMToolCallError("tool argument must be an object")
    return value

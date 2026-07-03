from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from dnd_llm.core.resolver import PlayerActionDraft

DM_TOOL_SCHEMA_VERSION = "dm-tools-v1"

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
            {},
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
    if tool_call.name not in DM_VISIBLE_TOOL_NAMES:
        raise DMToolCallError(f"tool is not allowed for DM runtime: {tool_call.name}")
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
        return PlayerActionDraft(
            actor_id=actor_id,
            verb="attack",
            target_ids=[str(args["target_id"])],
            candidate_action_id=str(args["action_id"]),
            raw_text=player_text,
        )
    if tool_call.name == "cast_spell":
        _require_actor_match(actor_id, args.get("caster_id"))
        params: dict[str, Any] = {
            "slot_level": int(args.get("slot_level", 0)),
            "as_ritual": bool(args.get("as_ritual", False)),
        }
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

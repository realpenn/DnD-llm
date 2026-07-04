from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from dnd_llm.core.automation.definitions import ActionDefinition
from dnd_llm.core.compendium.localization import normalize_name
from dnd_llm.core.resolver import PlayerActionDraft
from dnd_llm.dm.adjudicator import Adjudicator
from dnd_llm.dm.context import (
    PROMPT_VERSION,
    SUMMARY_MAX_CHARS,
    SUMMARY_PROMPT_VERSION,
    build_dm_messages,
    build_summary_messages,
    sanitize_summary,
    summarize,
)
from dnd_llm.dm.narrator import Narrator
from dnd_llm.dm.tool_calling import (
    DM_TOOL_SCHEMA_VERSION,
    DMToolCall,
    DMToolCallError,
    dm_tool_schemas,
    draft_from_tool_call,
    extract_dm_tool_calls,
)
from dnd_llm.dm.usage import model_usage_from_response
from dnd_llm.orchestrator.session import GameSession, SessionResult

DIRECT_DM_TOOL_NAMES = {
    "roll_check",
    "roll_save",
    "interact",
    "trigger_event",
    "apply_hazard",
    "award",
    "request_combat",
    "request_end_combat",
    "expand_zone",
}

_MEMORY_NUMBER_RE = re.compile(r"\b\d+\b")
_RESTRICTED_SUMMARY_TERMS = (
    "金币",
    "银币",
    "铜币",
    "白金币",
    "gp",
    "gold",
    "reward",
    "奖励",
    "item",
    "物品",
    "potion",
    "药水",
    "scroll",
    "卷轴",
    "weapon",
    "武器",
    "法术",
    "spell",
    "magic item",
    "魔法物品",
)


@dataclass
class DMResponse:
    accepted: bool
    narration: str
    draft: PlayerActionDraft
    engine_payload: dict[str, Any]
    retries: int = 0


class DMRuntime:
    def __init__(
        self,
        session: GameSession,
        *,
        adjudicator: Adjudicator | None = None,
        narrator: Narrator | None = None,
        client: Any | None = None,
        model_id: str | None = None,
        summary_client: Any | None = None,
        summary_model_id: str | None = None,
        max_retries: int = 1,
        summary_max_chars: int = SUMMARY_MAX_CHARS,
    ):
        self.session = session
        self.adjudicator = adjudicator or Adjudicator()
        self.narrator = narrator or Narrator()
        self.client = client
        self.model_id = model_id
        self.summary_client = summary_client
        self.summary_model_id = summary_model_id
        self.max_retries = max_retries
        self.summary_max_chars = summary_max_chars

    def handle_player_text(
        self,
        *,
        actor_id: str,
        text: str,
        idempotency_key: str,
    ) -> DMResponse:
        draft, model_error, direct_payload = self._draft(
            actor_id=actor_id, text=text, idempotency_key=idempotency_key
        )
        if direct_payload is not None:
            response = DMResponse(
                accepted=True,
                narration=self.narrator.narrate_tool_result(direct_payload),
                draft=draft,
                engine_payload=direct_payload,
                retries=0,
            )
            self._capture_public_memory(text, response, idempotency_key)
            return response
        if model_error is not None:
            return DMResponse(
                accepted=False,
                narration=self.narrator.narrate_rejection(str(model_error["reason"])),
                draft=draft,
                engine_payload=model_error,
                retries=0,
            )
        result = self.session.submit_player_action(draft, idempotency_key)
        response = self._response_from_result(draft, result, retries=0)
        retries = 0
        while not response.accepted and retries < self.max_retries:
            retries += 1
            legal_options = self._legal_retry_options(draft)
            retry_draft = self._retry_draft(
                draft,
                response.engine_payload,
                legal_options=legal_options,
            )
            if retry_draft == draft:
                break
            self.session.audit_log.append(
                self.session.state,
                idempotency_key=f"{idempotency_key}:dm_retry:{retries}",
                player_text=text,
                player_intent=retry_draft.__dict__,
                tool_name="dm.retry",
                tool_args={
                    "previous": draft.__dict__,
                    "error": response.engine_payload,
                    "legal_options": legal_options,
                },
                tool_result={"retry": retries, "draft": retry_draft.__dict__},
                model_id=None,
                prompt_version="dm-runtime-v1",
            )
            retry_result = self.session.submit_player_action(
                retry_draft,
                f"{idempotency_key}:retry:{retries}",
            )
            response = self._response_from_result(retry_draft, retry_result, retries=retries)
            draft = retry_draft
        if not response.accepted:
            self.session.audit_log.append(
                self.session.state,
                idempotency_key=f"{idempotency_key}:dm_degrade",
                player_text=text,
                player_intent=draft.__dict__,
                tool_name="dm.degrade",
                tool_args={"error": response.engine_payload},
                tool_result={"degraded": True},
                model_id=None,
                prompt_version="dm-runtime-v1",
            )
        else:
            self._capture_public_memory(text, response, idempotency_key)
        return response

    def summarize_scene(self, scene_notes: str, *, idempotency_key: str) -> str:
        cached = self.session.queue.idempotency.get(idempotency_key)
        if isinstance(cached, SessionResult) and cached.accepted:
            return str(cached.payload.get("summary", self.session.state.summary))
        clean_notes = scene_notes.strip()
        if not clean_notes:
            return self.session.state.summary
        previous_summary = self.session.state.summary
        summary, model_usage, prompt_version = self._summary_text(
            previous_summary=previous_summary,
            scene_notes=clean_notes,
        )
        result = self.session.update_summary(
            summary=summary,
            scene_notes=clean_notes,
            idempotency_key=idempotency_key,
            model_id=self.summary_model_id,
            prompt_version=prompt_version,
            model_usage=model_usage,
        )
        if isinstance(result, SessionResult) and result.accepted:
            return str(result.payload.get("summary", summary))
        return summary

    def timeout_takeover_draft(
        self,
        actor_id: str,
        now: int,
        idempotency_key: str,
    ) -> PlayerActionDraft | None:
        text = (
            "DD [timeout takeover] 当前玩家回合已超时。"
            "请按该角色性格、当前战场处境和可见合法动作，替其选择一个本回合行动。"
            "只提交行动草案，不创造物品、奖励、法术或规则数字。"
        )
        return self._model_controlled_action_draft(
            actor_id=actor_id,
            text=f"{text}\nnow={now}",
            idempotency_key=idempotency_key,
            audit_prefix="timeout_model",
        )

    def monster_turn_draft(
        self,
        actor_id: str,
        now: int,
        idempotency_key: str,
    ) -> PlayerActionDraft | None:
        text = (
            "DD [monster turn] 当前首领或特殊怪物回合。"
            "请依据其战术倾向、当前战场态势和可见合法动作，选择一个本回合行动。"
            "只提交行动草案，不创造物品、奖励、法术、怪物能力或规则数字。"
        )
        return self._model_controlled_action_draft(
            actor_id=actor_id,
            text=f"{text}\nnow={now}",
            idempotency_key=idempotency_key,
            audit_prefix="monster_model",
        )

    def _model_controlled_action_draft(
        self,
        *,
        actor_id: str,
        text: str,
        idempotency_key: str,
        audit_prefix: str,
    ) -> PlayerActionDraft | None:
        if self.client is None:
            return None
        messages = build_dm_messages(self.session.context_for(actor_id, query=text), text)
        try:
            response = self.client.chat(messages=messages, tools=dm_tool_schemas())
            if response.get("type") == "unconfigured":
                return None
            model_usage = model_usage_from_response(response)
            tool_calls = extract_dm_tool_calls(response)
        except DMToolCallError as exc:
            self._audit_model_error(
                idempotency_key=f"{idempotency_key}:{audit_prefix}",
                text=text,
                reason=str(exc),
                response={},
                model_usage={},
            )
            return None
        except Exception as exc:  # pragma: no cover - concrete SDK failures vary.
            self.session.audit_log.append(
                self.session.state,
                idempotency_key=f"{idempotency_key}:{audit_prefix}_unavailable",
                player_text=text,
                tool_name=f"dm.{audit_prefix}_unavailable",
                tool_args={"error": type(exc).__name__},
                tool_result={"fallback": True},
                model_id=self.model_id,
                prompt_version=self._prompt_version,
            )
            return None
        if not tool_calls:
            self.session.audit_log.append(
                self.session.state,
                idempotency_key=f"{idempotency_key}:{audit_prefix}_no_tool_call",
                player_text=text,
                tool_name=f"dm.{audit_prefix}_no_tool_call",
                tool_args={"response_type": response.get("type")},
                tool_result={"fallback": True},
                model_id=self.model_id,
                prompt_version=self._prompt_version,
                model_usage=model_usage,
            )
            return None
        tool_call = tool_calls[0]
        try:
            draft = draft_from_tool_call(
                actor_id=actor_id,
                player_text=text,
                tool_call=tool_call,
            )
        except DMToolCallError as exc:
            self._audit_model_error(
                idempotency_key=f"{idempotency_key}:{audit_prefix}",
                text=text,
                reason=str(exc),
                response={"tool_name": tool_call.name, "arguments": tool_call.arguments},
                model_usage=model_usage,
            )
            return None
        self.session.audit_log.append(
            self.session.state,
            idempotency_key=f"{idempotency_key}:{audit_prefix}_draft",
            player_text=text,
            player_intent=draft.__dict__,
            tool_name=f"dm.{audit_prefix}_draft",
            tool_args={"tool_name": tool_call.name, "arguments": tool_call.arguments},
            tool_result={"draft": draft.__dict__},
            model_id=self.model_id,
            prompt_version=self._prompt_version,
            model_usage=model_usage,
        )
        return draft

    def _draft(
        self,
        *,
        actor_id: str,
        text: str,
        idempotency_key: str,
    ) -> tuple[PlayerActionDraft, dict[str, Any] | None, dict[str, Any] | None]:
        model_draft, model_error, direct_payload = self._model_draft(
            actor_id=actor_id,
            text=text,
            idempotency_key=idempotency_key,
        )
        if direct_payload is not None:
            return self._empty_draft(actor_id, text), None, direct_payload
        if model_error is not None:
            return self._empty_draft(actor_id, text), model_error, None
        if model_draft is not None:
            return model_draft, None, None
        return self._heuristic_draft(actor_id=actor_id, text=text), None, None

    def _capture_public_memory(
        self,
        text: str,
        response: DMResponse,
        idempotency_key: str,
    ) -> None:
        if not response.accepted:
            return
        note = _public_memory_note(text, response.narration)
        if note is None:
            return
        self.session.remember(
            text=note,
            tags=["scene"],
            visibility="public",
            idempotency_key=f"{idempotency_key}:memory",
        )

    def _model_draft(
        self,
        *,
        actor_id: str,
        text: str,
        idempotency_key: str,
    ) -> tuple[PlayerActionDraft | None, dict[str, Any] | None, dict[str, Any] | None]:
        if self.client is None:
            return None, None, None
        messages = build_dm_messages(self.session.context_for(actor_id, query=text), text)
        tools = dm_tool_schemas()
        try:
            response = self.client.chat(messages=messages, tools=tools)
            if response.get("type") == "unconfigured":
                return None, None, None
            model_usage = model_usage_from_response(response)
            tool_calls = extract_dm_tool_calls(response)
        except DMToolCallError as exc:
            return (
                None,
                self._audit_model_error(
                    idempotency_key=idempotency_key,
                    text=text,
                    reason=str(exc),
                    response={},
                    model_usage={},
                ),
                None,
            )
        except Exception as exc:  # pragma: no cover - concrete SDK failures vary.
            self.session.audit_log.append(
                self.session.state,
                idempotency_key=f"{idempotency_key}:dm_model_unavailable",
                player_text=text,
                tool_name="dm.model_unavailable",
                tool_args={"error": type(exc).__name__},
                tool_result={"fallback": True},
                model_id=self.model_id,
                prompt_version=self._prompt_version,
            )
            return None, None, None
        if not tool_calls:
            self.session.audit_log.append(
                self.session.state,
                idempotency_key=f"{idempotency_key}:dm_model_no_tool_call",
                player_text=text,
                tool_name="dm.model_no_tool_call",
                tool_args={"response_type": response.get("type")},
                tool_result={"fallback": True},
                model_id=self.model_id,
                prompt_version=self._prompt_version,
                model_usage=model_usage,
            )
            return None, None, None
        tool_call = tool_calls[0]
        if tool_call.name in DIRECT_DM_TOOL_NAMES:
            try:
                direct_payload = self._execute_direct_tool_call(
                    actor_id=actor_id,
                    tool_call=tool_call,
                    idempotency_key=idempotency_key,
                )
            except Exception as exc:
                return (
                    None,
                    self._audit_model_error(
                        idempotency_key=idempotency_key,
                        text=text,
                        reason=str(exc),
                        response={"tool_name": tool_call.name, "arguments": tool_call.arguments},
                        model_usage=model_usage,
                    ),
                    None,
                )
            self._audit_direct_tool_choice(
                idempotency_key=idempotency_key,
                text=text,
                tool_call=tool_call,
                tool_result=direct_payload,
                model_usage=model_usage,
            )
            return None, None, direct_payload
        try:
            draft = draft_from_tool_call(
                actor_id=actor_id,
                player_text=text,
                tool_call=tool_call,
            )
        except DMToolCallError as exc:
            return (
                None,
                self._audit_model_error(
                    idempotency_key=idempotency_key,
                    text=text,
                    reason=str(exc),
                    response={"tool_name": tool_call.name, "arguments": tool_call.arguments},
                    model_usage=model_usage,
                ),
                None,
            )
        self.session.audit_log.append(
            self.session.state,
            idempotency_key=f"{idempotency_key}:dm_model_draft",
            player_text=text,
            player_intent=draft.__dict__,
            tool_name="dm.model_draft",
            tool_args={"tool_name": tool_call.name, "arguments": tool_call.arguments},
            tool_result={"draft": draft.__dict__},
            model_id=self.model_id,
            prompt_version=self._prompt_version,
            model_usage=model_usage,
        )
        return draft, None, None

    def _execute_direct_tool_call(
        self,
        *,
        actor_id: str,
        tool_call: DMToolCall,
        idempotency_key: str,
    ) -> dict[str, Any]:
        args = tool_call.arguments
        tool_key = f"{idempotency_key}:dm_tool:{tool_call.name}"
        if tool_call.name == "roll_check":
            self._require_actor_match(actor_id, args.get("actor_id"))
            return self.session.tools.roll_check(
                actor_id,
                str(args["ability"]),
                skill=_optional_str(args.get("skill")),
                tool=_optional_str(args.get("tool")),
                difficulty_tier=_optional_str(args.get("difficulty_tier")),
                dc_ref=_optional_str(args.get("dc_ref")),
                advantage=_optional_str(args.get("advantage")),
                use_tactical_mind=_optional_bool(args.get("use_tactical_mind")),
                use_primal_knowledge=_optional_bool(args.get("use_primal_knowledge")),
                use_stroke_of_luck=_optional_bool(args.get("use_stroke_of_luck")),
                idempotency_key=tool_key,
            )
        if tool_call.name == "roll_save":
            self._require_actor_match(actor_id, args.get("actor_id"))
            return self.session.tools.roll_save(
                actor_id,
                str(args["ability"]),
                difficulty_tier=_optional_str(args.get("difficulty_tier")),
                dc_ref=_optional_str(args.get("dc_ref")),
                advantage=_optional_str(args.get("advantage")),
                use_stroke_of_luck=_optional_bool(args.get("use_stroke_of_luck")),
                idempotency_key=tool_key,
            )
        if tool_call.name == "interact":
            self._require_actor_match(actor_id, args.get("actor_id"))
            return self.session.tools.interact(
                actor_id,
                str(args["feature_id"]),
                str(args["intent"]),
                idempotency_key=tool_key,
            )
        if tool_call.name == "trigger_event":
            return self.session.tools.trigger_event(
                str(args["event_id"]),
                actor_ids=_string_list(args.get("actor_ids")),
                targets=_string_list(args.get("targets")),
                idempotency_key=tool_key,
            )
        if tool_call.name == "apply_hazard":
            params = args.get("params")
            if not isinstance(params, dict):
                raise DMToolCallError("hazard params must be an object")
            return self.session.tools.apply_hazard(
                _string_list(args.get("target_ids")),
                str(args["hazard_type"]),
                params,
                idempotency_key=tool_key,
            )
        if tool_call.name == "award":
            return self.session.tools.award(
                _string_list(args.get("actor_ids")),
                str(args["reward_id"]),
                idempotency_key=tool_key,
            )
        if tool_call.name == "expand_zone":
            self._require_actor_match(actor_id, args.get("actor_id"))
            actor_zone = self._actor_zone(actor_id)
            parent_zone_id = _optional_str(args.get("parent_zone_id")) or actor_zone
            if parent_zone_id != actor_zone:
                raise DMToolCallError("expand_zone parent must match actor current zone")
            result = self.session.expand_dynamic_zone(
                parent_zone_id=parent_zone_id,
                theme=str(args["theme"]),
                name=_optional_str(args.get("name")),
                idempotency_key=tool_key,
            )
            if not isinstance(result, SessionResult):
                raise DMToolCallError("unexpected expand_zone result")
            return {"success": result.accepted, "tool": "expand_zone", **result.payload}
        if tool_call.name == "request_combat":
            return self.session.tools.request_combat(
                _string_list(args.get("participants")),
                idempotency_key=tool_key,
            )
        if tool_call.name == "request_end_combat":
            return self.session.tools.request_end_combat(idempotency_key=tool_key)
        raise DMToolCallError(f"unsupported direct DM tool: {tool_call.name}")

    def _audit_direct_tool_choice(
        self,
        *,
        idempotency_key: str,
        text: str,
        tool_call: DMToolCall,
        tool_result: dict[str, Any],
        model_usage: dict[str, int],
    ) -> None:
        audit_key = f"{idempotency_key}:dm_model_direct_tool"
        if any(event.idempotency_key == audit_key for event in self.session.audit_log.events):
            return
        self.session.audit_log.append(
            self.session.state,
            idempotency_key=audit_key,
            player_text=text,
            tool_name="dm.model_direct_tool",
            tool_args={"tool_name": tool_call.name, "arguments": tool_call.arguments},
            tool_result=tool_result,
            model_id=self.model_id,
            prompt_version=self._prompt_version,
            model_usage=model_usage,
        )

    @staticmethod
    def _require_actor_match(expected_actor_id: str, received_actor_id: Any) -> None:
        if received_actor_id is not None and str(received_actor_id) != expected_actor_id:
            raise DMToolCallError("tool actor_id does not match current actor")

    def _actor_zone(self, actor_id: str) -> str:
        entity = self.session.state.entity_for_actor(actor_id)
        zone_id = getattr(entity, "zone_id", None)
        return str(zone_id or self.session.state.world.current_zone_id)

    def _audit_model_error(
        self,
        *,
        idempotency_key: str,
        text: str,
        reason: str,
        response: dict[str, Any],
        model_usage: dict[str, int],
    ) -> dict[str, Any]:
        payload = {"status": "rejected", "reason": reason}
        self.session.audit_log.append(
            self.session.state,
            idempotency_key=f"{idempotency_key}:dm_degrade",
            player_text=text,
            player_intent=None,
            tool_name="dm.degrade",
            tool_args={"error": response},
            tool_result=payload,
            model_id=self.model_id,
            prompt_version=self._prompt_version,
            model_usage=model_usage,
        )
        return payload

    @property
    def _prompt_version(self) -> str:
        return f"{PROMPT_VERSION}/{DM_TOOL_SCHEMA_VERSION}"

    def _summary_text(
        self,
        *,
        previous_summary: str,
        scene_notes: str,
    ) -> tuple[str, dict[str, int], str]:
        prompt_version = SUMMARY_PROMPT_VERSION
        if self.summary_client is None:
            return (
                summarize(
                    previous_summary,
                    scene_notes,
                    max_chars=self.summary_max_chars,
                ),
                {},
                prompt_version,
            )
        messages = build_summary_messages(previous_summary, scene_notes)
        try:
            response = self.summary_client.chat(messages=messages)
        except Exception:  # pragma: no cover - concrete SDK failures vary.
            return (
                summarize(
                    previous_summary,
                    scene_notes,
                    max_chars=self.summary_max_chars,
                ),
                {},
                prompt_version,
            )
        if response.get("type") == "unconfigured":
            return (
                summarize(
                    previous_summary,
                    scene_notes,
                    max_chars=self.summary_max_chars,
                ),
                {},
                prompt_version,
            )
        content = _summary_content_from_response(response)
        if not content:
            return (
                summarize(
                    previous_summary,
                    scene_notes,
                    max_chars=self.summary_max_chars,
                ),
                model_usage_from_response(response),
                prompt_version,
            )
        source_text = f"{previous_summary}\n{scene_notes}"
        if _introduces_restricted_summary_terms(content, source_text):
            return (
                summarize(
                    previous_summary,
                    scene_notes,
                    max_chars=self.summary_max_chars,
                ),
                model_usage_from_response(response),
                prompt_version,
            )
        return (
            sanitize_summary(content, max_chars=self.summary_max_chars),
            model_usage_from_response(response),
            prompt_version,
        )

    def _heuristic_draft(self, *, actor_id: str, text: str) -> PlayerActionDraft:
        action = self._match_action(text)
        targets = self._match_targets(text, action, actor_id=actor_id)
        return self.adjudicator.draft_from_text(
            actor_id=actor_id,
            text=text,
            candidate_action_id=action.id if action else None,
            target_ids=targets,
        )

    def _empty_draft(self, actor_id: str, text: str) -> PlayerActionDraft:
        return PlayerActionDraft(actor_id=actor_id, verb=text.strip(), raw_text=text)

    def _retry_draft(
        self,
        draft: PlayerActionDraft,
        error_payload: dict[str, Any],
        *,
        legal_options: list[dict[str, Any]],
    ) -> PlayerActionDraft:
        if error_payload.get("status") == "ambiguous" and draft.candidate_action_id is None:
            action_id = _first_legal_action_id(legal_options)
            action = (
                self.session.compendium.actions.get(action_id) if action_id is not None else None
            ) or self._first_affordance()
            if action is not None:
                return PlayerActionDraft(
                    actor_id=draft.actor_id,
                    verb=action.name,
                    candidate_action_id=action.id,
                    target_ids=self._match_targets(draft.raw_text, action, actor_id=draft.actor_id),
                    raw_text=draft.raw_text,
                )
        if error_payload.get("reason") in {"not enough targets", "no matching action"}:
            action = (
                self.session.compendium.actions.get(draft.candidate_action_id)
                if draft.candidate_action_id
                else self._first_affordance()
            )
            if action is not None:
                return PlayerActionDraft(
                    actor_id=draft.actor_id,
                    verb=draft.verb,
                    candidate_action_id=action.id,
                    target_ids=self._fallback_targets(action, actor_id=draft.actor_id),
                    raw_text=draft.raw_text,
                )
        return draft

    def _legal_retry_options(self, draft: PlayerActionDraft) -> list[dict[str, Any]]:
        context = self.session.context_for(draft.actor_id, query=draft.raw_text)
        if context.affordances:
            return [
                {
                    "action_id": option.get("action_id"),
                    "name": option.get("name"),
                    "economy": option.get("economy"),
                    "target_type": option.get("target_type"),
                    "candidate_target_ids": option.get("candidate_target_ids", []),
                }
                for option in context.affordances
            ]
        options = []
        for action_id in self._action_ids_for_actor(draft.actor_id):
            action = self.session.compendium.actions.get(action_id)
            if action is None:
                continue
            options.append(
                {
                    "action_id": action.id,
                    "name": action.localization.get("zh") or action.name,
                    "economy": action.action_economy,
                    "target_type": _target_type(action),
                    "candidate_target_ids": self._fallback_targets(
                        action,
                        actor_id=draft.actor_id,
                    ),
                }
            )
        return options

    def _response_from_result(
        self,
        draft: PlayerActionDraft,
        result: SessionResult | object,
        *,
        retries: int,
    ) -> DMResponse:
        if not isinstance(result, SessionResult):
            payload = {"status": "rejected", "reason": "unexpected session result"}
            return DMResponse(
                accepted=False,
                narration=self.narrator.narrate_rejection(payload["reason"]),
                draft=draft,
                engine_payload=payload,
                retries=retries,
            )
        if result.accepted:
            return DMResponse(
                accepted=True,
                narration=self.narrator.narrate_tool_result(result.payload),
                draft=draft,
                engine_payload=result.payload,
                retries=retries,
            )
        reason = str(result.payload.get("reason", result.payload.get("status", "rejected")))
        return DMResponse(
            accepted=False,
            narration=self.narrator.narrate_rejection(reason),
            draft=draft,
            engine_payload=result.payload,
            retries=retries,
        )

    def _match_action(self, text: str) -> ActionDefinition | None:
        normalized_text = normalize_name(text)
        for action in self.session.compendium.actions.values():
            names = [action.id, action.name]
            localization = action.localization
            for key in ("zh", "en"):
                if isinstance(localization.get(key), str):
                    names.append(localization[key])
            aliases = localization.get("aliases", [])
            if isinstance(aliases, list):
                names.extend(str(alias) for alias in aliases)
            if any(normalize_name(name) in normalized_text for name in names):
                return action
        return None

    def _match_targets(
        self,
        text: str,
        action: ActionDefinition | None,
        *,
        actor_id: str,
    ) -> list[str]:
        if action is None or self.session.state.encounter is None:
            return []
        normalized_text = normalize_name(text)
        matched = [
            combatant_id
            for combatant_id, combatant in self.session.state.encounter.combatants.items()
            if combatant_id != actor_id
            and (
                normalize_name(combatant_id) in normalized_text
                or normalize_name(combatant.name) in normalized_text
            )
        ]
        if matched:
            return matched[: int(action.target_policy.get("max", len(matched)) or len(matched))]
        return self._fallback_targets(action, actor_id=actor_id)

    def _fallback_targets(self, action: ActionDefinition, *, actor_id: str) -> list[str]:
        if self.session.state.encounter is None or int(action.target_policy.get("min", 0)) == 0:
            return []
        actor = (
            self.session.state.encounter.combatants.get(actor_id) if actor_id is not None else None
        )
        for combatant_id, combatant in self.session.state.encounter.combatants.items():
            if actor is not None and action.target_policy.get("harmful", False):
                if combatant.side != actor.side:
                    return [combatant_id]
            elif combatant_id != actor_id:
                return [combatant_id]
        return [actor_id] if actor_id is not None else []

    def _first_affordance(self) -> ActionDefinition | None:
        current = (
            self.session.state.encounter.current_combatant_id
            if self.session.state.encounter is not None
            else None
        )
        if current is None:
            return None
        for action_id in self._action_ids_for_actor(current):
            action = self.session.compendium.actions.get(action_id)
            if action is not None:
                return action
        return None

    def _action_ids_for_actor(self, actor_id: str) -> list[str]:
        if (
            self.session.state.encounter is not None
            and actor_id in self.session.state.encounter.combatants
        ):
            combatant = self.session.state.encounter.combatants[actor_id]
            if combatant.entity_id in self.session.state.characters:
                return list(self.session.state.characters[combatant.entity_id].actions)
            if combatant.entity_id in self.session.state.monsters:
                return list(self.session.state.monsters[combatant.entity_id].actions)
            if combatant.actions:
                return list(combatant.actions)
        actor = self.session.state.entity_for_actor(actor_id)
        return list(getattr(actor, "actions", []))


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _optional_bool(value: Any) -> bool:
    return value if isinstance(value, bool) else False


def _first_legal_action_id(options: list[dict[str, Any]]) -> str | None:
    for option in options:
        action_id = option.get("action_id")
        if isinstance(action_id, str) and action_id:
            return action_id
    return None


def _target_type(action: ActionDefinition) -> str:
    policy = action.target_policy
    if policy.get("self") is True:
        return "self"
    if int(policy.get("max", policy.get("min", 0)) or 0) == 0:
        return "none"
    return "hostile" if bool(policy.get("harmful", False)) else "creature"


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _public_memory_note(player_text: str, narration: str) -> str | None:
    action = _sanitize_memory_text(player_text)
    result = _sanitize_memory_text(narration)
    if not action and not result:
        return None
    note = f"玩家行动：{action}；公开结果：{result}".strip("；")
    return note[:500]


def _sanitize_memory_text(text: str) -> str:
    return _MEMORY_NUMBER_RE.sub("<num>", text.strip())


def _summary_content_from_response(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    return content.strip()
            text = first.get("text")
            if isinstance(text, str):
                return text.strip()
    content = response.get("content")
    if isinstance(content, str):
        return content.strip()
    return ""


def _introduces_restricted_summary_terms(summary: str, source_text: str) -> bool:
    normalized_source = source_text.casefold()
    normalized_summary = summary.casefold()
    return any(
        term.casefold() in normalized_summary and term.casefold() not in normalized_source
        for term in _RESTRICTED_SUMMARY_TERMS
    )

from __future__ import annotations

from ..core.resolver import PlayerActionDraft


class Adjudicator:
    """Natural-language to draft adapter.

    The production path can call an OpenAI-compatible model. The fallback keeps
    runtime numeric authority outside the LLM by only producing a draft.
    """

    def draft_from_text(
        self,
        *,
        actor_id: str,
        text: str,
        candidate_action_id: str | None = None,
        target_ids: list[str] | None = None,
    ) -> PlayerActionDraft:
        verb = candidate_action_id or text.strip().split(maxsplit=1)[0]
        return PlayerActionDraft(
            actor_id=actor_id,
            verb=verb,
            target_ids=target_ids or [],
            candidate_action_id=candidate_action_id,
            raw_text=text,
        )

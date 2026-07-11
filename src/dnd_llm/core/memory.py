from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any

from .models import GameState, MemoryFragment

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+")
_DEFAULT_DIMENSIONS = 128
_PUBLIC_VISIBILITY = {"public"}


@dataclass(frozen=True)
class RetrievedMemory:
    fragment: MemoryFragment
    score: float

    def to_context_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.fragment.id,
            "text": self.fragment.text,
            "tags": list(self.fragment.tags),
            "score": round(self.score, 4),
        }


def remember_fragment(
    state: GameState,
    *,
    text: str,
    tags: list[str] | None = None,
    visibility: str = "public",
    source_event_id: str | None = None,
) -> MemoryFragment:
    normalized_text = text.strip()
    if not normalized_text:
        raise ValueError("memory text cannot be empty")
    normalized_tags = [tag.strip() for tag in (tags or []) if tag.strip()]
    fragment = MemoryFragment(
        id=f"memory-{len(state.memory_fragments) + 1:08d}",
        text=normalized_text,
        tags=normalized_tags,
        visibility=visibility,
        source_event_id=source_event_id,
        created_at_event_counter=state.event_counter,
        embedding=embed_text(" ".join([normalized_text, *normalized_tags])),
    )
    state.memory_fragments.append(fragment)
    return fragment


def retrieve_memory(
    state: GameState,
    *,
    query: str,
    limit: int = 3,
    min_score: float = 0.05,
    visible_to: set[str] | None = None,
) -> list[RetrievedMemory]:
    if limit <= 0:
        return []
    query_embedding = embed_text(query)
    if not query_embedding:
        return []
    allowed_visibility = visible_to or _PUBLIC_VISIBILITY
    scored: list[RetrievedMemory] = []
    for fragment in state.memory_fragments:
        if fragment.visibility not in allowed_visibility:
            continue
        score = cosine_similarity(query_embedding, fragment.embedding)
        if score >= min_score:
            scored.append(RetrievedMemory(fragment=fragment, score=score))
    scored.sort(
        key=lambda item: (
            -item.score,
            item.fragment.created_at_event_counter,
            item.fragment.id,
        )
    )
    return scored[:limit]


def embed_text(text: str, *, dimensions: int = _DEFAULT_DIMENSIONS) -> dict[str, float]:
    vector: dict[str, float] = {}
    for token in _tokens(text):
        dimension = _dimension_for_token(token, dimensions)
        vector[dimension] = vector.get(dimension, 0.0) + 1.0
    return vector


def cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(value * right.get(key, 0.0) for key, value in left.items())
    if dot <= 0:
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for match in _TOKEN_RE.finditer(text):
        part = match.group(0)
        if part.isascii():
            tokens.append(part.casefold())
            continue
        tokens.extend(part)
        if len(part) > 1:
            tokens.extend(part[index : index + 2] for index in range(len(part) - 1))
    return tokens


def _dimension_for_token(token: str, dimensions: int) -> str:
    digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
    return str(int.from_bytes(digest, "big") % dimensions)

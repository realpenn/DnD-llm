from __future__ import annotations

import re
import unicodedata

_SPACE_RE = re.compile(r"\s+")


def normalize_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    return _SPACE_RE.sub(" ", normalized)


class AliasIndex:
    def __init__(self) -> None:
        self._index: dict[str, list[str]] = {}

    def add(self, action_id: str, *names: str) -> None:
        for name in names:
            key = normalize_name(name)
            self._index.setdefault(key, [])
            if action_id not in self._index[key]:
                self._index[key].append(action_id)

    def resolve(self, name: str) -> tuple[str, ...]:
        return tuple(self._index.get(normalize_name(name), ()))

    def ambiguous(self) -> dict[str, list[str]]:
        return {key: ids for key, ids in self._index.items() if len(ids) > 1}

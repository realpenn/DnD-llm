from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SchemaRegistry:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def load(self, name: str) -> dict[str, Any]:
        path = self.root / f"{name}.schema.json"
        if not path.exists():
            raise FileNotFoundError(path)
        return json.loads(path.read_text(encoding="utf-8"))

    def validate_required(self, name: str, data: dict[str, Any]) -> list[str]:
        schema = self.load(name)
        errors: list[str] = []
        for field in schema.get("required", []):
            if field not in data:
                errors.append(f"{name}: missing required field {field}")
        properties = schema.get("properties", {})
        for key, value in data.items():
            expected = properties.get(key, {}).get("type")
            if expected == "array" and not isinstance(value, list):
                errors.append(f"{name}.{key}: expected array")
            elif expected == "object" and not isinstance(value, dict):
                errors.append(f"{name}.{key}: expected object")
            elif expected == "string" and not isinstance(value, str):
                errors.append(f"{name}.{key}: expected string")
        return errors

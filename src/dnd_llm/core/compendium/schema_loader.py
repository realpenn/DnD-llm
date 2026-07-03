from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SchemaRegistry:
    root: Path = Path("rules_data/schemas")
    schemas: dict[str, dict[str, Any]] = field(default_factory=dict)

    def schema(self, name: str) -> dict[str, Any] | None:
        if name in self.schemas:
            return self.schemas[name]
        path = self.root / f"{name}.schema.json"
        if not path.exists():
            return None
        schema = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(schema, dict):
            raise ValueError(f"schema {name} must be a JSON object")
        self.schemas[name] = schema
        return schema

    def validate(self, name: str, data: Any) -> list[str]:
        schema = self.schema(name)
        if schema is None:
            return []
        return _validate_value(data, schema, path=name)


def _validate_value(value: Any, schema: dict[str, Any], *, path: str) -> list[str]:
    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type is not None and not _matches_type(value, expected_type):
        errors.append(f"{path}: expected {expected_type}, got {_type_name(value)}")
        return errors
    if isinstance(value, dict):
        required = schema.get("required", [])
        if isinstance(required, list):
            for field_name in required:
                if field_name not in value:
                    errors.append(f"{path}: missing required field {field_name}")
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for field_name, child_schema in properties.items():
                if field_name in value and isinstance(child_schema, dict):
                    errors.extend(
                        _validate_value(
                            value[field_name],
                            child_schema,
                            path=f"{path}.{field_name}",
                        )
                    )
    if isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(_validate_value(item, item_schema, path=f"{path}[{index}]"))
    return errors


def _matches_type(value: Any, expected_type: Any) -> bool:
    if isinstance(expected_type, list):
        return any(_matches_type(value, item) for item in expected_type)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return (isinstance(value, int | float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return type(value).__name__

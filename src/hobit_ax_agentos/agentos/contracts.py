from __future__ import annotations

from typing import Any


class AgentContractError(ValueError):
    """Raised when an agent output does not match its declared schema."""


def validate_output_contract(
    *,
    agent_id: str,
    node_id: str,
    result: dict[str, Any],
    schema: dict[str, Any] | None,
) -> None:
    if not schema:
        return
    try:
        _validate_value(result, schema, path="$")
    except AgentContractError as exc:
        raise AgentContractError(
            f"{agent_id}/{node_id} output contract violation: {exc}"
        ) from exc


def _validate_value(value: Any, schema: dict[str, Any], path: str) -> None:
    expected_type = schema.get("type")
    if expected_type and not _matches_type(value, str(expected_type)):
        raise AgentContractError(
            f"{path} expected {expected_type}, got {type(value).__name__}"
        )

    if expected_type == "object":
        if not isinstance(value, dict):
            return
        for key in schema.get("required", []):
            if key not in value:
                raise AgentContractError(f"{path}.{key} is required")
        properties = schema.get("properties") or {}
        for key, property_schema in properties.items():
            if key in value and isinstance(property_schema, dict):
                _validate_value(value[key], property_schema, f"{path}.{key}")

    if expected_type == "array":
        if not isinstance(value, list):
            return
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                _validate_value(item, item_schema, f"{path}[{index}]")


def _matches_type(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True

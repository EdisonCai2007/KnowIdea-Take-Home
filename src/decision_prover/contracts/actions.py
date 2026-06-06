from __future__ import annotations

from typing import Any, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator


JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]


def _is_json_compatible(value: Any) -> bool:
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, list):
        return all(_is_json_compatible(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _is_json_compatible(item) for key, item in value.items())
    return False


class StructuredAction(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_extras(self) -> "StructuredAction":
        extras = self.model_extra or {}
        for key, value in extras.items():
            if not key:
                raise ValueError("action parameter names must be non-empty strings")
            if not _is_json_compatible(value):
                raise ValueError(
                    f"action parameter '{key}' must be JSON-compatible, got {type(value).__name__}"
                )
        return self

    def value_for(self, key: str) -> JsonValue:
        if key == "type":
            return self.type
        extras = self.model_extra or {}
        return extras.get(key)

    def has_field(self, key: str) -> bool:
        if key == "type":
            return True
        extras = self.model_extra or {}
        return key in extras


ActionPayload: TypeAlias = StructuredAction


def validate_action_payload(value: Any) -> StructuredAction:
    if not isinstance(value, dict):
        raise TypeError("action payload must be an object")

    action_type = value.get("type")
    if not isinstance(action_type, str) or not action_type.strip():
        raise ValueError("action.type must be a non-empty string")

    return StructuredAction.model_validate(value)

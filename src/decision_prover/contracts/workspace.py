from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorkspaceCompanyProfile(StrictModel):
    name: str = Field(min_length=1)
    sector: str = Field(min_length=1)
    description: str | None = None

    @field_validator("name", "sector", mode="before")
    @classmethod
    def normalize_required_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or None


class WorkspaceState(StrictModel):
    active_company: WorkspaceCompanyProfile | None = None

from __future__ import annotations

from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .actions import ActionPayload, validate_action_payload


FactScalar: TypeAlias = str | int | float | bool


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CompanyFact(StrictModel):
    value: FactScalar
    unit: str = Field(min_length=1)
    note: str | None = None


class Constraint(StrictModel):
    id: str = Field(min_length=1)
    kind: Literal["hard"]
    statement: str = Field(min_length=1)
    semi_formal: str = Field(min_length=1)
    note: str | None = None


class Company(StrictModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    sector: str = Field(min_length=1)
    facts: dict[str, CompanyFact]
    constraints: list[Constraint]


class StatedAssumption(StrictModel):
    id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    status: Literal["given", "projected"]


class Decision(StrictModel):
    id: str = Field(min_length=1)
    company: str = Field(min_length=1)
    proposal: str = Field(min_length=1)
    action: ActionPayload
    objective: str = Field(min_length=1)
    stated_assumptions: list[StatedAssumption]

    @field_validator("action", mode="before")
    @classmethod
    def validate_action(cls, value: object) -> ActionPayload:
        return validate_action_payload(value)


class VerdictDefinitions(StrictModel):
    SUPPORTED: str = Field(min_length=1)
    REFUTED: str = Field(min_length=1)
    UNDECIDABLE: str = Field(min_length=1)
    precedence_rule: str = Field(min_length=1)


class BatterySchemaDescription(StrictModel):
    company: str = Field(min_length=1)
    decision: str = Field(min_length=1)
    expected_output_per_decision: str = Field(min_length=1)


class DecisionBattery(StrictModel):
    battery_version: str = Field(min_length=1)
    title: str = Field(min_length=1)
    note_to_candidate: str = Field(min_length=1)
    verdict_definitions: VerdictDefinitions
    schema_: BatterySchemaDescription = Field(
        validation_alias="schema",
        serialization_alias="schema",
    )
    companies: list[Company]
    decisions: list[Decision]


class PartialCompany(StrictModel):
    id: str | None = None
    name: str | None = None
    sector: str | None = None
    facts: dict[str, CompanyFact] = Field(default_factory=dict)
    constraints: list[Constraint] = Field(default_factory=list)


class PartialDecision(StrictModel):
    id: str | None = None
    company: str | None = None
    proposal: str | None = None
    action: dict[str, Any] = Field(default_factory=dict)
    objective: str | None = None
    stated_assumptions: list[StatedAssumption] = Field(default_factory=list)


class PartialDecisionBattery(StrictModel):
    battery_version: str | None = None
    title: str | None = None
    note_to_candidate: str | None = None
    verdict_definitions: VerdictDefinitions | None = None
    schema_: BatterySchemaDescription | None = Field(
        default=None,
        validation_alias="schema",
        serialization_alias="schema",
    )
    companies: list[PartialCompany] = Field(default_factory=list)
    decisions: list[PartialDecision] = Field(default_factory=list)

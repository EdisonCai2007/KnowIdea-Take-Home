from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .output import Stage1Outcome, Stage2FormalizationOutcome, VerificationResult


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


class WorkspaceProposalSubmitRequest(StrictModel):
    proposal: str = Field(min_length=1)

    @field_validator("proposal", mode="before")
    @classmethod
    def normalize_proposal_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized


class WorkspaceProposalAnswersRequest(StrictModel):
    answers: dict[str, str] = Field(default_factory=dict)


class WorkspaceProposalSession(StrictModel):
    proposal_id: str = Field(min_length=1)
    workspace_company: WorkspaceCompanyProfile
    proposal: str = Field(min_length=1)
    answers: dict[str, str] = Field(default_factory=dict)
    result: Stage1Outcome
    formalization: Stage2FormalizationOutcome | None = None
    verification_result: VerificationResult | None = None


class WorkspaceProposalSessionState(StrictModel):
    active_session: WorkspaceProposalSession | None = None

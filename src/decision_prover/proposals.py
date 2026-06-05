from pydantic import BaseModel, ConfigDict, Field


class ProposalPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class ProposalFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    proposals: list[ProposalPrompt] = Field(default_factory=list)


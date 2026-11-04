from pydantic import BaseModel, Field


class FindingsIn(BaseModel):
    findings: str = Field(min_length=10, max_length=4000)
    disposition: str = Field(pattern="^(monitor|escalate|false_positive|insufficient_evidence)$")


class ResolutionIn(BaseModel):
    rationale: str = Field(min_length=10, max_length=2000)
    disposition: str = Field(pattern="^(resolved|false_positive|monitoring)$")


class ResponseActionIn(BaseModel):
    action_type: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=10, max_length=2000)
    owner_role: str | None = Field(default=None, max_length=100)
    due_date: str | None = Field(default=None, pattern=r"^\\d{4}-\\d{2}-\\d{2}$")

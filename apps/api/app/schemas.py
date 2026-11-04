from datetime import date
from pydantic import BaseModel, ConfigDict, Field, model_validator
from uuid import UUID

class ObservationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain: str = Field(pattern="^(community|workforce)$")
    group_code: str = Field(min_length=1, max_length=80)
    source_code: str = Field(min_length=1, max_length=80)
    observed_date: date
    indicator: str = Field(min_length=2, max_length=120)
    value: float = Field(ge=0, le=1_000_000_000)
    denominator: int | None = Field(default=None, gt=0)
    unit: str = Field(min_length=1, max_length=40)

class ImportResult(BaseModel):
    accepted: int
    rejected: int
    errors: list[str]

class DetectionOut(BaseModel):
    observation_id: UUID
    baseline: float | None
    anomaly_score: float | None
    is_candidate: bool
    reason: str

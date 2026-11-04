import uuid
from datetime import datetime, date
from sqlalchemy import (
    String, Date, DateTime, Numeric, Integer, ForeignKey, CheckConstraint,
    UniqueConstraint, JSON, Float
)
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    organization_type: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class Community(Base):
    __tablename__ = "communities"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    region_code: Mapped[str] = mapped_column(String(80), nullable=False)
    population_estimate: Mapped[int | None] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("organization_id", "region_code"),)

class WorkforceGroup(Base):
    __tablename__ = "workforce_groups"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    sector: Mapped[str] = mapped_column(String(100), nullable=False)
    location_code: Mapped[str | None] = mapped_column(String(80))

class DataSource(Base):
    __tablename__ = "data_sources"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    provenance: Mapped[str | None] = mapped_column(String(500))
    authorised: Mapped[bool] = mapped_column(default=False, nullable=False)

class HealthObservation(Base):
    __tablename__ = "health_observations"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    community_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("communities.id"))
    workforce_group_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workforce_groups.id"))
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("data_sources.id"), nullable=False)
    observed_date: Mapped[date] = mapped_column(Date, nullable=False)
    indicator: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    denominator: Mapped[int | None] = mapped_column(Integer)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    __table_args__ = (
        CheckConstraint("(community_id IS NOT NULL AND workforce_group_id IS NULL) OR (community_id IS NULL AND workforce_group_id IS NOT NULL)", name="ck_observation_one_domain"),
        CheckConstraint("value >= 0", name="ck_observation_nonnegative"),
        CheckConstraint("denominator IS NULL OR denominator > 0", name="ck_observation_denominator_positive"),
        UniqueConstraint("source_id", "community_id", "workforce_group_id", "observed_date", "indicator", name="uq_observation_source_group_date_indicator"),
    )

class DetectionResult(Base):
    __tablename__ = "detection_results"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    observation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("health_observations.id"), nullable=False)
    baseline: Mapped[float | None] = mapped_column(Float)
    anomaly_score: Mapped[float | None] = mapped_column(Float)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    detection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("detection_results.id"), unique=True, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending_review", nullable=False)
    explanation: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

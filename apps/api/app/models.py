import uuid
from datetime import date, datetime
from sqlalchemy import (
    String, Date, DateTime, Numeric, Integer, ForeignKey, CheckConstraint, Boolean,
    UniqueConstraint, JSON, Float, Index
)
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
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
    cohort_size: Mapped[int | None] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("organization_id", "location_code"),)

class DataSource(Base):
    __tablename__ = "data_sources"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
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
        Index("uq_community_observation", "source_id", "community_id", "observed_date", "indicator", unique=True, postgresql_where=__import__("sqlalchemy").text("community_id IS NOT NULL"), sqlite_where=__import__("sqlalchemy").text("community_id IS NOT NULL")),
        Index("uq_workforce_observation", "source_id", "workforce_group_id", "observed_date", "indicator", unique=True, postgresql_where=__import__("sqlalchemy").text("workforce_group_id IS NOT NULL"), sqlite_where=__import__("sqlalchemy").text("workforce_group_id IS NOT NULL")),
        Index("ix_observations_date_indicator", "observed_date", "indicator"),
    )

class DetectionResult(Base):
    __tablename__ = "detection_results"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    observation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("health_observations.id"), nullable=False, unique=True)
    baseline: Mapped[float | None] = mapped_column(Float)
    anomaly_score: Mapped[float | None] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(String(80), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    history_count: Mapped[int] = mapped_column(Integer, nullable=False)
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



class Investigation(Base):
    __tablename__ = "investigations"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    alert_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("alerts.id"), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(30), default="in_progress", nullable=False)
    started_by: Mapped[str] = mapped_column(String(120), nullable=False)
    findings: Mapped[str | None] = mapped_column(String(4000))
    disposition: Mapped[str | None] = mapped_column(String(40))
    resolution_rationale: Mapped[str | None] = mapped_column(String(2000))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("status IN ('in_progress', 'closed')", name="ck_investigation_status"),)


class ResponseAction(Base):
    __tablename__ = "response_actions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    alert_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("alerts.id"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    owner_role: Mapped[str | None] = mapped_column(String(100))
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="planned", nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    __table_args__ = (CheckConstraint("status IN ('planned', 'in_progress', 'completed', 'cancelled')", name="ck_response_action_status"),)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    alert_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("alerts.id"), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)



class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(300), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),
        CheckConstraint("role IN ('org_admin', 'analyst', 'reviewer', 'viewer')", name="ck_membership_role"),
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class OrganizationInvitation(Base):
    __tablename__ = "organization_invitations"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    __table_args__ = (
        CheckConstraint("role IN ('org_admin', 'analyst', 'reviewer', 'viewer')", name="ck_invitation_role"),
    )

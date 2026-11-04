from datetime import date
from uuid import UUID
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db import get_db
from app.models import Organization, Community, WorkforceGroup, DataSource, HealthObservation, DetectionResult, Alert
from app.services.ingestion import parse_csv
from app.services.detection import robust_anomaly

app = FastAPI(title="PulseGrid Health API", version="0.2.0")
origins = [x.strip() for x in settings.cors_origins.split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_credentials=False,
    allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Authorization"],
)

def demo_only():
    if settings.app_env.lower() == "production":
        raise HTTPException(status_code=503, detail="production_auth_and_tenant_controls_required")

def _get_or_create_source(db: Session, code: str) -> DataSource:
    source = db.scalar(select(DataSource).where(DataSource.source_name == code))
    if source:
        return source
    source = DataSource(source_name=code, source_type="csv", provenance="Aggregate CSV upload; uploader must confirm authorisation", authorised=False)
    db.add(source)
    db.flush()
    return source

def _get_or_create_group(db: Session, row):
    org = db.scalar(select(Organization).where(Organization.name == "PulseGrid Demonstration"))
    if not org:
        org = Organization(name="PulseGrid Demonstration", organization_type="demo")
        db.add(org)
        db.flush()
    if row.domain == "community":
        group = db.scalar(select(Community).where(Community.organization_id == org.id, Community.region_code == row.group_code))
        if not group:
            group = Community(organization_id=org.id, name=f"Community {row.group_code}", region_code=row.group_code,
                              population_estimate=row.denominator)
            db.add(group)
            db.flush()
        elif row.denominator:
            group.population_estimate = max(group.population_estimate or 0, row.denominator)
        return org, group, None
    group = db.scalar(select(WorkforceGroup).where(WorkforceGroup.organization_id == org.id, WorkforceGroup.location_code == row.group_code))
    if not group:
        group = WorkforceGroup(organization_id=org.id, name=f"Workforce {row.group_code}", sector="unspecified",
                               location_code=row.group_code, cohort_size=row.denominator)
        db.add(group)
        db.flush()
    elif row.denominator:
        group.cohort_size = min(group.cohort_size or row.denominator, row.denominator)
    return org, None, group

def _detect_for_observation(db: Session, observation: HealthObservation) -> int:
    group_filter = (HealthObservation.community_id == observation.community_id) if observation.community_id else (HealthObservation.workforce_group_id == observation.workforce_group_id)
    history_rows = db.scalars(
        select(HealthObservation.value)
        .where(group_filter, HealthObservation.indicator == observation.indicator,
               HealthObservation.observed_date < observation.observed_date)
        .order_by(HealthObservation.observed_date.desc())
        .limit(max(settings.min_baseline_points, 26))
    ).all()
    history = [float(value) for value in reversed(history_rows)]
    result = robust_anomaly(history, float(observation.value),
                            min_history=settings.min_baseline_points,
                            threshold=settings.anomaly_z_threshold)
    detection = DetectionResult(
        observation_id=observation.id, baseline=result.baseline,
        anomaly_score=result.anomaly_score, reason=result.reason,
        threshold=settings.anomaly_z_threshold, history_count=len(history),
        model_name="median_mad", model_version="0.2.0",
    )
    db.add(detection)
    db.flush()
    if result.is_candidate:
        severity = "high" if (result.anomaly_score or 0) >= settings.anomaly_z_threshold * 2 else "medium"
        db.add(Alert(
            detection_id=detection.id,
            severity=severity, status="pending_review",
            explanation=f"{observation.indicator} measured {float(observation.value):g} {observation.unit}; historical median {result.baseline:g}; robust score {result.anomaly_score:g}. Candidate signal only; human review required."
        ))
        return 1
    return 0

@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.app_env, "version": app.version}

@app.get("/api/v1/dashboard")
def dashboard(db: Session = Depends(get_db)):
    demo_only()
    community_count = db.scalar(select(func.count()).select_from(HealthObservation).where(HealthObservation.community_id.is_not(None))) or 0
    workforce_count = db.scalar(select(func.count()).select_from(HealthObservation).join(WorkforceGroup).where(WorkforceGroup.cohort_size >= settings.min_workforce_cohort_size)) or 0
    alert_count = db.scalar(
        select(func.count()).select_from(Alert)
        .join(DetectionResult, Alert.detection_id == DetectionResult.id)
        .join(HealthObservation, DetectionResult.observation_id == HealthObservation.id)
        .outerjoin(WorkforceGroup, HealthObservation.workforce_group_id == WorkforceGroup.id)
        .where(Alert.status == "pending_review")
        .where(and_(
            HealthObservation.community_id.is_not(None)
            | (WorkforceGroup.cohort_size >= settings.min_workforce_cohort_size)
        ))
    ) or 0
    latest = db.execute(
        select(HealthObservation, Community.region_code, WorkforceGroup.location_code)
        .outerjoin(Community, HealthObservation.community_id == Community.id)
        .outerjoin(WorkforceGroup, HealthObservation.workforce_group_id == WorkforceGroup.id)
        .order_by(HealthObservation.observed_date.desc()).limit(12)
    ).all()
    observations = []
    for obs, community_code, workforce_code in latest:
        if obs.workforce_group_id:
            cohort = db.scalar(select(WorkforceGroup.cohort_size).where(WorkforceGroup.id == obs.workforce_group_id))
            if not cohort or cohort < settings.min_workforce_cohort_size:
                continue
        observations.append({
            "id": str(obs.id), "domain": "community" if obs.community_id else "workforce",
            "group_code": community_code or workforce_code, "observed_date": obs.observed_date.isoformat(),
            "indicator": obs.indicator, "value": float(obs.value), "unit": obs.unit
        })
    return {"community_observations": community_count, "workforce_observations": workforce_count,
            "pending_alerts": alert_count, "recent_observations": observations}

@app.get("/api/v1/alerts")
def list_alerts(status: str = Query(default="pending_review", max_length=30), limit: int = Query(default=50, ge=1, le=100), db: Session = Depends(get_db)):
    demo_only()
    rows = db.execute(
        select(Alert, DetectionResult, HealthObservation)
        .join(DetectionResult, Alert.detection_id == DetectionResult.id)
        .join(HealthObservation, DetectionResult.observation_id == HealthObservation.id)
        .where(Alert.status == status).order_by(Alert.created_at.desc()).limit(limit)
    ).all()
    result = []
    for alert, detection, obs in rows:
        group_code = None
        if obs.community_id:
            group_code = db.scalar(select(Community.region_code).where(Community.id == obs.community_id))
        else:
            group = db.scalar(select(WorkforceGroup).where(WorkforceGroup.id == obs.workforce_group_id))
            if not group or not group.cohort_size or group.cohort_size < settings.min_workforce_cohort_size:
                continue
            group_code = group.location_code
        result.append({
            "id": str(alert.id), "status": alert.status, "severity": alert.severity,
            "group_code": group_code, "domain": "community" if obs.community_id else "workforce",
            "observed_date": obs.observed_date.isoformat(), "indicator": obs.indicator,
            "value": float(obs.value), "unit": obs.unit, "baseline": detection.baseline,
            "score": detection.anomaly_score, "history_count": detection.history_count,
            "reason": detection.reason, "explanation": alert.explanation,
        })
    return {"items": result}

@app.post("/api/v1/observations/import")
async def import_observations(file: UploadFile = File(...), db: Session = Depends(get_db)):
    demo_only()
    if file.content_type not in ("text/csv", "application/vnd.ms-excel", "application/octet-stream"):
        raise HTTPException(status_code=415, detail="csv_only")
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    try:
        rows, errors = parse_csv(content, settings.max_upload_mb * 1024 * 1024)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    accepted = duplicates = alerts_created = 0
    try:
        # Process chronologically so each observation is evaluated only against prior dates.
        for row in sorted(rows, key=lambda item: (item.observed_date, item.domain, item.group_code, item.indicator)):
            source = _get_or_create_source(db, row.source_code)
            _, community, workforce = _get_or_create_group(db, row)
            if row.domain == "workforce" and workforce and workforce.cohort_size and workforce.cohort_size < settings.min_workforce_cohort_size:
                errors.append(f"{row.group_code}/{row.observed_date}: workforce_cohort_below_minimum")
                continue
            filters = [HealthObservation.source_id == source.id, HealthObservation.observed_date == row.observed_date,
                       HealthObservation.indicator == row.indicator]
            filters.append(HealthObservation.community_id == community.id if community else HealthObservation.workforce_group_id == workforce.id)
            existing = db.scalar(select(HealthObservation.id).where(*filters))
            if existing:
                duplicates += 1
                continue
            observation = HealthObservation(
                community_id=community.id if community else None,
                workforce_group_id=workforce.id if workforce else None,
                source_id=source.id, observed_date=row.observed_date,
                indicator=row.indicator, value=row.value, denominator=row.denominator, unit=row.unit,
            )
            db.add(observation)
            db.flush()
            alerts_created += _detect_for_observation(db, observation)
            accepted += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"accepted": accepted, "duplicates": duplicates, "rejected": len(errors),
            "alerts_created": alerts_created, "errors": errors[:50],
            "notice": "Aggregate observations only. Candidate alerts require human review."}

@app.post("/api/v1/detection/run")
def run_detection(db: Session = Depends(get_db)):
    demo_only()
    observations = db.scalars(
        select(HealthObservation).outerjoin(DetectionResult, DetectionResult.observation_id == HealthObservation.id)
        .where(DetectionResult.id.is_(None)).order_by(HealthObservation.observed_date.asc())
    ).all()
    alerts_created = 0
    for observation in observations:
        alerts_created += _detect_for_observation(db, observation)
    db.commit()
    return {"evaluated": len(observations), "alerts_created": alerts_created}

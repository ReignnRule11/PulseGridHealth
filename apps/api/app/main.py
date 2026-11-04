from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db import get_db
from app.models import Organization, Community, WorkforceGroup, DataSource, HealthObservation, DetectionResult, Alert
from app.security import router as security_router, get_request_tenant, enforce_roles, require_tenant_csrf
from app.review import router as review_router
from app.services.ingestion import parse_csv
from app.services.detection import robust_anomaly

app = FastAPI(title="PulseGrid Health API", version="0.4.0")
app.include_router(security_router)
app.include_router(review_router)
origins = [x.strip() for x in settings.cors_origins.split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token", "X-Organization-ID", "X-Bootstrap-Token"],
)


def _get_or_create_source(db: Session, code: str, organization_id) -> DataSource:
    scoped_name = f"{organization_id}:{code}"
    source = db.scalar(select(DataSource).where(
        DataSource.organization_id == organization_id, DataSource.source_name == scoped_name
    ))
    if source:
        return source
    source = DataSource(organization_id=organization_id, source_name=scoped_name, source_type="csv",
                        provenance="Aggregate CSV upload; uploader must confirm authorisation", authorised=False)
    db.add(source)
    db.flush()
    return source


def _get_or_create_group(db: Session, row, organization_id, cohort_size_hint=None):
    org = db.get(Organization, organization_id)
    if row.domain == "community":
        group = db.scalar(select(Community).where(
            Community.organization_id == organization_id, Community.region_code == row.group_code
        ))
        if not group:
            group = Community(organization_id=organization_id, name=f"Community {row.group_code}",
                              region_code=row.group_code, population_estimate=row.denominator)
            db.add(group)
            db.flush()
        elif row.denominator:
            group.population_estimate = max(group.population_estimate or 0, row.denominator)
        return org, group, None
    group = db.scalar(select(WorkforceGroup).where(
        WorkforceGroup.organization_id == organization_id, WorkforceGroup.location_code == row.group_code
    ))
    if not group:
        group = WorkforceGroup(organization_id=organization_id, name=f"Workforce {row.group_code}",
                               sector="unspecified", location_code=row.group_code,
                               cohort_size=row.denominator or cohort_size_hint)
        db.add(group)
        db.flush()
    else:
        known_size = row.denominator or cohort_size_hint
        if known_size:
            group.cohort_size = min(group.cohort_size or known_size, known_size)
    return org, None, group


def _detect_for_observation(db: Session, observation: HealthObservation) -> int:
    group_filter = (HealthObservation.community_id == observation.community_id
                    if observation.community_id else
                    HealthObservation.workforce_group_id == observation.workforce_group_id)
    history_rows = db.scalars(
        select(HealthObservation.value).where(
            HealthObservation.organization_id == observation.organization_id,
            group_filter, HealthObservation.indicator == observation.indicator,
            HealthObservation.observed_date < observation.observed_date,
        ).order_by(HealthObservation.observed_date.desc()).limit(max(settings.min_baseline_points, 26))
    ).all()
    history = [float(value) for value in reversed(history_rows)]
    result = robust_anomaly(history, float(observation.value),
                            min_history=settings.min_baseline_points, threshold=settings.anomaly_z_threshold)
    detection = DetectionResult(
        organization_id=observation.organization_id, observation_id=observation.id,
        baseline=result.baseline, anomaly_score=result.anomaly_score, reason=result.reason,
        threshold=settings.anomaly_z_threshold, history_count=len(history),
        model_name="median_mad", model_version="0.2.0",
    )
    db.add(detection)
    db.flush()
    if result.is_candidate:
        severity = "high" if (result.anomaly_score or 0) >= settings.anomaly_z_threshold * 2 else "medium"
        db.add(Alert(
            organization_id=observation.organization_id, detection_id=detection.id,
            severity=severity, status="pending_review",
            explanation=f"{observation.indicator} measured {float(observation.value):g} {observation.unit}; historical median {result.baseline:g}; robust score {result.anomaly_score:g}. Candidate signal only; human review required."
        ))
        return 1
    return 0


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.app_env, "version": app.version}


@app.get("/api/v1/dashboard")
def dashboard(context: dict = Depends(get_request_tenant), db: Session = Depends(get_db)):
    org_id = context["organization_id"]
    community_count = db.scalar(select(func.count()).select_from(HealthObservation).where(
        HealthObservation.organization_id == org_id, HealthObservation.community_id.is_not(None)
    )) or 0
    workforce_count = db.scalar(select(func.count()).select_from(HealthObservation)
        .join(WorkforceGroup, HealthObservation.workforce_group_id == WorkforceGroup.id)
        .where(HealthObservation.organization_id == org_id, WorkforceGroup.organization_id == org_id,
               WorkforceGroup.cohort_size >= settings.min_workforce_cohort_size)) or 0
    alert_count = db.scalar(select(func.count()).select_from(Alert)
        .join(DetectionResult, Alert.detection_id == DetectionResult.id)
        .join(HealthObservation, DetectionResult.observation_id == HealthObservation.id)
        .outerjoin(WorkforceGroup, HealthObservation.workforce_group_id == WorkforceGroup.id)
        .where(Alert.organization_id == org_id, Alert.status == "pending_review",
               or_(HealthObservation.community_id.is_not(None),
                   WorkforceGroup.cohort_size >= settings.min_workforce_cohort_size))) or 0
    latest = db.execute(select(HealthObservation, Community.region_code, WorkforceGroup.location_code)
        .outerjoin(Community, HealthObservation.community_id == Community.id)
        .outerjoin(WorkforceGroup, HealthObservation.workforce_group_id == WorkforceGroup.id)
        .where(HealthObservation.organization_id == org_id)
        .order_by(HealthObservation.observed_date.desc()).limit(12)).all()
    observations = []
    for obs, community_code, workforce_code in latest:
        if obs.workforce_group_id:
            cohort = db.scalar(select(WorkforceGroup.cohort_size).where(
                WorkforceGroup.id == obs.workforce_group_id, WorkforceGroup.organization_id == org_id))
            if not cohort or cohort < settings.min_workforce_cohort_size:
                continue
        observations.append({"id": str(obs.id), "domain": "community" if obs.community_id else "workforce",
            "group_code": community_code or workforce_code, "observed_date": obs.observed_date.isoformat(),
            "indicator": obs.indicator, "value": float(obs.value), "unit": obs.unit})
    return {"community_observations": community_count, "workforce_observations": workforce_count,
            "pending_alerts": alert_count, "recent_observations": observations}


@app.get("/api/v1/alerts")
def list_alerts(status: str = Query(default="pending_review", max_length=30),
                limit: int = Query(default=50, ge=1, le=100),
                context: dict = Depends(get_request_tenant), db: Session = Depends(get_db)):
    org_id = context["organization_id"]
    rows = db.execute(select(Alert, DetectionResult, HealthObservation)
        .join(DetectionResult, Alert.detection_id == DetectionResult.id)
        .join(HealthObservation, DetectionResult.observation_id == HealthObservation.id)
        .where(Alert.organization_id == org_id,
               Alert.status == status if status != "all" else True)
        .order_by(Alert.created_at.desc()).limit(limit)).all()
    result = []
    for alert, detection, obs in rows:
        if obs.community_id:
            group_code = db.scalar(select(Community.region_code).where(
                Community.id == obs.community_id, Community.organization_id == org_id))
        else:
            group = db.scalar(select(WorkforceGroup).where(
                WorkforceGroup.id == obs.workforce_group_id, WorkforceGroup.organization_id == org_id))
            if not group or not group.cohort_size or group.cohort_size < settings.min_workforce_cohort_size:
                continue
            group_code = group.location_code
        result.append({"id": str(alert.id), "status": alert.status, "severity": alert.severity,
            "group_code": group_code, "domain": "community" if obs.community_id else "workforce",
            "observed_date": obs.observed_date.isoformat(), "indicator": obs.indicator,
            "value": float(obs.value), "unit": obs.unit, "baseline": detection.baseline,
            "score": detection.anomaly_score, "history_count": detection.history_count,
            "reason": detection.reason, "explanation": alert.explanation})
    return {"items": result}


@app.post("/api/v1/observations/import")
async def import_observations(file: UploadFile = File(...),
                              context: dict = Depends(get_request_tenant),
                              csrf: bool = Depends(require_tenant_csrf), db: Session = Depends(get_db)):
    enforce_roles(context, "org_admin", "analyst")
    org_id = context["organization_id"]
    if file.content_type not in ("text/csv", "application/vnd.ms-excel", "application/octet-stream"):
        raise HTTPException(status_code=415, detail="csv_only")
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    try:
        rows, errors = parse_csv(content, settings.max_upload_mb * 1024 * 1024)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    accepted = duplicates = alerts_created = 0
    cohort_hints = {}
    for item in rows:
        if item.domain == "workforce" and item.denominator is not None:
            cohort_hints[item.group_code] = min(cohort_hints.get(item.group_code, item.denominator), item.denominator)
    try:
        for row in sorted(rows, key=lambda item: (item.observed_date, item.domain, item.group_code, item.indicator)):
            source = _get_or_create_source(db, row.source_code, org_id)
            _, community, workforce = _get_or_create_group(
                db, row, org_id, cohort_hints.get(row.group_code) if row.domain == "workforce" else None)
            if row.domain == "workforce" and workforce and (
                not workforce.cohort_size or workforce.cohort_size < settings.min_workforce_cohort_size):
                errors.append(f"{row.group_code}/{row.observed_date}: workforce_cohort_below_minimum")
                continue
            filters = [HealthObservation.organization_id == org_id, HealthObservation.source_id == source.id,
                       HealthObservation.observed_date == row.observed_date, HealthObservation.indicator == row.indicator]
            filters.append(HealthObservation.community_id == community.id if community
                           else HealthObservation.workforce_group_id == workforce.id)
            if db.scalar(select(HealthObservation.id).where(*filters)):
                duplicates += 1
                continue
            observation = HealthObservation(organization_id=org_id,
                community_id=community.id if community else None,
                workforce_group_id=workforce.id if workforce else None,
                source_id=source.id, observed_date=row.observed_date, indicator=row.indicator,
                value=row.value, denominator=row.denominator, unit=row.unit)
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
def run_detection(context: dict = Depends(get_request_tenant),
                  csrf: bool = Depends(require_tenant_csrf), db: Session = Depends(get_db)):
    enforce_roles(context, "org_admin", "analyst")
    org_id = context["organization_id"]
    observations = db.scalars(select(HealthObservation)
        .outerjoin(DetectionResult, DetectionResult.observation_id == HealthObservation.id)
        .where(HealthObservation.organization_id == org_id, DetectionResult.id.is_(None))
        .order_by(HealthObservation.observed_date.asc())).all()
    alerts_created = sum(_detect_for_observation(db, observation) for observation in observations)
    db.commit()
    return {"evaluated": len(observations), "alerts_created": alerts_created}


@app.get("/ready")
def readiness(db: Session = Depends(get_db)):
    """Readiness probe: confirm the API can reach its configured database."""
    from sqlalchemy.exc import SQLAlchemyError

    try:
        db.execute(select(1)).scalar_one()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="database_unavailable") from exc
    return {"status": "ready", "database": "reachable", "version": app.version}

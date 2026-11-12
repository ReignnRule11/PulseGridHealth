from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Alert, Investigation, ResponseAction, AuditLog, User, OrganizationMembership, Notification, DetectionResult, HealthObservation, Community, WorkforceGroup, DataImportBatch
from app.review_schemas import FindingsIn, ResolutionIn, ResponseActionIn
from app.security import get_request_tenant, enforce_roles, require_tenant_csrf

router = APIRouter(prefix="/api/v1/alerts", tags=["human review"])



class AssignmentIn(BaseModel):
    reviewer_user_id: UUID | None


@router.get("/inbox")
def reviewer_inbox(context: dict = Depends(get_request_tenant), db: Session = Depends(get_db)):
    enforce_roles(context, "org_admin", "reviewer")
    query = select(Alert, DetectionResult, HealthObservation, User, DataImportBatch).join(
        DetectionResult, Alert.detection_id == DetectionResult.id
    ).join(HealthObservation, DetectionResult.observation_id == HealthObservation.id
    ).outerjoin(User, Alert.assigned_to_user_id == User.id
    ).outerjoin(DataImportBatch, HealthObservation.import_batch_id == DataImportBatch.id
    ).where(Alert.organization_id == context["organization_id"])
    if context["role"] == "reviewer":
        query = query.where(
            (Alert.assigned_to_user_id == context["actor_user_id"]) |
            (Alert.assigned_to_user_id.is_(None))
        )
    rows = db.execute(query.order_by(Alert.created_at.desc()).limit(100)).all()
    items = []
    for alert, detection, observation, assignee, batch in rows:
        if observation.community_id:
            group_code = db.scalar(select(Community.region_code).where(
                Community.id == observation.community_id,
                Community.organization_id == context["organization_id"]))
            domain = "community"
        else:
            group = db.scalar(select(WorkforceGroup).where(
                WorkforceGroup.id == observation.workforce_group_id,
                WorkforceGroup.organization_id == context["organization_id"]))
            if not group or not group.cohort_size:
                continue
            group_code, domain = group.location_code, "workforce"
        items.append({
            "id": str(alert.id), "status": alert.status, "severity": alert.severity,
            "domain": domain, "group_code": group_code,
            "observed_date": observation.observed_date.isoformat(),
            "indicator": observation.indicator, "value": float(observation.value),
            "unit": observation.unit, "baseline": detection.baseline,
            "score": detection.anomaly_score, "explanation": alert.explanation,
            "assigned_to_user_id": str(alert.assigned_to_user_id) if alert.assigned_to_user_id else None,
            "assignee_name": assignee.full_name if assignee else None,
            "assignee_email": assignee.email if assignee else None,
            "uploaded_filename": batch.filename if batch else None,
        })
    return {"items": items}


@router.patch("/{alert_id}/assignment")
def assign_alert(alert_id: UUID, payload: AssignmentIn,
                 context: dict = Depends(get_request_tenant),
                 csrf: bool = Depends(require_tenant_csrf),
                 db: Session = Depends(get_db)):
    enforce_roles(context, "org_admin")
    alert = _alert(db, alert_id, context["organization_id"])
    reviewer = None
    if payload.reviewer_user_id:
        reviewer = db.scalar(
            select(User).join(OrganizationMembership, OrganizationMembership.user_id == User.id)
            .where(
                User.id == payload.reviewer_user_id, User.is_active.is_(True),
                OrganizationMembership.organization_id == context["organization_id"],
                OrganizationMembership.is_active.is_(True),
                OrganizationMembership.role.in_(["reviewer", "org_admin"]),
            )
        )
        if not reviewer:
            raise HTTPException(status_code=422, detail="assignee_must_be_active_reviewer_or_admin")
    before = str(alert.assigned_to_user_id) if alert.assigned_to_user_id else None
    alert.assigned_to_user_id = reviewer.id if reviewer else None
    alert.assigned_by_user_id = context["actor_user_id"]
    _audit(db, alert, context, "alert.assignment_changed", {
        "before_user_id": before,
        "after_user_id": str(reviewer.id) if reviewer else None,
    })
    if reviewer and reviewer.id != context["actor_user_id"]:
        db.add(Notification(
            organization_id=context["organization_id"], recipient_user_id=reviewer.id,
            kind="review_assignment", title="A candidate alert was assigned to you",
            message=f"{alert.severity.title()} priority candidate alert assigned for review.",
            related_type="alert", related_id=alert.id,
        ))
    db.commit()
    return {"alert_id": str(alert.id),
            "assigned_to_user_id": str(reviewer.id) if reviewer else None,
            "assignee_name": reviewer.full_name if reviewer else None}

def _alert(db: Session, alert_id: UUID, org_id) -> Alert:
    alert = db.scalar(select(Alert).where(Alert.id == alert_id, Alert.organization_id == org_id))
    if not alert:
        raise HTTPException(status_code=404, detail="alert_not_found")
    return alert


def _investigation(db: Session, alert_id: UUID, org_id) -> Investigation:
    item = db.scalar(select(Investigation).where(
        Investigation.alert_id == alert_id, Investigation.organization_id == org_id))
    if not item:
        raise HTTPException(status_code=409, detail="investigation_not_started")
    return item


def _audit(db: Session, alert: Alert, context: dict, event: str, detail: dict | None = None):
    db.add(AuditLog(organization_id=alert.organization_id, alert_id=alert.id,
        actor=context["actor"], event_type=event, detail=detail or {}))


@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: UUID, context: dict = Depends(get_request_tenant), csrf: bool = Depends(require_tenant_csrf), db: Session = Depends(get_db)):
    enforce_roles(context, "org_admin", "reviewer")
    alert = _alert(db, alert_id, context["organization_id"])
    if alert.status != "pending_review":
        raise HTTPException(status_code=409, detail="invalid_transition_expected_pending_review")
    alert.status = "acknowledged"
    _audit(db, alert, context, "alert.acknowledged")
    result = {"id": str(alert.id), "status": alert.status}
    db.commit()
    return result


@router.post("/{alert_id}/investigation")
def start_investigation(alert_id: UUID, context: dict = Depends(get_request_tenant), csrf: bool = Depends(require_tenant_csrf), db: Session = Depends(get_db)):
    enforce_roles(context, "org_admin", "reviewer")
    alert = _alert(db, alert_id, context["organization_id"])
    if alert.status != "acknowledged":
        raise HTTPException(status_code=409, detail="invalid_transition_expected_acknowledged")
    if db.scalar(select(Investigation.id).where(
        Investigation.alert_id == alert.id, Investigation.organization_id == context["organization_id"])):
        raise HTTPException(status_code=409, detail="investigation_already_exists")
    item = Investigation(organization_id=alert.organization_id, alert_id=alert.id,
                         status="in_progress", started_by=context["actor"])
    db.add(item)
    alert.status = "investigating"
    db.flush()
    _audit(db, alert, context, "investigation.started", {"investigation_id": str(item.id)})
    result = {"id": str(item.id), "alert_id": str(alert.id), "status": item.status}
    db.commit()
    return result


@router.post("/{alert_id}/findings")
def record_findings(alert_id: UUID, payload: FindingsIn,
                    context: dict = Depends(get_request_tenant), csrf: bool = Depends(require_tenant_csrf), db: Session = Depends(get_db)):
    enforce_roles(context, "org_admin", "reviewer")
    alert = _alert(db, alert_id, context["organization_id"])
    if alert.status != "investigating":
        raise HTTPException(status_code=409, detail="invalid_transition_expected_investigating")
    item = _investigation(db, alert.id, context["organization_id"])
    item.findings = payload.findings
    item.disposition = payload.disposition
    item.updated_at = datetime.now(timezone.utc)
    _audit(db, alert, context, "investigation.findings_recorded", {"disposition": payload.disposition})
    result = {"alert_id": str(alert.id), "disposition": item.disposition, "updated": True}
    db.commit()
    return result


@router.post("/{alert_id}/actions")
def add_response_action(alert_id: UUID, payload: ResponseActionIn,
                        context: dict = Depends(get_request_tenant), csrf: bool = Depends(require_tenant_csrf), db: Session = Depends(get_db)):
    enforce_roles(context, "org_admin", "reviewer")
    alert = _alert(db, alert_id, context["organization_id"])
    if alert.status != "investigating":
        raise HTTPException(status_code=409, detail="invalid_transition_expected_investigating")
    _investigation(db, alert.id, context["organization_id"])
    action = ResponseAction(organization_id=alert.organization_id, alert_id=alert.id,
        action_type=payload.action_type, description=payload.description,
        owner_role=payload.owner_role, due_date=payload.due_date, created_by=context["actor"])
    db.add(action)
    db.flush()
    _audit(db, alert, context, "response_action.created",
           {"action_id": str(action.id), "action_type": action.action_type})
    result = {"id": str(action.id), "status": action.status}
    db.commit()
    return result


@router.post("/{alert_id}/resolve")
def resolve_alert(alert_id: UUID, payload: ResolutionIn,
                  context: dict = Depends(get_request_tenant), csrf: bool = Depends(require_tenant_csrf), db: Session = Depends(get_db)):
    enforce_roles(context, "org_admin", "reviewer")
    alert = _alert(db, alert_id, context["organization_id"])
    if alert.status != "investigating":
        raise HTTPException(status_code=409, detail="invalid_transition_expected_investigating")
    item = _investigation(db, alert.id, context["organization_id"])
    item.resolution_rationale = payload.rationale
    item.disposition = payload.disposition
    item.status = "closed"
    item.closed_at = datetime.now(timezone.utc)
    item.updated_at = item.closed_at
    alert.status = "resolved"
    _audit(db, alert, context, "alert.resolved",
           {"disposition": payload.disposition, "rationale": payload.rationale})
    result = {"id": str(alert.id), "status": alert.status, "disposition": item.disposition}
    db.commit()
    return result


@router.get("/{alert_id}/history")
def alert_history(alert_id: UUID, context: dict = Depends(get_request_tenant), db: Session = Depends(get_db)):
    alert = _alert(db, alert_id, context["organization_id"])
    investigation = db.scalar(select(Investigation).where(
        Investigation.alert_id == alert.id, Investigation.organization_id == context["organization_id"]))
    actions = db.scalars(select(ResponseAction).where(
        ResponseAction.alert_id == alert.id, ResponseAction.organization_id == context["organization_id"]
    ).order_by(ResponseAction.created_at)).all()
    events = db.scalars(select(AuditLog).where(
        AuditLog.alert_id == alert.id, AuditLog.organization_id == context["organization_id"]
    ).order_by(AuditLog.created_at)).all()
    return {
        "alert": {"id": str(alert.id), "status": alert.status, "severity": alert.severity},
        "investigation": None if investigation is None else {
            "id": str(investigation.id), "status": investigation.status, "findings": investigation.findings,
            "disposition": investigation.disposition, "resolution_rationale": investigation.resolution_rationale},
        "response_actions": [{"id": str(a.id), "action_type": a.action_type, "description": a.description,
            "owner_role": a.owner_role, "due_date": a.due_date.isoformat() if a.due_date else None,
            "status": a.status} for a in actions],
        "audit_events": [{"event_type": e.event_type, "actor": e.actor, "detail": e.detail,
            "created_at": e.created_at.isoformat()} for e in events],
    }

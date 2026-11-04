from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models import Alert, Investigation, ResponseAction, AuditLog
from app.review_schemas import FindingsIn, ResolutionIn, ResponseActionIn

router = APIRouter(prefix="/api/v1/alerts", tags=["human review"])
DEMO_ACTOR = "demo-reviewer"


def _demo_only():
    if settings.app_env.lower() == "production":
        raise HTTPException(status_code=503, detail="production_auth_and_tenant_controls_required")


def _alert(db: Session, alert_id: UUID) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="alert_not_found")
    return alert


def _investigation(db: Session, alert_id: UUID) -> Investigation:
    item = db.scalar(select(Investigation).where(Investigation.alert_id == alert_id))
    if item is None:
        raise HTTPException(status_code=409, detail="investigation_not_started")
    return item


def _audit(db: Session, alert_id: UUID, event: str, detail: dict | None = None):
    db.add(AuditLog(alert_id=alert_id, actor=DEMO_ACTOR, event_type=event, detail=detail or {}))


def _commit(db: Session):
    db.commit()


@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: UUID, db: Session = Depends(get_db)):
    _demo_only()
    alert = _alert(db, alert_id)
    if alert.status != "pending_review":
        raise HTTPException(status_code=409, detail="invalid_transition_expected_pending_review")
    alert.status = "acknowledged"
    _audit(db, alert.id, "alert.acknowledged")
    _commit(db)
    return {"id": str(alert.id), "status": alert.status}


@router.post("/{alert_id}/investigation")
def start_investigation(alert_id: UUID, db: Session = Depends(get_db)):
    _demo_only()
    alert = _alert(db, alert_id)
    if alert.status != "acknowledged":
        raise HTTPException(status_code=409, detail="invalid_transition_expected_acknowledged")
    if db.scalar(select(Investigation.id).where(Investigation.alert_id == alert.id)):
        raise HTTPException(status_code=409, detail="investigation_already_exists")
    item = Investigation(alert_id=alert.id, status="in_progress", started_by=DEMO_ACTOR)
    db.add(item)
    alert.status = "investigating"
    db.flush()
    _audit(db, alert.id, "investigation.started", {"investigation_id": str(item.id)})
    _commit(db)
    return {"id": str(item.id), "alert_id": str(alert.id), "status": item.status}


@router.post("/{alert_id}/findings")
def record_findings(alert_id: UUID, payload: FindingsIn, db: Session = Depends(get_db)):
    _demo_only()
    alert = _alert(db, alert_id)
    if alert.status != "investigating":
        raise HTTPException(status_code=409, detail="invalid_transition_expected_investigating")
    item = _investigation(db, alert.id)
    item.findings = payload.findings
    item.disposition = payload.disposition
    item.updated_at = datetime.now(timezone.utc)
    _audit(db, alert.id, "investigation.findings_recorded", {"disposition": payload.disposition})
    _commit(db)
    return {"alert_id": str(alert.id), "disposition": item.disposition, "updated": True}


@router.post("/{alert_id}/actions")
def add_response_action(alert_id: UUID, payload: ResponseActionIn, db: Session = Depends(get_db)):
    _demo_only()
    alert = _alert(db, alert_id)
    if alert.status != "investigating":
        raise HTTPException(status_code=409, detail="invalid_transition_expected_investigating")
    _investigation(db, alert.id)
    due = date.fromisoformat(payload.due_date) if payload.due_date else None
    action = ResponseAction(alert_id=alert.id, action_type=payload.action_type,
                            description=payload.description, owner_role=payload.owner_role,
                            due_date=due, created_by=DEMO_ACTOR)
    db.add(action)
    db.flush()
    _audit(db, alert.id, "response_action.created", {"action_id": str(action.id), "action_type": action.action_type})
    _commit(db)
    return {"id": str(action.id), "status": action.status}


@router.post("/{alert_id}/resolve")
def resolve_alert(alert_id: UUID, payload: ResolutionIn, db: Session = Depends(get_db)):
    _demo_only()
    alert = _alert(db, alert_id)
    if alert.status != "investigating":
        raise HTTPException(status_code=409, detail="invalid_transition_expected_investigating")
    item = _investigation(db, alert.id)
    item.resolution_rationale = payload.rationale
    item.disposition = payload.disposition
    item.status = "closed"
    item.closed_at = datetime.now(timezone.utc)
    item.updated_at = item.closed_at
    alert.status = "resolved"
    _audit(db, alert.id, "alert.resolved", {"disposition": payload.disposition, "rationale": payload.rationale})
    _commit(db)
    return {"id": str(alert.id), "status": alert.status, "disposition": item.disposition}


@router.get("/{alert_id}/history")
def alert_history(alert_id: UUID, db: Session = Depends(get_db)):
    _demo_only()
    alert = _alert(db, alert_id)
    investigation = db.scalar(select(Investigation).where(Investigation.alert_id == alert.id))
    actions = db.scalars(select(ResponseAction).where(ResponseAction.alert_id == alert.id).order_by(ResponseAction.created_at)).all()
    events = db.scalars(select(AuditLog).where(AuditLog.alert_id == alert.id).order_by(AuditLog.created_at)).all()
    return {
        "alert": {"id": str(alert.id), "status": alert.status, "severity": alert.severity},
        "investigation": None if investigation is None else {
            "id": str(investigation.id), "status": investigation.status,
            "findings": investigation.findings, "disposition": investigation.disposition,
            "resolution_rationale": investigation.resolution_rationale,
        },
        "response_actions": [{"id": str(a.id), "action_type": a.action_type, "description": a.description,
                              "owner_role": a.owner_role, "due_date": a.due_date.isoformat() if a.due_date else None,
                              "status": a.status} for a in actions],
        "audit_events": [{"event_type": e.event_type, "actor": e.actor, "detail": e.detail,
                          "created_at": e.created_at.isoformat()} for e in events],
    }

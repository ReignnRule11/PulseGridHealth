from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DataImportBatch, Notification, OrganizationMembership, User
from app.security import get_request_tenant, enforce_roles, require_tenant_csrf

router = APIRouter(tags=["organization activity"])


@router.get("/api/v1/activity/uploads")
def upload_activity(context: dict = Depends(get_request_tenant), db: Session = Depends(get_db)):
    enforce_roles(context, "org_admin", "analyst")
    if context["is_demo"]:
        return {"items": []}
    query = select(DataImportBatch, User).join(
        User, DataImportBatch.uploaded_by_user_id == User.id
    ).where(DataImportBatch.organization_id == context["organization_id"])
    if context["role"] != "org_admin":
        query = query.where(DataImportBatch.uploaded_by_user_id == context["actor_user_id"])
    rows = db.execute(query.order_by(DataImportBatch.created_at.desc()).limit(100)).all()
    return {"items": [{
        "id": str(batch.id), "filename": batch.filename,
        "file_size_bytes": batch.file_size_bytes, "status": batch.status,
        "accepted": batch.accepted_count, "duplicates": batch.duplicate_count,
        "rejected": batch.rejected_count, "alerts_created": batch.alerts_created,
        "uploaded_by": user.full_name, "uploader_email": user.email,
        "created_at": batch.created_at.isoformat(),
    } for batch, user in rows]}


@router.get("/api/v1/notifications")
def list_notifications(context: dict = Depends(get_request_tenant), db: Session = Depends(get_db)):
    if context["is_demo"]:
        return {"items": [], "unread_count": 0}
    rows = db.scalars(select(Notification).where(
        Notification.organization_id == context["organization_id"],
        Notification.recipient_user_id == context["actor_user_id"],
    ).order_by(Notification.created_at.desc()).limit(50)).all()
    return {
        "unread_count": sum(1 for item in rows if not item.is_read),
        "items": [{
            "id": str(item.id), "kind": item.kind, "title": item.title,
            "message": item.message, "related_type": item.related_type,
            "related_id": str(item.related_id) if item.related_id else None,
            "is_read": item.is_read, "created_at": item.created_at.isoformat(),
        } for item in rows],
    }


@router.post("/api/v1/notifications/{notification_id}/read")
def mark_notification_read(notification_id: UUID,
                           context: dict = Depends(get_request_tenant),
                           csrf: bool = Depends(require_tenant_csrf),
                           db: Session = Depends(get_db)):
    if context["is_demo"]:
        raise HTTPException(status_code=404, detail="notification_not_found")
    item = db.scalar(select(Notification).where(
        Notification.id == notification_id,
        Notification.organization_id == context["organization_id"],
        Notification.recipient_user_id == context["actor_user_id"],
    ))
    if not item:
        raise HTTPException(status_code=404, detail="notification_not_found")
    if not item.is_read:
        item.is_read = True
        item.read_at = datetime.now(timezone.utc)
        db.commit()
    return {"id": str(item.id), "is_read": item.is_read}


@router.get("/api/v1/reviewers")
def list_reviewers(context: dict = Depends(get_request_tenant), db: Session = Depends(get_db)):
    enforce_roles(context, "org_admin")
    rows = db.execute(
        select(OrganizationMembership, User)
        .join(User, OrganizationMembership.user_id == User.id)
        .where(
            OrganizationMembership.organization_id == context["organization_id"],
            OrganizationMembership.is_active.is_(True),
            User.is_active.is_(True),
            OrganizationMembership.role.in_(["org_admin", "reviewer"]),
        )
        .order_by(User.full_name.asc())
    ).all()
    return {"items": [{
        "user_id": str(user.id), "full_name": user.full_name,
        "email": user.email, "role": membership.role,
    } for membership, user in rows]}

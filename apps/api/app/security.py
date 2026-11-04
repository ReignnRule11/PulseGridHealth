import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models import (
    AuthSession, Organization, OrganizationInvitation,
    OrganizationMembership, User,
)

router = APIRouter(prefix="/api/v1/auth", tags=["identity and access"])
SESSION_COOKIE = "pulsegrid_session"
CSRF_COOKIE = "pulsegrid_csrf"
ROLES = {"org_admin", "analyst", "reviewer", "viewer"}


class BootstrapIn(BaseModel):
    organization_name: str = Field(min_length=2, max_length=200)
    organization_type: str = Field(min_length=2, max_length=80)
    admin_email: str = Field(min_length=5, max_length=254)
    admin_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=12, max_length=256)


class LoginIn(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class InviteIn(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    role: str = Field(pattern="^(org_admin|analyst|reviewer|viewer)$")


class AcceptInviteIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=12, max_length=256)


def _now():
    return datetime.now(timezone.utc)


def _aware(value: datetime):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=64)
    return "scrypt$16384$8$1$" + salt.hex() + "$" + derived.hex()


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_hex, digest_hex = encoded.split("$")
        if algorithm != "scrypt":
            return False
        derived = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
                                 n=int(n), r=int(r), p=int(p), dklen=len(bytes.fromhex(digest_hex)))
        return hmac.compare_digest(derived.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def _origin_ok(request: Request):
    origin = request.headers.get("origin")
    allowed = {item.strip().rstrip("/") for item in settings.cors_origins.split(",") if item.strip()}
    if origin and origin.rstrip("/") not in allowed:
        raise HTTPException(status_code=403, detail="origin_not_allowed")
    if settings.app_env.lower() == "production" and not origin:
        raise HTTPException(status_code=403, detail="origin_required")


def _csrf_pre_auth(request: Request):
    _origin_ok(request)
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get("X-CSRF-Token")
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise HTTPException(status_code=403, detail="csrf_validation_failed")


def _set_session_cookies(response: Response, session_token: str, csrf_token: str):
    secure = settings.app_env.lower() == "production"
    response.set_cookie(SESSION_COOKIE, session_token, httponly=True, secure=secure,
                        samesite="strict", max_age=settings.session_ttl_hours * 3600, path="/")
    response.set_cookie(CSRF_COOKIE, csrf_token, httponly=False, secure=secure,
                        samesite="strict", max_age=settings.session_ttl_hours * 3600, path="/")


def get_identity(request: Request, db: Session = Depends(get_db)):
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        raise HTTPException(status_code=401, detail="authentication_required")
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == _hash_token(raw)))
    if not session or session.revoked_at or _aware(session.expires_at) <= _now():
        raise HTTPException(status_code=401, detail="session_invalid_or_expired")
    user = db.get(User, session.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="account_inactive")
    return {"user": user, "session": session}


def get_membership(
    x_organization_id: str = Header(..., alias="X-Organization-ID"),
    identity: dict = Depends(get_identity),
    db: Session = Depends(get_db),
):
    try:
        organization_id = UUID(x_organization_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_organization_id") from exc
    membership = db.scalar(select(OrganizationMembership).where(
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.user_id == identity["user"].id,
        OrganizationMembership.is_active.is_(True),
    ))
    if not membership:
        raise HTTPException(status_code=403, detail="organization_access_denied")
    return {"identity": identity, "membership": membership}


def require_roles(*roles: str):
    def dependency(context: dict = Depends(get_membership)):
        if context["membership"].role not in roles:
            raise HTTPException(status_code=403, detail="insufficient_role")
        return context
    return dependency


def require_csrf(request: Request, identity: dict = Depends(get_identity)):
    _origin_ok(request)
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get("X-CSRF-Token")
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise HTTPException(status_code=403, detail="csrf_validation_failed")
    if not hmac.compare_digest(_hash_token(cookie), identity["session"].csrf_hash):
        raise HTTPException(status_code=403, detail="csrf_session_mismatch")
    return True


@router.get("/csrf")
def issue_csrf(response: Response, request: Request, db: Session = Depends(get_db)):
    _origin_ok(request)
    token = secrets.token_urlsafe(32)
    raw_session = request.cookies.get(SESSION_COOKIE)
    if raw_session:
        active_session = db.scalar(select(AuthSession).where(AuthSession.token_hash == _hash_token(raw_session)))
        if active_session and not active_session.revoked_at and _aware(active_session.expires_at) > _now():
            active_session.csrf_hash = _hash_token(token)
            db.commit()
    secure = settings.app_env.lower() == "production"
    response.set_cookie(CSRF_COOKIE, token, httponly=False, secure=secure, samesite="strict", path="/")
    return {"csrf_token": token}


@router.post("/bootstrap")
def bootstrap(payload: BootstrapIn, request: Request, response: Response,
              x_bootstrap_token: str = Header(default="", alias="X-Bootstrap-Token"),
              db: Session = Depends(get_db)):
    _csrf_pre_auth(request)
    configured = settings.bootstrap_token
    if not configured or not hmac.compare_digest(x_bootstrap_token, configured):
        raise HTTPException(status_code=403, detail="bootstrap_not_authorized")
    email = payload.admin_email.strip().lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="email_already_registered")
    if db.scalar(select(Organization.id).where(Organization.name == payload.organization_name.strip())):
        raise HTTPException(status_code=409, detail="organization_already_exists")
    organization = Organization(name=payload.organization_name.strip(), organization_type=payload.organization_type.strip())
    user = User(email=email, full_name=payload.admin_name.strip(), password_hash=_hash_password(payload.password))
    db.add_all([organization, user])
    db.flush()
    db.add(OrganizationMembership(organization_id=organization.id, user_id=user.id, role="org_admin"))
    db.commit()
    return {"organization_id": str(organization.id), "user_id": str(user.id), "status": "created"}


@router.post("/login")
def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    _csrf_pre_auth(request)
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    generic = HTTPException(status_code=401, detail="invalid_credentials")
    if not user or not user.is_active:
        raise generic
    now = _now()
    if user.locked_until and _aware(user.locked_until) > now:
        raise HTTPException(status_code=429, detail="account_temporarily_locked")
    if not _verify_password(payload.password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= 5:
            user.failed_login_count = 0
            user.locked_until = now + timedelta(minutes=15)
        db.commit()
        raise generic
    user.failed_login_count = 0
    user.locked_until = None
    session_token = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)
    auth_session = AuthSession(user_id=user.id, token_hash=_hash_token(session_token),
                               csrf_hash=_hash_token(csrf_token),
                               expires_at=now + timedelta(hours=settings.session_ttl_hours))
    db.add(auth_session)
    db.commit()
    _set_session_cookies(response, session_token, csrf_token)
    memberships = db.scalars(select(OrganizationMembership).where(
        OrganizationMembership.user_id == user.id, OrganizationMembership.is_active.is_(True)
    )).all()
    return {"user": {"id": str(user.id), "email": user.email, "full_name": user.full_name},
            "organizations": [{"id": str(m.organization_id), "role": m.role} for m in memberships]}


@router.post("/logout")
def logout(request: Request, response: Response, identity: dict = Depends(get_identity),
           csrf: bool = Depends(require_csrf), db: Session = Depends(get_db)):
    identity["session"].revoked_at = _now()
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/", secure=settings.app_env.lower() == "production",
                           httponly=True, samesite="strict")
    response.delete_cookie(CSRF_COOKIE, path="/", secure=settings.app_env.lower() == "production",
                           httponly=False, samesite="strict")
    return {"status": "signed_out"}


@router.get("/me")
def me(identity: dict = Depends(get_identity), db: Session = Depends(get_db)):
    user = identity["user"]
    memberships = db.scalars(select(OrganizationMembership).where(
        OrganizationMembership.user_id == user.id, OrganizationMembership.is_active.is_(True)
    )).all()
    organizations = []
    for membership in memberships:
        organization = db.get(Organization, membership.organization_id)
        if organization:
            organizations.append({"id": str(organization.id), "name": organization.name, "role": membership.role})
    return {"id": str(user.id), "email": user.email, "full_name": user.full_name,
            "organizations": organizations, "session_expires_at": identity["session"].expires_at.isoformat()}


@router.post("/organizations/{organization_id}/invitations")
def create_invitation(organization_id: UUID, payload: InviteIn, request: Request,
                      context: dict = Depends(require_roles("org_admin")),
                      csrf: bool = Depends(require_csrf), db: Session = Depends(get_db)):
    _origin_ok(request)
    membership = context["membership"]
    if membership.organization_id != organization_id:
        raise HTTPException(status_code=403, detail="organization_access_denied")
    email = payload.email.strip().lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="email_already_registered")
    existing = db.scalar(select(OrganizationInvitation.id).where(
        OrganizationInvitation.organization_id == organization_id,
        OrganizationInvitation.email == email,
        OrganizationInvitation.accepted_at.is_(None),
        OrganizationInvitation.expires_at > _now(),
    ))
    if existing:
        raise HTTPException(status_code=409, detail="active_invitation_exists")
    raw_token = secrets.token_urlsafe(36)
    invitation = OrganizationInvitation(
        organization_id=organization_id, email=email, role=payload.role,
        token_hash=_hash_token(raw_token),
        expires_at=_now() + timedelta(hours=settings.invitation_ttl_hours),
        created_by=context["identity"]["user"].id,
    )
    db.add(invitation)
    db.commit()
    return {"invitation_id": str(invitation.id), "email": email, "role": payload.role,
            "expires_at": invitation.expires_at.isoformat(), "invitation_token": raw_token,
            "delivery": "manual_secure_delivery_required"}


@router.post("/invitations/accept")
def accept_invitation(payload: AcceptInviteIn, request: Request, db: Session = Depends(get_db)):
    _csrf_pre_auth(request)
    invitation = db.scalar(select(OrganizationInvitation).where(
        OrganizationInvitation.token_hash == _hash_token(payload.token)
    ).with_for_update())
    if not invitation or invitation.accepted_at or _aware(invitation.expires_at) <= _now():
        raise HTTPException(status_code=400, detail="invitation_invalid_or_expired")
    if db.scalar(select(User.id).where(User.email == invitation.email)):
        raise HTTPException(status_code=409, detail="email_already_registered")
    user = User(email=invitation.email, full_name=payload.full_name.strip(),
                password_hash=_hash_password(payload.password))
    db.add(user)
    db.flush()
    db.add(OrganizationMembership(organization_id=invitation.organization_id, user_id=user.id, role=invitation.role))
    invitation.accepted_at = _now()
    db.commit()
    return {"status": "accepted", "user_id": str(user.id), "organization_id": str(invitation.organization_id)}

import hashlib
import hmac
import secrets
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models import (
    AuthSession, Organization, OrganizationInvitation,
    OrganizationMembership, User, AccountActionToken,
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

    # Serialize first-run attempts in PostgreSQL so two concurrent requests cannot
    # both observe an empty installation and create separate initial administrators.
    if db.bind and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"),
                   {"lock_key": 0x50554C5345424F4F})

    # Bootstrap is only for the first organization and its first org_admin.
    # Additional users must enter through an administrator-issued invitation.
    if db.scalar(select(User.id).limit(1)) or db.scalar(select(Organization.id).limit(1)):
        db.rollback()
        raise HTTPException(status_code=409, detail="bootstrap_already_completed")

    email = payload.admin_email.strip().lower()
    organization = Organization(name=payload.organization_name.strip(),
                                 organization_type=payload.organization_type.strip())
    user = User(email=email, full_name=payload.admin_name.strip(),
                password_hash=_hash_password(payload.password))
    try:
        db.add_all([organization, user])
        db.flush()
        db.add(OrganizationMembership(organization_id=organization.id, user_id=user.id, role="org_admin"))
        db.commit()
    except Exception:
        db.rollback()
        raise
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
            organizations.append({"id": str(organization.id), "name": organization.name, "organization_type": organization.organization_type, "role": membership.role})
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



def get_request_tenant(
    request: Request,
    x_organization_id: str | None = Header(default=None, alias="X-Organization-ID"),
    db: Session = Depends(get_db),
):
    raw = request.cookies.get(SESSION_COOKIE)
    actor = "demo-reviewer"
    is_demo = False
    if raw:
        auth_session = db.scalar(select(AuthSession).where(AuthSession.token_hash == _hash_token(raw)))
        if not auth_session or auth_session.revoked_at or _aware(auth_session.expires_at) <= _now():
            raise HTTPException(status_code=401, detail="session_invalid_or_expired")
        user = db.get(User, auth_session.user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="account_inactive")
        if not x_organization_id:
            raise HTTPException(status_code=400, detail="organization_header_required")
        try:
            organization_id = UUID(x_organization_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid_organization_id") from exc
        membership = db.scalar(select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.is_active.is_(True),
        ))
        if not membership:
            raise HTTPException(status_code=403, detail="organization_access_denied")
        role = membership.role
        actor = user.email
    else:
        if settings.app_env.lower() == "production":
            raise HTTPException(status_code=401, detail="authentication_required")
        organization = db.scalar(select(Organization).where(Organization.name == "PulseGrid Demonstration"))
        if not organization:
            organization = Organization(name="PulseGrid Demonstration", organization_type="demo")
            db.add(organization)
            db.flush()
        organization_id = organization.id
        role = "demo"
        is_demo = True
    if db.bind and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT set_config('app.organization_id', :organization_id, true)"),
                   {"organization_id": str(organization_id)})
    return {"organization_id": organization_id, "role": role, "actor": actor, "is_demo": is_demo, "csrf_hash": auth_session.csrf_hash if raw else None}


def enforce_roles(context: dict, *allowed: str):
    if context["is_demo"]:
        return
    if context["role"] not in allowed:
        raise HTTPException(status_code=403, detail="insufficient_role")


def require_tenant_csrf(request: Request, context: dict = Depends(get_request_tenant)):
    if context["is_demo"]:
        return True
    _origin_ok(request)
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get("X-CSRF-Token")
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise HTTPException(status_code=403, detail="csrf_validation_failed")
    if not hmac.compare_digest(_hash_token(cookie), context["csrf_hash"] or ""):
        raise HTTPException(status_code=403, detail="csrf_session_mismatch")
    return True


# Account management ---------------------------------------------------------
class ProfileUpdateIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class EmailChangeRequestIn(BaseModel):
    new_email: str = Field(min_length=5, max_length=254)
    current_password: str = Field(min_length=1, max_length=256)


class TokenIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class PasswordResetRequestIn(BaseModel):
    email: str = Field(min_length=5, max_length=254)


class PasswordResetIn(TokenIn):
    new_password: str = Field(min_length=12, max_length=256)


class OrganizationUpdateIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    organization_type: str = Field(min_length=2, max_length=80)


def _send_account_email(recipient: str, subject: str, body: str):
    if not settings.smtp_host or not settings.smtp_from_email:
        raise HTTPException(status_code=503, detail="email_delivery_not_configured")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            if settings.smtp_starttls:
                server.starttls()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise HTTPException(status_code=502, detail="email_delivery_failed") from exc


def _issue_account_token(db: Session, user: User, purpose: str, ttl_minutes: int = 30) -> str:
    # Invalidate older outstanding tokens for the same purpose.
    db.query(AccountActionToken).filter(
        AccountActionToken.user_id == user.id,
        AccountActionToken.purpose == purpose,
        AccountActionToken.used_at.is_(None),
    ).update({"used_at": _now()}, synchronize_session=False)
    raw = secrets.token_urlsafe(36)
    db.add(AccountActionToken(
        user_id=user.id, purpose=purpose, token_hash=_hash_token(raw),
        expires_at=_now() + timedelta(minutes=ttl_minutes),
    ))
    db.flush()
    return raw


def _consume_account_token(db: Session, raw: str, purpose: str):
    token = db.scalar(select(AccountActionToken).where(
        AccountActionToken.token_hash == _hash_token(raw),
        AccountActionToken.purpose == purpose,
    ).with_for_update())
    if not token or token.used_at or _aware(token.expires_at) <= _now():
        raise HTTPException(status_code=400, detail="token_invalid_or_expired")
    user = db.get(User, token.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="account_unavailable")
    token.used_at = _now()
    return user


@router.patch("/profile")
def update_profile(payload: ProfileUpdateIn, identity: dict = Depends(get_identity),
                   csrf: bool = Depends(require_csrf), db: Session = Depends(get_db)):
    user = identity["user"]
    user.full_name = payload.full_name.strip()
    db.commit()
    return {"id": str(user.id), "full_name": user.full_name, "email": user.email}


@router.post("/password/change")
def change_password(payload: PasswordChangeIn, identity: dict = Depends(get_identity),
                    csrf: bool = Depends(require_csrf), db: Session = Depends(get_db)):
    user = identity["user"]
    if not _verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="current_password_incorrect")
    if hmac.compare_digest(payload.current_password, payload.new_password):
        raise HTTPException(status_code=400, detail="new_password_must_be_different")
    user.password_hash = _hash_password(payload.new_password)
    # Revoke every other session; retain the session used to change the password.
    db.query(AuthSession).filter(
        AuthSession.user_id == user.id,
        AuthSession.id != identity["session"].id,
        AuthSession.revoked_at.is_(None),
    ).update({"revoked_at": _now()}, synchronize_session=False)
    db.commit()
    return {"status": "password_changed", "other_sessions_revoked": True}


@router.post("/email/change/request")
def request_email_change(payload: EmailChangeRequestIn, request: Request,
                         identity: dict = Depends(get_identity),
                         csrf: bool = Depends(require_csrf), db: Session = Depends(get_db)):
    _origin_ok(request)
    user = identity["user"]
    if not _verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="current_password_incorrect")
    new_email = payload.new_email.strip().lower()
    if new_email == user.email:
        raise HTTPException(status_code=400, detail="email_unchanged")
    if db.scalar(select(User.id).where(User.email == new_email)):
        raise HTTPException(status_code=409, detail="email_already_registered")
    raw = _issue_account_token(db, user, "email_change")
    db.commit()
    _send_account_email(new_email, "Confirm your PulseGrid Health email change",
        f"Someone requested to change your PulseGrid Health account email to this address. "
        f"If this was you, confirm within 30 minutes using this token:\n\n{raw}\n\n"
        "If you did not request this, ignore this email.")
    # The requested address is stored only after confirmation; token is never returned.
    pending = db.scalar(select(AccountActionToken).where(
        AccountActionToken.token_hash == _hash_token(raw), AccountActionToken.purpose == "email_change"))
    pending.payload = new_email
    db.commit()
    return {"status": "verification_sent", "message": "Check the new email address to confirm the change."}


@router.post("/email/change/confirm")
def confirm_email_change(payload: TokenIn, identity: dict = Depends(get_identity),
                         csrf: bool = Depends(require_csrf), db: Session = Depends(get_db)):
    user = identity["user"]
    token = db.scalar(select(AccountActionToken).where(
        AccountActionToken.token_hash == _hash_token(payload.token),
        AccountActionToken.purpose == "email_change",
    ).with_for_update())
    if not token or token.used_at or _aware(token.expires_at) <= _now():
        raise HTTPException(status_code=400, detail="token_invalid_or_expired")
    new_email = token.payload
    if not new_email or db.scalar(select(User.id).where(User.email == new_email)):
        raise HTTPException(status_code=409, detail="email_already_registered")
    if token.user_id != user.id:
        raise HTTPException(status_code=403, detail="token_account_mismatch")
    user.email = new_email
    token.used_at = _now()
    db.query(AuthSession).filter(
        AuthSession.user_id == user.id,
        AuthSession.id != identity["session"].id,
        AuthSession.revoked_at.is_(None),
    ).update({"revoked_at": _now()}, synchronize_session=False)
    db.commit()
    return {"status": "email_changed", "email": user.email, "other_sessions_revoked": True}


@router.post("/password/forgot")
def request_password_reset(payload: PasswordResetRequestIn, request: Request,
                           db: Session = Depends(get_db)):
    _csrf_pre_auth(request)
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
    # Always return the same response for known and unknown addresses.
    if user:
        raw = _issue_account_token(db, user, "password_reset")
        db.commit()
        try:
            _send_account_email(email, "Reset your PulseGrid Health password",
                f"A password reset was requested for your account. Use this one-time token "
                f"within 30 minutes in the PulseGrid Health password reset screen:\n\n{raw}\n\n"
                "If you did not request this, ignore this email.")
        except HTTPException:
            # Do not expose account existence; log-free fail closed.
            pass
    return {"status": "if_account_exists_email_sent"}


@router.post("/password/reset")
def reset_password(payload: PasswordResetIn, request: Request, db: Session = Depends(get_db)):
    _csrf_pre_auth(request)
    user = _consume_account_token(db, payload.token, "password_reset")
    user.password_hash = _hash_password(payload.new_password)
    db.query(AuthSession).filter(
        AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)
    ).update({"revoked_at": _now()}, synchronize_session=False)
    db.commit()
    return {"status": "password_reset", "sessions_revoked": True}


@router.patch("/organizations/{organization_id}")
def update_organization(organization_id: UUID, payload: OrganizationUpdateIn,
                        context: dict = Depends(require_roles("org_admin")),
                        csrf: bool = Depends(require_csrf), db: Session = Depends(get_db)):
    membership = context["membership"]
    if membership.organization_id != organization_id:
        raise HTTPException(status_code=403, detail="organization_access_denied")
    organization = db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="organization_not_found")
    name = payload.name.strip()
    duplicate = db.scalar(select(Organization.id).where(
        Organization.name == name, Organization.id != organization_id))
    if duplicate:
        raise HTTPException(status_code=409, detail="organization_name_already_used")
    organization.name = name
    organization.organization_type = payload.organization_type.strip()
    db.commit()
    return {"id": str(organization.id), "name": organization.name,
            "organization_type": organization.organization_type}

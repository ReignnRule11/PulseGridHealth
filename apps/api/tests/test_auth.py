import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db import Base, get_db
from app.main import app
from app.models import Organization, OrganizationMembership, User
from app.security import _hash_password


@pytest.fixture()
def auth_client(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "test")
    monkeypatch.setattr(settings, "bootstrap_token", "test-bootstrap-secret")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _csrf(client):
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return response.json()["csrf_token"]


def _bootstrap(client, email="admin@example.org"):
    token = _csrf(client)
    return client.post("/api/v1/auth/bootstrap", headers={
        "X-CSRF-Token": token, "X-Bootstrap-Token": "test-bootstrap-secret"
    }, json={
        "organization_name": "Example Health Authority",
        "organization_type": "public_health",
        "admin_email": email,
        "admin_name": "Organization Admin",
        "password": "Strong-Password-2026!",
    })


def _login(client, email="admin@example.org", password="Strong-Password-2026!"):
    token = _csrf(client)
    return client.post("/api/v1/auth/login", headers={"X-CSRF-Token": token}, json={
        "email": email, "password": password
    })


def test_bootstrap_login_me_and_logout(auth_client):
    client = auth_client
    assert _bootstrap(client).status_code == 200
    login = _login(client)
    assert login.status_code == 200
    organization_id = login.json()["organizations"][0]["id"]
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["organizations"][0]["id"] == organization_id
    csrf = client.cookies.get("pulsegrid_csrf")
    logout = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert logout.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_bootstrap_is_one_time_only(auth_client):
    client = auth_client
    first = _bootstrap(client)
    assert first.status_code == 200

    token = _csrf(client)
    second = client.post("/api/v1/auth/bootstrap", headers={
        "X-CSRF-Token": token, "X-Bootstrap-Token": "test-bootstrap-secret"
    }, json={
        "organization_name": "Second Health Authority",
        "organization_type": "public_health",
        "admin_email": "second-admin@example.org",
        "admin_name": "Second Administrator",
        "password": "Another-Strong-Password-2026!",
    })
    assert second.status_code == 409
    assert second.json()["detail"] == "bootstrap_already_completed"


def test_bootstrap_is_closed_without_secret(auth_client, monkeypatch):
    monkeypatch.setattr(settings, "bootstrap_token", "")
    client = auth_client
    csrf = _csrf(client)
    response = client.post("/api/v1/auth/bootstrap", headers={"X-CSRF-Token": csrf}, json={
        "organization_name": "Unauthorized Org", "organization_type": "other",
        "admin_email": "bad@example.org", "admin_name": "Bad Actor",
        "password": "Strong-Password-2026!",
    })
    assert response.status_code == 403


def test_org_admin_can_issue_single_use_invitation(auth_client):
    client = auth_client
    assert _bootstrap(client).status_code == 200
    login = _login(client)
    organization_id = login.json()["organizations"][0]["id"]
    csrf = client.cookies.get("pulsegrid_csrf")
    invite = client.post(f"/api/v1/auth/organizations/{organization_id}/invitations",
        headers={"X-CSRF-Token": csrf, "X-Organization-ID": organization_id},
        json={"email": "reviewer@example.org", "role": "reviewer"})
    assert invite.status_code == 200, invite.text
    data = invite.json()
    assert data["delivery"] == "manual_secure_delivery_required"
    token = data["invitation_token"]
    preauth_csrf = _csrf(client)
    accepted = client.post("/api/v1/auth/invitations/accept",
        headers={"X-CSRF-Token": preauth_csrf},
        json={"token": token, "full_name": "Health Reviewer", "password": "Another-Strong-2026!"})
    assert accepted.status_code == 200, accepted.text
    assert client.post("/api/v1/auth/invitations/accept",
        headers={"X-CSRF-Token": preauth_csrf},
        json={"token": token, "full_name": "Health Reviewer", "password": "Another-Strong-2026!"}).status_code == 400


def test_membership_is_required_for_selected_organization(auth_client):
    client = auth_client
    assert _bootstrap(client).status_code == 200
    _login(client)
    response = client.get("/api/v1/auth/me")
    organization_id = response.json()["organizations"][0]["id"]
    denied = client.post(f"/api/v1/auth/organizations/{organization_id}/invitations",
        headers={"X-CSRF-Token": client.cookies.get("pulsegrid_csrf"),
                 "X-Organization-ID": "00000000-0000-0000-0000-000000000001"},
        json={"email": "outsider@example.org", "role": "viewer"})
    assert denied.status_code == 403



def test_organization_data_isolation_and_membership_enforcement(auth_client):
    import io
    client = auth_client
    assert _bootstrap(client, email="first-admin@example.org").status_code == 200
    first_login = _login(client, email="first-admin@example.org")
    first_org = first_login.json()["organizations"][0]["id"]
    csrf = _csrf(client)
    # Seed a second tenant directly for this isolation test. The public bootstrap
    # endpoint is intentionally one-time and must not be used for tenant creation.
    db_dependency = app.dependency_overrides[get_db]()
    db = next(db_dependency)
    try:
        second_organization = Organization(
            name="Second Health Authority", organization_type="public_health")
        second_user = User(
            email="second-admin@example.org", full_name="Second Admin",
            password_hash=_hash_password("Second-Strong-Password-2026!"))
        db.add_all([second_organization, second_user])
        db.flush()
        db.add(OrganizationMembership(
            organization_id=second_organization.id, user_id=second_user.id, role="org_admin"))
        db.commit()
        second_org = str(second_organization.id)
    finally:
        db_dependency.close()
    csrf = _csrf(client)
    rows = "domain,group_code,source_code,observed_date,indicator,value,denominator,unit\n"
    rows += "".join(f"community,ONLY-FIRST,SRC,2026-06-{day:02d},weekly_reports,{value},5000,reports\n"
                    for day, value in [(1,10),(2,11),(3,9),(4,10),(5,11),(6,10),(7,9),(8,35)])
    imported = client.post("/api/v1/observations/import",
        headers={"X-CSRF-Token": csrf, "X-Organization-ID": first_org},
        files={"file": ("tenant.csv", io.BytesIO(rows.encode()), "text/csv")})
    assert imported.status_code == 200, imported.text
    assert imported.json()["accepted"] == 8
    assert _login(client, email="second-admin@example.org", password="Second-Strong-Password-2026!").status_code == 200
    dashboard = client.get("/api/v1/dashboard", headers={"X-Organization-ID": second_org})
    assert dashboard.status_code == 200
    assert dashboard.json()["community_observations"] == 0
    assert dashboard.json()["pending_alerts"] == 0
    denied = client.get("/api/v1/dashboard", headers={"X-Organization-ID": first_org})
    assert denied.status_code == 403

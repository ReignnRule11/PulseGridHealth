import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db import Base, get_db
from app.main import app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "test")
    monkeypatch.setattr(settings, "bootstrap_token", "workspace-test-bootstrap")
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
    with TestClient(app) as test_client:
        test_client.testing_session = testing_session
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def csrf(client):
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return response.json()["csrf_token"]


def bootstrap(client):
    token = csrf(client)
    response = client.post("/api/v1/auth/bootstrap", headers={
        "X-CSRF-Token": token, "X-Bootstrap-Token": "workspace-test-bootstrap",
    }, json={
        "organization_name": "Workspace Test Authority",
        "organization_type": "public_health",
        "admin_email": "admin@workspace.test",
        "admin_name": "Workspace Administrator",
        "password": "Admin-Password-2026!",
    })
    assert response.status_code == 200, response.text
    return response.json()["organization_id"]


def login(client, email, password):
    token = csrf(client)
    response = client.post("/api/v1/auth/login", headers={"X-CSRF-Token": token},
                           json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    # Rotate the authenticated session's CSRF secret before subsequent writes.
    token = csrf(client)
    return response.json(), token


def invite(client, organization_id, email, role, token):
    response = client.post(
        f"/api/v1/auth/organizations/{organization_id}/invitations",
        headers={"X-Organization-ID": organization_id, "X-CSRF-Token": token},
        json={"email": email, "role": role},
    )
    assert response.status_code == 200, response.text
    return response.json()["invitation_token"]


def accept(client, token, name, password):
    csrf_token = csrf(client)
    response = client.post("/api/v1/auth/invitations/accept",
        headers={"X-CSRF-Token": csrf_token},
        json={"token": token, "full_name": name, "password": password})
    assert response.status_code == 200, response.text


def test_role_scoped_workspace_reads_ingestion_review_and_csrf(client):
    organization_id = bootstrap(client)
    admin, admin_csrf = login(client, "admin@workspace.test", "Admin-Password-2026!")

    reviewer_token = invite(client, organization_id, "reviewer@workspace.test", "reviewer", admin_csrf)
    analyst_token = invite(client, organization_id, "analyst@workspace.test", "analyst", admin_csrf)
    viewer_token = invite(client, organization_id, "viewer@workspace.test", "viewer", admin_csrf)
    accept(client, reviewer_token, "Health Reviewer", "Reviewer-Password-2026!")
    accept(client, analyst_token, "Data Analyst", "Analyst-Password-2026!")
    accept(client, viewer_token, "Read Only Viewer", "Viewer-Password-2026!")
    # Invitation acceptance is a pre-auth flow; refresh the current admin browser token.
    admin_csrf = csrf(client)

    # Seed a candidate alert as the organization administrator.
    rows = "domain,group_code,source_code,observed_date,indicator,value,denominator,unit\n"
    rows += "".join(
        f"community,WORKSPACE-GROUP,WORKSPACE-SOURCE,2026-07-{day:02d},weekly_reports,{value},5000,reports\n"
        for day, value in [(1, 10), (2, 11), (3, 9), (4, 10), (5, 11), (6, 10), (7, 9), (8, 35)]
    )
    imported = client.post("/api/v1/observations/import",
        headers={"X-Organization-ID": organization_id, "X-CSRF-Token": admin_csrf},
        files={"file": ("workspace.csv", io.BytesIO(rows.encode()), "text/csv")})
    assert imported.status_code == 200, imported.text
    alert_id = client.get("/api/v1/alerts?status=all",
        headers={"X-Organization-ID": organization_id}).json()["items"][0]["id"]

    # Reviewer: can read and review, but write requests must carry the session CSRF token.
    reviewer, reviewer_csrf = login(client, "reviewer@workspace.test", "Reviewer-Password-2026!")
    headers = {"X-Organization-ID": organization_id}
    assert client.get("/api/v1/dashboard", headers=headers).status_code == 200
    assert client.post(f"/api/v1/alerts/{alert_id}/acknowledge", headers=headers).status_code == 403
    reviewed = client.post(f"/api/v1/alerts/{alert_id}/acknowledge",
        headers={**headers, "X-CSRF-Token": reviewer_csrf})
    assert reviewed.status_code == 200, reviewed.text

    # Analyst: can ingest but cannot perform clinical/public-health review actions.
    analyst, analyst_csrf = login(client, "analyst@workspace.test", "Analyst-Password-2026!")
    assert client.get("/api/v1/dashboard", headers=headers).status_code == 200
    analyst_import = client.post("/api/v1/observations/import",
        headers={**headers, "X-CSRF-Token": analyst_csrf},
        files={"file": ("empty.csv", io.BytesIO(
            b"domain,group_code,source_code,observed_date,indicator,value,denominator,unit\n"
        ), "text/csv")})
    assert analyst_import.status_code == 200, analyst_import.text
    denied_review = client.post(f"/api/v1/alerts/{alert_id}/investigation",
        headers={**headers, "X-CSRF-Token": analyst_csrf})
    assert denied_review.status_code == 403

    # Viewer: read-only access, including alerts and dashboard.
    viewer, viewer_csrf = login(client, "viewer@workspace.test", "Viewer-Password-2026!")
    assert client.get("/api/v1/dashboard", headers=headers).status_code == 200
    assert client.get("/api/v1/alerts?status=all", headers=headers).status_code == 200
    denied_import = client.post("/api/v1/observations/import",
        headers={**headers, "X-CSRF-Token": viewer_csrf},
        files={"file": ("empty.csv", io.BytesIO(
            b"domain,group_code,source_code,observed_date,indicator,value,denominator,unit\n"
        ), "text/csv")})
    assert denied_import.status_code == 403
    denied_review = client.post(f"/api/v1/alerts/{alert_id}/investigation",
        headers={**headers, "X-CSRF-Token": viewer_csrf})
    assert denied_review.status_code == 403

    # Membership is checked server-side even if the browser changes the organization header.
    assert client.get("/api/v1/dashboard", headers={
        "X-Organization-ID": "00000000-0000-0000-0000-000000000099"
    }).status_code == 403



def test_primary_admin_is_the_only_account_that_can_hold_admin_role(client):
    organization_id = bootstrap(client)
    _, admin_csrf = login(client, "admin@workspace.test", "Admin-Password-2026!")
    denied_invite = client.post(
        f"/api/v1/auth/organizations/{organization_id}/invitations",
        headers={"X-Organization-ID": organization_id, "X-CSRF-Token": admin_csrf},
        json={"email": "second-admin@workspace.test", "role": "org_admin"},
    )
    assert denied_invite.status_code == 422
    member_token = invite(client, organization_id, "member@workspace.test", "analyst", admin_csrf)
    accept(client, member_token, "Organization Member", "Member-Password-2026!")
    admin_csrf = csrf(client)
    access = client.get(f"/api/v1/auth/organizations/{organization_id}/access", headers={"X-Organization-ID": organization_id})
    assert access.status_code == 200
    primary = next(item for item in access.json()["members"] if item["email"] == "admin@workspace.test")
    member = next(item for item in access.json()["members"] if item["email"] == "member@workspace.test")
    assert primary["is_primary_admin"] is True
    assert member["is_primary_admin"] is False
    assert primary["role"] == "org_admin"
    member_id = member["user_id"]
    promote = client.patch(
        f"/api/v1/auth/organizations/{organization_id}/members/{member_id}",
        headers={"X-Organization-ID": organization_id, "X-CSRF-Token": admin_csrf},
        json={"role": "org_admin"},
    )
    assert promote.status_code == 403
    assert promote.json()["detail"] == "primary_admin_role_reserved"


def test_ai_alert_explanation_security_grounding_and_provider_failures(client, monkeypatch):
    import urllib.error
    from uuid import UUID
    from fastapi import HTTPException
    from app import ai_intelligence
    from app.models import WorkforceGroup

    organization_id = bootstrap(client)
    _, token = login(client, "admin@workspace.test", "Admin-Password-2026!")
    rows = "domain,group_code,source_code,observed_date,indicator,value,denominator,unit\n"
    rows += "".join(
        f"community,AI-GROUP,AI-SOURCE,2026-08-{day:02d},weekly_reports,{value},5000,reports\n"
        for day, value in [(1, 10), (2, 11), (3, 9), (4, 10), (5, 11), (6, 10), (7, 9), (8, 35)]
    )
    imported = client.post("/api/v1/observations/import",
        headers={"X-Organization-ID": organization_id, "X-CSRF-Token": token},
        files={"file": ("ai.csv", io.BytesIO(rows.encode()), "text/csv")})
    assert imported.status_code == 200, imported.text
    alert = client.get("/api/v1/alerts?status=all",
        headers={"X-Organization-ID": organization_id}).json()["items"][0]
    url = f"/api/v1/ai/alerts/{alert['id']}/explanation"
    headers = {"X-Organization-ID": organization_id, "X-CSRF-Token": token}
    assert client.post(url, headers=headers).status_code == 503

    monkeypatch.setattr(ai_intelligence.settings, "ai_enabled", True)
    monkeypatch.setattr(ai_intelligence.settings, "ai_api_key", "synthetic-test-key")

    # A different tenant cannot reach the model gateway, even with a valid session.
    def must_not_call_provider(*args, **kwargs):
        raise AssertionError("provider must not be called for a cross-tenant request")
    monkeypatch.setattr(ai_intelligence.urllib.request, "urlopen", must_not_call_provider)
    cross_tenant = client.post(url, headers={**headers,
        "X-Organization-ID": "00000000-0000-0000-0000-000000000099"})
    assert cross_tenant.status_code == 403

    # Provider transport failures fail closed and do not leak upstream details.
    def provider_timeout(*args, **kwargs):
        raise urllib.error.URLError("synthetic upstream outage")
    monkeypatch.setattr(ai_intelligence.urllib.request, "urlopen", provider_timeout)
    unavailable = client.post(url, headers=headers)
    assert unavailable.status_code == 502
    assert unavailable.json()["detail"] == "ai_provider_unavailable_or_invalid_response"

    # A syntactically malformed provider response is also rejected.
    class BadResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, size=-1): return b'{"choices":[{"message":{"content":"not-json"}}]}'
    monkeypatch.setattr(ai_intelligence.urllib.request, "urlopen", lambda *a, **k: BadResponse())
    malformed = client.post(url, headers=headers)
    assert malformed.status_code == 502
    assert malformed.json()["detail"] == "ai_provider_unavailable_or_invalid_response"

    # Model-authored prose cannot introduce quantitative facts.
    qualitative = ai_intelligence.AlertExplanation(
        summary="A candidate aggregate signal differs from the established pattern.",
        possible_interpretations=[{
            "hypothesis": "A reporting-process change may explain the observed signal.",
            "supporting_evidence_ids": ["obs:known"], "contradicting_evidence_ids": [],
            "confidence_label": "low"
        }],
        requires_human_review=True, classification="candidate_signal",
        evidence_ids=["obs:known"]
    )
    ai_intelligence._reject_numeric_claims(qualitative)
    ai_intelligence._validate_evidence_references(qualitative, {"obs:known"})
    with pytest.raises(HTTPException) as foreign_error:
        ai_intelligence._validate_evidence_references(qualitative, {"obs:another-tenant"})
    assert foreign_error.value.status_code == 502
    numeric = qualitative.model_copy(update={"summary": "Reports increased by 40 percent."})
    with pytest.raises(HTTPException) as numeric_error:
        ai_intelligence._reject_numeric_claims(numeric)
    assert numeric_error.value.status_code == 502
    ratio_claim = qualitative.model_copy(update={"summary": "Reports doubled during the latest period."})
    with pytest.raises(HTTPException):
        ai_intelligence._reject_numeric_claims(ratio_claim)
    with pytest.raises(Exception):
        ai_intelligence.AlertExplanation.model_validate({
            **qualitative.model_dump(), "untrusted_extra_field": "must be rejected"
        })

    # Workforce evidence is suppressed when the cohort is below threshold or unknown.
    workforce_rows = "domain,group_code,source_code,observed_date,indicator,value,denominator,unit\n"
    workforce_rows += "".join(
        f"workforce,AI-WORKFORCE,AI-W-SOURCE,2026-09-{day:02d},heat_symptoms,{value},25,reports\n"
        for day, value in [(1, 2), (2, 3), (3, 4), (4, 3), (5, 4), (6, 3), (7, 4), (8, 15)]
    )
    workforce_import = client.post("/api/v1/observations/import",
        headers={"X-Organization-ID": organization_id, "X-CSRF-Token": token},
        files={"file": ("workforce.csv", io.BytesIO(workforce_rows.encode()), "text/csv")})
    assert workforce_import.status_code == 200, workforce_import.text
    db = client.testing_session()
    try:
        group = db.query(WorkforceGroup).filter_by(
            organization_id=UUID(organization_id), location_code="AI-WORKFORCE").one()
        workforce_alert = client.get("/api/v1/alerts?status=all",
            headers={"X-Organization-ID": organization_id}).json()["items"]
        workforce_alert = next(item for item in workforce_alert if item["domain"] == "workforce")
        workforce_url = f"/api/v1/ai/alerts/{workforce_alert['id']}/explanation"
        group.cohort_size = 19
        db.commit()
        suppressed = client.post(workforce_url, headers=headers)
        assert suppressed.status_code == 404
        group.cohort_size = None
        db.commit()
        unknown = client.post(workforce_url, headers=headers)
        assert unknown.status_code == 404
    finally:
        db.close()


def test_upload_activity_notifications_and_reviewer_assignment(client):
    organization_id = bootstrap(client)
    _, admin_csrf = login(client, "admin@workspace.test", "Admin-Password-2026!")
    reviewer_token = invite(client, organization_id, "reviewer@workspace.test", "reviewer", admin_csrf)
    accept(client, reviewer_token, "Health Reviewer", "Reviewer-Password-2026!")
    admin_csrf = csrf(client)

    rows = "domain,group_code,source_code,observed_date,indicator,value,denominator,unit\n"
    rows += "".join(
        f"community,ACTIVITY-GROUP,ACTIVITY-SOURCE,2026-10-{day:02d},weekly_reports,{value},5000,reports\n"
        for day, value in [(1, 10), (2, 11), (3, 9), (4, 10), (5, 11), (6, 10), (7, 9), (8, 35)]
    )
    imported = client.post("/api/v1/observations/import",
        headers={"X-Organization-ID": organization_id, "X-CSRF-Token": admin_csrf},
        files={"file": ("activity.csv", io.BytesIO(rows.encode()), "text/csv")})
    assert imported.status_code == 200, imported.text

    headers = {"X-Organization-ID": organization_id}
    history = client.get("/api/v1/activity/uploads", headers=headers)
    assert history.status_code == 200
    assert history.json()["items"][0]["filename"] == "activity.csv"
    assert history.json()["items"][0]["uploaded_by"] == "Workspace Administrator"

    reviewers = client.get("/api/v1/reviewers", headers=headers)
    reviewer_id = reviewers.json()["items"][0]["user_id"]
    alert_id = client.get("/api/v1/alerts?status=all", headers=headers).json()["items"][0]["id"]
    assigned = client.patch(f"/api/v1/alerts/{alert_id}/assignment",
        headers={**headers, "X-CSRF-Token": admin_csrf},
        json={"reviewer_user_id": reviewer_id})
    assert assigned.status_code == 200, assigned.text

    _, reviewer_csrf = login(client, "reviewer@workspace.test", "Reviewer-Password-2026!")
    inbox = client.get("/api/v1/alerts/inbox", headers=headers)
    assert inbox.status_code == 200
    assert len(inbox.json()["items"]) == 1
    assert inbox.json()["items"][0]["assigned_to_user_id"] == reviewer_id

    notifications = client.get("/api/v1/notifications", headers=headers)
    assert notifications.status_code == 200
    kinds = {item["kind"] for item in notifications.json()["items"]}
    assert "review_queue" in kinds
    assert "review_assignment" in kinds
    assignment_notice = next(item for item in notifications.json()["items"] if item["kind"] == "review_assignment")
    marked = client.post(f"/api/v1/notifications/{assignment_notice['id']}/read",
        headers={**headers, "X-CSRF-Token": reviewer_csrf})
    assert marked.status_code == 200
    assert marked.json()["is_read"] is True

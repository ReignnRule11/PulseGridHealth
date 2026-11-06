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



def test_ai_alert_explanation_is_guarded_and_evidence_validated(client, monkeypatch):
    from app import ai_intelligence
    organization_id = bootstrap(client)
    _, token = login(client, "admin@workspace.test", "Admin-Password-2026!")
    rows = "domain,group_code,source_code,observed_date,indicator,value,denominator,unit\\n"
    rows += "".join(
        f"community,AI-GROUP,AI-SOURCE,2026-08-{day:02d},weekly_reports,{value},5000,reports\\n"
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
    disabled = client.post(url, headers=headers)
    assert disabled.status_code == 503
    monkeypatch.setattr(ai_intelligence.settings, "ai_enabled", True)
    monkeypatch.setattr(ai_intelligence.settings, "ai_api_key", "synthetic-test-key")

    def valid_response(evidence):
        current_id = evidence["current"]["evidence_id"]
        detector_id = evidence["detector"]["evidence_id"]
        return {
            "summary": "A candidate aggregate signal differs from its historical baseline.",
            "observed_changes": [{"metric": evidence["indicator"], "evidence_id": current_id}],
            "possible_interpretations": [{
                "hypothesis": "A change in reporting patterns may explain this signal.",
                "supporting_evidence_ids": [current_id, detector_id],
                "contradicting_evidence_ids": [], "confidence_label": "low"
            }],
            "data_quality_caveats": ["Reporting completeness has not been independently verified."],
            "review_questions": ["Was the reporting process consistent during this period?"],
            "recommended_review_steps": ["Verify the source aggregate and reporting window."],
            "limitations": ["Synthetic test data; no epidemiological validation."],
            "requires_human_review": True, "classification": "candidate_signal",
            "evidence_ids": [current_id, detector_id],
        }
    monkeypatch.setattr(ai_intelligence, "_provider_generate", valid_response)
    response = client.post(url, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["explanation"]["requires_human_review"] is True

    monkeypatch.setattr(ai_intelligence, "_provider_generate", lambda evidence: {
        **valid_response(evidence), "evidence_ids": ["obs:foreign-tenant-record"]
    })
    rejected = client.post(url, headers=headers)
    assert rejected.status_code == 502
    assert rejected.json()["detail"] == "ai_evidence_validation_failed"

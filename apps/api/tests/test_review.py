from datetime import date
import io


def _seed_alert(client):
    rows = "".join(
        f"community,REVIEW-GROUP,REVIEW-SOURCE,2026-05-{day:02d},weekly_reports,{value},5000,reports\\n"
        for day, value in [(1,10),(2,11),(3,9),(4,10),(5,11),(6,10),(7,9),(8,35)]
    )
    header = "domain,group_code,source_code,observed_date,indicator,value,denominator,unit\\n"
    result = client.post("/api/v1/observations/import", files={"file": ("review.csv", io.BytesIO((header + rows).encode()), "text/csv")})
    assert result.status_code == 200
    return client.get("/api/v1/alerts").json()["items"][0]["id"]


def test_alert_review_lifecycle_and_audit_history(client):
    alert_id = _seed_alert(client)
    assert client.post(f"/api/v1/alerts/{alert_id}/investigation").status_code == 409
    acknowledged = client.post(f"/api/v1/alerts/{alert_id}/acknowledge")
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "acknowledged"
    investigation = client.post(f"/api/v1/alerts/{alert_id}/investigation")
    assert investigation.status_code == 200
    assert investigation.json()["status"] == "in_progress"
    findings = client.post(f"/api/v1/alerts/{alert_id}/findings", json={
        "findings": "Reviewed aggregate signal and compared with recent baseline.",
        "disposition": "monitor",
    })
    assert findings.status_code == 200
    action = client.post(f"/api/v1/alerts/{alert_id}/actions", json={
        "action_type": "follow_up", "description": "Request a second aggregate data review from the local team.",
        "owner_role": "public health reviewer", "due_date": "2026-05-20",
    })
    assert action.status_code == 200
    assert client.post(f"/api/v1/alerts/{alert_id}/resolve", json={
        "rationale": "Continue routine monitoring; no corroborating evidence was supplied.",
        "disposition": "monitoring",
    }).status_code == 200
    history = client.get(f"/api/v1/alerts/{alert_id}/history")
    assert history.status_code == 200
    body = history.json()
    assert body["alert"]["status"] == "resolved"
    assert body["investigation"]["status"] == "closed"
    assert len(body["response_actions"]) == 1
    assert len(body["audit_events"]) == 5
    assert client.post(f"/api/v1/alerts/{alert_id}/acknowledge").status_code == 409


def test_resolution_requires_rationale(client):
    alert_id = _seed_alert(client)
    client.post(f"/api/v1/alerts/{alert_id}/acknowledge")
    client.post(f"/api/v1/alerts/{alert_id}/investigation")
    response = client.post(f"/api/v1/alerts/{alert_id}/resolve", json={
        "rationale": "short", "disposition": "monitoring"
    })
    assert response.status_code == 422

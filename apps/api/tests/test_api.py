import csv
import io
import os
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app


@pytest.fixture()
def client():
    database_url = os.getenv("DATABASE_URL", "")
    if database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        engine = create_engine(database_url, pool_pre_ping=True)
    else:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
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


def csv_file(rows):
    header = "domain,group_code,source_code,observed_date,indicator,value,denominator,unit\n"
    return (header + rows).encode()


def test_import_persists_and_is_idempotent(client):
    payload = csv_file(
        "community,C001,SYNTHETIC,2026-01-05,weekly_reports,10,5000,reports\n"
        "community,C001,SYNTHETIC,2026-01-12,weekly_reports,11,5000,reports\n"
    )
    first = client.post("/api/v1/observations/import", files={"file": ("community.csv", io.BytesIO(payload), "text/csv")})
    assert first.status_code == 200
    assert first.json()["accepted"] == 2
    second = client.post("/api/v1/observations/import", files={"file": ("community.csv", io.BytesIO(payload), "text/csv")})
    assert second.status_code == 200
    assert second.json()["duplicates"] == 2
    dashboard = client.get("/api/v1/dashboard").json()
    assert dashboard["community_observations"] == 2


def test_import_generates_persisted_candidate_alert(client):
    lines = "".join(
        f"community,C002,SYNTHETIC,2026-02-{day:02d},weekly_reports,{value},5000,reports\n"
        for day, value in [(1,10),(2,11),(3,9),(4,10),(5,11),(6,10),(7,9),(8,35)]
    )
    response = client.post("/api/v1/observations/import", files={"file": ("demo.csv", io.BytesIO(csv_file(lines)), "text/csv")})
    assert response.status_code == 200
    assert response.json()["alerts_created"] == 1
    alerts = client.get("/api/v1/alerts").json()["items"]
    assert len(alerts) == 1
    assert alerts[0]["status"] == "pending_review"
    assert alerts[0]["baseline"] == 10.0


def test_end_to_end_community_and_workforce_alerts(client):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["domain", "group_code", "source_code", "observed_date", "indicator", "value", "denominator", "unit"])
    start = date(2026, 1, 5)
    for week in range(9):
        observed = (start + timedelta(days=week * 7)).isoformat()
        community_value = ([10, 11] * 4)[week] if week < 8 else 35
        symptom_value = ([4, 5] * 4)[week] if week < 8 else 18
        heat_value = ([30, 31] * 4)[week] if week < 8 else 40
        writer.writerow(["community", "C-DEMO", "SYNTHETIC", observed, "weekly_febrile_illness_reports", community_value, 5000, "reports"])
        writer.writerow(["workforce", "W-DEMO", "SYNTHETIC", observed, "weekly_heat_related_symptom_reports", symptom_value, 250, "reports"])
        writer.writerow(["workforce", "W-DEMO", "SYNTHETIC", observed, "weekly_mean_heat_index", heat_value, "", "celsius"])
    payload = output.getvalue().encode()

    imported = client.post("/api/v1/observations/import", files={"file": ("both-domains.csv", io.BytesIO(payload), "text/csv")})
    assert imported.status_code == 200, imported.text
    result = imported.json()
    assert result["accepted"] == 27
    assert result["rejected"] == 0
    assert result["alerts_created"] == 3

    duplicate = client.post("/api/v1/observations/import", files={"file": ("both-domains.csv", io.BytesIO(payload), "text/csv")})
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["accepted"] == 0
    assert duplicate.json()["duplicates"] == 27
    assert duplicate.json()["alerts_created"] == 0

    dashboard = client.get("/api/v1/dashboard")
    assert dashboard.status_code == 200
    metrics = dashboard.json()
    assert metrics["community_observations"] == 9
    assert metrics["workforce_observations"] == 18
    assert metrics["pending_alerts"] == 3

    alerts = client.get("/api/v1/alerts").json()["items"]
    assert len(alerts) == 3
    assert {item["domain"] for item in alerts} == {"community", "workforce"}
    assert all(item["history_count"] == 8 for item in alerts)


def test_workforce_cohort_below_minimum_is_suppressed(client):
    lines = "".join(
        f"workforce,W-SMALL,SYNTHETIC,2026-03-{day:02d},weekly_heat_related_symptom_reports,{value},10,reports\n"
        for day, value in [(1, 4), (8, 5), (15, 4), (22, 5), (29, 30)]
    )
    response = client.post("/api/v1/observations/import", files={"file": ("small-cohort.csv", io.BytesIO(csv_file(lines)), "text/csv")})
    assert response.status_code == 200
    assert response.json()["accepted"] == 0
    assert response.json()["rejected"] == 5
    assert response.json()["alerts_created"] == 0
    assert client.get("/api/v1/alerts").json()["items"] == []
    assert client.get("/api/v1/dashboard").json()["workforce_observations"] == 0

def test_generated_synthetic_datasets_import_end_to_end(client, tmp_path):
    from pathlib import Path
    import subprocess
    import sys

    repo_root = Path(__file__).resolve().parents[3]
    output = tmp_path / "synthetic"
    subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "generate_synthetic_data.py"),
         "--output", str(output), "--seed", "20261104"],
        check=True,
    )
    community = (output / "community_observations.csv").read_bytes()
    workforce = (output / "workforce_observations.csv").read_bytes()

    community_result = client.post(
        "/api/v1/observations/import",
        files={"file": ("community.csv", io.BytesIO(community), "text/csv")},
    )
    assert community_result.status_code == 200, community_result.text
    assert community_result.json()["accepted"] == 180

    workforce_result = client.post(
        "/api/v1/observations/import",
        files={"file": ("workforce.csv", io.BytesIO(workforce), "text/csv")},
    )
    assert workforce_result.status_code == 200, workforce_result.text
    assert workforce_result.json()["accepted"] == 360

    alerts = client.get("/api/v1/alerts").json()["items"]
    assert any(a["domain"] == "community" and a["group_code"] == "C002" for a in alerts)
    assert any(a["domain"] == "workforce" and a["group_code"] == "W003" for a in alerts)
    dashboard = client.get("/api/v1/dashboard").json()
    assert dashboard["community_observations"] == 180
    assert dashboard["workforce_observations"] == 360

    duplicate = client.post(
        "/api/v1/observations/import",
        files={"file": ("community.csv", io.BytesIO(community), "text/csv")},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["accepted"] == 0
    assert duplicate.json()["duplicates"] == 180


def test_workforce_without_known_cohort_size_is_suppressed(client):
    lines = "".join(
        f"workforce,W-UNKNOWN,SYNTHETIC,2026-04-{day:02d},weekly_mean_heat_index,{value},,celsius\n"
        for day, value in [(1, 30), (8, 31), (15, 30), (22, 32), (29, 45)]
    )
    response = client.post(
        "/api/v1/observations/import",
        files={"file": ("unknown-cohort.csv", io.BytesIO(csv_file(lines)), "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["accepted"] == 0
    assert response.json()["rejected"] == 5
    assert client.get("/api/v1/dashboard").json()["workforce_observations"] == 0

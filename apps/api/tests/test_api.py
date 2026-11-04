import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db import Base, get_db
from app.main import app

@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
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

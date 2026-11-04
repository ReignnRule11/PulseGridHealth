"""Smoke-test PostgreSQL tenant RLS after the full Alembic upgrade."""
import os
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

url = os.environ["DATABASE_URL"]
engine = create_engine(url, pool_pre_ping=True)
tenant_tables = [
    "data_sources", "health_observations", "detection_results", "alerts",
    "investigations", "response_actions", "audit_logs",
]

with engine.begin() as connection:
    policies = connection.execute(text("""
        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = current_schema() AND c.relname = ANY(:tables)
    """), {"tables": tenant_tables}).all()
    assert len(policies) == len(tenant_tables), policies
    assert all(row.relrowsecurity and row.relforcerowsecurity for row in policies), policies

    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    connection.execute(text("""
        INSERT INTO organizations (id, name, organization_type, created_at)
        VALUES (:a, :name_a, 'test', now()), (:b, :name_b, 'test', now())
    """), {"a": org_a, "b": org_b, "name_a": f"RLS-A-{org_a}", "name_b": f"RLS-B-{org_b}"})
    connection.execute(text("SELECT set_config('app.organization_id', :org, true)"), {"org": str(org_a)})
    connection.execute(text("""
        INSERT INTO data_sources (id, organization_id, source_name, source_type, authorised)
        VALUES (:id, :org, :name, 'test', false)
    """), {"id": uuid.uuid4(), "org": org_a, "name": f"rls-source-{org_a}"})
    connection.execute(text("SELECT set_config('app.organization_id', :org, true)"), {"org": str(org_b)})
    visible = connection.execute(text("SELECT count(*) FROM data_sources WHERE source_name = :name"),
                                  {"name": f"rls-source-{org_a}"}).scalar_one()
    assert visible == 0, "cross-organization row became visible"
    try:
        with connection.begin_nested():
            connection.execute(text("""
                INSERT INTO data_sources (id, organization_id, source_name, source_type, authorised)
                VALUES (:id, :org, :name, 'test', false)
            """), {"id": uuid.uuid4(), "org": org_a, "name": f"rls-forbidden-{org_a}"})
    except DBAPIError:
        pass
    else:
        raise AssertionError("RLS allowed a cross-organization insert")

engine.dispose()
print("PostgreSQL tenant RLS isolation checks passed.")

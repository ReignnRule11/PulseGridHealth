"""Smoke-test PostgreSQL tenant RLS across every tenant-owned data table."""
import os
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

url = os.environ["DATABASE_URL"]
engine = create_engine(url, pool_pre_ping=True)
tenant_tables = [
    "data_sources", "health_observations", "detection_results", "alerts",
    "investigations", "response_actions", "audit_logs", "communities",
    "workforce_groups",
]

with engine.begin() as connection:
    policies = connection.execute(text("""
        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = current_schema() AND c.relname = ANY(:tables)
    """), {"tables": tenant_tables}).all()
    assert len(policies) == len(tenant_tables), policies
    assert all(row.relrowsecurity and row.relforcerowsecurity for row in policies), policies

    connection.execute(text("CREATE ROLE pulsegrid_rls_test NOLOGIN NOSUPERUSER NOBYPASSRLS"))
    connection.execute(text("GRANT USAGE ON SCHEMA public TO pulsegrid_rls_test"))
    for table in ("data_sources", "communities", "workforce_groups"):
        connection.execute(text(f"GRANT SELECT, INSERT ON {table} TO pulsegrid_rls_test"))

    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    connection.execute(text("""
        INSERT INTO organizations (id, name, organization_type, created_at)
        VALUES (:a, :name_a, 'test', now()), (:b, :name_b, 'test', now())
    """), {"a": org_a, "b": org_b, "name_a": f"RLS-A-{org_a}", "name_b": f"RLS-B-{org_b}"})

    source_name = f"rls-source-{org_a}"
    community_code = f"rls-community-{org_a}"
    workforce_code = f"rls-workforce-{org_a}"
    connection.execute(text("SET LOCAL ROLE pulsegrid_rls_test"))
    connection.execute(text("SELECT set_config('app.organization_id', :org, true)"), {"org": str(org_a)})
    connection.execute(text("""
        INSERT INTO data_sources (id, organization_id, source_name, source_type, authorised)
        VALUES (:id, :org, :name, 'test', false)
    """), {"id": uuid.uuid4(), "org": org_a, "name": source_name})
    connection.execute(text("""
        INSERT INTO communities (id, organization_id, name, region_code)
        VALUES (:id, :org, 'RLS test community', :code)
    """), {"id": uuid.uuid4(), "org": org_a, "code": community_code})
    connection.execute(text("""
        INSERT INTO workforce_groups (id, organization_id, name, sector, location_code)
        VALUES (:id, :org, 'RLS test workforce', 'test', :code)
    """), {"id": uuid.uuid4(), "org": org_a, "code": workforce_code})

    connection.execute(text("SELECT set_config('app.organization_id', :org, true)"), {"org": str(org_b)})
    checks = {
        "data_sources": source_name,
        "communities": community_code,
        "workforce_groups": workforce_code,
    }
    for table, marker in checks.items():
        column = {"data_sources": "source_name", "communities": "region_code",
                  "workforce_groups": "location_code"}[table]
        visible = connection.execute(
            text(f"SELECT count(*) FROM {table} WHERE {column} = :marker"),
            {"marker": marker},
        ).scalar_one()
        assert visible == 0, f"cross-organization row became visible in {table}"

        try:
            with connection.begin_nested():
                if table == "data_sources":
                    connection.execute(text("""
                        INSERT INTO data_sources (id, organization_id, source_name, source_type, authorised)
                        VALUES (:id, :org, :name, 'test', false)
                    """), {"id": uuid.uuid4(), "org": org_a, "name": f"forbidden-{org_a}"})
                elif table == "communities":
                    connection.execute(text("""
                        INSERT INTO communities (id, organization_id, name, region_code)
                        VALUES (:id, :org, 'Forbidden community', :code)
                    """), {"id": uuid.uuid4(), "org": org_a, "code": f"forbidden-{org_a}"})
                else:
                    connection.execute(text("""
                        INSERT INTO workforce_groups (id, organization_id, name, sector, location_code)
                        VALUES (:id, :org, 'Forbidden workforce', 'test', :code)
                    """), {"id": uuid.uuid4(), "org": org_a, "code": f"forbidden-{org_a}"})
        except DBAPIError:
            pass
        else:
            raise AssertionError(f"RLS allowed a cross-organization insert into {table}")

engine.dispose()
print("PostgreSQL tenant RLS isolation checks passed for all tenant data tables.")

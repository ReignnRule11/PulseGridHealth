"""Verify forced tenant RLS and exercise cross-tenant isolation on root tables.

Run only against a disposable PostgreSQL test database after migrations. The test
creates a uniquely named temporary role and removes all test rows and grants.
"""
import os
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError


TENANT_TABLES = (
    "data_sources",
    "health_observations",
    "detection_results",
    "alerts",
    "investigations",
    "response_actions",
    "audit_logs",
    "communities",
    "workforce_groups",
    "data_import_batches",
    "notifications",
)
EXERCISED_TABLES = {
    "data_sources": ("source_name",),
    "communities": ("region_code",),
    "workforce_groups": ("location_code",),
}


def normalize_postgres_url(raw_url: str) -> str:
    if raw_url.startswith("postgres://"):
        return "postgresql+psycopg://" + raw_url[len("postgres://"):]
    if raw_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + raw_url[len("postgresql://"):]
    return raw_url


def is_rls_check_violation(error: DBAPIError) -> bool:
    """Accept only PostgreSQL's explicit row-level-security WITH CHECK rejection."""
    original = error.orig
    sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    diagnostic = getattr(original, "diag", None)
    message = getattr(diagnostic, "message_primary", "") or str(original)
    return sqlstate == "42501" and "row-level security" in message.lower()


def main() -> int:
    raw_url = os.environ.get("DATABASE_URL", "").strip()
    if not raw_url:
        raise SystemExit("FAIL: DATABASE_URL is required.")
    url = normalize_postgres_url(raw_url)
    if not make_url(url).drivername.startswith("postgresql"):
        raise SystemExit("FAIL: verify_rls.py requires a PostgreSQL DATABASE_URL.")

    engine = create_engine(url, pool_pre_ping=True)
    role = "pulsegrid_rls_test_" + uuid.uuid4().hex
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    try:
        with engine.begin() as connection:
            policies = connection.execute(
                text("""
                    SELECT relation.relname, relation.relrowsecurity,
                           relation.relforcerowsecurity, count(policy.policyname) AS policy_count
                    FROM pg_class AS relation
                    JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                    LEFT JOIN pg_policies AS policy
                      ON policy.schemaname = namespace.nspname
                     AND policy.tablename = relation.relname
                    WHERE namespace.nspname = current_schema()
                      AND relation.relname = ANY(:tables)
                    GROUP BY relation.relname, relation.relrowsecurity, relation.relforcerowsecurity
                """),
                {"tables": list(TENANT_TABLES)},
            ).mappings().all()
            by_name = {row["relname"]: row for row in policies}
            for table in TENANT_TABLES:
                row = by_name.get(table)
                assert row is not None, f"tenant table {table} is missing"
                assert row["relrowsecurity"] and row["relforcerowsecurity"], (
                    f"forced RLS is not enabled on {table}"
                )
                assert row["policy_count"] > 0, f"no RLS policy exists on {table}"

            # The generated identifier contains only a fixed prefix and UUID hex.
            connection.execute(text(
                f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOREPLICATION NOBYPASSRLS"
            ))
            connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {role}"))
            for table in EXERCISED_TABLES:
                connection.execute(text(
                    f"GRANT SELECT, INSERT ON {table} TO {role}"
                ))

            connection.execute(
                text("""
                    INSERT INTO organizations (id, name, organization_type, created_at)
                    VALUES (:a, :name_a, 'test', now()), (:b, :name_b, 'test', now())
                """),
                {
                    "a": org_a,
                    "b": org_b,
                    "name_a": f"RLS-A-{org_a}",
                    "name_b": f"RLS-B-{org_b}",
                },
            )

            markers = {
                "data_sources": f"rls-source-{org_a}",
                "communities": f"rls-community-{org_a}",
                "workforce_groups": f"rls-workforce-{org_a}",
            }
            connection.execute(text(f"SET LOCAL ROLE {role}"))
            connection.execute(
                text("SELECT set_config('app.organization_id', :org, true)"),
                {"org": str(org_a)},
            )
            connection.execute(
                text("""
                    INSERT INTO data_sources
                        (id, organization_id, source_name, source_type, authorised)
                    VALUES (:id, :org, :name, 'test', false)
                """),
                {"id": uuid.uuid4(), "org": org_a, "name": markers["data_sources"]},
            )
            connection.execute(
                text("""
                    INSERT INTO communities (id, organization_id, name, region_code)
                    VALUES (:id, :org, 'RLS test community', :code)
                """),
                {"id": uuid.uuid4(), "org": org_a, "code": markers["communities"]},
            )
            connection.execute(
                text("""
                    INSERT INTO workforce_groups
                        (id, organization_id, name, sector, location_code)
                    VALUES (:id, :org, 'RLS test workforce', 'test', :code)
                """),
                {"id": uuid.uuid4(), "org": org_a, "code": markers["workforce_groups"]},
            )

            connection.execute(
                text("SELECT set_config('app.organization_id', :org, true)"),
                {"org": str(org_b)},
            )
            for table, (column,) in EXERCISED_TABLES.items():
                visible = connection.execute(
                    text(f"SELECT count(*) FROM {table} WHERE {column} = :marker"),
                    {"marker": markers[table]},
                ).scalar_one()
                assert visible == 0, f"cross-organization row became visible in {table}"

                try:
                    with connection.begin_nested():
                        if table == "data_sources":
                            connection.execute(
                                text("""
                                    INSERT INTO data_sources
                                        (id, organization_id, source_name, source_type, authorised)
                                    VALUES (:id, :org, :name, 'test', false)
                                """),
                                {"id": uuid.uuid4(), "org": org_a, "name": f"forbidden-{org_a}"},
                            )
                        elif table == "communities":
                            connection.execute(
                                text("""
                                    INSERT INTO communities (id, organization_id, name, region_code)
                                    VALUES (:id, :org, 'Forbidden community', :code)
                                """),
                                {"id": uuid.uuid4(), "org": org_a, "code": f"forbidden-{org_a}"},
                            )
                        else:
                            connection.execute(
                                text("""
                                    INSERT INTO workforce_groups
                                        (id, organization_id, name, sector, location_code)
                                    VALUES (:id, :org, 'Forbidden workforce', 'test', :code)
                                """),
                                {"id": uuid.uuid4(), "org": org_a, "code": f"forbidden-{org_a}"},
                            )
                except DBAPIError as error:
                    if not is_rls_check_violation(error):
                        raise AssertionError(
                            f"{table} insert failed for a reason other than RLS WITH CHECK"
                        ) from error
                else:
                    raise AssertionError(
                        f"RLS allowed a cross-organization insert into {table}"
                    )

            # Leave no role or test fixtures behind on a successful run.
            connection.execute(text("RESET ROLE"))
            for table in EXERCISED_TABLES:
                connection.execute(text(f"REVOKE ALL PRIVILEGES ON {table} FROM {role}"))
            connection.execute(text(f"REVOKE ALL PRIVILEGES ON SCHEMA public FROM {role}"))
            connection.execute(text(f"DROP ROLE {role}"))
            connection.execute(
                text("DELETE FROM data_sources WHERE organization_id = :org"),
                {"org": org_a},
            )
            connection.execute(
                text("DELETE FROM communities WHERE organization_id = :org"),
                {"org": org_a},
            )
            connection.execute(
                text("DELETE FROM workforce_groups WHERE organization_id = :org"),
                {"org": org_a},
            )
            connection.execute(
                text("DELETE FROM organizations WHERE id IN (:a, :b)"),
                {"a": org_a, "b": org_b},
            )
        print(
            "PostgreSQL tenant RLS checks passed: all 11 tenant tables have forced RLS "
            "and policies; cross-tenant reads and RLS write checks passed on 3 root tables."
        )
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())

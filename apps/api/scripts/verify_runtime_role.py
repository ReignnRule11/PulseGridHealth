"""Verify the connected PostgreSQL identity is safe for application runtime.

Run this with the exact DATABASE_URL configured for the API service after migrations.
The check is intentionally read-only and fails closed.
"""
import os
import sys

from sqlalchemy import create_engine, text


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
)


def main() -> int:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("FAIL: DATABASE_URL is required; no database was contacted.")
        return 2

    engine = create_engine(database_url, pool_pre_ping=True)
    failures = []
    try:
        with engine.connect() as connection:
            identity = connection.execute(text("""
                SELECT session_user, current_user,
                       current_setting('row_security') AS row_security
            """)).mappings().one()

            if identity["session_user"] != identity["current_user"]:
                failures.append("session_user differs from current_user; role switching is not allowed")
            if identity["row_security"] != "on":
                failures.append("row_security is not enabled for this connection")

            roles = connection.execute(text("""
                WITH RECURSIVE reachable_roles(roleid) AS (
                    SELECT oid FROM pg_roles WHERE rolname = session_user
                    UNION
                    SELECT membership.roleid
                    FROM pg_auth_members AS membership
                    JOIN reachable_roles AS reachable ON membership.member = reachable.roleid
                )
                SELECT role.rolname, role.rolsuper, role.rolbypassrls
                FROM pg_roles AS role
                JOIN reachable_roles AS reachable ON reachable.roleid = role.oid
                ORDER BY role.rolname
            """)).mappings().all()

            if not roles:
                failures.append("connected role could not be resolved")
            for role in roles:
                if role["rolsuper"]:
                    failures.append(f"connected role or granted role {role['rolname']} is SUPERUSER")
                if role["rolbypassrls"]:
                    failures.append(f"connected role or granted role {role['rolname']} has BYPASSRLS")

            policies = connection.execute(text("""
                SELECT relation.relname,
                       relation.relrowsecurity,
                       relation.relforcerowsecurity,
                       count(policy.policyname) AS policy_count
                FROM pg_class AS relation
                JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                LEFT JOIN pg_policies AS policy
                  ON policy.schemaname = namespace.nspname
                 AND policy.tablename = relation.relname
                WHERE namespace.nspname = current_schema()
                  AND relation.relname = ANY(:tables)
                GROUP BY relation.relname, relation.relrowsecurity, relation.relforcerowsecurity
            """), {"tables": list(TENANT_TABLES)}).mappings().all()

            by_name = {row["relname"]: row for row in policies}
            for table in TENANT_TABLES:
                row = by_name.get(table)
                if row is None:
                    failures.append(f"tenant table {table} is missing from current schema")
                elif not row["relrowsecurity"] or not row["relforcerowsecurity"] or row["policy_count"] < 1:
                    failures.append(f"tenant table {table} does not have forced RLS and a policy")

            if failures:
                print("Runtime database security verification FAILED:")
                for failure in failures:
                    print(f"- {failure}")
                return 1

            print(
                "Runtime database security verification PASSED: "
                f"role={identity['current_user']}; "
                f"checked {len(TENANT_TABLES)} forced-RLS tenant tables; "
                "no superuser/BYPASSRLS role is reachable."
            )
            return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())

"""Verify the connected PostgreSQL identity is safe for application runtime.

Run this with the exact API DATABASE_URL after migrations. The check is read-only
and fails closed if the API role can administer or own tenant tables.
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
                       current_setting('row_security') AS row_security,
                       current_schema() AS current_schema,
                       current_database() AS current_database
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
                SELECT role.rolname, role.rolsuper, role.rolbypassrls,
                       role.rolcreaterole, role.rolcreatedb, role.rolreplication
                FROM pg_roles AS role
                JOIN reachable_roles AS reachable ON reachable.roleid = role.oid
                ORDER BY role.rolname
            """)).mappings().all()

            if not roles:
                failures.append("connected role could not be resolved")
            reachable_names = {role["rolname"] for role in roles}
            for role in roles:
                if role["rolsuper"]:
                    failures.append(f"connected role or granted role {role['rolname']} is SUPERUSER")
                if role["rolbypassrls"]:
                    failures.append(f"connected role or granted role {role['rolname']} has BYPASSRLS")
                if role["rolcreaterole"] or role["rolcreatedb"] or role["rolreplication"]:
                    failures.append(f"connected role or granted role {role['rolname']} has database/role administration privileges")

            if connection.execute(
                text("SELECT has_schema_privilege(session_user, current_schema(), 'CREATE')")
            ).scalar_one():
                failures.append("runtime role can CREATE objects in the application schema")
            if connection.execute(
                text("SELECT has_database_privilege(session_user, current_database(), 'CREATE')")
            ).scalar_one():
                failures.append("runtime role can CREATE schemas in the database")

            policies = connection.execute(text("""
                SELECT relation.relname,
                       owner.rolname AS owner_name,
                       relation.relrowsecurity,
                       relation.relforcerowsecurity,
                       count(policy.policyname) AS policy_count
                FROM pg_class AS relation
                JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                JOIN pg_roles AS owner ON owner.oid = relation.relowner
                LEFT JOIN pg_policies AS policy
                  ON policy.schemaname = namespace.nspname
                 AND policy.tablename = relation.relname
                WHERE namespace.nspname = current_schema()
                  AND relation.relname = ANY(:tables)
                GROUP BY relation.relname, owner.rolname,
                         relation.relrowsecurity, relation.relforcerowsecurity
            """), {"tables": list(TENANT_TABLES)}).mappings().all()

            by_name = {row["relname"]: row for row in policies}
            for table in TENANT_TABLES:
                row = by_name.get(table)
                if row is None:
                    failures.append(f"tenant table {table} is missing from current schema")
                    continue
                if row["owner_name"] in reachable_names:
                    failures.append(f"runtime role can act as owner of tenant table {table}")
                if not row["relrowsecurity"] or not row["relforcerowsecurity"] or row["policy_count"] < 1:
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
                "no privileged role memberships, schema/database CREATE, or tenant-table ownership."
            )
            return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())

# Neon database setup for PulseGrid Health

This guide creates a restricted API runtime role while keeping schema migrations under a separate owner role. Use a fresh synthetic staging database. Never paste credentials into source control, issues, chat or screenshots.

## 1. Create the runtime role

1. Open the Neon SQL Editor for the intended PulseGrid database.
2. Confirm the current SQL identity is the database owner/migration identity.
3. Run the following SQL after replacing the database name and password with your own values:

```sql
CREATE ROLE pulsegrid_runtime
  LOGIN
  PASSWORD 'REPLACE_WITH_A_LONG_RANDOM_PASSWORD'
  NOSUPERUSER
  NOCREATEDB
  NOCREATEROLE
  NOREPLICATION
  NOBYPASSRLS;

GRANT CONNECT ON DATABASE neondb TO pulsegrid_runtime;
GRANT USAGE ON SCHEMA public TO pulsegrid_runtime;

GRANT SELECT, INSERT, UPDATE, DELETE
  ON ALL TABLES IN SCHEMA public TO pulsegrid_runtime;

GRANT USAGE, SELECT
  ON ALL SEQUENCES IN SCHEMA public TO pulsegrid_runtime;
```

Replace `neondb` if your database has a different name. Do not grant membership in the migration-owner role or any role that owns application tables.

## 2. Set default privileges for future migrations

Run these statements as the role that will own/create the application's tables. Replace `YOUR_MIGRATION_OWNER_ROLE` with that exact role name:

```sql
ALTER DEFAULT PRIVILEGES FOR ROLE YOUR_MIGRATION_OWNER_ROLE IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO pulsegrid_runtime;

ALTER DEFAULT PRIVILEGES FOR ROLE YOUR_MIGRATION_OWNER_ROLE IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO pulsegrid_runtime;
```

These grants allow the runtime role to use tables and sequences created later, without making it an owner. Do not grant CREATE on the schema or database to the runtime role.

## 3. Configure the two Neon connection strings

In Neon, copy two connection strings for the same database:

- Runtime: select the `pulsegrid_runtime` role and use the pooled connection option. This becomes Render `DATABASE_URL`.
- Migration: use the migration-owner role and the direct/non-pooled connection option. This becomes Render `MIGRATION_DATABASE_URL`.

Keep TLS enabled (Neon's connection strings normally include `sslmode=require`). Keep the URLs private. Do not put either URL in a `NEXT_PUBLIC_*` variable.

## 4. Verify before deploying

After migrations have run, the Render start command runs:

```bash
python scripts/verify_runtime_role.py
```

The check fails if the runtime identity or any inherited role is privileged, if it can create schema objects, if it owns tenant tables, or if any of the nine tenant tables lacks forced RLS and a policy.

The CI check is a synthetic proof of the verifier. It is not a substitute for running the check against the actual Neon database. Record the hosted result before considering staging verification complete.

## 5. Operational cautions

- Keep the Neon migration-owner URL out of the running API process; it is used only by Alembic during the single-instance staging startup sequence.
- Do not enable automatic deploys until the database migration process has been reviewed.
- Confirm the Neon plan's compute, connection, backup/restore, retention and pricing limits before relying on it.
- Use synthetic data only. This configuration is not approval to load patient or employee health data.

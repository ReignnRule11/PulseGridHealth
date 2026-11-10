# Database notes

The schema uses UUID primary keys, UTC timestamps, aggregate date-grained observations, mandatory source provenance and duplicate-protection constraints. Observations must belong to exactly one community or workforce group.

## Tenant isolation

Alembic migration `0004_tenant_isolation` adds organization ownership to the observation, source, detection, alert, investigation, response-action and audit tables. It also enables and forces PostgreSQL row-level security for those tables and for the already organization-owned `communities` and `workforce_groups` tables.

The tenant context is transaction-local (`app.organization_id`). Authenticated API requests establish it after verifying active organization membership. Every production runtime database role must be non-superuser and have `NOBYPASSRLS`; never run the application with the migration owner or a database superuser.

## Before real operational data

- Verify RLS against the exact hosted PostgreSQL role and schema after migrations.
- Confirm every query is organization-scoped and every tenant-owned data table has an RLS policy.
- Configure encrypted backups and complete a restore rehearsal.
- Define retention, deletion, access-review and incident-response procedures.
- Obtain data-controller authorization and independent security/privacy review.
- Use synthetic or explicitly authorized aggregate data only until these gates are complete.

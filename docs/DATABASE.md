# Database notes

The first migration creates the core aggregate data model.

Key rules:
- UUID primary keys.
- UTC timestamps.
- Observations are date-grained and aggregate.
- `community_id` XOR `workforce_group_id`.
- Source provenance is mandatory.
- Duplicate protection uses a unique key over source, group, date, and indicator.
- Detection results retain model name/version and baseline evidence.
- Alert records are candidate signals requiring human review.

Before production:
- Add organisation/tenant foreign keys to every tenant-owned table.
- Enforce tenant-scoped queries and PostgreSQL RLS.
- Add immutable audit events for sensitive operations.
- Define retention and deletion policies.

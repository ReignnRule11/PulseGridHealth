# Security baseline

- No patient- or employee-identifiable data in the prototype.
- No secrets in Git.
- HTTPS in hosted environments.
- Strong password hashing and secure session cookies when authentication is added.
- Server-side RBAC and tenant-scoped database access.
- Upload size and content limits.
- CSV parsing with strict allowlisted columns.
- SQLAlchemy parameterised queries; no string-built SQL.
- Audit privileged actions.
- Redact tokens and sensitive payloads from logs.
- Workforce minimum cohort-size suppression.
- Human review required for every alert and response.

This document is a baseline, not a certification or compliance claim.

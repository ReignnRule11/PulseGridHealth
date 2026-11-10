# Deployment and operational readiness

PulseGrid Health is a demonstration MVP. Passing CI does not authorize production use with patient, employee, or other sensitive health data.

## Recommended deployment topology

- Deploy the Next.js frontend to Vercel when ready and the FastAPI API to Render.
- Use Neon PostgreSQL as the managed database; keep database access private to approved services and administration.
- Use a dedicated migration-owner connection for Alembic and a separate restricted runtime role for API requests.
- Prefer a same-site custom-domain arrangement, such as the frontend at the apex/www host and the API at an `api.` subdomain, after verifying cookie and CORS behavior.
- Use exact CORS origins only; no wildcard.
- A reference Nginx edge template with HTTPS, security headers, request limits and query-string-free access logs is in deploy/nginx/nginx.conf. It is a template, not active protection on Render.

## Required environment

Render API:
- `APP_ENV=production`
- `DATABASE_URL`: Neon runtime connection using the restricted application role. Prefer Neon's pooled connection endpoint for application traffic.
- `MIGRATION_DATABASE_URL`: Neon direct (non-pooler) connection using the migration-owner role. Alembic uses this URL; the API process does not.
- `CORS_ORIGINS`: exact browser frontend origin(s), comma-separated only if genuinely required.
- `BOOTSTRAP_TOKEN`: high-entropy secret for initial administrator bootstrap. Deliver through the provider secret manager, never source control. After bootstrap, rotate or unset it.
- Set `SESSION_TTL_HOURS`, `INVITATION_TTL_HOURS`, `MAX_UPLOAD_MB`, `MIN_BASELINE_POINTS`, `ANOMALY_Z_THRESHOLD` and `MIN_WORKFORCE_COHORT_SIZE` to reviewed values.
- Keep `AI_ENABLED=false` until the AI feature has a separate security, privacy and cost review.

Vercel frontend (when deployed):
- `NEXT_PUBLIC_API_URL`: the public API base URL, for example `https://api.your-domain.example`. It is public configuration, not a secret.
- Never put database URLs, bootstrap tokens or other secrets in `NEXT_PUBLIC_*` variables.

## Release procedure

1. Provision Neon and create the restricted runtime role using [NEON_SETUP.md](NEON_SETUP.md).
2. Set `DATABASE_URL`, `MIGRATION_DATABASE_URL` and exact `CORS_ORIGINS` in Render's protected environment settings.
3. Confirm Neon connection strings require TLS; do not commit them or paste them into issues/chat.
4. Run migrations with the migration-owner connection: `alembic upgrade head`.
5. Run `python scripts/verify_runtime_role.py` with the exact runtime `DATABASE_URL`; it must pass before the API starts.
6. Deploy the API from a reviewed immutable commit.
7. Confirm GET `/health` returns HTTP 200; this is liveness only.
8. Confirm GET `/ready` returns HTTP 200 and a ready/database-reachable response. A 503 means database unavailable.
9. When the frontend is deployed, confirm browser sign-in, organization selection, CSV import, alert review and sign-out using synthetic aggregate data.
10. Confirm cross-organization access is denied and role permissions match the role matrix.
11. Confirm browser cookies are Secure, HttpOnly for session, SameSite=Strict and scoped to intended host/path.
12. Confirm backup restoration, monitoring, alerting, secret rotation and incident response before real operational use.

## Mandatory controls before real health data

- Deploy gateway rate limiting for login, bootstrap, invitation acceptance and uploads. The reference Nginx config provides starting limits; it is not active until deployed at the public edge.
- Add account recovery, account deactivation, session revocation management and secure invitation delivery.
- Configure encrypted backups, tested restoration, retention/deletion policy and audit-log access controls.
- Disable default request-target access logging at the API server and configure provider/edge logs to omit query strings, cookies, authorization headers, request bodies, CSV contents and sensitive observations. Review actual provider logs before pilot.
- Complete independent security/privacy review and applicable legal/regulatory assessment.
- Validate workforce cohort suppression threshold and aggregation rules with domain experts.
- Use synthetic or explicitly authorized aggregate data only until all controls are independently verified.

## Health endpoints

- GET `/health`: process liveness; does not prove database availability.
- GET `/ready`: readiness; executes a lightweight database query and returns 503 when database is unavailable.

Green CI verifies automated tests, migrations, RLS checks, TypeScript and frontend production build. It does not prove live deployment, browser E2E, backup recovery or production security.

# Deployment and operational readiness

PulseGrid Health is a demonstration MVP. Passing CI does not authorize production use with patient, employee, or other sensitive health data.

## Recommended deployment topology

- Deploy Next.js and FastAPI behind one HTTPS origin, or use intentionally configured same-site subdomains.
- Prefer a reverse proxy routing /api/*, /health and /ready to FastAPI and all other paths to Next.js. This keeps browser API calls same-origin and avoids cross-site cookie problems with SameSite=Strict.
- Use managed PostgreSQL 15+ with a dedicated application role that is not superuser and has NOBYPASSRLS.
- Do not expose PostgreSQL publicly. Restrict network access to API runtime and controlled administration.
- A reference Nginx edge template with HTTPS, security headers, request limits and query-string-free access logs is in deploy/nginx/nginx.conf. The required proxy-header snippet is in deploy/nginx/snippets/pulsegrid-proxy-headers.conf. Follow docs/OPERATIONS.md before use.

## Required environment

API:
- APP_ENV=production
- DATABASE_URL=postgresql+psycopg://... using the restricted application role.
- CORS_ORIGINS=https://your-frontend.example with exact origins only; no wildcard.
- BOOTSTRAP_TOKEN: high-entropy secret for initial administrator bootstrap. Deliver through secret manager, never source control. After bootstrap, rotate or unset it.
- Set SESSION_TTL_HOURS, INVITATION_TTL_HOURS, MAX_UPLOAD_MB, MIN_BASELINE_POINTS, ANOMALY_Z_THRESHOLD and MIN_WORKFORCE_COHORT_SIZE to reviewed values.

Frontend:
- NEXT_PUBLIC_API_URL should be the same-origin API base URL, e.g. https://your-frontend.example when reverse proxy routes API paths.

Never put secrets in NEXT_PUBLIC_* variables. Never commit a real .env file.

## Release procedure

1. Provision PostgreSQL and create a dedicated application role without superuser or BYPASSRLS privileges.
2. Configure environment variables in the hosting provider's secret/configuration manager.
3. Run migrations as a controlled release step from apps/api: alembic upgrade head. Do not run migrations from every web worker at startup.
4. Deploy API and frontend from the same reviewed commit.
5. Confirm GET /health returns HTTP 200; this is liveness only.
6. Confirm GET /ready returns HTTP 200 and a ready/database-reachable response. A 503 means database unavailable.
7. Confirm browser sign-in, organization selection, CSV import, alert review and sign-out using synthetic aggregate data.
8. Confirm cross-organization access is denied and role permissions match the role matrix.
9. Confirm browser cookies are Secure, HttpOnly for session, SameSite=Strict and scoped to intended host/path.
10. Confirm backup restoration, monitoring, alerting, secret rotation and incident response before real operational use.

## Mandatory controls before real health data

- Deploy gateway rate limiting for login, bootstrap, invitation acceptance and uploads. The reference Nginx config provides starting limits; it is not active until deployed at the public edge.
- Add account recovery, account deactivation, session revocation management and secure invitation delivery.
- Configure encrypted backups, tested restoration, retention/deletion policy and audit-log access controls.
- Add operational monitoring without logging passwords, session tokens, invitation tokens, CSV contents or sensitive observations.
- Complete independent security/privacy review and applicable legal/regulatory assessment.
- Validate workforce cohort suppression threshold and aggregation rules with domain experts.
- Use synthetic or explicitly authorized aggregate data only until all controls are independently verified.

## Health endpoints

- GET /health: process liveness; does not prove database availability.
- GET /ready: readiness; executes a lightweight database query and returns 503 when database is unavailable.

Green CI verifies automated tests, migrations, RLS checks, TypeScript and frontend production build. It does not prove live deployment, browser E2E, backup recovery or production security.

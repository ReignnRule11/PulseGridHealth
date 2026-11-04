# Deployment and operational readiness

PulseGrid Health is a demonstration MVP. Passing CI does not authorize production use with patient, employee, or other sensitive health data.

## Recommended deployment topology

- Deploy the Next.js frontend and FastAPI API behind one HTTPS origin, or use subdomains that are intentionally configured as same-site.
- Prefer a reverse proxy that routes `/api/*`, `/health`, and `/ready` to FastAPI and all other paths to Next.js. This keeps the browser API URL same-origin and avoids cross-site cookie problems with `SameSite=Strict`.
- Use managed PostgreSQL 15+ with a dedicated application role. The role must not be a superuser and must have `NOBYPASSRLS`.
- Do not expose PostgreSQL publicly. Restrict network access to the API runtime and controlled administrative access.

## Required environment

API:

- `APP_ENV=production`
- `DATABASE_URL=postgresql+psycopg://...` using the restricted application role.
- `CORS_ORIGINS=https://your-frontend.example` with exact origins only; no wildcard.
- `BOOTSTRAP_TOKEN`: a high-entropy secret for the initial administrator bootstrap. Deliver it through the deployment secret manager, never source control. After the intended bootstrap operation, rotate or unset it.
- `SESSION_TTL_HOURS`, `INVITATION_TTL_HOURS`, `MAX_UPLOAD_MB`, `MIN_BASELINE_POINTS`, `ANOMALY_Z_THRESHOLD`, and `MIN_WORKFORCE_COHORT_SIZE` set to reviewed values.

Frontend:

- `NEXT_PUBLIC_API_URL` should be the same-origin API base URL, for example `https://your-frontend.example` when the reverse proxy routes API paths.

Never put secrets in `NEXT_PUBLIC_*` variables. Never commit a real `.env` file.

## Release procedure

1. Provision PostgreSQL and create a dedicated application role with no superuser or `BYPASSRLS` privileges.
2. Configure the environment variables above in the hosting provider's secret/configuration manager.
3. Run database migrations as a controlled release step: from `apps/api`, execute `alembic upgrade head`. Do not run migrations from every web worker at startup.
4. Deploy the API and frontend from the same reviewed commit.
5. Confirm `GET /health` returns HTTP 200. This is a liveness check only.
6. Confirm `GET /ready` returns HTTP 200 and `{"status":"ready","database":"reachable"}`. A 503 indicates the API cannot reach its database.
7. Confirm browser sign-in, organization selection, CSV import, alert review, and sign-out against synthetic aggregate data.
8. Confirm cross-organization access is denied and viewer/analyst/reviewer permissions match the role matrix.
9. Confirm browser cookies are Secure, HttpOnly for the session cookie, SameSite=Strict, and scoped to the intended host/path.
10. Confirm backup restoration, monitoring, alerting, secret rotation, and incident response procedures before any real operational use.

## Mandatory controls before real health data

- Add edge or gateway rate limiting for login, bootstrap, invitation acceptance, and upload endpoints. The current application-level account lockout is not a substitute for IP/device-aware rate limiting.
- Add account recovery, account deactivation, session revocation management, and secure invitation delivery.
- Configure encrypted backups, tested restoration, retention/deletion policy, and audit-log access controls.
- Add structured operational monitoring without logging passwords, session tokens, invitation tokens, CSV contents, or sensitive health observations.
- Complete an independent security/privacy review and applicable legal/regulatory assessment.
- Validate the workforce cohort suppression threshold and aggregation rules with domain experts.
- Use synthetic or explicitly authorized aggregate data only until all controls have been independently verified.

## Health endpoints

- `GET /health`: process liveness; does not prove database availability.
- `GET /ready`: readiness; executes a lightweight database query and returns 503 when the database is unavailable.

A green CI run verifies automated tests, migrations, RLS checks, TypeScript, and the frontend production build. It does not prove a live deployment, browser-level end-to-end behavior, backup recovery, or production security.

# Render staging deployment (GitHub Blueprint)

This guide prepares a temporary, synthetic-data-only staging deployment from this repository. It does not authorize a production deployment or real health data.

## What the Blueprint creates

- `pulsegrid-web`: Next.js web service.
- `pulsegrid-api`: FastAPI service.
- `pulsegrid-staging-db`: PostgreSQL 16 database.
- Frankfurt region for all three resources.
- HTTPS endpoints managed by Render.
- API CORS restricted to the expected frontend origin.
- A generated bootstrap token stored as a Render secret.
- AI remains disabled.

The web and API services use separate `onrender.com` subdomains. They are HTTPS subdomains under the same registrable domain, so the application's `SameSite=Strict` cookies remain same-site; the API CORS allowlist is restricted to the exact web origin. Do not add wildcard origins.

## Important free-tier limits

This Blueprint deliberately selects free plans to avoid creating billable resources without approval. Render documents that free web services spin down after 15 minutes idle and can take about a minute to wake. Free Postgres is limited to 1 GB, expires 30 days after creation, and has no backups. Therefore:
- Use only synthetic demonstration data.
- Do not treat this environment as production, a durable pilot, or a place for patient/employee data.
- Export no sensitive information; the free database has no managed backup.
- Monitor the database expiry date and delete the environment when finished, or explicitly approve an upgrade after reviewing the price.

See Render's current [free-tier limitations](https://render.com/docs/free) and [Blueprint reference](https://render.com/docs/blueprint-spec).

## Connect the repository

1. Sign in to Render.
2. Open [New Blueprint](https://dashboard.render.com/blueprints).
3. Choose **Connect a repository** and authorize GitHub if prompted.
4. Select `ReignnRule11/PulseGridHealth`.
5. Render detects the root `render.yaml`. Review the three resources and confirm every plan is **Free** before applying.
6. Apply the Blueprint. Do not change any plan to a paid tier without reviewing the exact price first.
7. Wait for the API, web service and database to finish provisioning. Because automatic deploys are disabled, use the service dashboard's manual deploy action when you are ready to deploy a reviewed commit.

## Deployment-specific implementation notes

- Render's managed PostgreSQL connection string uses `postgresql://`; the API settings normalize it to the installed Psycopg 3 SQLAlchemy dialect.
- Free web services do not support Render's `preDeployCommand`. To keep this no-cost staging path deployable, the API start command runs `alembic upgrade head` before starting Uvicorn. This is acceptable only for this single-instance, synthetic-data staging environment. Before a paid or multi-instance deployment, move migrations into a dedicated release/pre-deploy step and use separate migration/runtime database roles.
- The API health check is `/health`; after the first start, separately verify `/ready` returns 200. A healthy process with an unavailable database is not ready.
- The frontend build embeds `NEXT_PUBLIC_API_URL`; changing the API hostname requires a frontend rebuild.
- The generated `BOOTSTRAP_TOKEN` is available only in Render's protected environment settings. Do not paste it into chat, GitHub issues, logs or source files. Use it only for the first administrator bootstrap, then rotate/unset it.

## Required post-deploy verification

1. Confirm both services have HTTPS URLs and record the deployed commit SHA.
2. Open the API `/health` endpoint; expect HTTP 200.
3. Open the API `/ready` endpoint; expect HTTP 200 and database reachable.
4. Verify the API's environment has `APP_ENV=production`, exact `CORS_ORIGINS`, a generated bootstrap token and `AI_ENABLED=false`.
5. Run the complete synthetic browser workflow: bootstrap, sign-in, organization selection, CSV import, alert review, invitation/role restrictions, cross-tenant denial and sign-out.
6. Inspect cookie attributes: session cookie must be Secure, HttpOnly and SameSite=Strict; CSRF cookie must be Secure and SameSite=Strict.
7. Verify PostgreSQL runtime role is non-superuser and NOBYPASSRLS, and repeat tenant-isolation tests against the hosted database.
8. Record results in [E1 tracking issue](https://github.com/ReignnRule11/PulseGridHealth/issues/1).

A successful Render deploy is not proof of the complete E1 acceptance criteria. Rate limiting, redacted logs, encrypted backups/restore, independent security/privacy review and data-authority approval remain outstanding. Do not load real health data until E1 is formally complete.

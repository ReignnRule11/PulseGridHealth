# Render API staging deployment with Neon

This guide prepares a temporary, synthetic-data-only FastAPI staging deployment on Render using Neon PostgreSQL. It does not authorize a production deployment or real health data. The Blueprint provisions only the API; it does not create a Render database or deploy the frontend.

## What the Blueprint configures

- `pulsegrid-api`: FastAPI web service on Render.
- Frankfurt Render region; choose a Neon region close to Frankfurt to reduce database latency.
- Render-managed HTTPS endpoint; optionally attach your custom API subdomain after the service is deployed.
- `DATABASE_URL` and `MIGRATION_DATABASE_URL` as manually supplied protected environment variables.
- Exact `CORS_ORIGINS` set to the Vercel default HTTPS origin after the frontend project URL is known.
- A generated bootstrap token stored as a Render secret.
- AI remains disabled.
- Automatic deploys are off; deployment is a deliberate manual action.

## Neon connection design

Use two Neon connection strings for the same database:

- `DATABASE_URL`: runtime role, preferably Neon pooled endpoint, least-privilege role, TLS required.
- `MIGRATION_DATABASE_URL`: direct/non-pooler endpoint, migration-owner role, TLS required.

Do not use the Neon owner connection as the API runtime identity. Follow [NEON_SETUP.md](NEON_SETUP.md) to create the restricted role and grant only application table/sequence access. The startup command applies migrations with the migration URL, then runs the runtime-role verifier using `DATABASE_URL`; the API will not start if the runtime role can bypass RLS, administer roles/database, create schema objects, or own tenant tables.

## Connect the repository

1. Sign in to Render and open [New Blueprint](https://dashboard.render.com/blueprints).
2. Connect GitHub and select `ReignnRule11/PulseGridHealth`.
3. Review the root `render.yaml`. It should show **one API service only** and no Render PostgreSQL resource.
4. Apply the Blueprint. The dashboard will ask you to supply the unsynced environment values.
5. In the API service's protected environment settings, set:
   - `DATABASE_URL`: Neon pooled runtime connection string.
   - `MIGRATION_DATABASE_URL`: Neon direct migration-owner connection string.
   - `CORS_ORIGINS`: exact Vercel origin, e.g. `https://your-project.vercel.app`. Do not use `*`.
6. Keep `AI_ENABLED=false` and automatic deploys disabled.
7. Do not paste either database URL or the bootstrap token into GitHub, chat, logs or screenshots.

## Deployment and verification

1. Review the exact commit and CI result before using Render's manual deploy.
2. Confirm the migration step completes successfully.
3. Confirm the runtime-role verification reports PASS before Uvicorn starts.
4. Confirm Render's API HTTPS URL and deployed commit SHA.
5. Check API `/health` returns HTTP 200.
6. Check API `/ready` returns HTTP 200 and database reachable.
7. Deploy the frontend to Vercel using its default `*.vercel.app` domain. Set the Vercel server-side environment variable `API_BACKEND_ORIGIN` to the Render HTTPS origin (e.g. `https://your-api.onrender.com`). Do not set `NEXT_PUBLIC_API_URL` in production; the browser must use relative `/api/...` paths through the same-origin rewrite. Set Render `CORS_ORIGINS` to the exact Vercel origin.
8. Run the complete synthetic browser workflow: bootstrap, sign-in, organization selection, CSV import, alert review, invitation/role restrictions, cross-tenant denial and sign-out.
9. Inspect cookies on the Vercel origin: session cookie must be Secure, HttpOnly and SameSite=Strict; CSRF cookie must be Secure and SameSite=Strict. Confirm the browser never calls the Render origin directly for authenticated API requests.
10. Record results in [E1 tracking issue](https://github.com/ReignnRule11/PulseGridHealth/issues/1).

## Limits and remaining gates

The free Render web service may spin down after inactivity and cold-start slowly. Confirm current plan limits and pricing before applying; do not assume free-tier availability or durability. Neon plan limits, compute scale-to-zero, connection limits, backup/restore retention and pricing must also be reviewed in the Neon console. This setup is synthetic staging only.

Rate limiting, provider/edge log inspection, encrypted backup/restore rehearsal, uptime/error alerting, independent security/privacy review and data-authority approval remain outstanding. Do not load real health data until E1 is formally complete.

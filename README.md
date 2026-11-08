# PulseGrid Health

[![CI](https://github.com/ReignnRule11/PulseGridHealth/actions/workflows/ci.yml/badge.svg)](https://github.com/ReignnRule11/PulseGridHealth/actions/workflows/ci.yml)

**Population and Workforce Health Early-Warning Intelligence**

PulseGrid Health is an organization-scoped application for importing aggregate community and workforce health observations, screening historical time series for unusual increases, and routing statistical candidate signals into a documented human-review workflow.

It is designed as an early-warning and review-support layer. It is **not** an electronic medical record (EMR), diagnostic system, outbreak declaration service, clinical prediction model, or autonomous occupational-health decision-maker.

> [!IMPORTANT]
> This repository contains a demonstration MVP. Use synthetic data or explicitly authorized aggregate data only. Do not upload patient-identifiable or employee-identifiable records. Candidate alerts are statistical signals, not diagnoses or confirmed events, and require qualified human review. The system has not been clinically or epidemiologically validated and is not certified for regulated health-data processing.

---

## Contents

- [What the application currently does](#what-the-application-currently-does)
- [Architecture](#architecture)
- [Technology stack](#technology-stack)
- [Repository structure](#repository-structure)
- [Data model](#data-model)
- [Observation ingestion](#observation-ingestion)
- [Anomaly screening](#anomaly-screening)
- [Human review workflow](#human-review-workflow)
- [Identity, roles and tenant isolation](#identity-roles-and-tenant-isolation)
- [AI explanation capability](#ai-explanation-capability)
- [API routes](#api-routes)
- [Local development](#local-development)
- [Synthetic data and evaluation](#synthetic-data-and-evaluation)
- [Tests and continuous integration](#tests-and-continuous-integration)
- [Configuration](#configuration)
- [Deployment notes](#deployment-notes)
- [Known limitations and production gates](#known-limitations-and-production-gates)
- [Additional documentation](#additional-documentation)

## What the application currently does

The current implementation provides these connected capabilities:

1. **Aggregate CSV ingestion** — accepts structured observations for community or workforce groups, validates the upload and individual rows, checks duplicates and persists accepted records.
2. **Historical statistical screening** — compares each new observation with prior observations for the same organization, group and indicator using a median / median absolute deviation (MAD) method.
3. **Evidence-backed candidate alerts** — stores detector output, including the baseline, score when calculable, history count, threshold, reason and detector version.
4. **Human review and investigation** — supports acknowledgement, investigation creation, findings, response actions, resolution and review-history retrieval.
5. **Organization workspaces** — supports initial organization bootstrap, sign-in, invitation-based onboarding, organization selection and role-aware workspace behavior.
6. **Tenant-scoped persistence** — applies organization membership checks and PostgreSQL row-level security (RLS) to tenant-owned data.
7. **Optional AI-assisted interpretation** — includes a server-side OpenAI-compatible provider adapter for qualitative explanations of existing candidate alerts. The feature is disabled by default; a successful live provider request has not been verified.

### Observation domains in the current implementation

| Domain | Data represented in the repository | Grouping |
|---|---|---|
| Community | Aggregate, date-grained health indicators. The synthetic scenario includes weekly febrile-illness reports. | Organization-owned community / region code |
| Workforce | Aggregate symptom and environmental indicators. The synthetic scenario includes heat-related symptom reports and mean heat index. | Organization-owned workforce group / location code |

An observation is associated with exactly one domain target: a community or a workforce group. Workforce observations are suppressed when cohort size is unknown or below the configured minimum. The default minimum is 20; this is an implementation default, not a universally validated privacy threshold.

## Architecture

The repository is a **modular monolith**, not a microservices deployment.

| Component | Responsibility |
|---|---|
| Next.js web application | Browser UI, authentication flow, organization workspace, CSV upload and alert review interactions |
| FastAPI application | HTTP API, request validation, authentication dependencies, ingestion, detection orchestration and review/AI routes |
| PostgreSQL | Persistent organization, identity, observation, detection, alert, investigation and audit data |
| SQLAlchemy | Database models and application queries |
| Alembic | Versioned database schema migrations |
| GitHub Actions | Backend, migration, RLS, frontend and browser end-to-end checks |

### Request and data flow

1. A signed-in organization member selects an organization workspace.
2. An authorized administrator or analyst submits an aggregate CSV file.
3. The API checks the upload media type and byte limit, validates the CSV header and parses rows into typed input models.
4. The API resolves organization-owned source and group records, applies workforce cohort suppression, and skips duplicate observations.
5. Accepted observations are persisted. The detector evaluates each observation against preceding observations in its own organization/group/indicator series.
6. A candidate alert is persisted when the detector identifies an unusual increase.
7. An authorized reviewer acknowledges the candidate, starts an investigation, records findings and response actions, and may resolve it.
8. The web workspace retrieves organization-scoped summaries, alerts and review history.

The browser is an untrusted client. Authorization and tenant checks are performed by the API and database; hiding a UI control is not treated as a security boundary.

## Technology stack

| Layer | Technologies evidenced in the repository |
|---|---|
| Web framework | Next.js 15 App Router |
| UI | React 19, TypeScript 5.7 |
| Styling | CSS |
| API framework | Python 3.11+, FastAPI, Uvicorn |
| Request/data validation | Pydantic 2 and pydantic-settings |
| Persistence | SQLAlchemy 2, PostgreSQL |
| Migrations | Alembic |
| PostgreSQL driver | Psycopg 3 |
| Password hashing | Python standard-library hashlib.scrypt |
| Backend tests | pytest, HTTPX |
| Browser tests | Playwright |
| CI | GitHub Actions |

Exact dependency ranges are declared in `apps/api/requirements.txt` and `apps/web/package.json`.

There is no trained machine-learning model, real-time sensor connector, external epidemiological feed, or native mobile application in this repository. The anomaly detector is deterministic statistical code. The optional LLM adapter does not detect anomalies or make decisions.

## Repository structure

The following tree is based on the tracked files on the repository's `main` branch. It includes the actual application, tests, migrations, scripts, deployment templates and documentation. Empty package-marker files and generated files are shown where useful; generated local datasets are not tracked in this tree.

```text
PulseGridHealth/
├── .env.example
├── .github/
│   └── workflows/
│       ├── ai-provider-smoke.yml
│       └── ci.yml
├── .gitignore
├── README.md
├── render.yaml
├── apps/
│   ├── api/
│   │   ├── alembic.ini
│   │   ├── requirements.txt
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── ai_intelligence.py
│   │   │   ├── db.py
│   │   │   ├── main.py
│   │   │   ├── models.py
│   │   │   ├── review.py
│   │   │   ├── review_schemas.py
│   │   │   ├── schemas.py
│   │   │   ├── security.py
│   │   │   ├── core/
│   │   │   │   ├── __init__.py
│   │   │   │   └── config.py
│   │   │   └── services/
│   │   │       ├── __init__.py
│   │   │       ├── detection.py
│   │   │       └── ingestion.py
│   │   ├── migrations/
│   │   │   ├── env.py
│   │   │   ├── script.py.mako
│   │   │   └── versions/
│   │   │       ├── 0001_initial.py
│   │   │       ├── 0002_alert_review.py
│   │   │       ├── 0003_identity_access.py
│   │   │       └── 0004_tenant_isolation.py
│   │   ├── scripts/
│   │   │   ├── ai_provider_smoke.py
│   │   │   ├── test_rls.py
│   │   │   └── verify_rls.py
│   │   └── tests/
│   │       ├── test_api.py
│   │       ├── test_auth.py
│   │       ├── test_authenticated_workspace.py
│   │       ├── test_config.py
│   │       ├── test_detection.py
│   │       ├── test_evaluation.py
│   │       ├── test_ingestion.py
│   │       └── test_review.py
│   └── web/
│       ├── .env.example
│       ├── next-env.d.ts
│       ├── next.config.ts
│       ├── package.json
│       ├── playwright.config.ts
│       ├── tsconfig.json
│       ├── app/
│       │   ├── globals.css
│       │   ├── layout.tsx
│       │   └── page.tsx
│       ├── components/
│       │   ├── review-panel.tsx
│       │   ├── upload-form.tsx
│       │   └── workspace.tsx
│       └── tests/
│           └── e2e/
│               └── workspace.spec.ts
├── deploy/
│   └── nginx/
│       ├── nginx.conf
│       └── snippets/
│           └── pulsegrid-proxy-headers.conf
├── docs/
│   ├── AI_ARCHITECTURE.md
│   ├── ARCHITECTURE.md
│   ├── DATABASE.md
│   ├── DEPLOYMENT.md
│   ├── EVALUATION.md
│   ├── GITHUB_SETUP.md
│   ├── IMPLEMENTATION_PLAN.md
│   ├── OPERATIONS.md
│   ├── PRD.md
│   ├── RENDER_STAGING.md
│   └── SECURITY.md
└── scripts/
    ├── evaluate_synthetic_detector.py
    └── generate_synthetic_data.py
```

### Important code locations

| Path | Responsibility |
|---|---|
| `apps/api/app/main.py` | FastAPI application, health/readiness endpoints, dashboard and alert reads, CSV import and detection orchestration |
| `apps/api/app/security.py` | Bootstrap, login, session handling, CSRF/origin checks, invitations, membership and role enforcement |
| `apps/api/app/models.py` | SQLAlchemy entities, constraints and indexes |
| `apps/api/app/services/ingestion.py` | CSV decoding, required-column checks, row parsing and validation |
| `apps/api/app/services/detection.py` | Deterministic median/MAD anomaly-screening function |
| `apps/api/app/review.py` | Alert acknowledgement, investigations, findings, response actions, resolution and audit history |
| `apps/api/app/ai_intelligence.py` | Optional provider adapter, evidence assembly and output validation |
| `apps/api/migrations/versions/` | Initial schema, review workflow, identity/access and tenant-isolation migrations |
| `apps/web/components/workspace.tsx` | Main authenticated browser workspace and API integration |
| `apps/web/tests/e2e/workspace.spec.ts` | Browser workflow and access-boundary tests |
| `scripts/` | Synthetic data generation and offline detector evaluation |
| `render.yaml` | Render staging Blueprint definition |
| `deploy/nginx/` | Reference reverse-proxy configuration templates; not automatically active |

## Data model

The SQLAlchemy models and migrations define the following principal records:

| Entity / table | Purpose |
|---|---|
| `organizations` | Organization / tenant identity |
| `users` | User accounts and password hashes |
| `organization_memberships` | User-to-organization membership and role |
| `auth_sessions` | Hashed session token, CSRF hash, expiry and revocation |
| `organization_invitations` | Hashed, expiring, single-use invitation tokens and assigned roles |
| `communities` | Organization-owned community / region groups |
| `workforce_groups` | Organization-owned workforce groups and cohort-size metadata |
| `data_sources` | Organization-scoped source identifiers and provenance metadata |
| `health_observations` | Aggregate, date-grained observations |
| `detection_results` | Detector output, baseline evidence and detector metadata |
| `alerts` | Candidate signals and review status |
| `investigations` | Human investigation status, findings, disposition and resolution rationale |
| `response_actions` | Actions recorded against an investigation/alert |
| `audit_logs` | Organization-scoped review and response events |

Notable database constraints include:
- An observation must reference exactly one of a community or a workforce group.
- Observation values must be non-negative.
- A supplied denominator must be positive.
- Membership and invitation roles are restricted to the supported role values.
- Unique indexes protect against duplicate observations for the same source, group, date and indicator.
- The tenant-isolation migration enables PostgreSQL RLS for tenant-owned tables and applies forced row-level security policies.

The runtime database role must be a restricted, non-superuser role without `BYPASSRLS`. PostgreSQL superusers bypass row-level security; using a superuser as the application runtime role defeats this isolation boundary.

## Observation ingestion

The API accepts UTF-8 CSV uploads using this exact column set:

```csv
domain,group_code,source_code,observed_date,indicator,value,denominator,unit
community,C001,SYNTHETIC,2026-01-05,weekly_febrile_illness_reports,12,5500,reports
workforce,W001,SYNTHETIC,2026-01-05,weekly_heat_related_symptom_reports,5,250,reports
```

| Column | Meaning and validation |
|---|---|
| `domain` | `community` or `workforce` |
| `group_code` | Organization-scoped community or workforce group code |
| `source_code` | Source identifier |
| `observed_date` | ISO date |
| `indicator` | Indicator name |
| `value` | Finite, non-negative numeric value |
| `denominator` | Optional positive integer; blank is allowed |
| `unit` | Measurement unit |

The current implementation:
- Allows CSV media types `text/csv`, `application/vnd.ms-excel` and `application/octet-stream`.
- Enforces a configurable upload byte limit (default 5 MB).
- Requires the exact set of column names and rejects duplicate/missing/extra headers.
- Validates each row with a typed Pydantic model.
- Counts accepted, duplicate and rejected rows and returns bounded row-error details.
- Processes rows in chronological order and checks for duplicate source/group/date/indicator records.
- Suppresses workforce rows when cohort size is unknown or below `MIN_WORKFORCE_COHORT_SIZE`.

Only aggregate data should be uploaded. Do not include names, email addresses, staff IDs, patient IDs, phone numbers, free-text case notes or other direct identifiers.

## Anomaly screening

The current detector is a univariate, historical robust-deviation screen implemented in `apps/api/app/services/detection.py`.

1. The API selects preceding observations for the same organization, group and indicator.
2. It uses a configurable minimum history (default: 6 observations).
3. It calculates the historical median.
4. It calculates the median absolute deviation (MAD).
5. It scales MAD by 1.4826 and calculates a robust deviation score.
6. It flags unusually high values at or above the configured threshold (default: 3.5).

The operational API uses up to the preceding 26 observations and processes imported observations chronologically. It does not score an observation using later records.

When MAD is zero, the detector does not fabricate a score: a value equal to the baseline is treated as stable; a different value receives a `zero_mad_requires_review` reason and is not automatically classified as a candidate by this detector.

Detection records include the baseline, score when calculable, reason, threshold, history count and detector name/version (`median_mad`, version `0.2.0`). Candidate severity is assigned from the score when the candidate alert is created.

**Interpretation limit:** this is anomaly screening, not causal analysis, diagnosis, outbreak prediction or a validated clinical/occupational risk model. A candidate must be interpreted in context by an appropriately qualified reviewer.

## Human review workflow

The review API supports the following state progression:

```text
pending_review
      |
      | acknowledge (org_admin or reviewer)
      v
acknowledged
      |
      | start investigation (org_admin or reviewer)
      v
investigating
      |
      +--> record findings / disposition
      |
      +--> add response action(s)
      |
      +--> resolve with rationale
```

Review actions are recorded in the audit log. The implementation validates expected state transitions and organization ownership before changing an alert. Reviewers are responsible for determining what a candidate means; the application does not automatically declare an outbreak or initiate real-world interventions.

## Identity, roles and tenant isolation

Four organization roles are implemented:

| Capability | `org_admin` | `analyst` | `reviewer` | `viewer` |
|---|:---:|:---:|:---:|:---:|
| View organization dashboard and alerts | Yes | Yes | Yes | Yes |
| Import aggregate CSV observations | Yes | Yes | No | No |
| Run detection | Yes | Yes | No | No |
| Acknowledge alerts | Yes | No | Yes | No |
| Start investigations and record findings | Yes | No | Yes | No |
| Add response actions and resolve alerts | Yes | No | Yes | No |
| Create organization invitations | Yes | No | No | No |

The API enforces role permissions server-side. Authentication uses:
- Scrypt password hashes.
- Opaque, database-backed session tokens; only token hashes are stored.
- HttpOnly session cookies, with Secure enabled when `APP_ENV=production`.
- SameSite=Strict cookies.
- CSRF token validation and origin checks for state-changing requests.
- Session expiry and server-side revocation on logout.
- Temporary account lockout after repeated failed login attempts.
- Hashed, expiring, single-use invitation tokens. Invitation delivery is manual; the API returns a token for delivery through a separate secure channel.

Tenant-owned database work sets an organization context and uses RLS policies. Authenticated organization requests require an active membership and an organization identifier. Do not treat frontend role-based visibility as authorization.

## AI explanation capability

The repository contains `apps/api/app/ai_intelligence.py`, a server-side adapter for an OpenAI-compatible chat-completions endpoint. It is intended to generate qualitative explanations for existing statistical candidate alerts using tenant-scoped aggregate evidence.

The current implementation includes:
- A feature flag; `AI_ENABLED` defaults to `false`.
- Provider configuration through environment variables.
- A bounded request timeout and response-size limit.
- A strict Pydantic output schema.
- Evidence-reference validation against supplied evidence IDs.
- Rejection of numeric claims in model-authored prose; numeric facts remain server-derived.
- Human-review and candidate-signal constraints in the response contract.
- Audit logging of provider/model identifiers and evidence references.

AI does not run the anomaly detector, create the underlying statistical evidence, diagnose, declare an outbreak or make employment/clinical decisions. The generated explanation is returned to the caller and is not persisted as a durable explanation record in the current implementation.

**Operational status:** AI is disabled by default. A live provider smoke test has not passed with the currently available provider account because the provider returned an insufficient-quota / exhausted-credit response. Do not describe live AI inference as verified or enable the feature until provider access, cost controls and operational safeguards have been independently confirmed.

The broader AI roadmap described in `docs/AI_ARCHITECTURE.md` includes proposed capabilities beyond the implemented AI explanation endpoint. Proposed capabilities should not be read as shipped functionality.

## API routes

The following routes are defined in the current FastAPI application and included routers:

| Method | Route | Purpose |
|---|---|---|
| GET | `/health` | Process liveness |
| GET | `/ready` | Database readiness check |
| GET | `/api/v1/auth/csrf` | Issue a CSRF token |
| POST | `/api/v1/auth/bootstrap` | Create the initial organization and administrator |
| POST | `/api/v1/auth/login` | Authenticate and create a session |
| POST | `/api/v1/auth/logout` | Revoke the current session and clear cookies |
| GET | `/api/v1/auth/me` | Return current identity and organization memberships |
| POST | `/api/v1/auth/organizations/{organization_id}/invitations` | Create an organization invitation |
| POST | `/api/v1/auth/invitations/accept` | Accept an invitation |
| GET | `/api/v1/dashboard` | Organization-scoped dashboard summary |
| GET | `/api/v1/alerts` | Organization-scoped candidate-alert list |
| POST | `/api/v1/observations/import` | Import an aggregate CSV file (multipart field: `file`) |
| POST | `/api/v1/detection/run` | Evaluate observations without stored detection results |
| POST | `/api/v1/ai/alerts/{alert_id}/explanation` | Request a qualitative AI explanation (feature disabled unless configured) |
| POST | `/api/v1/alerts/{alert_id}/acknowledge` | Acknowledge a candidate alert |
| POST | `/api/v1/alerts/{alert_id}/investigation` | Start an investigation |
| POST | `/api/v1/alerts/{alert_id}/findings` | Record investigation findings |
| POST | `/api/v1/alerts/{alert_id}/actions` | Add a response action |
| POST | `/api/v1/alerts/{alert_id}/resolve` | Resolve an alert |
| GET | `/api/v1/alerts/{alert_id}/history` | Retrieve review history |

Authenticated organization data routes require a valid session and active organization membership. Organization-scoped requests use the `X-Organization-ID` header. Mutating authenticated requests require `X-CSRF-Token`; bootstrap additionally requires `X-Bootstrap-Token`.

## Local development

### Prerequisites

- Python 3.11 or newer.
- Node.js 22 or newer.
- PostgreSQL 15 or newer.
- Git.

The repository's documented local workflow does not require Docker.

### 1. Configure the API

Create a local environment file from the root `.env.example` and set `DATABASE_URL` to a local PostgreSQL database. The settings loader reads environment variables and is configured with a relative `.env` path; when running commands from `apps/api`, make sure the environment values are available to the process.

From the repository root:

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

On Windows, activate the virtual environment with:

```powershell
.venv\Scripts\activate
```

The API listens on the local Uvicorn address (by default, `http://127.0.0.1:8000`).

### 2. Configure the web application

In a second terminal:

```bash
cd apps/web
```

Create `.env.local` with the API base URL:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Install dependencies and start Next.js:

```bash
npm install
npm run dev
```

Open the local URL printed by Next.js (normally `http://localhost:3000`). The API URL must be reachable from the browser. For hosted deployments, use a topology compatible with the application's SameSite=Strict session cookies and exact CORS allowlist.

### 3. Bootstrap the first administrator

Set a high-entropy `BOOTSTRAP_TOKEN` in the API environment before calling `POST /api/v1/auth/bootstrap`. First obtain a CSRF token from `GET /api/v1/auth/csrf`, then submit the bootstrap request with the CSRF token and `X-Bootstrap-Token` headers. Bootstrap creates the organization, user and `org_admin` membership. Sign in separately through the normal login endpoint.

Rotate or unset the bootstrap token after the intended bootstrap operation. Do not commit it or share it in source control, logs or chat.

### 4. Environment file safety

The root `.env.example` and web `apps/web/.env.example` are templates. Create local private environment files as needed. Never commit real credentials, database URLs, provider API keys, bootstrap tokens, session tokens or other secrets. Never place secrets in `NEXT_PUBLIC_*` variables; those values are exposed to the browser.

## Synthetic data and evaluation

Generate reproducible synthetic inputs from the repository root:

```bash
python scripts/generate_synthetic_data.py --output datasets/synthetic --seed 20261104
```

The generator writes:
- `community_observations.csv`
- `workforce_observations.csv`
- `ground_truth.csv`

The observation files are intended for import through the workspace. Ground-truth labels are separate and are used only by the offline evaluation script; they are not detector inputs.

Run the offline benchmark:

```bash
python scripts/evaluate_synthetic_detector.py --input datasets/synthetic --output evaluation_report.json
```

The benchmark replays observations chronologically and reports confusion counts, precision, recall, F1, false alerts per group-week and mean detection delay, separately for community and workforce domains.

This is an engineering benchmark against deliberately planted synthetic changes, not evidence of clinical validity, outbreak prediction, occupational-health efficacy or real-world performance. Results depend on the generator seed and detector parameters. See `docs/EVALUATION.md`.

## Tests and continuous integration

Backend tests are under `apps/api/tests`. The GitHub Actions workflow `.github/workflows/ci.yml` currently defines three jobs:

- **Backend:** starts PostgreSQL 15, installs Python dependencies, runs pytest, applies Alembic migrations, runs the RLS verification script, downgrades to base and upgrades again.
- **Frontend:** uses Node.js 22, installs npm dependencies, runs TypeScript checking and creates a Next.js production build.
- **Browser E2E:** starts PostgreSQL, applies migrations, installs Playwright/Chromium, then runs the browser workflow against local API and web servers.

Useful local checks:

Backend, from `apps/api`:

```bash
PYTHONPATH=. pytest
```

Frontend, from `apps/web`:

```bash
npx tsc --noEmit
npm run build
```

Browser E2E, from `apps/web` (with the required local PostgreSQL test database available):

```bash
npx playwright install chromium
npm run test:e2e
```

The CI workflow also contains a separate `.github/workflows/ai-provider-smoke.yml` workflow for an explicitly configured provider smoke test. A green standard CI run does not mean that a live AI provider call succeeded or that a hosted deployment is operational.

**Latest repository check recorded for the current staging Blueprint change:** GitHub Actions run [#98](https://github.com/ReignnRule11/PulseGridHealth/actions/runs/42219382447) passed its backend, frontend and E2E jobs. This is CI evidence for that commit, not proof of production readiness or successful live staging API routing.

## Configuration

The API settings are defined in `apps/api/app/core/config.py`. The main variables are:

| Variable | Purpose | Default in application |
|---|---|---|
| `DATABASE_URL` | PostgreSQL SQLAlchemy connection URL | Required |
| `APP_ENV` | Runtime environment; controls production cookie security behavior | `development` |
| `CORS_ORIGINS` | Comma-separated exact allowed browser origins | `http://localhost:3000` |
| `MAX_UPLOAD_MB` | Maximum CSV upload size in MiB | `5` |
| `MIN_BASELINE_POINTS` | Minimum historical observations for screening | `6` |
| `ANOMALY_Z_THRESHOLD` | Robust deviation threshold | `3.5` |
| `MIN_WORKFORCE_COHORT_SIZE` | Minimum workforce group size for inclusion | `20` |
| `BOOTSTRAP_TOKEN` | Secret authorizing initial administrator bootstrap | Empty |
| `SESSION_TTL_HOURS` | Session lifetime | `12` |
| `INVITATION_TTL_HOURS` | Invitation lifetime | `72` |
| `AI_ENABLED` | Enables the optional AI explanation endpoint | `false` |
| `AI_PROVIDER_NAME` | Provider identifier used in configuration/audit metadata | `openai_compatible` |
| `AI_API_BASE` | OpenAI-compatible API base URL | `https://api.openai.com/v1` |
| `AI_API_KEY` | Provider credential | Empty |
| `AI_MODEL` | Provider model identifier | `gpt-4.1-mini` |
| `AI_TIMEOUT_SECONDS` | Provider request timeout | `20` |

The Render Blueprint supplies staging-specific values for several of these settings. Review the configuration files before deploying; do not assume a sample/default value is appropriate for another environment.

## Deployment notes

### Render staging Blueprint

The root `render.yaml` defines a temporary staging topology with:
- A Python API web service (`pulsegrid-api`).
- A Node web service (`pulsegrid-web`).
- A PostgreSQL 16 database (`pulsegrid-staging-db`).
- Frankfurt region and free-tier plans.
- AI explicitly disabled.
- Automatic deployment disabled.

The API start command runs `alembic upgrade head` before Uvicorn. The repository documents this as a staging-only compromise for the free service configuration. For a paid or multi-instance deployment, migrations should be moved to a controlled release/pre-deploy step and separated from the runtime database role.

The frontend build embeds `NEXT_PUBLIC_API_URL`; changing the API hostname requires a frontend rebuild. The API's `/health` endpoint is a liveness check; `/ready` additionally checks database connectivity.

> [!WARNING]
> Render's free PostgreSQL instance is temporary (30-day expiry), limited in storage and does not include managed backups. Free web services can spin down when idle. This environment is for synthetic demonstrations only, not production, durable pilot use or sensitive health data. Check current provider limits before relying on the environment.

**Staging verification is not complete.** The frontend hostname was reachable during a browser check, but the configured public API hostname returned routes belonging to a different application rather than this repository's FastAPI routes. The Render service dashboard still needs authenticated inspection to confirm the actual service hostname, deployed commit and service configuration. Do not use that API hostname for PulseGrid Health until the mapping is corrected and `/health`, `/ready` and the complete synthetic browser workflow have been verified against the correct API.

### Production deployment is not a supported claim

`docs/DEPLOYMENT.md`, `docs/OPERATIONS.md` and `deploy/nginx/` contain reference guidance and templates. They do not mean that a production edge proxy, backup process, monitoring stack or recovery process has been deployed. Read and adapt those documents before any controlled pilot.

## Known limitations and production gates

The current codebase is a demonstration MVP. Important limitations include:

- No clinical, epidemiological or occupational-health validation of indicators, thresholds or detector performance.
- No patient/employee identifiable data handling authorization or regulatory certification.
- No real-time sensor integration or external epidemiological data feed.
- No trained ML model; the operational detector is a deterministic univariate statistical method.
- AI is disabled by default; live provider inference has not been verified due to provider quota/credit failure.
- Invitation tokens are returned for manual secure delivery; automated email delivery is not implemented.
- Account recovery, administrator-managed account deactivation and session-management workflows are not implemented.
- The Render free database is temporary and has no managed backups.
- Staging API hostname/routing has not yet been validated as serving this repository's API.
- The Nginx configuration is a reference template, not an active public edge deployment.
- Production rate limiting, encrypted backups and tested restoration, retention/deletion controls, monitoring, incident response, and independent security/privacy/legal review remain release requirements.

Before any real operational or sensitive-data use, the deployment needs a restricted PostgreSQL runtime role without `BYPASSRLS`, verified tenant isolation, rate limiting, secure invitation delivery, account recovery and session revocation, encrypted backups with restore rehearsals, defined retention/deletion, operational monitoring, incident response, and independent privacy/security/domain review. Workforce cohort thresholds and aggregation rules must be validated for the intended context.

## Additional documentation

| Document | Contents |
|---|---|
| [Product requirements](docs/PRD.md) | Product scope, requirements and acceptance criteria |
| [Architecture](docs/ARCHITECTURE.md) | Runtime components, request/data flow and trust boundaries |
| [Database notes](docs/DATABASE.md) | Data model and database considerations |
| [AI architecture](docs/AI_ARCHITECTURE.md) | Implemented AI-1 boundary and proposed future AI capabilities |
| [Evaluation](docs/EVALUATION.md) | Synthetic detector benchmark method and limitations |
| [Deployment](docs/DEPLOYMENT.md) | Recommended topology and release requirements |
| [Render staging](docs/RENDER_STAGING.md) | Blueprint setup and staging verification checklist |
| [Operations](docs/OPERATIONS.md) | Release, proxy, database, backup, monitoring and incident runbook |
| [Security baseline](docs/SECURITY.md) | Security principles and boundaries |
| [Implementation plan](docs/IMPLEMENTATION_PLAN.md) | Phased implementation plan |
| [GitHub setup](docs/GITHUB_SETUP.md) | Repository and CI setup notes |

---

## Project status

PulseGrid Health has a working codebase with automated backend, migration, frontend and browser E2E checks. The current status should be described precisely:

- **Implemented in the repository:** aggregate CSV ingestion, deterministic anomaly screening, organization workspaces, identity and roles, tenant isolation, human alert review, audit history and an optional AI explanation adapter.
- **Automated checks:** the referenced CI run passed backend, frontend and E2E jobs.
- **AI provider:** not live-verified; disabled by default.
- **Hosted staging:** frontend reachable, API hostname mapping unresolved; end-to-end staging verification incomplete.
- **Production:** not approved or ready for real patient/employee data.

For development, testing and demonstration, use synthetic aggregate data and keep the human-review boundary intact.

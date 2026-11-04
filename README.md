# PulseGrid Health


[![Phase 1 CI](https://github.com/ReignnRule11/PulseGridHealth/actions/workflows/ci.yml/badge.svg)](https://github.com/ReignnRule11/PulseGridHealth/actions/workflows/ci.yml)


**Population and Workforce Health Early-Warning Intelligence**

PulseGrid Health is an organization-scoped prototype for collecting aggregate community and workforce health observations, screening historical signals for unusual increases, and routing statistical candidates into a documented human-review workflow.

It is an **early-warning and review-support layer**. It is not an electronic medical record (EMR), diagnostic system, outbreak declaration service, clinical prediction model, or autonomous occupational-health decision-maker.

> **Data and safety boundary:** The current implementation is a demonstration MVP. Use synthetic data or explicitly authorized aggregate data only. Do not upload patient-identifiable or employee-identifiable records. Candidate alerts are statistical signals and require qualified human review. The platform has not been clinically or epidemiologically validated and is not certified for regulated health-data processing.

## 1. Platform overview

The current repository implements five connected capabilities:

1. **Aggregate signal ingestion** — accepts structured CSV observations for community and workforce groups, validates the file and individual rows, and persists accepted records.
2. **Historical anomaly screening** — compares each new observation with prior observations for the same organization, group, and indicator using a median/MAD robust-deviation method.
3. **Evidence-backed candidate alerts** — stores the baseline, score (where calculable), history count, detector metadata, and an explanation for signals that cross the configured threshold.
4. **Human review and investigation** — supports acknowledgement, investigation, findings, response actions, resolution, and review-history retrieval.
5. **Organization workspace and access control** — provides sign-in, invitation-based onboarding, organization selection, role-aware workspace controls, and organization-scoped API/database access.

### Supported observation domains

| Domain | Current data represented | Grouping |
|---|---|---|
| Community | Aggregate weekly health indicators; the included synthetic scenario uses weekly febrile-illness reports | Community / region code |
| Workforce | Aggregate health-symptom and environmental indicators; the included synthetic scenario uses heat-related symptom reports and mean heat index | Workforce group / location code |

Each observation belongs to exactly one domain target: a community or a workforce group. Workforce observations are suppressed when the cohort size is unknown or below the configured minimum. The default minimum is 20; deployments should review this threshold with appropriate domain and privacy experts.

## 2. Product workflow

1. An organization administrator bootstraps the first organization and administrator account using a configured bootstrap secret.
2. The administrator signs in and can invite members with one of the supported roles.
3. Invitees accept a single-use invitation token and create their account credentials.
4. An authorized administrator or analyst uploads an aggregate CSV file.
5. The API validates the file, rejects invalid rows, checks duplicates and cohort suppression, and stores accepted observations.
6. The detector evaluates each observation against historical values only; it does not use future observations.
7. Candidate alerts are persisted for review. An administrator or reviewer can acknowledge the alert, open an investigation, record findings, add response actions, and resolve it.
8. The workspace displays organization-scoped summary counts, recent observations, candidate alerts, and review history.

Invitation delivery is currently manual: the application returns a one-time token for the administrator to deliver through a separate secure channel. Email delivery is not implemented.

## 3. Technology stack

| Layer | Technology | Role |
|---|---|---|
| Web application | Next.js 15 (App Router) | Browser application and page routing |
| UI | React 19, TypeScript 5.7 | Interactive organization workspace and typed client logic |
| Styling | CSS | Responsive workspace styling |
| API | Python 3.11+, FastAPI | HTTP API, validation, authentication dependencies, workflow endpoints |
| Validation | Pydantic 2 (through FastAPI and settings dependencies) | Request and CSV-row validation |
| ORM | SQLAlchemy 2 | Database models and queries |
| Database | PostgreSQL 15+ | Persistent application, observation, detection, and review data |
| Migrations | Alembic | Versioned schema migrations |
| PostgreSQL driver | psycopg 3 | API database connectivity |
| Password hashing | Python standard-library hashlib.scrypt | Password hash derivation and verification |
| Test tooling | pytest, HTTPX | API and service-level tests |
| CI | GitHub Actions | PostgreSQL-backed backend checks and frontend type/build checks |

The frontend dependencies and scripts are declared in apps/web/package.json. Backend dependencies and supported version ranges are declared in apps/api/requirements.txt.

**No machine-learning model, LLM integration, real-time sensor connector, external epidemiological feed, or mobile-native application is implemented in the current repository.** The anomaly detector is a deterministic statistical service.

## 4. Repository structure

This tree reflects the current repository organization; generated files and empty package-marker files are omitted for readability.

~~~text
PulseGridHealth/
├── .github/
│   └── workflows/
│       └── ci.yml
├── apps/
│   ├── api/
│   │   ├── app/
│   │   │   ├── core/
│   │   │   │   └── config.py
│   │   │   ├── services/
│   │   │   │   ├── detection.py
│   │   │   │   └── ingestion.py
│   │   │   ├── db.py
│   │   │   ├── main.py
│   │   │   ├── models.py
│   │   │   ├── review.py
│   │   │   ├── review_schemas.py
│   │   │   ├── schemas.py
│   │   │   └── security.py
│   │   ├── migrations/
│   │   │   ├── versions/
│   │   │   │   ├── 0001_initial.py
│   │   │   │   ├── 0002_alert_review.py
│   │   │   │   ├── 0003_identity_access.py
│   │   │   │   └── 0004_tenant_isolation.py
│   │   │   ├── env.py
│   │   │   └── script.py.mako
│   │   ├── scripts/
│   │   │   └── verify_rls.py
│   │   ├── tests/
│   │   │   ├── test_api.py
│   │   │   ├── test_auth.py
│   │   │   ├── test_authenticated_workspace.py
│   │   │   ├── test_detection.py
│   │   │   ├── test_evaluation.py
│   │   │   ├── test_ingestion.py
│   │   │   └── test_review.py
│   │   ├── alembic.ini
│   │   └── requirements.txt
│   └── web/
│       ├── app/
│       │   ├── globals.css
│       │   ├── layout.tsx
│       │   └── page.tsx
│       ├── components/
│       │   ├── review-panel.tsx
│       │   ├── upload-form.tsx
│       │   └── workspace.tsx
│       ├── next.config.ts
│       ├── package.json
│       └── tsconfig.json
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DATABASE.md
│   ├── DEPLOYMENT.md
│   ├── EVALUATION.md
│   ├── GITHUB_SETUP.md
│   ├── IMPLEMENTATION_PLAN.md
│   └── SECURITY.md
├── scripts/
│   ├── evaluate_synthetic_detector.py
│   └── generate_synthetic_data.py
├── .env.example
└── README.md
~~~

### Main code areas

- apps/api/app/main.py — FastAPI application, health/readiness endpoints, dashboard and alert reads, CSV import, and detection execution.
- apps/api/app/security.py — bootstrap, login, session handling, CSRF validation, invitations, membership checks, roles, and tenant context.
- apps/api/app/review.py — alert review and investigation endpoints, response actions, and audit-history retrieval.
- apps/api/app/models.py — SQLAlchemy persistence models and database constraints.
- apps/api/app/services/ingestion.py — CSV decoding, column checks, row parsing, and validation.
- apps/api/app/services/detection.py — median/MAD anomaly-screening function.
- apps/web/components/workspace.tsx — authenticated browser workspace and API integration.
- apps/api/migrations/versions/ — schema evolution, including identity/access and tenant-isolation migrations.
- scripts/ — reproducible synthetic-data generation and offline detector evaluation.

## 5. Data model

The SQLAlchemy models and migrations cover these entities:

| Entity | Purpose |
|---|---|
| organizations | Organization / tenant identity |
| users | User accounts and password hashes |
| organization_memberships | User-to-organization membership and role |
| auth_sessions | Hashed session-token records, CSRF hash, expiry, and revocation |
| organization_invitations | Hashed, expiring, single-use invitation tokens and assigned roles |
| communities | Organization-owned community / region groups |
| workforce_groups | Organization-owned workforce groups and cohort-size metadata |
| data_sources | Source identifier and provenance metadata |
| health_observations | Aggregate, date-grained observations |
| detection_results | Detector output and evidence for an observation |
| alerts | Candidate signals and review status |
| investigations | Human investigation state, findings, disposition, and resolution rationale |
| response_actions | Actions recorded against an investigation |
| audit_logs | Organization-scoped review and response events |

Observation constraints enforce one domain target per record, non-negative values, and a positive denominator when supplied. Unique indexes protect against duplicate observations for the same source, group, date, and indicator.

The tenant-isolation migration adds organization ownership to tenant data tables and configures PostgreSQL row-level security (RLS). The application establishes a transaction-local app.organization_id context for tenant-scoped database work. The deployment database role must be a restricted, non-superuser role without BYPASSRLS; PostgreSQL superusers bypass row-level security.

## 6. Detection method

The current detector is a univariate, historical robust-deviation screen.

1. Retrieves preceding observations for the same organization and group/indicator series.
2. Requires a configurable minimum history (default: 6 observations).
3. Calculates the historical median.
4. Calculates the median absolute deviation (MAD).
5. Scales MAD by 1.4826 and computes a robust deviation score.
6. Flags unusually high values at or above the configured threshold (default: 3.5).

The operational API uses a trailing history window capped at 26 prior observations and processes observations chronologically. It does not score an observation using later records. When MAD is zero, the detector does not invent a score: a value equal to the baseline is treated as stable, while a different value receives a non-candidate zero_mad_requires_review reason.

Detection output includes the baseline, score when calculable, reason, threshold, history count, and detector name/version (median_mad). Severity is assigned from the score when a candidate is created.

**Interpretation limits:** This is anomaly screening, not causal analysis, diagnosis, outbreak prediction, or a validated clinical/occupational risk model. A candidate should be investigated in context by an appropriately qualified reviewer.

## 7. CSV import contract

The importer expects UTF-8 CSV with this exact set of columns:

~~~csv
domain,group_code,source_code,observed_date,indicator,value,denominator,unit
community,C001,SYNTHETIC,2026-01-05,weekly_febrile_illness_reports,12,5500,reports
workforce,W001,SYNTHETIC,2026-01-05,weekly_heat_related_symptom_reports,5,250,reports
~~~

- domain: community or workforce.
- group_code: organization-scoped group code.
- source_code: source identifier.
- observed_date: observation date in ISO date format.
- indicator: indicator name.
- value: finite, non-negative numeric value.
- denominator: optional positive integer; blank is permitted.
- unit: measurement unit.

The API checks the upload content type and configured byte limit, validates the CSV header and row values, and returns counts for accepted rows, duplicates, rejected rows, and candidate alerts created. Row-level error details are bounded in the response. Workforce rows are not ingested when the group cohort is unknown or below the configured suppression threshold.

Only aggregate data should be uploaded. Do not put names, email addresses, staff IDs, patient IDs, phone numbers, free-text case notes, or other direct identifiers into CSVs.

## 8. Identity, roles, and permissions

The application implements four organization roles:

| Capability | org_admin | analyst | reviewer | viewer |
|---|:---:|:---:|:---:|:---:|
| View organization dashboard and alerts | Yes | Yes | Yes | Yes |
| Import aggregate CSV observations | Yes | Yes | No | No |
| Run detection | Yes | Yes | No | No |
| Acknowledge alerts | Yes | No | Yes | No |
| Start investigations and record findings | Yes | No | Yes | No |
| Add response actions and resolve alerts | Yes | No | Yes | No |
| Create organization invitations | Yes | No | No | No |

The API enforces permissions server-side; hiding a control in the browser is not the security boundary. Authenticated organization requests must identify an organization for which the user has an active membership. Tenant-owned health and review records are scoped to that organization.

Authentication uses scrypt password hashes and opaque, database-backed session tokens whose hashes are stored server-side. Session cookies are HttpOnly, SameSite=Strict, and marked Secure when APP_ENV=production. Mutating requests use CSRF tokens and origin checks. Repeated failed login attempts trigger an account lockout.

## 9. API surface

| Method | Route | Purpose |
|---|---|---|
| GET | /health | Process liveness |
| GET | /ready | Database readiness check |
| GET | /api/v1/auth/csrf | Issue a CSRF token |
| POST | /api/v1/auth/bootstrap | Create initial organization and administrator |
| POST | /api/v1/auth/login | Sign in and create a session |
| POST | /api/v1/auth/logout | Revoke current session and clear cookies |
| GET | /api/v1/auth/me | Current identity and organization memberships |
| POST | /api/v1/auth/organizations/{organization_id}/invitations | Create an organization invitation |
| POST | /api/v1/auth/invitations/accept | Accept an invitation |
| GET | /api/v1/dashboard | Organization dashboard summary |
| GET | /api/v1/alerts | Organization candidate-alert list |
| POST | /api/v1/observations/import | Import aggregate CSV (file multipart field) |
| POST | /api/v1/detection/run | Evaluate observations without stored detection results |
| POST | /api/v1/alerts/{alert_id}/acknowledge | Acknowledge a candidate alert |
| POST | /api/v1/alerts/{alert_id}/investigation | Start an investigation |
| POST | /api/v1/alerts/{alert_id}/findings | Record investigation findings |
| POST | /api/v1/alerts/{alert_id}/actions | Add a response action |
| POST | /api/v1/alerts/{alert_id}/resolve | Resolve an alert |
| GET | /api/v1/alerts/{alert_id}/history | Retrieve review history |

Authenticated organization data routes require a valid session and organization membership. Mutating requests require the CSRF token in X-CSRF-Token; tenant routes also use the X-Organization-ID header. The bootstrap endpoint additionally requires X-Bootstrap-Token.

## 10. Local development

### Prerequisites

- Python 3.11 or newer.
- Node.js 22 or newer.
- PostgreSQL 15 or newer.
- Git.

Docker is not required by the documented local setup.

### Configure the API

From the repository root, create a local environment file based on .env.example and set a PostgreSQL connection string. Never commit a real .env file or production secret.

~~~bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
~~~

On Windows, activate the virtual environment with .venv\\Scripts\\activate.

### Configure the web application

In a second terminal:

~~~bash
cd apps/web
~~~

Create .env.local with the API base URL:

~~~dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
~~~

Then run:

~~~bash
npm install
npm run dev
~~~

Open the local Next.js development URL printed by the command. The API base URL must be reachable from the browser. For hosted deployments, configure a same-site HTTPS topology consistent with the session cookie policy; see docs/DEPLOYMENT.md.

### Synthetic data

From the repository root:

~~~bash
python scripts/generate_synthetic_data.py --output datasets/synthetic
~~~

The generator writes community_observations.csv, workforce_observations.csv, and ground_truth.csv. The observation files can be uploaded through the workspace. Ground-truth labels are separate and are used only by the offline evaluation script; they are not detector inputs.

### Initial administrator bootstrap

Set a high-entropy BOOTSTRAP_TOKEN in the API environment before calling POST /api/v1/auth/bootstrap. First obtain a CSRF token from GET /api/v1/auth/csrf, then submit the bootstrap request with the CSRF token and X-Bootstrap-Token headers. Bootstrap creates the organization, user, and org_admin membership; sign in separately through the normal login endpoint. The bootstrap token should be rotated or unset after the intended bootstrap operation.

The application does not currently provide a first-run bootstrap wizard or automated invitation email delivery.

## 11. Tests and CI

Backend tests are under apps/api/tests. The GitHub Actions workflow:

- Starts PostgreSQL 15 for the backend job.
- Installs Python dependencies and runs pytest.
- Applies Alembic migrations, runs the PostgreSQL RLS verification script, downgrades to base, and upgrades again.
- Installs frontend dependencies.
- Runs TypeScript type checking with npx tsc --noEmit.
- Runs the Next.js production build with npm run build.

Run backend tests locally from apps/api:

~~~bash
PYTHONPATH=. pytest
~~~

Run frontend checks from apps/web:

~~~bash
npx tsc --noEmit
npm run build
~~~

A successful CI run demonstrates that the automated checks above pass in the CI environment. It does **not** prove that a hosted deployment is live, that browser end-to-end workflows have been exercised against production infrastructure, or that the platform is production-secure.

## 12. Synthetic detector evaluation

The synthetic benchmark replays the detector chronologically and compares predicted group-weeks with separately generated ground-truth labels. It reports true/false positives and negatives, precision, recall, F1, false alerts per group-week, detected anomaly groups, and mean detection delay.

~~~bash
python scripts/generate_synthetic_data.py --output datasets/synthetic --seed 20261104
python scripts/evaluate_synthetic_detector.py --input datasets/synthetic --output evaluation_report.json
~~~

This is a reproducible engineering benchmark, not a field study. Results depend on the seed and parameters. The synthetic scenarios do not model reporting delays, missing periods, changing denominators, correlated reporting practices, or real-world confounders. See docs/EVALUATION.md.

## 13. Security and production-readiness status

Implemented foundations include:

- Password hashing and database-backed sessions.
- HttpOnly session cookies and CSRF/origin checks.
- Role-based authorization enforced by API dependencies.
- Organization membership checks and tenant-scoped data access.
- PostgreSQL RLS policies with FORCE RLS on tenant-owned health and review tables.
- Upload size/content checks and strict CSV schema validation.
- Duplicate-observation constraints.
- Audit events for alert review and response workflow operations.
- Workforce cohort-size suppression.

The deployment guide identifies controls that remain necessary before real health data or operational production use:

- Gateway/IP-aware rate limiting for authentication, bootstrap, invitation acceptance, and uploads.
- Account recovery, account deactivation, and session-revocation management.
- Secure invitation delivery.
- Encrypted backups and tested restoration.
- Retention and deletion policies.
- Operational monitoring, alerting, and incident response.
- Secret rotation and production cookie/CORS configuration.
- Independent security/privacy review and applicable legal/regulatory assessment.
- Domain-expert validation of workforce cohort suppression and aggregation rules.
- Live deployment and browser-level end-to-end verification.

Use a restricted PostgreSQL application role that is neither a superuser nor granted BYPASSRLS. Keep the database private and configure HTTPS, exact CORS origins, and same-site frontend/API deployment. Do not treat passing CI as a production security certification.

For the detailed release checklist, see docs/DEPLOYMENT.md. For the security baseline, see docs/SECURITY.md.

## 14. Current scope and known exclusions

The current repository does not implement:

- Native Android or iOS applications.
- Live sensor, wearable, laboratory, hospital, or government data integrations.
- Automated scheduled ingestion or streaming pipelines.
- Machine-learning training, LLM-based interpretation, or a conversational assistant.
- Clinical diagnosis, individual risk scoring, outbreak declaration, or automated response decisions.
- Automated email/SMS invitation delivery.
- Full account recovery or account/session administration workflows.
- Production compliance certification or independent penetration-test evidence.

These are exclusions of the current codebase, not implied roadmap commitments.

## 15. Project documentation

- Repository: https://github.com/ReignnRule11/PulseGridHealth
- Architecture: docs/ARCHITECTURE.md
- Database notes: docs/DATABASE.md
- Security baseline: docs/SECURITY.md
- Deployment runbook: docs/DEPLOYMENT.md
- Synthetic evaluation: docs/EVALUATION.md
- Implementation plan: docs/IMPLEMENTATION_PLAN.md

---

**PulseGrid Health — aggregate signals, explainable statistical screening, and accountable human review.**

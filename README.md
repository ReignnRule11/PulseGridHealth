# PulseGrid Health


[![Phase 1 CI](https://github.com/ReignnRule11/PulseGridHealth/actions/workflows/ci.yml/badge.svg)](https://github.com/ReignnRule11/PulseGridHealth/actions/workflows/ci.yml)


Population & Workforce Health Intelligence Platform.

PulseGrid Health is an explainable early-warning prototype for aggregate community and workforce health signals. The Phase 1 MVP connects CSV ingestion, PostgreSQL persistence, robust statistical screening, evidence-backed candidate alerts, and a live dashboard.

> **Demonstration boundary:** use synthetic or explicitly authorised aggregate data only. Do not upload patient- or employee-identifiable records. Statistical candidates are not diagnoses, outbreak declarations, or autonomous response decisions. Human review is mandatory.

## MVP capabilities

- Community aggregate weekly health observations.
- Workforce-group aggregate symptom and environmental observations.
- Strict CSV validation, bounded uploads, row-level errors, and duplicate protection.
- PostgreSQL persistence through SQLAlchemy and Alembic.
- Historical median/MAD anomaly screening with minimum history and zero-MAD safeguards.
- Stored detection evidence and pending-review candidate alerts.
- Dashboard summary, recent observations, and alert evidence.
- Workforce group suppression below the configured minimum cohort size.

## Repository layout

- `apps/api`: FastAPI, SQLAlchemy, Alembic, and tests.
- `apps/web`: Next.js dashboard and CSV import interface.
- `scripts`: deterministic synthetic data generation.
- `docs`: architecture, security, evaluation, and implementation notes.

## Run locally

Requirements: Python 3.11+, Node.js 22+, and PostgreSQL 15+. Docker is not required.

1. Create a PostgreSQL database and set `DATABASE_URL` from `.env.example`. Never commit the real value.
2. Backend:
   ```bash
   cd apps/api
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   alembic upgrade head
   uvicorn app.main:app --reload
   ```
3. Generate the repeatable demo data from the repository root:
   ```bash
   python scripts/generate_synthetic_data.py --output datasets/synthetic
   ```
4. Frontend in a second terminal:
   ```bash
   cd apps/web
   echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local
   npm install
   npm run dev
   ```
5. Open the Next.js app and import both generated CSV files.

## CSV contract

Exact columns: `domain,group_code,source_code,observed_date,indicator,value,denominator,unit`.

Domains are `community` or `workforce`. Values must be finite and non-negative; denominator, when supplied, must be positive. Workforce group data is suppressed when the known cohort size is below `MIN_WORKFORCE_COHORT_SIZE` (default 20).

## API

- `GET /health`
- `GET /api/v1/dashboard`
- `GET /api/v1/alerts?status=pending_review`
- `POST /api/v1/observations/import` (multipart field `file`)
- `POST /api/v1/detection/run`

## Security boundary

This is a local/synthetic demonstration MVP, not a production health-data service. In `APP_ENV=production`, data and dashboard endpoints fail closed until authentication, server-side RBAC, tenant isolation/RLS, audit controls, retention policies, and a security review are implemented. Keep hosted demo data synthetic. Configure CORS to the exact frontend origin.

## Detection and evaluation

The detector uses the prior observations for the same group and indicator, a trailing history window, median baseline, and MAD-scaled robust score. It never uses future observations. Minimum history defaults to six points; zero MAD is handled without inventing a score. Evaluate chronologically and report precision, recall, F1, false alerts per group-week, and detection delay separately for community and workforce domains.

## Tests

```bash
cd apps/api
PYTHONPATH=. pytest
```

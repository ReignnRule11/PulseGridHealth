# PulseGrid Health

Population & Workforce Health Intelligence Platform.

Phase 1 foundation: Next.js + FastAPI + PostgreSQL, synthetic aggregate datasets,
validated ingestion, and statistical anomaly detection.

> This is a development scaffold, not a clinically validated or production-ready
> medical system. Use synthetic or appropriately authorised aggregate data only.
> An anomaly is a statistical signal, not a diagnosis or outbreak declaration.

## MVP scope

- Community aggregate health observations.
- Workforce-group aggregate health observations.
- Environmental indicators associated with workforce groups.
- CSV ingestion with strict schema validation.
- Rolling baseline and robust z-score detection.
- Human-reviewed alerts (planned for subsequent Phase 1 increment).

## Repository layout

```text
apps/
  api/                 FastAPI backend
  web/                 Next.js frontend
database/
  migrations/          Alembic migrations
datasets/
  synthetic/           Generated demo CSVs
docs/                  Product and engineering docs
scripts/               Dataset generation utilities
.github/workflows/     CI
```

## Prerequisites

- Node.js 22+
- Python 3.11+
- PostgreSQL 15+ (hosted PostgreSQL is acceptable)
- Git and GitHub account

Docker is not required. For a phone-first workflow, create the repository on GitHub,
edit files in GitHub's web editor or Codespaces if available, and use a hosted
PostgreSQL provider. Never commit database credentials.

## Local setup

### 1. Clone and configure

```bash
git clone https://github.com/<YOUR_GITHUB_USERNAME>/PulseGrid-Health.git
cd PulseGrid-Health
cp .env.example .env
```

Set `DATABASE_URL` to a PostgreSQL connection string. Use a dedicated development
database and a separate test database.

### 2. Backend

```bash
cd apps/api
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux/Termux: source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

API health check: `GET http://127.0.0.1:8000/health`

### 3. Generate synthetic data

From repository root:

```bash
python scripts/generate_synthetic_data.py --output datasets/synthetic
```

The generator creates:
- `community_observations.csv`
- `workforce_observations.csv`

All records are synthetic and include deliberately planted anomalies for
reproducible evaluation.

### 4. Frontend

```bash
cd apps/web
npm install
npm run dev
```

Open `http://localhost:3000`.

### 5. Run tests

```bash
cd apps/api
pytest
```

## API endpoints in this scaffold

- `GET /health`
- `POST /api/v1/observations/import` — CSV upload
- `POST /api/v1/detection/run` — run baseline detector on stored observations
- `GET /api/v1/observations` — list aggregate observations
- `GET /api/v1/alerts` — list candidate alerts

Authentication and organisation-scoped authorisation are required before any
non-synthetic or multi-tenant deployment. The initial scaffold intentionally
keeps the demo boundary explicit; do not expose it publicly with real data.

## Security rules

- Never commit `.env`, API keys, database URLs, tokens, or private datasets.
- Use aggregate observations; do not upload patient or employee identifiable data.
- Enforce tenant-scoped access in the API and database before production.
- Apply minimum cohort-size suppression to workforce and sensitive geographic views.
- Keep source provenance, model version, detection evidence, and audit history.
- Validate CSV size, columns, dates, units, non-negative values, and mutually
  exclusive community/workforce identifiers.
- AI explanations must be grounded only in stored detection evidence.
- Human reviewers own all investigation and response decisions.

## Detection methodology

The initial detector uses a trailing historical window and a robust median/MAD
baseline. It is intended for prototype anomaly screening, not epidemiological
forecasting. Minimum history and denominator checks are enforced. Results must
be evaluated chronologically and separately by domain.

## Before public deployment

This scaffold is not yet production ready. Complete:
1. Authentication, secure sessions, RBAC, and tenant isolation.
2. PostgreSQL row-level security or equivalent server-enforced tenant controls.
3. Audit logging for privileged actions.
4. Rate limits, upload limits, malware scanning where applicable.
5. Data retention, deletion, consent, and incident-response policies.
6. Independent security review and clinical/public-health review.
7. Monitoring, backups, restore tests, and migration rollback strategy.
8. Formal validation on representative, authorised data.

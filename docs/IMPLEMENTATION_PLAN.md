# Phase 1 Implementation Plan

## Product boundary

PulseGrid Health supports aggregate population and workforce health intelligence.
The first demonstration contains two data domains:
- Community: aggregate weekly acute-febrile-illness report counts.
- Workforce: aggregate weekly heat-related symptom reports plus environmental
  heat-exposure readings.

No individual-level patient or employee records are in scope.

## Milestones

### M0 — Repository and controls
- Create private GitHub repository `PulseGrid-Health`.
- Add README, `.gitignore`, `.env.example`, CI, and branch protection.
- Do not add secrets or real health data.

### M1 — Backend and database
- FastAPI application with configuration from environment.
- PostgreSQL connection and Alembic migrations.
- Tables for organizations, communities, workforce groups, data sources,
  aggregate observations, detection results, alerts, investigations, response
  actions, data-quality issues, and audit logs.
- Add constraints and indexes; add tenant scoping before multi-user exposure.

### M2 — Synthetic data and ingestion
- Deterministic synthetic data generator with fixed seed.
- Separate community and workforce CSVs.
- CSV schema validation, row-level rejection reasons, upload size limit,
  source provenance, duplicate detection, and transactional persistence.

### M3 — Detection
- Rolling median and median absolute deviation (MAD).
- Minimum history requirement.
- Guardrails for zero MAD, missing observations, low denominator, and incomplete
  reporting.
- Store model name/version, baseline, score, threshold, and evidence window.
- Generate candidate alerts only; never label an alert as a diagnosis.

### M4 — Evaluation
- Chronological evaluation with known planted anomaly windows.
- Precision, recall, F1, false alerts per group-week, and detection delay.
- Report results separately for community and workforce.
- Include missingness and baseline contamination tests.

### M5 — Web application
- Dashboard summary, community view, workforce view, ingestion status,
  candidate alert list, and alert evidence detail.
- Use accessible labels and clear "synthetic demo data" markers.
- Human review workflow in the next increment.

## Definition of done

- Clean install from README.
- Migrations apply to an empty PostgreSQL database.
- Synthetic generator produces repeatable data.
- Valid CSV imports; malformed CSV is rejected safely.
- Duplicate imports do not duplicate observations.
- Detection is deterministic for fixed input.
- Tests cover normal, planted anomaly, missing data, and insufficient history.
- CI passes on pull request.
- No credentials or personal health information in repository history.

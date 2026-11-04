# Architecture

## Runtime components

- `apps/web`: Next.js App Router UI.
- `apps/api`: FastAPI API, ingestion service, analytics service.
- PostgreSQL: durable aggregate observations and detection evidence.
- `datasets/synthetic`: generated demo inputs only.

## Request/data flow

1. CSV upload arrives at FastAPI.
2. Upload-size and file-type checks run before parsing.
3. Pydantic validation checks every row.
4. Domain and source provenance are validated.
5. Rows are inserted transactionally with duplicate protection.
6. Detector loads a time-ordered series by domain/group/indicator.
7. Detector computes a trailing median and MAD-based score.
8. Detection result and evidence are persisted.
9. Web UI reads summaries and candidate alerts.

## Domain separation

An observation must belong to exactly one:
- a community, or
- a workforce group.

The database check constraint enforces this. Workforce exposure indicators
(e.g. heat index) and workforce health indicators remain distinct indicators
within the workforce domain.

## Trust boundaries

- Browser is untrusted.
- API validates all input.
- Database credentials exist only on the server.
- AI explanation service, if added, receives only structured aggregate evidence.
- No autonomous clinical or occupational decisions.

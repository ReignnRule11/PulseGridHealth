# Operations runbook

This is a controlled-pilot starting point, not evidence that a production environment or recovery process exists. Rehearse in non-production first. Do not use real patient or employee records in the current MVP.

## 1. Release and rollback

1. Select a reviewed immutable Git commit and record its SHA.
2. Confirm CI passed for that exact SHA.
3. Confirm the Neon backup/restore controls and restore point meet the approved RPO.
4. Run Alembic migrations once with the dedicated migration-owner connection.
5. Deploy the API and frontend behind the intended HTTPS origin arrangement.
6. Verify /health, /ready, login, role restrictions, CSV import, alert review and logout using synthetic aggregate data.
7. Stop rollout if smoke tests fail. Revert the application to the previous immutable commit. Do not automatically downgrade the database; use a reviewed forward fix unless a rollback migration exists.
8. Record operator, commit, timestamps, smoke results and incident/ticket reference.

## 2. Edge proxy and rate limiting

The deploy/nginx/nginx.conf file is a template for a single HTTPS origin. It is not active merely because it exists in the repository. Before use:

- Replace the example hostname and certificate paths; configure DNS, valid TLS and automated renewal.
- Ensure only the edge proxy is public. Keep database access restricted.
- Configure upstream DNS names to match private service names.
- Create /etc/nginx/snippets/pulsegrid-proxy-headers.conf with these directives:

    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Request-ID $request_id;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_connect_timeout 5s;
    proxy_send_timeout 30s;
    proxy_read_timeout 30s;

- Run nginx -t before reload.
- Supplied rate limits are conservative starting values, not load-tested capacity guarantees.
- If Nginx is behind a load balancer/CDN, configure real-client-IP handling only for that provider's trusted IP ranges. Never trust arbitrary client-supplied X-Forwarded-For.
- Review 429 counts. Nginx access logs intentionally omit query strings. The Render API command disables Uvicorn access logs; verify provider logs separately.

The template keys limits by $remote_addr. If behind another proxy, trusted client-IP handling is a prerequisite or limits may apply to the load balancer.

## 3. PostgreSQL controls

- Use a dedicated runtime role with NOSUPERUSER, NOBYPASSRLS, NOCREATEROLE, NOCREATEDB and NOREPLICATION; never use the migration owner or a superuser at runtime.
- The runtime role must not own tenant tables, inherit the migration-owner role, create objects in the application schema or create schemas in the database.
- Keep `DATABASE_URL` (runtime, pooled Neon endpoint) separate from `MIGRATION_DATABASE_URL` (direct migration-owner endpoint).
- Run `python scripts/verify_rls.py` with the migration/test owner to exercise tenant isolation, then run `python scripts/verify_runtime_role.py` with the exact API `DATABASE_URL`. The runtime check must pass for all nine forced-RLS tenant tables.
- Store credentials in a secret manager and rotate under a documented change procedure.
- Require database TLS.

## 4. Encrypted backup and restore rehearsal

Choose and document backup provider, encryption-key owner, retention, access policy, RPO and RTO before pilot. Neon managed backup/restore capabilities and retention depend on the selected plan; verify the actual plan and perform an isolated restore rehearsal. An encrypted logical export to private object storage is an alternative, using a dedicated least-privilege backup identity.

A successful backup job is not a successful restore rehearsal. Record backup timestamp, schema revision, checksum, restore start/end times, smoke-test results, actual RTO/RPO and operator sign-off. Destroy isolated restore environments and temporary plaintext material securely.

## 5. Monitoring and incident response

Minimum pilot signals:
- API /health and /ready availability and latency.
- HTTP 5xx, 429 events, authentication failures/lockouts and upload rejections.
- Database connections, storage, CPU, compute availability, backup health and migration failures.
- Process restarts and deployment health.

Operational logs must not contain passwords, session/CSRF/invitation/bootstrap tokens, cookies, authorization headers, CSV contents, individual observations or free-text clinical/workforce notes. Keep security/audit records access-controlled and separate from general request logs. Define alert owners and escalation before pilot.

Incident checklist:
1. Triage severity, affected service, tenant scope and confidentiality/integrity/availability impact.
2. Contain: disable affected access, revoke exposed credentials/sessions, isolate services and preserve restricted audit evidence.
3. Notify security/privacy owner and follow applicable contractual/legal notification obligations.
4. Recover from known-good release/backup only after integrity checks.
5. Document timeline, impact, root cause, decisions, notifications and corrective actions.
6. Review incident and update controls/runbooks.

## 6. Data authority and privacy gate

Before loading any non-synthetic dataset, obtain written approval from the data controller/owner and document:
- Precise purpose, lawful authority/basis, permitted fields, aggregation method and provenance.
- Evidence that no direct identifiers or free-text records are present.
- Minimum group/cohort thresholds, suppression rules, re-identification risk review and small-cell handling.
- Data-sharing agreement, retention/deletion schedule, access roles and breach/incident contacts.
- Domain-owner validation of indicators and thresholds for the intended operational context.
- Independent privacy/security review and applicable legal/regulatory assessment.

For workforce data, cohort size must be known and meet the reviewed suppression threshold. Unknown or below-threshold cohorts fail closed. Do not ingest individual employee health records or use this system for individual employment decisions.

## 7. Pilot evidence register

| Evidence | Required proof | Status |
|---|---|---|
| Deployment | HTTPS URL, deployed commit SHA, provider and region | Not supplied |
| Browser workflow | E2E run for bootstrap, login, invite, import, review, role denial, tenant isolation, logout | CI passed on merged main commit; hosted staging smoke test pending |
| RLS | PostgreSQL verification using restricted NOBYPASSRLS role | CI runtime-role check added; hosted environment pending |
| Rate limiting | Deployed proxy config and observed 429 test | Template added; deployment pending |
| Logging | Redaction review and sample log inspection | Uvicorn access logs disabled in Blueprint; provider log review pending |
| Backup | Encrypted backup and successful isolated restore record | Not run |
| Security/privacy | Independent review with no unresolved critical findings | Not completed |
| Data authority | Signed pilot data authority and privacy gate | Not supplied |

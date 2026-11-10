# Operations runbook

This is a controlled-pilot starting point, not evidence that a production environment or recovery process exists. Rehearse in non-production first. Do not use real patient or employee records in the current MVP.

## 1. Release and rollback

1. Select a reviewed immutable Git commit and record its SHA.
2. Confirm CI passed for that exact SHA.
3. Build frontend and API images from that SHA; tag with the full Git SHA.
4. Confirm the database backup completed and the restore point meets the approved RPO.
5. Run Alembic migrations once as a release job, not from every application worker.
6. Deploy API and web privately behind the TLS edge proxy.
7. Verify /health, /ready, login, role restrictions, CSV import, alert review and logout using synthetic aggregate data.
8. Stop rollout if smoke tests fail. Revert application images to the previous immutable tag. Do not automatically downgrade the database; use a reviewed forward fix unless a rollback migration exists.
9. Record operator, commit, timestamps, smoke results and incident/ticket reference.

## 2. Edge proxy and rate limiting

The deploy/nginx/nginx.conf file is a template for a single HTTPS origin. Before use:

- Replace the example hostname and certificate paths; configure DNS, valid TLS and automated renewal.
- Ensure only Nginx is public. Bind API, web and PostgreSQL ports to private networking.
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
- Review 429 counts. Nginx access logs intentionally omit query strings. The Render API command disables Uvicorn access logs because default request-target logging is not an approved redaction policy. Verify provider logs separately; they must not include cookies, tokens, request bodies or health observations.

The template keys limits by $remote_addr. If behind another proxy, trusted client-IP handling is a prerequisite or limits may apply to the load balancer.

## 3. PostgreSQL controls

- Use a dedicated runtime role with NOSUPERUSER and NOBYPASSRLS; never use the migration owner or a superuser at runtime.
- Keep PostgreSQL private and restrict connections to API, backup and approved administration paths.
- Run `python scripts/verify_rls.py` with the migration/test owner to exercise tenant isolation, then run `python scripts/verify_runtime_role.py` with the exact API `DATABASE_URL`. The runtime check must pass for the actual non-superuser, non-BYPASSRLS role and all nine forced-RLS tenant tables.
- Store credentials in a secret manager and rotate under a documented change procedure.
- Require database TLS when not on a trusted private network.

## 4. Encrypted backup and restore rehearsal

Choose and document backup provider, encryption-key owner, retention, access policy, RPO and RTO before pilot. Example below uses PostgreSQL custom-format dumps encrypted with age; a managed backup service is acceptable if it provides equivalent encryption and restore evidence.

Create a backup with a dedicated least-privilege backup identity:

    pg_dump --format=custom --no-owner --no-acl "$BACKUP_DATABASE_URL" | age -r "$BACKUP_AGE_RECIPIENT" > "pulsegrid-$(date -u +%Y%m%dT%H%M%SZ).dump.age"

Store the encrypted artifact in private object storage with versioning and retention controls. Keep the decryption identity separate from the application runtime and restrict it to designated recovery operators. Never place decrypted dumps in shared folders.

Restore rehearsal into an isolated, empty recovery database:

    age -d -i "$BACKUP_AGE_IDENTITY_FILE" backup.dump.age | pg_restore --no-owner --no-acl --dbname="$RESTORE_DATABASE_URL"

Then:

1. Record backup timestamp, source commit/schema revision, checksum and restore start/end times.
2. Verify expected tables, Alembic revision, organisation counts and synthetic fixture counts.
3. Run readiness, authentication, tenant-isolation and RLS smoke tests against the restored database.
4. Confirm no production credentials or real health records were copied into test.
5. Compare actual recovery time and backup age against proposed RTO/RPO.
6. Destroy isolated restore environment and temporary plaintext material securely.
7. Remediate and repeat any failed check.

A green backup job is not a successful restore rehearsal. Attach the actual run record and operator sign-off before marking E1 backup acceptance complete.

## 5. Monitoring and incident response

Minimum pilot signals:
- API /health and /ready availability and latency.
- HTTP 5xx, 429 events, authentication failures/lockouts and upload rejections.
- Database connections, storage, CPU, replication/backup health and migration failures.
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
| Browser workflow | E2E run for bootstrap, login, invite, import, review, role denial, tenant isolation, logout | Not run |
| RLS | PostgreSQL verification using restricted NOBYPASSRLS role | CI runtime-role check added; hosted environment pending |
| Rate limiting | Deployed proxy config and observed 429 test | Template added; deployment pending |
| Logging | Redaction review and sample log inspection | Uvicorn access logs disabled in Blueprint; provider log review pending |
| Backup | Encrypted backup and successful isolated restore record | Not run |
| Security/privacy | Independent review with no unresolved critical findings | Not completed |
| Data authority | Signed pilot data authority and privacy gate | Not supplied |

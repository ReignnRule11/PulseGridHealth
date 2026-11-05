# PulseGrid Health — Implementation Plan & GitHub Backlog

**Version:** 1.0  
**PRD:** [docs/PRD.md](./PRD.md)  
**Planning baseline:** main at fb7211df78ae14f7ebf1b499a3cc49d01da34ea0  
**Status:** Proposed delivery plan. This document does not imply that proposed work is implemented.

## 1. Delivery strategy

Sequence work around the product's critical path:

1. Pilot deployment, security and operations.
2. Import batches and data quality.
3. Complete human review and disposition.
4. Customer access administration.
5. Commercial plans, entitlements and billing.
6. Safe reports and notifications.
7. One customer-backed integration.
8. Paid pilot and commercial validation.

Engineering and customer discovery run in parallel. Operational health data must not be used until the pilot safety gate passes.

## 2. Epic map

| Epic | Priority | Dependencies | Exit outcome |
|---|---|---|---|
| E1 — Pilot deployment, security and operations | P0 | Existing Phase 2 baseline | Controlled, monitored pilot deployment |
| E2 — Import batches and data quality | P0 | E1; current ingestion | Explainable, repeatable onboarding |
| E3 — Review workflow completeness | P0 | Existing alerts/review; E1 | Traceable human disposition |
| E4 — Customer access administration | P1 | Existing auth/RBAC; E1 | Customer-managed access lifecycle |
| E5 — Commercial foundation and billing | P1 | E4; pricing discovery | Server-enforced entitlements and reconciled billing |
| E6 — Reports and notifications | P1 | E2, E3, E4 | Safe customer outputs |
| E7 — First customer-backed integration | P2 | E1, E2; data agreement | Monitored, revocable connector |
| E8 — Paid pilot and commercial validation | P0 business track | E1–E3 minimum; buyer/data authority | Evidence of value, price and delivery economics |

P0 is required for an operational pilot. P1 is for repeatable commercial v1; it need not block a narrowly scoped paid pilot if contract and controls permit. P2 requires customer evidence.

## 3. Epic specifications

### E1 — Pilot deployment, security and operations
**Goal:** prove the existing application can run safely in a controlled pilot environment.

- Select and document frontend/API hosting topology, HTTPS, exact CORS and cookie settings.
- Provision PostgreSQL with a restricted non-superuser role without BYPASSRLS.
- Configure production secrets, bootstrap-token rotation/disablement and rate limiting.
- Add redacted error/operational monitoring and uptime/readiness checks.
- Configure encrypted backups and complete a restore rehearsal.
- Add browser E2E coverage: bootstrap, sign-in, invitations, import, review, role restrictions, tenant boundary and logout.
- Complete independent security/privacy review; document incident response, release, rollback and retention.

**Acceptance:** deployed browser smoke tests pass; RLS is verified using the production-equivalent DB role; restore rehearsal is evidenced; no unresolved critical security issue. No real health data before this gate.

### E2 — Import batches and data quality
**Goal:** make every upload understandable, auditable and safely repeatable.

- Persist import batch tenant, submitter, received time, source, file digest, status and aggregate row counts.
- Add import history/detail API and workspace views.
- Provide CSV template and data dictionary.
- Preserve bounded row rejection/suppression reasons without retaining unnecessary raw content.
- Show source freshness and missing periods; missing must never become zero.
- Define deterministic duplicate and idempotent retry behaviour.
- Test encoding, size, dates, domains, denominator shifts, duplicate file, partial failures and cohort suppression.
- Define retention for upload artefacts and digests.

**Acceptance:** analyst can see accepted, duplicate, suppressed and rejected counts/reasons; correct an import and retry without duplicate observations or alerts.

### E3 — Review workflow completeness
**Goal:** connect candidate evidence to an accountable human disposition.

- Add reviewer assignment/reassignment with audit events.
- Add structured dispositions validated with pilot reviewers.
- Require rationale for final disposition/resolution.
- Separate detector evidence from human notes and actions.
- Add assignment state, review timestamps, filters and history.
- Add idempotency/concurrency protections for transitions.
- Test audit integrity and reviewer/analyst/viewer permission boundaries.

**Acceptance:** every candidate is traceable from source observation and detector version to reviewer, investigation, rationale, actions and final disposition. No automated clinical or operational decision.

### E4 — Customer access administration
**Goal:** remove routine dependence on database-level user administration.

- Member listing and role changes.
- Member deactivation and session revocation.
- Secure account recovery/password reset.
- Select and integrate secure invitation email delivery.
- Audit membership/access changes.
- Define time-bounded, customer-visible support access if required.
- Test revoked/deactivated users and stale sessions.

**Acceptance:** administrator can safely manage member lifecycle; recovery and revocation work end-to-end.

### E5 — Commercial foundation and billing
**Goal:** enforce subscription entitlements and reconcile payments safely.

- Validate willingness to pay and package structure before publishing prices.
- Define plans, entitlements, subscriptions, usage ledger, invoices and payment events.
- Enforce entitlements in backend routes/actions, never only in UI.
- Model pilot/trial, active, past-due, grace, cancelled, expired and suspended states.
- Compare Nigerian payment providers for NGN/FX, settlement, recurring billing, fees, refunds, invoices and webhooks.
- Verify webhook signatures; handle replay and out-of-order events idempotently.
- Support invoice/bank-transfer contracts with controlled manual reconciliation.
- Add customer billing/usage and internal reconciliation views.
- Define grace, downgrade and cancellation behaviour; never delete data on downgrade.
- Review contracts, tax, refund and cancellation terms with qualified advisers.

**Acceptance:** lifecycle tests pass; API entitlements cannot be bypassed; payment records reconcile; downgrade/cancel does not destroy data; privacy/security protections are identical on every tier.

### E6 — Reports and notifications
**Goal:** provide safe, useful outputs.

- Tenant-scoped aggregate exports with cohort suppression.
- Include generation time, date range, filters, source and detector methodology/version.
- Audit export requests/downloads.
- Add notification preferences, delivery records and bounded retries.
- Do not put sensitive evidence in email or public URLs.
- Make failures visible and allow notifications to be disabled.
- Never phrase a candidate as a confirmed diagnosis/outbreak.

**Acceptance:** export and notification permission tests pass; suppressed groups remain protected; delivery failures are observable.

### E7 — First customer-backed integration
**Goal:** prove one repeatable connector, not speculative integrations.

- Select source only after design-partner confirmation of authority, schema and cadence.
- Agree data-processing/security requirements.
- Store credentials securely with rotation/revocation.
- Implement tenant-bound sync, idempotency, validation and provenance.
- Track last success, counts, errors and retries; support pause/resume.

**Acceptance:** tenant isolation, replay, failure, revocation and data-quality tests pass in a customer-approved environment.

### E8 — Paid pilot and commercial validation
**Goal:** validate buyer, workflow, price and delivery model.

- Interview buyers across employers, occupational-health providers and NGO/programmes.
- Select beachhead using urgency, budget ownership, data authority and procurement speed.
- Recruit design partner with named analyst/reviewer and authorised aggregate data.
- Agree baseline workflow and success measures before onboarding.
- Propose a fixed-scope 8–12 week paid pilot; negotiate price rather than treating draft pricing as established.
- Measure onboarding hours, import quality, reviewer activation, time-to-review, usefulness, false-alert feedback, support effort and direct costs.
- Conduct formal outcome review and annual-conversion decision; document non-purchase reasons.

**Acceptance:** complete at least one paid pilot with buyer feedback, workflow measures, delivery cost and convert/iterate/stop decision. Do not claim clinical outcome improvement from the pilot.

## 4. Initial execution sequence

| Increment | Focus | Deliverables |
|---|---|---|
| Sprint 0 | Readiness and evidence | Deploy environment, production smoke tests, security/restore gate, discovery interviews |
| Sprint 1 | Import operability | Import batch schema/API, template, history, row outcomes, retry tests |
| Sprint 2 | Review completion | Assignment, structured disposition, rationale, queue/history and audit tests |
| Sprint 3 | Customer operations | Member admin, deactivation, revocation, recovery, invitation delivery |
| Sprint 4 | Commercial foundation | Entitlements, subscription/usage models, provider decision, billing lifecycle tests |

Sprint duration is intentionally unspecified. Commit to dates only after capacity and external dependencies are known.

## 5. Definition of Ready

An issue is ready when:
- Persona/problem, scope and exclusions are stated.
- API, data and UI impact are identified.
- Tenant, role, CSRF, privacy and audit implications are specified.
- Acceptance criteria are testable.
- Migration, backfill and rollback are described.
- Dependencies/provider decisions are resolved.
- Synthetic fixtures are available; no real health data in tests.

## 6. Definition of Done

- Acceptance criteria and relevant backend/frontend checks pass.
- Tenant and role negative tests are included.
- Privacy/cohort suppression and audit behaviour are tested where relevant.
- Migration upgrade/downgrade is verified.
- Errors are safe; secrets and sensitive row contents are not logged.
- Documentation/runbooks are updated.
- No unsupported clinical, product or compliance claims are introduced.
- CI, deployment and pilot validation are reported as separate states.

## 7. Delivery controls

- Use feature branches and pull requests; do not force-push main.
- Keep changes small and vertically testable.
- Preserve the modular monolith unless measured evidence justifies change.
- Do not add Redis, Kubernetes, microservices or AI/LLM features as speculative prerequisites.
- Never gate privacy/security controls behind a paid plan.
- Never charge per alert or individual health record.
- Reject identifiable patient/employee records.
- Use synthetic data until governance and deployment gates pass.
- Distinguish implemented, CI verified, deployed and pilot validated.

## 8. GitHub execution source

The linked E1–E8 issues are the work-tracking source of truth. Update this plan when dependencies, scope or acceptance gates change.

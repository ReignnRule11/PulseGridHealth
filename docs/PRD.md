# PulseGrid Health — Product Requirements Document

**Version:** 1.0 | **Date:** 5 November 2026 | **Status:** Proposed product and implementation baseline  
**Repository:** https://github.com/ReignnRule11/PulseGridHealth  
**Category:** Population and workforce health early-warning intelligence  
**Initial market hypothesis:** Nigeria, followed by selected international markets after validation.

> This PRD describes the current engineering baseline, the requirements for a pilot-operable product, and a proposed commercial roadmap. Pricing is a set of hypotheses to test, not verified market rates. It does not claim that proposed features have already been implemented.

---

## 1. Executive summary

PulseGrid Health is an organisation-scoped early-warning intelligence platform for population and workforce health. It helps authorised organisations collect aggregate observations, identify unusual changes against historical patterns, inspect the evidence behind candidate signals, and coordinate documented human review.

The product is an early-warning and review-support layer. It is not an electronic medical record, diagnostic system, outbreak declaration service, clinical prediction model, or autonomous occupational-health decision-maker.

**Product thesis:** organisations need more than another dashboard. They need a dependable workflow between aggregate data collection and a human decision: validate the data, compare observations with an appropriate historical baseline, expose the evidence, assign review, document findings and preserve the response history.

**Commercial thesis:** sell recurring organisation-level software contracts, supported by paid onboarding, data mapping, integrations, training and premium support. Price by monitored coverage and service level—not by alert volume or individual health records.

### Current repository baseline

The current repository implements:
- Next.js 15, React 19 and TypeScript browser workspace.
- FastAPI backend and PostgreSQL persistence.
- Organisation memberships, four roles, invitations and database-backed sessions.
- Tenant-scoped access and PostgreSQL row-level security.
- Aggregate CSV ingestion and validation.
- Median/MAD statistical anomaly screening.
- Evidence-backed candidate alerts.
- Human acknowledgement, investigation, findings, response actions, resolution and history.
- Synthetic data generation and chronological detector evaluation.
- CI checks for backend tests, migrations/RLS, frontend type checking and production build.

Not implemented today: subscription billing, plan entitlements, payment collection, automated customer onboarding, email delivery, scheduled ingestion, external data connectors, notifications, production compliance certification, live sensors, ML or LLM interpretation. These are future requirements, not existing features.

## 2. Problem and opportunity

### User problem
Aggregate health and environmental observations can be fragmented across spreadsheets, periodic reports and different reporting systems. Teams may manually compare periods and coordinate follow-up through email or messaging. This can lead to:
- Late or inconsistent recognition of unusual changes.
- Inconsistent baselines and undocumented assumptions.
- Alerts without clear evidence or provenance.
- Unclear ownership of follow-up.
- Investigation findings and response actions scattered across tools.
- Limited ability to reconstruct why a signal was reviewed, dismissed or escalated.

### Organisational job
PulseGrid should help an organisation:
1. Import authorised aggregate observations.
2. Validate completeness, format and provenance.
3. Screen eligible observations against historical patterns.
4. Understand why a candidate signal was raised.
5. Assign qualified people to review it.
6. Record findings, actions and disposition.
7. Review performance and maintain an audit trail.

### Boundaries
PulseGrid must not diagnose individuals, predict individual illness, declare outbreaks, infer sensitive employee health status, establish causality from anomalies, replace statutory surveillance or guarantee prevention or health outcomes. A statistical deviation is a candidate for human review—not a confirmed event.

## 3. Vision, positioning and principles

**Vision:** organisations can identify and investigate meaningful population and workforce health changes earlier, with transparent evidence and responsible data practices.

**Positioning:** for public-health programmes, employers and occupational-health providers that need to monitor aggregate health indicators, PulseGrid is an early-warning and review-support platform that screens observations against historical patterns and coordinates accountable human review.

**Product promise:** See unusual patterns. Understand the evidence. Coordinate the human response.

Principles:
1. Human authority: software proposes candidates; authorised people decide.
2. Explainability: show inputs, baseline, method, threshold and limitations.
3. Privacy by design: aggregate-only data, minimisation, cohort suppression and tenant isolation.
4. Operational usefulness: connect ingestion to review, action and closure.
5. Honest uncertainty: missing or insufficient data must not be represented as normal.
6. Accessibility: responsive, low-bandwidth browser experience.
7. No harmful incentives: do not reward alert volume or collection of sensitive data.

## 4. Customers, buyers and personas

These segments are prioritisation hypotheses requiring discovery.

| Segment | Buyer / budget owner | Primary users | Job | Priority |
|---|---|---|---|---|
| Employers / industrial operators | HR, HSE, occupational health, operations | Occupational-health teams, HSE analysts, site reviewers | Monitor aggregate workforce indicators across sites | High |
| Occupational-health providers | Medical director, practice owner | Health professionals, analysts | Deliver recurring monitoring for contracted employers | High |
| NGOs / public-health programmes | Programme director, M&E lead | Public-health officers, field coordinators | Consolidate community aggregate reports and document follow-up | High |
| Government agencies | Department head, surveillance director, procurement | Surveillance officers, analysts | Review aggregate trends across communities | Strategic; longer sales cycle |
| Insurers / health administrators | Medical officer, population-health lead | Analysts, programme managers | Monitor aggregate programme indicators | Later |
| Research institutions | Principal investigator | Researchers, data managers | Explore authorised aggregate time series | Selective |

### Core personas
- **Organisation administrator:** provisions members, assigns roles and controls access.
- **Analyst:** imports observations, checks data quality and runs detection.
- **Reviewer:** inspects candidates, investigates, records findings/actions and resolves.
- **Viewer:** reads permitted summaries without mutation rights.
- **Economic buyer:** approves budget and needs evidence of operational value, security, implementation effort and total cost.

## 5. Scope and release definition

### Existing baseline
Authentication, memberships, roles, tenant isolation/RLS, CSV ingestion, validation, duplicate checks, cohort suppression, median/MAD detection, candidate alerts, review workflow, dashboard and synthetic evaluation exist in the repository.

### MVP goal
Make the current core workflow reliable in a controlled pilot:
1. Provision organisation and administrator.
2. Sign in and invite members.
3. Import approved aggregate CSV.
4. Return accepted, duplicate, suppressed and rejected row counts.
5. Screen eligible observations against prior history.
6. Display evidence-backed candidates.
7. Reviewer acknowledges, investigates, records findings/actions and resolves.
8. Administrator can inspect members, activity and usage.
9. Customer can understand plan, limits and support route once commercial controls are built.

### Exclusions for MVP
Native mobile apps; live wearables/sensors; automated ML training; LLM clinical interpretation; individual records; diagnosis; individual risk scores; outbreak declaration; automated clinical or operational decisions; multi-country compliance claims; microservices or Kubernetes.

### Release stages

| Stage | Goal | Exit criterion |
|---|---|---|
| R0 Engineering baseline | Preserve current working code and CI | Existing tests, migration/RLS checks and frontend build pass |
| R1 Pilot readiness | Reliable onboarding, data quality, review and operations | Deployed end-to-end acceptance tests pass |
| R2 Paid pilot | Validate willingness to pay and workflow value | Paid scoped pilot and formal outcome review |
| R3 Commercial v1 | Plans, entitlements, billing, support and customer admin | Subscription lifecycle tests pass |
| R4 Scale | Repeatable integrations, monitoring and deployment options | Renewals, security and delivery economics demonstrated |

## 6. Functional requirements

Priority: P0 = mandatory for safe pilot; P1 = commercial v1; P2 = later, evidence-led.

### FR-01 Organisation provisioning and onboarding [P0]
- Create unique organisation and initial administrator.
- Bootstrap secret is never exposed in normal responses or logs and can be disabled/rotated after use.
- Administrator signs in and sees only their memberships.
- Invitations are single-use, expiring, stored hashed and limited to roles the issuer may grant.
- Invitation tokens are removed from browser history after extraction.
- Errors do not reveal account existence to unauthorised parties.

### FR-02 Authentication and session lifecycle [P0]
- Passwords are securely hashed; plaintext passwords are never stored/logged.
- Session tokens are random, opaque, stored hashed, expire and can be revoked.
- Cookies are HttpOnly; Secure in production; SameSite/domain/path match deployment.
- CSRF and origin checks protect browser mutations.
- Add edge rate limiting before real customer use.
- Account recovery, deactivation and session-revocation management are required before broad commercial onboarding.
- Expired/revoked sessions cannot access protected routes.

### FR-03 Role-based access [P0]
- org_admin: manage members and organisation; access permitted data and review.
- analyst: import and run detection; no reviewer-only decisions.
- reviewer: inspect candidates and perform review; no data import by default.
- viewer: read-only.
- Permissions enforced server-side, not only by hiding UI controls.
- Tests cover every role against every protected operation.
- Role changes are effective on next request and are auditable.

### FR-04 Tenant isolation [P0]
- Every tenant-owned record has organisation ownership.
- All reads and writes enforce authenticated organisation context.
- Cross-tenant reads/writes/updates/deletes are denied.
- PostgreSQL RLS and FORCE RLS remain enabled on tenant tables.
- Production application DB role is non-superuser and has no BYPASSRLS.
- CI tests RLS with a restricted non-superuser role.
- Tenant context is transaction-local and cannot leak across pooled connections.
- Background jobs must explicitly establish tenant context.

### FR-05 Aggregate ingestion [P0]
Required CSV columns: domain, group_code, source_code, observed_date, indicator, value, denominator, unit.
- Validate encoding, headers, dates, domains, identifiers and numeric values.
- Enforce upload byte limit.
- Values finite and non-negative; supplied denominators positive.
- Each row identifies exactly one domain target.
- Detect duplicates deterministically.
- Return accepted, duplicate, suppressed and rejected counts.
- Rejection reasons are bounded and actionable; do not echo sensitive content.
- Preserve source and import provenance.
- No silent overwrite or duplicate alert on re-import.
- Individual identifiers and case records are not accepted as valid aggregate fields.

### FR-06 Data quality and provenance [P0/P1]
- Preserve source, group, indicator, date, unit and import provenance.
- Missing periods are not converted to zero.
- Distinguish invalid, duplicate, suppressed and accepted rows.
- Show rejection reasons, insufficient history and last successful import.
- P1: persistent data-quality issues with status, assignment and resolution.
- P1: source freshness and late-arriving data clearly labelled.

### FR-07 Workforce privacy and cohort suppression [P0]
- Unknown cohort size fails closed.
- Below-threshold cohorts are suppressed across dashboard, alert evidence, API and exports.
- Default threshold in current prototype is 20; deployments must validate it with privacy, occupational-health and legal experts.
- No employee identifiers, names or individual diagnoses.
- Conservative cohort-size handling when denominators change.
- Repeated queries, filters or exports must not expose suppressed values by inference.
- Explain that suppression is a privacy control, not proof that no event occurred.

### FR-08 Statistical screening [P0]
- Compare each observation only with earlier observations from same organisation, group and indicator.
- Current default minimum history: 6; trailing maximum: 26 prior observations; candidate threshold: 3.5.
- Persist baseline, score where calculable, reason, threshold, history count, detector name and version.
- Insufficient history has an explicit non-scored reason.
- Zero-MAD behaviour must not fabricate a finite score.
- Current MVP creates high-side candidates only; low-side deviations require separate product approval.
- Version parameters and prevent duplicate results/alerts on rerun.
- Failed detection is visible and not silently marked processed.
- UI labels output as statistical candidate, not diagnosis, prediction or declaration.

### FR-09 Alert queue and evidence [P0]
- Link alert to source observation and detection result.
- Show domain/group, indicator, date, value, baseline, score, threshold, history count and detector version.
- Explain severity derivation and status.
- Filter by status/domain/group/date where supported.
- Navigate to source observation and investigation history.
- Do not silently delete candidate alerts.
- No automatic public-health or employee notification solely from anomaly.

### FR-10 Human review [P0]
- Reviewer can acknowledge, start investigation, record findings, add response action and resolve.
- Resolution requires disposition and rationale.
- Every transition records actor, tenant, timestamp and safe event metadata.
- Resolved alerts remain in history.
- Mutations are idempotent or safely reject duplicates.
- Distinguish machine evidence from human-entered findings.
- No prescribed treatment or autonomous response.

### FR-11 Audit [P0]
- Record security- and review-relevant events with actor, tenant, event, target and timestamp.
- Never log passwords, session/invitation tokens, raw health files or sensitive row content.
- Audit history is not editable through normal workspace.
- Restrict audit access and define retention/export policy before real data.

### FR-12 Workspace [P0]
- Only show authorised organisation data.
- Dashboard counts reconcile with underlying records.
- Show data freshness and period where available.
- Provide clear empty, loading, validation, permission, network and server states.
- Responsive on mobile and desktop; core workflows usable on constrained connections.
- Candidate alerts include non-diagnostic disclaimer.

### FR-13 Notifications [P1]
- Optional, permission-aware notification preferences.
- Minimum necessary content; no sensitive evidence in public URLs.
- Authenticated links return to workspace.
- Bounded retries and delivery tracking.
- Never phrase candidate as confirmed diagnosis or emergency.

### FR-14 Exports and reports [P1]
- Export permitted aggregate summaries and review histories.
- Preserve tenant scope and cohort suppression.
- Include generation time, date range, filter and methodology/version.
- Audit exports; no credentials or individual health data.

### FR-15 Plans, subscriptions and billing [P1]
- Billable organisation has plan and subscription state.
- Entitlements stored as structured server-side configuration.
- Backend enforces limits; frontend is not a security boundary.
- Verify payment webhook signatures and process events idempotently.
- Explicit states for trial/pilot, active, past due, grace, cancelled, expired and suspended.
- Customer sees plan, usage, billing status and renewal.
- Downgrade must not silently delete data.
- Currency, taxes, invoices, refunds and procurement terms configurable by market.
- Safety and privacy protections are never reduced by plan tier.

### FR-16 Customer administration [P1]
- Member listing, role changes, deactivation and session revocation.
- Narrowly scoped, audited support access.
- Tenant suspension without deleting records.
- Documented data export, retention and deletion workflow.

### FR-17 Integrations and scheduled ingestion [P2]
- Build only against named customer use cases and approved data agreements.
- Document schema/provenance; secure connector credentials.
- Idempotent sync, last-successful timestamp, counts and failures.
- Same validation and tenant rules as CSV.
- Customer can pause/revoke connector.
- Do not claim live integration until monitoring and failure handling are tested.

## 7. Core user journeys

### A. Onboarding
Provision organisation → administrator signs in → invites members → members accept one-time invitations → administrator confirms roles → workspace shows onboarding checklist and synthetic-data option.

**Success:** intended users access the correct tenant with least privilege.

### B. First import
Analyst downloads template/data dictionary → prepares authorised aggregate file → uploads → system validates → summary shows accepted/duplicate/suppressed/rejected → analyst corrects errors → eligible observations enter detection.

**Success:** analyst understands exactly what was accepted and why rows were rejected or suppressed.

### C. Candidate review
Detector evaluates history → candidate appears → reviewer inspects evidence → acknowledges → opens investigation → records findings/actions → resolves with rationale → audit history shows sequence.

**Success:** organisation can reconstruct what was detected and what a human decided.

### D. Renewal
Customer success reviews usage, import quality, review completion, time-to-review and user feedback against baseline → buyer evaluates operational value and delivery cost → renew, expand, change plan or stop.

**Success:** renewal is based on demonstrated workflow value, not alert volume.

## 8. UX and information architecture

Navigation:
1. Overview
2. Observations
3. Import data
4. Alerts
5. Investigations
6. Reports (P1)
7. Organisation
8. Plan & billing (P1)
9. Help & support

UX requirements:
- Plain language beside technical labels.
- Distinguish observation, anomaly score, candidate alert, investigation and response action.
- Never communicate status through colour alone.
- Show period, source and freshness.
- Explain why a score is unavailable.
- Avoid complex visualisations as a prerequisite to action.
- Accessible labels, focus, contrast and keyboard interaction.
- Persistent aggregate-data reminder in import flow.

## 9. Data model and governance

### Existing entities
Organisations, users, memberships, sessions, invitations, communities, workforce groups, data sources, health observations, detection results, alerts, investigations, response actions and audit logs.

### Proposed future entities (not currently implemented)
| Entity | Purpose |
|---|---|
| import_batches | Upload provenance, submitter, file hash, status and row counts |
| data_quality_issues | Track defects, severity, assignment and resolution |
| alert_assignments | Reviewer ownership |
| alert_dispositions | Structured outcome and rationale |
| notification_preferences / deliveries | Consent, delivery state and retries |
| plans / plan_entitlements | Product packages and configurable limits |
| subscriptions | Organisation commercial lifecycle |
| usage_events | Metered usage ledger with idempotency |
| invoices / payment_events | Reconciliation and verified provider events |
| support_cases | Customer support and severity tracking |

Governance requirements:
- Aggregate-only data for MVP.
- Define indicator dictionary, units, denominators, reporting periods and group semantics.
- Missing is not zero.
- Preserve provenance and detector version.
- Define retention/deletion before operational data.
- Document controller/processor roles, lawful authority and data-sharing agreements.
- Least privilege for support and engineering.
- Encrypt transport and storage using supported hosting controls.
- Tested backups and restoration.
- Retain raw upload files only as long as necessary.
- No cross-customer benchmarks or model training without explicit legal basis, customer agreement and privacy review.

## 10. Detection quality and trust

Current detector: trailing historical median and MAD. Current defaults: minimum history 6, maximum 26 prior observations, candidate threshold 3.5. These are engineering defaults, not clinically validated thresholds.

Evaluation:
- Chronological replay; no random time-series split.
- Ground-truth labels separate from detector inputs.
- Report community and workforce separately.
- Measure precision, recall, F1, false alerts per group-week, anomaly groups detected and detection delay.
- Include counts and positive cases behind metrics.
- Test missing periods, denominator shifts, zero-MAD, duplicates, delayed data and reporting changes.
- Synthetic evaluation is engineering regression only.
- Domain expert review precedes real-world interpretation.

Trust metrics:
- Candidate evidence completeness.
- Import provenance completeness.
- Observations with sufficient history.
- Time to first human review.
- Investigations with documented rationale.
- Data-quality issue rate by source.
- False alerts per group-week.
- Reviewer usefulness feedback and dismissal reasons.

More alerts are not automatically better; zero alerts can indicate an insensitive detector.

## 11. Monetisation strategy

### 11.1 Recommended model

Adopt a **B2B/B2G organisation subscription model** with paid implementation and optional integration/support services.

Primary pricing unit: organisation plus monitored coverage band (sites, communities or reporting groups). Do not price per alert or individual record.

Why:
- Buyers budget for operational systems and programmes.
- Value comes from recurring monitoring and review.
- Coverage is more predictable than alert volume.
- Per-alert fees create an incentive to generate more alerts.
- Per-person health-data pricing conflicts with aggregate-first privacy.

### 11.2 Revenue streams

**1. Recurring platform subscription — primary**
Annual or monthly organisation contract for workspace, aggregate ingestion, statistical screening, review workflow and standard reporting within plan limits.

**2. Implementation and onboarding**
One-time fee for organisation setup, data dictionary mapping, CSV configuration, role setup, analyst/reviewer training and pilot configuration.

**3. Data integration services**
Fixed-scope secure file transfer or API integration, source mapping, validation and ongoing maintenance.

**4. Premium support**
Named contact, agreed response windows, scheduled reviews, training and escalation. Only sell service levels the team can staff.

**5. Private deployment / managed hosting**
Dedicated environment or customer-managed deployment for buyers with governance requirements. Offer only after upgrade, backup, monitoring and incident operations mature.

**6. Training and enablement**
Analyst onboarding, reviewer workflow, data-quality workshops and responsible interpretation of statistical signals.

**7. Research/programme partnerships**
Fixed-scope grant-funded or research deployments. Treat as project revenue, not assumed recurring SaaS revenue.

### 11.3 What must never be monetised
- Sale or brokerage of patient/employee health data.
- Individual-level health profiles or employee surveillance.
- Re-identification or inference of suppressed cohorts.
- Pay-per-alert or rewards for alert volume.
- Unsupported outbreak prediction or clinical guarantees.
- Cross-customer benchmarking/model training without explicit legal, privacy and contractual authorisation.

### 11.4 Proposed packaging

| Tier | Target | Package | Commercial purpose |
|---|---|---|---|
| Sandbox | Evaluators and demo users | Synthetic data only; limited workspace; no operational health data | Discovery and lead generation |
| Pilot | One employer, provider, NGO or programme | Fixed duration, scoped indicators, onboarding and outcome review | Paid validation |
| Professional | Smaller employer/provider | One organisation, standard coverage, core workflow and standard support | Entry recurring contract |
| Growth | Multi-site employer/provider or larger programme | Larger coverage, reports, priority support and integration allowance | Main SaaS tier |
| Enterprise / Public Sector | Large employer, insurer, agency or multi-region programme | Custom coverage, procurement, SLA, security review and deployment options | High-value annual contract |

Sandbox must use synthetic data only; it is not a free production tier.

### 11.5 Initial price experiments

These are **discovery ranges**, not market benchmarks or validated prices. Validate budgets, willingness to pay, delivery effort, local purchasing power, tax treatment and currency risk before publishing.

| Offer | Initial test range | Scope hypothesis |
|---|---:|---|
| Paid proof-of-value pilot | ₦1.5m–₦5m fixed | 8–12 weeks; one organisation/programme; agreed indicators; onboarding and outcome review |
| Professional | ₦250k–₦600k/month | Small coverage band; standard workspace and support |
| Growth | ₦750k–₦2m/month | Multi-site/larger programme; broader coverage and support |
| Enterprise / public sector | Custom annual contract | Scope, service level, deployment, procurement and integration |
| Implementation | ₦500k–₦3m one-time | Source mapping, configuration and training |
| Custom integration | Fixed statement of work | Quote after technical discovery |
| Training workshop | ₦150k–₦500k/session | Audience size and delivery format determine fee |

For international discovery, test USD value-based annual contracts rather than mechanically converting NGN prices. Review NGN prices quarterly or after material FX/cost changes. Each proposal must state treatment of VAT, withholding taxes, payment fees and other taxes.

Do not publish every tier at once. Start with paid pilots, measure delivery cost and buyer response, then choose one or two repeatable subscription packages.

### 11.6 Pricing metric and entitlement model

Potential coverage dimensions:
- Monitored sites, communities or reporting groups.
- Active data sources/integrations.
- Monthly observation volume or import frequency where infrastructure cost is material.
- Support tier and deployment mode.

Never charge per alert, investigation, reviewer action or suppressed cohort.

Proposed server-side entitlement keys:
- max_groups
- max_sites
- max_data_sources
- max_monthly_observations
- max_file_size_bytes
- max_members
- reporting_exports
- scheduled_imports
- api_access
- integration_slots
- support_level
- deployment_mode

Set exact limits only after pilot usage and cost data. Safety/privacy controls—tenant isolation, CSRF, role enforcement, cohort suppression, auditability and evidence transparency—apply to every plan.

### 11.7 Go-to-market sequence

**Beachhead 1: employers and occupational-health providers**
- Clear multi-site workforce monitoring use case.
- Potential recurring need.
- Requires strong employee privacy and aggregate-only boundaries.

**Beachhead 2: NGOs and funded public-health programmes**
- Programme budgets may support time-bound pilots.
- Good setting to validate community aggregate reporting.
- Renewal may follow grant cycles.

**Beachhead 3: government agencies**
- Strategic reach but longer procurement, policy, security and integration cycles.
- Pursue after references and operational readiness.

**Later: insurers and health administrators**
- Potentially attractive recurring use case, but requires stronger evidence and governance.

### 11.8 Sales motion
1. Identify operational owner and budget owner.
2. Interview about data flow, review process, reporting cadence and pain.
3. Map one use case and one or two indicators.
4. Confirm data authority, aggregation and privacy requirements.
5. Agree baseline and pilot success criteria.
6. Demonstrate with synthetic data.
7. Run paid pilot with authorised aggregate data.
8. Present measured workflow value and limitations.
9. Convert to annual contract if value/readiness are demonstrated.
10. Expand coverage/integrations only after initial workflow is stable.

### 11.9 Paid pilot design

**Duration:** proposed 8–12 weeks.  
**Scope:** one organisation/programme, agreed reporting groups and indicators, named reviewers.  
**Data:** synthetic during setup; authorised aggregate data only after legal, privacy and security approval.

Deliverables:
- Configured workspace and role setup.
- Data dictionary and CSV mapping.
- Analyst/reviewer onboarding.
- Import and data-quality report.
- Candidate-signal and review workflow report.
- Outcome review and recommended next step.

Success measures:
- Time to prepare/import reporting period.
- Accepted/rejected/duplicate/suppressed row rates.
- Evidence completeness.
- Time from candidate to first review.
- Investigations with documented disposition.
- Reviewer usefulness and dismissal reasons.
- User activation and repeat usage.
- Willingness to renew at a stated price.

Do not promise reductions in disease, absenteeism, outbreak size or mortality in an early software pilot.

### 11.10 Unit economics

Track actual per-customer costs: hosting/database, storage/backups/egress, monitoring/security, payment/FX, onboarding/training hours, integration hours, support hours, incident costs, sales/procurement and third-party messaging.

Formulas:
- MRR = sum of active recurring subscription value for the month.
- ARR = normalised annual value of active recurring contracts; exclude one-time services.
- Gross margin = (revenue − direct hosting, support and delivery costs) / revenue.
- CAC = attributable sales and marketing cost / new paying customers.
- CAC payback months = CAC / monthly gross profit per new customer.
- Logo retention = customers retained / customers at period start, excluding new customers.
- NRR = (opening recurring revenue + expansion − contraction − churn) / opening recurring revenue.
- Pilot conversion = eligible completed paid pilots converted / eligible completed paid pilots.

Do not publish CAC, LTV, churn, margin or ARR claims until actual contract and cost data exist. Aim for recurring revenue whose delivery cost does not rise linearly with every customer.

### 11.11 Commercial risks

| Risk | Mitigation |
|---|---|
| Buyer lacks data authority | Data authority and governance checklist before onboarding |
| Long public procurement | Start with employers/providers and funded programmes |
| Inconsistent source data | Paid readiness assessment, validation reports and scoped integrations |
| False-alert fatigue | Chronological evaluation, domain review, threshold tuning and transparent dispositions |
| Buyer expects clinical prediction | Clear positioning, contract language and UI disclaimers |
| Bespoke work erodes margin | Standard templates; charge scoped work; productise repeatable needs |
| FX/payment friction | Local currency where suitable, clear renewal rules, periodic price review |
| Data breach/tenant leakage | RLS, least privilege, independent testing, incident response and minimisation |
| Grants mask weak demand | Track paid renewals separately from grant-funded pilots |
| Support promises exceed capacity | Publish only service levels that can be staffed |

## 12. Success metrics

**North Star:** Monthly reviewed signal workflows—the number of candidate workflows in which an authorised reviewer records a disposition during the month. Pair with quality and safety metrics; more alerts are not inherently better.

Product metrics:
- Organisation activation: completes onboarding and first valid import.
- Time to first valid import.
- Import acceptance and rejection rates by source.
- Evidence completeness; required evidence target 100%.
- Review completion rate.
- Time to first review.
- Investigations with findings and resolution rationale.
- Monthly active organisations.
- Reviewer adoption.

Safety guardrails:
- Cross-tenant access incidents: zero.
- Individual identifiers accepted in aggregate import: zero.
- Unknown/small cohort disclosure: zero.
- Candidate without required evidence: zero.
- Unauthorised role action: zero.
- Critical audit-event loss: zero.
- Missing data silently converted to zero: zero.
- Monitor false alerts per group-week and unreviewed candidate volume.

Business metrics:
- Qualified buyer conversations.
- Discovery-to-pilot conversion.
- Paid pilot count/value.
- Pilot-to-annual conversion.
- MRR/ARR from recurring contracts only.
- Average contract value and gross margin.
- Implementation/support hours per customer.
- Renewal, churn, expansion and collection time.

## 13. Non-functional requirements

**Security:** HTTPS; secure password/session handling; CSRF/origin validation; server-side RBAC; tenant scoping and RLS; restricted DB role; secrets outside source control; rate limiting; audit logs; independent review before operational data.

**Privacy:** aggregate-only scope; cohort suppression; minimisation; documented legal roles/data agreements; retention/deletion; no data sale; no unauthorised cross-tenant analytics.

**Reliability:** liveness/readiness probes; tested backups/restoration; monitoring and incident response; migration/recovery process; bounded uploads/timeouts; idempotent imports and webhooks.

**Performance:** bounded/paginated dashboard queries; size-limited uploads; historical queries must not block review; async reporting when needed. Publish targets only after representative load tests.

**Accessibility:** responsive mobile/desktop; keyboard access; semantic labels; readable contrast; status not colour-only; current mainstream browsers; low-bandwidth page weight.

**Maintainability:** modular monolith; versioned migrations; typed API contracts; automated tests; documented API/data dictionary; no credentials or real health records in fixtures.

## 14. Technical architecture

Current stack:
- Frontend: Next.js 15 App Router, React 19, TypeScript.
- API: FastAPI, Python 3.11+.
- Database: PostgreSQL, SQLAlchemy 2, Alembic.
- Auth: scrypt password hashing, database-backed sessions, HttpOnly cookies and CSRF controls.
- Authorisation: organisation memberships and four roles.
- Tenant isolation: organisation ownership, transaction-local context and PostgreSQL RLS.
- Detection: deterministic median/MAD service.
- CI: GitHub Actions with PostgreSQL-backed checks and frontend checks.

Architecture rules:
- Keep modular monolith until measured scale justifies change.
- Keep detection deterministic and independent of UI.
- Database access remains server-side.
- Enforce billing entitlements in backend.
- Use transactional outbox or equivalent for future notifications/integrations.
- Do not add Redis, Kubernetes or microservices without evidence.
- Keep synthetic evaluation separate from production data.
- Treat background jobs as tenant-security boundaries.

Future modules: customer provisioning/support admin; import batches/data quality; alert assignment/disposition; notifications; reporting; plans/subscriptions/usage/payment; integration adapters; operational monitoring.

## 15. API and integration roadmap

Existing API routes are documented in repository README. Future routes must use the /api/v1 convention and enforce auth, tenant, role and entitlement checks.

| Proposed route | Purpose |
|---|---|
| GET /api/v1/organizations/{id}/members | List organisation members |
| PATCH /api/v1/organizations/{id}/members/{member_id} | Change role/deactivate |
| GET /api/v1/imports | List import batches |
| GET /api/v1/imports/{id} | Inspect import result |
| GET /api/v1/data-quality/issues | List quality issues |
| POST /api/v1/alerts/{id}/assignments | Assign reviewer |
| POST /api/v1/alerts/{id}/disposition | Record structured outcome |
| POST /api/v1/reports/exports | Request aggregate export |
| GET /api/v1/billing/subscription | View plan/subscription |
| GET /api/v1/billing/usage | View usage |
| POST /api/v1/billing/checkout | Start verified checkout |
| POST /api/v1/billing/webhooks/{provider} | Receive signed provider event |

Payment provider selection must compare Nigerian onboarding/settlement, NGN and FX collection, recurring billing, hosted checkout, invoices, signed webhooks, idempotency, refunds/disputes, fees and settlement time. Enterprise and public-sector customers may prefer invoice/bank transfer. Support both provider payments and manually reconciled contracts in the billing domain.

## 16. Roadmap and delivery epics

**Epic 1 — Pilot deployment [P0]:** hosting, production secrets/CORS/cookies, rate limiting, monitoring, backups/restore, live browser E2E, security/privacy review, incident and release procedures. Exit: deployed smoke test passes.

**Epic 2 — Data onboarding [P0]:** import batch records, template/data dictionary, quality summaries, idempotent retry, freshness/missing-period display. Exit: analyst can diagnose and safely repeat import.

**Epic 3 — Review completeness [P0]:** assignment, structured disposition, required rationale, workload/history and audit tests. Exit: candidate traceable from observation to human disposition.

**Epic 4 — Customer administration [P1]:** members, roles, deactivation, session revocation, recovery, secure invitation delivery and support. Exit: customer admin safely manages access.

**Epic 5 — Commercial foundation [P1]:** plans, entitlements, subscription state, usage ledger, provider evaluation, invoices, webhooks, billing page, grace/downgrade policy. Exit: upgrade/downgrade/renew/payment failure/cancel tested without entitlement bypass or data loss.

**Epic 6 — Reports/notifications [P1]:** safe exports, scheduled reports, preferences, delivery tracking. Exit: permission-aware reporting works.

**Epic 7 — Integrations [P2]:** one customer-backed connector, scheduled sync, failure monitoring, revocation and provenance. Exit: tenant/idempotency/quality/failure tests pass.

**Epic 8 — Scale/deployment options [P2]:** dedicated deployment, advanced monitoring, ingestion optimisation, localisation and recurring independent security testing. Exit: delivery/support cost viable across customers.

## 17. Release acceptance gates

### Pilot gate
- [ ] Production frontend/API URLs and HTTPS verified.
- [ ] Secure cookies and exact CORS origins verified.
- [ ] Private database; restricted non-superuser role without BYPASSRLS.
- [ ] Migrations and RLS tests pass.
- [ ] Rate limiting, backups and restore test in place.
- [ ] Admin bootstrap, sign-in, invitations and roles tested in browser.
- [ ] CSV valid/invalid/duplicate/suppressed cases tested.
- [ ] Detection history and zero-MAD cases tested.
- [ ] Alert evidence and full review workflow tested.
- [ ] Cross-tenant attempts rejected.
- [ ] Sign-out/session revocation and audit events verified.
- [ ] No direct identifiers in pilot data.
- [ ] Customer data authority and agreements approved.
- [ ] Security/privacy review completed or limitations documented.

### Commercial v1 gate
- [ ] Server-side plan entitlements configured.
- [ ] Subscription state transitions tested.
- [ ] Webhook signature/idempotency tests pass.
- [ ] Invoice/bank-transfer reconciliation documented.
- [ ] Usage ledger reconciles.
- [ ] Upgrade/downgrade/cancel/payment failure tested.
- [ ] Safety/privacy controls identical across tiers.
- [ ] Support and incident escalation staffed.
- [ ] Terms, privacy notice, DPA and retention reviewed by qualified counsel.
- [ ] Public prices and SLA claims match delivery capacity.

## 18. Assumptions, risks and open decisions

Assumptions to validate:
- Buyers have recurring aggregate observations and authority to share them.
- A recurring operational need is not adequately served by spreadsheets/dashboards.
- Review workflow value supports recurring subscription.
- Initial customers can provide consistent groups and historical data.
- Standard import templates can serve early customers.

Open decisions:
1. Which beachhead segment gets the first paid pilot: employer, occupational-health provider or NGO/programme?
2. Which indicators and reporting cadence are supported first?
3. What history length is realistic for each indicator?
4. Should low-side deviations be supported later?
5. Which structured dispositions are required?
6. What retention applies to uploads, observations, alerts and audit records?
7. What cohort threshold is appropriate per deployment?
8. Which payment/invoice methods suit first customers?
9. What support hours and response times can be delivered?
10. Which hosting region and legal arrangements suit each customer?

Risks include reporting changes, missing data, denominator shifts, seasonality, insufficient history, false alerts, limited visibility for small cohorts, slow public procurement, service-heavy integrations and the gap between security foundations and regulatory certification.

## 19. Validation and launch plan

**Phase A — Discovery**
- Interview at least 10 qualified stakeholders across priority segments.
- Map data sources, cadence, manual effort, review roles and budget.
- Test problem statement and packaging/pricing hypotheses.
- Confirm data authority and aggregate-only acceptance.

**Phase B — Design partner**
- Select one organisation with a data owner and named reviewer.
- Agree narrow indicators and cadence.
- Complete governance/security checks.
- Define baseline workflow metrics.
- Demonstrate synthetic data before authorised aggregate data.

**Phase C — Paid pilot**
- Sign scoped pilot agreement.
- Configure workspace, roles and import mapping.
- Train analysts/reviewers.
- Review weekly quality, candidate and workflow metrics.
- Document false alerts and dismissals.
- Conduct formal outcome review.

**Phase D — Commercial decision**
- Compare measured value with delivery cost and price.
- Convert to annual subscription only where value is demonstrated.
- Productise repeatable needs.
- Stop or redesign segments without willingness to pay, data authority or operational fit.

## 20. Final product decision

PulseGrid Health should be built and sold as a **privacy-aware, explainable early-warning and human-review platform**, not an AI doctor, outbreak predictor or health-data marketplace.

The immediate priority is to make the current core loop dependable in a controlled pilot: authorised aggregate data in, quality checks, historical screening, evidence-backed candidate, human review, documented disposition and measurable operational value.

The commercial priority is to validate one paying customer segment, one repeatable use case and one sustainable contract structure. Begin with paid pilots, convert proven workflows to organisation-level subscriptions, and expand through implementation, integrations, support and deployment services. Build billing and plan enforcement only after willingness to pay and delivery economics are evidenced.

**PulseGrid Health — aggregate signals, explainable screening, accountable human review.**

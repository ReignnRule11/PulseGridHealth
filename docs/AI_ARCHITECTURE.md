# PulseGrid Health — AI-Native Architecture

**Status:** Proposed implementation architecture  
**Product boundary:** Population and workforce health intelligence; not diagnosis, clinical decision support, outbreak declaration, or individual employee/patient monitoring.

## 1. Product thesis

PulseGrid becomes AI-native when intelligence is embedded in the data-to-action workflow—not when a chatbot is added to the dashboard.

The platform will combine:
1. Deterministic data validation and statistical detection.
2. AI-assisted interpretation of aggregate signals and contextual evidence.
3. Evidence-linked explanations and prioritisation for qualified human review.
4. Structured reviewer feedback and outcome measurement.
5. Governed, tenant-scoped natural-language exploration of authorised aggregate data.

AI must never replace the detector, invent evidence, or make autonomous clinical, public-health, employment, or resource-allocation decisions.

## 2. Target architecture

Retain the existing Next.js + FastAPI + PostgreSQL modular monolith. Do not introduce microservices, Kubernetes, Redis, or a vector database for the first AI release.

### Request and processing flow

1. **Ingestion boundary:** accept validated aggregate observations only; enforce schema, provenance, time range, unit, source, and cohort suppression rules.
2. **Deterministic analytics:** run the existing robust baseline/anomaly detector and data-quality checks. Preserve raw metrics, baseline window, threshold, detector version, and result.
3. **Context assembly:** construct a minimal, typed, tenant-scoped evidence packet from permitted aggregate observations, detector output, source metadata, and approved contextual references.
4. **AI orchestration:** call a provider-neutral model adapter with a versioned prompt and strict structured-output schema. Apply timeout, token/cost budget, rate limit, retry policy, and feature flag.
5. **Validation:** validate schema, evidence IDs, arithmetic claims, uncertainty language, and policy constraints. Reject unsupported claims; never silently repair fabricated evidence.
6. **Persistence:** store model/provider identifier, model version, prompt version, input evidence references, structured output, timestamps, latency, token/cost metadata, validation outcome, and reviewer feedback. Do not store secrets or raw sensitive payloads in logs.
7. **Human review:** show the candidate insight with its evidence, limitations, and uncertainty. A qualified reviewer decides whether to dismiss, investigate, or escalate under the organisation's approved process.
8. **Feedback/evaluation:** capture structured dispositions and reasons; measure usefulness, reviewer agreement, false-positive burden, and drift. Feedback does not automatically retrain or change production thresholds.

## 3. Initial AI capabilities

### AI-1: Evidence-backed alert explanation
For an existing statistical candidate alert, produce:
- concise plain-language summary of what changed;
- exact aggregate metrics and comparison period;
- detector result and baseline context;
- data-quality caveats and missingness;
- plausible non-diagnostic interpretations, clearly labelled as hypotheses;
- what evidence would strengthen or weaken the signal;
- suggested questions for a qualified reviewer;
- explicit statement that this is a candidate signal, not a diagnosis or confirmed event.

Every factual statement must map to evidence IDs in the input packet. If evidence is insufficient, the system must say so.

### AI-2: Data-quality intelligence
Explain missing periods, inconsistent units, duplicate aggregates, unusual reporting volume, stale feeds, and cohort suppression. Rules remain deterministic; AI may explain the issue and propose a correction checklist, but must not silently rewrite source data.

### AI-3: Aggregate health intelligence copilot
Allow natural-language questions only over a constrained set of tenant-scoped aggregate metrics and approved documentation. The model must generate a typed query plan from an allowlisted metric catalogue; the server validates and executes it with read-only permissions, row/time limits, cohort suppression, and tenant isolation. The model must not emit arbitrary SQL for direct execution.

### AI-4: Review synthesis
Summarise reviewer-entered structured dispositions and aggregate investigation notes. No individual-level inference, diagnosis, or automated closure/escalation.

## 4. Structured output contract

The explanation service should return a versioned object with:
- `summary`
- `observed_changes[]` — metric, value, unit, period, comparison, evidence_id
- `possible_interpretations[]` — hypothesis, supporting_evidence_ids, contradicting_evidence_ids, confidence_label
- `data_quality_caveats[]`
- `review_questions[]`
- `recommended_review_steps[]`
- `limitations[]`
- `requires_human_review: true`
- `classification: "candidate_signal"`
- `evidence_ids[]`
- `model_metadata` stored separately from user-facing content

Confidence labels are qualitative and must not be represented as calibrated probabilities unless calibration is separately validated. The model may not invent numerical risk scores.

## 5. Model gateway and provider portability

Define an internal interface such as `AIProvider.generate_structured(request, schema, limits)`. Provider implementations must be replaceable without changing domain logic.

Required controls:
- provider and model allowlist;
- secrets only in server-side environment/secret manager;
- no provider key in frontend bundles;
- explicit request timeout and bounded retries;
- per-organisation and global usage budgets;
- request-size and output-size limits;
- feature flag and deterministic fallback;
- prompt/schema versioning;
- provider outage handling;
- redacted operational telemetry.

Do not select a provider solely on benchmark claims. Compare quality, structured-output reliability, data-processing terms, regional availability, latency, and total cost using synthetic/approved aggregate fixtures. The AI-1 adapter is implemented, but the feature remains disabled until live provider verification and the release gates below are complete.

## 6. Security, privacy, and governance

- Aggregate-only data remains the product boundary. Do not send names, email addresses, employee IDs, patient identifiers, free-text clinical notes, or row-level records to a model.
- Workforce cohort minimums must be enforced before context assembly; unknown or suppressed cohort size fails closed.
- Tenant authorisation is enforced by the API before any model call and again when loading evidence for display.
- Model calls use the minimum necessary aggregate context; no cross-tenant prompts, caches, retrieval, or training.
- Treat uploaded text and source metadata as untrusted data, never as model instructions. Defend against prompt injection.
- No model tool may mutate observations, alerts, reviewer decisions, user permissions, or source configuration.
- No diagnosis, treatment advice, outbreak confirmation, employee fitness assessment, disciplinary recommendation, or individual risk scoring.
- Keep an audit trail of AI generation and reviewer disposition. Define retention and deletion controls before production.
- Complete independent privacy, security, legal, and domain-expert review before any real health data or operational deployment.

## 7. Evaluation before release

Build a versioned synthetic evaluation set with expected evidence references and reviewer-approved answer criteria. Evaluate:
- evidence attribution precision;
- unsupported/fabricated claim rate (target zero on release-gating fixtures);
- schema validity;
- correct abstention when evidence is insufficient;
- numerical consistency;
- prohibited-output rate;
- tenant-isolation tests;
- prompt-injection resistance;
- latency and cost per explanation;
- reviewer usefulness and agreement in a controlled study.

Use deterministic fixtures and regression tests. Do not use random train/test splits for temporal data. Do not claim clinical validity from synthetic evaluation.

## 8. Delivery phases

### AI-0 — Product and governance contract
- Approve scope, prohibited uses, aggregate-only boundary, model-provider evaluation criteria, and acceptance metrics.
- Define evidence packet and structured output schemas.

### AI-1 — Explainable alert intelligence
- Provider-neutral gateway and fake/test provider.
- Context builder over existing alert/detection records.
- Strict structured output, evidence validation, persistence, audit, feature flag, and deterministic fallback.
- UI explanation panel with evidence links, caveats, and reviewer controls.
- Synthetic fixtures and CI evaluation.

### AI-2 — Data-quality intelligence
- Explain deterministic quality issues and produce correction checklists.
- Preserve human-controlled source corrections.

### AI-3 — Aggregate intelligence copilot
- Metric catalogue and constrained query-plan compiler.
- Read-only, tenant-scoped execution and cohort suppression.
- Source-linked answers; abstain when unsupported.

### AI-4 — Feedback and model operations
- Reviewer feedback analysis, drift monitoring, cost/quality dashboards, model/prompt release gates.
- Any learning or threshold changes require offline evaluation and explicit approval.

## 9. Release gates

AI features remain disabled by default until:
- deterministic fallback works;
- tenant isolation and cohort suppression tests pass;
- output schema and evidence validation pass;
- synthetic regression suite passes;
- prompt injection and prohibited-use tests pass;
- provider data-processing review is complete;
- cost, rate, timeout, and logging controls are configured;
- human-review workflow is operational.

**Current truth:** This document is an architecture proposal. It does not claim that an LLM, ML model, vector store, AI copilot, or provider integration is currently implemented or validated.

"""Live provider smoke test using synthetic evidence only.

Run with AI_ENABLED=true and AI_API_KEY set in the environment. This script
never reads production records and never prints credentials or model output.
"""
import sys
from pathlib import Path

# Make the API package importable when this script is invoked by file path
# from the apps/api working directory in GitHub Actions.
API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.ai_intelligence import (
    AlertExplanation,
    _provider_generate,
    _reject_numeric_claims,
    _validate_evidence_references,
)
from app.core.config import settings


def main() -> None:
    if not settings.ai_api_key:
        raise SystemExit("AI_API_KEY is missing; add it as a protected GitHub Actions secret.")
    if not settings.ai_enabled:
        raise SystemExit("AI_ENABLED must be true for this one-off smoke test.")

    evidence = {
        "alert_id": "synthetic-alert-smoke-test",
        "classification": "candidate_signal",
        "domain": "community",
        "group_code": "SYNTHETIC-ONLY",
        "indicator": "synthetic_febrile_illness_reports",
        "current": {
            "evidence_id": "obs:synthetic-current",
            "date": "2026-10-01",
            "value": 18,
            "unit": "reports",
        },
        "detector": {
            "evidence_id": "det:synthetic-detector",
            "name": "trailing_median_mad",
            "version": "1",
            "baseline": 4.0,
            "robust_score": 4.2,
            "threshold": 3.5,
            "history_count": 8,
            "reason": "Synthetic deviation from historical baseline",
        },
        "history": [
            {"evidence_id": f"obs:synthetic-history-{index}", "date": f"2026-09-{index:02d}",
             "value": value, "unit": "reports"}
            for index, value in enumerate([2, 3, 4, 3, 5, 4, 3, 4], start=1)
        ],
        "constraints": [
            "Synthetic data only",
            "Aggregate data only",
            "No diagnosis or outbreak declaration",
            "No individual or employment decisions",
            "Human review required",
        ],
    }

    raw = _provider_generate(evidence)
    explanation = AlertExplanation.model_validate(raw)
    allowed_ids = {
        evidence["current"]["evidence_id"],
        evidence["detector"]["evidence_id"],
        *(item["evidence_id"] for item in evidence["history"]),
    }
    _validate_evidence_references(explanation, allowed_ids)
    _reject_numeric_claims(explanation)

    print(
        "LIVE_PROVIDER_SMOKE=PASS "
        f"provider={settings.ai_provider_name} "
        f"model={settings.ai_model} "
        f"schema_version=1.1 "
        "evidence=synthetic_only"
    )


if __name__ == "__main__":
    main()

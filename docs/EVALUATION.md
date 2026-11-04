# Synthetic detector evaluation

## Purpose
This benchmark checks whether the current median/MAD detector identifies deliberately planted changes in reproducible synthetic data. It is an engineering smoke benchmark, not evidence of clinical validity, outbreak prediction, or occupational-health efficacy.

## Reproduce
From the repository root:

```bash
python scripts/generate_synthetic_data.py --output datasets/synthetic --seed 20261104
python scripts/evaluate_synthetic_detector.py --input datasets/synthetic --output evaluation_report.json
```

The generator writes two observation CSVs and a separate `ground_truth.csv`. Ground-truth labels are not part of the observation files and are used only by the scoring script.

## Method
- Replay observations in date order, separately by domain, group, and indicator.
- For each observation, score only against up to the preceding 26 observations, with a minimum history of 6 and robust z-score threshold of 3.5 by default.
- Score at the group-week level. Multiple workforce indicator alerts in the same group-week count as one predicted group-week.
- Report confusion counts, precision, recall, F1, false alerts per group-week, and mean detection delay for detected anomaly groups.
- Report community and workforce domains separately.

## Interpretation
Incidental deviations outside the planted windows are counted as false positives. The benchmark's planted labels are intentionally sparse and simplified. Results are seed- and parameter-dependent; they should be used to compare code changes on the same scenario, not as estimates of real-world performance. A group with no detection contributes to false negatives and has no detection-delay value.

## Known limitations
- This is an online replay over the full generated timeline, not a prospective field trial.
- The synthetic generator does not model reporting delays, changing denominators, missing weeks, correlated reporting practices, or real-world confounders.
- Workforce indicators are combined only for group-week scoring; the operational dashboard still exposes indicator-level evidence.
- No real person, patient, or employee data is generated or required.

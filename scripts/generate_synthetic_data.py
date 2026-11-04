import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

FIELDS = ["domain", "group_code", "source_code", "observed_date",
          "indicator", "value", "denominator", "unit"]
TRUTH_FIELDS = ["domain", "group_code", "observed_date", "is_anomaly"]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="datasets/synthetic")
    parser.add_argument("--seed", type=int, default=20261104)
    args = parser.parse_args()
    rng = random.Random(args.seed)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    start = date(2026, 1, 5)
    community_rows, workforce_rows, truth_rows = [], [], []

    for group in range(1, 6):
        code = f"C{group:03d}"
        baseline = 10 + group * 2
        for week in range(36):
            value = max(0, round(rng.gauss(baseline, 2)))
            anomaly = group == 2 and 25 <= week <= 27
            if anomaly:
                value += 18
            observed = start + timedelta(days=7*week)
            community_rows.append({
                "domain":"community", "group_code":code, "source_code":"SYNTHETIC",
                "observed_date":observed.isoformat(),
                "indicator":"weekly_febrile_illness_reports", "value":value,
                "denominator":5000 + group*500, "unit":"reports"
            })
            truth_rows.append({"domain":"community", "group_code":code,
                               "observed_date":observed.isoformat(), "is_anomaly":int(anomaly)})

    for group in range(1, 6):
        code = f"W{group:03d}"
        base = 3 + group
        for week in range(36):
            symptoms = max(0, round(rng.gauss(base, 1.2)))
            heat = round(rng.gauss(31 + group*0.4, 1.5), 1)
            anomaly = group == 3 and 28 <= week <= 30
            if anomaly:
                symptoms += 10
                heat += 4.5
            observed = start + timedelta(days=7*week)
            workforce_rows.append({
                "domain":"workforce", "group_code":code, "source_code":"SYNTHETIC",
                "observed_date":observed.isoformat(),
                "indicator":"weekly_heat_related_symptom_reports", "value":symptoms,
                "denominator":250, "unit":"reports"
            })
            workforce_rows.append({
                "domain":"workforce", "group_code":code, "source_code":"SYNTHETIC",
                "observed_date":observed.isoformat(),
                "indicator":"weekly_mean_heat_index", "value":heat,
                "denominator":None, "unit":"celsius"
            })
            truth_rows.append({"domain":"workforce", "group_code":code,
                               "observed_date":observed.isoformat(), "is_anomaly":int(anomaly)})

    for filename, rows, fields in [
        ("community_observations.csv", community_rows, FIELDS),
        ("workforce_observations.csv", workforce_rows, FIELDS),
        ("ground_truth.csv", truth_rows, TRUTH_FIELDS),
    ]:
        with (out / filename).open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    print(f"Wrote {len(community_rows)} community, {len(workforce_rows)} workforce, "
          f"and {len(truth_rows)} ground-truth rows to {out}")

if __name__ == "__main__":
    main()

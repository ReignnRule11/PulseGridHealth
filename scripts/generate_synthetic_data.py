import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

FIELDS = ["domain", "group_code", "source_code", "observed_date",
          "indicator", "value", "denominator", "unit"]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="datasets/synthetic")
    parser.add_argument("--seed", type=int, default=20261104)
    args = parser.parse_args()
    rng = random.Random(args.seed)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    start = date(2026, 1, 5)
    community_rows, workforce_rows = [], []

    for group in range(1, 6):
        code = f"C{group:03d}"
        baseline = 10 + group * 2
        for week in range(36):
            value = max(0, round(rng.gauss(baseline, 2)))
            if group == 2 and 25 <= week <= 27:
                value += 18  # planted synthetic anomaly
            community_rows.append({
                "domain":"community", "group_code":code, "source_code":"SYNTHETIC",
                "observed_date":(start + timedelta(days=7*week)).isoformat(),
                "indicator":"weekly_febrile_illness_reports", "value":value,
                "denominator":5000 + group*500, "unit":"reports"
            })

    for group in range(1, 6):
        code = f"W{group:03d}"
        base = 3 + group
        for week in range(36):
            symptoms = max(0, round(rng.gauss(base, 1.2)))
            heat = round(rng.gauss(31 + group*0.4, 1.5), 1)
            if group == 3 and 28 <= week <= 30:
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

    for filename, rows in [
        ("community_observations.csv", community_rows),
        ("workforce_observations.csv", workforce_rows)
    ]:
        with (out / filename).open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    print(f"Wrote {len(community_rows)} community and {len(workforce_rows)} workforce rows to {out}")

if __name__ == "__main__":
    main()
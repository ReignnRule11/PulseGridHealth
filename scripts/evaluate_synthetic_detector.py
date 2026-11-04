"""Replay the production MAD detector over synthetic observations and score group-weeks.

Ground-truth labels are read only by the scoring layer, never by the detector.
This is a synthetic scenario benchmark, not clinical validation.
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.services.detection import robust_anomaly  # noqa: E402

def read_rows(paths):
    rows = []
    for path in paths:
        with Path(path).open(newline="", encoding="utf-8") as handle:
            rows.extend(csv.DictReader(handle))
    return rows

def replay(observations, min_history=6, threshold=3.5, window=26):
    """Return predicted anomalous (domain, group, date) keys using past-only history."""
    grouped = defaultdict(list)
    for row in observations:
        key = (row["domain"], row["group_code"], row["indicator"])
        grouped[key].append(row)
    predictions = set()
    for (domain, group, _indicator), series in grouped.items():
        history = []
        for row in sorted(series, key=lambda item: date.fromisoformat(item["observed_date"])):
            result = robust_anomaly(
                history[-window:], float(row["value"]),
                min_history=min_history, threshold=threshold,
            )
            if result.is_candidate:
                predictions.add((domain, group, row["observed_date"]))
            history.append(float(row["value"]))
    return predictions

def score_domain(domain, truth, predictions):
    expected = {key for key, label in truth.items() if key[0] == domain and label}
    universe = {key for key in truth if key[0] == domain}
    predicted = {key for key in predictions if key[0] == domain}
    tp = len(expected & predicted)
    fp = len(predicted - expected)
    fn = len(expected - predicted)
    tn = len(universe - expected - predicted)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    delay_weeks = []
    by_group = defaultdict(list)
    for key in expected:
        by_group[key[1]].append(key[2])
    for group, anomaly_dates in by_group.items():
        onset = min(anomaly_dates)
        detected = sorted(
            key[2] for key in predicted
            if key[1] == group and key[2] in anomaly_dates
        )
        if detected:
            delay_weeks.append((date.fromisoformat(detected[0]) - date.fromisoformat(onset)).days // 7)

    return {
        "group_weeks": len(universe), "true_positive": tp, "false_positive": fp,
        "false_negative": fn, "true_negative": tn,
        "precision": round(precision, 4), "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_alerts_per_group_week": round(fp / len(universe), 4) if universe else 0.0,
        "detected_anomaly_groups": len(delay_weeks),
        "anomaly_groups": len(by_group),
        "mean_detection_delay_weeks": round(sum(delay_weeks) / len(delay_weeks), 2) if delay_weeks else None,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="datasets/synthetic")
    parser.add_argument("--output", default="evaluation_report.json")
    parser.add_argument("--min-history", type=int, default=6)
    parser.add_argument("--threshold", type=float, default=3.5)
    parser.add_argument("--window", type=int, default=26)
    args = parser.parse_args()
    data_dir = Path(args.input)
    observations = read_rows([
        data_dir / "community_observations.csv",
        data_dir / "workforce_observations.csv",
    ])
    truth_rows = read_rows([data_dir / "ground_truth.csv"])
    truth = {
        (row["domain"], row["group_code"], row["observed_date"]): bool(int(row["is_anomaly"]))
        for row in truth_rows
    }
    predictions = replay(observations, args.min_history, args.threshold, args.window)
    report = {
        "benchmark": "pulsegrid_synthetic_online_replay",
        "seed_note": "Use the generator seed to reproduce this synthetic scenario.",
        "parameters": {"min_history": args.min_history, "threshold": args.threshold, "history_window": args.window},
        "observation_rows": len(observations),
        "ground_truth_group_weeks": len(truth),
        "predicted_group_weeks": len(predictions),
        "domains": {
            domain: score_domain(domain, truth, predictions)
            for domain in ("community", "workforce")
        },
        "limitations": [
            "Synthetic scenario benchmark only; not clinical or epidemiological validation.",
            "Group-week scoring collapses multiple workforce indicators into one alert opportunity.",
            "Labels identify only deliberately planted anomaly windows; incidental deviations count as false positives.",
            "The detector is replayed chronologically and sees only prior observations.",
        ],
    }
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()

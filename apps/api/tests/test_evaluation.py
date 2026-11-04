import json
import subprocess
import sys
from pathlib import Path

def test_synthetic_evaluation_emits_domain_metrics(tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    data_dir = tmp_path / "synthetic"
    report_path = tmp_path / "evaluation.json"
    subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "generate_synthetic_data.py"),
         "--output", str(data_dir), "--seed", "20261104"],
        check=True,
    )
    subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "evaluate_synthetic_detector.py"),
         "--input", str(data_dir), "--output", str(report_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["observation_rows"] == 540
    assert report["ground_truth_group_weeks"] == 360
    assert set(report["domains"]) == {"community", "workforce"}
    for metrics in report["domains"].values():
        assert metrics["group_weeks"] == 180
        assert metrics["true_positive"] + metrics["false_negative"] == 3
        assert 0.0 <= metrics["precision"] <= 1.0
        assert 0.0 <= metrics["recall"] <= 1.0
        assert 0.0 <= metrics["f1"] <= 1.0

# Evaluation protocol

## Dataset

The generator uses a fixed random seed and inserts known anomalous periods.
Ground-truth labels are retained in a separate evaluation manifest, not exposed
to the detector as input features.

## Split

Use chronological partitions:
- historical warm-up period,
- calibration period,
- held-out evaluation period.

Do not randomly split time-series rows. Prevent future information from entering
the baseline.

## Metrics

- Precision = TP / (TP + FP)
- Recall = TP / (TP + FN)
- F1 = 2 * precision * recall / (precision + recall)
- False alerts per group-week.
- Detection delay from planted anomaly onset to first detection.
- Data completeness and rejected-row rate.

Report community and workforce metrics separately. Synthetic benchmark results
do not establish clinical validity or real-world outbreak detection performance.

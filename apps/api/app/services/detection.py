from dataclasses import dataclass
from statistics import median
from typing import Sequence

@dataclass(frozen=True)
class Detection:
    baseline: float | None
    anomaly_score: float | None
    is_candidate: bool
    reason: str

def robust_anomaly(values: Sequence[float], current: float,
                   min_history: int = 6, threshold: float = 3.5) -> Detection:
    """Robust historical deviation detector; not a clinical/outbreak predictor."""
    history = [float(v) for v in values]
    if len(history) < min_history:
        return Detection(None, None, False, "insufficient_history")
    center = median(history)
    deviations = [abs(v - center) for v in history]
    mad = median(deviations)
    if mad == 0:
        # A zero MAD makes the robust score undefined. Do not fabricate certainty.
        if current == center:
            return Detection(center, 0.0, False, "stable_zero_variance_baseline")
        return Detection(center, None, False, "zero_mad_requires_review")
    robust_sigma = 1.4826 * mad
    score = (float(current) - center) / robust_sigma
    candidate = score >= threshold
    reason = "unusual_increase" if candidate else "within_threshold"
    return Detection(center, round(score, 4), candidate, reason)

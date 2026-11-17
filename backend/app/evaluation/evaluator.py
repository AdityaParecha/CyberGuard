"""
Measures CyberGuard's rule-based log detector against the hand-labelled
benchmark in log_benchmark.py.

Metrics:
- accuracy: share of lines whose predicted label (event type or "none")
  exactly matches the ground truth.
- precision / recall / F1: macro-averaged over the event types (a class that
  is never predicted gets precision 0), so every event type counts equally.
- confusion matrix: event detection as a two-class problem
  (line records an event vs. routine line).

The result does not depend on any single investigation; it describes how well
the detector that produces log evidence performs on known answers.
"""

from functools import lru_cache
from typing import Any

from backend.app.evaluation.log_benchmark import BENCHMARK, EVENT_LABELS, NO_EVENT
from backend.app.tools.log_tools import analyze_logs


def _predict(line: str) -> str:
    events = analyze_logs(line)
    return events[0]["event_type"] if events else NO_EVENT


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


@lru_cache(maxsize=1)
def evaluate_log_detector() -> dict[str, Any]:
    truths = [label for _, label in BENCHMARK]
    preds = [_predict(line) for line, _ in BENCHMARK]
    total = len(BENCHMARK)

    per_class = []
    for label in EVENT_LABELS:
        tp = sum(1 for t, p in zip(truths, preds) if t == label and p == label)
        fp = sum(1 for t, p in zip(truths, preds) if t != label and p == label)
        fn = sum(1 for t, p in zip(truths, preds) if t == label and p != label)
        precision = _ratio(tp, tp + fp)
        recall = _ratio(tp, tp + fn)
        f1 = _ratio(2 * precision * recall, precision + recall)
        per_class.append({
            "label": label,
            "support": tp + fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
        })

    scored = [c for c in per_class if c["support"] > 0]
    macro = lambda key: round(sum(c[key] for c in scored) / len(scored), 4)  # noqa: E731

    is_event = [t != NO_EVENT for t in truths]
    flagged = [p != NO_EVENT for p in preds]
    confusion = {
        "tp": sum(1 for e, f in zip(is_event, flagged) if e and f),
        "fp": sum(1 for e, f in zip(is_event, flagged) if not e and f),
        "fn": sum(1 for e, f in zip(is_event, flagged) if e and not f),
        "tn": sum(1 for e, f in zip(is_event, flagged) if not e and not f),
    }

    errors = [
        {"line": line, "expected": t, "predicted": p}
        for (line, t), p in zip(BENCHMARK, preds)
        if t != p
    ]

    return {
        "accuracy": round(_ratio(sum(t == p for t, p in zip(truths, preds)), total), 4),
        "precision": macro("precision"),
        "recall": macro("recall"),
        "f1_score": macro("f1_score"),
        "averaging": f"macro over {len(scored)} event types",
        "confusion_matrix": confusion,
        "confusion_matrix_label": "Event detection (security event vs. routine line)",
        "per_class": per_class,
        "misclassified": errors,
        "dataset": {
            "name": "CyberGuard hand-labelled log benchmark",
            "size": total,
            "event_lines": sum(is_event),
            "routine_lines": total - sum(is_event),
        },
        "scope": (
            "Measured for the rule-based log detector (Log Analyst) on a "
            f"hand-labelled benchmark of {total} log lines with known answers. "
            "These are not scores for this particular investigation, which "
            "has no ground truth, and they do not grade AI-written notes."
        ),
    }

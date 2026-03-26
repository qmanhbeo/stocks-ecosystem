"""Baseline supervised models and evaluation helpers."""

from __future__ import annotations

from typing import Dict, Iterable, Optional

import numpy as np


def build_logistic_regression_pipeline(random_state: int):
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise ImportError(
            "scikit-learn is required for supervised_label baseline training. Install requirements.txt first."
        ) from exc

    return Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=1000,
                    random_state=random_state,
                ),
            ),
        ]
    )


def compute_metrics(y_true: Iterable[int], y_pred: Iterable[int], y_prob: Optional[Iterable[float]] = None) -> Dict[str, Optional[float]]:
    try:
        from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
    except ImportError as exc:
        raise ImportError(
            "scikit-learn is required for supervised_label metrics. Install requirements.txt first."
        ) from exc

    y_true = np.asarray(list(y_true), dtype=int)
    y_pred = np.asarray(list(y_pred), dtype=int)
    result: Dict[str, Optional[float]] = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": None,
    }
    if y_prob is not None and len(np.unique(y_true)) > 1:
        result["roc_auc"] = float(roc_auc_score(y_true, np.asarray(list(y_prob), dtype=float)))
    return result


def label_distribution(y_true: Iterable[int]) -> Dict[str, int]:
    labels = np.asarray(list(y_true), dtype=int)
    return {
        "count": int(labels.size),
        "positive": int((labels == 1).sum()),
        "negative": int((labels == 0).sum()),
    }

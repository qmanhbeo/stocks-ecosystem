from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, roc_auc_score
from scipy.stats import binomtest
import numpy as np
import pandas as pd
from typing import Dict


def evaluate_model(y_true: pd.Series, y_pred: np.ndarray, y_prob: np.ndarray = None) -> Dict[str, float]:
    """
    y_true : actual values (continuous returns OR binary 0/1)
    y_pred : predicted values (continuous OR binary 0/1 from classifier)
    y_prob : predicted probabilities for class 1 (only for classifiers; enables AUC)
    """
    """
    Calculates evaluation metrics.

    Key metrics for signal detection:
      - direction_accuracy : fraction of correct up/down predictions
      - naive_dir_acc      : fraction of positive actual returns ("always up" baseline)
      - edge_over_naive    : direction_accuracy - naive_dir_acc  ← THE REAL SIGNAL
      - dir_pvalue         : p-value vs 50% (is model better than coin flip?)
      - dir_pvalue_vs_naive: p-value vs naive drift  ← THE REAL SIGNIFICANCE TEST
    """
    y_true_arr = np.array(y_true)

    metrics = {
        "mae": float(mean_absolute_error(y_true_arr, y_pred)),
        "mse": float(mean_squared_error(y_true_arr, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true_arr, y_pred))),
        "r2": float(r2_score(y_true_arr, y_pred)),
    }

    direction_match = (y_pred > 0) == (y_true_arr > 0)
    n = len(direction_match)
    n_correct = int(direction_match.sum())
    dir_acc = float(n_correct / n)
    naive_dir_acc = float((y_true_arr > 0).mean())

    metrics["direction_accuracy"] = dir_acc
    metrics["naive_dir_acc"] = naive_dir_acc
    metrics["edge_over_naive"] = round(dir_acc - naive_dir_acc, 4)

    # Significance vs 50%: is model beating a coin flip?
    metrics["dir_pvalue"] = float(
        binomtest(n_correct, n, p=0.5, alternative="greater").pvalue
    )

    # Significance vs naive drift: is model beating "always predict up"?
    # This is the REAL test — FPT has a strong upward bias that inflates raw dir_acc.
    naive_rate = max(naive_dir_acc, 0.001)  # guard against 0 or 1
    naive_rate = min(naive_rate, 0.999)
    metrics["dir_pvalue_vs_naive"] = float(
        binomtest(n_correct, n, p=naive_rate, alternative="greater").pvalue
    )

    # AUC: only meaningful when probability scores are available (classifiers)
    if y_prob is not None:
        try:
            metrics["auc"] = float(roc_auc_score(y_true_arr > 0, y_prob))
        except Exception:
            metrics["auc"] = float("nan")
    else:
        metrics["auc"] = float("nan")

    return metrics

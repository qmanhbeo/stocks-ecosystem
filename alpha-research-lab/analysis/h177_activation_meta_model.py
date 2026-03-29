"""
H177: Compact activation meta-model.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.activation_meta_experiment_utils import (
    add_common_args,
    load_meta_bundle,
    run_and_persist_activation_experiment,
    selector_confidence_series,
    selector_entry_quality_series,
    selector_prefix,
    thresholded_three_state_schedule,
    walk_forward_logistic_scores,
)


def parse_args() -> argparse.Namespace:
    parser = add_common_args(argparse.ArgumentParser())
    parser.add_argument("--min-train-years", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inputs, meta_state, meta_source = load_meta_bundle(args)
    gates_by_selector: dict[str, dict[str, pd.Series]] = {}
    feature_manifest: dict[str, list[str]] = {}
    for selector in inputs.selectors:
        prefix = selector_prefix(selector)
        work = meta_state[["time"]].copy()
        work["recent_rel3"] = pd.to_numeric(meta_state[f"{prefix}_recent_cycle_relative_return_ewm3"], errors="coerce")
        work["recent_rel5"] = pd.to_numeric(meta_state[f"{prefix}_recent_cycle_relative_return_ewm5"], errors="coerce")
        work["recent_hit5"] = pd.to_numeric(meta_state[f"{prefix}_recent_hit_rate_ewm5"], errors="coerce")
        work["recent_turnover3"] = pd.to_numeric(meta_state[f"{prefix}_recent_turnover_ewm3"], errors="coerce")
        work["recent_cash3"] = pd.to_numeric(meta_state[f"{prefix}_recent_cash_weight_ewm3"], errors="coerce")
        work["recent_blocked3"] = pd.to_numeric(meta_state[f"{prefix}_recent_blocked_buy_ewm3"], errors="coerce")
        work["selector_drawdown"] = pd.to_numeric(meta_state[f"{prefix}_selector_drawdown"], errors="coerce")
        work["selector_confidence"] = selector_confidence_series(meta_state, prefix=prefix)
        work["selector_entry_quality"] = selector_entry_quality_series(meta_state, prefix=prefix)
        work["target"] = (pd.to_numeric(meta_state[f"{prefix}_future_cycle_relative_return"], errors="coerce") > 0.0).astype(float)
        feature_columns = [
            "recent_rel3",
            "recent_rel5",
            "recent_hit5",
            "recent_turnover3",
            "recent_cash3",
            "recent_blocked3",
            "selector_drawdown",
            "selector_confidence",
            "selector_entry_quality",
        ]
        feature_manifest[selector.name] = list(feature_columns)
        prob = walk_forward_logistic_scores(
            work,
            feature_columns=feature_columns,
            target_column="target",
            min_train_years=int(args.min_train_years),
        ).fillna(0.5)
        gates_by_selector[selector.name] = {
            "h177__prob_ge55": prob >= 0.55,
            "h177__prob_ge60": prob >= 0.60,
            "h177__prob_45_60": thresholded_three_state_schedule(prob, low_threshold=0.45, high_threshold=0.60),
            "h177__prob_50_65": thresholded_three_state_schedule(prob, low_threshold=0.50, high_threshold=0.65),
            "h177__prob_direct": prob.clip(0.0, 1.0),
        }

    run_and_persist_activation_experiment(
        args=args,
        inputs=inputs,
        meta_state=meta_state,
        meta_source=meta_source,
        gates_by_selector=gates_by_selector,
        mode="portfolio_activation_meta_model",
        name="h177_activation_meta_model",
        stem="h177_activation_meta_model",
        title="H177: ACTIVATION META-MODEL",
        extra_summary={
            "hypothesis": "a compact walk-forward logistic meta-model can learn activation alpha from selector-efficacy state",
            "feature_manifest": feature_manifest,
        },
        metadata_extra={"min_train_years": int(args.min_train_years)},
    )


if __name__ == "__main__":
    main()

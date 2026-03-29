"""
H180: Small augmentations around the H175 rel2_gt0 champion.

Purpose:
- test only local refinements around the fixed rel2_gt0 activation rule
- avoid reopening broad activation-family search
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
    quantile_gate,
    run_and_persist_activation_experiment,
    selector_confidence_series,
    selector_entry_quality_series,
    selector_prefix,
    selector_recent_hit_rate_ewm,
    selector_recent_relative_ewm_from_prev,
)


def parse_args() -> argparse.Namespace:
    return add_common_args(argparse.ArgumentParser()).parse_args()


def _build_selector_gates(meta_state: pd.DataFrame, *, prefix: str) -> dict[str, pd.Series]:
    rel2 = selector_recent_relative_ewm_from_prev(meta_state, prefix=prefix, span=2)
    hit3 = selector_recent_hit_rate_ewm(meta_state, prefix=prefix, span=3)
    hit5 = selector_recent_hit_rate_ewm(meta_state, prefix=prefix, span=5)
    confidence = selector_confidence_series(meta_state, prefix=prefix)
    entry_quality = selector_entry_quality_series(meta_state, prefix=prefix)
    drawdown = pd.to_numeric(meta_state[f"{prefix}_selector_drawdown"], errors="coerce")
    blocked3 = pd.to_numeric(meta_state[f"{prefix}_recent_blocked_buy_ewm3"], errors="coerce")

    base = rel2 > 0.0
    low_blocked = ~quantile_gate(blocked3, 0.70, operator=">=")
    return {
        "h175__rel2_gt0": base,
        "h180__rel2_gt0_hit5_ge50": base & (hit5 >= 0.50),
        "h180__rel2_gt0_hit5_ge55": base & (hit5 >= 0.55),
        "h180__rel2_gt0_hit3_ge55": base & (hit3 >= 0.55),
        "h180__rel2_gt0_conf_q50": base & quantile_gate(confidence, 0.50),
        "h180__rel2_gt0_conf_q60": base & quantile_gate(confidence, 0.60),
        "h180__rel2_gt0_entry_q50": base & quantile_gate(entry_quality, 0.50),
        "h180__rel2_gt0_entry_q60": base & quantile_gate(entry_quality, 0.60),
        "h180__rel2_gt0_drawdown_gt_m10": base & (drawdown > -0.10),
        "h180__rel2_gt0_hit5_ge50_conf_q50": base & (hit5 >= 0.50) & quantile_gate(confidence, 0.50),
        "h180__rel2_gt0_hit5_ge50_low_blocked": base & (hit5 >= 0.50) & low_blocked,
    }


def main() -> None:
    args = parse_args()
    inputs, meta_state, meta_source = load_meta_bundle(args)

    gates_by_selector: dict[str, dict[str, pd.Series]] = {}
    for selector in inputs.selectors:
        prefix = selector_prefix(selector)
        if selector.name == "full_library_k5_r5_eq":
            gates_by_selector[selector.name] = _build_selector_gates(meta_state, prefix=prefix)
        else:
            gates_by_selector[selector.name] = {}

    results, _ = run_and_persist_activation_experiment(
        args=args,
        inputs=inputs,
        meta_state=meta_state,
        meta_source=meta_source,
        gates_by_selector=gates_by_selector,
        mode="portfolio_activation_h175_small_augmentations",
        name="h180_h175_small_augmentations",
        stem="h180_h175_small_augmentations",
        title="H180: H175 SMALL AUGMENTATIONS",
    )

    full_rows = results.loc[results["selector_name"] == "full_library_k5_r5_eq"].reset_index(drop=True)
    base_row = full_rows.loc[full_rows["gate_name"] == "h175__rel2_gt0"].head(1)
    base_rel = float(base_row.iloc[0]["relative_total_return"]) if not base_row.empty else None
    base_ir = float(base_row.iloc[0]["information_ratio_annualized"] or 0.0) if not base_row.empty else None
    best_augmented = full_rows.loc[full_rows["gate_name"].str.startswith("h180__", na=False)].head(1)
    if not best_augmented.empty:
        print("\nBest augmentation vs base:")
        row = best_augmented.iloc[0]
        print(
            {
                "gate_name": row["gate_name"],
                "relative_total_return": float(row["relative_total_return"]),
                "information_ratio_annualized": float(row["information_ratio_annualized"] or 0.0),
                "delta_relative_vs_h175": None if base_rel is None else float(row["relative_total_return"] - base_rel),
                "delta_ir_vs_h175": None if base_ir is None else float((row["information_ratio_annualized"] or 0.0) - base_ir),
            }
        )


if __name__ == "__main__":
    main()

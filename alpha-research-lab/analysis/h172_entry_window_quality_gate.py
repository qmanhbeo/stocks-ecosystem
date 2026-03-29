"""
H172: Entry-window quality predicts cycle quality.
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
    selector_entry_quality_series,
    selector_prefix,
)


def parse_args() -> argparse.Namespace:
    parser = add_common_args(argparse.ArgumentParser())
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inputs, meta_state, meta_source = load_meta_bundle(args)
    gates_by_selector: dict[str, dict[str, pd.Series]] = {}
    for selector in inputs.selectors:
        prefix = selector_prefix(selector)
        entry_quality = selector_entry_quality_series(meta_state, prefix=prefix)
        mean_clv = meta_state[f"{prefix}_top5_mean_clv"]
        tv_rank = meta_state[f"{prefix}_top5_mean_tv_to_adv20_rank"]
        buyable = meta_state[f"{prefix}_top5_buyable_count"]
        gates_by_selector[selector.name] = {
            "entry__quality_q60": quantile_gate(entry_quality, 0.60),
            "entry__quality_q70": quantile_gate(entry_quality, 0.70),
            "entry__clv_q60": quantile_gate(mean_clv, 0.60),
            "entry__tv_rank_q60": quantile_gate(tv_rank, 0.60),
            "entry__quality_q60_buyable_ge4": quantile_gate(entry_quality, 0.60) & (buyable >= 4.0),
            "entry__clv_q60_tv_q60": quantile_gate(mean_clv, 0.60) & quantile_gate(tv_rank, 0.60),
        }

    run_and_persist_activation_experiment(
        args=args,
        inputs=inputs,
        meta_state=meta_state,
        meta_source=meta_source,
        gates_by_selector=gates_by_selector,
        mode="portfolio_activation_entry_window_quality",
        name="h172_entry_window_quality_gate",
        stem="h172_entry_window_quality_gate",
        title="H172: ENTRY WINDOW QUALITY",
        extra_summary={"hypothesis": "entry-window quality predicts next-cycle selector quality"},
    )


if __name__ == "__main__":
    main()

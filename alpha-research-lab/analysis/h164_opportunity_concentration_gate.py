"""
H164: Cross-sectional opportunity concentration predicts next-cycle edge.
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
        spread = meta_state[f"{prefix}_top1_minus_top5_spread"]
        score_std = meta_state[f"{prefix}_top5_score_std"]
        entropy = meta_state[f"{prefix}_top10_score_entropy"]
        stability = meta_state[f"{prefix}_top5_prev_overlap_ratio"]
        gates_by_selector[selector.name] = {
            "conc__spread_q60": quantile_gate(spread, 0.60),
            "conc__spread_q70": quantile_gate(spread, 0.70),
            "conc__std_q60": quantile_gate(score_std, 0.60),
            "conc__low_entropy_q40": quantile_gate(entropy, 0.40, operator="<="),
            "conc__spread_q60_low_entropy_q40": quantile_gate(spread, 0.60) & quantile_gate(entropy, 0.40, operator="<="),
            "conc__spread_q60_stable_q60": quantile_gate(spread, 0.60) & quantile_gate(stability, 0.60),
        }

    run_and_persist_activation_experiment(
        args=args,
        inputs=inputs,
        meta_state=meta_state,
        meta_source=meta_source,
        gates_by_selector=gates_by_selector,
        mode="portfolio_activation_opportunity_concentration",
        name="h164_opportunity_concentration_gate",
        stem="h164_opportunity_concentration_gate",
        title="H164: OPPORTUNITY CONCENTRATION",
        extra_summary={"hypothesis": "opportunity concentration predicts next-cycle edge"},
    )


if __name__ == "__main__":
    main()

"""
H176: Turn H170 into 3-state exposure sizing.
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
    pct_rank,
    run_and_persist_activation_experiment,
    selector_prefix,
    thresholded_three_state_schedule,
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
        rel3 = pd.to_numeric(meta_state[f"{prefix}_recent_cycle_relative_return_ewm3"], errors="coerce")
        rel5 = pd.to_numeric(meta_state[f"{prefix}_recent_cycle_relative_return_ewm5"], errors="coerce")
        hit5 = pd.to_numeric(meta_state[f"{prefix}_recent_hit_rate_ewm5"], errors="coerce")
        blend = (pct_rank(rel3) + pct_rank(rel5) + hit5.fillna(0.5).clip(0.0, 1.0)) / 3.0
        gates_by_selector[selector.name] = {
            "h176__rel3_m01_p01": thresholded_three_state_schedule(rel3, low_threshold=-0.01, high_threshold=0.01),
            "h176__rel3_0_p01": thresholded_three_state_schedule(rel3, low_threshold=0.0, high_threshold=0.01),
            "h176__rel5_0_p01": thresholded_three_state_schedule(rel5, low_threshold=0.0, high_threshold=0.01),
            "h176__hit5_50_60": thresholded_three_state_schedule(hit5, low_threshold=0.50, high_threshold=0.60),
            "h176__blend_50_70": thresholded_three_state_schedule(blend, low_threshold=0.50, high_threshold=0.70),
            "h176__blend_55_75": thresholded_three_state_schedule(blend, low_threshold=0.55, high_threshold=0.75),
        }

    run_and_persist_activation_experiment(
        args=args,
        inputs=inputs,
        meta_state=meta_state,
        meta_source=meta_source,
        gates_by_selector=gates_by_selector,
        mode="portfolio_activation_h170_three_state_sizing",
        name="h176_h170_three_state_sizing",
        stem="h176_h170_three_state_sizing",
        title="H176: H170 THREE-STATE SIZING",
        extra_summary={"hypothesis": "smoothed selector efficacy is stronger as off/half/full sizing than binary activation"},
    )


if __name__ == "__main__":
    main()

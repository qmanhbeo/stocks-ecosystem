"""
H170: Recent selector edge has regime persistence, but only as a smoothed state.
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

from src.activation_meta_experiment_utils import add_common_args, load_meta_bundle, quantile_gate, run_and_persist_activation_experiment, selector_prefix


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
        turnover5 = pd.to_numeric(meta_state[f"{prefix}_recent_turnover_ewm5"], errors="coerce")
        gates_by_selector[selector.name] = {
            "recentsm__rel3_gt0": rel3 > 0.0,
            "recentsm__rel5_gt0": rel5 > 0.0,
            "recentsm__rel3_gt_m01": rel3 > -0.01,
            "recentsm__hit5_ge55": hit5 >= 0.55,
            "recentsm__rel3_q60_hit5_ge55": quantile_gate(rel3, 0.60) & (hit5 >= 0.55),
            "recentsm__rel5_gt0_turnover_q60": (rel5 > 0.0) & quantile_gate(turnover5, 0.60, operator="<="),
        }

    run_and_persist_activation_experiment(
        args=args,
        inputs=inputs,
        meta_state=meta_state,
        meta_source=meta_source,
        gates_by_selector=gates_by_selector,
        mode="portfolio_activation_smoothed_recent_efficacy",
        name="h170_smoothed_recent_efficacy_gate",
        stem="h170_smoothed_recent_efficacy_gate",
        title="H170: SMOOTHED RECENT EFFICACY",
        extra_summary={"hypothesis": "smoothed recent selector efficacy is more informative than one-cycle cooldowns"},
    )


if __name__ == "__main__":
    main()

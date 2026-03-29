"""
H169: Cross-sectional breadth collapse is a hidden risk-off for stock picking.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.activation_meta_experiment_utils import add_common_args, load_meta_bundle, quantile_gate, run_and_persist_activation_experiment


def parse_args() -> argparse.Namespace:
    parser = add_common_args(argparse.ArgumentParser())
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inputs, meta_state, meta_source = load_meta_bundle(args)

    buyable_q40 = quantile_gate(meta_state["buyable_breadth_all"], 0.40)
    liq_q40 = quantile_gate(meta_state["liq_open_breadth_all"], 0.40)
    full_buyable_ge7 = meta_state["full_top10_buyable_count"] >= 7.0
    full_liq_ge2 = meta_state["full_top10_liq_open_count"] >= 2.0
    shared_gates = {
        "breadth__buyable_q40": buyable_q40,
        "breadth__liq_q40": liq_q40,
        "breadth__buyable_ge7": full_buyable_ge7,
        "breadth__liq_ge2": full_liq_ge2,
        "breadth__buyable_ge7_liq_ge2": full_buyable_ge7 & full_liq_ge2,
        "breadth__broad_not_collapsing": buyable_q40 & liq_q40 & (meta_state["full_top5_blocked_buy_count"] <= 1.0),
    }
    gates_by_selector = {selector.name: shared_gates for selector in inputs.selectors}

    run_and_persist_activation_experiment(
        args=args,
        inputs=inputs,
        meta_state=meta_state,
        meta_source=meta_source,
        gates_by_selector=gates_by_selector,
        mode="portfolio_activation_breadth_collapse",
        name="h169_breadth_collapse_gate",
        stem="h169_breadth_collapse_gate",
        title="H169: BREADTH COLLAPSE GATES",
        extra_summary={"hypothesis": "stock-picking alpha decays when effective breadth collapses"},
    )


if __name__ == "__main__":
    main()

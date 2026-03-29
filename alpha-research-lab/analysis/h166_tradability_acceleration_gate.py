"""
H166: Tradability acceleration matters more than tradability level.
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

from src.activation_meta_experiment_utils import add_common_args, load_meta_bundle, quantile_gate, run_and_persist_activation_experiment


def parse_args() -> argparse.Namespace:
    parser = add_common_args(argparse.ArgumentParser())
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inputs, meta_state, meta_source = load_meta_bundle(args)

    shared_gates = {
        "tradacc__buyable_up_1d": pd.to_numeric(meta_state["delta_full_top10_buyable_count_1d"], errors="coerce") > 0.0,
        "tradacc__liq_open_up_1d": pd.to_numeric(meta_state["delta_full_top10_liq_open_count_1d"], errors="coerce") > 0.0,
        "tradacc__liq_breadth_delta_q60": quantile_gate(meta_state["delta_liq_open_breadth_all_1d"], 0.60),
        "tradacc__buyable_and_liq_up": (
            pd.to_numeric(meta_state["delta_full_top10_buyable_count_1d"], errors="coerce") > 0.0
        ) & (
            pd.to_numeric(meta_state["delta_full_top10_liq_open_count_1d"], errors="coerce") > 0.0
        ),
        "tradacc__liq_5d_q60": quantile_gate(meta_state["delta_liq_open_breadth_all_5d"], 0.60),
        "tradacc__liq_up_and_level_q60": quantile_gate(meta_state["delta_liq_open_breadth_all_1d"], 0.60) & quantile_gate(meta_state["liq_open_breadth_all"], 0.60),
    }
    gates_by_selector = {selector.name: shared_gates for selector in inputs.selectors}

    run_and_persist_activation_experiment(
        args=args,
        inputs=inputs,
        meta_state=meta_state,
        meta_source=meta_source,
        gates_by_selector=gates_by_selector,
        mode="portfolio_activation_tradability_acceleration",
        name="h166_tradability_acceleration_gate",
        stem="h166_tradability_acceleration_gate",
        title="H166: TRADABILITY ACCELERATION",
        extra_summary={"hypothesis": "change in deployability matters more than deployability level"},
    )


if __name__ == "__main__":
    main()

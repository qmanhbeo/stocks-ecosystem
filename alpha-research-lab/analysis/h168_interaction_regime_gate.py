"""
H168: Market regime works only interacted with selector state.
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
    selector_prefix,
)


def parse_args() -> argparse.Namespace:
    parser = add_common_args(argparse.ArgumentParser())
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inputs, meta_state, meta_source = load_meta_bundle(args)
    low_vol = quantile_gate(meta_state["vni_realized_vol_20d"], 0.60, operator="<=")
    risk_on = pd.to_numeric(meta_state["credit_risk_on"], errors="coerce") >= 2.0
    above_ma20 = pd.to_numeric(meta_state["vni_above_ma20"], errors="coerce") >= 1.0
    liq_breadth_high = quantile_gate(meta_state["liq_open_breadth_all"], 0.60)
    gates_by_selector: dict[str, dict[str, pd.Series]] = {}
    for selector in inputs.selectors:
        prefix = selector_prefix(selector)
        confidence = quantile_gate(selector_confidence_series(meta_state, prefix=prefix), 0.60)
        recent = quantile_gate(meta_state[f"{prefix}_recent_cycle_relative_return_ewm3"], 0.60)
        gates_by_selector[selector.name] = {
            "inter__conf_q60_above_ma20": confidence & above_ma20,
            "inter__conf_q60_risk_on": confidence & risk_on,
            "inter__conf_q60_low_vol": confidence & low_vol,
            "inter__recent_q60_low_vol": recent & low_vol,
            "inter__conf_q60_liq_q60_above_ma20": confidence & liq_breadth_high & above_ma20,
        }

    run_and_persist_activation_experiment(
        args=args,
        inputs=inputs,
        meta_state=meta_state,
        meta_source=meta_source,
        gates_by_selector=gates_by_selector,
        mode="portfolio_activation_interaction_regime",
        name="h168_interaction_regime_gate",
        stem="h168_interaction_regime_gate",
        title="H168: INTERACTION REGIME GATES",
        extra_summary={"hypothesis": "market regime only helps when interacted with selector state"},
    )


if __name__ == "__main__":
    main()

"""
H173: Selector-specific activation beats global activation.
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
    global_gate = {
        "spec__global_conf_liq_mkt": (
            quantile_gate(meta_state["selector_confidence_combo"], 0.60)
            & quantile_gate(meta_state["liq_open_breadth_all"], 0.60)
            & (pd.to_numeric(meta_state["vni_above_ma20"], errors="coerce") >= 1.0)
        )
    }
    gates_by_selector: dict[str, dict[str, pd.Series]] = {}
    for selector in inputs.selectors:
        prefix = selector_prefix(selector)
        confidence = quantile_gate(selector_confidence_series(meta_state, prefix=prefix), 0.60)
        if prefix == "full":
            selector_specific = {
                "spec__selector_specific": confidence & quantile_gate(meta_state["liq_open_breadth_all"], 0.60),
                **global_gate,
            }
        else:
            selector_specific = {
                "spec__selector_specific": confidence & quantile_gate(meta_state[f"{prefix}_recent_cycle_relative_return_ewm3"], 0.60),
                **global_gate,
            }
        gates_by_selector[selector.name] = selector_specific

    run_and_persist_activation_experiment(
        args=args,
        inputs=inputs,
        meta_state=meta_state,
        meta_source=meta_source,
        gates_by_selector=gates_by_selector,
        mode="portfolio_activation_selector_specific",
        name="h173_selector_specific_activation",
        stem="h173_selector_specific_activation",
        title="H173: SELECTOR-SPECIFIC ACTIVATION",
        extra_summary={"hypothesis": "selector-specific activation logic beats one universal activation rule"},
    )


if __name__ == "__main__":
    main()

"""
H174: Exposure should be triggered by opportunity streaks, not single-day states.
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
    hysteresis_schedule,
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
    gates_by_selector: dict[str, dict[str, pd.Series]] = {}
    liq_high = quantile_gate(meta_state["liq_open_breadth_all"], 0.60)
    for selector in inputs.selectors:
        prefix = selector_prefix(selector)
        strong = quantile_gate(selector_confidence_series(meta_state, prefix=prefix), 0.60) & liq_high
        weak = (
            pd.to_numeric(meta_state[f"{prefix}_recent_cycle_relative_return_ewm3"], errors="coerce") < -0.02
        ) | (
            pd.to_numeric(meta_state[f"{prefix}_selector_drawdown"], errors="coerce") < -0.10
        )
        gates_by_selector[selector.name] = {
            "streak__on2_off2": hysteresis_schedule(strong, weak, on_streak=2, off_streak=2),
            "streak__on3_off2": hysteresis_schedule(strong, weak, on_streak=3, off_streak=2),
            "streak__on2_off1": hysteresis_schedule(strong, weak, on_streak=2, off_streak=1),
            "streak__half_default_on2off2": hysteresis_schedule(
                strong,
                weak,
                on_streak=2,
                off_streak=2,
                on_scale=1.0,
                off_scale=0.5,
            ),
        }

    run_and_persist_activation_experiment(
        args=args,
        inputs=inputs,
        meta_state=meta_state,
        meta_source=meta_source,
        gates_by_selector=gates_by_selector,
        mode="portfolio_activation_hysteresis",
        name="h174_hysteresis_activation",
        stem="h174_hysteresis_activation",
        title="H174: HYSTERESIS / OPPORTUNITY STREAKS",
        extra_summary={"hypothesis": "opportunity streaks and hysteresis reduce activation whipsaw"},
    )


if __name__ == "__main__":
    main()

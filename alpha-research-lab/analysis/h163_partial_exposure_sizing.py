"""
H163: Partial exposure beats binary gating.

Purpose:
- test whether activation alpha lives in 0/50/100 exposure sizing rather than hard on/off

Usage:
    conda run -n stocks python analysis/h163_partial_exposure_sizing.py
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
    selector_confidence_series,
    selector_entry_quality_series,
    selector_prefix,
    three_level_schedule,
)


def parse_args() -> argparse.Namespace:
    parser = add_common_args(argparse.ArgumentParser())
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inputs, meta_state, meta_source = load_meta_bundle(args)

    market_support = (
        pd.to_numeric(meta_state["vni_above_ma20"], errors="coerce").fillna(0.0).clip(0.0, 1.0)
        + (1.0 - pct_rank(meta_state["vni_realized_vol_20d"]))
        + pd.to_numeric(meta_state["liq_open_breadth_all"], errors="coerce").fillna(0.0).clip(0.0, 1.0)
    ) / 3.0

    gates_by_selector: dict[str, dict[str, pd.Series]] = {}
    for selector in inputs.selectors:
        prefix = selector_prefix(selector)
        confidence = selector_confidence_series(meta_state, prefix=prefix)
        entry_quality = selector_entry_quality_series(meta_state, prefix=prefix)
        recent = pd.to_numeric(meta_state[f"{prefix}_recent_cycle_relative_return_ewm3"], errors="coerce").fillna(0.0)
        recent_rank = pct_rank(recent)
        blended = (confidence + entry_quality + market_support + recent_rank) / 4.0
        gates_by_selector[selector.name] = {
            "size__conf_q55_q70": three_level_schedule(confidence, mid_quantile=0.55, high_quantile=0.70),
            "size__entry_q55_q70": three_level_schedule(entry_quality, mid_quantile=0.55, high_quantile=0.70),
            "size__recent_q55_q70": three_level_schedule(recent_rank, mid_quantile=0.55, high_quantile=0.70),
            "size__blend_q55_q70": three_level_schedule(blended, mid_quantile=0.55, high_quantile=0.70),
            "size__blend_q60_q75": three_level_schedule(blended, mid_quantile=0.60, high_quantile=0.75),
        }

    run_and_persist_activation_experiment(
        args=args,
        inputs=inputs,
        meta_state=meta_state,
        meta_source=meta_source,
        gates_by_selector=gates_by_selector,
        mode="portfolio_activation_partial_exposure",
        name="h163_partial_exposure_sizing",
        stem="h163_partial_exposure_sizing",
        title="H163: PARTIAL EXPOSURE SIZING",
        extra_summary={"hypothesis": "partial exposure sizing beats binary gating"},
    )


if __name__ == "__main__":
    main()

"""
H171: Drawdown phase of the selector itself predicts recovery vs decay.
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
        drawdown = pd.to_numeric(meta_state[f"{prefix}_selector_drawdown"], errors="coerce")
        days_in_dd = pd.to_numeric(meta_state[f"{prefix}_days_in_drawdown"], errors="coerce")
        recovery = pd.to_numeric(meta_state[f"{prefix}_recovery_from_20d_trough"], errors="coerce")
        gates_by_selector[selector.name] = {
            "dd__gt_m05": drawdown > -0.05,
            "dd__gt_m10": drawdown > -0.10,
            "dd__shallow_short": (drawdown > -0.10) & (days_in_dd <= 10.0),
            "dd__recovery_phase": (drawdown <= -0.03) & (drawdown > -0.15) & (recovery > 0.02),
            "dd__recovery_phase_short": (drawdown <= -0.03) & (drawdown > -0.15) & (recovery > 0.02) & (days_in_dd <= 20.0),
        }

    run_and_persist_activation_experiment(
        args=args,
        inputs=inputs,
        meta_state=meta_state,
        meta_source=meta_source,
        gates_by_selector=gates_by_selector,
        mode="portfolio_activation_drawdown_phase",
        name="h171_selector_drawdown_phase_gate",
        stem="h171_selector_drawdown_phase_gate",
        title="H171: SELECTOR DRAWDOWN PHASE",
        extra_summary={"hypothesis": "selector drawdown phase can distinguish recovery from decay"},
    )


if __name__ == "__main__":
    main()

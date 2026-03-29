"""
H167: Selector fragility shows up in recent implementation pain.
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
        blocked = meta_state[f"{prefix}_recent_blocked_buy_ewm3"]
        cash = meta_state[f"{prefix}_recent_cash_weight_ewm3"]
        turnover = meta_state[f"{prefix}_recent_turnover_ewm3"]
        holding_age = meta_state[f"{prefix}_recent_holding_age_ewm3"]
        low_pain = quantile_gate(blocked, 0.40, operator="<=") & quantile_gate(cash, 0.40, operator="<=")
        gates_by_selector[selector.name] = {
            "frag__blocked_low_q40": quantile_gate(blocked, 0.40, operator="<="),
            "frag__cash_low_q40": quantile_gate(cash, 0.40, operator="<="),
            "frag__turnover_mid_q60": quantile_gate(turnover, 0.60, operator="<="),
            "frag__low_pain_combo": low_pain & quantile_gate(turnover, 0.60, operator="<="),
            "frag__low_pain_low_age": low_pain & quantile_gate(holding_age, 0.60, operator="<="),
        }

    run_and_persist_activation_experiment(
        args=args,
        inputs=inputs,
        meta_state=meta_state,
        meta_source=meta_source,
        gates_by_selector=gates_by_selector,
        mode="portfolio_activation_selector_fragility",
        name="h167_selector_fragility_gate",
        stem="h167_selector_fragility_gate",
        title="H167: SELECTOR FRAGILITY / IMPLEMENTATION PAIN",
        extra_summary={"hypothesis": "recent implementation pain predicts fragile future cycles"},
    )


if __name__ == "__main__":
    main()

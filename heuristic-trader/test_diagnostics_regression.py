#!/usr/bin/env python3
"""
Permanent regression guardrail: verify diagnostics=True doesn't alter metrics.

This test should PASS consistently to ensure the collect_diagnostics feature
does not change trading behavior or metrics.
"""

import sys
import signals as s
from backtest import simulate_topk_constraint_compliant, load_liquid_lookup, load_trad_lookup, load_price_cache

STRATEGY_WINDOW = {
    "signal": "s1_proba",
    "start": "2024-01-01",
    "end": "2024-12-31",
    "top_k": 5,
    "rebalance_days": 10,
    "min_hold_days": 3,
}


def run_comparison() -> bool:
    """Run diagnostics off/on comparison. Returns True if pass."""
    signal = s.load_rl_signal_matrix(
        start=STRATEGY_WINDOW["start"],
        end=STRATEGY_WINDOW["end"],
        allow_2026=False
    )
    signal_df = signal[["time", "ticker", STRATEGY_WINDOW["signal"]]].copy()
    
    liquid = load_liquid_lookup()
    trad = load_trad_lookup()
    cache = load_price_cache()
    
    result_off = simulate_topk_constraint_compliant(
        signal_df, cache,
        signal_col=STRATEGY_WINDOW["signal"],
        top_k=STRATEGY_WINDOW["top_k"],
        rebalance_days=STRATEGY_WINDOW["rebalance_days"],
        min_hold_days=STRATEGY_WINDOW["min_hold_days"],
        use_filters=True,
        liquid_lookup=liquid,
        trad_lookup=trad,
        collect_diagnostics=False,
    )
    
    result_on = simulate_topk_constraint_compliant(
        signal_df, cache,
        signal_col=STRATEGY_WINDOW["signal"],
        top_k=STRATEGY_WINDOW["top_k"],
        rebalance_days=STRATEGY_WINDOW["rebalance_days"],
        min_hold_days=STRATEGY_WINDOW["min_hold_days"],
        use_filters=True,
        liquid_lookup=liquid,
        trad_lookup=trad,
        collect_diagnostics=True,
    )
    
    fields = ["total_return", "annualized_return", "sharpe", "max_drawdown", "n_trades", "n_filtered"]
    all_match = True
    
    for field in fields:
        off_val = getattr(result_off, field)
        on_val = getattr(result_on, field)
        
        if isinstance(off_val, float):
            match = abs(off_val - on_val) < 1e-9
        else:
            match = off_val == on_val
        
        if not match:
            print(f"FAIL: {field} differs: off={off_val}, on={on_val}")
            all_match = False
    
    curve_off = result_off.curve["portfolio_value"].iloc[-1]
    curve_on = result_on.curve["portfolio_value"].iloc[-1]
    if abs(curve_off - curve_on) >= 1:
        print(f"FAIL: final_value differs: off={curve_off}, on={curve_on}")
        all_match = False
    
    return all_match


def main() -> int:
    print("=" * 60)
    print("DIAGNOSTICS REGRESSION GUARDRAIL")
    print(f"Window: {STRATEGY_WINDOW['start']} to {STRATEGY_WINDOW['end']}")
    print("=" * 60)
    
    success = run_comparison()
    
    if success:
        print("\nPASS: diagnostics on/off metrics are identical")
        return 0
    else:
        print("\nFAIL: metrics differ between diagnostics on/off")
        return 1


if __name__ == "__main__":
    sys.exit(main())
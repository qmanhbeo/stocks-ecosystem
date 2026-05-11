"""
Regression guardrail: ensure execution ablation baseline matches canonical behavior.

Compares:
A. Old/default call (no explicit params)
B. Explicit ablation params: candidate_scan_multiplier=3, sizing_mode="fixed_initial"

Must match exactly (within tiny float tolerance).
"""

import pandas as pd
import numpy as np
import signals as s
import backtest as bt


def run_canonical_with_params(
    signal_name: str,
    top_k: int,
    rebal_days: int,
    candidate_scan_multiplier: int | None = None,
    sizing_mode: str | None = None,
    start: str = "2024-01-01",
    end: str = "2024-12-31",
):
    """Run canonical backtest with optional params."""
    
    signal_df = s.load_rl_signal_matrix(start=start, end=end, allow_2026=False)
    if signal_df is None or len(signal_df) == 0:
        return None
    
    if "blend" in signal_name:
        c16_df = s.load_order_pressure(start=start, end=end)
        c16_df = c16_df[["time", "ticker", "order_volume_ratio_rank"]].copy()
        c16_df["time"] = pd.to_datetime(c16_df["time"], errors="coerce").dt.normalize()
        
        signal_df["time"] = pd.to_datetime(signal_df["time"], errors="coerce").dt.normalize()
        signal_df = signal_df.merge(c16_df, on=["time", "ticker"], how="left")
        
        if "blend" in signal_df.columns:
            signal_df.drop(columns=["blend"], inplace=True)
        
        signal_df["blend"] = signal_df["s1_proba"] * 0.7 + signal_df["order_volume_ratio_rank"] * 0.3
    
    cache = bt.load_price_cache()
    liquid_lookup = bt.load_liquid_lookup()
    trad_lookup = bt.load_trad_lookup()
    
    kwargs = {}
    if candidate_scan_multiplier is not None:
        kwargs["candidate_scan_multiplier"] = candidate_scan_multiplier
    if sizing_mode is not None:
        kwargs["sizing_mode"] = sizing_mode
    
    result = bt.simulate_topk_constraint_compliant(
        signal_df,
        cache,
        signal_col=signal_name,
        top_k=top_k,
        rebalance_days=rebal_days,
        min_hold_days=3,
        initial_capital=1_000_000_000.0,
        liquid_lookup=liquid_lookup,
        trad_lookup=trad_lookup,
        collect_diagnostics=False,
        **kwargs,
    )
    
    return result


def main():
    print("=" * 80)
    print("BASELINE PARITY TEST: Execution Ablation vs Canonical")
    print("=" * 80)
    
    test_cases = [
        ("blend", 5, 10, "blend_70_30_top5"),
        ("s1_proba", 5, 10, "s1_top5_rebal10"),
    ]
    
    all_passed = True
    
    for signal_name, top_k, rebal_days, test_name in test_cases:
        print(f"\n{'='*60}")
        print(f"Test: {test_name}")
        print(f"{'='*60}")
        
        print("\n[A] Running with defaults (no explicit params)...")
        result_a = run_canonical_with_params(
            signal_name, top_k, rebal_days,
            start="2024-01-01", end="2024-12-31",
        )
        
        print("[B] Running with explicit baseline params (scan=3, sizing=fixed_initial)...")
        result_b = run_canonical_with_params(
            signal_name, top_k, rebal_days,
            candidate_scan_multiplier=3,
            sizing_mode="fixed_initial",
            start="2024-01-01", end="2024-12-31",
        )
        
        if result_a is None or result_b is None:
            print("ERROR: One or both results are None")
            all_passed = False
            continue
        
        print(f"\n  [A] total_return: {result_a.total_return:.6f}")
        print(f"  [B] total_return: {result_b.total_return:.6f}")
        print(f"  [A] annualized_return: {result_a.annualized_return:.6f}")
        print(f"  [B] annualized_return: {result_b.annualized_return:.6f}")
        print(f"  [A] sharpe: {result_a.sharpe:.6f}")
        print(f"  [B] sharpe: {result_b.sharpe:.6f}")
        print(f"  [A] max_drawdown: {result_a.max_drawdown:.6f}")
        print(f"  [B] max_drawdown: {result_b.max_drawdown:.6f}")
        print(f"  [A] n_trades: {result_a.n_trades}")
        print(f"  [B] n_trades: {result_b.n_trades}")
        print(f"  [A] n_filtered: {result_a.n_filtered}")
        print(f"  [B] n_filtered: {result_b.n_filtered}")
        
        final_val_a = result_a.curve["portfolio_value"].iloc[-1] if len(result_a.curve) > 0 else 0
        final_val_b = result_b.curve["portfolio_value"].iloc[-1] if len(result_b.curve) > 0 else 0
        print(f"  [A] final_portfolio_value: {final_val_a:.2f}")
        print(f"  [B] final_portfolio_value: {final_val_b:.2f}")
        
        tol = 1e-9
        
        diff_return = abs(result_a.total_return - result_b.total_return)
        diff_ann = abs(result_a.annualized_return - result_b.annualized_return)
        diff_sharpe = abs(result_a.sharpe - result_b.sharpe)
        diff_dd = abs(result_a.max_drawdown - result_b.max_drawdown)
        diff_trades = abs(result_a.n_trades - result_b.n_trades)
        diff_filtered = abs(result_a.n_filtered - result_b.n_filtered)
        diff_final = abs(final_val_a - final_val_b)
        
        passed = (
            diff_return <= tol and
            diff_ann <= tol and
            diff_sharpe <= tol and
            diff_dd <= tol and
            diff_trades == 0 and
            diff_filtered == 0 and
            diff_final <= 1.0
        )
        
        print(f"\n  DIFF total_return: {diff_return:.2e} (tol={tol})")
        print(f"  DIFF annualized_return: {diff_ann:.2e} (tol={tol})")
        print(f"  DIFF sharpe: {diff_sharpe:.2e} (tol={tol})")
        print(f"  DIFF max_drawdown: {diff_dd:.2e} (tol={tol})")
        print(f"  DIFF n_trades: {diff_trades} (tol=0)")
        print(f"  DIFF n_filtered: {diff_filtered} (tol=0)")
        print(f"  DIFF final_value: {diff_final:.2f} (tol=1.0)")
        
        if passed:
            print(f"\n  ✅ PASSED: Baseline parity confirmed")
        else:
            print(f"\n  ❌ FAILED: Baseline mismatch!")
            all_passed = False
    
    print(f"\n{'='*80}")
    if all_passed:
        print("OVERALL: ✅ ALL TESTS PASSED")
    else:
        print("OVERALL: ❌ SOME TESTS FAILED")
    print(f"{'='*80}")
    
    return all_passed


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
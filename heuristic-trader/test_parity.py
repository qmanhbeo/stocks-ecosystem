#!/usr/bin/env python3
"""
Pre-computed vs legacy parity test.

Run: python test_parity.py

Compares the fast pre-computed lookup caches against the legacy
on-the-fly filter functions. Both paths should produce identical results.

STATUS:
  - PARITY_UNKNOWN: test has not been run yet
  - PARITY_PASS: pre-computed matches legacy exactly
  - PARITY_FAIL: pre-computed differs from legacy (precomputed unsafe)
  - LEGACY_UNAVAILABLE: legacy mode could not run (e.g. price cache empty)

F00006 notes: pre-computed cache gave +99.86% vs legacy +82.39% (unknown bug).
This test quantifies exactly where the divergence occurs.
"""

import sys
import time
import signals as s
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import backtest as bt


def load_legacy_data(start, end):
    """Load data for legacy (on-the-fly) mode."""
    pc = bt.load_price_cache()
    if not pc:
        print("  Legacy: price cache empty, skipping")
        return None, None
    trad_df = s.load_order_pressure(start=start, end=end)
    return pc, trad_df


def load_precomputed_data():
    """Load pre-computed fast lookup caches."""
    liquid = bt.load_liquid_lookup()
    trad = bt.load_trad_lookup()
    pc = bt.load_price_cache()
    return pc, liquid, trad


def run_precomputed(signal_df, price_cache, liquid_lookup, trad_lookup, **kwargs):
    """Run with pre-computed fast lookups."""
    return bt.simulate_topk_constraint_compliant(
        signal_df, price_cache,
        liquid_lookup=liquid_lookup, trad_lookup=trad_lookup,
        use_filters=True, **kwargs
    )


def run_legacy(signal_df, price_cache, tradability_df, **kwargs):
    """Run with legacy on-the-fly filtering (no pre-computed caches)."""
    return bt.simulate_topk_constraint_compliant(
        signal_df, price_cache,
        liquid_lookup=None, trad_lookup=None,
        tradability_df=tradability_df, use_filters=True, **kwargs
    )


def compare_results(r1, r2, name1="precomputed", name2="legacy"):
    """Compare two BacktestResult objects."""
    fields = ["total_return", "annualized_return", "sharpe", "max_drawdown", "n_trades", "n_filtered"]
    diffs = []
    for f in fields:
        v1 = getattr(r1, f, None)
        v2 = getattr(r2, f, None)
        if v1 is None or v2 is None:
            diffs.append(f"  {f}: {name1}={v1}, {name2}={v2} (N/A comparison)")
        else:
            diff = abs(v1 - v2)
            rel = diff / (abs(v2) + 1e-10)
            diffs.append(f"  {f}: {name1}={v1:.6f}, {name2}={v2:.6f}, diff={diff:.6f} ({rel:.4%})")
    return diffs


def run_parity_test(strategy="s1_top5_rebal10", start="2024-01-01", end="2025-12-31",
                    short_window=False):
    """Run parity test on a strategy over a date range.

    If short_window=True, uses 2025-01-01 to 2025-03-31 for fast testing.
    """
    from strategies import loader as strategy_loader

    if short_window:
        start, end = "2025-01-01", "2025-03-31"

    print(f"\n{'='*60}")
    print(f"PARITY TEST: {strategy} [{start} -> {end}]")
    print(f"{'='*60}")

    config = strategy_loader.load_strategy_config(strategy)

    signal_type = config["signal_type"]
    s1 = s.load_rl_signal_matrix(start=start, end=end)
    if signal_type == "s1_only":
        signal_df = s1[['time', 'ticker', 's1_proba']].copy()
        signal_col = "s1_proba"
    elif signal_type == "c16_only":
        c16 = s.load_order_pressure(start=start, end=end)
        signal_df = c16[['time', 'ticker', 'order_volume_ratio_rank']].copy()
        signal_col = "order_volume_ratio_rank"
    elif signal_type in ("blend_70_30", "blend_50_50"):
        c16 = s.load_order_pressure(start=start, end=end)
        df = s1[['time', 'ticker', 's1_proba']].merge(
            c16[['time', 'ticker', 'order_volume_ratio_rank']], on=['time', 'ticker'])
        if signal_type == "blend_70_30":
            df['blend'] = df['s1_proba'] * 0.7 + df['order_volume_ratio_rank'] * 0.3
        else:
            df['blend'] = df['s1_proba'] * 0.5 + df['order_volume_ratio_rank'] * 0.5
        signal_df = df[['time', 'ticker', 'blend']]
        signal_col = "blend"
    else:
        print(f"Unknown signal_type: {signal_type}")
        return None

    top_k = config["top_k"]
    rebal = config["rebalance_days"]
    min_hold = config["min_hold_days"]

    print(f"Signal: {signal_col}, K={top_k}, rebal={rebal}d, min_hold={min_hold}d")
    print(f"Signal rows: {len(signal_df):,}")

    # --- PRECOMPUTED MODE ---
    print(f"\n[1] Pre-computed mode...")
    t0 = time.time()
    pc_pre, liq_pre, trad_pre = load_precomputed_data()
    if not pc_pre:
        print("  FAIL: price cache empty")
        return "PARITY_FAIL"
    print(f"  Liquid dates: {len(liq_pre):,}, Trad entries: {len(trad_pre):,}")
    r_pre = run_precomputed(signal_df, pc_pre, liq_pre, trad_pre,
                            signal_col=signal_col, top_k=top_k,
                            rebalance_days=rebal, min_hold_days=min_hold)
    t_pre = time.time() - t0
    print(f"  Result: {r_pre.total_return:.4%}, {r_pre.n_trades}tr, {t_pre:.1f}s")
    print(f"  Filtered: {r_pre.n_filtered}")

    # --- LEGACY MODE ---
    print(f"\n[2] Legacy mode (on-the-fly)...")
    t0 = time.time()
    pc_leg, trad_df = load_legacy_data(start, end)
    if pc_leg is None:
        print("  LEGACY_UNAVAILABLE: price cache empty")
        return "LEGACY_UNAVAILABLE"
    r_leg = run_legacy(signal_df, pc_leg, trad_df,
                        signal_col=signal_col, top_k=top_k,
                        rebalance_days=rebal, min_hold_days=min_hold)
    t_leg = time.time() - t0
    print(f"  Result: {r_leg.total_return:.4%}, {r_leg.n_trades}tr, {t_leg:.1f}s")
    print(f"  Filtered: {r_leg.n_filtered}")

    # --- COMPARE ---
    print(f"\n[3] Comparison:")
    diffs = compare_results(r_pre, r_leg)

    tolerance_total_return = 1e-6
    tolerance_n_trades = 0
    tolerance_n_filtered = 0

    total_return_diff = abs(r_pre.total_return - r_leg.total_return)
    n_trades_diff = abs(r_pre.n_trades - r_leg.n_trades)
    n_filtered_diff = abs(r_pre.n_filtered - r_leg.n_filtered)

    all_pass = (
        total_return_diff <= tolerance_total_return and
        n_trades_diff <= tolerance_n_trades and
        n_filtered_diff <= tolerance_n_filtered
    )

    for d in diffs:
        print(d)

    print(f"\nTolerance: total_return<={tolerance_total_return}, n_trades<={tolerance_n_trades}, n_filtered<={tolerance_n_filtered}")

    if all_pass:
        print(f"\nPARITY_PASS: pre-computed matches legacy exactly.")
        print(f"Pre-computed cache is TRUSTED for this strategy/period.")
        return "PARITY_PASS"
    else:
        print(f"\nPARITY_FAIL: pre-computed diverges from legacy.")
        print(f"** Pre-computed cache is UNSAFE for production use. **")
        print(f"** FALLING BACK to legacy mode as truth path. **")
        print(f"Root cause investigation needed:")
        print(f"  - total_return gap: {total_return_diff:.6f} ({total_return_diff/abs(r_leg.total_return+1e-10):.2%} relative)")
        print(f"  - n_trades gap: {n_trades_diff}")
        print(f"  - n_filtered gap: {n_filtered_diff}")
        return "PARITY_FAIL"


def main():
    print("=" * 60)
    print("heuristic-trader - Pre-computed vs Legacy Parity Test")
    print("=" * 60)
    print()
    print("Quick test (Q1 2025, fast):")
    result_fast = run_parity_test(strategy="s1_top5_rebal10", short_window=True)
    print()
    print("Full test (2024-2025, authoritative):")
    result_full = run_parity_test(strategy="s1_top5_rebal10", start="2024-01-01", end="2025-12-31")

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Quick test:  {result_fast}")
    print(f"  Full test:  {result_full}")
    print()

    if result_full == "PARITY_PASS":
        print("VERDICT: pre-computed cache is SAFE. Use freely.")
        sys.exit(0)
    elif result_full == "PARITY_FAIL":
        print("VERDICT: pre-computed cache has a BUG. Use legacy mode only.")
        print("The bug is recorded in findings_00001_00030.md (F00006).")
        sys.exit(1)
    elif result_full == "LEGACY_UNAVAILABLE":
        print("VERDICT: Cannot determine parity. Legacy price cache empty.")
        sys.exit(2)
    else:
        print(f"VERDICT: Unknown result {result_full}")
        sys.exit(3)


if __name__ == "__main__":
    main()
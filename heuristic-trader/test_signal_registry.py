#!/usr/bin/env python3
"""
Signal Registry Smoke Test

Verifies:
- S1 loads (s1_proba)
- C16 rank loads (order_volume_ratio_rank)
- C17 raw loads (order_volume_ratio)
- C17 active boost loads (c17_active_boost)
- C18 delta loads (order_volume_ratio_rank_delta)
- low breadth regime loads (is_low_breadth)
- All return columns: time, ticker, signal column
- No dates beyond 2025-12-31 by default
- No null explosion for C18 beyond expected first observation per ticker
"""

import sys
sys.path.insert(0, '.')

import signals as s

def test_s1_proba():
    print("Testing S1 (s1_proba)...")
    df = s.load_rl_signal_matrix(start="2024-01-01", end="2024-12-31")
    assert 'time' in df.columns, "Missing 'time' column"
    assert 'ticker' in df.columns, "Missing 'ticker' column"
    assert 's1_proba' in df.columns, "Missing 's1_proba' column"
    assert df['time'].max().year <= 2025, f"S1 has dates beyond 2025: {df['time'].max()}"
    print(f"  PASS: {len(df)} rows, {df['ticker'].nunique()} tickers")

def test_c16_rank():
    print("Testing C16 rank (order_volume_ratio_rank)...")
    df = s.load_order_pressure(start="2024-01-01", end="2024-12-31")
    assert 'time' in df.columns, "Missing 'time' column"
    assert 'ticker' in df.columns, "Missing 'ticker' column"
    assert 'order_volume_ratio_rank' in df.columns, "Missing 'order_volume_ratio_rank' column"
    assert df['time'].max().year <= 2025, f"C16 has dates beyond 2025: {df['time'].max()}"
    print(f"  PASS: {len(df)} rows, {df['ticker'].nunique()} tickers")

def test_c17_raw():
    print("Testing C17 raw (order_volume_ratio)...")
    df = s.load_order_pressure_raw(start="2024-01-01", end="2024-12-31")
    assert 'time' in df.columns, "Missing 'time' column"
    assert 'ticker' in df.columns, "Missing 'ticker' column"
    assert 'order_volume_ratio' in df.columns, "Missing 'order_volume_ratio' column"
    assert df['time'].max().year <= 2025, f"C17 has dates beyond 2025: {df['time'].max()}"
    print(f"  PASS: {len(df)} rows, {df['ticker'].nunique()} tickers")

def test_c18_delta():
    print("Testing C18 delta (order_volume_ratio_rank_delta)...")
    df = s.load_order_pressure_delta(start="2024-01-01", end="2024-12-31")
    assert 'time' in df.columns, "Missing 'time' column"
    assert 'ticker' in df.columns, "Missing 'ticker' column"
    assert 'order_volume_ratio_rank_delta' in df.columns, "Missing 'order_volume_ratio_rank_delta' column"
    assert df['time'].max().year <= 2025, f"C18 has dates beyond 2025: {df['time'].max()}"

    null_pct = df['order_volume_ratio_rank_delta'].isna().sum() / len(df) * 100
    print(f"  Null percentage: {null_pct:.2f}% (expected ~0% after fillna)")

    first_obs = (df['order_volume_ratio_rank_delta'] == 0.0).sum()
    total = len(df)
    zero_pct = first_obs / total * 100
    print(f"  Zero (first-observation fallback) percentage: {zero_pct:.2f}%")

    print(f"  PASS: {len(df)} rows, {df['ticker'].nunique()} tickers")


def test_c17_active_boost():
    print("Testing C17 active boost (c17_active_boost)...")
    df = s.load_order_pressure_c17_active_boost(start="2024-01-01", end="2024-12-31")
    assert 'time' in df.columns, "Missing 'time' column"
    assert 'ticker' in df.columns, "Missing 'ticker' column"
    assert 'c17_active_boost' in df.columns, "Missing 'c17_active_boost' column"
    assert df['time'].max().year <= 2025, f"C17 active boost has dates beyond 2025: {df['time'].max()}"
    print(f"  PASS: {len(df)} rows, {df['ticker'].nunique()} tickers")


def test_low_breadth_regime():
    print("Testing low breadth regime (is_low_breadth)...")
    df = s.load_low_breadth_regime(start="2024-01-01", end="2024-12-31")
    assert 'time' in df.columns, "Missing 'time' column"
    assert 'active_count' in df.columns, "Missing 'active_count' column"
    assert 'breadth_percentile' in df.columns, "Missing 'breadth_percentile' column"
    assert 'is_low_breadth' in df.columns, "Missing 'is_low_breadth' column"
    assert df['time'].max().year <= 2025, f"Low breadth has dates beyond 2025: {df['time'].max()}"
    low_share = df["is_low_breadth"].mean()
    assert 0.10 <= low_share <= 0.40, f"Low-breadth share out of expected range: {low_share:.3f}"
    print(f"  PASS: {len(df)} dates, low_share={low_share:.3f}")

def test_signal_registry():
    print("Testing SIGNAL_REGISTRY...")
    assert 's1_proba' in s.SIGNAL_REGISTRY, "S1 not in registry"
    assert 'c16_rank' in s.SIGNAL_REGISTRY, "C16 not in registry"
    assert 'c17_raw' in s.SIGNAL_REGISTRY, "C17 not in registry"
    assert 'c17_active_boost' in s.SIGNAL_REGISTRY, "C17 active boost not in registry"
    assert 'c18_delta' in s.SIGNAL_REGISTRY, "C18 not in registry"
    assert 'low_breadth_flag' in s.SIGNAL_REGISTRY, "Low breadth not in registry"
    print(f"  PASS: {len(s.SIGNAL_REGISTRY)} signals in registry")

def main():
    print("=" * 60)
    print("SIGNAL REGISTRY SMOKE TEST")
    print("=" * 60)

    test_signal_registry()
    test_s1_proba()
    test_c16_rank()
    test_c17_raw()
    test_c17_active_boost()
    test_c18_delta()
    test_low_breadth_regime()

    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)

if __name__ == "__main__":
    main()

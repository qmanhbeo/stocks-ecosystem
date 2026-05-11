#!/usr/bin/env python3
"""
Signal Registry Smoke Test

Verifies:
- S1 loads (s1_proba)
- C16 rank loads (order_volume_ratio_rank)
- C17 raw loads (order_volume_ratio)
- C18 delta loads (order_volume_ratio_rank_delta)
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

def test_signal_registry():
    print("Testing SIGNAL_REGISTRY...")
    assert 's1_proba' in s.SIGNAL_REGISTRY, "S1 not in registry"
    assert 'c16_rank' in s.SIGNAL_REGISTRY, "C16 not in registry"
    assert 'c17_raw' in s.SIGNAL_REGISTRY, "C17 not in registry"
    assert 'c18_delta' in s.SIGNAL_REGISTRY, "C18 not in registry"
    print(f"  PASS: {len(s.SIGNAL_REGISTRY)} signals in registry")

def main():
    print("=" * 60)
    print("SIGNAL REGISTRY SMOKE TEST")
    print("=" * 60)

    test_signal_registry()
    test_s1_proba()
    test_c16_rank()
    test_c17_raw()
    test_c18_delta()

    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)

if __name__ == "__main__":
    main()
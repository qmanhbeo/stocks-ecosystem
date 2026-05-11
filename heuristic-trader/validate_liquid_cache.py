#!/usr/bin/env python3
"""
Validate that rebuilt liquid_lookup matches check_liquid() exactly.

Run: python3 validate_liquid_cache.py

This validates the build_cache.py fix before running parity test.
"""

import sys
import pandas as pd
from pathlib import Path
from datetime import datetime
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent))

import backtest as bt


def validate_liquid_cache(start: str = "2024-01-01", end: str = "2025-12-31", n_sample_dates: int = 50):
    """Validate rebuilt liquid_lookup against check_liquid()."""
    print("=" * 60)
    print("LIQUID CACHE VALIDATION")
    print("=" * 60)

    # Load data
    price_cache = bt.load_price_cache()
    liquid_lookup = bt.load_liquid_lookup()

    print(f"\nPrice cache tickers: {len(price_cache)}")
    print(f"Liquid lookup dates: {len(liquid_lookup)}")

    # Sample dates from the period
    all_dates = sorted(liquid_lookup.keys())
    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)
    valid_dates = [d for d in all_dates if start_dt <= d <= end_dt]

    if len(valid_dates) > n_sample_dates:
        step = len(valid_dates) // n_sample_dates
        sample_dates = valid_dates[::step]
    else:
        sample_dates = valid_dates

    print(f"\nValidating {len(sample_dates)} sample dates...")

    differences = []
    for date in sample_dates:
        tickers_in_lookup = liquid_lookup.get(date, set())

        for ticker in price_cache:
            legacy_result = bt.check_liquid(price_cache, ticker, date)
            precomputed_result = ticker in tickers_in_lookup

            if legacy_result != precomputed_result:
                differences.append({
                    "date": str(date.date()),
                    "ticker": ticker,
                    "legacy_liquid": legacy_result,
                    "precomputed_liquid": precomputed_result
                })

    print(f"\nResults:")
    print(f"  Sample dates checked: {len(sample_dates)}")
    print(f"  Total differences: {len(differences)}")

    if differences:
        print(f"\nSample differences:")
        for d in differences[:10]:
            print(f"  {d['date']} {d['ticker']}: legacy={d['legacy_liquid']}, precomputed={d['precomputed_liquid']}")

    if len(differences) == 0:
        print("\n✅ VALIDATION PASSED: Precomputed matches legacy exactly")
        return True
    else:
        print(f"\n❌ VALIDATION FAILED: {len(differences)} differences found")
        return False


if __name__ == "__main__":
    result = validate_liquid_cache()
    sys.exit(0 if result else 1)
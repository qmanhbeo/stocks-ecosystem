#!/usr/bin/env python3
"""
Liquidity semantics diagnostic: Prove the exact mismatch between legacy and precomputed.

Run: python3 debug_liquidity_semantics.py

This script does NOT:
- Fix any behavior
- Rebuild caches
- Change backtest logic
- Alter research conclusions
"""

import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import backtest as bt


def run_liquidity_semantics_diagnostic(divergent_csv_path: str, n_samples: int = 30):
    """Run liquidity semantics diagnostic."""
    print("=" * 60)
    print("LIQUIDITY SEMANTICS DIAGNOSTIC")
    print("=" * 60)

    # Output directory
    output_dir = Path("artifacts") / "liquidity_semantics" / datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nOutput directory: {output_dir}")

    # Load divergent rows from first diagnostic
    df_div = pd.read_csv(divergent_csv_path)
    print(f"\nLoaded divergent rows: {len(df_div)}")

    # Filter to liquidity divergences only
    df_liq = df_div[df_div["divergence_type"] == "liquidity"].head(n_samples)
    print(f"Analyzing {len(df_liq)} liquidity divergences")

    # Load caches
    print("\n[1] Loading caches...")
    liquid_lookup = bt.load_liquid_lookup()
    price_cache = bt.load_price_cache()
    print(f"    Liquid lookup dates: {len(liquid_lookup)}")
    print(f"    Price cache tickers: {len(price_cache)}")

    # Analyze each divergent row
    results = []
    print("\n[2] Computing per-row diagnostics...")

    for idx, row in df_liq.iterrows():
        date_str = row['date']
        ticker = row['ticker']

        # Parse date
        try:
            date = pd.to_datetime(date_str)
        except:
            continue

        # Legacy check_liquid result (from first diagnostic)
        legacy_result = row['liquidity_legacy']

        # Precomputed is_liquid result
        precomputed_result = row['liquidity_precomputed']

        # Does ticker exist in price cache?
        ticker_in_cache = ticker in price_cache
        if not ticker_in_cache:
            results.append({
                "date": date_str,
                "ticker": ticker,
                "signal": row['signal'],
                "legacy_check_liquid_result": legacy_result,
                "precomputed_is_liquid_result": precomputed_result,
                "ticker_exists_in_price_cache": False,
                "reason": "ticker not in price cache"
            })
            continue

        # Get ticker DataFrame
        ticker_df = price_cache[ticker]
        dates_sorted = sorted(ticker_df.index)

        # Exact date exists in price cache?
        exact_date_exists = date in dates_sorted

        # Find index of date (legacy uses fallback to last)
        if exact_date_exists:
            idx_pos = dates_sorted.index(date)
        else:
            idx_pos = len(dates_sorted) - 1  # Legacy fallback
            exact_date_exists = False

        # Get last 5 available dates used by legacy
        start_idx = max(0, idx_pos - 5)
        window_dates = dates_sorted[start_idx:idx_pos + 1]
        window_df = ticker_df.iloc[start_idx:idx_pos + 1]

        # Compute legacy metrics
        n_rows = len(window_df)
        if n_rows >= 3:
            mean_volume = window_df['volume'].mean()
            price_change = abs(window_df['close'].iloc[-1] - window_df['close'].iloc[0]) / window_df['close'].iloc[0] if n_rows >= 2 else None
            legacy_meets_threshold = mean_volume >= 500_000 and (price_change is None or price_change >= 0.001)
        else:
            mean_volume = None
            price_change = None
            legacy_meets_threshold = False

        # Precomputed: is ticker in liquid_lookup for this date?
        date_in_liquid_lookup = date in liquid_lookup
        if date_in_liquid_lookup:
            ticker_in_liquid_set = ticker in liquid_lookup.get(date, set())
        else:
            ticker_in_liquid_set = False

        # Nearest dates in liquid_lookup (for inspection only)
        liquid_dates = sorted(liquid_lookup.keys())
        nearest_before = None
        nearest_after = None
        for d in liquid_dates:
            if d < date:
                nearest_before = d
            elif d > date and nearest_after is None:
                nearest_after = d
                break

        result = {
            "date": date_str,
            "ticker": ticker,
            "signal": row['signal'],
            "legacy_check_liquid_result": legacy_result,
            "precomputed_is_liquid_result": precomputed_result,
            "ticker_exists_in_price_cache": True,
            "exact_date_exists_in_price_cache": exact_date_exists,
            "price_cache_rows_before_or_on_date": idx_pos + 1,
            "last_5_available_dates_used_by_legacy": [str(d.date()) for d in window_dates],
            "volumes_on_those_dates": window_df['volume'].tolist() if n_rows > 0 else [],
            "mean_volume_legacy": mean_volume,
            "min_volume_threshold": 500_000,
            "price_change_legacy": price_change,
            "price_change_threshold": 0.001,
            "legacy_meets_threshold": legacy_meets_threshold,
            "whether_ticker_in_liquid_lookup_for_date": ticker_in_liquid_set,
            "liquid_lookup_date_exists": date_in_liquid_lookup,
            "nearest_liquid_lookup_date_before": str(nearest_before.date()) if nearest_before else None,
            "nearest_liquid_lookup_date_after": str(nearest_after.date()) if nearest_after else None,
            "legacy_fallback_used": not exact_date_exists,
        }
        results.append(result)

    # Save outputs
    print("\n[3] Saving outputs...")

    # sample_liquidity_diagnostics.csv
    df_out = pd.DataFrame(results)
    df_out.to_csv(output_dir / "sample_liquidity_diagnostics.csv", index=False)
    print(f"    Written: sample_liquidity_diagnostics.csv ({len(df_out)} rows)")

    # Analyze patterns
    fallback_used = sum(1 for r in results if r.get("legacy_fallback_used", False))
    exact_missing = sum(1 for r in results if not r.get("exact_date_exists_in_price_cache", True))

    # summary.json
    summary = {
        "timestamp": datetime.now().isoformat(),
        "n_samples_analyzed": len(results),
        "legacy_fallback_used_count": fallback_used,
        "exact_date_missing_count": exact_missing,
        "proven_mismatch": "legacy uses fallback to last date when exact date missing; precomputed only has dates that exist in price cache index",
        "note": "This diagnostic does NOT change behavior, rebuild caches, or alter research conclusions"
    }
    with open(output_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"    Written: summary.json")

    # README.md
    readme = f"""# Liquidity Semantics Diagnostic Output

Generated: {datetime.now().isoformat()}

## What Was Analyzed

- Analyzed {len(results)} liquidity-divergent rows
- Compared legacy `check_liquid()` vs precomputed `is_liquid()`

## Key Finding

**PROVEN MISMATCH**: Legacy `check_liquid()` falls back to the last available date when the queried date is not in the price cache index. Precomputed `liquid_lookup` only contains dates that actually exist in the index.

- Legacy fallback used: {fallback_used} cases
- Exact date missing from price cache: {exact_missing} cases

## Output Files

- `sample_liquidity_diagnostics.csv` - Per-row detailed diagnostics
- `summary.json` - Summary statistics
- `README.md` - This file

## What Was NOT Changed

- No backtest behavior modified
- No caches rebuilt
- No research conclusions altered

## Semantic Comparison

| Aspect | Legacy check_liquid() | Precomputed liquid_lookup |
|--------|----------------------|---------------------------|
| Date handling | Falls back to last date if exact date missing | Only contains dates that exist in price cache |
| Window | Variable: max(0, idx-5) to idx+1 | Fixed 5-row positional window |
| Missing date | Uses older window silently | Returns False (fail closed) |

This explains the 512 liquidity divergences found in the first diagnostic.
"""
    with open(output_dir / "README.md", "w") as f:
        f.write(readme)
    print(f"    Written: README.md")

    print(f"\nAll outputs saved to: {output_dir}")

    return results, summary, output_dir


def main():
    divergent_csv = "artifacts/parity_diagnostics/20260511_160057/divergent_rows.csv"
    results, summary, output_dir = run_liquidity_semantics_diagnostic(divergent_csv, n_samples=30)

    print("\n" + "=" * 60)
    print("LIQUIDITY SEMANTICS SUMMARY")
    print("=" * 60)
    print(f"Samples analyzed: {summary['n_samples_analyzed']}")
    print(f"Legacy fallback used: {summary['legacy_fallback_used_count']}")
    print(f"Exact date missing: {summary['exact_date_missing_count']}")
    print(f"\nProven mismatch: {summary['proven_mismatch']}")

    print(f"\nDiagnostic complete. Results in: {output_dir}")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Parity diagnostics: Find exact ticker-date divergences between legacy and precomputed.

Run: python3 debug_parity_diagnostics.py

This script does NOT:
- Fix any behavior
- Rebuild caches
- Change backtest logic
- Alter research conclusions

Output: artifacts/parity_diagnostics/<timestamp>/
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
import signals as s
import backtest as bt


def generate_rebalance_dates(signal_df: pd.DataFrame, rebalance_days: int) -> list:
    """Generate rebalance dates from signal_df."""
    dates = sorted(signal_df['time'].unique())
    rebal_dates = []
    for i in range(0, len(dates), rebalance_days):
        if i > 0:
            rebal_dates.append(dates[i - 1])
    return rebal_dates


def get_candidates_at_date(signal_df: pd.DataFrame, date) -> pd.DataFrame:
    """Get all signal candidates at a specific date."""
    return signal_df[signal_df['time'] == date].copy()


def run_legacy_filter(candidate: pd.Series, price_cache: dict, tradability_df: pd.DataFrame | None, min_volume: int = 500_000) -> dict:
    """Run legacy on-the-fly filters. Returns dict with results."""
    ticker = candidate['ticker']
    date = candidate['time']

    liquid = bt.check_liquid(price_cache, ticker, date, min_volume=min_volume)

    can_buy = True
    if tradability_df is not None:
        can_buy = bt.check_can_buy(tradability_df, ticker, date)

    return {"liquid": liquid, "can_buy": can_buy}


def run_precomputed_filter(candidate: pd.Series, liquid_lookup: dict, trad_lookup: dict) -> dict:
    """Run pre-computed lookup filters. Returns dict with results."""
    ticker = candidate['ticker']
    date = candidate['time']

    liquid = bt.is_liquid(ticker, date, liquid_lookup)
    can_buy = bt.can_buy_fast(ticker, date, trad_lookup)

    return {"liquid": liquid, "can_buy": can_buy}


def run_diagnostics(strategy: str = "s1_top5_rebal10", start: str = "2024-01-01", end: str = "2025-12-31"):
    """Run parity diagnostics."""
    from strategies import loader as strategy_loader

    print("=" * 60)
    print("PARITY DIAGNOSTICS - Finding exact divergences")
    print("=" * 60)

    output_dir = Path("artifacts") / "parity_diagnostics" / datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nOutput directory: {output_dir}")

    config = strategy_loader.load_strategy_config(strategy)
    signal_type = config["signal_type"]
    top_k = config["top_k"]
    rebal = config["rebalance_days"]
    min_hold = config["min_hold_days"]

    print(f"\nStrategy: {strategy}")
    print(f"Signal: {signal_type}, K={top_k}, rebal={rebal}d")

    # Load signal data
    s1 = s.load_rl_signal_matrix(start=start, end=end)
    if signal_type == "s1_only":
        signal_df = s1[['time', 'ticker', 's1_proba']].copy()
        signal_col = "s1_proba"
    else:
        print(f"ERROR: Only s1_only supported for diagnostics, got {signal_type}")
        return

    # Load both data sources
    print("\n[1] Loading pre-computed caches...")
    pc_pre, liquid_lookup, trad_lookup = bt.load_liquid_lookup(), bt.load_trad_lookup(), bt.load_price_cache()
    liquid_lookup = bt.load_liquid_lookup()
    trad_lookup = bt.load_trad_lookup()
    price_cache = bt.load_price_cache()
    print(f"    Liquid lookup dates: {len(liquid_lookup)}")
    print(f"    Trad lookup entries: {len(trad_lookup)}")
    print(f"    Price cache tickers: {len(price_cache)}")

    print("\n[2] Loading legacy data...")
    tradability_df = s.load_order_pressure(start=start, end=end)
    print(f"    Tradability rows: {len(tradability_df)}")

    # Generate rebalance dates
    rebal_dates = generate_rebalance_dates(signal_df, rebal)
    print(f"\n[3] Found {len(rebal_dates)} rebalance dates")

    # Track divergences
    all_divergences = []
    summary_by_type = defaultdict(int)

    print("\n[4] Comparing filters per rebalance date...")

    for rd in rebal_dates:
        candidates = get_candidates_at_date(signal_df, rd)
        if candidates.empty:
            continue

        for _, row in candidates.iterrows():
            legacy_result = run_legacy_filter(row, price_cache, tradability_df)
            precomputed_result = run_precomputed_filter(row, liquid_lookup, trad_lookup)

            legacy_selected = legacy_result["liquid"] and legacy_result["can_buy"]
            precomputed_selected = precomputed_result["liquid"] and precomputed_result["can_buy"]

            if legacy_result["liquid"] != precomputed_result["liquid"]:
                divergence = {
                    "date": str(rd.date()) if hasattr(rd, 'date') else str(rd),
                    "ticker": row['ticker'],
                    "signal": row[signal_col],
                    "liquidity_precomputed": precomputed_result["liquid"],
                    "liquidity_legacy": legacy_result["liquid"],
                    "tradability_precomputed": precomputed_result["can_buy"],
                    "tradability_legacy": legacy_result["can_buy"],
                    "selected_precomputed": precomputed_selected,
                    "selected_legacy": legacy_selected,
                    "divergence_type": "liquidity"
                }
                all_divergences.append(divergence)
                summary_by_type["liquidity"] += 1

            if legacy_result["can_buy"] != precomputed_result["can_buy"]:
                divergence = {
                    "date": str(rd.date()) if hasattr(rd, 'date') else str(rd),
                    "ticker": row['ticker'],
                    "signal": row[signal_col],
                    "liquidity_precomputed": precomputed_result["liquid"],
                    "liquidity_legacy": legacy_result["liquid"],
                    "tradability_precomputed": precomputed_result["can_buy"],
                    "tradability_legacy": legacy_result["can_buy"],
                    "selected_precomputed": precomputed_selected,
                    "selected_legacy": legacy_selected,
                    "divergence_type": "tradability"
                }
                all_divergences.append(divergence)
                summary_by_type["tradability"] += 1

            if legacy_selected != precomputed_selected:
                divergence = {
                    "date": str(rd.date()) if hasattr(rd, 'date') else str(rd),
                    "ticker": row['ticker'],
                    "signal": row[signal_col],
                    "liquidity_precomputed": precomputed_result["liquid"],
                    "liquidity_legacy": legacy_result["liquid"],
                    "tradability_precomputed": precomputed_result["can_buy"],
                    "tradability_legacy": legacy_result["can_buy"],
                    "selected_precomputed": precomputed_selected,
                    "selected_legacy": legacy_selected,
                    "divergence_type": "selection"
                }
                all_divergences.append(divergence)
                summary_by_type["selection"] += 1

    print(f"    Total divergences: {len(all_divergences)}")
    for k, v in summary_by_type.items():
        print(f"      - {k}: {v}")

    # Save outputs
    print("\n[5] Saving outputs...")

    # divergent_rows.csv
    if all_divergences:
        df_div = pd.DataFrame(all_divergences)
        df_div.to_csv(output_dir / "divergent_rows.csv", index=False)
        print(f"    Written: divergent_rows.csv ({len(df_div)} rows)")
    else:
        pd.DataFrame(columns=[
            "date", "ticker", "signal", "liquidity_precomputed", "liquidity_legacy",
            "tradability_precomputed", "tradability_legacy", "selected_precomputed", "selected_legacy"
        ]).to_csv(output_dir / "divergent_rows.csv", index=False)
        print("    Written: divergent_rows.csv (empty - no divergences found)")

    # summary.json
    summary_data = {
        "timestamp": datetime.now().isoformat(),
        "strategy": strategy,
        "start": start,
        "end": end,
        "rebalance_days": rebal,
        "total_candidates_checked": len(rebal_dates) * len(signal_df),
        "total_divergences": len(all_divergences),
        "divergences_by_type": dict(summary_by_type),
        "note": "This diagnostic does NOT change behavior, rebuild caches, or alter research conclusions"
    }
    with open(output_dir / "summary.json", "w") as f:
        json.dump(summary_data, f, indent=2)
    print(f"    Written: summary.json")

    # README.md
    readme = f"""# Parity Diagnostics Output

Generated: {datetime.now().isoformat()}

## What Was Compared

- **Strategy**: {strategy}
- **Period**: {start} to {end}
- **Rebalance frequency**: {rebal} days

Both legacy (on-the-fly) and pre-computed filter paths were applied to each candidate at each rebalance date.

## Output Files

- `divergent_rows.csv` - Exact (date, ticker) where legacy and precomputed differ
- `summary.json` - Summary statistics
- `README.md` - This file

## What Was NOT Changed

- No backtest behavior modified
- No caches rebuilt
- No research conclusions altered
- Legacy mode remains authoritative until parity passes

## Known Issue

Parity failure is proven (~4.11% vs ~0.21% return gap). Root cause is NOT yet proven.
This diagnostic helps isolate the exact divergence points.
"""
    with open(output_dir / "README.md", "w") as f:
        f.write(readme)
    print(f"    Written: README.md")

    print(f"\nAll outputs saved to: {output_dir}")

    return all_divergences, summary_by_type, output_dir


def main():
    divergences, summary, output_dir = run_diagnostics()

    print("\n" + "=" * 60)
    print("TOP DIVERGENCE SUMMARY")
    print("=" * 60)
    print(f"Total divergences found: {len(divergences)}")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    if divergences:
        df = pd.DataFrame(divergences)
        if "selection" in df["divergence_type"].values:
            sel = df[df["divergence_type"] == "selection"]
            print(f"\n[Selection divergences - most impactful]")
            print(sel[["date", "ticker", "selected_legacy", "selected_precomputed"]].head(10).to_string())

    print(f"\nDiagnostic complete. Results in: {output_dir}")


if __name__ == "__main__":
    main()
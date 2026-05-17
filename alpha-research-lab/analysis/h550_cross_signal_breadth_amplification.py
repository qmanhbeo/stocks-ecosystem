#!/usr/bin/env python3
"""
H550 - Cross-Signal Low-Breadth Amplification

Test if individual C23/C24/C25/C26 signals have different optimal breadth windows.
H543 found composite×low_breadth = 0.2364 (+0.1066). Now test if each signal
amplifies by its OWN low-breadth dates (each might have different optimal windows).

Hypothesis: C23's low_breadth dates ≠ C24's low_breadth dates ≠ C25's ≠ C26's.
Each signal may have a different "sweet spot" breadth regime.
"""

import sys
sys.path.insert(0, "/home/manh/stocks-ecosystem/alpha-research-lab")

import numpy as np
import pandas as pd
from datetime import datetime
from scipy.stats import spearmanr
from pathlib import Path

from src.experiment_contract import (
    safe_spearman,
    yearly_ic,
    summarize_ic_rows,
    normalize_time_ticker,
    restrict_years,
    require_columns,
)
from src.repo_paths import artifact_path, data_path


def load_data() -> pd.DataFrame:
    """Load S1, C16, and order stats for signal construction."""
    s1_path = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
    s1_df = pd.read_parquet(s1_path, columns=["time", "ticker", "xs_proba", "actual"])
    s1_df = normalize_time_ticker(s1_df, source="S1 panel")
    s1_df = restrict_years(s1_df, start_year=2015, end_year=2025, source="S1 panel")
    s1_df = s1_df.rename(columns={"xs_proba": "s1_xs_proba", "actual": "s1_barrier_hit_1d"})
    
    c16_path = data_path("features/xs_order_pressure_daily.parquet")
    c16_df = pd.read_parquet(c16_path)
    c16_df = normalize_time_ticker(c16_df, source="C16 panel")
    c16_df = restrict_years(c16_df, start_year=2015, end_year=2025, source="C16 panel")
    
    df = s1_df.merge(c16_df, on=["time", "ticker"], how="inner")
    print(f"Merged panel: {len(df)} rows, years {df['time'].dt.year.min()}-{df['time'].dt.year.max()}")
    return df


def compute_signals_and_breadth(df: pd.DataFrame) -> pd.DataFrame:
    """Compute C23/C24/C25/C26 signals and date-level breadth for each."""
    panel = df.copy()
    
    # Volatility regime
    panel["volatility"] = panel.groupby("ticker")["order_volume_ratio_rank"].transform(
        lambda x: x.rolling(5, min_periods=1).std()
    )
    panel["vol_expansion"] = panel.groupby("time", sort=False)["volatility"].rank(pct=True) >= 0.8
    
    # Illiquidity (Amihud proxy)
    if "total_trade_value" in panel.columns and "return_1d" in panel.columns:
        panel["amihud"] = np.abs(panel["return_1d"]) / (panel["total_trade_value"] + 1)
        illiq_rank = panel.groupby("time", sort=False)["amihud"].rank(pct=True)
        panel["high_illiq"] = illiq_rank >= 0.8
    else:
        panel["order_rank"] = panel.groupby("time", sort=False)["order_volume_ratio_rank"].rank(pct=True)
        panel["high_illiq"] = panel["order_rank"] >= 0.8
    
    # C16 level
    panel["c16_low"] = panel["order_volume_ratio_rank"] < 0.2
    panel["c16_high"] = panel["order_volume_ratio_rank"] >= 0.8
    
    # C23: high_illiq × vol_expansion
    panel["c23_signal"] = panel["high_illiq"] & panel["vol_expansion"]
    
    # C24: ceiling proxy (high positive pct_change) × vol_expansion
    if "pct_change" in panel.columns:
        panel["ceiling_proxy"] = panel["pct_change"] >= 5.0
    else:
        panel["ceiling_proxy"] = panel["order_volume_ratio_rank"] < 0.1
    panel["c24_signal"] = panel["ceiling_proxy"] & panel["vol_expansion"]
    
    # C25: VWAP below proxy × vol_expansion
    if "pct_change" in panel.columns:
        panel["vwap_below_proxy"] = panel["pct_change"] <= -2.0
    else:
        panel["vwap_below_proxy"] = panel["order_volume_ratio_rank"] >= 0.9
    panel["c25_signal"] = panel["vwap_below_proxy"] & panel["vol_expansion"]
    
    # C26: buy-heavy × illiq × vol_expansion
    if "buy_sell_imbalance" in panel.columns:
        panel["buy_heavy"] = panel.groupby("time", sort=False)["buy_sell_imbalance"].rank(pct=True) >= 0.8
    else:
        panel["buy_heavy"] = panel["order_volume_ratio_rank"] < 0.15
    panel["c26_signal"] = panel["buy_heavy"] & panel["high_illiq"] & panel["vol_expansion"]
    
    # Composite: OR of all signals
    panel["composite_signal"] = (
        panel["c23_signal"] | panel["c24_signal"] | panel["c25_signal"] | panel["c26_signal"]
    )
    
    # Compute date-level breadth for EACH signal
    for signal_name in ["c23_signal", "c24_signal", "c25_signal", "c26_signal", "composite_signal"]:
        active_per_date = panel[panel[signal_name]].groupby("time")["ticker"].nunique().reset_index()
        active_per_date.columns = ["time", f"{signal_name}_active_tickers"]
        
        total_per_date = panel.groupby("time")["ticker"].nunique().reset_index()
        total_per_date.columns = ["time", "total_tickers"]
        
        breadth_df = active_per_date.merge(total_per_date, on="time", how="outer")
        breadth_df[f"{signal_name}_breadth"] = breadth_df[f"{signal_name}_active_tickers"] / breadth_df["total_tickers"]
        breadth_df[f"{signal_name}_breadth"] = breadth_df[f"{signal_name}_breadth"].fillna(0)
        
        # Binary low breadth for each signal (bottom 20% of dates where signal is active)
        signal_dates = breadth_df[breadth_df[f"{signal_name}_active_tickers"] > 0]
        if len(signal_dates) > 0:
            threshold = signal_dates[f"{signal_name}_breadth"].quantile(0.2)
            breadth_df[f"{signal_name}_low_breadth"] = breadth_df[f"{signal_name}_breadth"] <= threshold
        else:
            breadth_df[f"{signal_name}_low_breadth"] = False
        
        panel = panel.merge(breadth_df[["time", f"{signal_name}_breadth", f"{signal_name}_low_breadth"]], 
                           on="time", how="left")
    
    print("\nSignal coverage:")
    for signal in ["c23_signal", "c24_signal", "c25_signal", "c26_signal"]:
        rows = panel[signal].sum()
        print(f"  {signal}: {rows} rows")
    
    return panel


def evaluate_signal(panel: pd.DataFrame, signal_col: str, filter_col: str | None, 
                   score_col: str, target_col: str, name: str, min_rows: int = 500) -> dict:
    """Evaluate IC for a signal, optionally with breadth filter."""
    if filter_col and filter_col in panel.columns:
        subset = panel[(panel[signal_col]) & (panel[filter_col])].copy()
    else:
        subset = panel[panel[signal_col]].copy()
    
    if len(subset) < min_rows:
        return {"name": name, "ic": None, "rows": len(subset)}
    
    result = safe_spearman(subset, score_col, target_col, min_rows=min_rows)
    return {
        "name": name,
        "ic": result.get("ic"),
        "rows": len(subset),
    }


def main():
    print("=" * 60)
    print("H550 - Cross-Signal Low-Breadth Amplification")
    print("=" * 60)
    
    print("\n[1/3] Loading data...")
    df = load_data()
    
    print("\n[2/3] Computing signals and per-signal breadth...")
    panel = compute_signals_and_breadth(df)
    
    print("\n[3/3] Evaluating each signal with own vs composite breadth...")
    
    baseline_result = safe_spearman(panel, "s1_xs_proba", "s1_barrier_hit_1d", min_rows=500)
    baseline_ic = baseline_result.get("ic", 0)
    print(f"\nBaseline (all rows): IC={baseline_ic:.4f}")
    
    results = []
    
    signals = ["c23_signal", "c24_signal", "c25_signal", "c26_signal", "composite_signal"]
    
    for signal in signals:
        signal_name = signal.replace("_signal", "").upper()
        
        # Signal alone (no breadth filter)
        result_alone = evaluate_signal(panel, signal, None, "s1_xs_proba", "s1_barrier_hit_1d", f"{signal_name}_alone")
        if result_alone["ic"] is not None:
            results.append({
                "name": f"{signal_name}_alone",
                "ic": result_alone["ic"],
                "rows": result_alone["rows"],
                "lift": result_alone["ic"] - baseline_ic
            })
            print(f"\n{signal_name} alone: IC={result_alone['ic']:.4f} ({result_alone['rows']} rows), lift={result_alone['ic']-baseline_ic:+.4f}")
        
        # Signal × own low breadth
        own_breadth_col = f"{signal}_low_breadth"
        if own_breadth_col in panel.columns:
            result_own = evaluate_signal(panel, signal, own_breadth_col, "s1_xs_proba", "s1_barrier_hit_1d", f"{signal_name}_own_breadth")
            if result_own["ic"] is not None:
                results.append({
                    "name": f"{signal_name}_own_breadth",
                    "ic": result_own["ic"],
                    "rows": result_own["rows"],
                    "lift": result_own["ic"] - baseline_ic
                })
                print(f"{signal_name} × own_low_breadth: IC={result_own['ic']:.4f} ({result_own['rows']} rows), lift={result_own['ic']-baseline_ic:+.4f}")
        
        # Signal × composite low breadth (for comparison)
        if signal != "composite_signal":
            result_composite = evaluate_signal(panel, signal, "composite_signal_low_breadth", 
                                               "s1_xs_proba", "s1_barrier_hit_1d", f"{signal_name}_comp_breadth")
            if result_composite["ic"] is not None:
                results.append({
                    "name": f"{signal_name}_comp_breadth",
                    "ic": result_composite["ic"],
                    "rows": result_composite["rows"],
                    "lift": result_composite["ic"] - baseline_ic
                })
                print(f"{signal_name} × composite_low_breadth: IC={result_composite['ic']:.4f} ({result_composite['rows']} rows), lift={result_composite['ic']-baseline_ic:+.4f}")
    
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values("ic", ascending=False)
    
    print(f"\n{'Signal':<30} {'IC':>8} {'Rows':>10} {'Lift':>10}")
    print("-" * 60)
    for _, row in results_df.iterrows():
        print(f"{row['name']:<30} {row['ic']:>8.4f} {row['rows']:>10} {row['lift']:>+10.4f}")
    
    best_own = results_df[results_df["name"].str.contains("_own_breadth")].sort_values("ic", ascending=False)
    best_comp = results_df[results_df["name"].str.contains("_comp_breadth")].sort_values("ic", ascending=False)
    
    if not best_own.empty and not best_comp.empty:
        own_best = best_own.iloc[0]
        comp_best = best_comp.iloc[0]
        
        own_vs_comp = own_best["ic"] - comp_best["ic"]
        print(f"\nOwn breadth vs Composite breadth: {own_vs_comp:+.4f}")
        
        if own_vs_comp > 0.01:
            verdict = "PASSED"
            print(f"Verdict: {verdict} - Each signal has different optimal breadth windows!")
        elif own_vs_comp > 0:
            verdict = "MIXED"
            print(f"Verdict: {verdict} - Weak own-breadth advantage")
        else:
            verdict = "FAILED"
            print(f"Verdict: {verdict} - Composite breadth is as good or better")
    else:
        verdict = "MIXED"
        print(f"\nVerdict: {verdict} - Insufficient data to compare")
    
    import json
    output = {
        "hypothesis": "Cross-Signal Low-Breadth Amplification",
        "baseline_ic": baseline_ic,
        "results": results,
        "verdict": verdict,
        "timestamp": datetime.now().isoformat()
    }
    
    out_path = artifact_path(f"run_summaries/{datetime.now().strftime('%Y%m%d_%H%M%S')}_cross_signal_breadth_amplification.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved: {out_path}")
    
    return output


if __name__ == "__main__":
    main()
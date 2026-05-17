#!/usr/bin/env python3
"""
H549 - Signal Ignorance as Alpha

Test if composite of weak-signal regimes (high_breadth, ultra_negative, floor_pressure)
forms an "ignore" signal that avoids degraded IC periods.

H525: high_breadth = worse IC (0.1149 vs 0.1454)
H480: ultra_negative exists as a state
H485: floor_pressure is anti-predictive

Hypothesis: Dates when these "weak signal" regimes are active have degraded S1 quality.
If we can identify these dates and reduce exposure, overall IC improves.

Decision rule:
- PASSED: S1 WITHOUT ignore_regime beats S1 WITH ignore_regime by >+0.01 IC
- MIXED: lift exists but < +0.01
- FAILED: ignore regime does not predict IC degradation
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


def load_signals() -> pd.DataFrame:
    """Load S1 and C16 signals."""
    s1_path = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
    s1_df = pd.read_parquet(s1_path, columns=["time", "ticker", "xs_proba", "actual"])
    s1_df = normalize_time_ticker(s1_df, source="S1 panel")
    s1_df = restrict_years(s1_df, start_year=2015, end_year=2025, source="S1 panel")
    s1_df = s1_df.rename(columns={"xs_proba": "s1_xs_proba", "actual": "s1_barrier_hit_1d"})
    
    c16_path = data_path("features/xs_order_pressure_daily.parquet")
    c16_cols = ["time", "ticker", "order_volume_ratio_rank"]
    c16_df = pd.read_parquet(c16_path, columns=c16_cols)
    c16_df = normalize_time_ticker(c16_df, source="C16 panel")
    c16_df = restrict_years(c16_df, start_year=2015, end_year=2025, source="C16 panel")
    
    df = s1_df.merge(c16_df, on=["time", "ticker"], how="inner")
    print(f"Merged panel: {len(df)} rows, years {df['time'].dt.year.min()}-{df['time'].dt.year.max()}")
    return df


def compute_date_breadth(df: pd.DataFrame) -> pd.DataFrame:
    """Compute date-level active-stock density (from H525)."""
    result = df.copy()
    
    rank = result["order_volume_ratio_rank"]
    result["is_active"] = (rank < 0.25).astype(int)
    
    date_stats = result.groupby("time").agg(
        total_tickers=("ticker", "count"),
        active_count=("is_active", "sum"),
        active_fraction=("is_active", "mean")
    ).reset_index()
    
    result = result.merge(date_stats, on="time", how="left")
    
    threshold_high = result["active_fraction"].quantile(0.8)
    result["high_breadth"] = (result["active_fraction"] >= threshold_high).astype(int)
    
    return result


def load_sentiment_data(df: pd.DataFrame) -> pd.DataFrame:
    """Load news sentiment to compute ultra_negative date-level fraction."""
    try:
        news_path = data_path("features/news_tabular_article_stage.parquet")
        news_df = pd.read_parquet(news_path, columns=["time", "ticker", "prob_neg"])
        news_df = normalize_time_ticker(news_df, source="News panel")
        news_df = restrict_years(news_df, start_year=2015, end_year=2025, source="News panel")
        
        news_df["ultra_negative"] = (news_df["prob_neg"] <= 0.05).astype(int)
        
        date_sentiment = news_df.groupby("time").agg(
            total_news=("ticker", "count"),
            ultra_negative_count=("ultra_negative", "sum"),
            ultra_negative_fraction=("ultra_negative", "mean")
        ).reset_index()
        
        result = df.merge(date_sentiment[["time", "ultra_negative_fraction"]], on="time", how="left")
        result["ultra_negative_fraction"] = result["ultra_negative_fraction"].fillna(0)
        
        threshold = result["ultra_negative_fraction"].quantile(0.8) if result["ultra_negative_fraction"].max() > 0 else 0
        result["high_ultra_negative"] = (result["ultra_negative_fraction"] >= threshold).astype(int)
        
        print(f"News sentiment loaded: {len(date_sentiment)} dates, max ultra_neg fraction: {result['ultra_negative_fraction'].max():.3f}")
        return result
    except Exception as e:
        print(f"Warning: Could not load sentiment data: {e}")
        result = df.copy()
        result["ultra_negative_fraction"] = 0
        result["high_ultra_negative"] = 0
        return result


def load_floor_pressure_data(df: pd.DataFrame) -> pd.DataFrame:
    """Load floor pressure data (from H485)."""
    try:
        order_stats_path = data_path("order_stats/cafef/order_stats_daily.parquet")
        order_stats = pd.read_parquet(order_stats_path)
        order_stats = order_stats.rename(columns={"date": "time"})
        order_stats["time"] = pd.to_datetime(order_stats["time"])
        order_stats = restrict_years(order_stats, start_year=2015, end_year=2025, source="Order stats")
        
        import re
        def parse_price_change(s):
            if pd.isna(s):
                return np.nan
            try:
                match = re.search(r'\(\s*([+-]?[\d,]+)\s*%\)', str(s))
                if match:
                    return float(match.group(1).replace(',', '.'))
                return np.nan
            except:
                return np.nan
        
        order_stats["price_change"] = order_stats["price_change"].apply(parse_price_change)
        order_stats["floor_pressure"] = (order_stats["price_change"] <= -7).astype(int)
        
        date_floor = order_stats.groupby("time").agg(
            floor_pressure_count=("floor_pressure", "sum"),
            floor_pressure_fraction=("floor_pressure", "mean")
        ).reset_index()
        
        result = df.merge(date_floor[["time", "floor_pressure_fraction"]], on="time", how="left")
        result["floor_pressure_fraction"] = result["floor_pressure_fraction"].fillna(0)
        
        threshold = result["floor_pressure_fraction"].quantile(0.8) if result["floor_pressure_fraction"].max() > 0 else 0
        result["high_floor_pressure"] = (result["floor_pressure_fraction"] >= threshold).astype(int)
        
        print(f"Floor pressure loaded: {len(date_floor)} dates, max floor fraction: {result['floor_pressure_fraction'].max():.3f}")
        return result
    except Exception as e:
        print(f"Warning: Could not load floor pressure data: {e}")
        result = df.copy()
        result["floor_pressure_fraction"] = 0
        result["high_floor_pressure"] = 0
        return result


def compute_ignore_regime(df: pd.DataFrame) -> pd.DataFrame:
    """Compute composite ignore regime flag."""
    result = df.copy()
    
    result["ignore_regime"] = (
        (result.get("high_breadth", 0) == 1) | 
        (result.get("high_ultra_negative", 0) == 1) | 
        (result.get("high_floor_pressure", 0) == 1)
    ).astype(int)
    
    date_ignore = result.groupby("time")["ignore_regime"].max().reset_index()
    date_ignore = date_ignore.rename(columns={"ignore_regime": "date_has_ignore_regime"})
    
    result = result.merge(date_ignore, on="time", how="left")
    
    print(f"\nIgnore regime stats:")
    print(f"  Dates with ignore regime: {date_ignore['date_has_ignore_regime'].sum()} / {len(date_ignore)}")
    print(f"  Ignore regime fraction: {date_ignore['date_has_ignore_regime'].mean():.3f}")
    
    return result


def evaluate_regime(df: pd.DataFrame, regime_col: str, score_col: str, target_col: str, 
                   min_rows: int) -> dict:
    """Evaluate IC for a regime."""
    require_columns(df, [regime_col, score_col, target_col], context=f"regime {regime_col}")
    
    subset = df.loc[df[regime_col] == 1].copy()
    if len(subset) < min_rows:
        return {"regime": regime_col, "rows": len(subset), "ic": None}
    
    pooled = safe_spearman(subset, score_col, target_col, min_rows=min_rows)
    years = yearly_ic(subset, score_col, target_col, min_year_rows=min_rows)
    summary = summarize_ic_rows(years)
    
    return {
        "regime": regime_col,
        "rows": len(subset),
        "ic": pooled.get("ic") if isinstance(pooled, dict) else pooled,
        "positive_years": summary["positive_years"],
        "mean_ic": summary["avg_ic"],
    }


def main():
    print("=" * 60)
    print("H549 - Signal Ignorance as Alpha")
    print("=" * 60)
    
    print("\n[1/5] Loading signals...")
    df = load_signals()
    
    print("\n[2/5] Computing date-level breadth...")
    df = compute_date_breadth(df)
    
    print("\n[3/5] Loading sentiment data for ultra_negative...")
    df = load_sentiment_data(df)
    
    print("\n[4/5] Loading floor pressure data...")
    df = load_floor_pressure_data(df)
    
    print("\n[5/5] Computing ignore regime and evaluating...")
    df = compute_ignore_regime(df)
    
    baseline_result = safe_spearman(df, "s1_xs_proba", "s1_barrier_hit_1d", min_rows=500)
    baseline_ic = baseline_result.get("ic", 0)
    print(f"\nBaseline (all rows): IC={baseline_ic:.4f}")
    
    results = {}
    
    results["baseline"] = {
        "ic": baseline_ic,
        "rows": len(df),
        "lift": 0.0
    }
    
    ignore_dates = evaluate_regime(df, "date_has_ignore_regime", "s1_xs_proba", "s1_barrier_hit_1d", min_rows=500)
    if ignore_dates.get("ic") is not None:
        ignore_ic = ignore_dates["ic"]
        results["with_ignore_regime"] = {
            "ic": ignore_ic,
            "rows": ignore_dates["rows"],
            "lift": ignore_ic - baseline_ic
        }
        print(f"\nS1 WITH ignore_regime: IC={ignore_ic:.4f}, rows={ignore_dates['rows']}, lift={ignore_ic-baseline_ic:+.4f}")
    
    no_ignore_df = df[df.get("date_has_ignore_regime", 0) == 0]
    no_ignore_result = safe_spearman(no_ignore_df, "s1_xs_proba", "s1_barrier_hit_1d", min_rows=500)
    no_ignore_ic = no_ignore_result.get("ic", 0) or 0
    results["without_ignore_regime"] = {
        "ic": no_ignore_ic,
        "rows": len(no_ignore_df),
        "lift": no_ignore_ic - baseline_ic
    }
    print(f"S1 WITHOUT ignore_regime: IC={no_ignore_ic:.4f}, rows={len(no_ignore_df)}, lift={no_ignore_ic-baseline_ic:+.4f}")
    
    if "high_breadth" in df.columns:
        high_breadth = evaluate_regime(df, "high_breadth", "s1_xs_proba", "s1_barrier_hit_1d", min_rows=500)
        if high_breadth.get("ic") is not None:
            hb_ic = high_breadth["ic"]
            results["high_breadth"] = {
                "ic": hb_ic,
                "rows": high_breadth["rows"],
                "lift": hb_ic - baseline_ic
            }
            print(f"  high_breadth alone: IC={hb_ic:.4f}, lift={hb_ic-baseline_ic:+.4f}")
    
    if "high_ultra_negative" in df.columns:
        high_ultra = evaluate_regime(df, "high_ultra_negative", "s1_xs_proba", "s1_barrier_hit_1d", min_rows=500)
        if high_ultra.get("ic") is not None:
            hu_ic = high_ultra["ic"]
            results["high_ultra_negative"] = {
                "ic": hu_ic,
                "rows": high_ultra["rows"],
                "lift": hu_ic - baseline_ic
            }
            print(f"  high_ultra_negative alone: IC={hu_ic:.4f}, lift={hu_ic-baseline_ic:+.4f}")
    
    if "high_floor_pressure" in df.columns:
        high_floor = evaluate_regime(df, "high_floor_pressure", "s1_xs_proba", "s1_barrier_hit_1d", min_rows=500)
        if high_floor.get("ic") is not None:
            hf_ic = high_floor["ic"]
            results["high_floor_pressure"] = {
                "ic": hf_ic,
                "rows": high_floor["rows"],
                "lift": hf_ic - baseline_ic
            }
            print(f"  high_floor_pressure alone: IC={hf_ic:.4f}, lift={hf_ic-baseline_ic:+.4f}")
    
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    
    ignore_lift = results.get("without_ignore_regime", {}).get("lift", 0)
    baseline_lift = 0
    
    print(f"\n{'Regime':<30} {'IC':>8} {'Rows':>10} {'Lift':>10}")
    print("-" * 60)
    for name, r in results.items():
        ic_val = r.get("ic", 0)
        rows_val = r.get("rows", 0)
        lift_val = r.get("lift", 0)
        print(f"{name:<30} {ic_val:>8.4f} {rows_val:>10} {lift_val:>+10.4f}")
    
    verdict = "MIXED"
    if ignore_lift > 0.01:
        verdict = "PASSED"
        print(f"\nVerdict: {verdict} - ignore regime identifies degraded IC periods")
    elif ignore_lift > 0:
        verdict = "MIXED"
        print(f"\nVerdict: {verdict} - weak effect, not actionable")
    else:
        verdict = "FAILED"
        print(f"\nVerdict: {verdict} - ignore regime does NOT identify IC degradation")
    
    import json
    output = {
        "hypothesis": "Signal Ignorance as Alpha",
        "baseline_ic": baseline_ic,
        "results": results,
        "verdict": verdict,
        "timestamp": datetime.now().isoformat()
    }
    
    out_path = artifact_path(f"run_summaries/{datetime.now().strftime('%Y%m%d_%H%M%S')}_signal_ignorance_alpha.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved: {out_path}")
    
    return output


if __name__ == "__main__":
    main()
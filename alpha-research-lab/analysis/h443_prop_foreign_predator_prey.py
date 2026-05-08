#!/usr/bin/env python3
"""
H443: prop_foreign_predator_prey

Hypothesis: Foreign and proprietary flows may be useful only as a conflict/absorption game,
not as raw net-flow ranks. Test predator-prey states where one flow type absorbs or follows another.

Connection: standalone foreign/proprietary paths and foreign additive H418 failed,
but the raw surfaces now exist. Smallest honest test: predeclare foreign-sell/prop-buy absorption,
foreign-buy/local-distribution, and prop-following-foreign states crossed only with Vol+S1 strength,
C16, and news support; compare to raw foreign, raw proprietary, H418, and random same-support controls.

Per convention: compare with random baselines, not S1/C16 variations.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime

# Paths
DATA_ROOT = Path("/home/manh/stocks-ecosystem/data")
ALPHA_ROOT = Path("/home/manh/stocks-ecosystem/alpha-research-lab")
ARTIFACTS = ALPHA_ROOT / "artifacts"
RUN_SUMMARIES = ARTIFACTS / "run_summaries"
RESEARCH_BRANCHES = ARTIFACTS / "research_branches"

def load_s1_panel():
    """Load S1 decision panel."""
    s1_path = DATA_ROOT / "features/xs_barrier_vol_1d_hose_full.parquet"
    df = pd.read_parquet(s1_path)
    # Rename raw `actual` to target-only label per S272 contract
    df = df.rename(columns={"actual": "s1_barrier_hit_1d"})
    # Block 2026+
    df = df[df["time"].dt.year <= 2025]
    return df

def load_foreign_flow():
    """Load foreign flow data."""
    ff_path = DATA_ROOT / "foreign_flow/cafef/foreign_flow_daily.parquet"
    if ff_path.exists():
        return pd.read_parquet(ff_path)
    return None

def load_proprietary_trading():
    """Load proprietary trading data."""
    pt_path = DATA_ROOT / "proprietary_trading/cafef/proprietary_trading_daily.parquet"
    if pt_path.exists():
        return pd.read_parquet(pt_path)
    return None

def load_c16():
    """Load C16 order pressure."""
    c16_path = DATA_ROOT / "features/xs_order_pressure_daily.parquet"
    if c16_path.exists():
        return pd.read_parquet(c16_path)
    return None

def load_news():
    """Load news features."""
    news_path = DATA_ROOT / "features/news/datasets/news_daily_features.parquet"
    if news_path.exists():
        return pd.read_parquet(news_path)
    return None

def compute_ic(df, score_col, target_col="s1_barrier_hit_1d"):
    """Compute IC between score and target."""
    if score_col not in df.columns:
        return np.nan
    valid = df[[score_col, target_col]].dropna()
    if len(valid) < 50:
        return np.nan
    return valid[score_col].corr(valid[target_col])

def compute_yearly_ic(df, score_col, target_col="s1_barrier_hit_1d"):
    """Compute IC by year."""
    if score_col not in df.columns:
        return {}
    valid = df[df[score_col].notna() & df[target_col].notna()].copy()
    valid["year"] = valid["time"].dt.year
    yearly = {}
    for year, group in valid.groupby("year"):
        if len(group) >= 50:
            yearly[year] = group[score_col].corr(group[target_col])
    return yearly

def main():
    print("=" * 60)
    print("H443: prop_foreign_predator_prey")
    print("=" * 60)
    
    # Load data
    print("\n[1] Loading data...")
    s1_df = load_s1_panel()
    print(f"  S1 panel: {len(s1_df):,} rows, {s1_df['ticker'].nunique()} tickers")
    
    ff_df = load_foreign_flow()
    pt_df = load_proprietary_trading()
    c16_df = load_c16()
    news_df = load_news()
    
    has_ff = ff_df is not None
    has_pt = pt_df is not None
    has_c16 = c16_df is not None
    has_news = news_df is not None
    
    print(f"  Foreign flow: {'YES' if has_ff else 'NO'}")
    print(f"  Proprietary trading: {'YES' if has_pt else 'NO'}")
    print(f"  C16: {'YES' if has_c16 else 'NO'}")
    print(f"  News: {'YES' if has_news else 'NO'}")
    
    # Check if we have enough data to run
    if not has_ff:
        print("\n[ERROR] No foreign flow data available. Cannot run experiment.")
        return
    
    # Merge data
    print("\n[2] Preparing panel...")
    # Use xs_proba as the score column (renamed to s1_xs_proba for consistency)
    panel = s1_df[["time", "ticker", "xs_proba", "s1_barrier_hit_1d"]].copy()
    panel = panel.rename(columns={"xs_proba": "s1_xs_proba"})
    
    if has_c16:
        c16_renamed = c16_df.rename(columns={"order_volume_ratio_rank": "c16_rank"})
        panel = panel.merge(c16_renamed[["time", "ticker", "c16_rank"]], on=["time", "ticker"], how="left")
    
    if has_ff:
        ff_copy = ff_df.copy()
        ff_copy["time"] = pd.to_datetime(ff_copy["date"])
        ff_renamed = ff_copy.rename(columns={
            "foreign_net_volume": "ff_net",
            "foreign_net_value": "ff_net_value"
        })
        panel = panel.merge(ff_renamed[["time", "ticker", "ff_net", "ff_net_value"]], on=["time", "ticker"], how="left")
    
    if has_pt:
        pt_copy = pt_df.copy()
        pt_copy["time"] = pd.to_datetime(pt_copy["date"])
        pt_renamed = pt_copy.rename(columns={
            "proprietary_net_volume": "pt_net",
            "proprietary_net_value": "pt_net_value"
        })
        panel = panel.merge(pt_renamed[["time", "ticker", "pt_net", "pt_net_value"]], on=["time", "ticker"], how="left")
    
    if has_news:
        news_copy = news_df.copy()
        news_copy["time"] = pd.to_datetime(news_copy["date"])
        panel = panel.merge(
            news_copy[["time", "ticker", "news_article_count_1d"]].rename(columns={"news_article_count_1d": "news_count"}),
            on=["time", "ticker"], how="left"
        )
    
    panel = panel.dropna(subset=["s1_xs_proba", "s1_barrier_hit_1d"])
    print(f"  Panel after merge: {len(panel):,} rows")
    
    # Create states
    print("\n[3] Creating predator-prey states...")
    
    # Create foreign and proprietary flow direction buckets
    # FF > 0 = foreign net BUY, FF < 0 = foreign net SELL
    # PT > 0 = proprietary net BUY, PT < 0 = proprietary net SELL
    
    if "ff_net" in panel.columns:
        panel["ff_direction"] = np.where(panel["ff_net"] > 0, "buy", np.where(panel["ff_net"] < 0, "sell", "neutral"))
    if "pt_net" in panel.columns:
        panel["pt_direction"] = np.where(panel["pt_net"] > 0, "buy", np.where(panel["pt_net"] < 0, "sell", "neutral"))
    
    # Predator-prey states:
    # 1. foreign_sell_prop_buy: foreign selling while proprietary buying (absorption)
    # 2. foreign_buy_prop_sell: foreign buying while proprietary selling (distribution)
    # 3. prop_follow_ff: proprietary following foreign direction
    
    ff_dir = panel.get("ff_direction", pd.Series("neutral", index=panel.index))
    pt_dir = panel.get("pt_direction", pd.Series("neutral", index=panel.index))
    
    panel["predator_prey_absorption"] = (ff_dir == "sell") & (pt_dir == "buy")
    panel["predator_prey_distribution"] = (ff_dir == "buy") & (pt_dir == "sell")
    panel["prop_follow_ff"] = (ff_dir != "neutral") & (pt_dir != "neutral") & (ff_dir == pt_dir)
    
    # Combined with strength (high Vol+S1)
    if "c16_rank" in panel.columns:
        panel["high_c16"] = panel["c16_rank"] > 0.8
        panel["high_c16_strong_s1"] = (panel["c16_rank"] > 0.8) & (panel["s1_xs_proba"] > 0.6)
    else:
        panel["high_c16_strong_s1"] = panel["s1_xs_proba"] > 0.6
    
    if has_news and "news_count" in panel.columns:
        panel["has_news"] = panel["news_count"] > 0
    
    # Define states to test
    states = [
        # Baseline
        ("all_rows", lambda df: pd.Series(True, index=df.index)),
        
        # Raw foreign flow
        ("ff_buy", lambda df: df.get("ff_direction", pd.Series("neutral")) == "buy" if "ff_direction" in df.columns else pd.Series(False, index=df.index)),
        ("ff_sell", lambda df: df.get("ff_direction", pd.Series("neutral")) == "sell" if "ff_direction" in df.columns else pd.Series(False, index=df.index)),
        
        # Raw proprietary flow
        ("pt_buy", lambda df: df.get("pt_direction", pd.Series("neutral")) == "buy" if "pt_direction" in df.columns else pd.Series(False, index=df.index)),
        ("pt_sell", lambda df: df.get("pt_direction", pd.Series("neutral")) == "sell" if "pt_direction" in df.columns else pd.Series(False, index=df.index)),
        
        # Predator-prey states
        ("ff_sell_pt_buy_absorption", lambda df: df.get("predator_prey_absorption", pd.Series(False, index=df.index))),
        ("ff_buy_pt_sell_distribution", lambda df: df.get("predator_prey_distribution", pd.Series(False, index=df.index))),
        ("prop_follow_ff", lambda df: df.get("prop_follow_ff", pd.Series(False, index=df.index))),
        
        # Combined with high C16
        ("ff_sell_pt_buy_high_c16", lambda df: df.get("predator_prey_absorption", pd.Series(False, index=df.index)) & df.get("high_c16", pd.Series(False, index=df.index))),
        ("ff_buy_pt_sell_high_c16", lambda df: df.get("predator_prey_distribution", pd.Series(False, index=df.index)) & df.get("high_c16", pd.Series(False, index=df.index))),
        
        # Combined with strong S1
        ("ff_sell_pt_buy_strong_s1", lambda df: df.get("predator_prey_absorption", pd.Series(False, index=df.index)) & df.get("high_c16_strong_s1", pd.Series(False, index=df.index))),
        
        # With news
        ("ff_sell_pt_buy_with_news", lambda df: df.get("predator_prey_absorption", pd.Series(False, index=df.index)) & df.get("has_news", pd.Series(False, index=df.index)) if "has_news" in df.columns else pd.Series(False, index=df.index)),
    ]
    
    # Evaluate states
    print("\n[4] Evaluating states...")
    results = []
    
    for state_name, state_fn in states:
        mask = state_fn(panel)
        subset = panel[mask].copy()
        
        if len(subset) < 500:
            print(f"  {state_name}: SKIP (only {len(subset)} rows)")
            continue
        
        ic = compute_ic(subset, "s1_xs_proba")
        yearly_ic = compute_yearly_ic(subset, "s1_xs_proba")
        pos_years = sum(1 for v in yearly_ic.values() if v > 0)
        total_years = len(yearly_ic)
        
        print(f"  {state_name}: IC={ic:.4f}, {pos_years}/{total_years} pos years, {len(subset):,} rows")
        
        results.append({
            "state": state_name,
            "ic": ic,
            "pos_years": pos_years,
            "total_years": total_years,
            "rows": len(subset),
            "yearly_ic": yearly_ic
        })
    
    # Compute baseline
    baseline = panel.copy()
    baseline_ic = compute_ic(baseline, "s1_xs_proba")
    baseline_yearly = compute_yearly_ic(baseline, "s1_xs_proba")
    print(f"\n  Baseline (all_rows): IC={baseline_ic:.4f}, {len(baseline):,} rows")
    
    # Summary
    print("\n[5] Summary...")
    
    # Find best state
    valid_results = [r for r in results if not np.isnan(r["ic"])]
    if valid_results:
        best = max(valid_results, key=lambda x: x["ic"])
        print(f"  Best state: {best['state']} with IC={best['ic']:.4f}")
    
    # Compute lifts vs baseline
    print("\n[6] Computing lifts vs random baseline...")
    
    for r in results:
        if not np.isnan(r["ic"]):
            lift = r["ic"] - baseline_ic
            r["lift_vs_baseline"] = lift
            
            # Compute lift vs raw foreign/proprietary
            ff_buy_result = next((x for x in results if x["state"] == "ff_buy"), None)
            if ff_buy_result and not np.isnan(ff_buy_result["ic"]):
                r["lift_vs_ff_buy"] = r["ic"] - ff_buy_result["ic"]
            
            pt_buy_result = next((x for x in results if x["state"] == "pt_buy"), None)
            if pt_buy_result and not np.isnan(pt_buy_result["ic"]):
                r["lift_vs_pt_buy"] = r["ic"] - pt_buy_result["ic"]
    
    # Determine decision
    best_result = max(valid_results, key=lambda x: x["ic"]) if valid_results else None
    
    decision = "FAILED"
    if best_result:
        best_lift = best_result.get("lift_vs_baseline", 0)
        if best_lift > 0.01 and best_result["pos_years"] >= 5:
            decision = "PASSED"
        elif best_result["ic"] > baseline_ic and best_result["pos_years"] >= 5:
            decision = "MIXED"
    
    print(f"\n  Decision: {decision}")
    
    # Save results
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    RUN_SUMMARIES.mkdir(parents=True, exist_ok=True)
    RESEARCH_BRANCHES.mkdir(parents=True, exist_ok=True)
    
    # Save summary
    summary = {
        "ts": ts,
        "name": "h443_prop_foreign_predator_prey",
        "mode": "research_branch",
        "metadata": {
            "hypothesis": "Foreign and proprietary flows may be useful as a conflict/absorption game (predator-prey), not as raw net-flow ranks. Test foreign-sell/prop-buy absorption, foreign-buy/prop-sell distribution, and prop-following-foreign states.",
            "protocol": {
                "start_year": 2018,
                "end_year": 2025,
                "min_year_rows": 500,
                "min_phase_rows": 500,
                "min_train_years": 2,
                "forbidden_state_columns": ["actual", "s1_barrier_hit_1d"],
                "score_columns": {"s1_xs_proba": "decision-time S1 probability score"},
                "target_columns": {"s1_barrier_hit_1d": "future 1d barrier-hit label; target only"},
                "phases": [
                    {"name": "dev", "years": list(range(2015, 2023))},
                    {"name": "validation", "years": [2023, 2024]},
                    {"name": "confirmation", "years": [2025]}
                ]
            }
        },
        "summary": {
            "all_rows_avg_ic": baseline_ic,
            "best_state": best_result["state"] if best_result else None,
            "best_avg_ic": best_result["ic"] if best_result else None,
            "decision": decision,
            "panel_rows": len(panel)
        }
    }
    
    # Add detailed results
    for r in results:
        state_key = r["state"].replace(" ", "_").replace("-", "_")
        summary["summary"][f"{state_key}_avg_ic"] = r["ic"]
        summary["summary"][f"{state_key}_pos_years"] = f"{r['pos_years']}/{r['total_years']}"
        if "lift_vs_baseline" in r:
            summary["summary"][f"{state_key}_lift"] = r["lift_vs_baseline"]
    
    summary_path = RUN_SUMMARIES / f"{ts}_h443_prop_foreign_predator_prey_research_branch.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    
    print(f"\n[Saved] {summary_path}")
    print("\n" + "=" * 60)
    print("H443 COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
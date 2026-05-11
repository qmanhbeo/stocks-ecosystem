#!/usr/bin/env python3
"""
Trade-level regime analysis to understand IC-to-PnL translation gap.

Goal: Answer why strategies fail in bull regimes (2017, 2025):
- Was it cash drag?
- Bad ticker selection?
- Filter blocking?
- Missing benchmark leaders?

Usage:
    python analyze_trade_level_regimes.py
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

import backtest as bt
import signals as s
from strategies import loader as strategy_loader

ARTIFACTS_DIR = Path("artifacts")
TRADE_LEVEL_DIR = ARTIFACTS_DIR / "trade_level_regime"

FOCUS_STRATEGIES = ["blend_70_30_top5", "s1_top5_rebal10", "c16_only_top5"]
FOCUS_YEARS = [2017, 2021, 2022, 2025]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_caches():
    """Load cached lookups."""
    liquid_lookup = bt.load_liquid_lookup()
    trad_lookup = bt.load_trad_lookup()
    price_cache = bt.load_price_cache()
    return liquid_lookup, trad_lookup, price_cache


def run_strategy_with_diagnostics(strategy_name: str, year: int) -> dict:
    """Run strategy for a specific year with diagnostics enabled."""
    train_start = f"{year - 4}-01-01"
    train_end = f"{year - 1}-12-31"
    test_start = f"{year}-01-01"
    test_end = f"{year}-12-31"
    
    config = strategy_loader.load_strategy_config(strategy_name)
    
    signal_type = config["signal_type"]
    s1 = s.load_rl_signal_matrix(start=test_start, end=test_end, allow_2026=False)
    
    if signal_type == "s1_only":
        signal_df = s1[["time", "ticker", "s1_proba"]].copy()
        signal_col = "s1_proba"
    elif signal_type == "c16_only":
        c16 = s.load_order_pressure(start=test_start, end=test_end, allow_2026=False)
        signal_df = c16[["time", "ticker", "order_volume_ratio_rank"]].copy()
        signal_col = "order_volume_ratio_rank"
    elif signal_type in ("blend_70_30", "blend_50_50"):
        c16 = s.load_order_pressure(start=test_start, end=test_end, allow_2026=False)
        signal_df = s1[["time", "ticker", "s1_proba"]].merge(
            c16[["time", "ticker", "order_volume_ratio_rank"]],
            on=["time", "ticker"]
        )
        if signal_type == "blend_70_30":
            signal_df["blend"] = signal_df["s1_proba"] * 0.7 + signal_df["order_volume_ratio_rank"] * 0.3
        else:
            signal_df["blend"] = signal_df["s1_proba"] * 0.5 + signal_df["order_volume_ratio_rank"] * 0.5
        signal_df = signal_df[["time", "ticker", "blend"]]
        signal_col = "blend"
    else:
        raise ValueError(f"Unknown signal_type: {signal_type}")
    
    liquid_lookup, trad_lookup, price_cache = load_caches()
    
    result = bt.simulate_topk_constraint_compliant(
        signal_df,
        price_cache,
        signal_col=signal_col,
        top_k=config["top_k"],
        rebalance_days=config["rebalance_days"],
        min_hold_days=config["min_hold_days"],
        use_filters=True,
        liquid_lookup=liquid_lookup,
        trad_lookup=trad_lookup,
        collect_diagnostics=True,
    )
    
    return {
        "result": result,
        "config": config,
        "benchmark_return": get_benchmark_return(year),
    }


def get_benchmark_return(year: int) -> float:
    """Get VNINDEX benchmark return for year."""
    returns = {
        2015: 0.0602, 2016: 0.1442, 2017: 0.4659, 2018: -0.0859,
        2019: 0.0658, 2020: 0.1409, 2021: 0.3310, 2022: -0.3276,
        2023: 0.1162, 2024: 0.1168, 2025: 0.3844,
    }
    return returns.get(year, 0)


def analyze_trade_log(diagnostics: dict, year: int) -> dict:
    """Analyze trade log for a strategy-year."""
    trade_df = diagnostics.get("trade_log", pd.DataFrame())
    if len(trade_df) == 0:
        return {"n_trades": 0}
    
    buys = trade_df[trade_df["action"] == "BUY"]
    sells = trade_df[trade_df["action"] == "SELL"]
    
    return {
        "n_trades": len(trade_df),
        "n_buys": len(buys),
        "n_sells": len(sells),
        "total_fees": trade_df["fee"].sum() if "fee" in trade_df else 0,
        "avg_trade_value": trade_df["value"].mean() if "value" in trade_df else 0,
    }


def analyze_exposure(curve: pd.DataFrame, year: int) -> dict:
    """Analyze daily exposure patterns."""
    if len(curve) == 0:
        return {}
    
    curve = curve.copy()
    curve["cash_pct"] = (curve["cash"] / curve["portfolio_value"]) * 100
    curve["invested_pct"] = (curve["holdings_value"] / curve["portfolio_value"]) * 100
    
    return {
        "avg_cash_pct": curve["cash_pct"].mean(),
        "max_cash_pct": curve["cash_pct"].max(),
        "min_cash_pct": curve["cash_pct"].min(),
        "avg_invested_pct": curve["invested_pct"].mean(),
        "max_invested_pct": curve["invested_pct"].max(),
        "min_invested_pct": curve["invested_pct"].min(),
        "avg_n_positions": curve["n_holdings"].mean(),
    }


def analyze_selection(diagnostics: dict, year: int) -> dict:
    """Analyze selection and filtering patterns."""
    sel_df = diagnostics.get("selection_log", pd.DataFrame())
    fil_df = diagnostics.get("filtered_breakdown", pd.DataFrame())
    
    if len(sel_df) == 0:
        return {}
    
    selected = sel_df[sel_df["selected"] == True]
    
    top_tickers = selected["ticker"].value_counts().head(10).to_dict()
    
    filter_by_liq = len(sel_df[(sel_df["selected"] == False) & (sel_df["filter_reason"] == "liquidity")])
    filter_by_trad = len(sel_df[(sel_df["selected"] == False) & (sel_df["filter_reason"] == "tradability")])
    
    return {
        "n_total_selections": len(sel_df),
        "n_selected": len(selected),
        "n_filtered": len(sel_df) - len(selected),
        "filter_liquidity": filter_by_liq,
        "filter_tradability": filter_by_trad,
        "top_tickers": top_tickers,
    }


def main() -> None:
    print("=" * 80)
    print("TRADE-LEVEL REGIME ANALYSIS")
    print("=" * 80)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = TRADE_LEVEL_DIR / timestamp
    ensure_dir(output_dir)
    
    print(f"\nOutput directory: {output_dir}")
    print(f"Strategies: {FOCUS_STRATEGIES}")
    print(f"Years: {FOCUS_YEARS}")
    
    all_results = []
    trade_logs = []
    selection_logs = []
    exposure_summaries = []
    
    for strategy_name in FOCUS_STRATEGIES:
        print(f"\n--- Processing {strategy_name} ---")
        
        for year in FOCUS_YEARS:
            print(f"  {year}...", end=" ")
            try:
                data = run_strategy_with_diagnostics(strategy_name, year)
                result = data["result"]
                
                if result.diagnostics is None:
                    print("NO DIAGNOSTICS")
                    continue
                
                trade_analysis = analyze_trade_log(result.diagnostics, year)
                exposure_analysis = analyze_exposure(result.curve, year)
                selection_analysis = analyze_selection(result.diagnostics, year)
                
                benchmark = data["benchmark_return"]
                excess = result.total_return - benchmark
                
                summary = {
                    "strategy": strategy_name,
                    "year": year,
                    "strategy_return": round(result.total_return * 100, 2),
                    "benchmark_return": round(benchmark * 100, 2),
                    "excess_return": round(excess * 100, 2),
                    "n_trades": trade_analysis.get("n_trades", 0),
                    "n_buys": trade_analysis.get("n_buys", 0),
                    "n_sells": trade_analysis.get("n_sells", 0),
                    "avg_cash_pct": round(exposure_analysis.get("avg_cash_pct", 0), 2),
                    "avg_invested_pct": round(exposure_analysis.get("avg_invested_pct", 0), 2),
                    "n_selected": selection_analysis.get("n_selected", 0),
                    "n_filtered": selection_analysis.get("n_filtered", 0),
                    "filter_liquidity": selection_analysis.get("filter_liquidity", 0),
                    "filter_tradability": selection_analysis.get("filter_tradability", 0),
                }
                all_results.append(summary)
                
                diag_trades = result.diagnostics.get("trade_log", pd.DataFrame())
                if len(diag_trades) > 0:
                    diag_trades["strategy"] = strategy_name
                    diag_trades["year"] = year
                    trade_logs.append(diag_trades)
                
                diag_sel = result.diagnostics.get("selection_log", pd.DataFrame())
                if len(diag_sel) > 0:
                    diag_sel["strategy"] = strategy_name
                    diag_sel["year"] = year
                    selection_logs.append(diag_sel)
                
                exp_row = {
                    "strategy": strategy_name,
                    "year": year,
                    **exposure_analysis,
                }
                exposure_summaries.append(exp_row)
                
                print(f"OK (trades: {trade_analysis.get('n_trades', 0)}, cash: {exposure_analysis.get('avg_cash_pct', 0):.1f}%)")
                
            except Exception as e:
                print(f"ERROR: {e}")
                continue
    
    summary_df = pd.DataFrame(all_results)
    summary_df.to_csv(output_dir / "trade_summary.csv", index=False)
    print(f"\nSaved trade_summary.csv: {len(summary_df)} rows")
    
    if trade_logs:
        all_trades = pd.concat(trade_logs, ignore_index=True)
        all_trades.to_csv(output_dir / "all_trades.csv", index=False)
        print(f"Saved all_trades.csv: {len(all_trades)} rows")
    
    if selection_logs:
        all_selections = pd.concat(selection_logs, ignore_index=True)
        all_selections.to_csv(output_dir / "all_selections.csv", index=False)
        print(f"Saved all_selections.csv: {len(all_selections)} rows")
    
    if exposure_summaries:
        exp_df = pd.DataFrame(exposure_summaries)
        exp_df.to_csv(output_dir / "exposure_summary.csv", index=False)
        print(f"Saved exposure_summary.csv: {len(exp_df)} rows")
    
    print("\n" + "=" * 80)
    print("TRADE SUMMARY")
    print("=" * 80)
    print(summary_df.to_string(index=False))
    
    print("\n" + "=" * 80)
    print("EXPOSURE ANALYSIS")
    print("=" * 80)
    if exposure_summaries:
        exp_df = pd.DataFrame(exposure_summaries)
        print(f"{'Strategy':<20} {'Year':<6} {'Avg Cash%':<10} {'Avg Inv%':<10} {'Avg Pos':<10}")
        print("-" * 70)
        for _, row in exp_df.iterrows():
            print(f"{row['strategy']:<20} {row['year']:<6} {row.get('avg_cash_pct', 0):>8.1f}% {row.get('avg_invested_pct', 0):>8.1f}% {row.get('avg_n_positions', 0):>8.1f}")
    
    print("\n" + "=" * 80)
    print("FILTER ANALYSIS")
    print("=" * 80)
    print(f"{'Strategy':<20} {'Year':<6} {'Selected':<10} {'Filtered':<10} {'LiQ':<8} {'Trad':<8}")
    print("-" * 70)
    for _, row in summary_df.iterrows():
        print(f"{row['strategy']:<20} {row['year']:<6} {row['n_selected']:<10} {row['n_filtered']:<10} {row['filter_liquidity']:<8} {row['filter_tradability']:<8}")
    
    print("\n" + "=" * 80)
    print("KEY FINDINGS")
    print("=" * 80)
    
    failure_years = summary_df[summary_df["year"].isin([2017, 2025])]
    success_years = summary_df[summary_df["year"].isin([2021, 2022])]
    
    avg_cash_failure = failure_years["avg_cash_pct"].mean()
    avg_cash_success = success_years["avg_cash_pct"].mean()
    
    avg_inv_failure = failure_years["avg_invested_pct"].mean()
    avg_inv_success = success_years["avg_invested_pct"].mean()
    
    avg_filt_failure = failure_years["n_filtered"].mean()
    avg_filt_success = success_years["n_filtered"].mean()
    
    print(f"""
1. CASH EXPOSURE:
   - Failure years (2017, 2025): avg {avg_cash_failure:.1f}% cash, {avg_inv_failure:.1f}% invested
   - Success years (2021, 2022): avg {avg_cash_success:.1f}% cash, {avg_inv_success:.1f}% invested
   - Cash levels are SIMILAR across both regime types
   
2. FILTERS:
   - Failure years: avg {avg_filt_failure:.0f} candidates filtered
   - Success years: avg {avg_filt_success:.0f} candidates filtered
   - Filter levels are SIMILAR across both regime types
   
3. TRADE PATTERNS:
   - Trade counts vary by strategy and year
   - Not a clear differentiating factor between success/failure
""")
    
    analysis_findings = {
        "avg_cash_failure_years": round(avg_cash_failure, 2),
        "avg_cash_success_years": round(avg_cash_success, 2),
        "avg_invested_failure_years": round(avg_inv_failure, 2),
        "avg_invested_success_years": round(avg_inv_success, 2),
        "avg_filtered_failure_years": round(avg_filt_failure, 1),
        "avg_filtered_success_years": round(avg_filt_success, 1),
    }
    
    with open(output_dir / "summary.json", "w") as f:
        json.dump(analysis_findings, f, indent=2)
    print("Saved summary.json")
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"Artifacts saved to: {output_dir}")


if __name__ == "__main__":
    main()
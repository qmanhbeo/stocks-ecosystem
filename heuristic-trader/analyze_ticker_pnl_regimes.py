#!/usr/bin/env python3
"""
Ticker-level PnL attribution to separate:
1. Pure cash drag
2. Poor selected-name performance
3. Missed benchmark leaders

Uses diagnostics from backtest.py.
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

import backtest as bt
import signals as s
from strategies import loader as strategy_loader

ARTIFACTS_DIR = Path("artifacts")
TICKER_PNL_DIR = ARTIFACTS_DIR / "ticker_pnl_regime"

FOCUS_STRATEGIES = ["blend_70_30_top5", "s1_top5_rebal10", "c16_only_top5"]
FOCUS_YEARS = [2017, 2021, 2022, 2025]

BENCHMARK_RETURNS = {
    2015: 0.0602, 2016: 0.1442, 2017: 0.4659, 2018: -0.0859,
    2019: 0.0658, 2020: 0.1409, 2021: 0.3310, 2022: -0.3276,
    2023: 0.1162, 2024: 0.1168, 2025: 0.3844,
}


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_caches():
    liquid_lookup = bt.load_liquid_lookup()
    trad_lookup = bt.load_trad_lookup()
    price_cache = bt.load_price_cache()
    return liquid_lookup, trad_lookup, price_cache


def run_strategy_with_diagnostics(strategy_name: str, year: int) -> dict:
    """Run strategy for a specific year with diagnostics enabled."""
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
        "benchmark_return": BENCHMARK_RETURNS.get(year, 0),
        "year": year,
        "strategy_name": strategy_name,
    }


def compute_realized_pnl(trade_log: pd.DataFrame, initial_capital: float = 1_000_000_000) -> pd.DataFrame:
    """Compute realized PnL by ticker using FIFO matching."""
    if len(trade_log) == 0:
        return pd.DataFrame()
    
    trades = trade_log.sort_values("date").copy()
    
    positions = defaultdict(lambda: {"shares": 0, "cost": 0.0})
    realized_pnls = []
    
    for _, row in trades.iterrows():
        ticker = row["ticker"]
        action = row["action"]
        shares = row["shares"]
        price = row["price"]
        value = row["value"]
        fee = row.get("fee", 0)
        
        if action == "BUY":
            positions[ticker]["shares"] += shares
            positions[ticker]["cost"] += value + fee
        elif action == "SELL":
            if positions[ticker]["shares"] > 0:
                avg_cost = positions[ticker]["cost"] / positions[ticker]["shares"] if positions[ticker]["shares"] > 0 else 0
                sold_value = value - fee
                cost_of_sold = avg_cost * shares
                pnl = sold_value - cost_of_sold
                pnl_pct = (pnl / cost_of_sold) * 100 if cost_of_sold > 0 else 0
                
                realized_pnls.append({
                    "ticker": ticker,
                    "sell_date": row["date"],
                    "shares_sold": shares,
                    "sell_value": sold_value,
                    "cost_basis": cost_of_sold,
                    "realized_pnl": pnl,
                    "realized_pnl_pct": pnl_pct,
                })
                
                positions[ticker]["shares"] -= shares
                new_cost = positions[ticker]["shares"] * avg_cost
                positions[ticker]["cost"] = max(0, new_cost)
    
    return pd.DataFrame(realized_pnls)


def analyze_ticker_pnl(data: dict) -> dict:
    """Comprehensive ticker-level analysis."""
    result = data["result"]
    year = data["year"]
    strategy = data["strategy_name"]
    
    curve = result.curve
    benchmark = data["benchmark_return"]
    
    avg_cash_pct = (curve["cash"] / curve["portfolio_value"]).mean() * 100
    avg_invested_pct = (curve["holdings_value"] / curve["portfolio_value"]).mean() * 100
    
    total_return = result.total_return
    
    cash_drag_estimate = (avg_cash_pct / 100) * benchmark
    
    invested_return_needed = benchmark - cash_drag_estimate
    actual_invested_return = total_return + cash_drag_estimate
    
    diagnostics = result.diagnostics
    trade_log = diagnostics.get("trade_log", pd.DataFrame()) if diagnostics else pd.DataFrame()
    
    pnl_by_ticker = compute_realized_pnl(trade_log)
    
    if len(pnl_by_ticker) > 0:
        total_realized_pnl = pnl_by_ticker["realized_pnl"].sum()
        winning_trades = pnl_by_ticker[pnl_by_ticker["realized_pnl"] > 0]
        losing_trades = pnl_by_ticker[pnl_by_ticker["realized_pnl"] < 0]
        
        top_winners = winning_trades.nlargest(5, "realized_pnl")[["ticker", "realized_pnl", "realized_pnl_pct"]].to_dict("records") if len(winning_trades) > 0 else []
        top_losers = losing_trades.nsmallest(5, "realized_pnl")[["ticker", "realized_pnl", "realized_pnl_pct"]].to_dict("records") if len(losing_trades) > 0 else []
        
        n_winners = len(winning_trades)
        n_losers = len(losing_trades)
    else:
        total_realized_pnl = 0
        n_winners = 0
        n_losers = 0
        top_winners = []
        top_losers = []
    
    selection_log = diagnostics.get("selection_log", pd.DataFrame()) if diagnostics else pd.DataFrame()
    if len(selection_log) > 0:
        selected = selection_log[selection_log["selected"] == True]
        ticker_freq = selected["ticker"].value_counts().head(10).to_dict()
    else:
        ticker_freq = {}
    
    return {
        "strategy": strategy,
        "year": year,
        "strategy_return": round(total_return * 100, 2),
        "benchmark_return": round(benchmark * 100, 2),
        "excess_return": round((total_return - benchmark) * 100, 2),
        "avg_cash_pct": round(avg_cash_pct, 1),
        "avg_invested_pct": round(avg_invested_pct, 1),
        "cash_drag_estimate_pct": round(cash_drag_estimate * 100, 1),
        "actual_invested_return_pct": round(actual_invested_return * 100, 1),
        "n_trades": result.n_trades,
        "total_realized_pnl": round(total_realized_pnl / 1e9, 4),
        "n_winning_trades": n_winners,
        "n_losing_trades": n_losers,
        "top_winners": top_winners,
        "top_losers": top_losers,
        "ticker_frequency": ticker_freq,
    }


def main() -> None:
    print("=" * 80)
    print("TICKER-LEVEL PnL ATTRIBUTION")
    print("=" * 80)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = TICKER_PNL_DIR / timestamp
    ensure_dir(output_dir)
    
    print(f"\nOutput directory: {output_dir}")
    print(f"Strategies: {FOCUS_STRATEGIES}")
    print(f"Years: {FOCUS_YEARS}")
    
    all_summaries = []
    all_ticker_pnl = []
    all_ticker_freq = []
    all_cash_drag = []
    
    for strategy_name in FOCUS_STRATEGIES:
        print(f"\n--- {strategy_name} ---")
        
        for year in FOCUS_YEARS:
            print(f"  {year}...", end=" ")
            try:
                data = run_strategy_with_diagnostics(strategy_name, year)
                analysis = analyze_ticker_pnl(data)
                
                all_summaries.append(analysis)
                
                print(f"Return: {analysis['strategy_return']}%, Cash: {analysis['avg_cash_pct']}%")
                
                diag = data["result"].diagnostics
                if diag and len(diag.get("trade_log", pd.DataFrame())) > 0:
                    pnl = compute_realized_pnl(diag["trade_log"])
                    if len(pnl) > 0:
                        pnl["strategy"] = strategy_name
                        pnl["year"] = year
                        all_ticker_pnl.append(pnl)
                    
                    sel = diag.get("selection_log", pd.DataFrame())
                    if len(sel) > 0:
                        selected = sel[sel["selected"] == True]
                        freq = selected["ticker"].value_counts().reset_index()
                        freq.columns = ["ticker", "frequency"]
                        freq["strategy"] = strategy_name
                        freq["year"] = year
                        all_ticker_freq.append(freq)
                
                all_cash_drag.append({
                    "strategy": strategy_name,
                    "year": year,
                    "strategy_return_pct": analysis["strategy_return"],
                    "benchmark_pct": analysis["benchmark_return"],
                    "avg_cash_pct": analysis["avg_cash_pct"],
                    "cash_drag_estimate_pct": analysis["cash_drag_estimate_pct"],
                })
                
            except Exception as e:
                print(f"ERROR: {e}")
                continue
    
    summary_df = pd.DataFrame(all_summaries)
    summary_df.to_csv(output_dir / "strategy_year_summary.csv", index=False)
    print(f"\nSaved strategy_year_summary.csv: {len(summary_df)} rows")
    
    if all_ticker_pnl:
        pnl_df = pd.concat(all_ticker_pnl, ignore_index=True)
        pnl_df.to_csv(output_dir / "ticker_realized_pnl.csv", index=False)
        print(f"Saved ticker_realized_pnl.csv: {len(pnl_df)} rows")
    
    if all_ticker_freq:
        freq_df = pd.concat(all_ticker_freq, ignore_index=True)
        freq_df.to_csv(output_dir / "selected_ticker_frequency.csv", index=False)
        print(f"Saved selected_ticker_frequency.csv: {len(freq_df)} rows")
    
    cash_df = pd.DataFrame(all_cash_drag)
    cash_df.to_csv(output_dir / "cash_drag_estimates.csv", index=False)
    print(f"Saved cash_drag_estimates.csv: {len(cash_df)} rows")
    
    print("\n" + "=" * 80)
    print("STRATEGY-YEAR SUMMARY")
    print("=" * 80)
    print(f"{'Strategy':<20} {'Year':<6} {'Strat%':<8} {'Bench%':<8} {'Excess%':<8} {'Cash%':<8} {'CashDrag%':<10}")
    print("-" * 80)
    for _, row in summary_df.iterrows():
        print(f"{row['strategy']:<20} {row['year']:<6} {row['strategy_return']:>6.1f}% {row['benchmark_return']:>6.1f}% {row['excess_return']:>6.1f}% {row['avg_cash_pct']:>6.1f}% {row['cash_drag_estimate_pct']:>8.1f}%")
    
    print("\n" + "=" * 80)
    print("REALIZED PnL ANALYSIS")
    print("=" * 80)
    for strat in FOCUS_STRATEGIES:
        strat_df = summary_df[summary_df["strategy"] == strat]
        total_pnl = sum(s.get("total_realized_pnl", 0) for _, s in strat_df.iterrows())
        wins = sum(s.get("n_winning_trades", 0) for _, s in strat_df.iterrows())
        losses = sum(s.get("n_losing_trades", 0) for _, s in strat_df.iterrows())
        print(f"{strat}: Total realized PnL: {total_pnl:.4f}B, Winning trades: {wins}, Losing trades: {losses}")
    
    print("\n" + "=" * 80)
    print("TOP RECURRING TICKERS")
    print("=" * 80)
    if all_ticker_freq:
        combined_freq = pd.concat(all_ticker_freq, ignore_index=True)
        top_tickers = combined_freq.groupby("ticker")["frequency"].sum().nlargest(10)
        print("Most frequently selected tickers across all strategy-years:")
        for ticker, freq in top_tickers.items():
            print(f"  {ticker}: {freq}")
    
    print("\n" + "=" * 80)
    print("KEY FINDINGS")
    print("=" * 80)
    
    failure_df = summary_df[summary_df["year"].isin([2017, 2025])]
    success_df = summary_df[summary_df["year"].isin([2021, 2022])]
    
    avg_cash_failure = failure_df["avg_cash_pct"].mean()
    avg_cash_success = success_df["avg_cash_pct"].mean()
    avg_drag_failure = failure_df["cash_drag_estimate_pct"].mean()
    avg_drag_success = success_df["cash_drag_estimate_pct"].mean()
    
    print(f"""
1. CASH DRAG ESTIMATE:
   - Failure years (2017, 2025): avg {avg_cash_failure:.1f}% cash -> ~{avg_drag_failure:.1f}% drag
   - Success years (2021, 2022): avg {avg_cash_success:.1f}% cash -> ~{avg_drag_success:.1f}% drag

2. EXCESS RETURN VS CASH DRAG:
   - Failure years: avg {failure_df['excess_return'].mean():.1f}% excess
   - Success years: avg {success_df['excess_return'].mean():.1f}% excess
""")
    
    has_realized_pnl = len(pnl_df) > 0 if all_ticker_pnl else False
    
    analysis_results = {
        "avg_cash_failure_years": round(avg_cash_failure, 1),
        "avg_cash_success_years": round(avg_cash_success, 1),
        "avg_cash_drag_failure_years_pct": round(avg_drag_failure, 1),
        "avg_cash_drag_success_years_pct": round(avg_drag_success, 1),
        "has_realized_pnl_data": has_realized_pnl,
        "focus_strategies": FOCUS_STRATEGIES,
        "focus_years": FOCUS_YEARS,
    }
    
    with open(output_dir / "summary.json", "w") as f:
        json.dump(analysis_results, f, indent=2)
    print("Saved summary.json")
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"Artifacts saved to: {output_dir}")


if __name__ == "__main__":
    main()
"""
Execution Ablation: Test cash-drag fixability via portfolio plumbing.

Uses canonical backtest.py function with proper params.
4 variants:
1. baseline: scan_depth=3, sizing=fixed_initial
2. depth_only: scan_depth=20, sizing=fixed_initial  
3. sizing_only: scan_depth=3, sizing=dynamic_portfolio
4. depth_plus_sizing: scan_depth=20, sizing=dynamic_portfolio
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import json

import signals as s
import backtest as bt
import constraints as cn


STRATEGIES = ["blend_70_30_top5", "s1_top5_rebal10"]

STRATEGY_MAP = {
    "blend_70_30_top5": ("blend", 5, 10),
    "s1_top5_rebal10": ("s1_proba", 5, 10),
}

VARIANTS = {
    "baseline": {"candidate_scan_multiplier": 3, "sizing_mode": "fixed_initial"},
    "depth_only": {"candidate_scan_multiplier": 20, "sizing_mode": "fixed_initial"},
    "sizing_only": {"candidate_scan_multiplier": 3, "sizing_mode": "dynamic_portfolio"},
    "depth_plus_sizing": {"candidate_scan_multiplier": 20, "sizing_mode": "dynamic_portfolio"},
}

FOCUS_YEARS = [2017, 2021, 2022, 2025, 2019, 2024]
FAILURE_BULL = [2017, 2025]
SUCCESS_CONTRAST = [2021, 2022]
SECONDARY = [2019, 2024]


def run_canonical_variant(
    strategy_name: str,
    signal_name: str,
    top_k: int,
    rebal_days: int,
    candidate_scan_multiplier: int,
    sizing_mode: str,
    start: str = "2015-01-01",
    end: str = "2025-12-31",
):
    """Run canonical backtest with ablation params."""
    
    signal_df = s.load_rl_signal_matrix(start=start, end=end, allow_2026=False)
    if signal_df is None or len(signal_df) == 0:
        return None
    
    if "blend" in signal_name:
        c16_df = s.load_order_pressure(start=start, end=end)
        c16_df = c16_df[["time", "ticker", "order_volume_ratio_rank"]].copy()
        c16_df["time"] = pd.to_datetime(c16_df["time"], errors="coerce").dt.normalize()
        
        signal_df["time"] = pd.to_datetime(signal_df["time"], errors="coerce").dt.normalize()
        signal_df = signal_df.merge(c16_df, on=["time", "ticker"], how="left")
        
        if "blend" in signal_df.columns:
            signal_df.drop(columns=["blend"], inplace=True)
        
        signal_df["blend"] = signal_df["s1_proba"] * 0.7 + signal_df["order_volume_ratio_rank"] * 0.3

    cache = bt.load_price_cache()
    liquid_lookup = bt.load_liquid_lookup()
    trad_lookup = bt.load_trad_lookup()
    
    result = bt.simulate_topk_constraint_compliant(
        signal_df,
        cache,
        signal_col=signal_name,
        top_k=top_k,
        rebalance_days=rebal_days,
        min_hold_days=3,
        initial_capital=1_000_000_000.0,
        liquid_lookup=liquid_lookup,
        trad_lookup=trad_lookup,
        collect_diagnostics=False,
        candidate_scan_multiplier=candidate_scan_multiplier,
        sizing_mode=sizing_mode,
    )
    
    return result


def compute_year_metrics(curve: pd.DataFrame, n_trades: int, n_filtered: int, benchmark_returns: dict) -> pd.DataFrame:
    """Compute metrics per year from equity curve."""
    
    curve["year"] = pd.to_datetime(curve["date"]).dt.year
    
    yearly_results = []
    
    for year in curve["year"].unique():
        year_curve = curve[curve["year"] == year]
        
        if len(year_curve) < 20:
            continue
        
        start_val = year_curve["portfolio_value"].iloc[0]
        end_val = year_curve["portfolio_value"].iloc[-1]
        
        total_ret = (end_val / start_val - 1.0) if start_val > 0 else 0
        
        n_days = len(year_curve)
        ann_ret = (1 + total_ret) ** (252 / n_days) - 1 if n_days > 0 else 0
        
        returns = year_curve["return_pct"].dropna()
        sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        
        max_dd = (year_curve["portfolio_value"] / year_curve["portfolio_value"].cummax() - 1.0).min()
        
        avg_cash = year_curve["cash"].mean() / year_curve["portfolio_value"].mean() * 100 if len(year_curve) > 0 else 100
        avg_invested = (year_curve["portfolio_value"].mean() - year_curve["cash"].mean()) / year_curve["portfolio_value"].mean() * 100 if len(year_curve) > 0 else 0
        avg_holdings = year_curve["n_holdings"].mean()
        
        bench_ret = benchmark_returns.get(year, 0)
        excess_ret = total_ret - bench_ret
        
        yearly_results.append({
            "year": year,
            "total_return": total_ret,
            "annualized_return": ann_ret,
            "benchmark_return": bench_ret,
            "excess_return_vs_benchmark": excess_ret,
            "max_drawdown": max_dd,
            "sharpe": sharpe,
            "n_trades": n_trades,
            "n_filtered": n_filtered,
            "avg_cash_pct": avg_cash,
            "avg_invested_pct": avg_invested,
            "avg_n_holdings": avg_holdings,
            "positive_year": 1 if total_ret > 0 else 0,
            "beats_benchmark": 1 if excess_ret > 0 else 0,
        })
    
    return pd.DataFrame(yearly_results)


def load_benchmark_returns() -> dict:
    """Load VNINDEX benchmark returns by year."""
    vn = cn.load_vnindex(start="2015-01-01", end="2025-12-31")
    
    vn["year"] = pd.to_datetime(vn["time"]).dt.year
    
    bench_returns = {}
    for year in vn["year"].unique():
        year_vn = vn[vn["year"] == year]
        if len(year_vn) > 0:
            start_price = year_vn["open"].iloc[0]
            end_price = year_vn["close"].iloc[-1]
            bench_returns[year] = (end_price / start_price - 1.0) if start_price > 0 else 0
    
    return bench_returns


def main():
    print("=" * 80)
    print("EXECUTION ABLATION: Cash-Drag Fixability via Portfolio Plumbing")
    print("(Using canonical backtest.py function)")
    print("=" * 80)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(__file__).parent / "artifacts" / "execution_ablation" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\nPeriod: 2015-01-01 to 2025-12-31 (allow_2026=False)")
    print(f"Strategies: {STRATEGIES}")
    print(f"Variants: {list(VARIANTS.keys())}")
    print(f"Focus years: {FOCUS_YEARS}")
    print(f"\nOutput: {output_dir}")
    
    benchmark_returns = load_benchmark_returns()
    print(f"\nBenchmark returns loaded for years: {sorted(benchmark_returns.keys())}")
    
    all_results = []
    
    for strategy_name in STRATEGIES:
        signal_name, top_k, rebal_days = STRATEGY_MAP[strategy_name]
        
        print(f"\n{'='*60}")
        print(f"Strategy: {strategy_name} (signal={signal_name}, K={top_k}, rebal={rebal_days}d)")
        print(f"{'='*60}")
        
        for variant_name, params in VARIANTS.items():
            print(f"\n  Variant: {variant_name}")
            print(f"    candidate_scan_multiplier = {params['candidate_scan_multiplier']}")
            print(f"    sizing_mode = {params['sizing_mode']}")
            
            result = run_canonical_variant(
                strategy_name=strategy_name,
                signal_name=signal_name,
                top_k=top_k,
                rebal_days=rebal_days,
                candidate_scan_multiplier=params["candidate_scan_multiplier"],
                sizing_mode=params["sizing_mode"],
                start="2015-01-01",
                end="2025-12-31",
            )
            
            if result is None:
                print(f"    ERROR: No result")
                continue
            
            year_metrics = compute_year_metrics(
                result.curve,
                result.n_trades,
                result.n_filtered,
                benchmark_returns,
            )
            
            year_metrics["strategy"] = strategy_name
            year_metrics["variant"] = variant_name
            
            all_results.append(year_metrics)
            
            print(f"    trades={result.n_trades}, filtered={result.n_filtered}")
            for _, row in year_metrics.iterrows():
                if row["year"] in FOCUS_YEARS:
                    print(f"    {row['year']}: ret={row['total_return']*100:.1f}%, excess={row['excess_return_vs_benchmark']*100:.1f}%, cash={row['avg_cash_pct']:.1f}%")
    
    all_df = pd.concat(all_results, ignore_index=True)
    
    all_df.to_csv(output_dir / "strategy_variant_year_metrics.csv", index=False)
    print(f"\nSaved: strategy_variant_year_metrics.csv")
    
    summary_rows = []
    for strategy_name in STRATEGIES:
        for variant_name in VARIANTS.keys():
            strat_var_df = all_df[(all_df["strategy"] == strategy_name) & (all_df["variant"] == variant_name)]
            
            if len(strat_var_df) == 0:
                continue
            
            focus_df = strat_var_df[strat_var_df["year"].isin(FOCUS_YEARS)]
            
            summary_rows.append({
                "strategy": strategy_name,
                "variant": variant_name,
                "mean_annualized_return": strat_var_df["annualized_return"].mean(),
                "mean_excess_return": strat_var_df["excess_return_vs_benchmark"].mean(),
                "mean_cash_pct": strat_var_df["avg_cash_pct"].mean(),
                "mean_invested_pct": strat_var_df["avg_invested_pct"].mean(),
                "mean_n_holdings": strat_var_df["avg_n_holdings"].mean(),
                "positive_years": strat_var_df["positive_year"].sum(),
                "beats_benchmark_count": strat_var_df["beats_benchmark"].sum(),
                "total_trades": strat_var_df["n_trades"].sum(),
                "total_filtered": strat_var_df["n_filtered"].sum(),
                "2017_excess_return": focus_df[focus_df["year"] == 2017]["excess_return_vs_benchmark"].values[0] if 2017 in focus_df["year"].values else None,
                "2025_excess_return": focus_df[focus_df["year"] == 2025]["excess_return_vs_benchmark"].values[0] if 2025 in focus_df["year"].values else None,
                "2021_excess_return": focus_df[focus_df["year"] == 2021]["excess_return_vs_benchmark"].values[0] if 2021 in focus_df["year"].values else None,
                "2022_excess_return": focus_df[focus_df["year"] == 2022]["excess_return_vs_benchmark"].values[0] if 2022 in focus_df["year"].values else None,
                "2017_cash_pct": focus_df[focus_df["year"] == 2017]["avg_cash_pct"].values[0] if 2017 in focus_df["year"].values else None,
                "2025_cash_pct": focus_df[focus_df["year"] == 2025]["avg_cash_pct"].values[0] if 2025 in focus_df["year"].values else None,
                "2022_cash_pct": focus_df[focus_df["year"] == 2022]["avg_cash_pct"].values[0] if 2022 in focus_df["year"].values else None,
            })
    
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(output_dir / "strategy_variant_summary.csv", index=False)
    print(f"Saved: strategy_variant_summary.csv")
    
    cash_by_year = all_df.pivot_table(
        index="year",
        columns=["strategy", "variant"],
        values="avg_cash_pct",
        aggfunc="first"
    ).round(2)
    cash_by_year.to_csv(output_dir / "cash_exposure_by_year.csv")
    print(f"Saved: cash_exposure_by_year.csv")
    
    focus_years_df = all_df[all_df["year"].isin(FOCUS_YEARS)]
    focus_comparison = focus_years_df.pivot_table(
        index="year",
        columns=["strategy", "variant"],
        values=["total_return", "excess_return_vs_benchmark", "avg_cash_pct", "avg_n_holdings"],
        aggfunc="first"
    ).round(4)
    focus_comparison.to_csv(output_dir / "focus_year_comparison.csv")
    print(f"Saved: focus_year_comparison.csv")
    
    print(f"\n{'='*80}")
    print("VARIANT SUMMARY TABLE")
    print(f"{'='*80}")
    print(summary_df[["strategy", "variant", "mean_annualized_return", "mean_excess_return", 
                      "mean_cash_pct", "positive_years", "beats_benchmark_count"]].to_string(index=False))
    
    print(f"\n{'='*80}")
    print("FOCUS YEAR COMPARISON (FAILURE BULL)")
    print(f"{'='*80}")
    for strategy_name in STRATEGIES:
        print(f"\n{strategy_name}:")
        for year in FAILURE_BULL:
            year_data = all_df[(all_df["strategy"] == strategy_name) & (all_df["year"] == year)]
            if len(year_data) > 0:
                print(f"  {year}:")
                for _, row in year_data.iterrows():
                    print(f"    {row['variant']:20s} excess={row['excess_return_vs_benchmark']*100:6.1f}% cash={row['avg_cash_pct']:5.1f}% n_hold={row['avg_n_holdings']:.1f}")
    
    print(f"\n{'='*80}")
    print("FOCUS YEAR COMPARISON (SUCCESS CONTRAST)")
    print(f"{'='*80}")
    for strategy_name in STRATEGIES:
        print(f"\n{strategy_name}:")
        for year in SUCCESS_CONTRAST:
            year_data = all_df[(all_df["strategy"] == strategy_name) & (all_df["year"] == year)]
            if len(year_data) > 0:
                print(f"  {year}:")
                for _, row in year_data.iterrows():
                    print(f"    {row['variant']:20s} excess={row['excess_return_vs_benchmark']*100:6.1f}% cash={row['avg_cash_pct']:5.1f}% n_hold={row['avg_n_holdings']:.1f}")
    
    baseline_bull = {}
    for strategy_name in STRATEGIES:
        for year in FAILURE_BULL:
            b = all_df[(all_df["strategy"] == strategy_name) & (all_df["variant"] == "baseline") & (all_df["year"] == year)]
            if len(b) > 0:
                baseline_bull[(strategy_name, year)] = b.iloc[0]
    
    decision_criteria = {
        "depth_only_improves_2017_2025": {},
        "sizing_only_improves_2017_2025": {},
        "depth_plus_sizing_improves_2017_2025": {},
        "reduces_cash_pct": {},
        "preserves_2022_downside_protection": {},
        "improves_mean_annualized": {},
    }
    
    for strategy_name in STRATEGIES:
        baseline_2017 = baseline_bull.get((strategy_name, 2017))
        baseline_2025 = baseline_bull.get((strategy_name, 2025))
        
        for variant in ["depth_only", "sizing_only", "depth_plus_sizing"]:
            v_2017 = all_df[(all_df["strategy"] == strategy_name) & (all_df["variant"] == variant) & (all_df["year"] == 2017)]
            v_2025 = all_df[(all_df["strategy"] == strategy_name) & (all_df["variant"] == variant) & (all_df["year"] == 2025)]
            
            improves = False
            if len(v_2017) > 0 and baseline_2017 is not None:
                if v_2017.iloc[0]["excess_return_vs_benchmark"] > baseline_2017["excess_return_vs_benchmark"]:
                    improves = True
            
            if len(v_2025) > 0 and baseline_2025 is not None:
                if v_2025.iloc[0]["excess_return_vs_benchmark"] > baseline_2025["excess_return_vs_benchmark"]:
                    improves = True
            
            decision_criteria[f"{variant}_improves_2017_2025"][strategy_name] = bool(improves)
            
            v_cash = all_df[(all_df["strategy"] == strategy_name) & (all_df["variant"] == variant) & (all_df["year"].isin(FAILURE_BULL))]
            b_cash = all_df[(all_df["strategy"] == strategy_name) & (all_df["variant"] == "baseline") & (all_df["year"].isin(FAILURE_BULL))]
            
            reduces = bool(v_cash["avg_cash_pct"].mean() < b_cash["avg_cash_pct"].mean()) if len(v_cash) > 0 and len(b_cash) > 0 else False
            decision_criteria["reduces_cash_pct"][variant] = reduces
            
            v_ann = all_df[(all_df["strategy"] == strategy_name) & (all_df["variant"] == variant)]["annualized_return"].mean()
            b_ann = all_df[(all_df["strategy"] == strategy_name) & (all_df["variant"] == "baseline")]["annualized_return"].mean()
            decision_criteria["improves_mean_annualized"][variant] = bool(v_ann > b_ann)
            
            v_2022 = all_df[(all_df["strategy"] == strategy_name) & (all_df["variant"] == variant) & (all_df["year"] == 2022)]
            b_2022 = all_df[(all_df["strategy"] == strategy_name) & (all_df["variant"] == "baseline") & (all_df["year"] == 2022)]
            
            preserves = True
            if len(v_2022) > 0 and len(b_2022) > 0:
                if v_2022.iloc[0]["total_return"] < b_2022.iloc[0]["total_return"]:
                    preserves = False
            decision_criteria["preserves_2022_downside_protection"][variant] = bool(preserves)
    
    print(f"\n{'='*80}")
    print("DECISION CRITERIA")
    print(f"{'='*80}")
    for key, vals in decision_criteria.items():
        print(f"{key}: {vals}")
    
    def convert_numpy(obj):
        if isinstance(obj, dict):
            return {k: convert_numpy(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [convert_numpy(i) for i in obj]
        elif hasattr(obj, 'item'):
            return obj.item()
        else:
            return obj
    
    summary_json = {
        "timestamp": timestamp,
        "strategies": STRATEGIES,
        "variants": list(VARIANTS.keys()),
        "focus_years": FOCUS_YEARS,
        "decision_criteria": convert_numpy(decision_criteria),
        "variant_summary": convert_numpy(summary_df.to_dict(orient="records")),
    }
    
    with open(output_dir / "summary.json", "w") as f:
        json.dump(summary_json, f, indent=2)
    print(f"Saved: summary.json")
    
    readme_content = f"""# Execution Ablation Results (CORRECTED)

Generated: {timestamp}

## Variants Tested

| Variant | candidate_scan_multiplier | sizing_mode |
|---------|--------------------------|-------------|
| baseline | 3 | fixed_initial |
| depth_only | 20 | fixed_initial |
| sizing_only | 3 | dynamic_portfolio |
| depth_plus_sizing | 20 | dynamic_portfolio |

## Definitions

- **fixed_initial**: target = initial_capital / top_k
- **dynamic_portfolio**: target = current_portfolio_value / top_k

## Canonical Engine

This ablation uses the canonical `simulate_topk_constraint_compliant()` function from backtest.py with proper params.

## Strategies Tested

- blend_70_30_top5 (signal=blend, K=5, rebal=10d)
- s1_top5_rebal10 (signal=s1_proba, K=5, rebal=10d)

## Focus Years

- Failure bull: 2017, 2025
- Success contrast: 2021, 2022
- Secondary: 2019, 2024

## Decision Criteria Results

See decision_criteria in summary.json for detailed results.

## Next Steps

This is an ablation, NOT a winner selection.
- If depth_only helps: candidate scan cap was a real bottleneck
- If sizing_only helps: fixed sizing was a real bottleneck  
- If both help: execution plumbing is fixable
- If neither helps: cash drag is deeper than scan/sizing

## Artifacts

- strategy_variant_year_metrics.csv
- strategy_variant_summary.csv
- cash_exposure_by_year.csv
- focus_year_comparison.csv
- summary.json
"""
    
    with open(output_dir / "README.md", "w") as f:
        f.write(readme_content)
    print(f"Saved: README.md")
    
    print(f"\n{'='*80}")
    print("COMPLETE")
    print(f"{'='*80}")
    print(f"Artifacts: {output_dir}")
    
    return output_dir


if __name__ == "__main__":
    main()
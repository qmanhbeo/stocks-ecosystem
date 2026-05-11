#!/usr/bin/env python3
"""
S1 Depth5 Full 11-Fold Validation
Compare s1_top5_rebal10 (baseline) vs s1_top5_rebal10_depth5 across all folds 2015-2025
"""
import json
import os
import pandas as pd
from datetime import datetime
from pathlib import Path

import backtest as bt
from strategies import loader as strategy_loader
from walk_forward_validate import run_strategy_on_fold, FOLDS, load_caches

STRATEGIES = [
    "s1_top5_rebal10",
    "s1_top5_rebal10_depth5",
]

CACHE_DIR = Path(__file__).parent / "cache"
bt.CACHE_DIR = CACHE_DIR
bt.PRICE_CACHE_FILE = CACHE_DIR / "price_cache.parquet"
bt.LIQUID_CACHE_FILE = CACHE_DIR / "liquid_lookup.joblib"
bt.TRAD_CACHE_FILE = CACHE_DIR / "trad_lookup.joblib"

def run_all_folds(liquid_lookup, trad_lookup, price_cache):
    results = {}
    for strategy in STRATEGIES:
        print(f"\n{'='*60}")
        print(f"Running {strategy} across all 11 folds")
        print(f"{'='*60}")
        
        config = strategy_loader.load_strategy_config(strategy)
        strategy_results = []
        
        for fold in FOLDS:
            fold_name = fold["name"]
            test_start = fold["test_start"]
            test_end = fold["test_end"]
            print(f"\n--- {fold_name}: {test_start} to {test_end} ---")
            
            try:
                result = run_strategy_on_fold(
                    config, fold, liquid_lookup, trad_lookup, price_cache
                )
                
                strategy_results.append({
                    "fold_name": fold["name"],
                    "test_start": fold["test_start"],
                    "test_end": fold["test_end"],
                    "total_return": result.get("total_return", 0),
                    "annualized_return": result.get("annualized_return", 0),
                    "sharpe": result.get("sharpe", 0),
                    "max_drawdown": result.get("max_drawdown", 0),
                    "n_trades": result.get("n_trades", 0),
                    "n_filtered": result.get("n_filtered", 0),
                    "benchmark_return": result.get("benchmark_return", None),
                    "excess_return": result.get("excess_return_vs_benchmark", None),
                })
                excess_val = result.get('excess_return_vs_benchmark')
                excess_str = f"{excess_val*100:.2f}%" if excess_val is not None else "N/A"
                print(f"  Return: {result.get('total_return', 0)*100:.2f}%, Trades: {result.get('n_trades', 0)}, Excess: {excess_str}")
            except Exception as e:
                print(f"  FAILED: {e}")
                strategy_results.append({
                    "fold_name": fold["name"],
                    "test_start": fold["test_start"],
                    "test_end": fold["test_end"],
                    "total_return": None,
                    "annualized_return": None,
                    "sharpe": None,
                    "max_drawdown": None,
                    "n_trades": None,
                    "n_filtered": None,
                    "benchmark_return": None,
                    "excess_return": None,
                })
        
        results[strategy] = strategy_results
    
    return results

def generate_artifacts(results):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    artifact_dir = Path(f"artifacts/s1_depth5_validation_walkforward/{timestamp}")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n📁 Artifact directory: {artifact_dir}")

    baseline = pd.DataFrame(results["s1_top5_rebal10"])
    depth5 = pd.DataFrame(results["s1_top5_rebal10_depth5"])

    baseline["strategy"] = "s1_top5_rebal10"
    depth5["strategy"] = "s1_top5_rebal10_depth5"

    combined = pd.concat([baseline, depth5], ignore_index=True)
    combined.to_csv(artifact_dir / "fold_metrics.csv", index=False)
    print(f"✅ Saved fold_metrics.csv")

    summary_data = []
    for strategy in STRATEGIES:
        strat_df = pd.DataFrame(results[strategy])
        valid_returns = strat_df["total_return"].dropna()
        valid_excess = strat_df["excess_return"].dropna()
        valid_ann = strat_df["annualized_return"].dropna()
        valid_dd = strat_df["max_drawdown"].dropna()

        summary_data.append({
            "strategy": strategy,
            "mean_annualized_return": valid_ann.mean() if len(valid_ann) > 0 else None,
            "median_annualized_return": valid_ann.median() if len(valid_ann) > 0 else None,
            "mean_total_return": valid_returns.mean() if len(valid_returns) > 0 else None,
            "positive_folds": int((valid_returns > 0).sum()),
            "total_folds": len(valid_returns),
            "beats_benchmark": int((valid_excess > 0).sum()) if len(valid_excess) > 0 else 0,
            "mean_excess_return": valid_excess.mean() if len(valid_excess) > 0 else None,
            "max_drawdown_mean": valid_dd.mean() if len(valid_dd) > 0 else None,
            "total_trades": int(strat_df["n_trades"].sum()),
            "total_filtered": int(strat_df["n_filtered"].sum()),
        })

    summary_df = pd.DataFrame(summary_data)
    summary_df.to_csv(artifact_dir / "strategy_summary.csv", index=False)
    print(f"✅ Saved strategy_summary.csv")

    comparison = baseline.merge(depth5, on="fold_name", suffixes=("_baseline", "_depth5"))
    keep_cols = ["fold_name", "total_return_baseline", "total_return_depth5",
                 "benchmark_return_baseline", "excess_return_baseline", "excess_return_depth5"]
    available_cols = [c for c in keep_cols if c in comparison.columns]
    comparison = comparison[available_cols]
    comparison["delta_total"] = comparison["total_return_depth5"] - comparison["total_return_baseline"]
    comparison["delta_excess"] = comparison["excess_return_depth5"] - comparison["excess_return_baseline"]
    comparison["depth5_improved"] = comparison["delta_total"] > 0
    comparison.to_csv(artifact_dir / "baseline_vs_depth5_by_year.csv", index=False)
    print(f"✅ Saved baseline_vs_depth5_by_year.csv")

    summary_json = {
        "timestamp": timestamp,
        "strategies": STRATEGIES,
        "folds": [f["name"] for f in FOLDS],
        "summary": summary_data,
        "comparison": comparison.to_dict(orient="records"),
    }
    with open(artifact_dir / "summary.json", "w") as f:
        json.dump(summary_json, f, indent=2, default=str)
    print(f"✅ Saved summary.json")

    with open(artifact_dir / "README.md", "w") as f:
        f.write(f"# S1 Depth5 Full 11-Fold Validation\n\n")
        f.write(f"**Timestamp:** {timestamp}\n\n")
        f.write(f"## Strategies Compared\n")
        for s in STRATEGIES:
            f.write(f"- {s}\n")
        f.write(f"\n## Folds: 2015-2025 ({len(FOLDS)} folds)\n")
        f.write(f"\n## Summary Statistics\n\n")
        f.write(summary_df.to_markdown(index=False))
        f.write(f"\n\n## Year-by-Year Comparison\n\n")
        f.write(comparison.to_markdown(index=False))
        f.write(f"\n\n## Decision Rules Applied\n")
        f.write("1. If depth5 improves mean annualized return AND does not reduce positive folds AND does not materially worsen downside years -> VALIDATED_CANDIDATE\n")
        f.write("2. If depth5 only helps selected years but worsens broader folds -> FOCUS_YEAR_OVERFIT\n")
        f.write("3. If depth5 improves return but increases drawdown materially -> RISK_TRADEOFF\n")
    print(f"✅ Saved README.md")

    return artifact_dir, summary_df, comparison

if __name__ == "__main__":
    print("="*60)
    print("S1 DEPTH5 FULL 11-FOLD VALIDATION")
    print("Comparing baseline vs depth5 across all folds 2015-2025")
    print("="*60)

    print("\nLoading caches...")
    liquid_lookup, trad_lookup, price_cache = load_caches()
    print("✅ Caches loaded")

    results = run_all_folds(liquid_lookup, trad_lookup, price_cache)
    artifact_dir, summary_df, comparison = generate_artifacts(results)

    print("\n" + "="*60)
    print("VALIDATION RESULT")
    print("="*60)
    print("\n📊 Strategy Summary:")
    print(summary_df.to_string(index=False))
    print("\n📅 Year-by-Year Comparison:")
    print(comparison[["fold_name", "total_return_baseline", "total_return_depth5", "delta_total", "depth5_improved"]].to_string(index=False))

    baseline_ann = summary_df[summary_df["strategy"] == "s1_top5_rebal10"]["mean_annualized_return"].values[0]
    depth5_ann = summary_df[summary_df["strategy"] == "s1_top5_rebal10_depth5"]["mean_annualized_return"].values[0]
    baseline_pos = summary_df[summary_df["strategy"] == "s1_top5_rebal10"]["positive_folds"].values[0]
    depth5_pos = summary_df[summary_df["strategy"] == "s1_top5_rebal10_depth5"]["positive_folds"].values[0]

    print(f"\n🎯 Key Metrics:")
    print(f"  Baseline mean annualized: {baseline_ann*100:.2f}%")
    print(f"  Depth5 mean annualized:   {depth5_ann*100:.2f}%")
    print(f"  Delta:                    {(depth5_ann - baseline_ann)*100:.2f}%")
    print(f"  Baseline positive folds:  {baseline_pos}/11")
    print(f"  Depth5 positive folds:   {depth5_pos}/11")

    improved_folds = comparison["depth5_improved"].sum()
    print(f"  Depth5 improved in:      {improved_folds}/11 folds")

    print(f"\n📁 Artifacts: {artifact_dir}")
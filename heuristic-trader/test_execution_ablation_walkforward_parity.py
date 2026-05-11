"""
Baseline parity guardrail: compare original vs explicit baseline via canonical walk-forward.

Uses the same walk_forward_validate.py harness, not a custom loop.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import json

import walk_forward_validate as wfv
import strategies.loader as loader
import backtest as bt


def run_fold_comparison(strategy_a: str, strategy_b: str, folds: list) -> dict:
    """Compare two strategies across all folds using canonical walk-forward logic."""
    
    config_a = loader.load_strategy_config(strategy_a)
    config_b = loader.load_strategy_config(strategy_b)
    
    liquid_lookup = bt.load_liquid_lookup()
    trad_lookup = bt.load_trad_lookup()
    price_cache = bt.load_price_cache()
    
    results_a = []
    results_b = []
    
    for fold in folds:
        print(f"\n  Fold: {fold['name']}")
        
        # Run both strategies on the same fold
        metrics_a = wfv.run_strategy_on_fold(config_a, fold, liquid_lookup, trad_lookup, price_cache)
        metrics_b = wfv.run_strategy_on_fold(config_b, fold, liquid_lookup, trad_lookup, price_cache)
        
        results_a.append(metrics_a)
        results_b.append(metrics_b)
    
    # Compare metrics
    comparison = []
    for i, (a, b) in enumerate(zip(results_a, results_b)):
        fold_name = a.get("fold_name", f"fold_{i}")
        
        diff_return = abs(a.get("total_return", 0) - b.get("total_return", 0))
        diff_ann = abs(a.get("annualized_return", 0) - b.get("annualized_return", 0))
        diff_sharpe = abs(a.get("sharpe", 0) - b.get("sharpe", 0))
        diff_dd = abs(a.get("max_drawdown", 0) - b.get("max_drawdown", 0))
        diff_trades = abs(a.get("n_trades", 0) - b.get("n_trades", 0))
        diff_filtered = abs(a.get("n_filtered", 0) - b.get("n_filtered", 0))
        
        passed = (
            diff_return <= 1e-9 and
            diff_ann <= 1e-9 and
            diff_sharpe <= 1e-9 and
            diff_dd <= 1e-9 and
            diff_trades == 0 and
            diff_filtered == 0
        )
        
        comparison.append({
            "fold": fold_name,
            "a_total_return": a.get("total_return"),
            "b_total_return": b.get("total_return"),
            "diff_total_return": diff_return,
            "diff_annualized_return": diff_ann,
            "diff_sharpe": diff_sharpe,
            "diff_max_drawdown": diff_dd,
            "diff_n_trades": diff_trades,
            "diff_n_filtered": diff_filtered,
            "passed": passed,
        })
        
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"    {status}: diff_return={diff_return:.2e}, diff_trades={diff_trades}")
    
    all_passed = all(c["passed"] for c in comparison)
    
    return {
        "strategy_a": strategy_a,
        "strategy_b": strategy_b,
        "folds": comparison,
        "all_passed": all_passed,
    }


def main():
    print("=" * 80)
    print("BASELINE PARITY TEST: Original vs Explicit Baseline")
    print("Using canonical walk-forward path")
    print("=" * 80)
    
    # Define folds
    folds = [
        {"name": f"fold_{year}", "train_start": f"{year-3}-01-01", "train_end": f"{year-1}-12-31", "test_start": f"{year}-01-01", "test_end": f"{year}-12-31"}
        for year in [2017, 2019, 2021, 2022, 2024, 2025]
    ]
    
    all_results = []
    
    # Test 1: blend_70_30_top5 vs blend_70_30_top5_baseline_explicit
    print(f"\n{'='*60}")
    print("Test 1: blend_70_30_top5 vs blend_70_30_top5_baseline_explicit")
    print(f"{'='*60}")
    
    result1 = run_fold_comparison("blend_70_30_top5", "blend_70_30_top5_baseline_explicit", folds)
    all_results.append(result1)
    
    # Test 2: s1_top5_rebal10 vs s1_top5_rebal10_baseline_explicit
    print(f"\n{'='*60}")
    print("Test 2: s1_top5_rebal10 vs s1_top5_rebal10_baseline_explicit")
    print(f"{'='*60}")
    
    result2 = run_fold_comparison("s1_top5_rebal10", "s1_top5_rebal10_baseline_explicit", folds)
    all_results.append(result2)
    
    # Summary
    print(f"\n{'='*80}")
    print("OVERALL RESULTS")
    print(f"{'='*80}")
    
    for r in all_results:
        status = "✅ PASSED" if r["all_passed"] else "❌ FAILED"
        print(f"{r['strategy_a']} vs {r['strategy_b']}: {status}")
    
    all_passed = all(r["all_passed"] for r in all_results)
    
    print(f"\n{'='*80}")
    if all_passed:
        print("OVERALL: ✅ ALL PARITY TESTS PASSED")
    else:
        print("OVERALL: ❌ SOME PARITY TESTS FAILED")
    print(f"{'='*80}")
    
    return all_passed


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
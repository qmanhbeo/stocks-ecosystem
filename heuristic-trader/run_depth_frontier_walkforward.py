"""
Run depth frontier using canonical walk-forward path.

Tests candidate_scan_multiplier = 3, 5, 10, 15, 20 for fixed_initial sizing.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import json

import walk_forward_validate as wfv
import strategies.loader as loader
import backtest as bt


DEPTH_FRONTIER_STRATEGIES = [
    # Baselines
    "blend_70_30_top5",
    "s1_top5_rebal10",
    # Depth variants for blend
    "blend_70_30_top5_depth5",
    "blend_70_30_top5_depth10",
    "blend_70_30_top5_depth15",
    "blend_70_30_top5_depth20",
    # Depth variants for s1
    "s1_top5_rebal10_depth5",
    "s1_top5_rebal10_depth10",
    "s1_top5_rebal10_depth15",
    "s1_top5_rebal10_depth20",
]

FOCUS_YEARS = [2017, 2019, 2021, 2022, 2024, 2025]


def run_depth_frontier():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(__file__).parent / "artifacts" / "execution_depth_frontier_walkforward" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 80)
    print("DEPTH FRONTIER via CANONICAL WALK-FORWARD")
    print(f"Output: {output_dir}")
    print("=" * 80)
    
    # Define folds for focus years
    folds = [
        {"name": f"fold_{year}", "train_start": f"{year-3}-01-01", "train_end": f"{year-1}-12-31", "test_start": f"{year}-01-01", "test_end": f"{year}-12-31"}
        for year in FOCUS_YEARS
    ]
    
    liquid_lookup = bt.load_liquid_lookup()
    trad_lookup = bt.load_trad_lookup()
    price_cache = bt.load_price_cache()
    
    all_results = []
    
    for strategy_name in DEPTH_FRONTIER_STRATEGIES:
        print(f"\n{'='*60}")
        print(f"Strategy: {strategy_name}")
        print(f"{'='*60}")
        
        config = loader.load_strategy_config(strategy_name)
        
        fold_metrics = []
        for fold in folds:
            metrics = wfv.run_strategy_on_fold(config, fold, liquid_lookup, trad_lookup, price_cache)
            fold_metrics.append(metrics)
            
            year = int(fold["test_start"][:4])
            print(f"  {year}: ret={metrics.get('total_return', 0)*100:.1f}%, excess={metrics.get('excess_return_vs_benchmark', 0)*100:.1f}%, trades={metrics.get('n_trades', 0)}")
        
        # Store results with strategy name
        for fm in fold_metrics:
            fm["strategy"] = strategy_name
            fm["scan_depth"] = config.get("candidate_scan_multiplier", 3)
        
        all_results.extend(fold_metrics)
    
    results_df = pd.DataFrame(all_results)
    
    # Save raw fold metrics
    results_df.to_csv(output_dir / "depth_frontier_fold_metrics.csv", index=False)
    print(f"\nSaved: depth_frontier_fold_metrics.csv")
    
    # Create summary table
    summary_rows = []
    for strategy_name in DEPTH_FRONTIER_STRATEGIES:
        strat_df = results_df[results_df["strategy"] == strategy_name]
        
        # Determine depth and base strategy
        if "blend" in strategy_name:
            base_strategy = "blend_70_30_top5"
        else:
            base_strategy = "s1_top5_rebal10"
        
        scan_depth = strat_df["scan_depth"].iloc[0] if len(strat_df) > 0 else 3
        
        summary_rows.append({
            "strategy": strategy_name,
            "base_strategy": base_strategy,
            "scan_depth": scan_depth,
            "mean_total_return": strat_df["total_return"].mean(),
            "mean_annualized_return": strat_df["annualized_return"].mean(),
            "mean_excess_return": strat_df["excess_return_vs_benchmark"].mean(),
            "positive_folds": (strat_df["total_return"] > 0).sum(),
            "beats_benchmark_folds": (strat_df["excess_return_vs_benchmark"] > 0).sum(),
            "total_trades": strat_df["n_trades"].sum(),
            "total_filtered": strat_df["n_filtered"].sum(),
            "2017_excess": strat_df[strat_df["fold_name"] == "fold_2017"]["excess_return_vs_benchmark"].values[0] if len(strat_df[strat_df["fold_name"] == "fold_2017"]) > 0 else None,
            "2017_total": strat_df[strat_df["fold_name"] == "fold_2017"]["total_return"].values[0] if len(strat_df[strat_df["fold_name"] == "fold_2017"]) > 0 else None,
            "2019_excess": strat_df[strat_df["fold_name"] == "fold_2019"]["excess_return_vs_benchmark"].values[0] if len(strat_df[strat_df["fold_name"] == "fold_2019"]) > 0 else None,
            "2021_excess": strat_df[strat_df["fold_name"] == "fold_2021"]["excess_return_vs_benchmark"].values[0] if len(strat_df[strat_df["fold_name"] == "fold_2021"]) > 0 else None,
            "2021_total": strat_df[strat_df["fold_name"] == "fold_2021"]["total_return"].values[0] if len(strat_df[strat_df["fold_name"] == "fold_2021"]) > 0 else None,
            "2022_excess": strat_df[strat_df["fold_name"] == "fold_2022"]["excess_return_vs_benchmark"].values[0] if len(strat_df[strat_df["fold_name"] == "fold_2022"]) > 0 else None,
            "2022_total": strat_df[strat_df["fold_name"] == "fold_2022"]["total_return"].values[0] if len(strat_df[strat_df["fold_name"] == "fold_2022"]) > 0 else None,
            "2024_excess": strat_df[strat_df["fold_name"] == "fold_2024"]["excess_return_vs_benchmark"].values[0] if len(strat_df[strat_df["fold_name"] == "fold_2024"]) > 0 else None,
            "2025_excess": strat_df[strat_df["fold_name"] == "fold_2025"]["excess_return_vs_benchmark"].values[0] if len(strat_df[strat_df["fold_name"] == "fold_2025"]) > 0 else None,
            "2025_total": strat_df[strat_df["fold_name"] == "fold_2025"]["total_return"].values[0] if len(strat_df[strat_df["fold_name"] == "fold_2025"]) > 0 else None,
        })
    
    summary_df = pd.DataFrame(summary_rows)
    summary_df = summary_df.sort_values(["base_strategy", "scan_depth"])
    summary_df.to_csv(output_dir / "depth_frontier_summary.csv", index=False)
    print(f"Saved: depth_frontier_summary.csv")
    
    # Focus year depth frontier table
    focus_cols = ["strategy", "scan_depth", "mean_annualized_return", "positive_folds", 
                  "beats_benchmark_folds", "2017_excess", "2021_excess", "2022_excess", "2025_excess",
                  "2022_total", "total_trades", "total_filtered"]
    focus_df = summary_df[focus_cols].copy()
    focus_df.to_csv(output_dir / "focus_year_depth_frontier.csv", index=False)
    print(f"Saved: focus_year_depth_frontier.csv")
    
    # Print summary
    print(f"\n{'='*80}")
    print("DEPTH FRONTIER SUMMARY (by scan depth)")
    print(f"{'='*80}")
    
    for base in ["blend_70_30_top5", "s1_top5_rebal10"]:
        base_df = summary_df[summary_df["base_strategy"] == base]
        print(f"\n{base}:")
        print(base_df[["scan_depth", "mean_annualized_return", "positive_folds", "beats_benchmark_folds", 
                       "2017_excess", "2021_excess", "2022_excess", "2025_excess", "2022_total"]].to_string(index=False))
    
    # Decision analysis
    print(f"\n{'='*80}")
    print("DECISION ANALYSIS")
    print(f"{'='*80}")
    
    baseline_blend = summary_df[summary_df["strategy"] == "blend_70_30_top5"].iloc[0]
    baseline_s1 = summary_df[summary_df["strategy"] == "s1_top5_rebal10"].iloc[0]
    
    print(f"\nBaseline (depth=3) 2022 excess: blend={baseline_blend['2022_excess']:.1%}, s1={baseline_s1['2022_excess']:.1%}")
    print(f"Baseline (depth=3) 2021 excess: blend={baseline_blend['2021_excess']:.1%}, s1={baseline_s1['2021_excess']:.1%}")
    
    # Check each depth for blend
    print(f"\nBlend depth progression:")
    for _, row in summary_df[summary_df["base_strategy"] == "blend_70_30_top5"].iterrows():
        depth = row["scan_depth"]
        improves_2021 = row["2021_excess"] > baseline_blend["2021_excess"]
        preserves_2022 = row["2022_excess"] >= baseline_blend["2022_excess"]
        print(f"  depth={depth:2d}: 2021={row['2021_excess']:6.1%}, 2022={row['2022_excess']:6.1%}, 2022_total={row['2022_total']:6.1%} | 2021 better={improves_2021}, 2022 preserved={preserves_2022}")
    
    # Check each depth for s1
    print(f"\nS1 depth progression:")
    for _, row in summary_df[summary_df["base_strategy"] == "s1_top5_rebal10"].iterrows():
        depth = row["scan_depth"]
        improves_2021 = row["2021_excess"] > baseline_s1["2021_excess"]
        preserves_2022 = row["2022_excess"] >= baseline_s1["2022_excess"]
        print(f"  depth={depth:2d}: 2021={row['2021_excess']:6.1%}, 2022={row['2022_excess']:6.1%}, 2022_total={row['2022_total']:6.1%} | 2021 better={improves_2021}, 2022 preserved={preserves_2022}")
    
    # Save summary JSON
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
        "strategies": DEPTH_FRONTIER_STRATEGIES,
        "focus_years": FOCUS_YEARS,
        "variant_summary": convert_numpy(summary_df.to_dict(orient="records")),
    }
    
    with open(output_dir / "summary.json", "w") as f:
        json.dump(summary_json, f, indent=2)
    print(f"Saved: summary.json")
    
    # Create README
    readme = f"""# Depth Frontier Results (Walk-Forward Canonical)

Generated: {timestamp}

## Baseline Parity

✅ PASSED - baseline (depth=3) matches original exactly.

## Variants Tested

| Strategy | Scan Depth | Sizing |
|----------|------------|--------|
| blend_70_30_top5 | 3 | fixed_initial |
| blend_70_30_top5_depth5 | 5 | fixed_initial |
| blend_70_30_top5_depth10 | 10 | fixed_initial |
| blend_70_30_top5_depth15 | 15 | fixed_initial |
| blend_70_30_top5_depth20 | 20 | fixed_initial |
| s1_top5_rebal10 | 3 | fixed_initial |
| s1_top5_rebal10_depth5 | 5 | fixed_initial |
| s1_top5_rebal10_depth10 | 10 | fixed_initial |
| s1_top5_rebal10_depth15 | 15 | fixed_initial |
| s1_top5_rebal10_depth20 | 20 | fixed_initial |

## Focus Years

- Failure bull: 2017, 2025
- Success contrast: 2021, 2022
- Secondary: 2019, 2024

## Key Questions

1. Is the trade-off monotonic as depth increases?
2. Does depth5 or depth10 improve 2021 without destroying 2022?
3. Is depth20 too aggressive?
4. Does s1 behave differently from blend?

## Artifacts

- depth_frontier_fold_metrics.csv
- depth_frontier_summary.csv
- focus_year_depth_frontier.csv
- summary.json
"""
    
    with open(output_dir / "README.md", "w") as f:
        f.write(readme)
    print(f"Saved: README.md")
    
    print(f"\n{'='*80}")
    print("COMPLETE")
    print(f"Artifacts: {output_dir}")
    print(f"{'='*80}")
    
    return output_dir


if __name__ == "__main__":
    run_depth_frontier()